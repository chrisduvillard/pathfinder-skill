from __future__ import annotations


AMBIGUOUS_MEMBERSHIP_TYPES = frozenset({
    "Team", "RepositoryRole", "OrganizationAdmin",
})


def ruleset_bypass_actor_key(
    actor_type: object, actor_id: object, bypass_mode: object
) -> str:
    return f"{actor_type}:{actor_id}:{bypass_mode}"


def ruleset_bypass_actor_identity(key: str) -> str:
    return key.rsplit(":", 1)[0]


def bypass_actor_type(key: str) -> str:
    return key.split(":", 1)[0]
