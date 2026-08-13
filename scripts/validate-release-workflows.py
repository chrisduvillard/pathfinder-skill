#!/usr/bin/env python3
"""Semantically enforce Pathfinder's manual-only release authority boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class UniqueBaseLoader(yaml.BaseLoader):
    """BaseLoader variant that rejects duplicate YAML mapping keys."""


def construct_unique_mapping(
    loader: UniqueBaseLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ConstructorError("while constructing a mapping", node.start_mark, "unhashable key", key_node.start_mark) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueBaseLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
)


def fail(path: Path, message: str) -> None:
    print(f"::error file={path}::{message}")
    raise SystemExit(1)


def mapping(value: Any, path: Path, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        fail(path, f"{label} must be a YAML mapping with string keys")
    return value


def permissions_allow_release(value: Any) -> bool:
    if value == "write-all":
        return True
    return isinstance(value, dict) and value.get("contents") == "write"


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueBaseLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        fail(path, f"invalid workflow YAML: {exc}")
    return mapping(loaded, path, "workflow")


def validate_canonical(path: Path, workflow: dict[str, Any]) -> None:
    events = mapping(workflow.get("on"), path, "release trigger")
    if set(events) != {"workflow_dispatch"}:
        fail(path, "release trigger must be exactly one workflow_dispatch event")
    dispatch = mapping(events["workflow_dispatch"], path, "workflow_dispatch")
    inputs = mapping(dispatch.get("inputs"), path, "workflow_dispatch inputs")
    if set(inputs) != {"version"}:
        fail(path, "release dispatch must require one typed version confirmation")
    version_input = mapping(inputs["version"], path, "version input")
    if (
        version_input.get("required") != "true"
        or version_input.get("type") != "string"
        or "default" in version_input
    ):
        fail(path, "release dispatch must require one typed version confirmation")

    if workflow.get("permissions") != {"contents": "read"}:
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")

    jobs = mapping(workflow.get("jobs"), path, "release jobs")
    if set(jobs) != {"validate", "release"}:
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")
    validate = mapping(jobs["validate"], path, "validate job")
    release = mapping(jobs["release"], path, "release job")

    if validate.get("if") != "github.ref == 'refs/heads/main'" or "permissions" in validate:
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")
    expected_gate = "github.ref == 'refs/heads/main' && needs.validate.outputs.version == inputs.version"
    if (
        release.get("if") != expected_gate
        or release.get("needs") != "validate"
        or release.get("permissions") != {"contents": "write"}
    ):
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")

    steps = release.get("steps")
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")
    step = steps[0]
    if set(step) != {"name", "env", "run"} or step.get("name") != "Create release if VERSION.md declares a new version":
        fail(path, "release workflow must have exactly two gated jobs and one isolated write permission")
    env = mapping(step["env"], path, "release step environment")
    expected_env = {
        "GH_TOKEN": "${{ github.token }}",
        "COMMIT_SHA": "${{ github.sha }}",
        "DECLARED_VERSION": "${{ needs.validate.outputs.version }}",
        "REQUESTED_VERSION": "${{ inputs.version }}",
        "REPO": "${{ github.repository }}",
    }
    if env != expected_env or not isinstance(step["run"], str):
        fail(path, "release workflow must bind requested and validated versions and expose one executable release program")


def validate_other(path: Path, workflow: dict[str, Any]) -> None:
    permissions = workflow.get("permissions")
    if permissions is None or permissions_allow_release(permissions):
        fail(path, "release/tag authority is permitted only in .github/workflows/release.yml")
    jobs = mapping(workflow.get("jobs"), path, "workflow jobs")
    for job_name, raw_job in jobs.items():
        job = mapping(raw_job, path, f"job {job_name}")
        if permissions_allow_release(job.get("permissions")):
            fail(path, "release/tag authority is permitted only in .github/workflows/release.yml")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate-release-workflows.py ROOT", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    workflow_dir = root / ".github" / "workflows"
    paths = sorted({*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")})
    canonical = workflow_dir / "release.yml"
    if canonical not in paths:
        fail(canonical, "manual release workflow is missing")
    for path in paths:
        workflow = load_workflow(path)
        if path == canonical:
            validate_canonical(path, workflow)
        else:
            validate_other(path, workflow)
    print("ok: workflow YAML semantically limits release authority to the manual release job")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
