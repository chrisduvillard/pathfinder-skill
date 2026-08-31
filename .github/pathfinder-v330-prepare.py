from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence in {relative}, found {count}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


storage = r'''from __future__ import annotations

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
from .state import transition, utc_now


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
KNOWN_MUTABLE_STATE_FIELDS = frozenset(
    {
        "authorization_id",
        "attempt_id",
        "worktree_id",
        "worktree_path",
        "branch_id",
        "branch_name",
        "commit_ids",
        "native_goal_id",
        "pr_id",
        "pr_url",
        "terminal_reason",
    }
)
TRANSITION_CHANGE_FIELDS = {
    ("planned", "authorized"): frozenset({"authorization_id", "attempt_id"}),
    (
        "authorized",
        "prepared",
    ): frozenset(
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


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


def write_atomic(path: Path, document: dict) -> None:
    _ensure_private_directory(path.parent)
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
        _fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def canonical_sha256(document: object, hash_field: str | None = None) -> str:
    payload = document
    if hash_field is not None:
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
        _ensure_private_directory(self.path.parent)
        for _attempt in range(2):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if not break_stale or not self._is_stale():
                    raise StateError(f"mission lock is already held: {self.path}")
                self.path.unlink()
                _fsync_directory(self.path.parent)
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self._lease(), stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            _fsync_directory(self.path.parent)
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
        _fsync_directory(self.path.parent)
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

    def peek(self) -> dict:
        """Read and validate canonical state without recovery or any filesystem write."""
        document = read_json(self.state_path)
        self._validate("mission/mission-state.schema.json", document)
        return document

    def load(self) -> dict:
        """Compatibility alias for the now strictly read-only state read."""
        return self.peek()

    def recovery_required(self, document: dict | None = None) -> bool:
        current = document if document is not None else self.peek()
        return self._event_path(current["revision"] + 1).is_file()

    def repair(self) -> dict:
        """Recover one interrupted transition while holding the canonical mission lock."""
        with self.locked():
            document = self.peek()
            repaired = self._recover_interrupted_transition(document)
            self._validate("mission/mission-state.schema.json", repaired)
            return repaired

    def _event_path(self, sequence: int) -> Path:
        return self.events_path / f"{sequence:08d}.json"

    def _validate_payload(self, event: dict) -> None:
        expected = canonical_sha256(event["changes"])
        if event["payload_sha256"] != expected:
            raise StateError("transition event payload hash mismatch")

    def _allowed_changes(self, current: str, target: str) -> frozenset[str]:
        if target == "blocked":
            return frozenset({"terminal_reason"})
        if target in {"abandoned", "merged"}:
            return frozenset()
        return TRANSITION_CHANGE_FIELDS.get((current, target), frozenset())

    def _validate_changes(self, current: str, target: str, changes: dict) -> None:
        immutable = sorted(set(changes) & IMMUTABLE_STATE_FIELDS)
        if immutable:
            raise StateError(f"transition cannot change immutable field: {immutable[0]}")
        unknown = sorted(set(changes) - KNOWN_MUTABLE_STATE_FIELDS)
        if unknown:
            raise StateError(f"transition contains unknown state field: {unknown[0]}")
        unexpected = sorted(set(changes) - self._allowed_changes(current, target))
        if unexpected:
            raise StateError(
                f"transition {current} -> {target} cannot change field: {unexpected[0]}"
            )

    def _previous_event_hash(self, sequence: int, mission_id: str) -> str | None:
        if sequence == 1:
            return None
        previous_path = self._event_path(sequence - 1)
        if not previous_path.is_file():
            raise StateError("transition event chain has a sequence gap")
        previous = read_json(previous_path)
        self._validate("mission/event.schema.json", previous)
        self._validate_payload(previous)
        if previous["mission_id"] != mission_id or previous["sequence"] != sequence - 1:
            raise StateError("transition event chain identity mismatch")
        return canonical_sha256(previous)

    def _candidate_from_event(self, document: dict, event: dict) -> dict:
        self._validate("mission/event.schema.json", event)
        self._validate_payload(event)
        if event["event_type"] != "transition":
            raise StateError("pending mission event is not a transition")
        if event["mission_id"] != document["mission_id"]:
            raise StateError("transition event mission identity mismatch")
        if event["sequence"] != document["revision"] + 1:
            raise StateError("transition event sequence mismatch")
        if event["from_state"] != document["state"]:
            raise StateError("transition event source state mismatch")
        changes = dict(event["changes"])
        self._validate_changes(document["state"], event["to_state"], changes)
        allowed_attempts = {None, document.get("attempt_id"), changes.get("attempt_id")}
        if event.get("attempt_id") not in allowed_attempts:
            raise StateError("transition event attempt identity mismatch")
        if event["schema_version"] >= 2:
            if event["state_before_sha256"] != canonical_sha256(document):
                raise StateError("transition event before-state hash mismatch")
            previous_hash = self._previous_event_hash(
                event["sequence"], document["mission_id"]
            )
            if event["previous_event_sha256"] != previous_hash:
                raise StateError("transition event chain hash mismatch")
        candidate = transition(document, event["to_state"], at=event["recorded_at"])
        candidate.update(changes)
        self._validate("mission/mission-state.schema.json", candidate)
        if (
            event["schema_version"] >= 2
            and event["state_after_sha256"] != canonical_sha256(candidate)
        ):
            raise StateError("transition event after-state hash mismatch")
        return candidate

    def _append_event(self, event: dict, *, current: dict | None = None) -> None:
        self._validate("mission/event.schema.json", event)
        self._validate_payload(event)
        if current is not None:
            self._candidate_from_event(current, event)
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
        recovered = self._candidate_from_event(document, event)
        write_atomic(self.state_path, recovered)
        return recovered

    def move(
        self, target: str, *, attempt_id: str | None = None, changes: dict | None = None
    ) -> dict:
        changes = dict(changes or {})
        with self.locked():
            current = self.peek()
            current = self._recover_interrupted_transition(current)
            if target == current["state"]:
                drift = {
                    key: value for key, value in changes.items() if current.get(key) != value
                }
                if drift:
                    raise StateError("idempotent transition cannot apply new state changes")
                return current
            self._validate_changes(current["state"], target, changes)
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
                "previous_event_sha256": self._previous_event_hash(
                    sequence, current["mission_id"]
                ),
                "state_before_sha256": canonical_sha256(current),
                "state_after_sha256": canonical_sha256(updated),
            }
            self._append_event(event, current=current)
            write_atomic(self.state_path, updated)
            return updated
'''
write("pathfinder_core/storage.py", storage)

