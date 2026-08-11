#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


BEGIN = "<!-- pathfinder:generated:protected-surfaces:v1:begin -->"
END = "<!-- pathfinder:generated:protected-surfaces:v1:end -->"
SOURCE = "policies/protected-surfaces.v1.json"
DOCUMENT = "docs/protected-surfaces.md"


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_policy(path: Path) -> dict:
    try:
        policy = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error
    if not isinstance(policy, dict) or policy.get("mode") != "baseline":
        raise ValueError("generated documentation requires a baseline policy object")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("generated documentation requires at least one policy rule")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"policy rule {index} must be an object")
        for field in ("category", "description", "patterns"):
            if field not in rule:
                raise ValueError(f"policy rule {index} is missing {field}")
        if not isinstance(rule["patterns"], list) or not rule["patterns"]:
            raise ValueError(f"policy rule {index} requires patterns")
    return policy


def _cell(value: object) -> str:
    return html.escape(str(value), quote=False).replace("|", "&#124;")


def render_policy_table(policy: dict) -> str:
    lines = [
        BEGIN,
        f"<!-- Generated from {SOURCE}; run `python3 scripts/render_protected_surfaces.py .` to refresh. -->",
        "",
        "| Category | Description | Canonical path patterns |",
        "|---|---|---|",
    ]
    for rule in policy["rules"]:
        patterns = "<br>".join(
            f"<code>{_cell(pattern)}</code>" for pattern in rule["patterns"]
        )
        lines.append(
            f"| <code>{_cell(rule['category'])}</code> | "
            f"{_cell(rule['description'])} | {patterns} |"
        )
    lines.append(END)
    return "\n".join(lines)


def replace_generated_region(document: str, generated: str) -> str:
    if document.count(BEGIN) != 1 or document.count(END) != 1:
        raise ValueError("expected exactly one generated protected-surface region")
    before, remainder = document.split(BEGIN, 1)
    _current, after = remainder.split(END, 1)
    return before + generated + after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="render protected-surface policy documentation from canonical JSON"
    )
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    policy_path = root / SOURCE
    document_path = root / DOCUMENT
    try:
        policy = load_policy(policy_path)
        document = document_path.read_text(encoding="utf-8")
        expected = replace_generated_region(document, render_policy_table(policy))
    except (OSError, TypeError, ValueError) as error:
        print(f"::error file={DOCUMENT}::{error}", file=sys.stderr)
        return 1
    if args.check:
        if document != expected:
            print(
                f"::error file={DOCUMENT}::generated protected-surface table is stale; "
                "run the renderer",
                file=sys.stderr,
            )
            return 1
        print("generated docs: protected-surface policy table is current")
        return 0
    document_path.write_text(expected, encoding="utf-8")
    print(f"updated {DOCUMENT} from {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
