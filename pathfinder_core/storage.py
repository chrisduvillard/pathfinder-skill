from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .state import ALLOWED_TRANSITIONS, transition


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
SEALED_FILE_MODE = 0o400
IMMUTABLE_STATE_FIELDS = frozenset(
    {
        "schema_version",
        "mission_id",
        "goal_id",
        "binding_id",
        "state",
        "revision",
        "base_commit",
        "dirty_policy",
        "created_at",
        "updated_at",
    }
)
COMMON_TERMINAL_CHANGE_FIELDS = frozenset({"terminal_reason"})
TRANSITION_CHANGE_FIELDS = {
    ("planned", "authorized"): frozenset({"authorization_id"}),
    ("authorized", "prepared"): frozenset(
        {"attempt_id", "worktree_id", "worktree_path", "branch_id", "branch_name"}
    ),
    ("prepared", "running"): frozenset({"native_goal_id"}),
    ("running", "verifying"): frozenset(),
    ("verifying", "running"): frozenset(),
    ("verifying", "verified"): frozenset(),
    ("verified", "committed"): frozenset({"commit_ids"}),
    ("committed", "published"): frozenset({"pr_id", "pr_url"}),
    ("committed", "awaiting-review"): frozenset(),
    ("published", "awaiting-review"): frozenset(),
    ("awaiting-review", "merged"): frozenset(),
}


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_stream(stream):
    """Parse one duplicate-safe JSON value from an already-open text stream."""
    return json.load(stream, object_pairs_hook=_reject_duplicate_keys)


