from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .state import transition


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

_TRANSITION_CHANGE_FIELDS = {
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

_TERMINAL_CHANGE_FIELDS = {
    "blocked": frozenset({"terminal_reason"}),
    "abandoned": frozenset(),
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


def ensure_private_directory(path: Path) -> None:
    """Create a controller-owned directory and keep it owner-only on POSIX."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix" and hasattr(os, "getuid"):
        try:
            metadata = path.stat()
            if metadata.st_uid == os.getuid():
                path.chmod(0o700)
        except OSError as error:
            raise StateError(f"cannot secure directory {path}: {error}") from error


def fsync_directory(path: Path) -> None:
    """Persist a directory entry update where the platform supports it."""
    if os.name != "posix":
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Some filesystems do not support directory fsync. The file itself has
        # already been synced, so retain the strongest available guarantee.
        pass
    finally:
        os.close(descriptor)


def write_atomic(path: Path, document: dict) -> None:
    ensure_private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    descriptor = None
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            path.chmod(0o600)
        fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def canonical_sha256(document: object, hash_field: str | None = None) -> str:
    payload = document
    if hash_field is not None:
        payload = {
            key: value
            for key, value in document.items()
            if key != hash_field
        }
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
                    self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
            except FileExistsError:
                if not break_stale or not self._is_stale():
                    raise StateError(f"mission lock is already held: {self.path}")
                self.path.unlink()
                fsync_directory(self.path.parent)
                continue
            with os.fdopen(descriptor, "w") as stream:
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
        write_atomic(self.state_path, document)

    def _event_path(self, sequence: int) -> Path:
        return self.events_path / f"{sequence:08d}.json"

    @staticmethod
    def _allowed_change_fields(source: str, target: str) -> frozenset[str]:
        if target in _TERMINAL_CHANGE_FIELDS:
            return _TERMINAL_CHANGE_FIELDS[target]
        return _TRANSITION_CHANGE_FIELDS.get((source, target), frozenset())

    def _validate_changes(self, source: str, target: str, changes: dict) -> None:
        supplied = set(changes)
        immutable = sorted(supplied & IMMUTABLE_STATE_FIELDS)
        if immutable:
            raise StateError(
                f"transition changes cannot overwrite immutable field: {immutable[0]}"
            )
        allowed = self._allowed_change_fields(source, target)
        unexpected = sorted(supplied - allowed)
        if unexpected:
            raise StateError(
                f"transition {source} -> {target} cannot change field: {unexpected[0]}"
            )

    def _validate_event_payload(self, event: dict) -> None:
        expected = canonical_sha256(event["changes"])
        if event["payload_sha256"] != expected:
            raise StateError("mission event payload hash mismatch")

    def _validate_history(self, document: dict) -> dict | None:
        previous = None
        previous_state_after = None
        for sequence in range(1, document["revision"] + 1):
            path = self._event_path(sequence)
            if not path.is_file():
                raise StateError(f"mission event history is missing sequence {sequence}")
            event = read_json(path)
            self._validate("mission/event.schema.json", event)
            self._validate_event_payload(event)
            if event["mission_id"] != document["mission_id"]:
                raise StateError("mission event identity mismatch")
            if event["sequence"] != sequence:
                raise StateError("mission event sequence mismatch")
            if event["event_type"] != "transition":
                raise StateError("mission state history contains a non-transition event")
            if previous is not None and event["from_state"] != previous["to_state"]:
                raise StateError("mission event state chain mismatch")
            self._validate_changes(event["from_state"], event["to_state"], event["changes"])
            try:
                transition(
                    {"state": event["from_state"], "revision": sequence - 1},
                    event["to_state"],
                    at=event["recorded_at"],
                )
            except StateError as error:
                raise StateError("mission event contains a forbidden transition") from error
            if event["schema_version"] >= 2:
                if sequence == 1:
                    if event["previous_event_sha256"] is not None:
                        raise StateError("first mission event cannot name a previous event")
                else:
                    if event["previous_event_sha256"] != canonical_sha256(previous):
                        raise StateError("mission event chain hash mismatch")
                if (
                    previous_state_after is not None
                    and event["state_before_sha256"] != previous_state_after
                ):
                    raise StateError("mission event state hash chain mismatch")
                previous_state_after = event["state_after_sha256"]
            else:
                previous_state_after = None
            previous = event
        if previous is not None:
            if previous["to_state"] != document["state"]:
                raise StateError("mission state does not match its latest event")
            if (
                previous["schema_version"] >= 2
                and previous["state_after_sha256"] != canonical_sha256(document)
            ):
                raise StateError("mission state hash does not match its latest event")
        return previous

    def _candidate_from_event(self, document: dict, event: dict) -> dict:
        self._validate("mission/event.schema.json", event)
        self._validate_event_payload(event)
        expected_sequence = document["revision"] + 1
        if event["mission_id"] != document["mission_id"]:
            raise StateError("pending mission event identity mismatch")
        if event["sequence"] != expected_sequence:
            raise StateError("pending mission event sequence mismatch")
        if event["event_type"] != "transition":
            raise StateError("pending mission event is not a transition")
        if event["from_state"] != document["state"]:
            raise StateError("event log and mission state cannot be reconciled")
        self._validate_changes(event["from_state"], event["to_state"], event["changes"])
        candidate = transition(
            document, event["to_state"], at=event["recorded_at"]
        )
        candidate.update(event["changes"])
        self._validate("mission/mission-state.schema.json", candidate)
        expected_attempt = candidate.get("attempt_id")
        if event["schema_version"] >= 2 and event["attempt_id"] != expected_attempt:
            raise StateError("pending mission event attempt identity mismatch")
        if event["schema_version"] >= 2:
            if event["state_before_sha256"] != canonical_sha256(document):
                raise StateError("pending mission event state-before hash mismatch")
            if event["state_after_sha256"] != canonical_sha256(candidate):
                raise StateError("pending mission event state-after hash mismatch")
            previous = (
                read_json(self._event_path(document["revision"]))
                if document["revision"] > 0
                else None
            )
            expected_previous = canonical_sha256(previous) if previous else None
            if event["previous_event_sha256"] != expected_previous:
                raise StateError("pending mission event previous-event hash mismatch")
        return candidate

    def _read_state(self) -> dict:
        document = read_json(self.state_path)
        self._validate("mission/mission-state.schema.json", document)
        self._validate_history(document)
        return document

    def _pending_event(self, document: dict) -> tuple[dict, dict] | None:
        path = self._event_path(document["revision"] + 1)
        if not path.exists():
            return None
        if not path.is_file():
            raise StateError("pending mission event must be a regular file")
        event = read_json(path)
        candidate = self._candidate_from_event(document, event)
        return event, candidate

    def peek(self) -> dict:
        """Return a validated, observation-only mission snapshot."""
        document = self._read_state()
        pending = self._pending_event(document)
        event = pending[0] if pending else None
        return {
            "state": deepcopy(document),
            "recovery_required": event is not None,
            "pending_event": (
                {
                    "event_id": event["event_id"],
                    "sequence": event["sequence"],
                    "from_state": event["from_state"],
                    "to_state": event["to_state"],
                    "recorded_at": event["recorded_at"],
                }
                if event
                else None
            ),
        }

    def load(self) -> dict:
        """Read current state without writing; require explicit repair when needed."""
        snapshot = self.peek()
        if snapshot["recovery_required"]:
            raise StateError("mission repair required before state can be loaded")
        return snapshot["state"]

    def _repair_locked(self) -> dict:
        document = self._read_state()
        pending = self._pending_event(document)
        if pending is None:
            return document
        _event, recovered = pending
        write_atomic(self.state_path, recovered)
        return recovered

    def repair(self) -> dict:
        """Recover one interrupted transition under the mission lock."""
        with self.locked():
            return self._repair_locked()

    def _append_event(self, event: dict) -> None:
        self._validate("mission/event.schema.json", event)
        self._validate_event_payload(event)
        path = self._event_path(event["sequence"])
        if path.exists():
            if read_json(path) == event:
                return
            raise StateError(f"event sequence already exists: {event['sequence']}")
        write_atomic(path, event)

    def move(
        self, target: str, *, attempt_id: str | None = None, changes: dict | None = None
    ) -> dict:
        changes = dict(changes or {})
        with self.locked():
            current = self._repair_locked()
            if target == current["state"]:
                drift = {
                    key: value
                    for key, value in changes.items()
                    if current.get(key) != value
                }
                if drift:
                    raise StateError("idempotent transition cannot apply new state changes")
                return current
            self._validate_changes(current["state"], target, changes)
            updated = transition(current, target)
            updated.update(changes)
            self._validate("mission/mission-state.schema.json", updated)
            sequence = updated["revision"]
            previous = (
                read_json(self._event_path(sequence - 1)) if sequence > 1 else None
            )
            event_attempt_id = updated.get("attempt_id")
            if attempt_id is not None and attempt_id != event_attempt_id:
                raise StateError("transition attempt identity does not match updated state")
            event = {
                "schema_version": 2,
                "event_id": f"event_{current['mission_id'][8:]}_{sequence:08d}",
                "mission_id": current["mission_id"],
                "sequence": sequence,
                "event_type": "transition",
                "from_state": current["state"],
                "to_state": target,
                "attempt_id": event_attempt_id,
                "recorded_at": updated["updated_at"],
                "changes": changes,
                "payload_sha256": canonical_sha256(changes),
                "previous_event_sha256": (
                    canonical_sha256(previous) if previous is not None else None
                ),
                "state_before_sha256": canonical_sha256(current),
                "state_after_sha256": canonical_sha256(updated),
            }
            self._append_event(event)
            write_atomic(self.state_path, updated)
            return updated
