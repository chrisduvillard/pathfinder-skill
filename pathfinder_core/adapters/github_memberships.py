from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence
from urllib.parse import quote

from .github_get import GitHubGETClient
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)


_TARGET_FIELDS = {
    "policy_source", "ruleset_id", "actor_type", "actor_id",
    "bypass_mode", "actor_name",
}
_BYPASS_MODES = {"always", "pull_request", "exempt"}


@dataclass(frozen=True)
class QualifiedMembershipResponse:
    data: Mapping[str, object] | None = field(repr=False)
    status: int
    audit: RequestAudit


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "GitHub bypass membership identity is malformed")
    return value


class GitHubBypassMembershipReader:
    """Resolve every membership-based bypass actor through exact GETs."""

    def __init__(self, client: GitHubGETClient):
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub membership reads require an installation token")
        self.client = client

    def read_qualified_membership(
        self, target: str, *, membership: str
    ) -> QualifiedMembershipResponse:
        patterns = {
            "team": r"/orgs/[^/]+/teams/[^/]+/memberships/[^/]+",
            "organization": r"/orgs/[^/]+/memberships/[^/]+",
        }
        pattern = patterns.get(membership)
        if pattern is None or re.fullmatch(pattern, target) is None:
            raise ValueError("GitHub membership target does not match its kind")
        response = self.client._response(
            "bypass-memberships", target, allowed_statuses=frozenset({404})
        )
        decoded = self.client._decode_json("bypass-memberships", response)
        accepted = {
            item.strip().lower()
            for item in decoded.headers.get(
                "x-accepted-github-permissions", ""
            ).split(";")
            if item.strip()
        }
        qualified = "members=read" in accepted
        audit = RequestAudit(
            decoded.audit.request_id,
            decoded.audit.observed_at,
            decoded.audit.etag,
            target,
            response.status,
            qualified,
        )
        if response.status not in {200, 404}:
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                "bypass-memberships",
                "GitHub membership response returned an unexpected status",
            )
        if not qualified:
            raise GitHubObservationError(
                ObservationOutcome.PERMISSION_MISSING,
                "bypass-memberships",
                "GitHub membership response did not qualify Members read",
            )
        if response.status == 200:
            if not isinstance(decoded.data, Mapping):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    "bypass-memberships",
                    "GitHub membership response is not an object",
                )
            return QualifiedMembershipResponse(
                decoded.data, response.status, audit
            )
        error = decoded.data
        if (
            not isinstance(error, Mapping)
            or set(error) != {"message", "documentation_url", "status"}
            or error["message"] != "Not Found"
            or error["status"] != "404"
            or not isinstance(error["documentation_url"], str)
            or not error["documentation_url"].startswith(
                "https://docs.github.com/rest/"
            )
        ):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                "bypass-memberships",
                "GitHub membership absence proof is malformed",
            )
        return QualifiedMembershipResponse(None, response.status, audit)

    @staticmethod
    def _target(value: Mapping[str, object], index: int) -> dict:
        surface = f"bypass-memberships[{index}]"
        if not isinstance(value, Mapping) or set(value) != _TARGET_FIELDS:
            raise _fail(surface, "GitHub bypass membership target is not closed")
        actor_type = value["actor_type"]
        if actor_type not in {"Team", "OrganizationAdmin", "RepositoryRole"}:
            raise _fail(surface, "GitHub bypass membership type is unsupported")
        policy_source = value["policy_source"]
        ruleset_id = value["ruleset_id"]
        bypass_mode = value["bypass_mode"]
        if policy_source == "classic-protection":
            if actor_type != "Team" or ruleset_id is not None or bypass_mode is not None:
                raise _fail(surface, "classic bypass membership identity differs")
        elif policy_source == "ruleset":
            _positive_int(ruleset_id, surface)
            if bypass_mode not in _BYPASS_MODES:
                raise _fail(surface, "ruleset bypass mode is unknown")
        else:
            raise _fail(surface, "bypass membership policy source is unknown")
        actor_id = value["actor_id"]
        actor_name = value["actor_name"]
        if actor_type == "OrganizationAdmin":
            if actor_id is not None or actor_name is not None:
                raise _fail(surface, "organization-admin bypass must be idless")
        else:
            _positive_int(actor_id, surface)
            pattern = (
                r"[A-Za-z0-9_.-]{1,100}"
                if actor_type == "Team"
                else r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}"
            )
            if (
                not isinstance(actor_name, str)
                or re.fullmatch(pattern, actor_name) is None
            ):
                raise _fail(surface, "bypass membership source metadata is missing")
        return dict(value)

    @staticmethod
    def _team(data: Mapping[str, object] | None, surface: str) -> tuple[str, str | None]:
        if data is None:
            return "absent", None
        if set(data) != {"url", "role", "state"}:
            raise _fail(surface, "GitHub team membership fields are missing or unknown")
        if data["state"] not in {"active", "pending"} or data["role"] not in {
            "member", "maintainer",
        }:
            raise _fail(surface, "GitHub team membership state or role is unknown")
        return str(data["state"]), str(data["role"])

    @staticmethod
    def _organization(
        data: Mapping[str, object] | None,
        surface: str,
        *,
        actor_id: int,
        login: str,
    ) -> tuple[str, str | None]:
        if data is None:
            return "absent", None
        required = {"url", "state", "role", "user"}
        optional = {
            "organization_url", "user", "organization", "direct_membership",
            "enterprise_teams_providing_indirect_membership",
        }
        if not required <= set(data) or set(data) - required - optional:
            raise _fail(
                surface, "GitHub organization membership fields are missing or unknown"
            )
        if data["state"] not in {"active", "pending"} or data["role"] not in {
            "admin", "member",
        }:
            raise _fail(
                surface, "GitHub organization membership state or role is unknown"
            )
        user = data["user"]
        if (
            not isinstance(user, Mapping)
            or user.get("id") != actor_id
            or user.get("login") != login
        ):
            raise _fail(
                surface, "GitHub organization membership subject identity differs"
            )
        return str(data["state"]), str(data["role"])

    def read_all(
        self,
        targets: Sequence[Mapping[str, object]],
        *,
        repository: Mapping[str, object],
        subject: Mapping[str, object],
    ) -> PageResponse:
        if set(repository) != {"owner", "name"} or set(subject) != {
            "actor_id", "login",
        }:
            raise ValueError("GitHub membership repository or subject is not closed")
        owner = repository["owner"]
        name = repository["name"]
        actor_id = _positive_int(subject["actor_id"], "bypass-memberships.subject")
        login = subject["login"]
        if (
            not isinstance(owner, str)
            or re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner
            ) is None
            or not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) is None
            or not isinstance(login, str)
            or re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\[bot\]",
                login,
            ) is None
        ):
            raise ValueError("GitHub membership repository or subject is malformed")
        escaped_owner = quote(owner, safe="")
        escaped_name = quote(name, safe="")
        escaped_login = quote(login, safe="")

        candidates = []
        seen = set()
        for index, candidate in enumerate(targets):
            target = self._target(candidate, index)
            key = json.dumps(target, sort_keys=True, separators=(",", ":"))
            if key in seen:
                raise _fail(
                    f"bypass-memberships[{index}]",
                    "GitHub bypass membership target is duplicated",
                )
            seen.add(key)
            candidates.append(target)
        if len(candidates) > self.client.max_pages:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "bypass-memberships",
                "GitHub membership request ceiling would be exceeded",
            )

        normalized = []
        audits = []
        for index, target in enumerate(candidates):
            common = {
                "policy_source": target["policy_source"],
                "ruleset_id": target["ruleset_id"],
                "actor_type": target["actor_type"],
                "actor_id": target["actor_id"],
                "bypass_mode": target["bypass_mode"],
                "subject_actor_id": actor_id,
                "subject_login": login,
            }
            if target["actor_type"] == "Team":
                endpoint = (
                    f"/orgs/{escaped_owner}/teams/"
                    f"{quote(str(target['actor_name']), safe='')}/memberships/"
                    f"{escaped_login}"
                )
                response = self.read_qualified_membership(
                    endpoint, membership="team"
                )
                state, role = self._team(
                    response.data, f"bypass-memberships[{index}]"
                )
                item = {
                    **common,
                    "request_id": response.audit.request_id,
                    "organization_login": owner,
                    "team_slug": target["actor_name"],
                    "membership_state": state,
                    "membership_role": role,
                }
            elif target["actor_type"] == "OrganizationAdmin":
                endpoint = f"/orgs/{escaped_owner}/memberships/{escaped_login}"
                response = self.read_qualified_membership(
                    endpoint, membership="organization"
                )
                state, role = self._organization(
                    response.data,
                    f"bypass-memberships[{index}]",
                    actor_id=actor_id,
                    login=login,
                )
                item = {
                    **common,
                    "request_id": response.audit.request_id,
                    "organization_login": owner,
                    "membership_state": state,
                    "organization_role": role,
                }
            else:
                endpoint = (
                    f"/repos/{escaped_owner}/{escaped_name}/collaborators/"
                    f"{escaped_login}/permission"
                )
                response = self.client.get_qualified_repository_permission(
                    "bypass-memberships", endpoint
                )
                data = response.data
                if data is None or set(data) != {"permission", "role_name", "user"}:
                    raise _fail(
                        f"bypass-memberships[{index}]",
                        "GitHub repository permission fields are missing or unknown",
                    )
                user = data["user"]
                if (
                    not isinstance(user, Mapping)
                    or user.get("id") != actor_id
                    or user.get("login") != login
                    or data["permission"] not in {
                        "admin", "maintain", "write", "triage", "read", "none",
                    }
                    or (
                        data["role_name"] is not None
                        and (
                            not isinstance(data["role_name"], str)
                            or re.fullmatch(
                                r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}",
                                data["role_name"],
                            ) is None
                        )
                    )
                ):
                    raise _fail(
                        f"bypass-memberships[{index}]",
                        "GitHub repository permission identity or role is unknown",
                    )
                item = {
                    **common,
                    "request_id": response.audit.request_id,
                    "bypass_role_name": target["actor_name"],
                    "subject_role_name": data["role_name"],
                    "subject_permission": data["permission"],
                }
            normalized.append(item)
            if any(
                audit.request_id == response.audit.request_id
                for audit in audits
            ):
                raise _fail(
                    "bypass-memberships", "GitHub membership request id is duplicated"
                )
            audits.append(response.audit)
        return PageResponse(
            tuple(normalized), len(audits), len(normalized), True, False,
            None, tuple(audits),
        )