def read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as stream:
            return load_json_stream(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StateError(f"cannot read valid JSON from {path}: {error}") from error


def _chmod_private(path: Path, mode: int) -> None:
    if os.name == "posix":
        path.chmod(mode)


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
    _chmod_private(path, PRIVATE_DIRECTORY_MODE)


def fsync_directory(path: Path) -> None:
    if os.name != "posix" or not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_atomic(path: Path, document: dict) -> None:
    ensure_private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    descriptor = None
    try:
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            PRIVATE_FILE_MODE,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _chmod_private(path, PRIVATE_FILE_MODE)
        fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def canonical_sha256(document: object, hash_field: str | None = None) -> str:
    payload = document
    if hash_field is not None:
        if not isinstance(document, dict):
            raise StateError("hash-field exclusion requires a JSON object")
        payload = {key: value for key, value in document.items() if key != hash_field}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class MissionLock:
    def __init__(self, path: Path, lease_seconds: int = 300):
        self.path = path
        self.lease_seconds = lease_seconds
        self.owner = secrets.token_hex(16)
        self.acquired = False

    def _lease(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "owner": self.owner,
            "pid": os.getpid(),
            "acquired_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(seconds=self.lease_seconds))
            .isoformat()
            .replace("+00:00", "Z"),
        }

    def acquire(self, *, break_stale: bool = False) -> None:
        ensure_private_directory(self.path.parent)
        for _attempt in range(2):
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    PRIVATE_FILE_MODE,
                )
            except FileExistsError:
                if not break_stale or not self._is_stale():
                    raise StateError(f"mission lock is already held: {self.path}")
                self.path.unlink()
                fsync_directory(self.path.parent)
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self._lease(), stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            fsync_directory(self.path.parent)
            self.acquired = True
            return
        raise StateError(f"could not acquire mission lock: {self.path}")

    def _is_stale(self) -> bool:
        try:
            lease = read_json(self.path)
            expires = datetime.fromisoformat(lease["expires_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError, StateError):
            return False
        return expires <= datetime.now(timezone.utc)

    def release(self) -> None:
        if not self.acquired:
            return
        lease = read_json(self.path)
        if lease.get("owner") != self.owner:
            raise StateError("mission lock ownership changed before release")
        self.path.unlink()
        fsync_directory(self.path.parent)
        self.acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()


class MissionStore:
    def __init__(self, root: Path, schema_root: Path | None = None):
        self.root = Path(root)
        self.state_path = self.root / "state.json"
        self.events_path = self.root / "events"
        self.lock_path = self.root / "mission.lock"
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"

    @contextmanager
    def locked(self):
        lock = MissionLock(self.lock_path)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def _validate(self, relative_schema: str, document: dict) -> None:
        schema = read_json(self.schema_root / relative_schema)
        try:
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for {relative_schema}{suffix}: {error.message}"
            ) from error

    def validate(self, relative_schema: str, document: dict) -> None:
        self._validate(relative_schema, document)

    def initialize(self, document: dict) -> None:
        if self.state_path.exists():
            raise StateError(f"mission already initialized: {self.root}")
        self._validate("mission/mission-state.schema.json", document)
        ensure_private_directory(self.root)
        ensure_private_directory(self.events_path)
        write_atomic(self.state_path, document)

    def peek(self) -> dict:
        """Read and validate canonical state without performing recovery or writes."""
        document = read_json(self.state_path)
        self._validate("mission/mission-state.schema.json", document)
        self._validate_committed_event_chain(document)
        return document

    def recovery_required(self, document: dict | None = None) -> bool:
        current = document if document is not None else self.peek()
        event_path = self._event_path(current["revision"] + 1)
        if not event_path.exists():
            return False
        self._recover_candidate(current, read_json(event_path))
        return True

    def load(self) -> dict:
        """Load canonical state, repairing a valid interrupted transition under lock."""
        with self.locked():
            return self._load_locked(recover=True)

    def repair(self) -> dict:
        """Explicitly repair one valid interrupted transition under the mission lock."""
        return self.repair_with_status()[0]

    def repair_with_status(self) -> tuple[dict, bool]:
        """Return repaired state and whether a transition was applied, under one lock."""
        with self.locked():
            document = self._load_locked(recover=False)
            required = self._event_path(document["revision"] + 1).exists()
            if required:
                document = self._recover_interrupted_transition_locked(document)
            return document, required

    def _load_locked(self, *, recover: bool) -> dict:
        document = read_json(self.state_path)
        self._validate("mission/mission-state.schema.json", document)
        self._validate_committed_event_chain(document)
        if recover:
            document = self._recover_interrupted_transition_locked(document)
        return document

    def _event_path(self, sequence: int) -> Path:
        return self.events_path / f"{sequence:08d}.json"

    def _validate_committed_event_chain(self, document: dict) -> None:
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

    def _previous_event_hash(self, sequence: int) -> str | None:
        if sequence == 1:
            return None
        previous_path = self._event_path(sequence - 1)
        if not previous_path.is_file():
            raise StateError("event log sequence has a gap")
        previous = read_json(previous_path)
        self._validate("mission/event.schema.json", previous)
        if previous["sequence"] != sequence - 1:
            raise StateError("previous event sequence does not match its filename")
        return canonical_sha256(previous)

    def _allowed_change_fields(self, from_state: str, to_state: str) -> frozenset[str]:
        if to_state in {"blocked", "abandoned"}:
            return COMMON_TERMINAL_CHANGE_FIELDS
        key = (from_state, to_state)
        if key not in TRANSITION_CHANGE_FIELDS:
            raise StateError(f"transition change policy is undefined: {from_state} -> {to_state}")
        return TRANSITION_CHANGE_FIELDS[key]

    def _validate_changes(self, from_state: str, to_state: str, changes: dict) -> None:
        forbidden = sorted(set(changes) & IMMUTABLE_STATE_FIELDS)
        if forbidden:
            raise StateError(f"transition changes immutable state field: {forbidden[0]}")
        allowed = self._allowed_change_fields(from_state, to_state)
        unexpected = sorted(set(changes) - allowed)
        if unexpected:
            raise StateError(
                f"transition changes field not allowed for {from_state} -> {to_state}: "
                f"{unexpected[0]}"
            )

    def _recover_candidate(self, document: dict, event: dict) -> dict:
        self._validate("mission/event.schema.json", event)
        expected_sequence = document["revision"] + 1
        if event["sequence"] != expected_sequence:
            raise StateError("event sequence does not follow mission revision")
        if event["mission_id"] != document["mission_id"]:
            raise StateError("event mission identity does not match canonical state")
        if event["event_type"] != "transition":
            raise StateError("only transition events can repair mission state")
        if event["from_state"] != document["state"]:
            raise StateError("event source state does not match canonical state")
        if document.get("attempt_id") is not None and event.get("attempt_id") != document.get(
            "attempt_id"
        ):
            raise StateError("event attempt identity does not match canonical state")
        changes = event.get("changes", {})
        if event["payload_sha256"] != canonical_sha256(changes):
            raise StateError("event payload hash does not match transition changes")
        self._validate_changes(event["from_state"], event["to_state"], changes)
        previous_hash = self._previous_event_hash(event["sequence"])
        if event["schema_version"] >= 2:
            if event["previous_event_sha256"] != previous_hash:
                raise StateError("event chain hash does not match previous event")
            if event["state_before_sha256"] != canonical_sha256(document):
                raise StateError("event state-before hash does not match canonical state")
        recovered = transition(document, event["to_state"], at=event["recorded_at"])
        recovered.update(changes)
        self._validate("mission/mission-state.schema.json", recovered)
        if event["schema_version"] >= 2 and event["state_after_sha256"] != canonical_sha256(
            recovered
        ):
            raise StateError("event state-after hash does not match recovered state")
        return recovered

    def _append_event(self, event: dict, *, current: dict, updated: dict) -> None:
        self._validate("mission/event.schema.json", event)
        if self._recover_candidate(current, event) != updated:
            raise StateError("event does not reproduce the proposed mission state")
        ensure_private_directory(self.events_path)
        path = self._event_path(event["sequence"])
        if path.exists():
            if read_json(path) == event:
                return
            raise StateError(f"event sequence already exists: {event['sequence']}")
        write_atomic(path, event)
        _chmod_private(path, SEALED_FILE_MODE)

    def _recover_interrupted_transition_locked(self, document: dict) -> dict:
        next_event_path = self._event_path(document["revision"] + 1)
        if not next_event_path.exists():
            return document
        recovered = self._recover_candidate(document, read_json(next_event_path))
        write_atomic(self.state_path, recovered)
        return recovered

    def move(
        self, target: str, *, attempt_id: str | None = None, changes: dict | None = None
    ) -> dict:
        changes = dict(changes or {})
        with self.locked():
            current = self._load_locked(recover=True)
            if target == current["state"]:
                drift = {key: value for key, value in changes.items() if current.get(key) != value}
                if drift:
                    raise StateError("idempotent transition cannot apply new state changes")
                return current
            self._validate_changes(current["state"], target, changes)
            if current.get("attempt_id") is not None and attempt_id != current.get("attempt_id"):
                raise StateError("transition attempt identity does not match canonical state")
            updated = transition(current, target)
            updated.update(changes)
            self._validate("mission/mission-state.schema.json", updated)
            sequence = updated["revision"]
            event = {
                "schema_version": 2,
                "event_id": f"event_{current['mission_id'][8:]}_{sequence:08d}",
                "mission_id": current["mission_id"],
                "sequence": sequence,
                "event_type": "transition",
                "from_state": current["state"],
                "to_state": target,
                "attempt_id": attempt_id,
                "recorded_at": updated["updated_at"],
                "changes": changes,
                "payload_sha256": canonical_sha256(changes),
                "previous_event_sha256": self._previous_event_hash(sequence),
                "state_before_sha256": canonical_sha256(current),
                "state_after_sha256": canonical_sha256(updated),
            }
            self._append_event(event, current=current, updated=updated)
            write_atomic(self.state_path, updated)
            return updated
