from __future__ import annotations

from .types import AdapterCapabilities, AdapterResult, GoalRecord, GoalStatus, Support
from ..errors import StateError


class GenericGoalAdapter:
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            Support.UNSUPPORTED, Support.MANUAL, Support.MANUAL,
            Support.MANUAL, Support.MANUAL,
        )

    def create(self, objective: str) -> AdapterResult:
        if not objective.strip():
            raise StateError("Goal objective cannot be empty")
        instruction = (
            "Implementation Goal (non-persistent):\n"
            f"{objective}\n\n"
            "Continue explicitly after each checkpoint until the evidence satisfies the objective."
        )
        return AdapterResult(
            "non-persistent-fallback",
            GoalRecord(None, objective, GoalStatus.NONE),
            instruction,
        )
