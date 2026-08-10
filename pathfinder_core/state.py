from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from .errors import StateError


ACTIVE_STATES = {
    "planned",
    "authorized",
    "prepared",
    "running",
    "verifying",
    "verified",
    "committed",
    "published",
}
TERMINAL_STATES = {"awaiting-review", "merged", "blocked", "abandoned"}
ALLOWED_TRANSITIONS = {
    "planned": {"authorized", "blocked", "abandoned"},
    "authorized": {"prepared", "blocked", "abandoned"},
    "prepared": {"running", "blocked", "abandoned"},
    "running": {"verifying", "blocked", "abandoned"},
    "verifying": {"verified", "running", "blocked", "abandoned"},
    "verified": {"committed", "blocked", "abandoned"},
    "committed": {"published", "awaiting-review", "blocked", "abandoned"},
    "published": {"awaiting-review", "blocked", "abandoned"},
    "awaiting-review": {"merged"},
    "merged": set(),
    "blocked": set(),
    "abandoned": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def transition(document: dict, target: str, *, at: str | None = None) -> dict:
    current = document.get("state")
    if current not in ALLOWED_TRANSITIONS:
        raise StateError(f"unknown current mission state: {current!r}")
    if target == current:
        return deepcopy(document)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise StateError(f"forbidden mission transition: {current} -> {target}")
    result = deepcopy(document)
    result["state"] = target
    result["revision"] = int(document.get("revision", 0)) + 1
    result["updated_at"] = at or utc_now()
    return result
