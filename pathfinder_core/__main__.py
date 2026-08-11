from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .artifacts import write_saved_prompt_goal
from .capabilities import capabilities_json, probe_capabilities
from .errors import PathfinderError, StateError
from .migrations import migrate_intent, migrate_mission
from .mission_host import HostMissionController
from .storage import MissionStore, read_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pathfinder_core")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect capabilities without writes")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    mission = commands.add_parser("mission", help="inspect controller mission state")
    mission_commands = mission.add_subparsers(dest="mission_command", required=True)
    start = mission_commands.add_parser("start", help="initialize a local host-driven mission")
    start.add_argument("--state-dir", required=True)
    start.add_argument("--goal-binding", required=True)
    start.add_argument("--authorization", required=True)
    start.add_argument("--runtime-boundary", required=True)
    start.add_argument(
        "--protected-policy",
        help="explicit additive protected-surface policy JSON",
    )
    start.add_argument("--json", action="store_true", dest="as_json")
    next_action = mission_commands.add_parser("next", help="return the next journaled host action")
    next_action.add_argument("--state-dir", required=True)
    next_action.add_argument("--json", action="store_true", dest="as_json")
    record = mission_commands.add_parser("record", help="record one typed host receipt")
    record.add_argument("--state-dir", required=True)
    record.add_argument("--receipt-file", required=True)
    record.add_argument("--json", action="store_true", dest="as_json")
    resume = mission_commands.add_parser("resume", help="resume without replaying pending work")
    resume.add_argument("--state-dir", required=True)
    resume.add_argument("--json", action="store_true", dest="as_json")
    status = mission_commands.add_parser("status", help="show current mission state")
    status.add_argument("--state-dir", required=True)
    status.add_argument("--json", action="store_true", dest="as_json")
    abandon = mission_commands.add_parser("abandon", help="mark an active mission abandoned")
    abandon.add_argument("--state-dir", required=True)
    abandon.add_argument("--json", action="store_true", dest="as_json")
    migrate = commands.add_parser("migrate", help="back up and migrate local Pathfinder state")
    migrate_commands = migrate.add_subparsers(dest="migrate_command", required=True)
    migrate_intent_parser = migrate_commands.add_parser("intent", help="migrate .pathfinder intent files")
    migrate_intent_parser.add_argument("--root", required=True)
    migrate_intent_parser.add_argument("--backup-dir", required=True)
    migrate_intent_parser.add_argument("--json", action="store_true", dest="as_json")
    migrate_mission_parser = migrate_commands.add_parser("mission", help="migrate a mission state directory")
    migrate_mission_parser.add_argument("--state-dir", required=True)
    migrate_mission_parser.add_argument("--backup-dir", required=True)
    migrate_mission_parser.add_argument("--json", action="store_true", dest="as_json")
    artifacts = commands.add_parser("artifacts", help="write controller-owned artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)
    goal_saved = artifact_commands.add_parser(
        "goal-saved", help="write canonical sidecars for a saved prompt Goal"
    )
    goal_saved.add_argument("--repo-root", required=True)
    goal_saved.add_argument("--output-dir", required=True)
    goal_saved.add_argument("--request-file", required=True)
    goal_saved.add_argument("--consume-request", action="store_true")
    goal_saved.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _doctor(as_json: bool) -> int:
    if as_json:
        print(capabilities_json())
        return 0
    report = probe_capabilities()
    print(f"runner_available: {str(report['runner_available']).lower()}")
    print(
        "unattended_execution_eligible: "
        f"{str(report['unattended_execution_eligible']).lower()}"
    )
    for name, capability in report["capabilities"].items():
        print(f"{name}: {capability['status']} — {capability['detail']}")
    return 0


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "doctor":
            return _doctor(args.as_json)
        if args.command == "mission" and args.mission_command == "status":
            state = MissionStore(args.state_dir).load()
            if args.as_json:
                print(json.dumps(state, indent=2, sort_keys=True))
            else:
                print(f"mission: {state['mission_id']}")
                print(f"state: {state['state']}")
                print(f"goal: {state['goal_id']}")
                print(f"branch: {state['branch_name'] or 'not prepared'}")
                print(f"pull_request: {state['pr_url'] or 'none'}")
            return 0
        if args.command == "mission" and args.mission_command == "start":
            state = HostMissionController(args.state_dir).start(
                binding=read_json(Path(args.goal_binding)),
                authorization=read_json(Path(args.authorization)),
                runtime_boundary=read_json(Path(args.runtime_boundary)),
                protected_policy=(
                    read_json(Path(args.protected_policy))
                    if args.protected_policy else None
                ),
            )
            if args.as_json:
                print(json.dumps(state, indent=2, sort_keys=True))
            else:
                print(f"mission: {state['mission_id']}")
                print(f"state: {state['state']}")
                print(f"attempt: {state['attempt_id']}")
                print("publication: local-only")
            return 0
        if args.command == "mission" and args.mission_command in {"next", "resume"}:
            result = HostMissionController(args.state_dir).next()
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"status: {result['status']}")
                if result["status"] == "action-required":
                    print(f"action: {result['action']['action_kind']}")
                    print(f"operation: {result['action']['operation_id']}")
                elif result.get("operation_id"):
                    print(f"operation: {result['operation_id']}")
            return 0
        if args.command == "mission" and args.mission_command == "record":
            result = HostMissionController(args.state_dir).record(
                read_json(Path(args.receipt_file))
            )
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"status: {result['status']}")
                print(f"operation: {result['operation_id']}")
                print(f"state: {result['state']['state']}")
            return 0
        if args.command == "mission" and args.mission_command == "abandon":
            store = MissionStore(args.state_dir)
            state = store.load()
            if state["state"] in {"awaiting-review", "merged", "blocked", "abandoned"}:
                raise StateError(f"cannot abandon terminal mission in {state['state']}")
            state = store.move("abandoned", attempt_id=state.get("attempt_id"))
            if args.as_json:
                print(json.dumps(state, indent=2, sort_keys=True))
            else:
                print(f"mission: {state['mission_id']}")
                print("state: abandoned")
            return 0
        if args.command == "migrate":
            if args.migrate_command == "intent":
                result = migrate_intent(args.root, args.backup_dir)
            else:
                result = migrate_mission(args.state_dir, args.backup_dir)
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"migration: {result['kind']} schema v{result['schema_version']}")
                print(f"changed: {', '.join(result['changed']) or 'none'}")
                print(f"backup: {result['backup_dir']}")
            return 0
        if args.command == "artifacts" and args.artifact_command == "goal-saved":
            result = write_saved_prompt_goal(
                args.repo_root,
                args.output_dir,
                args.request_file,
                consume_request=args.consume_request,
            )
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"mission: {result['mission_id']}")
                print(f"goal: {result['goal_id']}")
                print(f"binding: {result['binding_id']}")
                for path in result["artifacts"]:
                    print(f"artifact: {path}")
            return 0
        return 2
    except PathfinderError as error:
        print(error.as_json(), file=sys.stderr)
        return error.exit_code
    except Exception as error:  # keep CLI failures concise and machine-readable
        print(
            json.dumps({"error": {"code": "internal_error", "message": str(error)}}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
