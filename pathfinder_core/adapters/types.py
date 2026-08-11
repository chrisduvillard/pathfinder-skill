from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Support(str, Enum):
    SUPPORTED = "supported"
    MANUAL = "manual"
    UNSUPPORTED = "unsupported"


class GoalStatus(str, Enum):
    NONE = "none"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    BUDGET_LIMITED = "budget-limited"


@dataclass(frozen=True)
class AdapterCapabilities:
    inspect: Support
    create: Support
    observe: Support
    complete: Support
    block: Support

    def as_dict(self):
        return {
            "inspect": self.inspect.value,
            "create": self.create.value,
            "observe": self.observe.value,
            "complete": self.complete.value,
            "block": self.block.value,
        }


@dataclass(frozen=True)
class GoalRecord:
    goal_id: str | None
    objective: str | None
    status: GoalStatus


@dataclass(frozen=True)
class AdapterResult:
    mode: str
    record: GoalRecord
    instruction: str | None = None
