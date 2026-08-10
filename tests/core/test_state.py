import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import StateError
from pathfinder_core.state import ALLOWED_TRANSITIONS, transition
from pathfinder_core.storage import MissionLock, MissionStore, read_json, write_atomic


NOW = "2026-08-10T12:00:00Z"
COMMIT = "b" * 40


def initial_state():
    return {
        "schema_version": 1, "mission_id": "mission_12345678", "goal_id": "goal_12345678",
        "binding_id": "binding_12345678", "authorization_id": None, "attempt_id": None,
        "state": "planned", "revision": 0, "base_commit": COMMIT, "dirty_policy": "block",
        "worktree_id": None, "worktree_path": None, "branch_id": None, "branch_name": None,
        "commit_ids": [], "pr_id": None, "pr_url": None, "created_at": NOW, "updated_at": NOW,
    }


class StateTests(unittest.TestCase):
    def test_complete_transition_matrix(self):
        states = set(ALLOWED_TRANSITIONS)
        for current, allowed in ALLOWED_TRANSITIONS.items():
            document = initial_state()
            document["state"] = current
            for target in states:
                with self.subTest(current=current, target=target):
                    if target == current or target in allowed:
                        self.assertEqual(transition(document, target)["state"], target)
                    else:
                        with self.assertRaises(StateError):
                            transition(document, target)

    def test_allowed_transition_increments_revision(self):
        result = transition(initial_state(), "authorized", at=NOW)
        self.assertEqual(result["state"], "authorized")
        self.assertEqual(result["revision"], 1)

    def test_forbidden_transition_fails(self):
        with self.assertRaisesRegex(StateError, "forbidden"):
            transition(initial_state(), "committed")

    def test_same_transition_is_idempotent(self):
        state = initial_state()
        self.assertEqual(transition(state, "planned"), state)

    def test_atomic_failure_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_atomic(path, {"value": "old"})
            with mock.patch("pathfinder_core.storage.os.replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    write_atomic(path, {"value": "new"})
            self.assertEqual(read_json(path), {"value": "old"})

    def test_lock_prevents_concurrent_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mission.lock"
            first = MissionLock(path)
            first.acquire()
            try:
                with self.assertRaisesRegex(StateError, "already held"):
                    MissionLock(path).acquire()
            finally:
                first.release()

    def test_stale_lease_can_be_reclaimed_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mission.lock"
            stale = MissionLock(path, lease_seconds=-1)
            stale.acquire()
            replacement = MissionLock(path)
            replacement.acquire(break_stale=True)
            replacement.release()

    def test_store_recovers_event_written_before_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            interrupted = {
                "schema_version": 1, "event_id": "event_12345678", "mission_id": "mission_12345678",
                "sequence": 1, "event_type": "transition", "from_state": "planned", "to_state": "authorized",
                "attempt_id": None, "recorded_at": NOW, "changes": {"authorization_id": "authorization_12345678"},
                "payload_sha256": "0" * 64,
            }
            store._append_event(interrupted)
            recovered = store.load()
            self.assertEqual(recovered["state"], "authorized")
            self.assertEqual(recovered["authorization_id"], "authorization_12345678")

    def test_store_move_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(copy.deepcopy(initial_state()))
            first = store.move("authorized")
            second = store.move("authorized")
            self.assertEqual(first, second)
            self.assertEqual(len(list(store.events_path.glob("*.json"))), 1)

    def test_idempotent_move_rejects_uncheckpointed_change_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(copy.deepcopy(initial_state()))
            with self.assertRaisesRegex(StateError, "idempotent transition"):
                store.move("planned", changes={"branch_name": "pathfinder/auto/drift"})


if __name__ == "__main__":
    unittest.main()
