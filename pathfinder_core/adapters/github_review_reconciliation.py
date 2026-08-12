from __future__ import annotations

import re
from datetime import datetime
from typing import Mapping

from .github_graphql import (
    PULL_REQUEST_QUERY_SHA256,
    GraphQLPullRequestSnapshot,
)
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)


_OPINIONATED = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
_REST_FIELDS = {
    "id", "node_id", "user", "repository_permission", "state", "commit_id",
    "submitted_at", "author_association", "dismissed",
}
_REST_USER_FIELDS = {"id", "node_id", "login", "type"}
_GRAPHQL_FIELDS = {
    "id", "node_id", "state", "submitted_at", "commit_sha",
    "author_association", "actor_id", "actor_node_id", "actor_login",
    "actor_type",
}
_SHA = re.compile(r"[0-9a-f]{40}")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?")
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_ASSOCIATIONS = {
    "OWNER", "MEMBER", "COLLABORATOR", "CONTRIBUTOR", "FIRST_TIMER",
    "FIRST_TIME_CONTRIBUTOR", "NONE",
}
_PERMISSIONS = {"admin", "maintain", "write", "triage", "read", "none"}


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _time(value: object, surface: str) -> datetime:
    if not isinstance(value, str):
        raise _fail(surface, "review submission time is malformed")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(surface, "review submission time is malformed") from None
    if parsed.utcoffset() is None:
        raise _fail(surface, "review submission time has no UTC offset")
    return parsed