cache = r'''from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .errors import StateError


SCHEMA_VERSION = 1


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fsync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            pass
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class CacheIdentity:
    repository: str
    base_commit: str
    scoped_root: str
    route: str
    config_fingerprint: str
    content_fingerprint: str

    def fields(self) -> dict:
        if self.route not in {"prompt-to-goal", "full-exploration"}:
            raise StateError(f"unsupported discovery route: {self.route}")
        return {
            "identity_hash": _hash(self.repository),
            "base_commit": self.base_commit,
            "scope_hash": _hash(self.scoped_root),
            "route": self.route,
            "config_fingerprint": self.config_fingerprint,
            "content_fingerprint": self.content_fingerprint,
        }

    def key(self) -> str:
        canonical = json.dumps(self.fields(), sort_keys=True, separators=(",", ":"))
        return _hash(canonical)


class DiscoveryCache:
    def __init__(self, directory: str | Path, schema_root: str | Path | None = None):
        self.directory = Path(directory)
        root = (
            Path(schema_root)
            if schema_root
            else Path(__file__).resolve().parents[1] / "schemas"
        )
        schema = json.loads(
            (root / "cache/discovery-cache.schema.json").read_text(encoding="utf-8")
        )
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def _path(self, identity: CacheIdentity) -> Path:
        return self.directory / f"{identity.key()}.json"

    def _quarantine(self, path: Path) -> None:
        quarantine = path.with_name(
            f".{path.name}.corrupt-{secrets.token_hex(6)}"
        )
        try:
            os.replace(path, quarantine)
            if os.name == "posix":
                quarantine.chmod(0o600)
            _fsync_directory(path.parent)
        except OSError:
            # Cache corruption must never block source-grounded discovery.
            pass

    def load(self, identity: CacheIdentity) -> dict | None:
        path = self._path(identity)
        if not path.is_file():
            return None
        try:
            entry = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=self._unique_pairs,
            )
        except (OSError, UnicodeError, ValueError):
            self._quarantine(path)
            return None
        errors = sorted(self.validator.iter_errors(entry), key=lambda item: list(item.path))
        if errors:
            return None
        if entry["cache_key"] != identity.key() or any(
            entry[name] != value for name, value in identity.fields().items()
        ):
            return None
        return entry["payload"]

    def store(self, identity: CacheIdentity, payload: dict, created_at: str) -> Path:
        entry = {
            "schema_version": SCHEMA_VERSION,
            "cache_key": identity.key(),
            **identity.fields(),
            "created_at": created_at,
            "payload": payload,
        }
        self.validator.validate(entry)
        self.directory.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.directory.chmod(0o700)
        fd, name = tempfile.mkstemp(prefix=".discovery-", dir=self.directory)
        try:
            if os.name == "posix":
                os.chmod(name, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entry, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self._path(identity))
            if os.name == "posix":
                self._path(identity).chmod(0o600)
            _fsync_directory(self.directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return self._path(identity)

    @staticmethod
    def _unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result
'''
write("pathfinder_core/cache.py", cache)

