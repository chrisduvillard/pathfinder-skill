from __future__ import annotations

import re
from datetime import datetime
from typing import Mapping
from urllib.parse import quote

from .github_get import GitHubGETClient
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)


_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?")
_SHA = re.compile(r"[0-9a-f]{40}")
_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}
_ASSOCIATIONS = {
    "OWNER", "MEMBER", "COLLABORATOR", "CONTRIBUTOR", "FIRST_TIMER",
    "FIRST_TIME_CONTRIBUTOR", "NONE",
}
_PERMISSIONS = {"admin", "maintain", "write", "triage", "read", "none"}
_REVIEW_FIELDS = {
    "id", "node_id", "user", "body", "state", "html_url",
    "pull_request_url", "_links", "submitted_at", "commit_id",
    "author_association", "performed_via_github_app",
}
_USER_FIELDS = {
    "login", "id", "node_id", "avatar_url", "gravatar_id", "url",
    "html_url", "followers_url", "following_url", "gists_url",
    "starred_url", "subscriptions_url", "organizations_url", "repos_url",
    "events_url", "received_events_url", "type", "user_view_type",
    "site_admin", "name", "email", "starred_at",
}


def _fail(detail: str, *, surface: str = "reviews") -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _positive_int(value: object, detail: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(detail)
    return value


def _timestamp(value: object, detail: str) -> str:
    if not isinstance(value, str):
        raise _fail(detail)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(detail) from None
    if parsed.utcoffset() is None:
        raise _fail(detail)
    return value


class GitHubReviewReader:
    """Read every REST review and bind each actor's current repository access."""

    def __init__(self, client: GitHubGETClient):
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub review reads require an installation token")
        self.client = client

    @staticmethod
    def _identity(value: object, index: int) -> tuple[int, str, str]:
        surface = f"reviews[{index}].user"
        if not isinstance(value, Mapping):
            raise _fail("GitHub review actor is not an object", surface=surface)
        missing = {"id", "login", "type"} - value.keys()
        extras = set(value) - _USER_FIELDS
        if missing or extras:
            raise _fail(
                "GitHub review actor fields are missing or unknown", surface=surface
            )
        actor_id = _positive_int(value["id"], "GitHub review actor id is malformed")
        login = value["login"]
        actor_type = value["type"]
        if (
            not isinstance(login, str)
            or _LOGIN.fullmatch(login) is None
            or actor_type not in {"User", "Bot"}
            or (actor_type == "Bot") != login.endswith("[bot]")
        ):
            raise _fail(
                "GitHub review actor identity is unsupported", surface=surface
            )
        return actor_id, login, actor_type

    @staticmethod
    def _review(value: Mapping[str, object], index: int) -> dict[str, object]:
        surface = f"reviews[{index}]"
        required = {
            "id", "user", "state", "commit_id", "submitted_at",
            "author_association",
        }
        if not isinstance(value, Mapping) or required - value.keys():
            raise _fail("GitHub review fields are missing", surface=surface)
        if set(value) - _REVIEW_FIELDS:
            raise _fail("GitHub review fields are unknown", surface=surface)
        review_id = _positive_int(value["id"], "GitHub review id is malformed")
        actor_id, login, actor_type = GitHubReviewReader._identity(
            value["user"], index
        )
        state = value["state"]
        commit_id = value["commit_id"]
        association = value["author_association"]
        if (
            state not in _STATES
            or not isinstance(commit_id, str)
            or _SHA.fullmatch(commit_id) is None
            or association not in _ASSOCIATIONS
        ):
            raise _fail("GitHub review state or binding is unknown", surface=surface)
        submitted_at = _timestamp(
            value["submitted_at"], "GitHub review submission time is malformed"
        )
        return {
            "id": review_id,
            "user": {"id": actor_id, "login": login, "type": actor_type},
            "state": state,
            "commit_id": commit_id,
            "submitted_at": submitted_at,
            "author_association": association,
            "dismissed": state == "DISMISSED",
        }

    @staticmethod
    def _permission(
        data: object, *, actor_id: int, login: str, index: int
    ) -> dict[str, object]:
        surface = f"reviews[{index}].repository-permission"
        if not isinstance(data, Mapping) or set(data) != {
            "permission", "role_name", "user",
        }:
            raise _fail(
                "GitHub repository permission fields are missing or unknown",
                surface=surface,
            )
        user = data["user"]
        role_name = data["role_name"]
        if (
            not isinstance(user, Mapping)
            or user.get("id") != actor_id
            or user.get("login") != login
            or data["permission"] not in _PERMISSIONS
            or (
                role_name is not None
                and (not isinstance(role_name, str) or not 1 <= len(role_name) <= 100)
            )
        ):
            raise _fail(
                "GitHub repository permission identity or level differs",
                surface=surface,
            )
        return {
            "permission": data["permission"],
            "user": {"id": actor_id, "login": login},
        }

    def read_all(
        self,
        *,
        repository: Mapping[str, object],
        pull_number: int,
    ) -> PageResponse:
        if set(repository) != {"owner", "name"}:
            raise ValueError("GitHub review repository is not closed")
        owner = repository["owner"]
        name = repository["name"]
        if (
            not isinstance(owner, str)
            or _OWNER.fullmatch(owner) is None
            or not isinstance(name, str)
            or _NAME.fullmatch(name) is None
            or not isinstance(pull_number, int)
            or isinstance(pull_number, bool)
            or pull_number < 1
        ):
            raise ValueError("GitHub review repository or pull number is malformed")
        escaped_owner = quote(owner, safe="")
        escaped_name = quote(name, safe="")
        page = self.client.get_pages(
            "reviews",
            f"/repos/{escaped_owner}/{escaped_name}/pulls/{pull_number}/reviews",
        )
        if not page.complete or page.truncated:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "reviews",
                "GitHub review pagination is incomplete",
            )

        reviews = []
        actor_indexes: dict[tuple[int, str], list[int]] = {}
        actor_ids: dict[int, str] = {}
        actor_logins: dict[str, int] = {}
        review_ids = set()
        for index, value in enumerate(page.items):
            review = self._review(value, index)
            review_id = review["id"]
            actor = review["user"]
            actor_id = actor["id"]
            login = actor["login"]
            if review_id in review_ids:
                raise _fail("GitHub review id is duplicated")
            if actor_id in actor_ids and actor_ids[actor_id] != login:
                raise _fail("GitHub review actor id maps to multiple logins")
            if login in actor_logins and actor_logins[login] != actor_id:
                raise _fail("GitHub review login maps to multiple actor ids")
            review_ids.add(review_id)
            actor_ids[actor_id] = login
            actor_logins[login] = actor_id
            actor_indexes.setdefault((actor_id, login), []).append(index)
            reviews.append(review)

        if page.pages + len(actor_indexes) > self.client.max_pages:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "reviews",
                "GitHub review and permission request ceiling would be exceeded",
            )

        audits = list(page.audits)
        for (actor_id, login), indexes in actor_indexes.items():
            target = (
                f"/repos/{escaped_owner}/{escaped_name}/collaborators/"
                f"{quote(login, safe='')}/permission"
            )
            response = self.client.get_qualified_repository_permission(
                "reviews", target
            )
            permission = self._permission(
                response.data, actor_id=actor_id, login=login, index=indexes[0]
            )
            if any(
                audit.request_id == response.audit.request_id for audit in audits
            ):
                raise _fail("GitHub review request id is duplicated")
            audits.append(response.audit)
            for index in indexes:
                reviews[index]["repository_permission"] = dict(permission)

        return PageResponse(
            tuple(reviews), page.pages, page.total_count, True, False,
            None, tuple(audits),
        )
