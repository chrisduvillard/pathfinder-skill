from __future__ import annotations

from collections.abc import Callable

from .types import AdapterCapabilities, AdapterResult, GoalRecord, GoalStatus, Support
from ..errors import StateError


class ClaudeGoalAdapter:
    def __init__(self, launcher: Callable[[str], None] | None = None):
        self.launcher = launcher

    @property
    def capabilities(self) -> AdapterCapabilities:
        create = Support.SUPPORTED if self.launcher else Support.MANUAL
        return AdapterCapabilities(
            Support.MANUAL, create, Support.MANUAL, Support.MANUAL, Support.MANUAL
        )

    def create(self, objective: str) -> AdapterResult:
        if not objective.strip():
            raise StateError("Goal objective cannot be empty")
        command = f"/goal {objective}"
        if self.launcher:
            record = GoalRecord(None, objective, GoalStatus.ACTIVE)
            self.launcher(command)
            return AdapterResult("native-launched", record)
        return AdapterResult(
            "manual", GoalRecord(None, objective, GoalStatus.NONE), command
        )

    def inspect(self) -> AdapterResult:
        return AdapterResult(
            "manual", GoalRecord(None, None, GoalStatus.NONE),
            "Inspect the Claude /goal surface in the active session.",
        )