capabilities = r'''from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Capability:
    status: Availability
    detail: str


def _version(binary: str, args: Iterable[str] = ("--version",)) -> Capability:
    path = shutil.which(binary)
    if not path:
        return Capability(Availability.UNAVAILABLE, f"{binary} not found")
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return Capability(Availability.UNKNOWN, f"{binary} version probe failed")
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0][:160] if output else f"{binary} returned {result.returncode}"
    status = Availability.AVAILABLE if result.returncode == 0 else Availability.UNKNOWN
    return Capability(status, detail)


def probe_capabilities() -> dict:
    python_ok = sys.version_info >= (3, 11)
    schema_ok = importlib.util.find_spec("jsonschema") is not None
    date_format_ok = importlib.util.find_spec("rfc3339_validator") is not None
    controller_available = python_ok and schema_ok and date_format_ok
    dependency_status = (
        Availability.AVAILABLE if controller_available else Availability.UNAVAILABLE
    )
    mission_runner = Capability(
        dependency_status,
        "local host-driven mission protocol is callable; host runtime attestation remains required"
        if controller_available
        else "controller dependencies are unavailable",
    )
    capabilities = {
        "controller_importable": Capability(
            Availability.AVAILABLE, "pathfinder_core importable"
        ),
        "controller_dependencies": Capability(
            dependency_status,
            "Python, jsonschema, and RFC 3339 validation are available"
            if controller_available
            else "install Python 3.11+ and requirements-controller.txt",
        ),
        "controller": Capability(
            dependency_status,
            "controller dependencies satisfied"
            if controller_available
            else "controller dependencies unavailable",
        ),
        "python": Capability(
            Availability.AVAILABLE if python_ok else Availability.UNAVAILABLE,
            platform.python_version(),
        ),
        "schema_validation": Capability(
            Availability.AVAILABLE
            if schema_ok and date_format_ok
            else Availability.UNAVAILABLE,
            "jsonschema and RFC 3339 validation importable"
            if schema_ok and date_format_ok
            else "install requirements-controller.txt",
        ),
        "git": _version("git"),
        "github_cli": _version("gh"),
        "native_goal": Capability(
            Availability.UNKNOWN, "requires host adapter negotiation"
        ),
        "mission_protocol": mission_runner,
        "mission_runner": mission_runner,
        "host_runtime_attestation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "filesystem_sandbox": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "process_isolation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "network_policy": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "credential_isolation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "installed_publication": Capability(
            Availability.UNAVAILABLE,
            "the installed controller has no push, pull-request, merge, release, or deploy command",
        ),
        "source_publication_primitives": Capability(
            Availability.AVAILABLE,
            "default-off source components are present but have no installed caller",
        ),
        "publication": Capability(
            Availability.UNAVAILABLE,
            "publication is intentionally unavailable in the installed controller",
        ),
        "unattended_execution": Capability(
            Availability.UNAVAILABLE,
            "unavailable until every host enforcement capability is positively attested",
        ),
    }
    unattended = all(
        capabilities[name].status is Availability.AVAILABLE
        for name in (
            "controller",
            "python",
            "schema_validation",
            "mission_runner",
            "git",
            "filesystem_sandbox",
            "process_isolation",
            "network_policy",
            "credential_isolation",
        )
    )
    return {
        "schema_version": 1,
        "controller_available": controller_available,
        "runner_available": controller_available,
        "mission_runner_available": (
            mission_runner.status is Availability.AVAILABLE
        ),
        "unattended_execution_eligible": unattended,
        "capabilities": {
            name: asdict(value) for name, value in capabilities.items()
        },
    }


def capabilities_json() -> str:
    return json.dumps(probe_capabilities(), indent=2, sort_keys=True)
'''
write("pathfinder_core/capabilities.py", capabilities)

