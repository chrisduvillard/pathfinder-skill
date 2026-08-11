from __future__ import annotations

import json
import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .state import transition, utc_now


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, json.JSONDecodeError) as error:
        raise StateError(f"cannot read valid JSON from {path}: {error}") from error


def write_atomic(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if not break_stale or not self._is_stale():
                    raise StateError(f"mission lock is already held: {self.path}")
                self.path.unlink()
                continue
            with os.fdopen(descriptor, "w") as stream:
                json.dump(self._lease(), stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
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

    def load(self) -> dict:
        document = read_json(self.state_path)
        document = self._recover_interrupted_transition(document)
        self._validate("mission/mission-state.schema.json", document)
        return document

    def _event_path(self, sequence: int) -> Path:
        return self.events_path / f"{sequence:08d}.json"

    def _append_event(self, event: dict) -> None:
        self._validate("mission/event.schema.json", event)
        path = self._event_path(event["sequence"])
        if path.exists():
            if read_json(path) == event:
                return
            raise StateError(f"event sequence already exists: {event['sequence']}")
        write_atomic(path, event)

    def _recover_interrupted_transition(self, document: dict) -> dict:
        next_event_path = self._event_path(document["revision"] + 1)
        if not next_event_path.exists():
            return document
        event = read_json(next_event_path)
        if event.get("event_type") != "transition" or event.get("from_state") != document["state"]:
            raise StateError("event log and mission state cannot be reconciled")
        recovered = transition(document, event["to_state"], at=event["recorded_at"])
        recovered.update(event.get("changes", {}))
        self._validate("mission/mission-state.schema.json", recovered)
        write_atomic(self.state_path, recovered)
        return recovered

    def move(
        self, target: str, *, attempt_id: str | None = None, changes: dict | None = None
    ) -> dict:
        changes = dict(changes or {})
        with self.locked():
            current = self.load()
            if target == current["state"]:
                drift = {key: value for key, value in changes.items() if current.get(key) != value}
                if drift:
                    raise StateError("idempotent transition cannot apply new state changes")
                return current
            updated = transition(current, target)
            updated.update(changes)
            sequence = updated["revision"]
            payload_hash = hashlib.sha256(
                json.dumps(changes, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            event = {
                "schema_version": 1,
                "event_id": f"event_{current['mission_id'][8:]}_{sequence:08d}",
                "mission_id": current["mission_id"],
                "sequence": sequence,
                "event_type": "transition",
                "from_state": current["state"],
                "to_state": target,
                "attempt_id": attempt_id,
                "recorded_at": updated["updated_at"],
                "changes": changes,
                "payload_sha256": payload_hash,
            }
            self._append_event(event)
            self._validate("mission/mission-state.schema.json", updated)
            write_atomic(self.state_path, updated)
            return updated
