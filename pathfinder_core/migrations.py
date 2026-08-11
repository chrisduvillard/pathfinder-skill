from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from .errors import StateError
from .intent_store import INTENT_KINDS, IntentStore
from .storage import MissionStore, read_json


INTENT_FILES = {"charter": "charter.md", "roadmap": "roadmap.md", "doctrine": "doctrine.md"}
INTENT_SUFFIXES = ("json", "md")


def _atomic_write(path: Path, content: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _migrate_intent_text(kind: str, text: str) -> str:
    marker = re.search(rf"pathfinder:{kind} v(\d+)", text)
    if not marker:
        raise StateError(f"{kind} intent marker missing")
    if marker.group(1) != "1":
        raise StateError(f"unsupported {kind} intent version: {marker.group(1)}")
    if re.search(r"^intent_clarity: (resolved|unresolved)(?=\r?$)", text, re.MULTILINE):
        return text
    legacy = re.search(r"^clarity: (resolved|unresolved)(?=\r?$)", text, re.MULTILINE)
    if legacy:
        return text[: legacy.start()] + "intent_clarity: unresolved" + text[legacy.end() :]
    completion = re.search(r"^completion: (complete|incomplete)(?=\r?$)", text, re.MULTILINE)
    if not completion:
        raise StateError(f"{kind} completion metadata missing")
    return text[: completion.end()] + "\nintent_clarity: unresolved" + text[completion.end() :]


def migrate_intent(root: str | Path, backup_dir: str | Path) -> dict:
    intent_dir = Path(root).resolve() / ".pathfinder"
    backup = Path(backup_dir).resolve()
    if backup.exists():
        raise StateError(f"backup destination already exists: {backup}")
    originals, migrated = {}, {}
    for kind, filename in INTENT_FILES.items():
        path = intent_dir / filename
        if not path.is_file() or path.is_symlink():
            raise StateError(f"safe migration requires a regular {filename}")
        originals[path] = path.read_bytes()
        migrated[path] = _migrate_intent_text(kind, originals[path].decode("utf-8")).encode("utf-8")
    backup.mkdir(parents=True)
    for path, content in originals.items():
        (backup / path.name).write_bytes(content)
    changed = []
    try:
        for path, content in migrated.items():
            if content != originals[path]:
                _atomic_write(path, content)
                changed.append(path.name)
    except Exception:
        for path, content in originals.items():
            _atomic_write(path, content)
        raise
    return {"kind": "intent", "schema_version": 1, "changed": changed, "backup_dir": str(backup), "intent_clarity_granted": False, "authorization_granted": False}


def _activation_inputs(input_files: dict[str, str | Path]) -> dict[str, dict]:
    if set(input_files) != set(INTENT_KINDS):
        raise StateError("intent activation requires charter, roadmap, and doctrine JSON")
    documents = {}
    for kind in INTENT_KINDS:
        path = Path(input_files[kind])
        if path.is_symlink() or not path.is_file():
            raise StateError(f"intent activation requires a regular {kind} JSON input")
        documents[kind] = read_json(path)
    return documents


def _restore_intent_files(
    originals: dict[Path, bytes | None], intent_dir_existed: bool
) -> None:
    for path, content in originals.items():
        if content is None:
            if path.exists() and not path.is_symlink():
                path.unlink()
        else:
            _atomic_write(path, content)
    if not intent_dir_existed:
        try:
            next(iter(originals)).parent.rmdir()
        except OSError:
            pass


def activate_intent(
    root: str | Path,
    backup_dir: str | Path,
    input_files: dict[str, str | Path],
    *,
    creator_confirmed: bool,
) -> dict:
    if not creator_confirmed:
        raise StateError("intent activation requires explicit creator confirmation")
    documents = _activation_inputs(input_files)
    repo_root = Path(root).resolve()
    intent_dir = repo_root / ".pathfinder"
    store = IntentStore(repo_root)
    validator = MissionStore(intent_dir)
    for kind in INTENT_KINDS:
        validator.validate(f"intent/{kind}.schema.json", documents[kind])

    if intent_dir.is_symlink() or (intent_dir.exists() and not intent_dir.is_dir()):
        raise StateError("intent activation requires a safe .pathfinder directory")
    paths = [
        intent_dir / f"{kind}.{suffix}"
        for kind in INTENT_KINDS
        for suffix in INTENT_SUFFIXES
    ]
    for path in paths:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise StateError(f"intent activation requires a regular target: {path.name}")

    backup = Path(backup_dir).resolve()
    if backup.exists():
        raise StateError(f"backup destination already exists: {backup}")
    originals = {path: path.read_bytes() if path.exists() else None for path in paths}
    intent_dir_existed = intent_dir.exists()
    backup.mkdir(parents=True)
    for path, content in originals.items():
        if content is not None:
            (backup / path.name).write_bytes(content)

    try:
        store.write_all(documents)
    except Exception:
        _restore_intent_files(originals, intent_dir_existed)
        raise

    changed = [
        path.name
        for path, content in originals.items()
        if content is None or path.read_bytes() != content
    ]
    clarity = (
        "resolved"
        if all(
            document["completion"] == "complete"
            and document["intent_clarity"] == "resolved"
            for document in documents.values()
        )
        else "unresolved"
    )
    return {
        "kind": "intent-activation",
        "schema_version": 1,
        "changed": changed,
        "backup_dir": str(backup),
        "creator_confirmed": True,
        "intent_clarity": clarity,
        "authorization_granted": False,
        "autonomy_authorized": False,
    }


def migrate_mission(state_dir: str | Path, backup_dir: str | Path) -> dict:
    source = Path(state_dir).resolve()
    backup = Path(backup_dir).resolve()
    if backup.exists():
        raise StateError(f"backup destination already exists: {backup}")
    state = MissionStore(source).load()
    if state["schema_version"] != 1:
        raise StateError(f"unsupported mission schema version: {state['schema_version']}")
    shutil.copytree(source, backup, symlinks=True)
    return {"kind": "mission", "schema_version": 1, "changed": [], "backup_dir": str(backup), "authorization_granted": False}