event_schema = r'''{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pathfinder.local/schemas/mission/event.schema.json",
  "title": "Pathfinder Mission Event",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version", "event_id", "mission_id", "sequence", "event_type",
    "from_state", "to_state", "attempt_id", "recorded_at", "changes",
    "payload_sha256"
  ],
  "properties": {
    "schema_version": {"enum": [1, 2]},
    "event_id": {"type": "string", "pattern": "^event_[a-z0-9][a-z0-9_-]{7,63}$"},
    "mission_id": {"type": "string", "pattern": "^mission_[a-z0-9][a-z0-9_-]{7,63}$"},
    "sequence": {"type": "integer", "minimum": 1},
    "event_type": {"enum": ["transition", "command-started", "command-finished", "reconciled", "blocked"]},
    "from_state": {"type": ["string", "null"], "enum": [null, "planned", "authorized", "prepared", "running", "verifying", "verified", "committed", "published", "awaiting-review", "merged", "blocked", "abandoned"]},
    "to_state": {"enum": ["planned", "authorized", "prepared", "running", "verifying", "verified", "committed", "published", "awaiting-review", "merged", "blocked", "abandoned"]},
    "attempt_id": {"type": ["string", "null"], "pattern": "^attempt_[a-z0-9][a-z0-9_-]{7,63}$"},
    "recorded_at": {"type": "string", "format": "date-time"},
    "changes": {
      "type": "object",
      "propertyNames": {
        "enum": [
          "authorization_id", "attempt_id", "worktree_id", "worktree_path",
          "branch_id", "branch_name", "commit_ids", "native_goal_id",
          "pr_id", "pr_url", "terminal_reason", "schema_version",
          "mission_id", "goal_id", "binding_id", "state", "revision",
          "base_commit", "dirty_policy", "created_at", "updated_at"
        ]
      }
    },
    "payload_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "previous_event_sha256": {
      "oneOf": [
        {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        {"type": "null"}
      ]
    },
    "state_before_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "state_after_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
  },
  "allOf": [
    {
      "if": {"properties": {"schema_version": {"const": 2}}},
      "then": {
        "required": [
          "previous_event_sha256", "state_before_sha256", "state_after_sha256"
        ]
      }
    }
  ]
}
'''
write("schemas/mission/event.schema.json", event_schema)

# Read-only Git really means no optional index refresh.
replace_once(
    "pathfinder_core/repository.py",
    '        config_environment["GIT_TERMINAL_PROMPT"] = "0"\n',
    '        config_environment["GIT_TERMINAL_PROMPT"] = "0"\n'
    '        config_environment["GIT_OPTIONAL_LOCKS"] = "0"\n',
)
replace_once(
    "pathfinder_core/repository.py",
    '            "GIT_CONFIG_NOSYSTEM": "1",\n',
    '            "GIT_CONFIG_NOSYSTEM": "1",\n'
    '            "GIT_OPTIONAL_LOCKS": "0",\n',
)

# Status is observation-only. Recovery is a separate explicit command.
replace_once(
    "pathfinder_core/__main__.py",
    '    status = mission_commands.add_parser("status", help="show current mission state")\n'
    '    status.add_argument("--state-dir", required=True)\n'
    '    status.add_argument("--json", action="store_true", dest="as_json")\n',
    '    status = mission_commands.add_parser("status", help="show current mission state without writes")\n'
    '    status.add_argument("--state-dir", required=True)\n'
    '    status.add_argument("--json", action="store_true", dest="as_json")\n'
    '    repair = mission_commands.add_parser("repair", help="recover one interrupted transition under lock")\n'
    '    repair.add_argument("--state-dir", required=True)\n'
    '    repair.add_argument("--json", action="store_true", dest="as_json")\n',
)
replace_once(
    "pathfinder_core/__main__.py",
    '        if args.command == "mission" and args.mission_command == "status":\n'
    '            state = MissionStore(args.state_dir).load()\n'
    '            if args.as_json:\n'
    '                print(json.dumps(state, indent=2, sort_keys=True))\n'
    '            else:\n'
    '                print(f"mission: {state[\'mission_id\']}")\n'
    '                print(f"state: {state[\'state\']}")\n'
    '                print(f"goal: {state[\'goal_id\']}")\n'
    '                print(f"branch: {state[\'branch_name\'] or \'not prepared\'}")\n'
    '                print(f"pull_request: {state[\'pr_url\'] or \'none\'}")\n'
    '            return 0\n',
    '        if args.command == "mission" and args.mission_command == "status":\n'
    '            store = MissionStore(args.state_dir)\n'
    '            state = store.peek()\n'
    '            recovery_required = store.recovery_required(state)\n'
    '            if args.as_json:\n'
    '                payload = dict(state)\n'
    '                payload["recovery_required"] = recovery_required\n'
    '                print(json.dumps(payload, indent=2, sort_keys=True))\n'
    '            else:\n'
    '                print(f"mission: {state[\'mission_id\']}")\n'
    '                print(f"state: {state[\'state\']}")\n'
    '                print(f"goal: {state[\'goal_id\']}")\n'
    '                print(f"branch: {state[\'branch_name\'] or \'not prepared\'}")\n'
    '                print(f"pull_request: {state[\'pr_url\'] or \'none\'}")\n'
    '                print(f"recovery_required: {str(recovery_required).lower()}")\n'
    '            return 0\n'
    '        if args.command == "mission" and args.mission_command == "repair":\n'
    '            state = MissionStore(args.state_dir).repair()\n'
    '            if args.as_json:\n'
    '                print(json.dumps(state, indent=2, sort_keys=True))\n'
    '            else:\n'
    '                print(f"mission: {state[\'mission_id\']}")\n'
    '                print(f"state: {state[\'state\']}")\n'
    '                print("recovery_required: false")\n'
    '            return 0\n',
)
replace_once(
    "pathfinder_core/__main__.py",
    '            state = store.load()\n'
    '            if state["state"] in {"awaiting-review", "merged", "blocked", "abandoned"}:\n',
    '            state = store.repair()\n'
    '            if state["state"] in {"awaiting-review", "merged", "blocked", "abandoned"}:\n',
)

for relative in ("pathfinder_core/mission.py", "pathfinder_core/mission_host.py"):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    text = text.replace("self.store.load()", "self.store.repair()")
    path.write_text(text, encoding="utf-8")

# Sealed contracts and artifacts are private to the current user on POSIX.
for path in (ROOT / "pathfinder_core").glob("*.py"):
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH", "stat.S_IRUSR"
    )
    path.write_text(text, encoding="utf-8")

