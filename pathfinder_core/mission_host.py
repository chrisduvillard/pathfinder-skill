from __future__ import annotations

import hashlib
import json
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import StateError
from .host_protocol import HostAction, HostActionRequest, HostOutcome, HostProtocol
from .operations import OperationJournal
from .policy import ExecutionPolicy
from .protected_surfaces import BASELINE_PATH, ProtectedSurfaceRegistry
from .state import transition, utc_now
from .storage import MissionLock, MissionStore, read_json, write_atomic


ACTION_BY_STATE = {
    "authorized": ("prepare", "prepare-worktree"),
    "prepared": ("goal-activation", "activate-goal"),
    "running": ("implementation", "implement"),
    "verifying": ("verification", "verify"),
    "verified": ("commit", "commit"),
    "committed": ("goal-completion", "complete-goal"),
}
TERMINAL_STATES = {"awaiting-review", "merged", "blocked", "abandoned"}
SUCCESS_BY_ACTION = {
    "prepare-worktree": ("authorized", "prepared", "worktree-prepared"),
    "activate-goal": ("prepared", "running", "goal-active"),
    "implement": ("running", "verifying", "implementation-complete"),
    "verify": ("verifying", "verified", "verification-passed"),
    "commit": ("verified", "committed", "commit-created"),
    "complete-goal": ("committed", "awaiting-review", "goal-complete"),
}
RESULT_CODES = {
    "succeeded": "completed",
    "failed": "command-failed",
    "manual-handoff": "backend-unavailable",
    "not-observed": "not-found",
    "reconcile-required": "ambiguous",
}


