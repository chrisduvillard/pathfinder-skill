from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import PolicyError, StateError
from .storage import read_json


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "policy" / "protected-surfaces.schema.json"
BASELINE_PATH = ROOT / "policies" / "protected-surfaces.v1.json"


@dataclass(frozen=True)
class ProtectedRule:
    rule_id: str
    category: str
    patterns: tuple[str, ...]


def _validate(document: dict) -> None:
    schema = read_json(SCHEMA_PATH)
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    except (SchemaError, ValidationError) as error:
        location = ".".join(str(part) for part in getattr(error, "path", ()))
        suffix = f" at {location}" if location else ""
        raise StateError(
            f"schema validation failed for protected surface policy{suffix}: {error.message}"
        ) from error


class ProtectedSurfaceRegistry:
    def __init__(self, baseline: dict, additive: dict | None = None):
        _validate(baseline)
        if baseline["mode"] != "baseline":
            raise StateError("protected surface baseline policy must use baseline mode")
        documents = [baseline]
        if additive is not None:
            _validate(additive)
            if additive["mode"] != "additive":
                raise StateError("protected surface override must use additive mode")
            if additive["base_policy_id"] != baseline["policy_id"]:
                raise StateError("protected surface override names a different baseline")
            documents.append(additive)
        combined_rules = [dict(rule) for document in documents for rule in document["rules"]]
        seed = json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
        effective_id = baseline["policy_id"]
        if additive is not None:
            effective_id = f"protected-policy-effective-{hashlib.sha256(seed).hexdigest()[:16]}"
        self._document = {
            "schema_version": 1,
            "policy_id": effective_id,
            "mode": "baseline",
            "base_policy_id": None,
            "rules": combined_rules,
        }
        rules: list[ProtectedRule] = []
        seen: set[str] = set()
        for raw in combined_rules:
            if raw["rule_id"] in seen:
                raise StateError(f"duplicate protected surface rule: {raw['rule_id']}")
            seen.add(raw["rule_id"])
            rules.append(
                ProtectedRule(
                    rule_id=raw["rule_id"], category=raw["category"],
                    patterns=tuple(raw["patterns"]),
                )
            )
        _validate(self._document)
        self.policy_id = effective_id
        self.rules = tuple(rules)
        encoded = json.dumps(
            self._document, sort_keys=True, separators=(",", ":")
        ).encode()
        self.sha256 = hashlib.sha256(encoded).hexdigest()

    @classmethod
    def load(cls, additive_path: Path | None = None) -> "ProtectedSurfaceRegistry":
        additive = None
        if additive_path is not None:
            path = Path(additive_path)
            if path.is_symlink():
                raise PolicyError("protected surface override cannot be a symlink")
            additive = read_json(path)
        return cls(read_json(BASELINE_PATH), additive)

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(sorted({rule.category for rule in self.rules}))

    def to_document(self) -> dict:
        return json.loads(json.dumps(self._document))

    def classify(self, paths: list[str] | tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        result: dict[str, tuple[str, ...]] = {}
        for raw_path in paths:
            if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
                raise PolicyError("protected surface paths must use repository-relative POSIX form")
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
                raise PolicyError("protected surface path escapes the repository")
            categories = {
                rule.category
                for rule in self.rules
                if any(path.match(pattern) for pattern in rule.patterns)
            }
            if categories:
                result[str(path)] = tuple(sorted(categories))
        return result

    def required_categories(self, paths: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        classified = self.classify(paths)
        return tuple(sorted({item for values in classified.values() for item in values}))
