import copy
import json
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
        "schema_version": 1,
        "mission_id": "mission_12345678",
        "goal_id": "goal_12345678",
        "binding_id": "binding_12345678",
        "authorization_id": None,
        "attempt_id": None,
        "state": "planned",
        "revision": 0,
        "base_commit": COMMIT,
        "dirty_policy": "block",
        "worktree_id": None,
        "worktree_path": None,
        "branch_id": None,
        "branch_name": None,
        "commit_ids": [],
        "native_goal_id": None,
        "pr_id": None,
        "pr_url": None,
        "terminal_reason": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def transition_event(
    state: dict,
    target: str,
    changes: dict | None = None,
    *,
    previous_event_sha256: str | None = None,
) -> tuple[dict, dict]:
    changes = dict(changes or {})
    updated = transition(state, target, at=NOW)
    updated.update(changes)
    event = {
        "schema_version": 2,
        "event_id": f"event_12345678_{updated['revision']:08d}",
        "mission_id": state["mission_id"],
        "sequence": updated["revision"],
        "event_type": "transition",
        "from_state": state["state"],
        "to_state": target,
        "attempt_id": state["attempt_id"],
        "recorded_at": NOW,
        "changes": changes,
        "payload_sha256": canonical_sha256(changes),
        "previous_event_sha256": previous_event_sha256,
        "state_before_sha256": canonical_sha256(state),
        "state_after_sha256": canonical_sha256(updated),
    }
    return event, updated


def filesystem_snapshot(root: Path) -> dict:
    result = {}
    paths = [root, *sorted(root.rglob("*"))]
    for path in paths:
        stat_result = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        result[relative] = {
            "mode": stat_result.st_mode,
            "size": stat_result.st_size,
            "mtime_ns": stat_result.st_mtime_ns,
            "content": path.read_bytes() if path.is_file() else None,
        }
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

    def test_atomic_replace_syncs_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            with mock.patch("pathfinder_core.storage.fsync_directory") as sync:
                write_atomic(path, {"value": "new"})
            sync.assert_called_with(path.parent)

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

    def test_store_recovers_valid_event_written_before_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, updated = transition_event(
                state,
                "authorized",
                {"authorization_id": "authorization_12345678"},
            )
            write_atomic(store._event_path(1), event)
            recovered = store.load()
            self.assertEqual(recovered, updated)


    def test_store_recovers_legacy_v1_event_when_payload_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, updated = transition_event(
                state,
                "authorized",
                {"authorization_id": "authorization_12345678"},
            )
            event["schema_version"] = 1
            for field in (
                "previous_event_sha256",
                "state_before_sha256",
                "state_after_sha256",
            ):
                event.pop(field)
            write_atomic(store._event_path(1), event)
            self.assertEqual(store.repair(), updated)

    def test_status_peek_is_byte_for_byte_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, _updated = transition_event(
                state,
                "authorized",
                {"authorization_id": "authorization_12345678"},
            )
            write_atomic(store._event_path(1), event)
            before = filesystem_snapshot(store.root)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(
                    main(["mission", "status", "--state-dir", str(store.root), "--json"]),
                    0,
                )
            after = filesystem_snapshot(store.root)
            self.assertEqual(before, after)
            self.assertEqual(store.peek()["state"], "planned")
            self.assertTrue(store.recovery_required())

    def test_explicit_repair_applies_pending_event(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, updated = transition_event(
                state,
                "authorized",
                {"authorization_id": "authorization_12345678"},
            )
            write_atomic(store._event_path(1), event)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(
                    main(["mission", "repair", "--state-dir", str(store.root), "--json"]),
                    0,
                )
            self.assertEqual(store.peek(), updated)
            self.assertFalse(store.recovery_required())

    def test_recovery_rejects_wrong_payload_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, _updated = transition_event(
                state,
                "authorized",
                {"authorization_id": "authorization_12345678"},
            )
            event["payload_sha256"] = "0" * 64
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "payload hash"):
                store.repair()
            self.assertEqual(store.peek(), state)

    def test_recovery_rejects_state_before_and_after_hash_drift(self):
        for field in ("state_before_sha256", "state_after_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                store = MissionStore(Path(directory))
                state = initial_state()
                store.initialize(state)
                event, _updated = transition_event(
                    state,
                    "authorized",
                    {"authorization_id": "authorization_12345678"},
                )
                event[field] = "0" * 64
                write_atomic(store._event_path(1), event)
                with self.assertRaisesRegex(StateError, "state-(before|after) hash"):
                    store.repair()
                self.assertEqual(store.peek(), state)

    def test_recovery_rejects_cross_mission_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            event, _updated = transition_event(state, "authorized")
            event["mission_id"] = "mission_different1"
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "mission identity"):
                store.repair()

    def test_recovery_rejects_transition_field_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            state = initial_state()
            store.initialize(state)
            changes = {"branch_name": "pathfinder/auto/injected"}
            event, _updated = transition_event(state, "authorized", changes)
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "not allowed"):
                store.repair()

    def test_move_rejects_immutable_field_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            with self.assertRaisesRegex(StateError, "immutable.*mission_id"):
                store.move(
                    "authorized",
                    changes={"mission_id": "mission_different1"},
                )

    def test_move_rejects_attempt_identity_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            state = initial_state()
            state["attempt_id"] = "attempt_12345678"
            store = MissionStore(Path(directory))
            store.initialize(state)
            with self.assertRaisesRegex(StateError, "attempt identity"):
                store.move("authorized", attempt_id="attempt_different1")

    def test_event_chain_is_tamper_evident(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            first = store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            second = store.move(
                "prepared",
                changes={
                    "attempt_id": "attempt_12345678",
                    "worktree_id": "worktree_12345678",
                    "worktree_path": "/tmp/worktree",
                    "branch_id": "branch_12345678",
                    "branch_name": "pathfinder/auto/test",
                },
            )
            event_one = read_json(store._event_path(1))
            event_two = read_json(store._event_path(2))
            self.assertEqual(event_one["schema_version"], 2)
            self.assertEqual(event_two["previous_event_sha256"], canonical_sha256(event_one))
            self.assertEqual(event_two["state_before_sha256"], canonical_sha256(first))
            self.assertEqual(event_two["state_after_sha256"], canonical_sha256(second))

            event_two["previous_event_sha256"] = "0" * 64
            write_atomic(store._event_path(2), event_two)
            write_atomic(store.state_path, first)
            with self.assertRaisesRegex(StateError, "chain hash"):
                store.repair()

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

    @unittest.skipUnless(os.name == "posix", "POSIX mode semantics")
    def test_mission_state_is_owner_only_and_events_are_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory) / "mission")
            store.initialize(initial_state())
            store.move("authorized")
            self.assertEqual(store.root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(store.events_path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(store.state_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(store._event_path(1).stat().st_mode & 0o777, 0o400)


if __name__ == "__main__":
    unittest.main()
