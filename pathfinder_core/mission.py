from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .adapters.github import PublicationResult, PublicationState
from .adapters.types import AdapterResult
from .errors import StateError
from .storage import MissionStore


class MissionCallbacks(Protocol):
    def prepare(self, state: dict) -> dict: ...
    def activate(self, objective: str) -> AdapterResult: ...
    def implement(self, state: dict) -> None: ...
    def verify(self, state: dict) -> bool: ...
    def commit(self, state: dict) -> str: ...
    def publish(self, state: dict) -> PublicationResult: ...


class MissionOrchestrator:
    def __init__(
        self, *, store: MissionStore, objective: str, authorization: dict,
        runtime_boundary: dict, callbacks: MissionCallbacks, publish: bool,
        after_checkpoint: Callable[[dict], None] | None = None,
    ):
        self.store = store
        self.objective = objective
        self.authorization = authorization
        self.runtime_boundary = runtime_boundary
        self.callbacks = callbacks
        self.publish_enabled = publish
        self.after_checkpoint = after_checkpoint or (lambda _state: None)

    def _move(self, target: str, *, state: dict, changes=None) -> dict:
        updated = self.store.move(
            target, attempt_id=state.get("attempt_id"), changes=changes or {}
        )
        self.after_checkpoint(updated)
        return updated

    def _validate_contract(self, state: dict) -> None:
        self.store.validate("mission/authorization-snapshot.schema.json", self.authorization)
        self.store.validate("artifacts/runtime-boundary.schema.json", self.runtime_boundary)
        expected = (
            ("mission_id", state["mission_id"]),
            ("binding_id", state["binding_id"]),
            ("base_commit", state["base_commit"]),
        )
        for field, value in expected:
            if self.authorization[field] != value:
                raise StateError(f"authorization snapshot drift: {field} does not match mission")
        if not self.runtime_boundary["execution_eligible"]:
            raise StateError("runtime boundary is not eligible for unattended execution")

    def run(self) -> dict:
        state = self.store.load()
        self._validate_contract(state)
        if state["state"] in {"awaiting-review", "merged", "blocked", "abandoned"}:
            return state

        if state["state"] == "planned":
            state = self._move(
                "authorized", state=state,
                changes={"authorization_id": self.authorization["authorization_id"]},
            )
        if state["state"] == "authorized":
            prepared = self.callbacks.prepare(state)
            required = {"attempt_id", "worktree_id", "worktree_path", "branch_id", "branch_name"}
            if set(prepared) != required or any(prepared[name] is None for name in required):
                raise StateError("prepare callback returned an incomplete mission identity")
            state = self._move("prepared", state=state, changes=prepared)
        if state["state"] == "prepared":
            activation = self.callbacks.activate(self.objective)
            if activation.mode in {"manual", "non-persistent-fallback"}:
                return self._move("blocked", state=state)
            state = self._move("running", state=state)
        if state["state"] == "running":
            self.callbacks.implement(state)
            state = self._move("verifying", state=state)
        if state["state"] == "verifying":
            if not self.callbacks.verify(state):
                return self._move("blocked", state=state)
            state = self._move("verified", state=state)
        if state["state"] == "verified":
            commit_id = self.callbacks.commit(state)
            state = self._move("committed", state=state, changes={"commit_ids": [commit_id]})
        if state["state"] == "committed":
            if not self.publish_enabled:
                return self._move("awaiting-review", state=state)
            publication = self.callbacks.publish(state)
            if publication.state is not PublicationState.AWAITING_REVIEW or not publication.pull_request:
                return self._move("blocked", state=state)
            state = self._move(
                "published", state=state,
                changes={
                    "pr_id": publication.pull_request.pr_id,
                    "pr_url": publication.pull_request.url,
                },
            )
        if state["state"] == "published":
            state = self._move("awaiting-review", state=state)
        return state