state_tests = r'''import copy
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
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
        "created_at": NOW,
        "updated_at": NOW,
    }


def pending_event(store, current, target="authorized", changes=None):
    changes = dict(changes or {"authorization_id": "authorization_12345678"})
    updated = transition(current, target, at=NOW)
    updated.update(changes)
    sequence = updated["revision"]
    previous = None
    if sequence > 1:
        previous = canonical_sha256(read_json(store._event_path(sequence - 1)))
    return {
        "schema_version": 2,
        "event_id": f"event_12345678_{sequence:08d}",
        "mission_id": current["mission_id"],
        "sequence": sequence,
        "event_type": "transition",
        "from_state": current["state"],
        "to_state": target,
        "attempt_id": current.get("attempt_id"),
        "recorded_at": NOW,
        "changes": changes,
        "payload_sha256": canonical_sha256(changes),
        "previous_event_sha256": previous,
        "state_before_sha256": canonical_sha256(current),
        "state_after_sha256": canonical_sha256(updated),
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
            with mock.patch(
                "pathfinder_core.storage.os.replace", side_effect=OSError("crash")
            ):
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

    def test_status_is_read_only_and_repair_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            current = store.peek()
            event = pending_event(store, current)
            store._append_event(event, current=current)
            before = {
                path.relative_to(store.root).as_posix(): (
                    path.read_bytes(), path.stat().st_mtime_ns
                )
                for path in store.root.rglob("*")
                if path.is_file()
            }
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "mission",
                            "status",
                            "--state-dir",
                            str(store.root),
                            "--json",
                        ]
                    ),
                    0,
                )
            after = {
                path.relative_to(store.root).as_posix(): (
                    path.read_bytes(), path.stat().st_mtime_ns
                )
                for path in store.root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertIn('"recovery_required": true', output.getvalue())
            self.assertEqual(store.peek()["state"], "planned")
            repaired = store.repair()
            self.assertEqual(repaired["state"], "authorized")
            self.assertFalse(store.recovery_required(repaired))

    def test_tampered_payload_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            event = pending_event(store, store.peek())
            event["payload_sha256"] = "0" * 64
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "payload hash"):
                store.repair()
            self.assertEqual(store.peek()["state"], "planned")

    def test_immutable_field_injection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            changes = {
                "authorization_id": "authorization_12345678",
                "mission_id": "mission_attacker0",
            }
            event = pending_event(store, store.peek(), changes=changes)
            write_atomic(store._event_path(1), event)
            with self.assertRaisesRegex(StateError, "immutable field"):
                store.repair()

    def test_event_chain_hash_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory))
            store.initialize(initial_state())
            authorized = store.move(
                "authorized",
                changes={"authorization_id": "authorization_12345678"},
            )
            event = pending_event(
                store,
                authorized,
                target="prepared",
                changes={
                    "attempt_id": "attempt_12345678",
                    "worktree_id": "worktree_12345678",
                    "worktree_path": "/tmp/worktree",
                    "branch_id": "branch_12345678",
                    "branch_name": "pathfinder/auto/test",
                },
            )
            event["previous_event_sha256"] = "0" * 64
            write_atomic(store._event_path(2), event)
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

    @unittest.skipUnless(os.name == "posix", "POSIX permission semantics")
    def test_state_and_event_files_are_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MissionStore(Path(directory) / "mission")
            store.initialize(initial_state())
            store.move("authorized")
            self.assertEqual(store.root.stat().st_mode & 0o077, 0)
            self.assertEqual(store.state_path.stat().st_mode & 0o077, 0)
            self.assertEqual(store._event_path(1).stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
'''
write("tests/core/test_state.py", state_tests)