def document_sha256(document: dict) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise StateError("mission time must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class HostMissionController:
    def __init__(self, root: Path, *, clock=utc_now):
        self.root = Path(root)
        self.contracts_path = self.root / "contracts"
        self.start_lock_path = self.root / "mission-start.lock"
        self.receipt_lock_path = self.root / "host-receipts.lock"
        self.store = MissionStore(self.root)
        self.journal = OperationJournal(self.root)
        self.protocol = HostProtocol()
        self.clock = clock

    def _validate_contracts(
        self, binding: dict, authorization: dict, boundary: dict,
        protected_registry: ProtectedSurfaceRegistry,
    ) -> None:
        self.store.validate("artifacts/goal-binding.schema.json", binding)
        if binding["scope"].get("repository_kind", "git") != "git":
            raise StateError("host missions require a Git Goal Binding")
        self.store.validate("mission/authorization-snapshot.schema.json", authorization)
        self.store.validate("artifacts/runtime-boundary.schema.json", boundary)
        expected = (
            ("mission_id", binding["mission_id"]),
            ("binding_id", binding["binding_id"]),
            ("base_commit", binding["scope"]["base_commit"]),
        )
        for field, value in expected:
            if authorization[field] != value:
                raise StateError(f"authorization snapshot drift: {field}")
        for name, expected_hash in authorization["intent_hashes"].items():
            intent = binding["intent_snapshot"][name]
            if intent is None or intent["sha256"] != expected_hash:
                raise StateError(f"authorization intent hash drift: {name}")
        if authorization["publication_target"] not in {"none", "local-branch"}:
            raise StateError("host mission start supports local/no-publication targets only")
        if authorization["limits"]["max_total_prs"] != 0:
            raise StateError("host mission start requires max_total_prs to be zero")
        budgets = binding["budgets"]
        if budgets["max_open_prs"] != 0 or budgets["max_total_prs"] != 0:
            raise StateError("Goal Binding must disable publication for a local mission")
        for authorization_field, binding_field in (
            ("max_goals", "max_goals"),
            ("max_attempts", "max_attempts_per_goal"),
            ("max_wall_seconds", "max_wall_seconds"),
            ("max_total_prs", "max_total_prs"),
        ):
            if authorization["limits"][authorization_field] > budgets[binding_field]:
                raise StateError(
                    f"authorization {authorization_field} exceeds the Goal Binding budget"
                )
        unknown_surfaces = sorted(
            set(binding["protected_surfaces"]) - set(protected_registry.categories)
        )
        if unknown_surfaces:
            raise StateError(
                f"Goal Binding names an unknown protected surface: {unknown_surfaces[0]}"
            )
        ExecutionPolicy(self.root, ()).validate_boundary(boundary)

    def _deadline(self, state: dict, binding: dict, authorization: dict) -> datetime:
        max_seconds = min(
            binding["budgets"]["max_wall_seconds"],
            authorization["limits"]["max_wall_seconds"],
        )
        return _parse_instant(state["created_at"]) + timedelta(seconds=max_seconds)

    def _write_contract(self, name: str, document: dict) -> None:
        path = self.contracts_path / f"{name}.json"
        if path.is_symlink():
            raise StateError(f"mission contract cannot be a symlink: {name}")
        if path.exists():
            if read_json(path) != document:
                raise StateError(f"different persisted mission contract: {name}")
            path.chmod(stat.S_IRUSR)
            return
        write_atomic(path, document)
        path.chmod(stat.S_IRUSR)

    def _attempt_id(self, binding: dict) -> str:
        seed = f"{binding['mission_id']}:{binding['scope']['base_commit']}"
        return f"attempt_{hashlib.sha256(seed.encode()).hexdigest()[:24]}"

    def _initial_state(self, binding: dict, attempt_id: str, at: str) -> dict:
        return {
            "schema_version": 1,
            "mission_id": binding["mission_id"],
            "goal_id": binding["goal_id"],
            "binding_id": binding["binding_id"],
            "authorization_id": None,
            "attempt_id": attempt_id,
            "state": "planned",
            "revision": 0,
            "base_commit": binding["scope"]["base_commit"],
            "dirty_policy": binding["scope"]["dirty_policy"],
            "worktree_id": None,
            "worktree_path": None,
            "branch_id": None,
            "branch_name": None,
            "commit_ids": [],
            "native_goal_id": None,
            "pr_id": None,
            "pr_url": None,
            "created_at": at,
            "updated_at": at,
        }

    def _validate_state_identity(
        self, state: dict, binding: dict, attempt_id: str
    ) -> None:
        expected = {
            "mission_id": binding["mission_id"],
            "goal_id": binding["goal_id"],
            "binding_id": binding["binding_id"],
            "base_commit": binding["scope"]["base_commit"],
            "attempt_id": attempt_id,
        }
        for field, value in expected.items():
            if state[field] != value:
                raise StateError(f"persisted mission identity drift: {field}")

    def start(
        self, *, binding: dict, authorization: dict, runtime_boundary: dict,
        protected_policy: dict | None = None,
    ) -> dict:
        if self.root.is_symlink() or self.contracts_path.is_symlink():
            raise StateError("mission state and contracts directories cannot be symlinks")
        protected_registry = ProtectedSurfaceRegistry(
            read_json(BASELINE_PATH), protected_policy
        )
        self._validate_contracts(
            binding, authorization, runtime_boundary, protected_registry
        )
        attempt_id = self._attempt_id(binding)
        with MissionLock(self.start_lock_path):
            self._write_contract("goal-binding", binding)
            self._write_contract("authorization", authorization)
            self._write_contract("runtime-boundary", runtime_boundary)
            self._write_contract("protected-surfaces", protected_registry.to_document())
            if self.store.state_path.exists():
                state = self.store.repair()
            else:
                state = self._initial_state(binding, attempt_id, self.clock())
                self.store.initialize(state)
            self._validate_state_identity(state, binding, attempt_id)
            if state["state"] == "planned":
                state = self.store.move(
                    "authorized",
                    attempt_id=attempt_id,
                    changes={"authorization_id": authorization["authorization_id"]},
                )
            elif state["authorization_id"] != authorization["authorization_id"]:
                raise StateError("persisted mission authorization identity drift")
            return state

    def _load_contracts(
        self,
    ) -> tuple[dict, dict, dict, ProtectedSurfaceRegistry]:
        binding = read_json(self.contracts_path / "goal-binding.json")
        authorization = read_json(self.contracts_path / "authorization.json")
        boundary = read_json(self.contracts_path / "runtime-boundary.json")
        protected_registry = ProtectedSurfaceRegistry(
            read_json(self.contracts_path / "protected-surfaces.json")
        )
        self._validate_contracts(
            binding, authorization, boundary, protected_registry
        )
        return binding, authorization, boundary, protected_registry

    def _operation_id(self, state: dict, action_kind: str) -> str:
        seed = ":".join(
            (state["mission_id"], state["attempt_id"], str(state["revision"]), action_kind)
        )
        return f"operation_{hashlib.sha256(seed.encode()).hexdigest()[:24]}"

    def _documents_for_action(
        self, state: dict, binding: dict, authorization: dict, boundary: dict,
        protected_registry: ProtectedSurfaceRegistry,
        *, started_at: str,
    ) -> tuple[dict, dict]:
        stage, action_kind = ACTION_BY_STATE[state["state"]]
        operation_id = self._operation_id(state, action_kind)
        action_id = f"action_{hashlib.sha256(operation_id.encode()).hexdigest()[:24]}"
        context = {
            "binding_id": state["binding_id"],
            "goal_id": state["goal_id"],
            "worktree_id": state["worktree_id"],
            "deadline_at": _format_instant(
                self._deadline(state, binding, authorization)
            ),
            "protected_policy_sha256": protected_registry.sha256,
            "input_sha256": document_sha256(
                {"binding": document_sha256(binding), "revision": state["revision"],
                 "action_kind": action_kind}
            ),
        }
        if action_kind == "complete-goal":
            if not state.get("native_goal_id"):
                raise StateError("cannot complete a Goal without its activated native identity")
            context["native_goal_id"] = state["native_goal_id"]
        trusted = {
            "operation_id": operation_id,
            "mission_id": state["mission_id"],
            "attempt_id": state["attempt_id"],
            "action_kind": action_kind,
            "authorization_snapshot_sha256": document_sha256(authorization),
            "runtime_boundary_sha256": document_sha256(boundary),
            "context": context,
        }
        trusted["request_sha256"] = document_sha256(
            {**trusted, "action_id": action_id, "requested_at": started_at}
        )
        request = {
            "schema_version": 1, "action_id": action_id, **trusted,
            "requested_at": started_at,
        }
        intent = {
            "schema_version": 1,
            **{field: trusted[field] for field in (
                "operation_id", "mission_id", "attempt_id", "action_kind",
                "request_sha256", "authorization_snapshot_sha256",
                "runtime_boundary_sha256",
            )},
            "stage": stage,
            "protected_policy_sha256": protected_registry.sha256,
            "started_at": started_at,
        }
        self.protocol.validate_request(request, trusted_binding=trusted)
        return request, intent

    def next(self) -> dict:
        state = self.store.repair()
        if state["state"] in TERMINAL_STATES:
            return {"status": "terminal", "state": state}
        if state["state"] not in ACTION_BY_STATE:
            raise StateError(f"mission state has no host action: {state['state']}")
        binding, authorization, boundary, protected_registry = self._load_contracts()
        self._validate_state_identity(state, binding, self._attempt_id(binding))
        operation_id = self._operation_id(
            state, ACTION_BY_STATE[state["state"]][1]
        )
        intent_path = self.journal.operations_path / f"{operation_id}.intent.json"
        if intent_path.exists():
            loaded = self.journal.load(operation_id)
            receipt_path = self._receipt_path(operation_id)
            if receipt_path.exists():
                return self._finish_receipt(
                    state, loaded["intent"], read_json(receipt_path)
                )
            if loaded["state"] == "pending":
                return {
                    "status": "reconcile-required",
                    "mission_id": state["mission_id"],
                    "attempt_id": state["attempt_id"],
                    "operation_id": operation_id,
                    "action_kind": ACTION_BY_STATE[state["state"]][1],
                }
            raise StateError("operation result exists without its typed host receipt")
        requested_at = self.clock()
        if _parse_instant(requested_at) >= self._deadline(
            state, binding, authorization
        ):
            state = self.store.move(
                "blocked", attempt_id=state["attempt_id"],
                changes={"terminal_reason": "budget-limited"},
            )
            return {"status": "terminal", "state": state}
        request, intent = self._documents_for_action(
            state, binding, authorization, boundary, protected_registry,
            started_at=requested_at,
        )
        self.journal.record_intent(intent)
        return {"status": "action-required", "action": request}

    def _receipt_path(self, operation_id: str) -> Path:
        return self.journal.operations_path / f"{operation_id}.receipt.json"

    def _request_from_intent(self, intent: dict) -> HostActionRequest:
        action_id = f"action_{hashlib.sha256(intent['operation_id'].encode()).hexdigest()[:24]}"
        return HostActionRequest(
            action_id=action_id, operation_id=intent["operation_id"],
            mission_id=intent["mission_id"], attempt_id=intent["attempt_id"],
            action_kind=HostAction(intent["action_kind"]),
            request_sha256=intent["request_sha256"],
            authorization_snapshot_sha256=intent["authorization_snapshot_sha256"],
            runtime_boundary_sha256=intent["runtime_boundary_sha256"],
            context={}, requested_at=intent["started_at"],
        )

    def _persist_receipt(self, receipt: dict) -> None:
        path = self._receipt_path(receipt["operation_id"])
        with MissionLock(self.receipt_lock_path):
            if path.is_symlink():
                raise StateError("host receipt cannot be a symlink")
            if path.exists():
                if read_json(path) != receipt:
                    raise StateError("different host receipt already exists")
                path.chmod(stat.S_IRUSR)
                return
            write_atomic(path, receipt)
            path.chmod(stat.S_IRUSR)

    def _operation_result(self, intent: dict, receipt: dict) -> dict:
        outcome = receipt["outcome"]
        operation_outcome = "failed" if outcome == "manual-handoff" else outcome
        return {
            "schema_version": 1,
            **{field: intent[field] for field in (
                "operation_id", "mission_id", "attempt_id", "stage", "action_kind",
                "request_sha256", "authorization_snapshot_sha256",
                "runtime_boundary_sha256", "protected_policy_sha256", "started_at",
            )},
            "outcome": operation_outcome,
            "evidence": {
                "summary_code": RESULT_CODES[outcome],
                "external_id": receipt["evidence"]["stable_id"],
                "exit_status": receipt["evidence"]["exit_status"],
                "output_sha256": document_sha256(receipt),
            },
            "completed_at": receipt["completed_at"],
        }

    def _success_changes(self, action_kind: str, evidence: dict) -> dict:
        if action_kind == "prepare-worktree":
            return {
                "worktree_id": evidence["stable_id"],
                "worktree_path": evidence["worktree_path"],
                "branch_id": evidence["branch_id"],
                "branch_name": evidence["branch_name"],
            }
        if action_kind == "commit":
            return {"commit_ids": [evidence["stable_id"]]}
        if action_kind == "activate-goal":
            return {"native_goal_id": evidence["stable_id"]}
        return {}

    def _advance(self, state: dict, receipt: dict, *, apply: bool) -> dict:
        action_kind = receipt["action_kind"]
        outcome = receipt["outcome"]
        source, target, success_code = SUCCESS_BY_ACTION[action_kind]
        if state["state"] == "abandoned":
            return state
        if outcome != HostOutcome.SUCCEEDED.value:
            if state["state"] == "blocked":
                return state
            if state["state"] != source:
                raise StateError("failed host receipt does not match current mission state")
            if not apply:
                return transition(state, "blocked")
            return self.store.move("blocked", attempt_id=state["attempt_id"])
        if receipt["evidence"]["code"] != success_code:
            raise StateError(f"successful {action_kind} receipt has the wrong evidence code")
        changes = self._success_changes(action_kind, receipt["evidence"])
        if state["state"] == source:
            candidate = transition(state, target)
            candidate.update(changes)
            self.store.validate("mission/mission-state.schema.json", candidate)
            if not apply:
                return candidate
            return self.store.move(
                target, attempt_id=state["attempt_id"], changes=changes
            )
        if state["state"] == target or state["state"] in TERMINAL_STATES | {"published", "committed"}:
            for field, value in changes.items():
                if state[field] != value:
                    raise StateError(f"applied host receipt state drift: {field}")
            return state
        raise StateError("successful host receipt does not match current mission state")

    def _validate_receipt_for_state(self, state: dict, intent: dict, receipt: dict) -> None:
        binding, authorization, boundary, protected_registry = self._load_contracts()
        self._validate_state_identity(state, binding, self._attempt_id(binding))
        if intent["authorization_snapshot_sha256"] != document_sha256(authorization):
            raise StateError("operation authorization hash no longer matches mission contract")
        if intent["runtime_boundary_sha256"] != document_sha256(boundary):
            raise StateError("operation runtime hash no longer matches mission contract")
        if intent["protected_policy_sha256"] != protected_registry.sha256:
            raise StateError("operation protected policy hash no longer matches mission contract")
        self.protocol.validate_receipt(receipt, request=self._request_from_intent(intent))
        if (
            receipt["action_kind"] == "complete-goal"
            and receipt["outcome"] == HostOutcome.SUCCEEDED.value
            and receipt["evidence"]["stable_id"] != state.get("native_goal_id")
        ):
            raise StateError("Goal completion receipt does not match the activated native Goal")
        if receipt["outcome"] == HostOutcome.SUCCEEDED.value:
            required = set(
                protected_registry.required_categories(
                    tuple(receipt["evidence"]["changed_files"])
                )
            )
            undeclared = sorted(required - set(binding["protected_surfaces"]))
            if undeclared:
                raise StateError(
                    f"host action touched undeclared protected surface: {undeclared[0]}"
                )
        if (
            receipt["outcome"] == HostOutcome.SUCCEEDED.value
            and _parse_instant(receipt["completed_at"])
            > self._deadline(state, binding, authorization)
        ):
            raise StateError("successful host action completed after the mission deadline")
        self._advance(state, receipt, apply=False)

    def _finish_receipt(self, state: dict, intent: dict, receipt: dict) -> dict:
        self._validate_receipt_for_state(state, intent, receipt)
        self.journal.record_result(self._operation_result(intent, receipt))
        updated = self._advance(state, receipt, apply=True)
        status = receipt["outcome"] if receipt["outcome"] != "succeeded" else "advanced"
        return {"status": status, "operation_id": intent["operation_id"], "state": updated}

    def record(self, receipt: dict) -> dict:
        operation_id = receipt.get("operation_id")
        if not isinstance(operation_id, str):
            raise StateError("host receipt requires an operation_id")
        loaded = self.journal.load(operation_id)
        state = self.store.repair()
        self._validate_receipt_for_state(state, loaded["intent"], receipt)
        self._persist_receipt(receipt)
        return self._finish_receipt(state, loaded["intent"], receipt)
