from __future__ import annotations

import argparse
import json
import sys

from .capabilities import capabilities_json, probe_capabilities
from .errors import PathfinderError, StateError
from .migrations import migrate_intent, migrate_mission
from .storage import MissionStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pathfinder_core")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect capabilities without writes")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    mission = commands.add_parser("mission", help="inspect controller mission state")
    mission_commands = mission.add_subparsers(dest="mission_command", required=True)
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
