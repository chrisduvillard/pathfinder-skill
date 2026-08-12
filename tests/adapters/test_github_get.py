import inspect
import json
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from pathfinder_core.adapters.github_get import (
    ACCEPT,
    API_HOST,
    API_VERSION,
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    USER_AGENT,
    GETTransport,
    GitHubEvidenceCredential,
    GitHubEvidenceCredentialReceipt,
    GitHubGETClient,
    GitHubHTTPSGETTransport,
    RawGETResponse,
)
from pathfinder_core.adapters.github_checks import GitHubCheckRunReader
from pathfinder_core.adapters.github_memberships import GitHubBypassMembershipReader
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


def credential_receipt(**overrides):
    values = {
        "credential_receipt_id": "evidence_credential_receipt_fixture1",
        "source": "authenticated-host-credential-store",
        "credential_id": "evidence_credential_fixture1",
        "kind": "installation-token",
        "boundary": EVIDENCE_BOUNDARY,
        "permissions": permissions(),
        "repository_selection": "selected",
        "repository_ids": [123456789],
        "app_id": 86420,
        "app_node_id": "A_kgDOObserver1",
        "installation_id": 97531,
        "installation_account_id": 24680,
        "actor_id": 112233,
        "actor_node_id": "U_kgDOObserver1",
        "login": "pathfinder-observer[bot]",
        "issued_at": "2026-08-11T12:00:00+00:00",
        "expires_at": "2026-08-11T13:00:00+00:00",
        "verified_at": NOW,
        "suspended": False,
    }
    values.update(overrides)
    return GitHubEvidenceCredentialReceipt(**values)


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
    def test_authenticated_credential_receipt_is_hash_bound_and_current(self):
        receipt = credential_receipt()
        document = receipt.receipt_document()
        schema = json.loads((
            ROOT / "schemas" / "publication"
            / "evidence-credential-receipt.schema.json"
        ).read_text())
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(document)
        loaded = GitHubEvidenceCredentialReceipt.from_document(document)
        loaded.validate_binding(
            credential(),
            repository_id=123456789,
            observed_at=datetime.fromisoformat(NOW),
        )
        self.assertEqual(loaded.receipt_document(), document)
        self.assertNotIn(TOKEN, repr(loaded))

        tampered = dict(document)
        tampered["actor_id"] += 1
        with self.assertRaisesRegex(ValueError, "hash differs"):
            GitHubEvidenceCredentialReceipt.from_document(tampered)

    def test_authenticated_credential_receipt_fails_closed_on_scope_or_binding(self):
        with self.assertRaisesRegex(ValueError, "permissions must be exact"):
            credential_receipt(permissions={"metadata": "read"})
        with self.assertRaisesRegex(ValueError, "select exactly one"):
            credential_receipt(repository_ids=[123456789, 987654321])
        with self.assertRaisesRegex(ValueError, "window exceeds one hour"):
            credential_receipt(expires_at="2026-08-11T13:00:01+00:00")
        with self.assertRaisesRegex(ValueError, "is suspended"):
            credential_receipt(suspended=True)
        with self.assertRaisesRegex(ValueError, "receipt identity is malformed"):
            credential_receipt(
                credential_receipt_id="evidence_credential_receipt_short"
            )
        with self.assertRaisesRegex(ValueError, "node identity is malformed"):
            credential_receipt(actor_node_id="bad node")

        receipt = credential_receipt()
        with self.assertRaisesRegex(ValueError, "repository binding differs"):
            receipt.validate_binding(
                credential(), repository_id=987654321,
                observed_at=datetime.fromisoformat(NOW),
            )
        with self.assertRaisesRegex(ValueError, "is not fresh"):
            receipt.validate_binding(
                credential(), repository_id=123456789,
                observed_at=datetime.fromisoformat(
                    "2026-08-11T12:08:11+00:00"
                ),
            )

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

        transport = FixtureGETTransport(response(data={"permission": "write"}))
        value = client(transport).get_endpoint(
            "review-permission",
            "/repos/owner/repo/collaborators/reviewer/permission",
        )
        self.assertEqual(value.data["permission"], "write")

        for target in (
            "/orgs/owner/memberships/pathfinder-merge%5Bbot%5D",
            "/orgs/owner/teams/release-engineering/memberships/pathfinder-merge%5Bbot%5D",
        ):
            with self.subTest(target=target):
                transport = FixtureGETTransport(response(data={"state": "active"}))
                result = client(transport).get_endpoint(
                    "bypass-memberships", target
                )
                self.assertEqual(result.data["state"], "active")

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

    def test_plan_feature_absence_requires_exact_response_and_permission_header(self):
        target = "/repos/owner/repo/branches/main/protection"
        permission = {"X-Accepted-GitHub-Permissions": "administration=read"}
        transport = FixtureGETTransport(response(
            data={"required_status_checks": None}, headers=permission,
        ))
        observed = client(transport).get_qualified_feature(
            "classic-protection", target, feature="classic-protection"
        )
        self.assertEqual(observed.status, 200)
        self.assertEqual(observed.audit.target, target)
        self.assertTrue(observed.audit.permission_qualified)

        absent = {
            "message": (
                "Upgrade to GitHub Pro or make this repository public to enable "
                "this feature."
            ),
            "documentation_url": (
                "https://docs.github.com/rest/branches/branch-protection"
                "#get-branch-protection"
            ),
            "status": "403",
        }
        transport = FixtureGETTransport(response(
            403, data=absent, headers=permission,
        ))
        observed = client(transport).get_qualified_feature(
            "classic-protection", target, feature="classic-protection"
        )
        self.assertEqual(observed.status, 403)
        self.assertIsNone(observed.data)

        for data, headers in (
            (absent, {}),
            ({**absent, "message": "Forbidden"}, permission),
            ({**absent, "extra": True}, permission),
        ):
            with self.subTest(data=data, headers=headers):
                transport = FixtureGETTransport(response(
                    403, data=data, headers=headers,
                ))
                with self.assertRaises(GitHubObservationError) as caught:
                    client(transport).get_qualified_feature(
                        "classic-protection", target,
                        feature="classic-protection",
                    )
                self.assertEqual(
                    caught.exception.outcome,
                    ObservationOutcome.PERMISSION_MISSING,
                )

        with self.assertRaises(ValueError):
            client(FixtureGETTransport()).get_qualified_feature(
                "classic-protection", "/repos/owner/repo/rulesets",
                feature="classic-protection",
            )

    def test_membership_absence_requires_exact_endpoint_and_members_permission(self):
        target = (
            "/orgs/owner/teams/release-engineering/memberships/"
            "pathfinder-merge%5Bbot%5D"
        )
        permission = {"X-Accepted-GitHub-Permissions": "members=read"}
        absent = {
            "message": "Not Found",
            "documentation_url": (
                "https://docs.github.com/rest/teams/members"
                "#get-team-membership-for-a-user"
            ),
            "status": "404",
        }
        transport = FixtureGETTransport(response(
            404, data=absent, headers=permission,
        ))
        observed = GitHubBypassMembershipReader(
            client(transport)
        ).read_qualified_membership(
            target, membership="team"
        )
        self.assertEqual(observed.status, 404)
        self.assertIsNone(observed.data)
        self.assertEqual(observed.audit.target, target)
        self.assertTrue(observed.audit.permission_qualified)

        organization_target = (
            "/orgs/owner/memberships/pathfinder-merge%5Bbot%5D"
        )
        transport = FixtureGETTransport(response(
            data={"state": "active", "role": "member"},
            headers=permission,
        ))
        observed = GitHubBypassMembershipReader(
            client(transport)
        ).read_qualified_membership(
            organization_target, membership="organization"
        )
        self.assertEqual(observed.data["role"], "member")
        self.assertEqual(observed.status, 200)

        for data, headers, outcome in (
            (absent, {}, ObservationOutcome.PERMISSION_MISSING),
            ({**absent, "extra": True}, permission,
             ObservationOutcome.MALFORMED_RESPONSE),
        ):
            with self.subTest(data=data, headers=headers):
                transport = FixtureGETTransport(response(
                    404, data=data, headers=headers,
                ))
                with self.assertRaises(GitHubObservationError) as caught:
                    GitHubBypassMembershipReader(
                        client(transport)
                    ).read_qualified_membership(
                        target, membership="team"
                    )
                self.assertEqual(caught.exception.outcome, outcome)

        with self.assertRaises(ValueError):
            GitHubBypassMembershipReader(
                client(FixtureGETTransport())
            ).read_qualified_membership(
                organization_target, membership="team"
            )

    def test_check_collection_walks_every_suite_and_binds_the_exact_sha(self):
        sha = "c" * 40
        suites = [
            {"id": 11, "head_sha": sha},
            {"id": 12, "head_sha": sha},
        ]
        runs = [
            {"id": 101, "head_sha": sha, "check_suite": {"id": 11}},
            {"id": 102, "head_sha": sha, "check_suite": {"id": 12}},
        ]
        transport = FixtureGETTransport(
            response(
                data={"total_count": 2, "check_suites": suites},
                headers={"X-GitHub-Request-Id": "suite-page-1"},
            ),
            response(
                data={"total_count": 1, "check_runs": [runs[0]]},
                headers={"X-GitHub-Request-Id": "suite-11-runs-1"},
            ),
            response(
                data={"total_count": 1, "check_runs": [runs[1]]},
                headers={"X-GitHub-Request-Id": "suite-12-runs-1"},
            ),
        )
        observed = GitHubCheckRunReader(client(transport)).read_all(
            owner="owner", name="repo", sha=sha
        )
        self.assertTrue(observed.complete)
        self.assertEqual([item["id"] for item in observed.items], [101, 102])
        self.assertEqual(observed.pages, 3)
        self.assertEqual(len(observed.audits), 3)
        self.assertEqual(
            [call["path"] for call in transport.calls],
            [
                f"/repos/owner/repo/commits/{sha}/check-suites?per_page=100",
                "/repos/owner/repo/check-suites/11/check-runs?per_page=100",
                "/repos/owner/repo/check-suites/12/check-runs?per_page=100",
            ],
        )

        changed = dict(runs[0], head_sha="d" * 40)
        transport = FixtureGETTransport(
            response(
                data={"total_count": 1, "check_suites": [suites[0]]},
                headers={"X-GitHub-Request-Id": "suite-page-2"},
            ),
            response(
                data={"total_count": 1, "check_runs": [changed]},
                headers={"X-GitHub-Request-Id": "suite-11-runs-2"},
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            GitHubCheckRunReader(client(transport)).read_all(
                owner="owner", name="repo", sha=sha
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_check_collection_global_page_budget_and_request_ids_fail_closed(self):
        sha = "c" * 40
        suites = [
            {"id": 11, "head_sha": sha},
            {"id": 12, "head_sha": sha},
        ]
        run = {"id": 101, "head_sha": sha, "check_suite": {"id": 11}}
        transport = FixtureGETTransport(
            response(
                data={"total_count": 2, "check_suites": suites},
                headers={"X-GitHub-Request-Id": "suite-page-budget"},
            ),
            response(
                data={"total_count": 1, "check_runs": [run]},
                headers={"X-GitHub-Request-Id": "suite-11-budget"},
            ),
        )
        observed = GitHubCheckRunReader(
            client(transport, max_pages=2)
        ).read_all(
            owner="owner", name="repo", sha=sha
        )
        self.assertFalse(observed.complete)
        self.assertTrue(observed.truncated)
        self.assertEqual(len(transport.calls), 2)

        transport = FixtureGETTransport(
            response(
                data={"total_count": 1, "check_suites": [suites[0]]},
                headers={"X-GitHub-Request-Id": "reused-check-request"},
            ),
            response(
                data={"total_count": 1, "check_runs": [run]},
                headers={"X-GitHub-Request-Id": "reused-check-request"},
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            GitHubCheckRunReader(client(transport)).read_all(
                owner="owner", name="repo", sha=sha
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

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
        self.assertEqual(sorted(consumers), [
            "pathfinder_core/adapters/github_check_policy.py",
            "pathfinder_core/adapters/github_checks.py",
            "pathfinder_core/adapters/github_identity.py",
            "pathfinder_core/adapters/github_memberships.py",
            "pathfinder_core/adapters/github_reviews.py",
        ])
        identity_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_identity.py":
                continue
            if "GitHubIdentityVerifier(" in path.read_text():
                identity_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(identity_consumers, [])
        membership_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_memberships.py":
                continue
            if "GitHubBypassMembershipReader(" in path.read_text():
                membership_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(membership_consumers, [])
        check_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_checks.py":
                continue
            if "GitHubCheckRunReader(" in path.read_text():
                check_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(check_consumers, [])
        check_evidence_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_checks.py":
                continue
            if "GitHubCheckEvidenceReader(" in path.read_text():
                check_evidence_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(check_evidence_consumers, [])
        policy_projector_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_check_policy.py":
                continue
            if "GitHubRequiredCheckProjector(" in path.read_text():
                policy_projector_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(policy_projector_consumers, [])
        review_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_reviews.py":
                continue
            if "GitHubReviewReader(" in path.read_text():
                review_consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(review_consumers, [])
        review_reconciler_consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_review_reconciliation.py":
                continue
            if "GitHubReviewReconciler." in path.read_text():
                review_reconciler_consumers.append(
                    path.relative_to(ROOT).as_posix()
                )
        self.assertEqual(review_reconciler_consumers, [])
        sources = "\n".join(
            (ROOT / "pathfinder_core" / "adapters" / name).read_text()
            for name in (
                "github_evidence_credentials.py", "github_get.py",
                "github_get_policy.py", "github_get_transport.py",
                "github_check_policy.py", "github_checks.py",
                "github_memberships.py", "github_reviews.py",
                "github_review_reconciliation.py",
            )
        )
        self.assertNotIn("os.environ", sources)
        self.assertNotIn("getenv(", sources)


if __name__ == "__main__":
    unittest.main()
