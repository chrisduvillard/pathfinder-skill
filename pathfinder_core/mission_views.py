from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from .artifacts import validated_output_dir
from .errors import PolicyError, StateError
from .projections import build_mission_projection
from .rendering import render_mission_final_summary, render_run_log


def _validate_target(path: Path) -> None:
    if path.is_symlink():
        raise PolicyError(f"mission view must not be a symlink: {path}")
    if path.exists() and not path.is_file():
        raise PolicyError(f"mission view must be a regular file: {path}")


def _write_view(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(stat.S_IRUSR | stat.S_IWUSR)
        if path.exists():
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, path)
    except OSError as error:
        if previous_mode is not None and path.exists():
            path.chmod(previous_mode)
        raise StateError(f"cannot write mission view {path}: {error}") from error
    finally:
        if temporary.exists():
            temporary.unlink()


def _json_bytes(document: dict) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def _seal(path: Path) -> None:
    path.chmod(stat.S_IRUSR)


def write_mission_views(repo_root: str | Path, state_dir: str | Path, output_dir: str | Path) -> dict:
    output = validated_output_dir(Path(repo_root), Path(output_dir))
    projection = build_mission_projection(state_dir)
    run_log_markdown = render_run_log(projection).encode()
    summary = projection["final_summary"]
    summary_markdown = (
        render_mission_final_summary(projection).encode() if summary is not None else None
    )
    paths = {
        "run_json": output / "07-run-log.json",
        "run_markdown": output / "07-run-log.md",
        "summary_json": output / "08-final-summary.json",
        "summary_markdown": output / "08-final-summary.md",
    }
    targets = [paths["run_json"], paths["run_markdown"]]
    if summary is None:
        if paths["summary_json"].exists() or paths["summary_markdown"].exists():
            raise StateError("active mission cannot coexist with terminal summary views")
    else:
        targets.extend([paths["summary_json"], paths["summary_markdown"]])
    for path in targets:
        _validate_target(path)
    _write_view(paths["run_json"], _json_bytes(projection["run_log"]))
    if summary is not None:
        _write_view(paths["summary_json"], _json_bytes(summary))
    _write_view(paths["run_markdown"], run_log_markdown)
    if summary_markdown is not None:
        _write_view(paths["summary_markdown"], summary_markdown)
        for path in targets:
            _seal(path)
    return {
        "mission_id": projection["state"]["mission_id"],
        "state": projection["state"]["state"],
        "requires_reconciliation": projection["requires_reconciliation"],
        "artifacts": [str(path) for path in targets],
    }
