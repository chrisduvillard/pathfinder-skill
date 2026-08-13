import copy
import json
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from pathfinder_core.__main__ import main
from pathfinder_core.errors import StateError
from pathfinder_core.goal_pack import GoalPackController
from pathfinder_core.mission_host import document_sha256

from tests.integration.test_one_goal_mission import (
    BOUNDARY,
    COMMIT,
    HASH,
    NOW,
    goal_binding,
    host_receipt,
    write_document,
)


def pack_bindings(count=2):
    result = []
    for position in range(1, count + 1):
        binding = copy.deepcopy(goal_binding())
        suffix = f"packgoal{position:02d}"
        binding.update(
            mission_id=f"mission_{suffix}",
            goal_id=f"goal_{suffix}",
            binding_id=f"binding_{suffix}",
            objective=f"complete bounded pack goal {position}",
        )
        result.append(binding)
    return result


def pack_authorization(bindings):
    return {
        "schema_version": 1,
        "authorization_id": "authorization_pack1234",
        "pack_id": "pack_12345678",
        "explicit_request": True,
        "trusted_source": "current-user-turn",
        "authorized_at": NOW,
        "base_commit": COMMIT,
        "intent_hashes": {
            "charter": HASH,
            "roadmap": HASH,
            "doctrine": HASH,
        },
        "goal_bindings": [
            {
                "position": position,
                "mission_id": binding["mission_id"],
                "binding_id": binding["binding_id"],
                "goal_id": binding["goal_id"],
                "sha256": document_sha256(binding),
            }
            for position, binding in enumerate(bindings, 1)
        ],
        "limits": {
            "max_goals": len(bindings),
            "max_attempts_per_goal": 2,
            "max_wall_seconds": 3600,
            "max_total_prs": 0,
        },
        "publication_target": "local-branch",
        "snapshot_sha256": HASH,
    }


