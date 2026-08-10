from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .errors import StateError
from .policy import ExecutionPolicy
from .state import utc_now
from .storage import MissionLock, MissionStore, read_json, write_atomic


def document_sha256(document: dict) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class HostMissionController:
    def __init__(self, root: Path, *, clock=utc_now):
        self.root = Path(root)
        self.contracts_path = self.root / "contracts"
        self.start_lock_path = self.root / "mission-start.lock"
        self.store = MissionStore(self.root)
        self.clock = clock

    def _validate_contracts(
        self, binding: dict, authorization: dict, boundary: dict
    ) -> None:
        self.store.validate("artifacts/goal-binding.schema.json", binding)
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
        if authorization["publication_target"] not in {"none", "local-branch"}:
            raise StateError("host mission start supports local/no-publication targets only")
        if authorization["limits"]["max_total_prs"] != 0:
            raise StateError("host mission start requires max_total_prs to be zero")
        budgets = binding["budgets"]
        if budgets["max_open_prs"] != 0 or budgets["max_total_prs"] != 0:
            raise StateError("Goal Binding must disable publication for a local mission")
        ExecutionPolicy(self.root, ()).validate_boundary(boundary)

    def _write_contract(self, name: str, document: dict) -> None:
        path = self.contracts_path / f"{name}.json"
        if path.exists():
            if read_json(path) != document:
                raise StateError(f"different persisted mission contract: {name}")
            return
        write_atomic(path, document)

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
        self, *, binding: dict, authorization: dict, runtime_boundary: dict
    ) -> dict:
        if self.root.is_symlink() or self.contracts_path.is_symlink():
            raise StateError("mission state and contracts directories cannot be symlinks")
        self._validate_contracts(binding, authorization, runtime_boundary)
        attempt_id = self._attempt_id(binding)
        with MissionLock(self.start_lock_path):
            self._write_contract("goal-binding", binding)
            self._write_contract("authorization", authorization)
            self._write_contract("runtime-boundary", runtime_boundary)
            if self.store.state_path.exists():
                state = self.store.load()
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
