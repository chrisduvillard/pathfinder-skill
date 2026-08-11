from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .errors import StateError
from .operations import OperationJournal
from .protected_surfaces import ProtectedSurfaceRegistry
from .storage import MissionStore, read_json


TERMINAL_STATES = {"awaiting-review", "merged", "blocked", "abandoned"}
VERIFIED_STATES = {"verified", "committed", "published", "awaiting-review", "merged"}
STAGE_ORDER = {
    "prepare": 0,
    "goal-activation": 1,
    "implementation": 2,
    "verification": 3,
    "commit": 4,
    "publication": 5,
    "cleanup": 6,
}
OPERATION_FILE = re.compile(
    r"^(operation_[a-z0-9][a-z0-9_-]{7,63})\.(intent|result|receipt)\.json$"
)


def _sha256(document: dict) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_contract(store: MissionStore, name: str, schema: str) -> dict:
    path = store.root / "contracts" / f"{name}.json"
    if path.is_symlink() or not path.is_file():
        raise StateError(f"mission contract must be a regular file: {name}")
    document = read_json(path)
    store.validate(schema, document)
    return document


def _validate_identity(state: dict, binding: dict, authorization: dict) -> None:
    expected = {
        "mission_id": binding["mission_id"],
        "goal_id": binding["goal_id"],
        "binding_id": binding["binding_id"],
        "base_commit": binding["scope"]["base_commit"],
    }
    for field, value in expected.items():
        if state[field] != value:
            raise StateError(f"mission state does not match Goal Binding: {field}")
    for field in ("mission_id", "binding_id", "base_commit"):
        if authorization[field] != expected[field]:
            raise StateError(f"authorization does not match mission identity: {field}")
    if (
        state["authorization_id"] is not None
        and state["authorization_id"] != authorization["authorization_id"]
    ):
        raise StateError("authorization does not match mission state: authorization_id")


def _operation_files(root: Path) -> dict[str, set[str]]:
    operations_path = root / "operations"
    if not operations_path.exists():
        return {}
    if operations_path.is_symlink() or not operations_path.is_dir():
        raise StateError("mission operations path must be a regular directory")
    grouped: dict[str, set[str]] = {}
    for path in operations_path.iterdir():
        if path.is_symlink() or not path.is_file():
            raise StateError(f"mission operation artifact must be a regular file: {path.name}")
        if not path.name.endswith(".json"):
            continue
        match = OPERATION_FILE.fullmatch(path.name)
        if not match:
            raise StateError(f"invalid mission operation artifact: {path.name}")
        grouped.setdefault(match.group(1), set()).add(match.group(2))
    return grouped


def _validate_receipt(
    store: MissionStore,
    intent: dict,
    receipt: dict,
    result: dict | None,
) -> None:
    store.validate("mission/host-action-receipt.schema.json", receipt)
    action_id = f"action_{hashlib.sha256(intent['operation_id'].encode()).hexdigest()[:24]}"
    expected = {
        "action_id": action_id,
        "operation_id": intent["operation_id"],
        "mission_id": intent["mission_id"],
        "attempt_id": intent["attempt_id"],
        "action_kind": intent["action_kind"],
        "request_sha256": intent["request_sha256"],
        "authorization_snapshot_sha256": intent["authorization_snapshot_sha256"],
        "runtime_boundary_sha256": intent["runtime_boundary_sha256"],
    }
    for field, value in expected.items():
        if receipt[field] != value:
            raise StateError(f"operation receipt does not match intent: {field}")
    if result is None:
        return
    expected_outcome = "failed" if receipt["outcome"] == "manual-handoff" else receipt["outcome"]
    if result["outcome"] != expected_outcome:
        raise StateError("operation result does not match receipt outcome")
    if result["completed_at"] != receipt["completed_at"]:
        raise StateError("operation result does not match receipt completion time")
    evidence = result["evidence"]
    receipt_evidence = receipt["evidence"]
    if evidence["external_id"] != receipt_evidence["stable_id"]:
        raise StateError("operation result does not match receipt stable identity")
    if evidence["exit_status"] != receipt_evidence["exit_status"]:
        raise StateError("operation result does not match receipt exit status")
    if evidence["output_sha256"] != _sha256(receipt):
        raise StateError("operation result does not match the persisted receipt")


def _load_operations(
    store: MissionStore,
    state: dict,
    authorization: dict,
    boundary: dict,
    protected: dict,
) -> list[dict]:
    grouped = _operation_files(store.root)
    journal = OperationJournal(store.root, schema_root=store.schema_root)
    operations = []
    for operation_id, suffixes in grouped.items():
        if "intent" not in suffixes:
            raise StateError(f"operation artifact exists without intent: {operation_id}")
        loaded = journal.load(operation_id)
        intent, result = loaded["intent"], loaded["result"]
        for field in ("mission_id", "attempt_id"):
            if intent[field] != state[field]:
                raise StateError(f"operation {field} does not match mission state")
        expected_hashes = {
            "authorization_snapshot_sha256": _sha256(authorization),
            "runtime_boundary_sha256": _sha256(boundary),
            "protected_policy_sha256": ProtectedSurfaceRegistry(protected).sha256,
        }
        for field, value in expected_hashes.items():
            if intent[field] != value:
                raise StateError(f"operation contract hash drift: {field}")
        receipt_path = store.root / "operations" / f"{operation_id}.receipt.json"
        receipt = None
        if "receipt" in suffixes:
            receipt = read_json(receipt_path)
            _validate_receipt(store, intent, receipt, result)
        elif result is not None:
            raise StateError("operation result exists without its typed host receipt")
        if result is not None:
            status = receipt["outcome"]
        elif receipt is not None:
            status = "recovery-pending"
        else:
            status = "reconcile-required"
        operations.append({
            "operation_id": operation_id,
            "stage": intent["stage"],
            "action_kind": intent["action_kind"],
            "status": status,
            "started_at": intent["started_at"],
            "completed_at": receipt["completed_at"] if receipt is not None else None,
            "summary_code": result["evidence"]["summary_code"] if result is not None else None,
            "redacted_summary": receipt["evidence"]["redacted_summary"] if receipt is not None else None,
            "exit_status": receipt["evidence"]["exit_status"] if receipt is not None else None,
            "changed_files": list(receipt["evidence"]["changed_files"]) if receipt is not None else [],
            "artifact_sha256": receipt["evidence"]["artifact_sha256"] if receipt is not None else None,
        })
    return sorted(
        operations,
        key=lambda item: (STAGE_ORDER[item["stage"]], item["started_at"], item["operation_id"]),
    )


