from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from .errors import StateError
from .storage import MissionStore


INTENT_FILES = {"charter": "charter.md", "roadmap": "roadmap.md", "doctrine": "doctrine.md"}


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
    if re.search(r"^intent_clarity: (resolved|unresolved)$", text, re.MULTILINE):
        return text
    legacy = re.search(r"^clarity: (resolved|unresolved)$", text, re.MULTILINE)
    if legacy:
        return text[: legacy.start()] + "intent_clarity: unresolved" + text[legacy.end() :]
    completion = re.search(r"^completion: (complete|incomplete)$", text, re.MULTILINE)
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
