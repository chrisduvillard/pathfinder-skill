from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath


def object_evidence_records(files) -> list[dict]:
    return [
        {
            "path": item["path"],
            "previous_path": item["previous_path"],
            "object_kind": item["object_kind"],
            "binary": item["binary"],
        }
        for item in files
    ]


def object_evidence_sha256(files) -> str:
    encoded = json.dumps(
        object_evidence_records(files), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def derive_special_files(item) -> tuple[str, ...]:
    special = set()
    if item["object_kind"] in {"symlink", "submodule"}:
        special.add(item["object_kind"])
    if item["binary"]:
        special.add("binary")
    for raw_path in (item["path"], item["previous_path"]):
        if raw_path is None:
            continue
        path = PurePosixPath(raw_path)
        value = path.as_posix()
        if value.startswith(".github/workflows/"):
            special.add("workflow")
        if path.name == "CODEOWNERS":
            special.add("codeowners")
        if (
            value.startswith("policies/")
            or value.startswith("schemas/policy/")
            or value.startswith(".pathfinder/")
        ):
            special.add("policy")
    return tuple(sorted(special))