class GitHubReviewReconciler:
    """Cross-check REST review history against GraphQL latest-per-user reviews."""

    @staticmethod
    def _rest(page: PageResponse) -> tuple[dict[int, dict], set[str]]:
        if (
            not page.complete
            or page.truncated
            or page.last_cursor is not None
            or page.pages < 1
            or page.total_count != len(page.items)
            or len(page.audits) < page.pages
        ):
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "reviews",
                "REST review history is incomplete",
            )
        request_ids = [audit.request_id for audit in page.audits]
        if (
            any(
                not isinstance(request_id, str)
                or _REQUEST_ID.fullmatch(request_id) is None
                for request_id in request_ids
            )
            or len(request_ids) != len(set(request_ids))
        ):
            raise _fail("reviews", "REST review request id is duplicated")
        latest: dict[int, dict] = {}
        seen_reviews = set()
        seen_review_nodes = set()
        seen_actors: dict[int, tuple[str, str, str]] = {}
        previous_time = None
        for index, value in enumerate(page.items):
            surface = f"reviews[{index}]"
            if not isinstance(value, Mapping) or set(value) != _REST_FIELDS:
                raise _fail(surface, "REST review fields are missing or unknown")
            user = value["user"]
            if not isinstance(user, Mapping) or set(user) != _REST_USER_FIELDS:
                raise _fail(surface, "REST review actor fields are missing or unknown")
            permission = value["repository_permission"]
            if (
                not isinstance(permission, Mapping)
                or set(permission) != {"permission", "user"}
                or not isinstance(permission["user"], Mapping)
                or set(permission["user"]) != {"id", "login"}
            ):
                raise _fail(surface, "REST reviewer permission is not closed")
            review_id = value["id"]
            actor_id = user["id"]
            if (
                not isinstance(review_id, int)
                or isinstance(review_id, bool)
                or review_id < 1
                or not isinstance(actor_id, int)
                or isinstance(actor_id, bool)
                or actor_id < 1
                or not isinstance(value["node_id"], str)
                or not value["node_id"]
                or not isinstance(user["node_id"], str)
                or not user["node_id"]
                or not isinstance(user["login"], str)
                or _LOGIN.fullmatch(user["login"]) is None
                or user["type"] not in {"User", "Bot"}
                or (user["type"] == "Bot") != user["login"].endswith("[bot]")
                or value["state"] not in {
                    "APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED",
                }
                or value["dismissed"] != (value["state"] == "DISMISSED")
                or not isinstance(value["commit_id"], str)
                or _SHA.fullmatch(value["commit_id"]) is None
                or value["author_association"] not in _ASSOCIATIONS
                or permission["permission"] not in _PERMISSIONS
                or permission["user"]["id"] != actor_id
                or permission["user"]["login"] != user["login"]
            ):
                raise _fail(surface, "REST review identity or state is malformed")
            submitted = _time(value["submitted_at"], surface)
            if previous_time is not None and submitted < previous_time:
                raise _fail("reviews", "REST review history is not chronological")
            previous_time = submitted
            if review_id in seen_reviews or value["node_id"] in seen_review_nodes:
                raise _fail("reviews", "REST review identity is duplicated")
            seen_reviews.add(review_id)
            seen_review_nodes.add(value["node_id"])
            actor = (user["node_id"], user["login"], user["type"])
            if actor_id in seen_actors and seen_actors[actor_id] != actor:
                raise _fail("reviews", "REST review actor identity drifted")
            seen_actors[actor_id] = actor
            if value["state"] in _OPINIONATED:
                latest[actor_id] = dict(value)
        return latest, set(request_ids)

    @staticmethod
    def _graphql(
        snapshot: GraphQLPullRequestSnapshot,
    ) -> tuple[dict[int, dict], set[str]]:
        connection = snapshot.latest_reviews
        if (
            snapshot.query_sha256 != PULL_REQUEST_QUERY_SHA256
            or not connection.complete
            or connection.truncated
            or connection.last_cursor is not None
            or connection.pages < 1
            or connection.total_count != len(connection.items)
        ):
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "graphql.latest-reviews",
                "GraphQL latest-review view is incomplete or unbound",
            )
        request_ids = [audit.request_id for audit in snapshot.requests]
        if (
            not request_ids
            or any(
                not isinstance(request_id, str)
                or _REQUEST_ID.fullmatch(request_id) is None
                for request_id in request_ids
            )
            or len(request_ids) != len(set(request_ids))
        ):
            raise _fail(
                "graphql.latest-reviews", "GraphQL review request id is ambiguous"
            )
        latest = {}
        seen_reviews = set()
        seen_review_nodes = set()
        seen_actor_nodes = set()
        for index, value in enumerate(connection.items):
            surface = f"graphql.latest-reviews[{index}]"
            if not isinstance(value, Mapping) or set(value) != _GRAPHQL_FIELDS:
                raise _fail(surface, "GraphQL review fields are missing or unknown")
            actor_id = value["actor_id"]
            review_id = value["id"]
            if (
                not isinstance(actor_id, int)
                or isinstance(actor_id, bool)
                or actor_id < 1
                or not isinstance(review_id, int)
                or isinstance(review_id, bool)
                or review_id < 1
                or value["state"] not in _OPINIONATED
                or not isinstance(value["node_id"], str)
                or not value["node_id"]
                or not isinstance(value["actor_node_id"], str)
                or not value["actor_node_id"]
                or not isinstance(value["actor_login"], str)
                or _LOGIN.fullmatch(value["actor_login"]) is None
                or value["actor_type"] not in {"User", "Bot"}
                or (value["actor_type"] == "Bot")
                != value["actor_login"].endswith("[bot]")
                or not isinstance(value["commit_sha"], str)
                or _SHA.fullmatch(value["commit_sha"]) is None
                or value["author_association"] not in _ASSOCIATIONS
            ):
                raise _fail(surface, "GraphQL review identity or state is malformed")
            _time(value["submitted_at"], surface)
            if (
                actor_id in latest
                or review_id in seen_reviews
                or value["node_id"] in seen_review_nodes
                or value["actor_node_id"] in seen_actor_nodes
            ):
                raise _fail(
                    "graphql.latest-reviews",
                    "GraphQL latest-review identity is duplicated",
                )
            latest[actor_id] = dict(value)
            seen_reviews.add(review_id)
            seen_review_nodes.add(value["node_id"])
            seen_actor_nodes.add(value["actor_node_id"])
        return latest, set(request_ids)

    @classmethod
    def reconcile(
        cls,
        *,
        rest_reviews: PageResponse,
        graphql: GraphQLPullRequestSnapshot,
    ) -> tuple[int, ...]:
        rest, rest_requests = cls._rest(rest_reviews)
        graph, graph_requests = cls._graphql(graphql)
        if rest_requests & graph_requests:
            raise _fail("reviews", "REST and GraphQL reused a request id")
        if set(rest) != set(graph):
            raise _fail(
                "reviews", "REST and GraphQL latest-review actor sets differ"
            )
        matched = []
        for actor_id in sorted(rest):
            left = rest[actor_id]
            user = left["user"]
            right = graph[actor_id]
            if (
                left["id"] != right["id"]
                or left["node_id"] != right["node_id"]
                or left["state"] != right["state"]
                or left["commit_id"] != right["commit_sha"]
                or left["author_association"] != right["author_association"]
                or user["id"] != right["actor_id"]
                or user["node_id"] != right["actor_node_id"]
                or user["login"] != right["actor_login"]
                or user["type"] != right["actor_type"]
                or _time(left["submitted_at"], "reviews")
                != _time(right["submitted_at"], "graphql.latest-reviews")
            ):
                raise _fail(
                    f"reviews.{actor_id}",
                    "REST and GraphQL latest-review records differ",
                )
            matched.append(left["id"])
        return tuple(matched)
