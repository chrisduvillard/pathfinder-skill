from __future__ import annotations

from typing import Mapping


AMBIGUOUS_MEMBERSHIP_TYPES = frozenset({
    "Team", "RepositoryRole", "OrganizationAdmin",
})

IDLESS_RULESET_BYPASS_TYPES = frozenset({"OrganizationAdmin", "DeployKey"})


def _actor_identity(actor_type: object, actor_id: object) -> str:
    if actor_type in IDLESS_RULESET_BYPASS_TYPES:
        if actor_id is not None:
            raise ValueError(f"{actor_type} bypass actor must not carry an id")
        return f"{actor_type}:all"
    if not isinstance(actor_id, int) or isinstance(actor_id, bool) or actor_id < 1:
        raise ValueError(f"{actor_type} bypass actor requires a positive integer id")
    return f"{actor_type}:{actor_id}"


def ruleset_bypass_actor_key(
    actor_type: object, actor_id: object, bypass_mode: object
) -> str:
    return f"{_actor_identity(actor_type, actor_id)}:{bypass_mode}"


def ruleset_bypass_actor_identity(key: str) -> str:
    return key.rsplit(":", 1)[0]


def bypass_actor_type(key: str) -> str:
    return key.split(":", 1)[0]


def bypass_membership_key(value: Mapping[str, object]) -> tuple[object, ...]:
    actor_type = value["actor_type"]
    actor_id = value["actor_id"]
    if value["policy_source"] == "classic-protection":
        return ("classic-protection", None, _actor_identity(actor_type, actor_id), None)
    return (
        "ruleset",
        value["ruleset_id"],
        _actor_identity(actor_type, actor_id),
        value["bypass_mode"],
    )


def bypass_membership_assessment(value: Mapping[str, object]) -> str:
    """Derive match/no-match/unknown from a closed membership observation."""
    actor_type = value["actor_type"]
    if actor_type == "Team":
        state = value["membership_state"]
        role = value["membership_role"]
        if state == "active" and role in {"member", "maintainer"}:
            return "match"
        if state == "absent" and role is None:
            return "no-match"
        return "unknown"
    if actor_type == "OrganizationAdmin":
        state = value["membership_state"]
        role = value["organization_role"]
        if state == "active" and role == "admin":
            return "match"
        if (state == "active" and role == "member") or (
            state == "absent" and role is None
        ):
            return "no-match"
        return "unknown"
    if actor_type == "RepositoryRole":
        permission = value["subject_permission"]
        subject_role = value["subject_role_name"]
        if permission == "none" and subject_role is None:
            return "no-match"
        if permission != "none" and isinstance(subject_role, str):
            return "match" if subject_role == value["bypass_role_name"] else "unknown"
        return "unknown"
    return "unknown"


def bypass_membership_endpoint(
    value: Mapping[str, object], repository: Mapping[str, object]
) -> str:
    login = str(value["subject_login"]).replace("[", "%5B").replace("]", "%5D")
    actor_type = value["actor_type"]
    if actor_type == "Team":
        return (
            f"/orgs/{value['organization_login']}/teams/{value['team_slug']}"
            f"/memberships/{login}"
        )
    if actor_type == "OrganizationAdmin":
        return f"/orgs/{value['organization_login']}/memberships/{login}"
    if actor_type == "RepositoryRole":
        return (
            f"/repos/{repository['owner']}/{repository['name']}"
            f"/collaborators/{login}/permission"
        )
    raise ValueError("membership actor type has no evidence endpoint")


def bypass_membership_status(value: Mapping[str, object]) -> int:
    if value["actor_type"] in {"Team", "OrganizationAdmin"} and (
        value["membership_state"] == "absent"
    ):
        return 404
    return 200
