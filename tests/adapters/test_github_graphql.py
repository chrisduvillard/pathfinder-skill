import copy
import hashlib
import inspect
import json
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
)
from pathfinder_core.adapters.github_graphql import (
    MAX_PAGES,
    OPERATION_NAME,
    PULL_REQUEST_QUERY,
    PULL_REQUEST_QUERY_SHA256,
    GitHubGraphQLClient,
    GitHubHTTPSPullRequestGraphQLTransport,
    PullRequestGraphQLTransport,
    RawGraphQLResponse,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
)


TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
NOW = "2026-08-12T10:00:00+00:00"
ROOT = Path(__file__).resolve().parents[2]


def credential(kind="installation-token"):
    permissions = (
        {name: "read" for name in REQUIRED_READ_PERMISSIONS}
        if kind == "installation-token"
        else {}
    )
    return GitHubEvidenceCredential(
        TOKEN,
        kind=kind,
        permissions=permissions,
        boundary=EVIDENCE_BOUNDARY,
    )


def page(nodes=(), *, total=None, has_next=False, cursor=None):
    return {
        "totalCount": len(nodes) if total is None else total,
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": list(nodes),
    }


def review(database_id=91):
    return {
        "id": f"PRR_{database_id}",
        "databaseId": database_id,
        "state": "APPROVED",
        "submittedAt": "2026-08-12T09:59:00+00:00",
        "authorAssociation": "MEMBER",
        "commit": {"oid": "c" * 40},
        "author": {
            "__typename": "User",
            "id": "U_reviewer",
            "databaseId": 44,
            "login": "reviewer",
        },
    }


def review_request(database_id=92):
    return {
        "id": f"PRRQ_{database_id}",
        "databaseId": database_id,
        "asCodeOwner": True,
        "requestedReviewer": {
            "__typename": "Team",
            "id": "T_reviewers",
            "databaseId": 45,
            "slug": "reviewers",
        },
    }


def thread(node_id="PRRT_1"):
    return {"id": node_id, "isResolved": True, "isOutdated": False}


def data(
    *,
    reviews=None,
    requests=None,
    threads=None,
    state="OPEN",
    review_decision="APPROVED",
):
    pull_request = {
        "id": "PR_node",
        "databaseId": 72,
        "number": 7,
        "state": state,
        "isDraft": False,
        "headRefName": "pathfinder/auto/example",
        "headRefOid": "c" * 40,
        "headRepository": {
            "id": "R_node", "databaseId": 123, "nameWithOwner": "owner/repo",
        },
        "baseRefName": "main",
        "baseRefOid": "b" * 40,
        "baseRepository": {
            "id": "R_node", "databaseId": 123, "nameWithOwner": "owner/repo",
        },
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "reviewDecision": review_decision,
        "mergeQueueEntry": None,
    }
    if reviews is not None:
        pull_request["latestOpinionatedReviews"] = reviews
    if requests is not None:
        pull_request["reviewRequests"] = requests
    if threads is not None:
        pull_request["reviewThreads"] = threads
    return {
        "repository": {
            "id": "R_node",
            "databaseId": 123,
            "name": "repo",
            "owner": {"login": "owner"},
            "pullRequest": pull_request,
        },
        "rateLimit": {
            "cost": 1,
            "remaining": 4999,
            "resetAt": "2026-08-12T11:00:00+00:00",
        },
    }


def response(payload=None, *, status=200, request_id="graphql-request-1", body=None):
    headers = {"X-GitHub-Request-Id": request_id}
    encoded = json.dumps({"data": payload}).encode()
    return RawGraphQLResponse(status, headers, encoded if body is None else body)


class FixtureTransport:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def execute_pull_request_evidence(
        self, variables, headers, *, timeout, max_bytes
    ):
        self.calls.append({
            "variables": dict(variables),
            "headers": dict(headers),
            "timeout": timeout,
            "max_bytes": max_bytes,
        })
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def client(transport, **overrides):
    return GitHubGraphQLClient(
        credential(),
        transport=transport,
        clock=lambda: NOW,
        sleeper=lambda _seconds: None,
        **overrides,
    )


