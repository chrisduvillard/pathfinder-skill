from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .storage import read_json


class HostAction(str, Enum):
    PREPARE_WORKTREE = "prepare-worktree"
    ACTIVATE_GOAL = "activate-goal"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    COMMIT = "commit"
    COMPLETE_GOAL = "complete-goal"
    PUBLISH = "publish"


class HostOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    MANUAL_HANDOFF = "manual-handoff"
    NOT_OBSERVED = "not-observed"
    RECONCILE_REQUIRED = "reconcile-required"


TRUSTED_FIELDS = (
    "operation_id",
    "mission_id",
    "attempt_id",
    "action_kind",
    "request_sha256",
    "authorization_snapshot_sha256",
    "runtime_boundary_sha256",
)
REQUEST_TRUSTED_FIELDS = (*TRUSTED_FIELDS, "context")
RECEIPT_FIELDS = ("action_id", *TRUSTED_FIELDS)


@dataclass(frozen=True)
class HostActionRequest:
    action_id: str
    operation_id: str
    mission_id: str
    attempt_id: str
    action_kind: HostAction
    request_sha256: str
    authorization_snapshot_sha256: str
    runtime_boundary_sha256: str
    context: Mapping[str, object]
    requested_at: str


@dataclass(frozen=True)
class HostActionReceipt:
    action_id: str
    operation_id: str
    mission_id: str
    attempt_id: str
    action_kind: HostAction
    request_sha256: str
    authorization_snapshot_sha256: str
    runtime_boundary_sha256: str
    outcome: HostOutcome
    evidence: Mapping[str, object]
    completed_at: str


class HostProtocol:
    def __init__(self, schema_root: Path | None = None):
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

    def validate_request(
        self, document: dict, *, trusted_binding: Mapping[str, object]
    ) -> HostActionRequest:
        self._validate("host-action-request", document)
        for field in REQUEST_TRUSTED_FIELDS:
            if trusted_binding.get(field) != document[field]:
                raise StateError(f"host action request has forged trusted field: {field}")
        if (
            document["action_kind"] == HostAction.COMPLETE_GOAL.value
            and not document["context"].get("native_goal_id")
        ):
            raise StateError("Goal completion request requires the activated native Goal identity")
        return HostActionRequest(
            action_id=document["action_id"],
            operation_id=document["operation_id"],
            mission_id=document["mission_id"],
            attempt_id=document["attempt_id"],
            action_kind=HostAction(document["action_kind"]),
            request_sha256=document["request_sha256"],
            authorization_snapshot_sha256=document["authorization_snapshot_sha256"],
            runtime_boundary_sha256=document["runtime_boundary_sha256"],
            context=MappingProxyType(dict(document["context"])),
            requested_at=document["requested_at"],
        )

    def validate_receipt(
        self, document: dict, *, request: HostActionRequest
    ) -> HostActionReceipt:
        self._validate("host-action-receipt", document)
        for field in RECEIPT_FIELDS:
            expected = getattr(request, field)
            if isinstance(expected, Enum):
                expected = expected.value
            if document[field] != expected:
                raise StateError(f"host action receipt does not match request: {field}")
        outcome = HostOutcome(document["outcome"])
        evidence = document["evidence"]
        if outcome is HostOutcome.RECONCILE_REQUIRED and evidence["code"] != "ambiguous":
            raise StateError("reconcile-required receipt must carry ambiguous evidence")
        if outcome is HostOutcome.MANUAL_HANDOFF and evidence["code"] != "manual-handoff":
            raise StateError("manual handoff receipt must carry manual-handoff evidence")
        if (
            request.action_kind in {HostAction.ACTIVATE_GOAL, HostAction.COMPLETE_GOAL}
            and outcome is HostOutcome.SUCCEEDED
            and not evidence["stable_id"]
        ):
            raise StateError("successful Goal lifecycle action requires a stable native Goal identity")
        return HostActionReceipt(
            action_id=document["action_id"],
            operation_id=document["operation_id"],
            mission_id=document["mission_id"],
            attempt_id=document["attempt_id"],
            action_kind=HostAction(document["action_kind"]),
            request_sha256=document["request_sha256"],
            authorization_snapshot_sha256=document["authorization_snapshot_sha256"],
            runtime_boundary_sha256=document["runtime_boundary_sha256"],
            outcome=outcome,
            evidence=MappingProxyType(
                {**evidence, "changed_files": tuple(evidence["changed_files"])}
            ),
            completed_at=document["completed_at"],
        )
