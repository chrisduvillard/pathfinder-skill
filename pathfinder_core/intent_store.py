from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .intent_rendering import render_charter, render_doctrine, render_roadmap
from .storage import MissionLock, read_json, write_atomic


INTENT_KINDS = ("charter", "roadmap", "doctrine")
RENDERERS = {
    "charter": render_charter,
    "roadmap": render_roadmap,
    "doctrine": render_doctrine,
}


def _normalize_scoped_root(
    repo_root: Path, scoped_root: str | Path
) -> tuple[str, tuple[str, ...]]:
    raw = str(scoped_root).replace("\\", "/")
    if raw == ".":
        return ".", ()
    if not raw:
        raise StateError("scoped root must be a normalized repository-relative path")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        raise StateError("scoped root must be repository-relative")
    parts = tuple(raw.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise StateError("scoped root must be a normalized repository-relative path")
    if parts[0] == ".pathfinder":
        raise StateError("scoped root cannot use the reserved .pathfinder directory")

    current = repo_root
    for part in parts:
        current /= part
        if current.is_symlink():
            raise StateError(f"scoped root must not traverse a symlink: {raw}")
    if not current.is_dir():
        raise StateError(f"scoped root must be an existing directory: {raw}")
    try:
        current.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise StateError("scoped root escapes the repository") from error
    return "/".join(parts), parts


def _write_view_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class IntentStore:
    def __init__(
        self,
        repo_root: Path,
        schema_root: Path | None = None,
        *,
        scoped_root: str | Path = ".",
    ):
        self.repo_root = Path(repo_root)
        self.scoped_root, self._scope_parts = _normalize_scoped_root(
            self.repo_root, scoped_root
        )
        intent_root = self.repo_root / ".pathfinder"
        self.root = (
            intent_root
            if not self._scope_parts
            else intent_root / "scopes" / Path(*self._scope_parts) / "intent"
        )
        self.lock_path = self.root / "intent.lock"
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"

    def _validate_safe_root(self) -> None:
        _normalize_scoped_root(self.repo_root, self.scoped_root)
        current = self.repo_root
        for part in self.root.relative_to(self.repo_root).parts:
            current /= part
            if current.is_symlink():
                raise StateError(f"intent directory must not be a symlink: {current}")
            if current.exists() and not current.is_dir():
                raise StateError(f"intent path must be a directory: {current}")

    def _ensure_safe_root(self) -> None:
        self._validate_safe_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._validate_safe_root()

    def _path(self, kind: str, suffix: str) -> Path:
        if kind not in INTENT_KINDS:
            raise StateError(f"unknown intent kind: {kind}")
        return self.root / f"{kind}.{suffix}"

    def _validate_path(self, path: Path) -> None:
        if path.is_symlink():
            raise StateError(f"intent path must not be a symlink: {path}")
        if path.exists() and not path.is_file():
            raise StateError(f"intent path must be a regular file: {path}")

    def _validate(self, kind: str, document: dict) -> None:
        relative = f"intent/{kind}.schema.json"
        schema = read_json(self.schema_root / relative)
        try:
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for {relative}{suffix}: {error.message}"
            ) from error

    def _validated_documents(self, documents: dict[str, dict]) -> dict[str, dict]:
        if set(documents) != set(INTENT_KINDS):
            raise StateError("intent write requires charter, roadmap, and doctrine JSON")
        for kind in INTENT_KINDS:
            self._validate(kind, documents[kind])
        return documents

    def write_all(self, documents: dict[str, dict]) -> dict[str, str]:
        documents = self._validated_documents(documents)
        views = {kind: RENDERERS[kind](documents[kind]) for kind in INTENT_KINDS}
        self._ensure_safe_root()
        with MissionLock(self.lock_path):
            for kind in INTENT_KINDS:
                self._validate_path(self._path(kind, "json"))
                self._validate_path(self._path(kind, "md"))
            for kind in INTENT_KINDS:
                write_atomic(self._path(kind, "json"), documents[kind])
            for kind in INTENT_KINDS:
                _write_view_atomic(self._path(kind, "md"), views[kind])
        return {kind: str(self._path(kind, "json")) for kind in INTENT_KINDS}

    def load(self, kind: str) -> dict:
        self._validate_safe_root()
        path = self._path(kind, "json")
        self._validate_path(path)
        document = read_json(path)
        self._validate(kind, document)
        return document

    def load_all(self) -> dict[str, dict]:
        return {kind: self.load(kind) for kind in INTENT_KINDS}

    def refresh_views(self) -> dict[str, str]:
        self._ensure_safe_root()
        with MissionLock(self.lock_path):
            documents = self.load_all()
            views = {kind: RENDERERS[kind](documents[kind]) for kind in INTENT_KINDS}
            for kind in INTENT_KINDS:
                path = self._path(kind, "md")
                self._validate_path(path)
                _write_view_atomic(path, views[kind])
        return {kind: str(self._path(kind, "md")) for kind in INTENT_KINDS}
