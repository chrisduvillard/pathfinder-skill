from __future__ import annotations

import copy
import hashlib
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import StateError
from .mission_host import HostMissionController, document_sha256
from .policy import ExecutionPolicy
from .protected_surfaces import BASELINE_PATH, ProtectedSurfaceRegistry
from .state import utc_now
from .storage import MissionLock, MissionStore, read_json, write_atomic


TERMINAL_STATES = {"awaiting-review", "blocked", "abandoned"}
CHILD_TERMINAL_STATES = {"awaiting-review", "blocked", "abandoned"}


def _parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise StateError("goal pack time must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class GoalPackController:
    """Persist and drive an explicitly authorized sequence of one-Goal missions."""

    def __init__(self, root: str | Path, *, clock=utc_now):
        self.root = Path(root)
        self.state_path = self.root / "state.json"
        self.contracts_path = self.root / "contracts"
        self.binding_contracts_path = self.contracts_path / "goals"
        self.goals_path = self.root / "goals"
        self.lock_path = self.root / "goal-pack.lock"
        self.validator = MissionStore(self.root)
        self.clock = clock

    def _validate(self, schema: str, document: dict) -> None:
        self.validator.validate(schema, document)

    def _check_paths(self) -> None:
        for path in (
            self.root,
            self.contracts_path,
            self.binding_contracts_path,
            self.goals_path,
        ):
            if path.is_symlink():
                raise StateError(f"goal pack path cannot be a symlink: {path}")
            if path.exists() and not path.is_dir():
                raise StateError(f"goal pack path must be a directory: {path}")
        if self.state_path.is_symlink():
            raise StateError("goal pack state cannot be a symlink")

    def _write_contract(self, path: Path, document: dict) -> None:
        if path.is_symlink():
            raise StateError(f"goal pack contract cannot be a symlink: {path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise StateError(f"goal pack contract parent cannot be a symlink: {path.parent}")
        if path.exists():
            if not path.is_file() or read_json(path) != document:
                raise StateError(f"different persisted goal pack contract: {path.name}")
            path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            return
        write_atomic(path, document)
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    def _validate_bindings(
        self,
        bindings: list[dict],
        authorization: dict,
        registry: ProtectedSurfaceRegistry,
    ) -> None:
        if len(bindings) != len(authorization["goal_bindings"]):
            raise StateError("goal pack authorization does not cover every Goal Binding")
        if authorization["limits"]["max_goals"] != len(bindings):
            raise StateError("goal pack max_goals does not match the ordered Goal Binding count")
        identities = {"mission_id": set(), "binding_id": set(), "goal_id": set()}
        first_scope = None
        for position, (binding, authorized) in enumerate(
            zip(bindings, authorization["goal_bindings"], strict=True), 1
        ):
            self._validate("artifacts/goal-binding.schema.json", binding)
            if authorized["position"] != position:
                raise StateError("goal pack ordered Goal Binding positions are not sequential")
            expected = {
                "position": position,
                "mission_id": binding["mission_id"],
                "binding_id": binding["binding_id"],
                "goal_id": binding["goal_id"],
                "sha256": document_sha256(binding),
            }
            if authorized != expected:
                if authorized.get("sha256") != expected["sha256"]:
                    raise StateError("goal pack binding hash does not match its immutable contract")
                raise StateError("goal pack ordered Goal Binding identity does not match")
            for field in identities:
                value = binding[field]
                if value in identities[field]:
                    raise StateError(f"goal pack {field} values must be unique")
                identities[field].add(value)
            scope = binding["scope"]
            if first_scope is None:
                first_scope = scope
            elif scope != first_scope:
                raise StateError("every Goal Binding in a pack must use the same repository scope")
            if scope["base_commit"] != authorization["base_commit"]:
                raise StateError("goal pack authorization base_commit drift")
            for name, expected_hash in authorization["intent_hashes"].items():
                intent = binding["intent_snapshot"][name]
                if intent is None or intent["sha256"] != expected_hash:
                    raise StateError(f"goal pack intent hash drift: {name}")
            budgets = binding["budgets"]
            if budgets["max_open_prs"] != 0 or budgets["max_total_prs"] != 0:
                raise StateError("Goal Binding must disable publication for a goal pack")
            if (
                authorization["limits"]["max_attempts_per_goal"]
                > budgets["max_attempts_per_goal"]
            ):
                raise StateError("goal pack authorization widens max_attempts_per_goal")
            unknown = sorted(set(binding["protected_surfaces"]) - set(registry.categories))
            if unknown:
                raise StateError(
                    f"Goal Binding names an unknown protected surface: {unknown[0]}"
                )

    def _validate_start(
        self,
        bindings: list[dict],
        authorization: dict,
        runtime_boundary: dict,
        protected_policy: dict | None,
    ) -> ProtectedSurfaceRegistry:
        self._validate("mission/goal-pack-authorization.schema.json", authorization)
        self._validate("artifacts/runtime-boundary.schema.json", runtime_boundary)
        if authorization["publication_target"] not in {"none", "local-branch"}:
            raise StateError("goal pack supports local/no-publication targets only")
        if authorization["limits"]["max_total_prs"] != 0:
            raise StateError("goal pack authorization must disable publication")
        ExecutionPolicy(self.root, ()).validate_boundary(runtime_boundary)
        registry = ProtectedSurfaceRegistry(read_json(BASELINE_PATH), protected_policy)
        self._validate_bindings(bindings, authorization, registry)
        return registry

    def _initial_state(self, bindings: list[dict], authorization: dict, at: str) -> dict:
        deadline = _parse_instant(at) + timedelta(
            seconds=authorization["limits"]["max_wall_seconds"]
        )
        goals = []
        for position, binding in enumerate(bindings, 1):
            goals.append({
                "position": position,
                "mission_id": binding["mission_id"],
                "binding_id": binding["binding_id"],
                "goal_id": binding["goal_id"],
                "binding_sha256": document_sha256(binding),
                "status": "active" if position == 1 else "queued",
                "child_state_dir": f"goals/{position:04d}",
                "activated_at": at if position == 1 else None,
                "completed_at": None,
                "final_state": None,
            })
        return {
            "schema_version": 1,
            "pack_id": authorization["pack_id"],
            "authorization_id": authorization["authorization_id"],
            "state": "authorized",
            "revision": 0,
            "current_goal_index": 0,
            "goals": goals,
            "terminal_reason": None,
            "deadline_at": _format_instant(deadline),
            "created_at": at,
            "updated_at": at,
        }

    def _validate_state_invariants(self, state: dict) -> None:
        self._validate("mission/goal-pack-state.schema.json", state)
        if [item["position"] for item in state["goals"]] != list(
            range(1, len(state["goals"]) + 1)
        ):
            raise StateError("goal pack state positions are not sequential")
        for item in state["goals"]:
            if item["child_state_dir"] != f"goals/{item['position']:04d}":
                raise StateError("goal pack child state path does not match its position")
            status = item["status"]
            if status == "queued" and any(
                item[field] is not None
                for field in ("activated_at", "completed_at", "final_state")
            ):
                raise StateError("queued Goal cannot contain lifecycle timestamps")
            if status == "active" and (
                item["activated_at"] is None
                or item["completed_at"] is not None
                or item["final_state"] is not None
            ):
                raise StateError("active Goal has inconsistent lifecycle state")
            if status == "completed" and (
                item["completed_at"] is None
                or item["final_state"] != "awaiting-review"
            ):
                raise StateError("completed Goal lacks awaiting-review evidence")
            if status in {"blocked", "abandoned"} and (
                item["completed_at"] is None or item["final_state"] != status
            ):
                raise StateError(f"{status} Goal has inconsistent terminal evidence")
        active = [index for index, item in enumerate(state["goals"]) if item["status"] == "active"]
        if state["state"] in TERMINAL_STATES:
            if active or state["current_goal_index"] is not None:
                raise StateError("terminal goal pack cannot retain an active Goal")
        elif active != [state["current_goal_index"]]:
            raise StateError("goal pack must have exactly one active Goal")
        if state["state"] == "awaiting-review" and any(
            item["status"] != "completed" for item in state["goals"]
        ):
            raise StateError("awaiting-review goal pack contains incomplete work")
        identities = {
            name: [item[name] for item in state["goals"]]
            for name in ("mission_id", "binding_id", "goal_id")
        }
        if any(len(values) != len(set(values)) for values in identities.values()):
            raise StateError("goal pack state identities must be unique")

    def _load_state(self) -> dict:
        self._check_paths()
        if not self.state_path.is_file():
            raise StateError(f"goal pack state does not exist: {self.state_path}")
        state = read_json(self.state_path)
        self._validate_state_invariants(state)
        authorization = self._authorization()
        if state["pack_id"] != authorization["pack_id"]:
            raise StateError("goal pack state does not match authorization: pack_id")
        if state["authorization_id"] != authorization["authorization_id"]:
            raise StateError("goal pack state does not match authorization: authorization_id")
        expected_deadline = _format_instant(
            _parse_instant(state["created_at"])
            + timedelta(seconds=authorization["limits"]["max_wall_seconds"])
        )
        if state["deadline_at"] != expected_deadline:
            raise StateError("goal pack state deadline does not match authorization")
        expected_goals = [
            (
                item["position"], item["mission_id"], item["binding_id"],
                item["goal_id"], item["sha256"],
            )
            for item in authorization["goal_bindings"]
        ]
        actual_goals = [
            (
                item["position"], item["mission_id"], item["binding_id"],
                item["goal_id"], item["binding_sha256"],
            )
            for item in state["goals"]
        ]
        if actual_goals != expected_goals:
            raise StateError("goal pack state does not match ordered authorization bindings")
        return state

    def _save_state(self, current: dict, **changes) -> dict:
        latest = read_json(self.state_path)
        if latest["revision"] != current["revision"]:
            raise StateError("goal pack state changed while it was being updated")
        updated = copy.deepcopy(current)
        updated.update(changes)
        updated["revision"] = current["revision"] + 1
        updated["updated_at"] = self.clock()
        self._validate_state_invariants(updated)
        write_atomic(self.state_path, updated)
        return updated

    def _validate_persisted_identity(
        self, state: dict, bindings: list[dict], authorization: dict
    ) -> None:
        if state["pack_id"] != authorization["pack_id"]:
            raise StateError("persisted goal pack identity drift: pack_id")
        if state["authorization_id"] != authorization["authorization_id"]:
            raise StateError("persisted goal pack identity drift: authorization_id")
        expected = [
            (
                binding["mission_id"], binding["binding_id"], binding["goal_id"],
                document_sha256(binding),
            )
            for binding in bindings
        ]
        actual = [
            (
                item["mission_id"], item["binding_id"], item["goal_id"],
                item["binding_sha256"],
            )
            for item in state["goals"]
        ]
        if actual != expected:
            raise StateError("persisted goal pack ordered Goal Binding drift")

    def start(
        self,
        *,
        bindings: list[dict],
        authorization: dict,
        runtime_boundary: dict,
        protected_policy: dict | None = None,
    ) -> dict:
        bindings = list(bindings)
        self._check_paths()
        registry = self._validate_start(
            bindings, authorization, runtime_boundary, protected_policy
        )
        with MissionLock(self.lock_path):
            self._check_paths()
            self._write_contract(self.contracts_path / "authorization.json", authorization)
            self._write_contract(self.contracts_path / "runtime-boundary.json", runtime_boundary)
            self._write_contract(
                self.contracts_path / "protected-surfaces.json", registry.to_document()
            )
            if protected_policy is not None:
                self._write_contract(
                    self.contracts_path / "protected-policy.json", protected_policy
                )
            for position, binding in enumerate(bindings, 1):
                self._write_contract(
                    self.binding_contracts_path / f"{position:04d}.json", binding
                )
            if self.state_path.exists():
                state = self._load_state()
                self._validate_persisted_identity(state, bindings, authorization)
                return state
            state = self._initial_state(bindings, authorization, self.clock())
            self._validate_state_invariants(state)
            write_atomic(self.state_path, state)
            return state

    def status(self) -> dict:
        return self._load_state()

    def _active(self, state: dict) -> dict:
        index = state["current_goal_index"]
        if index is None:
            raise StateError("goal pack has no active Goal")
        return state["goals"][index]

    def _binding(self, item: dict) -> dict:
        path = self.binding_contracts_path / f"{item['position']:04d}.json"
        if path.is_symlink() or not path.is_file():
            raise StateError("goal pack binding contract must be a regular file")
        binding = read_json(path)
        self._validate("artifacts/goal-binding.schema.json", binding)
        if document_sha256(binding) != item["binding_sha256"]:
            raise StateError("persisted goal pack binding hash drift")
        return binding

    def _authorization(self) -> dict:
        path = self.contracts_path / "authorization.json"
        if path.is_symlink() or not path.is_file():
            raise StateError("goal pack authorization must be a regular file")
        authorization = read_json(path)
        self._validate("mission/goal-pack-authorization.schema.json", authorization)
        return authorization

    def _runtime_boundary(self) -> dict:
        path = self.contracts_path / "runtime-boundary.json"
        if path.is_symlink() or not path.is_file():
            raise StateError("goal pack Runtime Boundary must be a regular file")
        boundary = read_json(path)
        self._validate("artifacts/runtime-boundary.schema.json", boundary)
        return boundary

    def _protected_policy(self) -> dict | None:
        path = self.contracts_path / "protected-policy.json"
        if path.is_symlink():
            raise StateError("goal pack protected policy cannot be a symlink")
        if path.exists() and not path.is_file():
            raise StateError("goal pack protected policy must be a regular file")
        return read_json(path) if path.exists() else None

    def _derived_authorization(
        self, state: dict, item: dict, binding: dict, pack_authorization: dict
    ) -> dict:
        activated_at = _parse_instant(item["activated_at"])
        remaining = int((_parse_instant(state["deadline_at"]) - activated_at).total_seconds())
        if remaining < 1:
            raise StateError("goal pack wall-clock budget expired")
        seed = f"{pack_authorization['authorization_id']}:{binding['binding_id']}"
        child_authorization_id = f"authorization_{hashlib.sha256(seed.encode()).hexdigest()[:24]}"
        return {
            "schema_version": 1,
            "authorization_id": child_authorization_id,
            "mission_id": binding["mission_id"],
            "binding_id": binding["binding_id"],
            "explicit_request": True,
            "trusted_source": pack_authorization["trusted_source"],
            "authorized_at": pack_authorization["authorized_at"],
            "base_commit": binding["scope"]["base_commit"],
            "intent_hashes": pack_authorization["intent_hashes"],
            "limits": {
                "max_goals": 1,
                "max_attempts": min(
                    pack_authorization["limits"]["max_attempts_per_goal"],
                    binding["budgets"]["max_attempts_per_goal"],
                ),
                "max_wall_seconds": min(
                    remaining, binding["budgets"]["max_wall_seconds"]
                ),
                "max_total_prs": 0,
            },
            "publication_target": pack_authorization["publication_target"],
            "snapshot_sha256": document_sha256({
                "pack_authorization_sha256": document_sha256(pack_authorization),
                "binding_sha256": document_sha256(binding),
            }),
        }

    def _child_controller(self, state: dict, item: dict) -> HostMissionController:
        child_root = self.root / item["child_state_dir"]
        if child_root.is_symlink():
            raise StateError("goal pack child state cannot be a symlink")
        binding = self._binding(item)
        pack_authorization = self._authorization()
        child_authorization = self._derived_authorization(
            state, item, binding, pack_authorization
        )
        boundary = self._runtime_boundary()
        starter = HostMissionController(
            child_root, clock=lambda: item["activated_at"]
        )
        starter.start(
            binding=binding,
            authorization=child_authorization,
            runtime_boundary=boundary,
            protected_policy=self._protected_policy(),
        )
        return HostMissionController(child_root, clock=self.clock)

    def _block_for_deadline(self, state: dict) -> dict:
        goals = copy.deepcopy(state["goals"])
        active = goals[state["current_goal_index"]]
        active.update(
            status="blocked", completed_at=self.clock(), final_state="blocked"
        )
        return self._save_state(
            state,
            state="blocked",
            current_goal_index=None,
            goals=goals,
            terminal_reason="budget-limited",
        )

    def _finish_active(self, state: dict, child_state: dict) -> dict:
        goals = copy.deepcopy(state["goals"])
        index = state["current_goal_index"]
        current = goals[index]
        current["completed_at"] = child_state["updated_at"]
        current["final_state"] = child_state["state"]
        if child_state["state"] != "awaiting-review":
            current["status"] = child_state["state"]
            terminal_reason = (
                "budget-limited"
                if child_state.get("terminal_reason") == "budget-limited"
                else (
                    "goal-blocked"
                    if child_state["state"] == "blocked"
                    else "abandoned"
                )
            )
            return self._save_state(
                state,
                state=child_state["state"],
                current_goal_index=None,
                goals=goals,
                terminal_reason=terminal_reason,
            )
        current["status"] = "completed"
        if index + 1 == len(goals):
            return self._save_state(
                state,
                state="awaiting-review",
                current_goal_index=None,
                goals=goals,
            )
        goals[index + 1].update(status="active", activated_at=self.clock())
        return self._save_state(
            state,
            state="running",
            current_goal_index=index + 1,
            goals=goals,
        )

    def _result(self, child_result: dict, state: dict) -> dict:
        result = dict(child_result)
        if "state" in result:
            result["goal_state"] = result.pop("state")
        result.update(
            pack_id=state["pack_id"],
            current_goal_index=state["current_goal_index"],
            state=state,
        )
        return result

    def next(self) -> dict:
        self._check_paths()
        with MissionLock(self.lock_path):
            state = self._load_state()
            if state["state"] in TERMINAL_STATES:
                return {"status": "terminal", "state": state}
            item = self._active(state)
            child_root = self.root / item["child_state_dir"]
            if child_root.is_symlink():
                raise StateError("goal pack child state cannot be a symlink")
            child_state_path = child_root / "state.json"
            if child_state_path.exists():
                child_state = MissionStore(child_root).load()
                if child_state["state"] in CHILD_TERMINAL_STATES:
                    updated = self._finish_active(state, child_state)
                    return {
                        "status": (
                            "terminal"
                            if updated["state"] in TERMINAL_STATES
                            else "goal-advanced"
                        ),
                        "state": updated,
                    }
            if _parse_instant(self.clock()) >= _parse_instant(state["deadline_at"]):
                return {"status": "terminal", "state": self._block_for_deadline(state)}
            controller = self._child_controller(state, item)
            if state["state"] == "authorized":
                state = self._save_state(state, state="running")
            return self._result(controller.next(), state)

    def record(self, receipt: dict) -> dict:
        self._check_paths()
        with MissionLock(self.lock_path):
            state = self._load_state()
            if state["state"] in TERMINAL_STATES:
                raise StateError(f"cannot record a receipt for terminal goal pack: {state['state']}")
            item = self._active(state)
            if receipt.get("mission_id") != item["mission_id"]:
                raise StateError("host receipt does not belong to the active queued Goal")
            child_root = self.root / item["child_state_dir"]
            if not (child_root / "state.json").is_file():
                raise StateError("active queued Goal has not started")
            result = HostMissionController(child_root, clock=self.clock).record(receipt)
            return self._result(result, state)

    def abandon(self) -> dict:
        self._check_paths()
        with MissionLock(self.lock_path):
            state = self._load_state()
            if state["state"] in TERMINAL_STATES:
                raise StateError(f"cannot abandon terminal goal pack in {state['state']}")
            item = self._active(state)
            child_root = self.root / item["child_state_dir"]
            child_state_path = child_root / "state.json"
            if child_state_path.exists():
                store = MissionStore(child_root)
                child_state = store.load()
                if child_state["state"] not in CHILD_TERMINAL_STATES:
                    store.move("abandoned", attempt_id=child_state.get("attempt_id"))
            goals = copy.deepcopy(state["goals"])
            goals[state["current_goal_index"]].update(
                status="abandoned", completed_at=self.clock(), final_state="abandoned"
            )
            return self._save_state(
                state,
                state="abandoned",
                current_goal_index=None,
                goals=goals,
                terminal_reason="abandoned",
            )