def _verification(state: dict, operations: list[dict], reconcile: bool) -> str:
    verify = [item for item in operations if item["action_kind"] == "verify"]
    if verify and verify[-1]["status"] == "succeeded":
        return "passed"
    if verify and verify[-1]["status"] == "failed":
        return "failed"
    if reconcile or state["state"] == "blocked":
        return "blocked"
    return "not-run"


def _binding_status(operations: list[dict], verification: str) -> str:
    if verification == "passed":
        return "matched"
    if any(item["action_kind"] == "implement" for item in operations):
        return "missing"
    return "not-run"


def _publication(state: dict, authorization: dict) -> str:
    if state["state"] in {"published", "awaiting-review", "merged"}:
        return "awaiting-review"
    if authorization["publication_target"] == "local-branch":
        return "local-only"
    return "not-requested"


def _residual_risks(
    state: dict,
    operations: list[dict],
    binding_status: str,
    reconcile: bool,
) -> list[str]:
    risks = ["host action receipts do not contain command-level argv/environment evidence"]
    if binding_status != "matched":
        risks.append("required Goal Binding proof is incomplete")
    if reconcile:
        risks.append("a persisted host action requires reconciliation")
    if state.get("terminal_reason") == "budget-limited":
        risks.append("mission wall-clock budget expired")
    risks.extend(
        item["redacted_summary"]
        for item in operations
        if item["status"] not in {"succeeded", "recovery-pending"}
        and item["redacted_summary"]
    )
    return list(dict.fromkeys(risks))


def _next_input(state: dict) -> str | None:
    if state["state"] == "awaiting-review":
        return "human review of the local branch and commit"
    if state["state"] == "blocked":
        return "resolve the recorded blocker and explicitly authorize a new mission"
    if state["state"] == "abandoned":
        return "explicitly authorize a new mission to continue"
    return None


def build_mission_projection(state_dir: str | Path) -> dict:
    root = Path(state_dir)
    if root.is_symlink() or not root.is_dir():
        raise StateError("mission state path must be a regular directory")
    store = MissionStore(root)
    state = store.load()
    binding = _load_contract(store, "goal-binding", "artifacts/goal-binding.schema.json")
    authorization = _load_contract(
        store, "authorization", "mission/authorization-snapshot.schema.json"
    )
    boundary = _load_contract(
        store, "runtime-boundary", "artifacts/runtime-boundary.schema.json"
    )
    protected = _load_contract(
        store, "protected-surfaces", "policy/protected-surfaces.schema.json"
    )
    _validate_identity(state, binding, authorization)
    operations = _load_operations(store, state, authorization, boundary, protected)
    reconcile = any(item["status"] == "reconcile-required" for item in operations)
    verification = _verification(state, operations, reconcile)
    if state["state"] in VERIFIED_STATES and verification != "passed":
        raise StateError("verified mission state lacks a successful verification receipt")
    binding_status = _binding_status(operations, verification)
    run_log = {
        "schema_version": 1,
        "mission_id": state["mission_id"],
        "attempt_id": state["attempt_id"],
        "binding_id": state["binding_id"],
        "runtime_boundary_id": boundary["boundary_id"],
        "commands": [],
        "binding_status": binding_status,
        "verification": verification,
        "publication": _publication(state, authorization),
        "updated_at": state["updated_at"],
    }
    store.validate("artifacts/run-log.schema.json", run_log)
    final_summary = None
    if state["state"] in TERMINAL_STATES:
        final_summary = {
            "schema_version": 1,
            "mission_id": state["mission_id"],
            "final_state": state["state"],
            "goals": [{
                "goal_id": state["goal_id"],
                "attempt_id": state["attempt_id"],
                "disposition": state["state"],
                "binding_status": binding_status,
                "verification": verification,
                "commit_ids": state["commit_ids"],
                "pr_url": state["pr_url"],
            }],
            "residual_risks": _residual_risks(
                state, operations, binding_status, reconcile
            ),
            "next_input_needed": _next_input(state),
            "replay_artifacts": [
                "07-run-log.json",
                "mission-state/state.json",
                "mission-state/contracts/goal-binding.json",
                "mission-state/contracts/runtime-boundary.json",
                "mission-state/operations/",
            ],
            "completed_at": state["updated_at"],
        }
        store.validate("artifacts/final-summary.schema.json", final_summary)
    return {
        "state": state,
        "binding": binding,
        "runtime_boundary": boundary,
        "operations": operations,
        "run_log": run_log,
        "final_summary": final_summary,
        "requires_reconciliation": reconcile,
    }
