from __future__ import annotations

from datetime import datetime


def parse_aware_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp and reject values without a UTC offset."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed
