from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"error": "usage", "message": "validate-artifact.py SCHEMA INSTANCE"}))
        return 2
    try:
        schema = json.loads(Path(sys.argv[1]).read_text(), object_pairs_hook=unique_pairs)
        instance = json.loads(Path(sys.argv[2]).read_text(), object_pairs_hook=unique_pairs)
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance),
            key=lambda error: list(error.path),
        )
        if errors:
            first = errors[0]
            location = "/".join(str(part) for part in first.path) or "<root>"
            print(json.dumps({"error": "schema_validation", "location": location, "message": first.message}))
            return 1
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"error": "invalid_json", "message": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
