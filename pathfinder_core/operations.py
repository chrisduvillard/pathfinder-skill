from __future__ import annotations

import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .storage import MissionLock, read_json, write_atomic


OPERATION_ID = re.compile(r"^operation_[a-z0-9][a-z0-9_-]{7,63}$")
BOUND_FIELDS = (
    "operation_id",
    "mission_id",
    "attempt_id",
    "stage",
    "action_kind",
    "request_sha256",
    "authorization_snapshot_sha256",
    "runtime_boundary_sha256",
    "started_at",
)


class OperationJournal:
    def __init__(self, root: Path, schema_root: Path | None = None):
        self.root = Path(root)
        self.operations_path = self.root / "operations"
        self.lock_path = self.root / "operations.lock"
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"

    def _validate(self, schema_name: str, document: dict) -> None:
        relative = f"mission/{schema_name}.schema.json"
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

    def _path(self, operation_id: str, suffix: str) -> Path:
        if not OPERATION_ID.fullmatch(operation_id):
            raise StateError(f"invalid operation id: {operation_id}")
        return self.operations_path / f"{operation_id}.{suffix}.json"

    def _write_once(self, path: Path, document: dict, label: str) -> dict:
        if path.exists():
            existing = read_json(path)
            if existing == document:
                return existing
            raise StateError(f"different {label} already exists: {path.name}")
        write_atomic(path, document)
        return document

    def record_intent(self, document: dict) -> dict:
        self._validate("operation-intent", document)
        path = self._path(document["operation_id"], "intent")
        with MissionLock(self.lock_path):
            return self._write_once(path, document, "operation intent")

    def record_result(self, document: dict) -> dict:
        self._validate("operation-result", document)
        intent_path = self._path(document["operation_id"], "intent")
        result_path = self._path(document["operation_id"], "result")
        with MissionLock(self.lock_path):
            if not intent_path.exists():
                raise StateError("operation result cannot be recorded before its intent")
            intent = read_json(intent_path)
            self._validate("operation-intent", intent)
            self._validate_binding(intent, document)
            return self._write_once(result_path, document, "operation result")

    def _validate_binding(self, intent: dict, result: dict) -> None:
        for field in BOUND_FIELDS:
            if result[field] != intent[field]:
                raise StateError(f"operation result does not match intent field: {field}")

    def load(self, operation_id: str) -> dict:
        intent_path = self._path(operation_id, "intent")
        result_path = self._path(operation_id, "result")
        if result_path.exists() and not intent_path.exists():
            raise StateError("operation journal contains a result without an intent")
        if not intent_path.exists():
            raise StateError(f"operation not found: {operation_id}")
        intent = read_json(intent_path)
        self._validate("operation-intent", intent)
        if not result_path.exists():
            return {
                "state": "pending",
                "disposition": "reconcile-required",
                "intent": intent,
                "result": None,
            }
        result = read_json(result_path)
        self._validate("operation-result", result)
        self._validate_binding(intent, result)
        return {
            "state": "terminal",
            "disposition": result["outcome"],
            "intent": intent,
            "result": result,
        }
