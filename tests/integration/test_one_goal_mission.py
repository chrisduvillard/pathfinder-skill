import tempfile
import unittest
import json
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

from pathfinder_core.adapters.github import PublicationResult, PublicationState, PullRequest
from pathfinder_core.adapters.types import AdapterResult, GoalRecord, GoalStatus
from pathfinder_core.errors import StateError
from pathfinder_core.mission import MissionOrchestrator
from pathfinder_core.mission_host import HostMissionController
from pathfinder_core.storage import MissionStore
from pathfinder_core.__main__ import main


NOW = "2026-08-10T12:00:00Z"
COMMIT = "b" * 40
HASH = "a" * 64


def initial_state():
    return {
        "schema_version": 1, "mission_id": "mission_12345678", "goal_id": "goal_12345678",
        "binding_id": "binding_12345678", "authorization_id": None, "attempt_id": None,
        "state": "planned", "revision": 0, "base_commit": COMMIT, "dirty_policy": "block",
        "worktree_id": None, "worktree_path": None, "branch_id": None, "branch_name": None,
        "commit_ids": [], "pr_id": None, "pr_url": None, "created_at": NOW, "updated_at": NOW,
    }


def authorization(explicit=True):
    return {
        "schema_version": 1, "authorization_id": "authorization_12345678",
        "mission_id": "mission_12345678", "binding_id": "binding_12345678",
        "explicit_request": explicit, "trusted_source": "current-user-turn", "authorized_at": NOW,
        "base_commit": COMMIT, "intent_hashes": {"charter": HASH, "roadmap": HASH, "doctrine": HASH},
        "limits": {"max_goals": 1, "max_attempts": 2, "max_wall_seconds": 3600, "max_total_prs": 1},
        "publication_target": "github-awaiting-review", "snapshot_sha256": HASH,
    }


def local_authorization():
    result = authorization()
    result["publication_target"] = "local-branch"
    result["limits"]["max_total_prs"] = 0
    return result


def goal_binding():
    return {
        "schema_version": 1, "binding_id": "binding_12345678",
        "mission_id": "mission_12345678", "goal_id": "goal_12345678",
        "objective": "complete one bounded goal", "objective_source": "roadmap-item",
        "selected_candidate_ids": [],
        "intent_snapshot": {
            "charter": {"version": 1, "sha256": HASH},
            "roadmap": {"version": 1, "sha256": HASH},
            "doctrine": {"version": 1, "sha256": HASH},
        },
        "capabilities": {"controller": "available"},
        "scope": {"repository_id": "fixture", "scoped_root": ".", "base_commit": COMMIT,
                  "dirty_policy": "block", "fingerprint": HASH},
        "proof_requirements": ["fixture verification passes"], "protected_surfaces": [],
        "runtime_boundary_required": True,
        "budgets": {"max_goals": 1, "max_attempts_per_goal": 2,
                    "max_wall_seconds": 3600, "max_open_prs": 0, "max_total_prs": 0},
        "created_at": NOW,
    }


def write_document(path, document):
    path.write_text(json.dumps(document))


BOUNDARY = {
    "schema_version": 1, "boundary_id": "boundary_12345678", "primary_runtime": "fixture",
    "filesystem": "enforced", "process": "enforced", "network": "denied", "credentials": "isolated",
    "repo_code_execution": "allowlisted", "tool_allowlist_enforced": True,
    "pre_execution_consent": True, "execution_eligible": True,
    "blocking_reasons": [], "observed_at": NOW,
}


class FakeCallbacks:
    def __init__(self, manual=False):
        self.manual = manual
        self.counts = {name: 0 for name in ("prepare", "activate", "implement", "verify", "commit", "publish")}

    def prepare(self, state):
        self.counts["prepare"] += 1
        return {
            "attempt_id": "attempt_12345678", "worktree_id": "worktree_12345678",
            "worktree_path": "/tmp/pathfinder-fixture", "branch_id": "branch_12345678",
            "branch_name": "pathfinder/auto/test-goal",
        }

    def activate(self, objective):
        self.counts["activate"] += 1
        mode = "manual" if self.manual else "native-created"
        return AdapterResult(mode, GoalRecord("goal_12345678", objective, GoalStatus.ACTIVE))

    def implement(self, state): self.counts["implement"] += 1
    def verify(self, state): self.counts["verify"] += 1; return True
    def commit(self, state): self.counts["commit"] += 1; return "c" * 40
    def publish(self, state):
        self.counts["publish"] += 1
        pr = PullRequest(
            "pr_12345678", "https://github.com/example/repo/pull/1",
            state["branch_name"], "main", state["mission_id"],
        )
        return PublicationResult(PublicationState.AWAITING_REVIEW, pr, False, 1, "passed")


