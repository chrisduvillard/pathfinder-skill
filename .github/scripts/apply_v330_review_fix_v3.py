from pathlib import Path

storage_path = Path("pathfinder_core/storage.py")
storage = storage_path.read_text(encoding="utf-8")

if "from .state import ALLOWED_TRANSITIONS, transition" not in storage:
    storage = storage.replace(
        "from .state import transition\n",
        "from .state import ALLOWED_TRANSITIONS, transition\n",
        1,
    )

method = '''    def _validate_committed_event_chain(self, document: dict) -> None:
        """Validate every committed event and bind the v2 tip to canonical state."""
        revision = int(document["revision"])
        if revision == 0:
            return
        previous_event = None
        previous_to_state = None
        previous_v2_state_after = None
        seen_v2 = False
        tracked_attempt_id = None
        for sequence in range(1, revision + 1):
            path = self._event_path(sequence)
            if not path.is_file():
                raise StateError(f"event chain is missing committed event {sequence}")
            event = read_json(path)
            self._validate("mission/event.schema.json", event)
            if event["event_type"] != "transition":
                raise StateError("committed event chain contains a non-transition event")
            if event["mission_id"] != document["mission_id"]:
                raise StateError("committed event chain mission identity drift")
            if event["sequence"] != sequence:
                raise StateError("committed event chain sequence drift")
            if sequence == 1 and event["from_state"] != "planned":
                raise StateError("committed event chain does not begin at planned")
            if previous_to_state is not None and event["from_state"] != previous_to_state:
                raise StateError("committed event chain state continuity drift")
            if event["to_state"] not in ALLOWED_TRANSITIONS[event["from_state"]]:
                raise StateError(
                    "committed event chain contains a forbidden transition: "
                    f"{event['from_state']} -> {event['to_state']}"
                )
            changes = dict(event.get("changes", {}))
            self._validate_changes(event["from_state"], event["to_state"], changes)
            if event["payload_sha256"] != canonical_sha256(changes):
                raise StateError("committed event chain payload hash mismatch")
            if tracked_attempt_id is not None and event.get("attempt_id") != tracked_attempt_id:
                raise StateError("committed event chain attempt identity drift")
            if event["schema_version"] >= 2:
                expected_previous = (
                    None if previous_event is None else canonical_sha256(previous_event)
                )
                if event["previous_event_sha256"] != expected_previous:
                    raise StateError("committed event chain previous hash mismatch")
                if seen_v2 and event["state_before_sha256"] != previous_v2_state_after:
                    raise StateError("committed event chain state hash continuity drift")
                previous_v2_state_after = event["state_after_sha256"]
                seen_v2 = True
            elif seen_v2:
                raise StateError("committed event chain cannot downgrade its schema version")
            if "attempt_id" in changes:
                tracked_attempt_id = changes["attempt_id"]
            previous_event = event
            previous_to_state = event["to_state"]
        if previous_to_state != document["state"]:
            raise StateError("committed event chain tip state drift")
        if tracked_attempt_id != document.get("attempt_id"):
            raise StateError("committed event chain attempt tip drift")
        if (
            previous_event is not None
            and previous_event["schema_version"] >= 2
            and previous_event["state_after_sha256"] != canonical_sha256(document)
        ):
            raise StateError("committed event chain tip does not match canonical state")

'''
marker = "    def _previous_event_hash(self, sequence: int) -> str | None:\n"
if "def _validate_committed_event_chain" not in storage:
    if marker not in storage:
        raise SystemExit("could not locate previous-event hash method")
    storage = storage.replace(marker, method + marker, 1)

peek_anchor = '        self._validate("mission/mission-state.schema.json", document)\n        return document\n\n    def recovery_required'
peek_replacement = '        self._validate("mission/mission-state.schema.json", document)\n        self._validate_committed_event_chain(document)\n        return document\n\n    def recovery_required'
if peek_replacement not in storage:
    if peek_anchor not in storage:
        raise SystemExit("could not locate observation-only peek body")
    storage = storage.replace(peek_anchor, peek_replacement, 1)

load_anchor = '    def _load_locked(self, *, recover: bool) -> dict:\n        document = read_json(self.state_path)\n        self._validate("mission/mission-state.schema.json", document)\n        if recover:'
load_replacement = '    def _load_locked(self, *, recover: bool) -> dict:\n        document = read_json(self.state_path)\n        self._validate("mission/mission-state.schema.json", document)\n        self._validate_committed_event_chain(document)\n        if recover:'
if load_replacement not in storage:
    if load_anchor not in storage:
        raise SystemExit("could not locate locked load body")
    storage = storage.replace(load_anchor, load_replacement, 1)

storage_path.write_text(storage, encoding="utf-8")

test_path = Path("tests/core/test_state.py")
tests = test_path.read_text(encoding="utf-8")
if "test_committed_event_chain_rejects_older_event_tampering" not in tests:
    insertion = '''
    def test_committed_event_chain_rejects_older_event_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(copy.deepcopy(initial_state()))
            store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            store.move(
                "prepared",
                attempt_id="attempt_12345678",
                changes={
                    "attempt_id": "attempt_12345678",
                    "worktree_id": "worktree_12345678",
                    "worktree_path": "/tmp/worktree",
                    "branch_id": "branch_12345678",
                    "branch_name": "pathfinder/auto/test",
                },
            )
            first_path = store._event_path(1)
            first = read_json(first_path)
            first["changes"] = {"authorization_id": "authorization_87654321"}
            first["payload_sha256"] = canonical_sha256(first["changes"])
            write_atomic(first_path, first)
            with self.assertRaisesRegex(StateError, "previous hash mismatch"):
                store.peek()

    def test_committed_event_chain_tip_is_bound_to_canonical_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(copy.deepcopy(initial_state()))
            store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            state = read_json(store.state_path)
            state["authorization_id"] = "authorization_87654321"
            write_atomic(store.state_path, state)
            with self.assertRaisesRegex(
                StateError, "tip does not match canonical state"
            ):
                store.peek()
'''
    footer = '\n\nif __name__ == "__main__":\n'
    if footer not in tests:
        raise SystemExit("could not locate test module footer")
    tests = tests.replace(footer, "\n" + insertion + footer, 1)
    test_path.write_text(tests, encoding="utf-8")
