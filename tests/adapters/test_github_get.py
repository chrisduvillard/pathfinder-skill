import inspect
import json
import unittest
from pathlib import Path

from pathfinder_core.adapters.github_get import (
    ACCEPT,
    API_HOST,
    API_VERSION,
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    USER_AGENT,
    GETTransport,
    GitHubEvidenceCredential,
    GitHubGETClient,
    GitHubHTTPSGETTransport,
    RawGETResponse,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
)


TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
NOW = "2026-08-11T12:08:10+00:00"
ROOT = Path(__file__).resolve().parents[2]


def permissions():
    return {name: "read" for name in REQUIRED_READ_PERMISSIONS}


def credential(kind="installation-token"):
    return GitHubEvidenceCredential(
        TOKEN,
        kind=kind,
        permissions=permissions() if kind == "installation-token" else {},
        boundary=EVIDENCE_BOUNDARY,
    )


def response(status=200, data=None, headers=None, body=None):
    values = {"X-GitHub-Request-Id": "request-fixture-1", **(headers or {})}
    encoded = json.dumps({"ok": True} if data is None else data).encode()
    return RawGETResponse(status, values, encoded if body is None else body)


class FixtureGETTransport:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def get(self, path, headers, *, timeout, max_bytes):
        self.calls.append({
            "path": path, "headers": dict(headers), "timeout": timeout,
            "max_bytes": max_bytes,
        })
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def client(transport, **overrides):
    return GitHubGETClient(
        credential(), transport=transport, clock=lambda: NOW,
        sleeper=lambda _seconds: None, **overrides,
    )


