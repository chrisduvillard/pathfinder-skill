from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from .github_graphql import (
    PULL_REQUEST_QUERY_SHA256,
    GraphQLConnection,
    GraphQLPullRequestSnapshot,
)
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)
from .github_publication_reconciliation import ControllerPusherProof


_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_NODE_ID = re.compile(r"[A-Za-z0-9_-]{4,128}={0,2}")
_REQUEST_FIELDS = {"id", "node_id", "reviewer", "as_code_owner"}
_THREAD_FIELDS = {"id", "is_resolved", "is_outdated"}
_PULL_FIELDS = {
    "id", "node_id", "number", "state", "draft", "head_ref", "head_sha",
    "head_repository_id", "head_repository_node_id", "base_ref", "base_sha",
    "base_repository_id", "base_repository_node_id", "mergeable",
    "merge_state_status", "review_decision", "merge_queue_entry",
}


def _fail(detail: str) -> GitHubObservationError:
    return GitHubObservationError(
        ObservationOutcome.FIELD_UNKNOWN,
        "graphql-pull-request",
        detail,
    )


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise _fail("GraphQL observation time is malformed")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail("GraphQL observation time is malformed") from None
    if parsed.utcoffset() is None:
        raise _fail("GraphQL observation time has no UTC offset")
    return parsed


@dataclass(frozen=True)
class GraphQLPullRequestProjection:
    query_sha256: str
    pull_request: Mapping[str, object]
    mergeability: Mapping[str, object]
    review_requests: tuple[Mapping[str, object], ...]
    review_threads: tuple[Mapping[str, object], ...]
    pagination: Mapping[str, Mapping[str, object]]
    audits: tuple[Mapping[str, object], ...]


class GitHubGraphQLProjector:
    """Project one complete exact GraphQL PR snapshot into evidence inputs."""

    @staticmethod
    def _connection(connection: object, surface: str) -> GraphQLConnection:
        if (
            not isinstance(connection, GraphQLConnection)
            or not connection.complete
            or connection.truncated
            or connection.last_cursor is not None
            or connection.pages < 1
            or connection.total_count != len(connection.items)
        ):
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                surface,
                "GraphQL connection is incomplete",
            )
        return connection

    @staticmethod
    def _audits(snapshot: GraphQLPullRequestSnapshot) -> tuple[dict, ...]:
        if not snapshot.requests or len(snapshot.rate_limits) != len(
            snapshot.requests
        ):
            raise _fail("GraphQL request or rate-limit audit coverage differs")
        result = []
        identities = set()
        previous = None
        for audit, rate in zip(snapshot.requests, snapshot.rate_limits):
            if (
                not isinstance(audit, RequestAudit)
                or not isinstance(audit.request_id, str)
                or _REQUEST_ID.fullmatch(audit.request_id) is None
                or audit.request_id in identities
                or (
                    audit.etag is not None
                    and (
                        not isinstance(audit.etag, str)
                        or not 1 <= len(audit.etag) <= 512
                    )
                )
                or audit.target is not None
                or audit.status is not None
                or audit.permission_qualified is not None
                or not isinstance(rate, Mapping)
                or set(rate) != {"cost", "remaining", "resetAt"}
                or not isinstance(rate["cost"], int)
                or isinstance(rate["cost"], bool)
                or rate["cost"] < 0
                or not isinstance(rate["remaining"], int)
                or isinstance(rate["remaining"], bool)
                or rate["remaining"] < 0
            ):
                raise _fail("GraphQL request or rate-limit audit is malformed")
            observed = _time(audit.observed_at)
            _time(rate["resetAt"])
            if previous is not None and observed < previous:
                raise _fail("GraphQL request audit timeline is not ordered")
            previous = observed
            identities.add(audit.request_id)
            result.append({
                "surface": "graphql-pull-request",
                "request_id": audit.request_id,
                "etag": audit.etag,
                "observed_at": audit.observed_at,
            })
        return tuple(result)

    @staticmethod
    def _review_requests(connection: GraphQLConnection) -> tuple[dict, ...]:
        result = []
        request_ids = set()
        request_nodes = set()
        reviewers = set()
        for item in connection.items:
            if not isinstance(item, Mapping) or set(item) != _REQUEST_FIELDS:
                raise _fail("GraphQL review-request fields are missing or unknown")
            reviewer = item["reviewer"]
            if (
                not isinstance(reviewer, Mapping)
                or set(reviewer) != {"id", "type"}
                or not isinstance(item["id"], int)
                or isinstance(item["id"], bool)
                or item["id"] < 1
                or not isinstance(item["node_id"], str)
                or _NODE_ID.fullmatch(item["node_id"]) is None
                or not isinstance(reviewer["id"], int)
                or isinstance(reviewer["id"], bool)
                or reviewer["id"] < 1
                or reviewer["type"] not in {"User", "Team"}
                or not isinstance(item["as_code_owner"], bool)
            ):
                raise _fail("GraphQL review-request identity is malformed")
            identity = (reviewer["type"], reviewer["id"])
            if (
                item["id"] in request_ids
                or item["node_id"] in request_nodes
                or identity in reviewers
            ):
                raise _fail("GraphQL review-request identity is duplicated")
            request_ids.add(item["id"])
            request_nodes.add(item["node_id"])
            reviewers.add(identity)
            result.append({
                "actor_id": reviewer["id"],
                "actor_type": reviewer["type"],
                "as_code_owner": item["as_code_owner"],
            })
        return tuple(sorted(
            result,
            key=lambda value: (value["actor_type"], value["actor_id"]),
        ))

    @staticmethod
    def _review_threads(connection: GraphQLConnection) -> tuple[dict, ...]:
        result = []
        identities = set()
        for item in connection.items:
            if (
                not isinstance(item, Mapping)
                or set(item) != _THREAD_FIELDS
                or not isinstance(item["id"], str)
                or _NODE_ID.fullmatch(item["id"]) is None
                or item["id"] in identities
                or not isinstance(item["is_resolved"], bool)
                or not isinstance(item["is_outdated"], bool)
            ):
                raise _fail("GraphQL review-thread identity is malformed or duplicated")
            identities.add(item["id"])
            result.append({
                "node_id": item["id"],
                "resolved": item["is_resolved"],
                "outdated": item["is_outdated"],
            })
        return tuple(sorted(result, key=lambda value: value["node_id"]))

    @classmethod
    def project(
        cls,
        *,
        graphql: GraphQLPullRequestSnapshot,
        controller_pusher: ControllerPusherProof,
    ) -> GraphQLPullRequestProjection:
        if (
            not isinstance(graphql, GraphQLPullRequestSnapshot)
            or not isinstance(controller_pusher, ControllerPusherProof)
            or graphql.query_sha256 != PULL_REQUEST_QUERY_SHA256
            or not isinstance(graphql.repository, Mapping)
            or not isinstance(graphql.pull_request, Mapping)
        ):
            raise _fail("GraphQL snapshot or controller pusher proof is malformed")
        repository = graphql.repository
        pull = graphql.pull_request
        if (
            set(pull) != _PULL_FIELDS
            or pull.get("state") not in {"open", "closed", "merged"}
            or not isinstance(pull.get("draft"), bool)
            or pull.get("mergeable")
            not in {"MERGEABLE", "CONFLICTING", "UNKNOWN"}
            or pull.get("merge_state_status")
            not in {
                "BEHIND", "BLOCKED", "CLEAN", "DIRTY", "DRAFT",
                "HAS_HOOKS", "UNKNOWN", "UNSTABLE",
            }
            or pull.get("review_decision")
            not in {None, "APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED"}
            or not isinstance(pull.get("merge_queue_entry"), bool)
        ):
            raise _fail("GraphQL pull request fields or states are unknown")
        expected_repository = {
            "id": controller_pusher.repository_id,
            "node_id": controller_pusher.repository_node_id,
            "owner": controller_pusher.repository_owner,
            "name": controller_pusher.repository_name,
        }
        expected_pull = {
            "id": controller_pusher.pull_request_id,
            "node_id": controller_pusher.pull_request_node_id,
            "number": controller_pusher.pull_request_number,
            "head_repository_id": controller_pusher.repository_id,
            "head_repository_node_id": controller_pusher.repository_node_id,
            "head_ref": controller_pusher.head_ref,
            "head_sha": controller_pusher.head_sha,
            "base_repository_id": controller_pusher.repository_id,
            "base_repository_node_id": controller_pusher.repository_node_id,
            "base_ref": controller_pusher.base_ref,
            "base_sha": controller_pusher.base_sha,
        }
        if dict(repository) != expected_repository or any(
            pull.get(key) != value for key, value in expected_pull.items()
        ):
            raise _fail("GraphQL and controller publication identities differ")

        latest = cls._connection(graphql.latest_reviews, "graphql.latest-reviews")
        requests = cls._connection(
            graphql.review_requests, "graphql.review-requests"
        )
        threads = cls._connection(graphql.review_threads, "graphql.review-threads")
        audits = cls._audits(graphql)
        if (
            max(latest.pages, requests.pages, threads.pages) > len(audits)
            or audits[-1]["observed_at"]
            != controller_pusher.graphql_observed_at
        ):
            raise _fail("GraphQL connection and publication audit bindings differ")

        review_requests = cls._review_requests(requests)
        review_threads = cls._review_threads(threads)
        pagination = {
            "latest_reviews": {
                "complete": True,
                "pages": latest.pages,
                "items": len(latest.items),
                "truncated": False,
                "last_cursor": None,
            },
            "review_requests": {
                "complete": True,
                "pages": requests.pages,
                "items": len(requests.items),
                "truncated": False,
                "last_cursor": None,
            },
            "review_threads": {
                "complete": True,
                "pages": threads.pages,
                "items": len(threads.items),
                "truncated": False,
                "last_cursor": None,
            },
        }
        mergeability = {
            "mergeable": pull["mergeable"],
            "merge_state_status": pull["merge_state_status"],
            "review_decision": pull["review_decision"] or "UNKNOWN",
            "queue_entry": pull["merge_queue_entry"],
            "required_sha": pull["head_sha"],
        }
        return GraphQLPullRequestProjection(
            PULL_REQUEST_QUERY_SHA256,
            dict(pull),
            mergeability,
            review_requests,
            review_threads,
            pagination,
            audits,
        )