class GitHubGraphQLClientTests(unittest.TestCase):
    def complete_response(self, **overrides):
        return response(data(
            reviews=page([review()]),
            requests=page([review_request()]),
            threads=page([thread()]),
            **overrides,
        ))

    def test_query_is_compiled_read_only_and_hash_bound(self):
        self.assertTrue(PULL_REQUEST_QUERY.lstrip().startswith("query "))
        self.assertNotIn("mutation ", PULL_REQUEST_QUERY.lower())
        self.assertEqual(
            PULL_REQUEST_QUERY_SHA256,
            hashlib.sha256(PULL_REQUEST_QUERY.encode()).hexdigest(),
        )
        evidence_schema = json.loads(
            (
                ROOT
                / "schemas"
                / "publication"
                / "merge-evidence.schema.json"
            ).read_text()
        )
        self.assertEqual(
            evidence_schema["properties"]["observation"]["properties"][
                "graphql_query_sha256"
            ],
            {"const": PULL_REQUEST_QUERY_SHA256},
        )
        self.assertIn(OPERATION_NAME, PULL_REQUEST_QUERY)
        methods = {
            name for name, value in PullRequestGraphQLTransport.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(methods, {"execute_pull_request_evidence"})
        source = inspect.getsource(GitHubHTTPSPullRequestGraphQLTransport)
        self.assertIn('connection.request("POST", "/graphql"', source)
        self.assertIn("PULL_REQUEST_QUERY", source)
        for forbidden in ('"PUT"', '"PATCH"', '"DELETE"'):
            self.assertNotIn(forbidden, source)

    def test_concrete_transport_sends_only_the_compiled_operation(self):
        class HTTPResponse:
            status = 200

            @staticmethod
            def read(_limit):
                return b'{"data":{}}'

            @staticmethod
            def getheaders():
                return [("X-GitHub-Request-Id", "request-1")]

        class Connection:
            instance = None

            def __init__(self, *args, **kwargs):
                self.request_call = None
                Connection.instance = self

            def request(self, *args, **kwargs):
                self.request_call = (args, kwargs)

            @staticmethod
            def getresponse():
                return HTTPResponse()

            @staticmethod
            def close():
                return None

        transport = GitHubHTTPSPullRequestGraphQLTransport()
        with mock.patch(
            "pathfinder_core.adapters.github_graphql.http.client.HTTPSConnection",
            Connection,
        ):
            transport.execute_pull_request_evidence(
                {"owner": "owner", "number": 7},
                {"Authorization": "redacted"},
                timeout=1,
                max_bytes=1024,
            )
        args, kwargs = Connection.instance.request_call
        self.assertEqual(args[:2], ("POST", "/graphql"))
        payload = json.loads(kwargs["body"])
        self.assertEqual(payload["operationName"], OPERATION_NAME)
        self.assertEqual(payload["query"], PULL_REQUEST_QUERY)
        self.assertEqual(payload["variables"], {"owner": "owner", "number": 7})

    def test_complete_snapshot_normalizes_exact_identity_and_connections(self):
        transport = FixtureTransport(self.complete_response())
        snapshot = client(transport).read_pull_request(
            owner="owner", name="repo", number=7
        )
        self.assertEqual(snapshot.repository, {
            "id": 123, "node_id": "R_node", "owner": "owner", "name": "repo",
        })
        self.assertEqual(snapshot.pull_request["head_sha"], "c" * 40)
        self.assertEqual(snapshot.pull_request["base_sha"], "b" * 40)
        self.assertEqual(snapshot.pull_request["review_decision"], "APPROVED")
        self.assertFalse(snapshot.pull_request["merge_queue_entry"])
        self.assertEqual(snapshot.latest_reviews.items[0]["actor_id"], 44)
        self.assertEqual(
            snapshot.review_requests.items[0]["reviewer"],
            {"id": 45, "type": "Team"},
        )
        self.assertTrue(snapshot.review_requests.items[0]["as_code_owner"])
        self.assertTrue(snapshot.review_threads.items[0]["is_resolved"])
        self.assertTrue(snapshot.latest_reviews.complete)
        self.assertEqual(snapshot.requests[0].request_id, "graphql-request-1")
        self.assertEqual(snapshot.query_sha256, PULL_REQUEST_QUERY_SHA256)
        call = transport.calls[0]
        self.assertEqual(call["variables"]["owner"], "owner")
        self.assertEqual(call["variables"]["number"], 7)
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {TOKEN}")
        self.assertEqual(call["headers"]["Content-Type"], "application/json")
        self.assertNotIn(TOKEN, repr(snapshot))

    def test_connections_paginate_independently_without_refetching_finished_pages(self):
        first = response(data(
            reviews=page([review(91)], total=2, has_next=True, cursor="reviews-1"),
            requests=page([], total=0),
            threads=page([thread()], total=1),
        ))
        second = response(
            data(reviews=page([review(93)], total=2)),
            request_id="graphql-request-2",
        )
        transport = FixtureTransport(first, second)
        snapshot = client(transport).read_pull_request(
            owner="owner", name="repo", number=7
        )
        self.assertEqual(len(snapshot.latest_reviews.items), 2)
        self.assertEqual(snapshot.latest_reviews.pages, 2)
        self.assertEqual(snapshot.review_requests.pages, 1)
        self.assertEqual(snapshot.review_threads.pages, 1)
        self.assertEqual(len(snapshot.requests), 2)
        variables = transport.calls[1]["variables"]
        self.assertEqual(variables["reviewsCursor"], "reviews-1")
        self.assertTrue(variables["includeReviews"])
        self.assertFalse(variables["includeRequests"])
        self.assertFalse(variables["includeThreads"])

    def test_page_ceiling_returns_explicit_incomplete_connection(self):
        transport = FixtureTransport(response(data(
            reviews=page([review()], total=2, has_next=True, cursor="reviews-1"),
            requests=page([]),
            threads=page([]),
        )))
        snapshot = client(transport, max_pages=1).read_pull_request(
            owner="owner", name="repo", number=7
        )
        self.assertFalse(snapshot.latest_reviews.complete)
        self.assertTrue(snapshot.latest_reviews.truncated)
        self.assertEqual(snapshot.latest_reviews.last_cursor, "reviews-1")
        self.assertTrue(snapshot.review_requests.complete)

    def test_pagination_cursor_and_request_id_must_advance(self):
        first = response(data(
            reviews=page([review(91)], total=3, has_next=True, cursor="stuck"),
            requests=page([]), threads=page([]),
        ))
        second = response(
            data(reviews=page(
                [review(93)], total=3, has_next=True, cursor="stuck"
            )),
            request_id="graphql-request-2",
        )
        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(first, second)).read_pull_request(
                owner="owner", name="repo", number=7
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE)

        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(first, response(
                data(reviews=page([review(93)], total=3))
            ))).read_pull_request(owner="owner", name="repo", number=7)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        oversized = response(data(
            reviews=page([], total=1, has_next=True, cursor="x" * 4097),
            requests=page([]), threads=page([]),
        ))
        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(oversized)).read_pull_request(
                owner="owner", name="repo", number=7
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

    def test_partial_data_errors_and_unknown_envelopes_fail_closed(self):
        cases = (
            ({"data": data(reviews=page([]), requests=page([]), threads=page([])),
              "errors": [{"message": f"contains {TOKEN}"}]}, ObservationOutcome.FIELD_UNKNOWN),
            ({"data": data(reviews=page([]), requests=page([]), threads=page([])),
              "extensions": {}}, ObservationOutcome.MALFORMED_RESPONSE),
        )
        for payload, outcome in cases:
            with self.subTest(outcome=outcome):
                transport = FixtureTransport(response(body=json.dumps(payload).encode()))
                with self.assertRaises(GitHubObservationError) as caught:
                    client(transport).read_pull_request(
                        owner="owner", name="repo", number=7
                    )
                self.assertEqual(caught.exception.outcome, outcome)
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_http_failures_retry_only_safe_query_and_never_leak_body(self):
        transport = FixtureTransport(
            TimeoutError(f"contains {TOKEN}"), self.complete_response()
        )
        client(transport).read_pull_request(owner="owner", name="repo", number=7)
        self.assertEqual(len(transport.calls), 2)

        cases = (
            (401, ObservationOutcome.AUTH_ERROR),
            (403, ObservationOutcome.PERMISSION_MISSING),
            (404, ObservationOutcome.NOT_FOUND),
            (429, ObservationOutcome.RATE_LIMITED),
        )
        for status, outcome in cases:
            with self.subTest(status=status):
                raw = RawGraphQLResponse(
                    status,
                    {"X-GitHub-Request-Id": "request-error"},
                    f"body contains {TOKEN}".encode(),
                )
                with self.assertRaises(GitHubObservationError) as caught:
                    client(FixtureTransport(raw), max_retries=0).read_pull_request(
                        owner="owner", name="repo", number=7
                    )
                self.assertEqual(caught.exception.outcome, outcome)
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_identity_enum_pagination_and_response_drift_fail_closed(self):
        mutations = []
        unknown_enum = data(
            reviews=page([]), requests=page([]), threads=page([]),
            state="NEW_STATE",
        )
        mutations.append((unknown_enum, ObservationOutcome.FIELD_UNKNOWN))

        repeated = data(
            reviews=page([review(), review()], total=2),
            requests=page([]), threads=page([]),
        )
        mutations.append((repeated, ObservationOutcome.FIELD_UNKNOWN))

        incomplete = data(
            reviews=page([review()], total=2),
            requests=page([]), threads=page([]),
        )
        mutations.append((incomplete, ObservationOutcome.PAGINATION_INCOMPLETE))

        for payload, outcome in mutations:
            with self.subTest(outcome=outcome):
                with self.assertRaises(GitHubObservationError) as caught:
                    client(FixtureTransport(response(payload))).read_pull_request(
                        owner="owner", name="repo", number=7
                    )
                self.assertEqual(caught.exception.outcome, outcome)

        first = response(data(
            reviews=page([review()], total=2, has_next=True, cursor="next"),
            requests=page([]), threads=page([]),
        ))
        changed = data(reviews=page([review(93)], total=2))
        changed["repository"]["pullRequest"]["headRefOid"] = "d" * 40
        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(first, response(changed))).read_pull_request(
                owner="owner", name="repo", number=7
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_malformed_json_duplicate_keys_size_and_request_id_fail_closed(self):
        bodies = (
            b'{"data":{"repository":1,"repository":2}}',
            b"not-json",
        )
        for body in bodies:
            with self.subTest(body=body):
                with self.assertRaises(GitHubObservationError) as caught:
                    client(FixtureTransport(response(body=body))).read_pull_request(
                        owner="owner", name="repo", number=7
                    )
                self.assertEqual(
                    caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE
                )

        raw = RawGraphQLResponse(200, {}, b'{"data":{}}')
        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(raw)).read_pull_request(
                owner="owner", name="repo", number=7
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

        raw = response(body=b"x" * 33)
        with self.assertRaises(GitHubObservationError) as caught:
            client(FixtureTransport(raw), max_response_bytes=32).read_pull_request(
                owner="owner", name="repo", number=7
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

    def test_only_installation_credentials_and_closed_inputs_are_accepted(self):
        with self.assertRaisesRegex(ValueError, "installation token"):
            GitHubGraphQLClient(credential("app-jwt"), transport=FixtureTransport())
        value = client(FixtureTransport())
        for owner, name, number in (
            ("../owner", "repo", 7),
            ("owner", "repo/name", 7),
            ("owner", "repo", 0),
            ("owner", "repo", True),
        ):
            with self.subTest(owner=owner, name=name, number=number):
                with self.assertRaises(ValueError):
                    value.read_pull_request(owner=owner, name=name, number=number)
        self.assertEqual(MAX_PAGES, 30)

    def test_query_boundary_has_no_enabled_caller_or_secret_loader(self):
        consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_graphql.py":
                continue
            if "github_graphql" in path.read_text():
                consumers.append(path.relative_to(ROOT).as_posix())
        consumers.sort()
        self.assertEqual(
            consumers,
            [
                "pathfinder_core/adapters/github_evidence_collector.py",
                "pathfinder_core/adapters/github_evidence_composer.py",
                "pathfinder_core/adapters/github_graphql_projection.py",
                "pathfinder_core/adapters/github_publication_reconciliation.py",
                "pathfinder_core/adapters/github_review_reconciliation.py",
            ],
        )
        constructors = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_graphql.py":
                continue
            if "GitHubGraphQLClient(" in path.read_text():
                constructors.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(constructors, [])
        source = "\n".join(
            (ROOT / "pathfinder_core/adapters" / name).read_text()
            for name in (
                "github_graphql.py",
                "github_graphql_projection.py",
                "github_publication_reconciliation.py",
                "github_review_reconciliation.py",
            )
        )
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv(", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