class GitHubGETClientTests(unittest.TestCase):
    def test_credential_boundary_rejects_write_scope_and_redacts_repr(self):
        value = credential()
        self.assertNotIn(TOKEN, repr(value))
        self.assertIn("<redacted>", repr(value))
        with self.assertRaisesRegex(ValueError, "GET-only"):
            GitHubEvidenceCredential(
                TOKEN, kind="installation-token", permissions=permissions(),
                boundary="publication-only",
            )
        widened = permissions()
        widened["contents"] = "write"
        with self.assertRaisesRegex(ValueError, "read permissions only"):
            GitHubEvidenceCredential(
                TOKEN, kind="installation-token", permissions=widened,
                boundary=EVIDENCE_BOUNDARY,
            )
        incomplete = permissions()
        del incomplete["administration"]
        with self.assertRaisesRegex(ValueError, "must be exact"):
            GitHubEvidenceCredential(
                TOKEN, kind="installation-token", permissions=incomplete,
                boundary=EVIDENCE_BOUNDARY,
            )
        widened = permissions()
        widened["issues"] = "read"
        with self.assertRaisesRegex(ValueError, "must be exact"):
            GitHubEvidenceCredential(
                TOKEN, kind="installation-token", permissions=widened,
                boundary=EVIDENCE_BOUNDARY,
            )
        self.assertEqual(credential("app-jwt").permissions, {})

    def test_success_uses_fixed_headers_and_records_safe_audit_fields(self):
        transport = FixtureGETTransport(response(
            data={"id": 123}, headers={"ETag": 'W/"fixture"'},
        ))
        result = client(transport).get_endpoint("repository", "/repos/owner/repo")
        self.assertEqual(result.data, {"id": 123})
        self.assertEqual(result.audit.request_id, "request-fixture-1")
        self.assertEqual(result.audit.etag, 'W/"fixture"')
        self.assertEqual(result.audit.observed_at, NOW)
        call = transport.calls[0]
        self.assertEqual(call["headers"]["Accept"], ACCEPT)
        self.assertEqual(call["headers"]["X-GitHub-Api-Version"], API_VERSION)
        self.assertEqual(call["headers"]["User-Agent"], USER_AGENT)
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {TOKEN}")
        self.assertNotIn(TOKEN, repr(result))

    def test_api_version_probe_requires_the_pinned_version(self):
        transport = FixtureGETTransport(response(data=["2022-11-28", API_VERSION]))
        audit = client(transport).verify_api_version()
        self.assertEqual(audit.request_id, "request-fixture-1")
        self.assertEqual(transport.calls[0]["path"], "/versions")

        transport = FixtureGETTransport(response(data=["2022-11-28"]))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).verify_api_version()
        self.assertEqual(caught.exception.outcome, ObservationOutcome.API_UNAVAILABLE)

    def test_endpoint_allowlist_rejects_general_api_and_graphql_paths(self):
        value = client(FixtureGETTransport())
        for target in (
            "/graphql", "/repos/owner/repo/issues", "https://api.github.com/versions",
            "/repos/owner/repo/../other", "/repos/owner/repo%2fother",
            "/repos/owner/repo?state=closed", "/repos/owner/repo?page=1&page=2",
            "/repos/owner/repo/rulesets?includes_parents=false",
            "/repos/owner/repo?page=31", "/repos/owner/repo?per_page=101",
        ):
            with self.subTest(target=target), self.assertRaises(ValueError):
                value.get_json("fixture", target)

    def test_statuses_map_without_leaking_body_or_credential(self):
        cases = (
            (401, {}, ObservationOutcome.AUTH_ERROR),
            (403, {}, ObservationOutcome.PERMISSION_MISSING),
            (403, {"X-RateLimit-Remaining": "0"}, ObservationOutcome.RATE_LIMITED),
            (404, {}, ObservationOutcome.NOT_FOUND),
            (410, {}, ObservationOutcome.API_UNAVAILABLE),
            (422, {}, ObservationOutcome.MALFORMED_RESPONSE),
            (429, {"Retry-After": "60"}, ObservationOutcome.RATE_LIMITED),
        )
        for status, headers, outcome in cases:
            with self.subTest(status=status, outcome=outcome):
                transport = FixtureGETTransport(response(
                    status, headers=headers,
                    body=f"body contains {TOKEN}".encode(),
                ))
                with self.assertRaises(GitHubObservationError) as caught:
                    client(transport, max_retries=0).get_json(
                        "repository", "/repos/owner/repo"
                    )
                self.assertEqual(caught.exception.outcome, outcome)
                self.assertNotIn(TOKEN, str(caught.exception))
                self.assertNotIn("body contains", str(caught.exception))

    def test_safe_transient_reads_retry_once_but_rate_limits_do_not(self):
        transport = FixtureGETTransport(
            TimeoutError("contains a secret"), response(data={"id": 1}),
        )
        result = client(transport).get_endpoint("repository", "/repos/owner/repo")
        self.assertEqual(result.data["id"], 1)
        self.assertEqual(len(transport.calls), 2)

        transport = FixtureGETTransport(
            response(503), response(data={"id": 2}),
        )
        result = client(transport).get_endpoint("repository", "/repos/owner/repo")
        self.assertEqual(result.data["id"], 2)
        self.assertEqual(len(transport.calls), 2)

        transport = FixtureGETTransport(response(
            429, headers={"Retry-After": "60"},
        ))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).get_json("repository", "/repos/owner/repo")
        self.assertEqual(caught.exception.outcome, ObservationOutcome.RATE_LIMITED)
        self.assertEqual(len(transport.calls), 1)

    def test_response_bounds_and_duplicate_or_missing_metadata_fail_closed(self):
        raw = response(body=f"body contains {TOKEN}".encode())
        self.assertNotIn(TOKEN, repr(raw))
        transport = FixtureGETTransport(response(body=b"x" * 33))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport, max_response_bytes=32).get_json(
                "repository", "/repos/owner/repo"
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

        transport = FixtureGETTransport(response(body=b'{"id":1,"id":2}'))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).get_json("repository", "/repos/owner/repo")
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

        transport = FixtureGETTransport(RawGETResponse(200, {}, b"{}"))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).get_json("repository", "/repos/owner/repo")
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

    def test_pagination_follows_only_same_host_and_marks_ceiling(self):
        link = '<https://api.github.com/repos/owner/repo/pulls/72/files?page=2&per_page=100>; rel="next"'
        transport = FixtureGETTransport(
            response(data=[{"id": 1}], headers={"Link": link}),
            response(data=[{"id": 2}], headers={"X-GitHub-Request-Id": "request-fixture-2"}),
        )
        result = client(transport).get_pages(
            "changed-files", "/repos/owner/repo/pulls/72/files"
        )
        self.assertEqual([item["id"] for item in result.items], [1, 2])
        self.assertTrue(result.complete)
        self.assertEqual(result.pages, 2)
        self.assertEqual(len(result.audits), 2)

        transport = FixtureGETTransport(response(data=[{"id": 1}], headers={"Link": link}))
        result = client(transport, max_pages=1).get_pages(
            "changed-files", "/repos/owner/repo/pulls/72/files"
        )
        self.assertFalse(result.complete)
        self.assertTrue(result.truncated)
        self.assertIn("page=2", result.last_cursor)

        transport = FixtureGETTransport(response(data={
            "total_count": 2, "check_runs": [{"id": 1}],
        }))
        result = client(transport).get_pages(
            "check-runs", "/repos/owner/repo/commits/abc/check-runs",
            item_key="check_runs", total_key="total_count",
        )
        self.assertFalse(result.complete)
        self.assertTrue(result.truncated)

        outside = '<https://evil.example/repos/owner/repo/pulls/72/files?page=2>; rel="next"'
        transport = FixtureGETTransport(response(data=[], headers={"Link": outside}))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).get_pages(
                "changed-files", "/repos/owner/repo/pulls/72/files"
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

        malformed = '<https://api.github.com/repos/owner/repo/pulls/72/files?page=2; rel="next"'
        transport = FixtureGETTransport(response(data=[], headers={"Link": malformed}))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).get_pages(
                "changed-files", "/repos/owner/repo/pulls/72/files"
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE)

    def test_same_host_redirect_is_get_only_and_external_redirect_is_blocked(self):
        transport = FixtureGETTransport(
            response(302, headers={"Location": "https://api.github.com/versions"}),
            response(data=[API_VERSION]),
        )
        client(transport).verify_api_version()
        self.assertEqual([call["path"] for call in transport.calls], ["/versions", "/versions"])

        transport = FixtureGETTransport(response(
            302, headers={"Location": "https://evil.example/versions"},
        ))
        with self.assertRaises(GitHubObservationError) as caught:
            client(transport).verify_api_version()
        self.assertEqual(caught.exception.outcome, ObservationOutcome.API_UNAVAILABLE)
        self.assertEqual(len(transport.calls), 1)

    def test_graphql_is_typed_unavailable_and_transport_has_only_get(self):
        with self.assertRaises(GitHubObservationError) as caught:
            GitHubGETClient.graphql_unavailable("review-threads")
        self.assertEqual(caught.exception.outcome, ObservationOutcome.API_UNAVAILABLE)
        methods = {
            name for name, value in GETTransport.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(methods, {"get"})
        source = inspect.getsource(GitHubHTTPSGETTransport)
        self.assertIn('connection.request("GET"', source)
        for forbidden in ('"POST"', '"PUT"', '"PATCH"', '"DELETE"'):
            self.assertNotIn(forbidden, source)
        self.assertEqual(API_HOST, "api.github.com")

    def test_get_boundary_has_no_enabled_production_caller_or_secret_loader(self):
        consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name in {
                "github_evidence_credentials.py", "github_get.py",
                "github_get_policy.py", "github_get_transport.py",
            }:
                continue
            if "github_get" in path.read_text():
                consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])
        sources = "\n".join(
            (ROOT / "pathfinder_core" / "adapters" / name).read_text()
            for name in (
                "github_evidence_credentials.py", "github_get.py",
                "github_get_policy.py", "github_get_transport.py",
            )
        )
        self.assertNotIn("os.environ", sources)
        self.assertNotIn("getenv(", sources)


if __name__ == "__main__":
    unittest.main()
