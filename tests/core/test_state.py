import copy
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from pathfinder_core.__main__ import main
from pathfinder_core.errors import StateError
from pathfinder_core.state import ALLOWED_TRANSITIONS, transition
from pathfinder_core.storage import (
    MissionLock,
    MissionStore,
    canonical_sha256,
    read_json,
    write_atomic,
)


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


def filesystem_snapshot(root: Path):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        result[relative] = (
            "directory" if path.is_dir() else "file",
            metadata.st_mode,
            metadata.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result


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

    @unittest.skipUnless(os.name == "posix", "POSIX permission semantics")
    def test_atomic_json_storage_is_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "state"
            parent.mkdir(mode=0o777)
            parent.chmod(0o777)
            path = parent / "document.json"
            write_atomic(path, {"value": "private"})
            self.assertEqual(parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

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

    def test_store_reports_then_repairs_event_written_before_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            changes = {"authorization_id": "authorization_12345678"}
            interrupted = {
                "schema_version": 1,
                "event_id": "event_12345678",
                "mission_id": "mission_12345678",
                "sequence": 1,
                "event_type": "transition",
                "from_state": "planned",
                "to_state": "authorized",
                "attempt_id": None,
                "recorded_at": NOW,
                "changes": changes,
                "payload_sha256": canonical_sha256(changes),
            }
            store._append_event(interrupted)

            before = store.state_path.read_bytes()
            snapshot = store.peek()
            self.assertTrue(snapshot["recovery_required"])
            self.assertEqual(snapshot["state"]["state"], "planned")
            self.assertEqual(store.state_path.read_bytes(), before)
            with self.assertRaisesRegex(StateError, "repair required"):
                store.load()

            recovered = store.repair()
            self.assertEqual(recovered["state"], "authorized")
            self.assertEqual(recovered["authorization_id"], "authorization_12345678")
            self.assertFalse(store.peek()["recovery_required"])

    def test_tampered_pending_event_hash_is_rejected_without_state_write(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            event = {
                "schema_version": 1,
                "event_id": "event_12345678",
                "mission_id": "mission_12345678",
                "sequence": 1,
                "event_type": "transition",
                "from_state": "planned",
                "to_state": "authorized",
                "attempt_id": None,
                "recorded_at": NOW,
                "changes": {"authorization_id": "authorization_12345678"},
                "payload_sha256": "0" * 64,
            }
            write_atomic(store._event_path(1), event)
            before = store.state_path.read_bytes()
            with self.assertRaisesRegex(StateError, "payload hash mismatch"):
                store.peek()
            self.assertEqual(store.state_path.read_bytes(), before)

    def test_pending_event_cannot_overwrite_immutable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            changes = {"mission_id": "mission_attacker1"}
            event = {
                "schema_version": 1,
                "event_id": "event_12345678",
                "mission_id": "mission_12345678",
                "sequence": 1,
                "event_type": "transition",
                "from_state": "planned",
                "to_state": "authorized",
                "attempt_id": None,
                "recorded_at": NOW,
                "changes": changes,
                "payload_sha256": canonical_sha256(changes),
            }
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "immutable field: mission_id"):
                store.repair()
            self.assertEqual(read_json(store.state_path)["mission_id"], "mission_12345678")

    def test_move_emits_tamper_evident_event_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            authorized = store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            prepared = store.move(
                "prepared",
                changes={
                    "attempt_id": "attempt_12345678",
                    "worktree_id": "worktree_12345678",
                    "worktree_path": "/tmp/pathfinder-worktree",
                    "branch_id": "branch_12345678",
                    "branch_name": "pathfinder/auto/test",
                },
            )
            first = read_json(store._event_path(1))
            second = read_json(store._event_path(2))
            self.assertEqual(first["schema_version"], 2)
            self.assertIsNone(first["previous_event_sha256"])
            self.assertEqual(first["state_after_sha256"], canonical_sha256(authorized))
            self.assertEqual(second["previous_event_sha256"], canonical_sha256(first))
            self.assertEqual(second["state_before_sha256"], canonical_sha256(authorized))
            self.assertEqual(second["state_after_sha256"], canonical_sha256(prepared))
            self.assertEqual(store.load(), prepared)

    def test_applied_v2_event_rejects_attempt_identity_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            state["attempt_id"] = "attempt_12345678"
            store.initialize(state)
            store.move(
                "authorized",
                attempt_id="attempt_12345678",
                changes={"authorization_id": "authorization_12345678"},
            )
            event_path = store._event_path(1)
            event = read_json(event_path)
            event["attempt_id"] = "attempt_tampered1"
            write_atomic(event_path, event)
            with self.assertRaisesRegex(StateError, "attempt identity mismatch"):
                store.peek()

    def test_applied_v2_event_rejects_recorded_at_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            event_path = store._event_path(1)
            event = read_json(event_path)
            event["recorded_at"] = "2026-08-10T12:00:01Z"
            write_atomic(event_path, event)
            with self.assertRaisesRegex(StateError, "state-after hash mismatch"):
                store.peek()

    def test_cli_status_is_observation_only_when_repair_is_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            changes = {"authorization_id": "authorization_12345678"}
            store._append_event(
                {
                    "schema_version": 1,
                    "event_id": "event_12345678",
                    "mission_id": "mission_12345678",
                    "sequence": 1,
                    "event_type": "transition",
                    "from_state": "planned",
                    "to_state": "authorized",
                    "attempt_id": None,
                    "recorded_at": NOW,
                    "changes": changes,
                    "payload_sha256": canonical_sha256(changes),
                }
            )
            before = filesystem_snapshot(Path(directory))
            output = StringIO()
            with redirect_stdout(output), redirect_stderr(StringIO()):
                result = main(
                    [
                        "mission",
                        "status",
                        "--state-dir",
                        directory,
                        "--json",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn('"recovery_required": true', output.getvalue())
            self.assertEqual(filesystem_snapshot(Path(directory)), before)

    def test_cli_repair_applies_pending_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            changes = {"authorization_id": "authorization_12345678"}
            store._append_event(
                {
                    "schema_version": 1,
                    "event_id": "event_12345678",
                    "mission_id": "mission_12345678",
                    "sequence": 1,
                    "event_type": "transition",
                    "from_state": "planned",
                    "to_state": "authorized",
                    "attempt_id": None,
                    "recorded_at": NOW,
                    "changes": changes,
                    "payload_sha256": canonical_sha256(changes),
                }
            )
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = main(
                    [
                        "mission",
                        "repair",
                        "--state-dir",
                        directory,
                        "--json",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(store.load()["state"], "authorized")

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