class OneGoalMissionTests(unittest.TestCase):
    def make_orchestrator(self, root, callbacks, hook=None, auth=None):
        store = MissionStore(Path(root) / "mission")
        if not store.state_path.exists():
            store.initialize(initial_state())
        return MissionOrchestrator(
            store=store, objective="complete one bounded goal", authorization=auth or authorization(),
            runtime_boundary=BOUNDARY, callbacks=callbacks, publish=True,
            after_checkpoint=hook,
        )

    def test_synthetic_mission_reaches_one_awaiting_review_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            callbacks = FakeCallbacks()
            result = self.make_orchestrator(directory, callbacks).run()
            self.assertEqual(result["state"], "awaiting-review")
            self.assertEqual(result["commit_ids"], ["c" * 40])
            self.assertEqual(result["pr_url"], "https://github.com/example/repo/pull/1")
            self.assertEqual(callbacks.counts["publish"], 1)

    def test_resume_after_every_checkpoint_does_not_duplicate_side_effects(self):
        checkpoints = [
            "authorized", "prepared", "running", "verifying", "verified",
            "committed", "published", "awaiting-review",
        ]
        for checkpoint in checkpoints:
            with self.subTest(checkpoint=checkpoint), tempfile.TemporaryDirectory() as directory:
                callbacks = FakeCallbacks()
                fired = set()

                def crash_once(state):
                    if state["state"] == checkpoint and checkpoint not in fired:
                        fired.add(checkpoint)
                        raise RuntimeError(f"crash after {checkpoint}")

                orchestrator = self.make_orchestrator(directory, callbacks, crash_once)
                with self.assertRaises(RuntimeError):
                    orchestrator.run()
                result = orchestrator.run()
                self.assertEqual(result["state"], "awaiting-review")
                for count in callbacks.counts.values():
                    self.assertLessEqual(count, 1)

    def test_manual_goal_activation_blocks_without_simulating_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.make_orchestrator(directory, FakeCallbacks(manual=True)).run()
            self.assertEqual(result["state"], "blocked")

    def test_non_explicit_authorization_is_rejected_before_work(self):
        with tempfile.TemporaryDirectory() as directory:
            callbacks = FakeCallbacks()
            with self.assertRaisesRegex(StateError, "explicit_request"):
                self.make_orchestrator(
                    directory, callbacks, auth=authorization(explicit=False)
                ).run()
            self.assertTrue(all(count == 0 for count in callbacks.counts.values()))

    def test_cli_abandon_is_explicit_and_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "mission"
            MissionStore(state_dir).initialize(initial_state())
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(["mission", "abandon", "--state-dir", str(state_dir), "--json"]), 0)
            self.assertEqual(MissionStore(state_dir).load()["state"], "abandoned")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(["mission", "abandon", "--state-dir", str(state_dir)]), 4)

    def test_host_mission_start_is_crash_safe_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            arguments = {"binding": goal_binding(), "authorization": local_authorization(),
                         "runtime_boundary": BOUNDARY}
            with mock.patch.object(controller.store, "initialize", side_effect=RuntimeError("crash")):
                with self.assertRaises(RuntimeError):
                    controller.start(**arguments)
            self.assertFalse(controller.store.state_path.exists())
            self.assertEqual(len(list(controller.contracts_path.glob("*.json"))), 3)
            first = HostMissionController(root, clock=lambda: NOW).start(**arguments)
            second = HostMissionController(root, clock=lambda: NOW).start(**arguments)
            self.assertEqual(first, second)
            self.assertEqual(first["state"], "authorized")
            self.assertEqual(len(list((root / "events").glob("*.json"))), 1)

    def test_host_mission_start_rejects_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = HostMissionController(Path(directory) / "mission")
            with self.assertRaisesRegex(StateError, "local/no-publication"):
                controller.start(
                    binding=goal_binding(), authorization=authorization(),
                    runtime_boundary=BOUNDARY,
                )
            self.assertFalse(controller.store.state_path.exists())

    def test_host_mission_start_recovers_state_before_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            arguments = {"binding": goal_binding(), "authorization": local_authorization(),
                         "runtime_boundary": BOUNDARY}
            with mock.patch.object(controller.store, "move", side_effect=RuntimeError("crash")):
                with self.assertRaises(RuntimeError):
                    controller.start(**arguments)
            self.assertEqual(MissionStore(root).load()["state"], "planned")
            recovered = HostMissionController(root, clock=lambda: NOW).start(**arguments)
            self.assertEqual(recovered["state"], "authorized")
            self.assertEqual(len(list((root / "events").glob("*.json"))), 1)

    def test_host_mission_start_rejects_contract_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            arguments = {"binding": goal_binding(), "authorization": local_authorization(),
                         "runtime_boundary": BOUNDARY}
            controller.start(**arguments)
            changed = goal_binding()
            changed["objective"] = "different objective"
            with self.assertRaisesRegex(StateError, "different persisted mission contract"):
                controller.start(
                    binding=changed, authorization=arguments["authorization"],
                    runtime_boundary=arguments["runtime_boundary"],
                )

    def test_cli_starts_local_mission_from_validated_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding_path, authorization_path, boundary_path = (
                root / "binding.json", root / "authorization.json", root / "boundary.json"
            )
            write_document(binding_path, goal_binding())
            write_document(authorization_path, local_authorization())
            write_document(boundary_path, BOUNDARY)
            output = StringIO()
            with redirect_stdout(output), redirect_stderr(StringIO()):
                exit_code = main([
                    "mission", "start", "--state-dir", str(root / "mission"),
                    "--goal-binding", str(binding_path), "--authorization", str(authorization_path),
                    "--runtime-boundary", str(boundary_path), "--json",
                ])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue())["state"], "authorized")


if __name__ == "__main__":
    unittest.main()
