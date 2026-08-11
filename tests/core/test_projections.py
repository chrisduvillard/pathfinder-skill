import json
import tempfile
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.mission_host import HostMissionController
from pathfinder_core.projections import build_mission_projection

from tests.integration.test_one_goal_mission import (
    BOUNDARY,
    NOW,
    goal_binding,
    host_receipt,
    local_authorization,
)


class ProjectionTests(unittest.TestCase):
    def start(self, directory: str) -> HostMissionController:
        controller = HostMissionController(Path(directory) / "mission", clock=lambda: NOW)
        controller.start(
            binding=goal_binding(),
            authorization=local_authorization(),
            runtime_boundary=BOUNDARY,
        )
        return controller

    def advance(self, controller: HostMissionController, count: int) -> None:
        for _step in range(count):
            action = controller.next()["action"]
            controller.record(host_receipt(action))

    def test_authorized_projection_is_schema_valid_and_not_final(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            projection = build_mission_projection(controller.root)
            run_log = projection["run_log"]
            self.assertEqual(run_log["mission_id"], goal_binding()["mission_id"])
            self.assertEqual(run_log["binding_status"], "not-run")
            self.assertEqual(run_log["verification"], "not-run")
            self.assertEqual(run_log["publication"], "local-only")
            self.assertEqual(run_log["commands"], [])
            self.assertIsNone(projection["final_summary"])
            self.assertFalse(projection["requires_reconciliation"])

    def test_verifying_projection_records_completed_host_actions_without_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            self.advance(controller, 3)
            projection = build_mission_projection(controller.root)
            self.assertEqual(projection["state"]["state"], "verifying")
            self.assertEqual(projection["run_log"]["binding_status"], "missing")
            self.assertEqual(projection["run_log"]["verification"], "not-run")
            self.assertEqual(projection["run_log"]["commands"], [])
            self.assertEqual(
                [item["action_kind"] for item in projection["operations"]],
                ["prepare-worktree", "activate-goal", "implement"],
            )
            self.assertTrue(all(item["status"] == "succeeded" for item in projection["operations"]))

    def test_awaiting_review_projection_is_terminal_and_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            self.advance(controller, 5)
            controller.next()
            projection = build_mission_projection(controller.root)
            summary = projection["final_summary"]
            self.assertEqual(projection["run_log"]["verification"], "passed")
            self.assertEqual(projection["run_log"]["binding_status"], "matched")
            self.assertEqual(projection["run_log"]["publication"], "awaiting-review")
            self.assertEqual(summary["final_state"], "awaiting-review")
            self.assertEqual(summary["goals"][0]["commit_ids"], ["c" * 40])
            self.assertEqual(summary["goals"][0]["verification"], "passed")
            self.assertIsNone(summary["goals"][0]["pr_url"])

    def test_blocked_projection_uses_only_redacted_receipt_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            self.advance(controller, 3)
            action = controller.next()["action"]
            receipt = host_receipt(action, outcome="failed")
            receipt["evidence"].update(
                code="verification-failed",
                redacted_summary="verification failed after redaction",
                exit_status=1,
            )
            controller.record(receipt)
            projection = build_mission_projection(controller.root)
            summary = projection["final_summary"]
            self.assertEqual(projection["run_log"]["verification"], "failed")
            self.assertEqual(summary["final_state"], "blocked")
            self.assertIn("verification failed after redaction", summary["residual_risks"])
            operation = projection["operations"][-1]
            self.assertEqual(
                set(operation),
                {
                    "operation_id", "stage", "action_kind", "status", "started_at",
                    "completed_at", "summary_code", "redacted_summary", "exit_status",
                    "changed_files", "artifact_sha256",
                },
            )
            self.assertNotIn("request_sha256", json.dumps(operation))

    def test_abandoned_projection_is_terminal_without_inventing_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            controller.store.move("abandoned", attempt_id=controller.store.load()["attempt_id"])
            projection = build_mission_projection(controller.root)
            self.assertEqual(projection["final_summary"]["final_state"], "abandoned")
            self.assertEqual(projection["run_log"]["binding_status"], "not-run")
            self.assertEqual(projection["run_log"]["verification"], "not-run")

    def test_pending_intent_requires_reconciliation_without_a_final_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            action = controller.next()["action"]
            projection = build_mission_projection(controller.root)
            self.assertTrue(projection["requires_reconciliation"])
            self.assertEqual(projection["operations"][0]["operation_id"], action["operation_id"])
            self.assertEqual(projection["operations"][0]["status"], "reconcile-required")
            self.assertEqual(projection["run_log"]["verification"], "blocked")
            self.assertIsNone(projection["final_summary"])

    def test_persisted_receipt_without_result_is_recovery_pending_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            action = controller.next()["action"]
            controller._persist_receipt(host_receipt(action))
            projection = build_mission_projection(controller.root)
            self.assertFalse(projection["requires_reconciliation"])
            self.assertEqual(projection["operations"][0]["status"], "recovery-pending")
            self.assertEqual(projection["state"]["state"], "authorized")

    def test_operation_identity_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.start(directory)
            action = controller.next()["action"]
            intent_path = controller.root / "operations" / f"{action['operation_id']}.intent.json"
            intent = json.loads(intent_path.read_text())
            intent["mission_id"] = "mission_different01"
            intent_path.write_text(json.dumps(intent))
            with self.assertRaisesRegex(StateError, "operation mission_id"):
                build_mission_projection(controller.root)


if __name__ == "__main__":
    unittest.main()
