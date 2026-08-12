from __future__ import annotations

import hashlib
import http.client
import json
import re
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.client import HTTPException
from typing import Callable, Mapping, Protocol

from .github_evidence_credentials import GitHubEvidenceCredential
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)


OPERATION_NAME = "PathfinderPullRequestEvidence"
API_HOST = "api.github.com"
USER_AGENT = "pathfinder-github-graphql/1"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 30
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")

# This is the only GraphQL operation the transport can send. Keeping the query
# beside the fixed transport makes POST a mechanically read-only capability:
# callers provide variables, never operation text.
PULL_REQUEST_QUERY = """\
query PathfinderPullRequestEvidence(
  $owner: String!
  $name: String!
  $number: Int!
  $reviewsCursor: String
  $requestsCursor: String
  $threadsCursor: String
  $includeReviews: Boolean!
  $includeRequests: Boolean!
  $includeThreads: Boolean!
) {
  repository(owner: $owner, name: $name) {
    id
    databaseId
    name
    owner { login }
    pullRequest(number: $number) {
      id
      databaseId
      number
      state
      isDraft
      headRefName
      headRefOid
      headRepository { id databaseId nameWithOwner }
      baseRefName
      baseRefOid
      baseRepository { id databaseId nameWithOwner }
      mergeable
      mergeStateStatus
      reviewDecision
      mergeQueueEntry { id }
      latestOpinionatedReviews(first: 100, after: $reviewsCursor)
        @include(if: $includeReviews) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          state
          submittedAt
          authorAssociation
          commit { oid }
          author {
            __typename
            login
            ... on User { id databaseId }
            ... on Bot { id databaseId }
          }
        }
      }
      reviewRequests(first: 100, after: $requestsCursor)
        @include(if: $includeRequests) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          asCodeOwner
          requestedReviewer {
            __typename
            ... on User { id databaseId login }
            ... on Team { id databaseId slug }
          }
        }
      }
      reviewThreads(first: 100, after: $threadsCursor)
        @include(if: $includeThreads) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { id isResolved isOutdated }
      }
    }
  }
  rateLimit { cost remaining resetAt }
}
"""
PULL_REQUEST_QUERY_SHA256 = hashlib.sha256(PULL_REQUEST_QUERY.encode()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class RawGraphQLResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes = field(repr=False)


class PullRequestGraphQLTransport(Protocol):
    def execute_pull_request_evidence(
        self,
        variables: Mapping[str, object],
        headers: Mapping[str, str],
        *,
        timeout: float,
        max_bytes: int,
    ) -> RawGraphQLResponse: ...


class GitHubHTTPSPullRequestGraphQLTransport:
    """Fixed-host TLS transport for one compiled GraphQL query operation."""

    def execute_pull_request_evidence(
        self,
        variables: Mapping[str, object],
        headers: Mapping[str, str],
        *,
        timeout: float,
        max_bytes: int,
    ) -> RawGraphQLResponse:
        body = json.dumps(
            {
                "operationName": OPERATION_NAME,
                "query": PULL_REQUEST_QUERY,
                "variables": dict(variables),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        connection = http.client.HTTPSConnection(
            API_HOST, 443, timeout=timeout, context=ssl.create_default_context()
        )
        try:
            connection.request("POST", "/graphql", body=body, headers=dict(headers))
            response = connection.getresponse()
            response_body = response.read(max_bytes + 1)
            if len(response_body) > max_bytes:
                raise ValueError("GitHub GraphQL response exceeded the byte ceiling")
            return RawGraphQLResponse(
                response.status, dict(response.getheaders()), response_body
            )
        finally:
            connection.close()


@dataclass(frozen=True)
class GraphQLConnection:
    items: tuple[Mapping[str, object], ...]
    pages: int
    total_count: int
    complete: bool
    truncated: bool
    last_cursor: str | None


@dataclass(frozen=True)
class GraphQLPullRequestSnapshot:
    repository: Mapping[str, object]
    pull_request: Mapping[str, object]
    latest_reviews: GraphQLConnection
    review_requests: GraphQLConnection
    review_threads: GraphQLConnection
    requests: tuple[RequestAudit, ...]
    rate_limits: tuple[Mapping[str, object], ...]
    query_sha256: str = PULL_REQUEST_QUERY_SHA256


class GitHubGraphQLClient:
    """Read one exact PR through a compiled, query-only GraphQL boundary."""

    _CONNECTIONS = {
        "latest_reviews": "latestOpinionatedReviews",
        "review_requests": "reviewRequests",
        "review_threads": "reviewThreads",
    }

    def __init__(
        self,
        credential: GitHubEvidenceCredential,
        *,
        transport: PullRequestGraphQLTransport | None = None,
        timeout: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        max_pages: int = MAX_PAGES,
        max_retries: int = 1,
        clock: Callable[[], str] = _utc_now,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if credential.kind != "installation-token":
            raise ValueError("GitHub GraphQL evidence requires an installation token")
        if not 0.1 <= timeout <= 30:
            raise ValueError("GitHub GraphQL timeout must be between 0.1 and 30 seconds")
        if not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("GitHub GraphQL response ceiling is out of bounds")
        if not 1 <= max_pages <= MAX_PAGES or not 0 <= max_retries <= 1:
            raise ValueError("GitHub GraphQL page or retry ceiling is out of bounds")
        self.credential = credential
        self.transport = transport or GitHubHTTPSPullRequestGraphQLTransport()
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.clock = clock
        self.sleeper = sleeper

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": self.credential._authorization(),
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    @staticmethod
    def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}

    @staticmethod
    def _status_error(surface: str, status: int, headers: Mapping[str, str]):
        request_id = headers.get("x-github-request-id", "")
        safe_id = request_id if _REQUEST_ID.fullmatch(request_id) else "unavailable"
        detail = f"GitHub GraphQL failed with status {status}; request id {safe_id}"
        if status == 401:
            outcome = ObservationOutcome.AUTH_ERROR
        elif status == 429 or (
            status == 403
            and (
                "retry-after" in headers
                or headers.get("x-ratelimit-remaining") == "0"
            )
        ):
            outcome = ObservationOutcome.RATE_LIMITED
        elif status == 403:
            outcome = ObservationOutcome.PERMISSION_MISSING
        elif status == 404:
            outcome = ObservationOutcome.NOT_FOUND
        elif status == 410 or status >= 500:
            outcome = ObservationOutcome.API_UNAVAILABLE
        else:
            outcome = ObservationOutcome.MALFORMED_RESPONSE
        raise GitHubObservationError(outcome, surface, detail)

    def _execute(
        self, surface: str, variables: Mapping[str, object]
    ) -> tuple[Mapping[str, object], RequestAudit]:
        retries = 0
        while True:
            try:
                response = self.transport.execute_pull_request_evidence(
                    variables,
                    self._headers(),
                    timeout=self.timeout,
                    max_bytes=self.max_response_bytes,
                )
            except TimeoutError:
                if retries < self.max_retries:
                    retries += 1
                    self.sleeper(0.25)
                    continue
                raise GitHubObservationError(
                    ObservationOutcome.TIMEOUT, surface, "GitHub GraphQL timed out"
                ) from None
            except (OSError, HTTPException):
                if retries < self.max_retries:
                    retries += 1
                    self.sleeper(0.25)
                    continue
                raise GitHubObservationError(
                    ObservationOutcome.API_UNAVAILABLE,
                    surface,
                    "GitHub GraphQL transport unavailable",
                ) from None
            except ValueError:
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL response exceeded a safety bound",
                ) from None

            headers = self._lower_headers(response.headers)
            if response.status in {500, 502, 503, 504} and retries < self.max_retries:
                retries += 1
                self.sleeper(0.25)
                continue
            if response.status != 200:
                self._status_error(surface, response.status, headers)
            if len(response.body) > self.max_response_bytes:
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL response exceeded the byte ceiling",
                )
            request_id = headers.get("x-github-request-id")
            if not request_id or not _REQUEST_ID.fullmatch(request_id):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL response omitted its request id",
                )
            try:
                payload = json.loads(
                    response.body, object_pairs_hook=_reject_duplicate_keys
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL returned malformed JSON",
                ) from None
            if not isinstance(payload, Mapping):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL response is not an object",
                )
            if "errors" in payload:
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    surface,
                    "GitHub GraphQL returned errors or partial data",
                )
            if set(payload) != {"data"} or not isinstance(payload["data"], Mapping):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    surface,
                    "GitHub GraphQL response has an unknown envelope",
                )
            return payload["data"], RequestAudit(
                request_id, self.clock(), headers.get("etag")
            )

    @staticmethod
    def _expect_keys(value: object, expected: set[str], surface: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping) or set(value) != expected:
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN,
                surface,
                "GitHub GraphQL fields are missing or unknown",
            )
        return value

    @classmethod
    def _core(cls, data: Mapping[str, object]) -> tuple[dict, dict, Mapping[str, object]]:
        root = cls._expect_keys(data, {"repository", "rateLimit"}, "graphql")
        repository = cls._expect_keys(
            root["repository"],
            {"id", "databaseId", "name", "owner", "pullRequest"},
            "graphql.repository",
        )
        owner = cls._expect_keys(repository["owner"], {"login"}, "graphql.repository.owner")
        pull = repository["pullRequest"]
        core_fields = {
            "id", "databaseId", "number", "state", "isDraft",
            "headRefName", "headRefOid", "headRepository", "baseRefName",
            "baseRefOid", "baseRepository", "mergeable", "mergeStateStatus",
            "reviewDecision", "mergeQueueEntry",
        }
        connection_fields = set(cls._CONNECTIONS.values())
        if (
            not isinstance(pull, Mapping)
            or not core_fields <= set(pull)
            or set(pull) - core_fields - connection_fields
        ):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN,
                "graphql.pull-request",
                "GitHub GraphQL fields are missing or unknown",
            )
        for side in ("headRepository", "baseRepository"):
            side_repository = cls._expect_keys(
                pull[side], {"id", "databaseId", "nameWithOwner"},
                f"graphql.pull-request.{side}",
            )
            if (
                not isinstance(side_repository["id"], str)
                or not side_repository["id"]
                or not isinstance(side_repository["databaseId"], int)
                or isinstance(side_repository["databaseId"], bool)
                or side_repository["databaseId"] < 1
                or not isinstance(side_repository["nameWithOwner"], str)
                or not side_repository["nameWithOwner"]
            ):
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    f"graphql.pull-request.{side}",
                    "GitHub GraphQL repository identity is unknown",
                )
        if (
            not isinstance(repository["id"], str)
            or not repository["id"]
            or not isinstance(repository["databaseId"], int)
            or isinstance(repository["databaseId"], bool)
            or repository["databaseId"] < 1
            or not isinstance(owner["login"], str)
            or not isinstance(repository["name"], str)
            or not isinstance(pull["id"], str)
            or not pull["id"]
            or not isinstance(pull["databaseId"], int)
            or isinstance(pull["databaseId"], bool)
            or pull["databaseId"] < 1
            or not isinstance(pull["number"], int)
            or isinstance(pull["number"], bool)
            or pull["number"] < 1
            or pull["state"] not in {"OPEN", "CLOSED", "MERGED"}
            or not isinstance(pull["isDraft"], bool)
            or pull["mergeable"] not in {"MERGEABLE", "CONFLICTING", "UNKNOWN"}
            or pull["mergeStateStatus"] not in {
                "BEHIND", "BLOCKED", "CLEAN", "DIRTY", "DRAFT", "HAS_HOOKS",
                "UNKNOWN", "UNSTABLE",
            }
            or pull["reviewDecision"] not in {
                None, "APPROVED", "CHANGES_REQUESTED", "REVIEW_REQUIRED",
            }
            or (
                pull["mergeQueueEntry"] is not None
                and (
                    not isinstance(pull["mergeQueueEntry"], Mapping)
                    or set(pull["mergeQueueEntry"]) != {"id"}
                    or not isinstance(pull["mergeQueueEntry"]["id"], str)
                    or not pull["mergeQueueEntry"]["id"]
                )
            )
        ):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN,
                "graphql.pull-request",
                "GitHub GraphQL identity or enum is unknown",
            )
        for key in ("headRefName", "headRefOid", "baseRefName", "baseRefOid"):
            if not isinstance(pull[key], str) or not pull[key]:
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    "graphql.pull-request",
                    "GitHub GraphQL ref identity is missing",
                )
        normalized_repository = {
            "id": repository["databaseId"],
            "node_id": repository["id"],
            "owner": owner["login"],
            "name": repository["name"],
        }
        normalized_pull = {
            "id": pull["databaseId"],
            "node_id": pull["id"],
            "number": pull["number"],
            "state": str(pull["state"]).lower(),
            "draft": pull["isDraft"],
            "head_ref": pull["headRefName"],
            "head_sha": pull["headRefOid"],
            "head_repository_id": pull["headRepository"]["databaseId"],
            "head_repository_node_id": pull["headRepository"]["id"],
            "base_ref": pull["baseRefName"],
            "base_sha": pull["baseRefOid"],
            "base_repository_id": pull["baseRepository"]["databaseId"],
            "base_repository_node_id": pull["baseRepository"]["id"],
            "mergeable": pull["mergeable"],
            "merge_state_status": pull["mergeStateStatus"],
            "review_decision": pull["reviewDecision"],
            "merge_queue_entry": pull["mergeQueueEntry"] is not None,
        }
        return normalized_repository, normalized_pull, pull

    @classmethod
    def _connection(
        cls, raw: object, *, surface: str
    ) -> tuple[list[Mapping[str, object]], int, bool, str | None]:
        value = cls._expect_keys(raw, {"totalCount", "pageInfo", "nodes"}, surface)
        page_info = cls._expect_keys(
            value["pageInfo"], {"hasNextPage", "endCursor"}, f"{surface}.page-info"
        )
        nodes = value["nodes"]
        total = value["totalCount"]
        has_next = page_info["hasNextPage"]
        cursor = page_info["endCursor"]
        if (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < 0
            or not isinstance(nodes, list)
            or len(nodes) > 100
            or any(not isinstance(node, Mapping) for node in nodes)
            or not isinstance(has_next, bool)
            or (
                cursor is not None
                and (
                    not isinstance(cursor, str)
                    or not 1 <= len(cursor) <= 4096
                    or any(character in cursor for character in "\r\n\0")
                )
            )
            or (has_next and cursor is None)
        ):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                surface,
                "GitHub GraphQL connection is malformed",
            )
        return list(nodes), total, has_next, cursor

    @classmethod
    def _normalize_latest_review(cls, raw: Mapping[str, object], index: int) -> dict:
        surface = f"graphql.latest-reviews[{index}]"
        value = cls._expect_keys(
            raw,
            {"id", "databaseId", "state", "submittedAt", "authorAssociation", "commit", "author"},
            surface,
        )
        commit = cls._expect_keys(value["commit"], {"oid"}, f"{surface}.commit")
        author = value["author"]
        if author is None:
            raise GitHubObservationError(
                ObservationOutcome.ACTOR_IDENTITY_UNKNOWN, surface,
                "GitHub GraphQL review author is missing",
            )
        author = cls._expect_keys(author, {"__typename", "login", "id", "databaseId"}, f"{surface}.author")
        if (
            value["state"] not in {
                "APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING",
            }
            or author["__typename"] not in {"User", "Bot"}
            or not isinstance(author["databaseId"], int)
            or isinstance(author["databaseId"], bool)
            or author["databaseId"] < 1
            or not isinstance(value["databaseId"], int)
            or isinstance(value["databaseId"], bool)
            or value["databaseId"] < 1
            or not isinstance(value["id"], str)
            or not value["id"]
            or not isinstance(author["id"], str)
            or not author["id"]
            or not isinstance(author["login"], str)
            or not isinstance(commit["oid"], str)
            or not isinstance(value["submittedAt"], str)
            or not isinstance(value["authorAssociation"], str)
        ):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN, surface,
                "GitHub GraphQL review identity or enum is unknown",
            )
        return {
            "id": value["databaseId"],
            "node_id": value["id"],
            "state": value["state"],
            "submitted_at": value["submittedAt"],
            "commit_sha": commit["oid"],
            "author_association": value["authorAssociation"],
            "actor_id": author["databaseId"],
            "actor_node_id": author["id"],
            "actor_login": author["login"],
            "actor_type": author["__typename"],
        }

    @classmethod
    def _normalize_review_request(cls, raw: Mapping[str, object], index: int) -> dict:
        surface = f"graphql.review-requests[{index}]"
        value = cls._expect_keys(
            raw, {"id", "databaseId", "asCodeOwner", "requestedReviewer"}, surface
        )
        reviewer = value["requestedReviewer"]
        if not isinstance(reviewer, Mapping):
            raise GitHubObservationError(
                ObservationOutcome.ACTOR_IDENTITY_UNKNOWN, surface,
                "GitHub GraphQL requested reviewer is missing",
            )
        actor_type = reviewer.get("__typename")
        expected = {
            "User": {"__typename", "id", "databaseId", "login"},
            "Team": {"__typename", "id", "databaseId", "slug"},
        }.get(actor_type)
        if expected is None:
            raise GitHubObservationError(
                ObservationOutcome.ACTOR_IDENTITY_UNKNOWN, surface,
                "GitHub GraphQL requested reviewer type is unknown",
            )
        reviewer = cls._expect_keys(reviewer, expected, f"{surface}.reviewer")
        if (
            not isinstance(value["asCodeOwner"], bool)
            or not isinstance(value["databaseId"], int)
            or isinstance(value["databaseId"], bool)
            or value["databaseId"] < 1
            or not isinstance(value["id"], str)
            or not value["id"]
            or not isinstance(reviewer["databaseId"], int)
            or isinstance(reviewer["databaseId"], bool)
            or reviewer["databaseId"] < 1
        ):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN, surface,
                "GitHub GraphQL review request identity is unknown",
            )
        return {
            "id": value["databaseId"],
            "node_id": value["id"],
            "reviewer": {"id": reviewer["databaseId"], "type": actor_type},
            "as_code_owner": value["asCodeOwner"],
        }

    @classmethod
    def _normalize_review_thread(cls, raw: Mapping[str, object], index: int) -> dict:
        surface = f"graphql.review-threads[{index}]"
        value = cls._expect_keys(raw, {"id", "isResolved", "isOutdated"}, surface)
        if (
            not isinstance(value["id"], str)
            or not value["id"]
            or not isinstance(value["isResolved"], bool)
            or not isinstance(value["isOutdated"], bool)
        ):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN, surface,
                "GitHub GraphQL review thread is unknown",
            )
        return {
            "id": value["id"],
            "is_resolved": value["isResolved"],
            "is_outdated": value["isOutdated"],
        }

    def read_pull_request(self, *, owner: str, name: str, number: int) -> GraphQLPullRequestSnapshot:
        if (
            not isinstance(owner, str)
            or not _NAME.fullmatch(owner)
            or not isinstance(name, str)
            or not _NAME.fullmatch(name)
            or not isinstance(number, int)
            or isinstance(number, bool)
            or number < 1
        ):
            raise ValueError("invalid exact GitHub GraphQL pull request identity")

        cursors = {key: None for key in self._CONNECTIONS}
        active = {key: True for key in self._CONNECTIONS}
        items: dict[str, list[Mapping[str, object]]] = {
            key: [] for key in self._CONNECTIONS
        }
        totals: dict[str, int | None] = {key: None for key in self._CONNECTIONS}
        pages = {key: 0 for key in self._CONNECTIONS}
        seen_cursors: dict[str, set[str]] = {
            key: set() for key in self._CONNECTIONS
        }
        audits: list[RequestAudit] = []
        rate_limits: list[Mapping[str, object]] = []
        stable_repository = stable_pull = None

        for _request_number in range(1, self.max_pages + 1):
            variables = {
                "owner": owner,
                "name": name,
                "number": number,
                "reviewsCursor": cursors["latest_reviews"],
                "requestsCursor": cursors["review_requests"],
                "threadsCursor": cursors["review_threads"],
                "includeReviews": active["latest_reviews"],
                "includeRequests": active["review_requests"],
                "includeThreads": active["review_threads"],
            }
            data, audit = self._execute("graphql-pull-request", variables)
            if any(existing.request_id == audit.request_id for existing in audits):
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    "graphql-pull-request",
                    "GitHub GraphQL request id was reused during pagination",
                )
            audits.append(audit)
            repository, pull_request, raw_pull = self._core(data)
            rate = self._expect_keys(
                data["rateLimit"], {"cost", "remaining", "resetAt"},
                "graphql.rate-limit",
            )
            if (
                not isinstance(rate["cost"], int)
                or isinstance(rate["cost"], bool)
                or rate["cost"] < 0
                or not isinstance(rate["remaining"], int)
                or isinstance(rate["remaining"], bool)
                or rate["remaining"] < 0
                or not isinstance(rate["resetAt"], str)
            ):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    "graphql.rate-limit",
                    "GitHub GraphQL rate-limit evidence is malformed",
                )
            rate_limits.append(dict(rate))
            if repository["owner"] != owner or repository["name"] != name or pull_request["number"] != number:
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    "graphql.pull-request",
                    "GitHub GraphQL returned a different pull request",
                )
            if stable_repository is None:
                stable_repository, stable_pull = repository, pull_request
            elif repository != stable_repository or pull_request != stable_pull:
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    "graphql.pull-request",
                    "GitHub GraphQL pull request changed during pagination",
                )

            normalizers = {
                "latest_reviews": self._normalize_latest_review,
                "review_requests": self._normalize_review_request,
                "review_threads": self._normalize_review_thread,
            }
            for key, field_name in self._CONNECTIONS.items():
                if not active[key]:
                    if field_name in raw_pull:
                        raise GitHubObservationError(
                            ObservationOutcome.FIELD_UNKNOWN,
                            f"graphql.{key.replace('_', '-')}",
                            "GitHub GraphQL returned an excluded connection",
                        )
                    continue
                page_items, total, has_next, cursor = self._connection(
                    raw_pull[field_name], surface=f"graphql.{key.replace('_', '-')}"
                )
                if totals[key] is None:
                    totals[key] = total
                elif totals[key] != total:
                    raise GitHubObservationError(
                        ObservationOutcome.FIELD_UNKNOWN,
                        f"graphql.{key.replace('_', '-')}",
                        "GitHub GraphQL total count changed during pagination",
                    )
                offset = len(items[key])
                normalized = [
                    normalizers[key](node, offset + index)
                    for index, node in enumerate(page_items)
                ]
                identities = {
                    (item.get("node_id"), item.get("id")) for item in items[key]
                }
                new_identities = [
                    (item.get("node_id"), item.get("id")) for item in normalized
                ]
                if any(
                    identity in identities for identity in new_identities
                ) or len(set(new_identities)) != len(new_identities):
                    raise GitHubObservationError(
                        ObservationOutcome.FIELD_UNKNOWN,
                        f"graphql.{key.replace('_', '-')}",
                        "GitHub GraphQL pagination repeated an item",
                    )
                items[key].extend(normalized)
                pages[key] += 1
                if has_next and cursor in seen_cursors[key]:
                    raise GitHubObservationError(
                        ObservationOutcome.PAGINATION_INCOMPLETE,
                        f"graphql.{key.replace('_', '-')}",
                        "GitHub GraphQL pagination cursor did not advance",
                    )
                cursors[key] = cursor
                if cursor is not None:
                    seen_cursors[key].add(cursor)
                active[key] = has_next
                if not has_next and totals[key] != len(items[key]):
                    raise GitHubObservationError(
                        ObservationOutcome.PAGINATION_INCOMPLETE,
                        f"graphql.{key.replace('_', '-')}",
                        "GitHub GraphQL connection count is incomplete",
                    )
            if not any(active.values()):
                break

        connections = {}
        for key in self._CONNECTIONS:
            complete = not active[key] and totals[key] == len(items[key])
            connections[key] = GraphQLConnection(
                tuple(items[key]),
                pages[key],
                totals[key] if totals[key] is not None else len(items[key]),
                complete,
                not complete,
                cursors[key] if not complete else None,
            )
        assert stable_repository is not None and stable_pull is not None
        return GraphQLPullRequestSnapshot(
            stable_repository,
            stable_pull,
            connections["latest_reviews"],
            connections["review_requests"],
            connections["review_threads"],
            tuple(audits),
            tuple(rate_limits),
        )
