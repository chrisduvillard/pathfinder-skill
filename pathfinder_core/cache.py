from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .errors import StateError
from .storage import ensure_private_directory, fsync_directory


SCHEMA_VERSION = 1


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
        root = Path(schema_root) if schema_root else Path(__file__).resolve().parents[1] / "schemas"
        schema = json.loads((root / "cache/discovery-cache.schema.json").read_text())
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.warnings: list[str] = []

    def _path(self, identity: CacheIdentity) -> Path:
        return self.directory / f"{identity.key()}.json"

    def _warn(self, message: str) -> None:
        self.warnings.append(message)

    def _quarantine(self, path: Path, reason: str) -> None:
        quarantine = path.with_name(
            f".{path.stem}.corrupt-{secrets.token_hex(6)}{path.suffix}"
        )
        try:
            os.replace(path, quarantine)
            fsync_directory(path.parent)
            self._warn(
                f"quarantined invalid discovery cache entry {path.name}: {reason}"
            )
        except OSError as error:
            self._warn(
                f"ignored invalid discovery cache entry {path.name}; "
                f"quarantine failed: {error}"
            )

    def load(self, identity: CacheIdentity) -> dict | None:
        path = self._path(identity)
        try:
            if not path.is_file():
                return None
        except OSError as error:
            self._warn(f"discovery cache unavailable for {path.name}: {error}")
            return None
        try:
            entry = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=self._unique_pairs,
            )
        except (OSError, UnicodeError, ValueError) as error:
            self._quarantine(path, str(error))
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
        entry = {"schema_version": SCHEMA_VERSION, "cache_key": identity.key(), **identity.fields(), "created_at": created_at, "payload": payload}
        self.validator.validate(entry)
        ensure_private_directory(self.directory)
        fd, name = tempfile.mkstemp(prefix=".discovery-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entry, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            target = self._path(identity)
            os.replace(name, target)
            if os.name == "posix":
                target.chmod(0o600)
            fsync_directory(self.directory)
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
