import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.mission_host import ACTION_BY_STATE, HostMissionController
from tests.integration.test_one_goal_mission import (
    BOUNDARY,
    NOW,
    RECEIPT_CODES,
    goal_binding,
    host_receipt,
    local_authorization,
)


ACTIONS = (
    "prepare-worktree",
    "activate-goal",
    "implement",
    "verify",
    "commit",
    "complete-goal",
)


class PersistentHostBackend:
    def __init__(self, path):
        self.path = Path(path)

    def perform(self, action):
        state = json.loads(self.path.read_text()) if self.path.exists() else {"counts": {}}
        kind = action["action_kind"]
        state["counts"][kind] = state["counts"].get(kind, 0) + 1
        self.path.write_text(json.dumps(state))
        return host_receipt(action)

    def count(self, action_kind):
        if not self.path.exists():
            return 0
        return json.loads(self.path.read_text())["counts"].get(action_kind, 0)


def ready_for(root, action_kind):
    controller = HostMissionController(root, clock=lambda: NOW)
    controller.start(
        binding=goal_binding(), authorization=local_authorization(),
        runtime_boundary=BOUNDARY,
    )
    for current in ACTIONS:
        if current == action_kind:
            return controller
        action = controller.next()["action"]
        controller.record(host_receipt(action))
    raise AssertionError(f"unknown action {action_kind}")


class HostBridgeCrashMatrixTests(unittest.TestCase):
    def test_matrix_covers_every_controller_action(self):
        controller_actions = tuple(
            action_kind for _, action_kind in ACTION_BY_STATE.values()
        )
        self.assertEqual(ACTIONS, controller_actions)
        self.assertEqual(set(ACTIONS), set(RECEIPT_CODES))

    def test_before_intent_and_after_intent_do_not_run_host_action(self):
        for action_kind in ACTIONS:
            with self.subTest(action=action_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mission"
                backend = PersistentHostBackend(Path(directory) / "host.json")
                controller = ready_for(root, action_kind)
                before = len(list((root / "operations").glob("*.intent.json")))
                self.assertEqual(backend.count(action_kind), 0)
                action = controller.next()["action"]
                self.assertEqual(
                    len(list((root / "operations").glob("*.intent.json"))), before + 1
                )
                retry = HostMissionController(root).next()
                self.assertEqual(retry["status"], "reconcile-required")
                self.assertNotIn("action", retry)
                self.assertEqual(backend.count(action_kind), 0)
                self.assertEqual(action["action_kind"], action_kind)

    def test_side_effect_without_receipt_requires_reconciliation_not_replay(self):
        for action_kind in ACTIONS:
            with self.subTest(action=action_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mission"
                backend = PersistentHostBackend(Path(directory) / "host.json")
                action = ready_for(root, action_kind).next()["action"]
                backend.perform(action)  # response is lost before record
                retry = HostMissionController(root).next()
                self.assertEqual(retry["status"], "reconcile-required")
                self.assertEqual(backend.count(action_kind), 1)

    def test_receipt_and_result_crashes_recover_every_local_action_once(self):
        for action_kind in ACTIONS:
            for boundary in ("after-receipt", "after-result"):
                with self.subTest(action=action_kind, boundary=boundary), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "mission"
                    backend = PersistentHostBackend(Path(directory) / "host.json")
                    controller = ready_for(root, action_kind)
                    action = controller.next()["action"]
                    receipt = backend.perform(action)
                    target = controller.journal if boundary == "after-receipt" else controller.store
                    method = "record_result" if boundary == "after-receipt" else "move"
                    with mock.patch.object(target, method, side_effect=RuntimeError("crash")):
                        with self.assertRaises(RuntimeError):
                            controller.record(receipt)
                    recovered = HostMissionController(root).next()
                    self.assertEqual(recovered["status"], "advanced")
                    self.assertEqual(backend.count(action_kind), 1)

    def test_after_transition_old_receipt_is_idempotent(self):
        for action_kind in ACTIONS:
            with self.subTest(action=action_kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "mission"
                backend = PersistentHostBackend(Path(directory) / "host.json")
                controller = ready_for(root, action_kind)
                action = controller.next()["action"]
                receipt = backend.perform(action)
                first = controller.record(receipt)
                second = HostMissionController(root).record(receipt)
                self.assertEqual(first["state"], second["state"])
                self.assertEqual(backend.count(action_kind), 1)


if __name__ == "__main__":
    unittest.main()