cache_tests = r'''import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pathfinder_core.cache import CacheIdentity, DiscoveryCache


HASH = "a" * 64
NOW = "2026-08-10T12:00:00Z"


class DiscoveryCacheTests(unittest.TestCase):
    def identity(self):
        return CacheIdentity(
            "private/repo",
            "b" * 40,
            "packages/app",
            "full-exploration",
            HASH,
            HASH,
        )

    def test_hit_does_not_persist_private_identity_or_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            path = cache.store(identity, {"findings": ["one"]}, NOW)
            self.assertEqual(cache.load(identity), {"findings": ["one"]})
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("private/repo", raw)
            self.assertNotIn("packages/app", raw)

    def test_commit_scope_route_config_and_content_changes_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            cache.store(identity, {"cached": True}, NOW)
            variants = [
                replace(identity, base_commit="c" * 40),
                replace(identity, scoped_root="packages/other"),
                replace(identity, route="prompt-to-goal"),
                replace(identity, config_fingerprint="d" * 64),
                replace(identity, content_fingerprint="e" * 64),
                replace(identity, repository="private/other"),
            ]
            for variant in variants:
                with self.subTest(variant=variant):
                    self.assertIsNone(cache.load(variant))

    def test_stale_schema_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            path = cache.store(identity, {"cached": True}, NOW)
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["schema_version"] = 0
            path.write_text(json.dumps(entry), encoding="utf-8")
            self.assertIsNone(cache.load(identity))

    def test_malformed_truncated_duplicate_and_invalid_encoding_are_cache_misses(self):
        payloads = [
            b'{"truncated":',
            b'{"schema_version":1,"schema_version":1}',
            b"\xff\xfe\x00\x00",
        ]
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                cache = DiscoveryCache(directory)
                identity = self.identity()
                path = cache.store(identity, {"cached": True}, NOW)
                path.write_bytes(payload)
                self.assertIsNone(cache.load(identity))
                quarantined = list(Path(directory).glob(".*.corrupt-*"))
                self.assertEqual(len(quarantined), 1)

    @unittest.skipUnless(os.name == "posix", "POSIX permission semantics")
    def test_cache_directory_and_entries_are_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            location = Path(directory) / "cache"
            cache = DiscoveryCache(location)
            path = cache.store(self.identity(), {"cached": True}, NOW)
            self.assertEqual(location.stat().st_mode & 0o077, 0)
            self.assertEqual(path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
'''
write("tests/core/test_cache.py", cache_tests)

# Extend repository and capability regressions without replacing the existing coverage.
repository_test = ROOT / "tests/core/test_repository.py"
text = repository_test.read_text(encoding="utf-8")
text = text.replace(
    '            self.assertIn("credential.helper=", command)\n',
    '            self.assertIn("credential.helper=", command)\n'
    '            environment = run.call_args.kwargs["env"]\n'
    '            self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")\n',
)
marker = '\n\nif __name__ == "__main__":\n'
addition = r'''
    def test_repository_inspection_does_not_refresh_git_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            index = root / ".git" / "index"
            tracked = root / "tracked.txt"
            os.utime(tracked, None)
            before_bytes = index.read_bytes()
            before_stat = index.stat()
            inspect_repository(root)
            after_stat = index.stat()
            self.assertEqual(index.read_bytes(), before_bytes)
            self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)
            self.assertEqual(after_stat.st_size, before_stat.st_size)
'''
if marker not in text:
    raise RuntimeError("test_repository.py main marker missing")
repository_test.write_text(text.replace(marker, addition + marker), encoding="utf-8")

capability_test = ROOT / "tests/core/test_capabilities.py"
text = capability_test.read_text(encoding="utf-8")
addition = r'''
    def test_installed_publication_is_explicitly_unavailable(self):
        report = capabilities.probe_capabilities()
        self.assertEqual(
            report["capabilities"]["installed_publication"]["status"],
            "unavailable",
        )
        self.assertEqual(
            report["capabilities"]["publication"]["status"],
            "unavailable",
        )
        self.assertEqual(
            report["capabilities"]["source_publication_primitives"]["status"],
            "available",
        )

    def test_controller_capability_tracks_dependency_availability(self):
        with mock.patch.object(capabilities.sys, "version_info", (3, 10)):
            report = capabilities.probe_capabilities()
        self.assertFalse(report["controller_available"])
        self.assertEqual(
            report["capabilities"]["controller"]["status"], "unavailable"
        )
'''
if marker not in text:
    raise RuntimeError("test_capabilities.py main marker missing")
capability_test.write_text(text.replace(marker, addition + marker), encoding="utf-8")