class GoalPackMissionTests(unittest.TestCase):
    def start(self, directory, *, bindings=None, authorization=None, clock=lambda: NOW):
        bindings = bindings or pack_bindings()
        authorization = authorization or pack_authorization(bindings)
        controller = GoalPackController(Path(directory) / "pack", clock=clock)
        state = controller.start(
            bindings=bindings,
            authorization=authorization,
            runtime_boundary=BOUNDARY,
        )
        return controller, state

    def advance_active_goal(self, controller):
        actions = []
        for _step in range(6):
            result = controller.next()
            self.assertEqual(result["status"], "action-required")
            actions.append(result["action"]["action_kind"])
            controller.record(host_receipt(result["action"]))
        return actions

    def test_start_persists_an_ordered_hash_bound_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            bindings = pack_bindings(3)
            controller, state = self.start(directory, bindings=bindings)
            self.assertEqual(state["state"], "authorized")
            self.assertEqual(state["current_goal_index"], 0)
            self.assertEqual(
                [item["status"] for item in state["goals"]],
                ["active", "queued", "queued"],
            )
            self.assertEqual(
                [item["binding_sha256"] for item in state["goals"]],
                [document_sha256(binding) for binding in bindings],
            )
            self.assertFalse((controller.root / "goals" / "0001" / "state.json").exists())
            for position, binding in enumerate(bindings, 1):
                path = controller.contracts_path / "goals" / f"{position:04d}.json"
                self.assertEqual(json.loads(path.read_text()), binding)
                self.assertEqual(path.stat().st_mode & 0o222, 0)

    def test_pack_start_rejects_non_git_goal_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            bindings = pack_bindings()
            for binding in bindings:
                binding["schema_version"] = 2
                binding["scope"].update(
                    repository_kind="non-git",
                    base_commit=None,
                    dirty_policy="not-applicable",
                )
            authorization = pack_authorization(bindings)
            with self.assertRaisesRegex(StateError, "require Git Goal Bindings"):
                self.start(
                    directory,
                    bindings=bindings,
                    authorization=authorization,
                )

    def test_start_is_idempotent_and_rejects_contract_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            bindings = pack_bindings()
            controller, first = self.start(directory, bindings=bindings)
            second = GoalPackController(controller.root, clock=lambda: NOW).start(
                bindings=bindings,
                authorization=pack_authorization(bindings),
                runtime_boundary=BOUNDARY,
            )
            self.assertEqual(first, second)
            changed = pack_bindings()
            changed[0]["objective"] = "different queued objective"
            with self.assertRaisesRegex(StateError, "binding hash|different persisted"):
                GoalPackController(controller.root).start(
                    bindings=changed,
                    authorization=pack_authorization(changed),
                    runtime_boundary=BOUNDARY,
                )

    def test_pack_rejects_unbound_reordered_or_duplicate_goals_before_state(self):
        for mutation, message in (
            ("hash", "binding hash"),
            ("order", "ordered Goal Binding"),
            ("duplicate", "unique"),
        ):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                bindings = pack_bindings()
                authorization = pack_authorization(bindings)
                if mutation == "hash":
                    authorization["goal_bindings"][0]["sha256"] = "f" * 64
                elif mutation == "order":
                    authorization["goal_bindings"].reverse()
                else:
                    bindings[1]["goal_id"] = bindings[0]["goal_id"]
                    authorization = pack_authorization(bindings)
                controller = GoalPackController(Path(directory) / "pack")
                with self.assertRaisesRegex(StateError, message):
                    controller.start(
                        bindings=bindings,
                        authorization=authorization,
                        runtime_boundary=BOUNDARY,
                    )
                self.assertFalse(controller.state_path.exists())

    def test_pack_runs_one_native_goal_at_a_time_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            expected = [
                "prepare-worktree", "activate-goal", "implement",
                "verify", "commit", "complete-goal",
            ]
            self.assertEqual(self.advance_active_goal(controller), expected)
            first_child = controller.root / "goals" / "0001"
            second_child = controller.root / "goals" / "0002"
            self.assertEqual(
                json.loads((first_child / "state.json").read_text())["state"],
                "awaiting-review",
            )
            self.assertFalse((second_child / "state.json").exists())

            advanced = GoalPackController(controller.root, clock=lambda: NOW).next()
            self.assertEqual(advanced["status"], "goal-advanced")
            self.assertEqual(
                [item["status"] for item in advanced["state"]["goals"]],
                ["completed", "active"],
            )
            self.assertFalse((second_child / "state.json").exists())

            resumed = GoalPackController(controller.root, clock=lambda: NOW)
            first_second_goal_action = resumed.next()
            self.assertEqual(first_second_goal_action["action"]["action_kind"], "prepare-worktree")
            resumed.record(host_receipt(first_second_goal_action["action"]))
            for _step in range(5):
                result = resumed.next()
                resumed.record(host_receipt(result["action"]))
            terminal = GoalPackController(controller.root, clock=lambda: NOW).next()
            self.assertEqual(terminal["status"], "terminal")
            self.assertEqual(terminal["state"]["state"], "awaiting-review")
            self.assertEqual(
                [item["status"] for item in terminal["state"]["goals"]],
                ["completed", "completed"],
            )

    def test_interrupted_queue_advance_retries_without_starting_the_next_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            self.advance_active_goal(controller)
            from pathfinder_core import goal_pack

            original = goal_pack.write_atomic

            def interrupt_state(path, document):
                if Path(path) == controller.state_path:
                    raise RuntimeError("simulated queue checkpoint crash")
                return original(path, document)

            with mock.patch.object(goal_pack, "write_atomic", side_effect=interrupt_state):
                with self.assertRaisesRegex(RuntimeError, "queue checkpoint crash"):
                    controller.next()
            self.assertEqual(controller.status()["current_goal_index"], 0)
            self.assertFalse((controller.root / "goals" / "0002" / "state.json").exists())
            recovered = GoalPackController(controller.root, clock=lambda: NOW).next()
            self.assertEqual(recovered["status"], "goal-advanced")
            self.assertEqual(recovered["state"]["current_goal_index"], 1)

    def test_tampered_queue_or_symlinked_contract_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            state = json.loads(controller.state_path.read_text())
            state["goals"][1]["status"] = "active"
            write_document(controller.state_path, state)
            with self.assertRaisesRegex(StateError, "active Goal"):
                controller.status()

        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            boundary_path = controller.contracts_path / "runtime-boundary.json"
            outside = Path(directory) / "outside-boundary.json"
            write_document(outside, BOUNDARY)
            boundary_path.chmod(boundary_path.stat().st_mode | stat.S_IWUSR)
            boundary_path.unlink()
            try:
                boundary_path.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(StateError, "Runtime Boundary.*regular file"):
                controller.next()

    def test_next_goal_cannot_start_before_native_goal_completion_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            for _step in range(5):
                result = controller.next()
                controller.record(host_receipt(result["action"]))
            completion = controller.next()
            self.assertEqual(completion["action"]["action_kind"], "complete-goal")
            pending = GoalPackController(controller.root, clock=lambda: NOW).next()
            self.assertEqual(pending["status"], "reconcile-required")
            self.assertFalse((controller.root / "goals" / "0002" / "state.json").exists())

    def test_blocked_goal_blocks_the_pack_without_starting_later_work(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            result = controller.next()
            receipt = host_receipt(result["action"], outcome="failed")
            receipt["evidence"].update(
                code="action-failed", stable_id=None, exit_status=1,
            )
            controller.record(receipt)
            terminal = controller.next()
            self.assertEqual(terminal["status"], "terminal")
            self.assertEqual(terminal["state"]["state"], "blocked")
            self.assertEqual(
                [item["status"] for item in terminal["state"]["goals"]],
                ["blocked", "queued"],
            )
            self.assertFalse((controller.root / "goals" / "0002" / "state.json").exists())

    def test_pack_deadline_blocks_before_a_later_goal_is_started(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, _state = self.start(directory)
            self.advance_active_goal(controller)
            advanced = controller.next()
            self.assertEqual(advanced["status"], "goal-advanced")
            expired = GoalPackController(
                controller.root, clock=lambda: "2026-08-10T13:00:00Z"
            ).next()
            self.assertEqual(expired["status"], "terminal")
            self.assertEqual(expired["state"]["state"], "blocked")
            self.assertEqual(expired["state"]["terminal_reason"], "budget-limited")
            self.assertFalse((controller.root / "goals" / "0002" / "state.json").exists())

    def test_cli_pack_transcript_exposes_queue_status_and_one_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = pack_bindings()
            binding_paths = []
            for position, binding in enumerate(bindings, 1):
                path = root / f"binding-{position}.json"
                write_document(path, binding)
                binding_paths.append(path)
            authorization_path = root / "authorization.json"
            boundary_path = root / "boundary.json"
            write_document(authorization_path, pack_authorization(bindings))
            write_document(boundary_path, BOUNDARY)
            args = ["mission", "pack-start", "--state-dir", str(root / "pack")]
            for path in binding_paths:
                args.extend(("--goal-binding", str(path)))
            args.extend((
                "--authorization", str(authorization_path),
                "--runtime-boundary", str(boundary_path), "--json",
            ))
            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main(args), 0, errors.getvalue())
            self.assertEqual(json.loads(output.getvalue())["state"], "authorized")

            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([
                    "mission", "pack-next", "--state-dir", str(root / "pack"),
                    "--json",
                ]), 0, errors.getvalue())
            next_result = json.loads(output.getvalue())
            self.assertEqual(next_result["status"], "action-required")
            self.assertEqual(next_result["action"]["action_kind"], "prepare-worktree")

            receipt_path = root / "receipt.json"
            write_document(receipt_path, host_receipt(next_result["action"]))
            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([
                    "mission", "pack-record", "--state-dir", str(root / "pack"),
                    "--receipt-file", str(receipt_path), "--json",
                ]), 0, errors.getvalue())
            self.assertEqual(json.loads(output.getvalue())["status"], "advanced")

            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([
                    "mission", "pack-resume", "--state-dir", str(root / "pack"),
                    "--json",
                ]), 0, errors.getvalue())
            self.assertEqual(
                json.loads(output.getvalue())["action"]["action_kind"],
                "activate-goal",
            )

            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([
                    "mission", "pack-status", "--state-dir", str(root / "pack"),
                    "--json",
                ]), 0, errors.getvalue())
            status = json.loads(output.getvalue())
            self.assertEqual(status["current_goal_index"], 0)
            self.assertEqual(status["goals"][0]["status"], "active")

            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main([
                    "mission", "pack-abandon", "--state-dir", str(root / "pack"),
                    "--json",
                ]), 0, errors.getvalue())
            self.assertEqual(json.loads(output.getvalue())["state"], "abandoned")


if __name__ == "__main__":
    unittest.main()
