from __future__ import annotations

from .base import NativeGoalBackend
from .types import AdapterCapabilities, AdapterResult, GoalRecord, GoalStatus, Support
from ..errors import CapabilityError, StateError


class CodexGoalAdapter:
    def __init__(self, backend: NativeGoalBackend | None = None):
        self.backend = backend

    @property
    def capabilities(self) -> AdapterCapabilities:
        support = Support.SUPPORTED if self.backend else Support.MANUAL
        return AdapterCapabilities(support, support, support, support, support)

    def inspect(self) -> AdapterResult:
        if not self.backend:
            return AdapterResult(
                "manual", GoalRecord(None, None, GoalStatus.NONE),
                "Run /goal to inspect the current Codex Goal.",
            )
        return AdapterResult("native", self.backend.inspect())

    def create(self, objective: str) -> AdapterResult:
        if not objective.strip():
            raise StateError("Goal objective cannot be empty")
        if not self.backend:
            return AdapterResult(
                "manual", GoalRecord(None, objective, GoalStatus.NONE), f"/goal {objective}"
            )
        current = self.backend.inspect()
        if current.status in {GoalStatus.ACTIVE, GoalStatus.PAUSED}:
            if current.objective == objective:
                return AdapterResult("native-reused", current)
            raise StateError("an unfinished Codex Goal already exists; resume, finish, or clear it")
        return AdapterResult("native-created", self.backend.create(objective))

    def observe(self) -> AdapterResult:
        if not self.backend:
            return self.inspect()
        return AdapterResult("native", self.backend.observe())

    def complete(self, goal_id: str, *, evidence_validated: bool) -> AdapterResult:
        if not evidence_validated:
            raise StateError("Goal completion requires controller-validated evidence")
        if not self.backend:
            return AdapterResult(
                "manual", GoalRecord(goal_id, None, GoalStatus.COMPLETE),
                "Use the host Goal completion control after reviewing the evidence.",
            )
        return AdapterResult("native-completed", self.backend.complete(goal_id))

    def block(self, goal_id: str, *, consecutive_blocked_turns: int) -> AdapterResult:
        if consecutive_blocked_turns < 3:
            raise CapabilityError("host-level blocked requires three consecutive blocked turns")
        if not self.backend:
            return AdapterResult(
                "manual", GoalRecord(goal_id, None, GoalStatus.BLOCKED),
                "Use the host Goal blocked control with the recorded blocker.",
            )
        return AdapterResult("native-blocked", self.backend.block(goal_id))