# Owner-only sealing assertion for generated artifacts.
artifact_test = ROOT / "tests/core/test_artifacts.py"
text = artifact_test.read_text(encoding="utf-8")
needle = '            self.assertEqual((output / "08-final-summary.json").stat().st_mode & 0o222, 0)\n'
replacement = needle + (
    '            if os.name == "posix":\n'
    '                for sealed in (\n'
    '                    goal_path,\n'
    '                    output / "06-goal-binding.json",\n'
    '                    output / "08-final-summary.md",\n'
    '                    output / "08-final-summary.json",\n'
    '                ):\n'
    '                    self.assertEqual(sealed.stat().st_mode & 0o077, 0)\n'
)
if text.count(needle) != 1:
    raise RuntimeError("artifact permission assertion anchor missing")
artifact_test.write_text(text.replace(needle, replacement), encoding="utf-8")

# Clarify the first-run documentation contract.
replace_once(
    "README.md",
    "Pathfinder shows its routes before doing work. Review the proposed scope, proof, safety boundary, and stop condition; then save the Goal or activate it in your host.",
    "A bare Pathfinder invocation shows its routes before doing work; a concrete request starts the matching route directly. Review the proposed scope, proof, safety boundary, and stop condition; then save the Goal or activate it in your host.",
)

operator = ROOT / "docs/operator-guide.md"
if operator.exists():
    text = operator.read_text(encoding="utf-8")
    section = """

## Repair an interrupted local mission

`mission status` is strictly observation-only. It reports `recovery_required: true` when the next transition event exists but canonical state has not advanced. Run the explicit locked repair command only after reviewing that condition:

```bash
bash "<trusted-plugin-root>/scripts/pathfinder-controller.sh" mission repair --state-dir <state-dir> --json
```

Repair verifies event schema, payload, mission and attempt identity, sequence, source and target state, allowed change fields, before/after state hashes, and the event-chain hash before replacing canonical state.
"""
    if "## Repair an interrupted local mission" not in text:
        operator.write_text(text.rstrip() + section + "\n", encoding="utf-8")

# Version and stable-channel metadata.
version_path = ROOT / "VERSION.md"
version_text = version_path.read_text(encoding="utf-8")
version_text, count = re.subn(
    r"^Version:\s+3\.2\.0\s*$", "Version: 3.3.0", version_text, count=1, flags=re.M
)
if count != 1:
    raise RuntimeError("VERSION.md 3.2.0 declaration missing or duplicated")
heading = "Changes in v3.2.0:"
if heading not in version_text:
    raise RuntimeError("VERSION.md v3.2.0 changelog anchor missing")
changes = """Changes in v3.3.0:

- Made mission status strictly read-only and added an explicit locked repair command for interrupted transitions.
- Added payload, identity, sequence, transition-field, before/after-state, and event-chain integrity verification while retaining legacy event readability.
- Prevented read-only Git inspection from refreshing the index with `GIT_OPTIONAL_LOCKS=0`.
- Made malformed, truncated, duplicate-key, and invalid-encoding discovery-cache entries degrade to quarantined cache misses.
- Clarified controller, host-attestation, installed-publication, source-only primitive, and unattended-execution capability states.
- Hardened atomic durability and POSIX privacy for mission state, events, contracts, receipts, artifacts, and cache entries.
- Added regression coverage for every confirmed correctness and safety finding above.

"""
if "Changes in v3.3.0:" not in version_text:
    version_text = version_text.replace(heading, changes + heading, 1)
version_path.write_text(version_text, encoding="utf-8")

for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    document["version"] = "3.3.0"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
    path = ROOT / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    for plugin in document.get("plugins", []):
        if plugin.get("name") == "pathfinder":
            plugin.setdefault("source", {})["ref"] = "v3.3.0"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

# Temporary preparation files must never appear in the final pull-request tree.
for relative in (
    ".github/pathfinder-v330-prepare.py",
    ".github/workflows/prepare-v330.yml",
):
    path = ROOT / relative
    if path.exists():
        path.unlink()
