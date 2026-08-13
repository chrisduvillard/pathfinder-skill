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
from pathfinder_core.mission_host import HostMissionController, document_sha256
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
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


def additive_policy():
    baseline = ProtectedSurfaceRegistry.load()
    return {
        "schema_version": 1,
        "policy_id": "protected-policy-fixture-extra",
        "mode": "additive",
        "base_policy_id": baseline.policy_id,
        "rules": [{
            "rule_id": "protected-rule-cryptography",
            "category": "cryptography",
            "description": "Repository-specific cryptographic implementation.",
            "patterns": ["crypto/**"],
        }],
    }


def write_document(path, document):
    path.write_text(json.dumps(document))


RECEIPT_CODES = {
    "prepare-worktree": "worktree-prepared",
    "activate-goal": "goal-active",
    "implement": "implementation-complete",
    "verify": "verification-passed",
    "commit": "commit-created",
    "complete-goal": "goal-complete",
}


def host_receipt(action, *, outcome="succeeded"):
    stable_ids = {
        "prepare-worktree": "worktree_12345678",
        "activate-goal": "goal_native_12345678",
        "implement": "implementation_12345678",
        "verify": "verification_12345678",
        "commit": "c" * 40,
        "complete-goal": "goal_native_12345678",
    }
    evidence = {
        "code": RECEIPT_CODES[action["action_kind"]],
        "redacted_summary": f"{action['action_kind']} fixture complete",
        "stable_id": stable_ids[action["action_kind"]],
        "artifact_sha256": HASH,
        "exit_status": 0,
        "changed_files": ["src/example.py"] if action["action_kind"] == "implement" else [],
        "worktree_path": None,
        "branch_id": None,
        "branch_name": None,
    }
    if action["action_kind"] == "prepare-worktree":
        evidence.update(
            worktree_path="/tmp/pathfinder-fixture",
            branch_id="branch_12345678",
            branch_name="pathfinder/auto/test-goal",
        )
    return {
        "schema_version": 1,
        **{field: action[field] for field in (
            "action_id", "operation_id", "mission_id", "attempt_id", "action_kind",
            "request_sha256", "authorization_snapshot_sha256", "runtime_boundary_sha256",
        )},
        "outcome": outcome,
        "evidence": evidence,
        "completed_at": NOW,
    }


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
            self.assertEqual(len(list(controller.contracts_path.glob("*.json"))), 4)
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

    def test_host_mission_start_rejects_non_git_goal_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = goal_binding()
            binding["schema_version"] = 2
            binding["scope"].update(
                repository_kind="non-git",
                base_commit=None,
                dirty_policy="not-applicable",
            )
            controller = HostMissionController(Path(directory) / "mission")
            with self.assertRaisesRegex(StateError, "require a Git Goal Binding"):
                controller.start(
                    binding=binding,
                    authorization=local_authorization(),
                    runtime_boundary=BOUNDARY,
                )
            self.assertFalse(controller.store.state_path.exists())

    def test_host_mission_start_rejects_intent_hash_drift(self):
        for name in ("charter", "roadmap", "doctrine"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                auth = local_authorization()
                auth["intent_hashes"][name] = "b" * 64
                controller = HostMissionController(Path(directory) / "mission")
                with self.assertRaisesRegex(StateError, f"intent hash drift: {name}"):
                    controller.start(
                        binding=goal_binding(), authorization=auth,
                        runtime_boundary=BOUNDARY,
                    )
                self.assertFalse(controller.store.state_path.exists())

    def test_host_mission_start_rejects_authorization_that_widens_binding_budgets(self):
        for field, value in (("max_attempts", 3), ("max_wall_seconds", 3601)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                auth = local_authorization()
                auth["limits"][field] = value
                with self.assertRaisesRegex(StateError, f"{field}.*Goal Binding"):
                    HostMissionController(Path(directory) / "mission").start(
                        binding=goal_binding(), authorization=auth,
                        runtime_boundary=BOUNDARY,
                    )

    def test_narrower_authorization_controls_the_action_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = local_authorization()
            auth["limits"]["max_wall_seconds"] = 60
            controller = HostMissionController(
                Path(directory) / "mission", clock=lambda: NOW
            )
            controller.start(
                binding=goal_binding(), authorization=auth,
                runtime_boundary=BOUNDARY,
            )
            action = controller.next()["action"]
            self.assertEqual(action["context"]["deadline_at"], "2026-08-10T12:01:00Z")

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

    def test_cli_accepts_only_an_explicit_additive_protected_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding_path, authorization_path, boundary_path, policy_path = (
                root / "binding.json", root / "authorization.json",
                root / "boundary.json", root / "protected-policy.json",
            )
            binding = goal_binding()
            binding["protected_surfaces"] = ["cryptography"]
            write_document(binding_path, binding)
            write_document(authorization_path, local_authorization())
            write_document(boundary_path, BOUNDARY)
            write_document(policy_path, additive_policy())
            output = StringIO()
            with redirect_stdout(output), redirect_stderr(StringIO()):
                exit_code = main([
                    "mission", "start", "--state-dir", str(root / "mission"),
                    "--goal-binding", str(binding_path),
                    "--authorization", str(authorization_path),
                    "--runtime-boundary", str(boundary_path),
                    "--protected-policy", str(policy_path), "--json",
                ])
            self.assertEqual(exit_code, 0)
            effective = ProtectedSurfaceRegistry(
                json.loads(
                    (root / "mission" / "contracts" / "protected-surfaces.json").read_text()
                )
            )
            self.assertIn("cryptography", effective.categories)

    def test_next_journals_action_before_return_and_never_blindly_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            first = controller.next()
            self.assertEqual(first["status"], "action-required")
            action = first["action"]
            self.assertEqual(action["action_kind"], "prepare-worktree")
            self.assertEqual(
                action["authorization_snapshot_sha256"],
                document_sha256(local_authorization()),
            )
            self.assertEqual(
                action["runtime_boundary_sha256"], document_sha256(BOUNDARY)
            )
            self.assertEqual(action["context"]["deadline_at"], "2026-08-10T13:00:00Z")
            self.assertEqual(
                action["context"]["protected_policy_sha256"],
                ProtectedSurfaceRegistry.load().sha256,
            )
            intent_path = root / "operations" / f"{action['operation_id']}.intent.json"
            self.assertTrue(intent_path.exists())
            second = HostMissionController(root, clock=lambda: NOW).next()
            self.assertEqual(second["status"], "reconcile-required")
            self.assertNotIn("action", second)

    def test_cli_next_returns_one_action_then_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            HostMissionController(root).start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            output = StringIO()
            with redirect_stdout(output), redirect_stderr(StringIO()):
                self.assertEqual(main([
                    "mission", "next", "--state-dir", str(root), "--json"
                ]), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "action-required")
            output = StringIO()
            with redirect_stdout(output), redirect_stderr(StringIO()):
                self.assertEqual(main([
                    "mission", "next", "--state-dir", str(root), "--json"
                ]), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "reconcile-required")

    def test_wall_budget_survives_restart_and_blocks_before_a_new_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            HostMissionController(root, clock=lambda: NOW).start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            expired = HostMissionController(
                root, clock=lambda: "2026-08-10T13:00:00Z"
            ).next()
            self.assertEqual(expired["status"], "terminal")
            self.assertEqual(expired["state"]["state"], "blocked")
            self.assertEqual(expired["state"]["terminal_reason"], "budget-limited")
            repeated = HostMissionController(root).next()
            self.assertEqual(repeated["state"], expired["state"])
            self.assertFalse((root / "operations").exists())

    def test_late_success_receipt_is_not_accepted_or_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            binding, auth = goal_binding(), local_authorization()
            binding["budgets"]["max_wall_seconds"] = 1
            auth["limits"]["max_wall_seconds"] = 1
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=binding, authorization=auth, runtime_boundary=BOUNDARY
            )
            action = controller.next()["action"]
            receipt = host_receipt(action)
            receipt["completed_at"] = "2026-08-10T12:00:02Z"
            with self.assertRaisesRegex(StateError, "after the mission deadline"):
                controller.record(receipt)
            self.assertFalse(controller._receipt_path(action["operation_id"]).exists())
            self.assertEqual(controller.next()["status"], "reconcile-required")

    def test_unknown_binding_surface_requires_an_explicit_additive_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = goal_binding()
            binding["protected_surfaces"] = ["cryptography"]
            controller = HostMissionController(Path(directory) / "mission")
            with self.assertRaisesRegex(StateError, "unknown protected surface"):
                controller.start(
                    binding=binding, authorization=local_authorization(),
                    runtime_boundary=BOUNDARY,
                )
            state = controller.start(
                binding=binding, authorization=local_authorization(),
                runtime_boundary=BOUNDARY, protected_policy=additive_policy(),
            )
            self.assertEqual(state["state"], "authorized")

    def test_implementation_receipt_cannot_hide_undeclared_protected_drift(self):
        for declared in (False, True):
            with self.subTest(declared=declared), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mission"
                binding = goal_binding()
                if declared:
                    binding["protected_surfaces"] = ["auth"]
                controller = HostMissionController(root, clock=lambda: NOW)
                controller.start(
                    binding=binding, authorization=local_authorization(),
                    runtime_boundary=BOUNDARY,
                )
                for _ in range(2):
                    controller.record(host_receipt(controller.next()["action"]))
                action = controller.next()["action"]
                receipt = host_receipt(action)
                receipt["evidence"]["changed_files"] = ["src/auth/login.py"]
                if declared:
                    result = controller.record(receipt)
                    self.assertEqual(result["state"]["state"], "verifying")
                else:
                    with self.assertRaisesRegex(StateError, "undeclared protected surface: auth"):
                        controller.record(receipt)
                    self.assertFalse(controller._receipt_path(action["operation_id"]).exists())
                    self.assertEqual(controller.next()["status"], "reconcile-required")

    def test_persisted_policy_drift_invalidates_the_pending_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            action = controller.next()["action"]
            policy_path = controller.contracts_path / "protected-surfaces.json"
            policy = json.loads(policy_path.read_text())
            policy["rules"][0]["description"] = "tampered after action issuance"
            policy_path.chmod(0o600)
            write_document(policy_path, policy)
            with self.assertRaisesRegex(StateError, "protected policy hash"):
                controller.record(host_receipt(action))

    def test_receipt_and_result_crash_boundaries_resume_without_replay(self):
        for boundary in ("after-receipt", "after-result"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mission"
                controller = HostMissionController(root, clock=lambda: NOW)
                controller.start(
                    binding=goal_binding(), authorization=local_authorization(),
                    runtime_boundary=BOUNDARY,
                )
                action = controller.next()["action"]
                receipt = host_receipt(action)
                target = controller.journal if boundary == "after-receipt" else controller.store
                method = "record_result" if boundary == "after-receipt" else "move"
                with mock.patch.object(target, method, side_effect=RuntimeError("crash")):
                    with self.assertRaises(RuntimeError):
                        controller.record(receipt)
                recovered = HostMissionController(root, clock=lambda: NOW).next()
                self.assertEqual(recovered["status"], "advanced")
                self.assertEqual(recovered["state"]["state"], "prepared")
                repeated = HostMissionController(root).record(receipt)
                self.assertEqual(repeated["state"], recovered["state"])
                self.assertEqual(len(list((root / "operations").glob("*.intent.json"))), 1)

    def test_manual_goal_handoff_blocks_instead_of_fabricating_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            controller.record(host_receipt(controller.next()["action"]))
            action = controller.next()["action"]
            receipt = host_receipt(action, outcome="manual-handoff")
            receipt["evidence"].update(
                code="manual-handoff", stable_id=None, artifact_sha256=None,
                exit_status=None, redacted_summary="Run /goal manually",
            )
            result = controller.record(receipt)
            self.assertEqual(result["status"], "manual-handoff")
            self.assertEqual(result["state"]["state"], "blocked")

    def test_native_goal_must_complete_before_the_mission_is_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            for _step in range(5):
                action = controller.next()["action"]
                controller.record(host_receipt(action))
            completion = controller.next()
            self.assertEqual(completion["status"], "action-required")
            self.assertEqual(completion["action"]["action_kind"], "complete-goal")
            self.assertEqual(
                completion["action"]["context"]["native_goal_id"],
                "goal_native_12345678",
            )
            pending = HostMissionController(root).next()
            self.assertEqual(pending["status"], "reconcile-required")
            self.assertEqual(controller.store.load()["state"], "committed")
            terminal = controller.record(host_receipt(completion["action"]))
            self.assertEqual(terminal["state"]["state"], "awaiting-review")

    def test_goal_completion_receipt_must_match_the_activated_native_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = HostMissionController(
                Path(directory) / "mission", clock=lambda: NOW
            )
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            for _step in range(5):
                action = controller.next()["action"]
                controller.record(host_receipt(action))
            action = controller.next()["action"]
            receipt = host_receipt(action)
            receipt["evidence"]["stable_id"] = "goal_native_different"
            with self.assertRaisesRegex(StateError, "activated native Goal"):
                controller.record(receipt)
            self.assertFalse(controller._receipt_path(action["operation_id"]).exists())

    def test_semantically_invalid_receipt_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "mission"
            controller = HostMissionController(root, clock=lambda: NOW)
            controller.start(
                binding=goal_binding(), authorization=local_authorization(),
                runtime_boundary=BOUNDARY,
            )
            action = controller.next()["action"]
            receipt = host_receipt(action)
            receipt["evidence"]["code"] = "action-failed"
            with self.assertRaisesRegex(StateError, "wrong evidence code"):
                controller.record(receipt)
            operation_prefix = root / "operations" / action["operation_id"]
            self.assertFalse(Path(f"{operation_prefix}.receipt.json").exists())
            self.assertFalse(Path(f"{operation_prefix}.result.json").exists())

    def test_cli_transcript_reaches_verified_local_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mission_root = root / "mission"
            binding_path, authorization_path, boundary_path = (
                root / "binding.json", root / "authorization.json", root / "boundary.json"
            )
            write_document(binding_path, goal_binding())
            write_document(authorization_path, local_authorization())
            write_document(boundary_path, BOUNDARY)

            def invoke(arguments):
                output, errors = StringIO(), StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    code = main(arguments)
                self.assertEqual(code, 0, errors.getvalue())
                return json.loads(output.getvalue())

            invoke([
                "mission", "start", "--state-dir", str(mission_root),
                "--goal-binding", str(binding_path), "--authorization", str(authorization_path),
                "--runtime-boundary", str(boundary_path), "--json",
            ])
            for expected_action in RECEIPT_CODES:
                next_result = invoke([
                    "mission", "resume", "--state-dir", str(mission_root), "--json"
                ])
                self.assertEqual(next_result["action"]["action_kind"], expected_action)
                receipt_path = root / "receipt.json"
                write_document(receipt_path, host_receipt(next_result["action"]))
                record_result = invoke([
                    "mission", "record", "--state-dir", str(mission_root),
                    "--receipt-file", str(receipt_path), "--json",
                ])
                self.assertEqual(record_result["status"], "advanced")
            terminal = invoke([
                "mission", "resume", "--state-dir", str(mission_root), "--json"
            ])
            self.assertEqual(terminal["status"], "terminal")
            self.assertEqual(terminal["state"]["state"], "awaiting-review")
            self.assertEqual(terminal["state"]["commit_ids"], ["c" * 40])
            self.assertIsNone(terminal["state"]["pr_id"])


if __name__ == "__main__":
    unittest.main()
