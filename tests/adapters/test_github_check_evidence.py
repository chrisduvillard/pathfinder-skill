import json
import unittest

from pathfinder_core.adapters.github_checks import GitHubCheckEvidenceReader
from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
)
from pathfinder_core.adapters.github_get import GitHubGETClient
from pathfinder_core.adapters.github_get_transport import RawGETResponse
from pathfinder_core.adapters.github_merge_observer import (
    GitHubMergeObserver,
    GitHubObservationError,
    ObservationOutcome,
)


TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
NOW = "2026-08-12T10:00:00+00:00"
SHA = "c" * 40


def response(data, request_id, *, link=None):
    headers = {"X-GitHub-Request-Id": request_id}
    if link is not None:
        headers["Link"] = f'<{link}>; rel="next"'
    return RawGETResponse(200, headers, json.dumps(data).encode())


def suite(suite_id=11):
    return {"id": suite_id, "head_sha": SHA}


def pull_relation(*, base_sha="b" * 40):
    return {
        "url": "https://api.github.com/repos/owner/repo/pulls/72",
        "id": 987654321,
        "number": 72,
        "head": {
            "ref": "pathfinder/goal",
            "sha": SHA,
            "repo": {
                "id": 123,
                "url": "https://api.github.com/repos/owner/repo",
                "name": "repo",
            },
        },
        "base": {
            "ref": "main",
            "sha": base_sha,
            "repo": {
                "id": 123,
                "url": "https://api.github.com/repos/owner/repo",
                "name": "repo",
            },
        },
    }


def run(run_id=101, *, suite_id=11, name="preflight", app_id=15368):
    return {
        "id": run_id,
        "node_id": f"CR_node_{run_id}",
        "name": name,
        "head_sha": SHA,
        "external_id": None,
        "url": f"https://api.github.com/repos/owner/repo/check-runs/{run_id}",
        "html_url": f"https://github.com/owner/repo/runs/{run_id}",
        "details_url": "https://example.invalid/check",
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-08-12T09:58:00Z",
        "completed_at": "2026-08-12T09:59:00Z",
        "output": {},
        "check_suite": {"id": suite_id},
        "app": {"id": app_id, "slug": "actions"},
        "pull_requests": [pull_relation()],
        "deployment": None,
    }


def status(status_id=201, *, context="license/cla", state="success"):
    return {
        "url": "https://api.github.com/repos/owner/repo/statuses/" + SHA,
        "avatar_url": None,
        "id": status_id,
        "node_id": f"CS_node_{status_id}",
        "state": state,
        "description": "fixture",
        "target_url": "https://example.invalid/status",
        "context": context,
        "created_at": "2026-08-12T09:58:00Z",
        "updated_at": "2026-08-12T09:59:00Z",
        "creator": {"id": 55, "login": "status-user", "type": "User"},
    }


def combined(statuses, *, state="success", sha=SHA, repository_id=123):
    return {
        "state": state,
        "statuses": statuses,
        "sha": sha,
        "total_count": len(statuses),
        "repository": {
            "id": repository_id,
            "name": "repo",
            "full_name": "owner/repo",
            "owner": {"login": "owner"},
        },
        "commit_url": "https://api.github.com/repos/owner/repo/commits/" + SHA,
        "url": "https://api.github.com/repos/owner/repo/commits/" + SHA + "/status",
    }


class FixtureTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, headers, *, timeout, max_bytes):
        self.calls.append(path)
        return self.responses.pop(0)


def reader(*responses, max_pages=30):
    credential = GitHubEvidenceCredential(
        TOKEN,
        kind="installation-token",
        permissions={name: "read" for name in REQUIRED_READ_PERMISSIONS},
        boundary=EVIDENCE_BOUNDARY,
    )
    transport = FixtureTransport(*responses)
    client = GitHubGETClient(
        credential,
        transport=transport,
        clock=lambda: NOW,
        sleeper=lambda _seconds: None,
        max_pages=max_pages,
    )
    return GitHubCheckEvidenceReader(client), transport


def read(value):
    return value.read_all(
        owner="owner",
        name="repo",
        repository_id=123,
        sha=SHA,
        required_checks=[{"context": "preflight", "app_id": 15368}],
        pull_request={
            "id": 987654321,
            "number": 72,
            "head_repository_id": 123,
            "head_ref": "pathfinder/goal",
            "head_sha": SHA,
            "base_repository_id": 123,
            "base_ref": "main",
            "base_sha": "b" * 40,
        },
    )


class GitHubCheckEvidenceReaderTests(unittest.TestCase):
    def test_projects_required_runs_and_individual_commit_statuses(self):
        legacy_status = status(context="preflight")
        value, transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(combined([legacy_status]), "statuses"),
            response([legacy_status], "status-history"),
        )
        check_page, status_page = read(value)
        self.assertTrue(check_page.complete)
        self.assertTrue(status_page.complete)
        self.assertTrue(check_page.items[0]["required"])
        self.assertTrue(status_page.items[0]["required"])
        self.assertEqual(check_page.items[0]["app"], {"id": 15368})
        self.assertEqual(status_page.items[0]["sha"], SHA)
        self.assertEqual(
            transport.calls,
            [
                f"/repos/owner/repo/commits/{SHA}/check-suites?per_page=100",
                "/repos/owner/repo/check-suites/11/check-runs?per_page=100",
                f"/repos/owner/repo/commits/{SHA}/status?per_page=1",
                f"/repos/owner/repo/commits/{SHA}/statuses?per_page=100",
            ],
        )
        unknowns = []
        normalized = GitHubMergeObserver._check_evidence(
            check_page, status_page, unknowns
        )
        self.assertEqual(unknowns, [])
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["source"], "check-run")

    def test_status_pagination_uses_the_remaining_global_request_budget(self):
        next_page = f"/repos/owner/repo/commits/{SHA}/statuses?per_page=100&page=2"
        first = [status(201)]
        second = [status(202, context="security")]
        envelope = combined([first[0], second[0]])
        value, transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(envelope, "combined-status"),
            response(first, "statuses-1", link=next_page),
            response(second, "statuses-2"),
            max_pages=5,
        )
        _checks, statuses = read(value)
        self.assertTrue(statuses.complete)
        self.assertEqual(statuses.pages, 3)
        self.assertEqual(len(statuses.items), 2)
        self.assertEqual(len(transport.calls), 5)

        value, transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(envelope, "combined-status"),
            response(first, "statuses-1", link=next_page),
            max_pages=4,
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE
        )
        self.assertEqual(len(transport.calls), 4)

    def test_identity_state_unknown_fields_and_duplicates_fail_closed(self):
        changed = run()
        changed["future_field"] = True
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [changed]}, "runs"
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        wrong = combined([status()], repository_id=999)
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(wrong, "statuses"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        mismatched_state = combined([status()], state="failure")
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(mismatched_state, "combined-status"),
            response([status()], "status-history"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        wrong_relation = run()
        wrong_relation["pull_requests"] = [pull_relation(base_sha="d" * 40)]
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [wrong_relation]}, "runs"
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        malformed_relation = pull_relation()
        malformed_relation["head"]["repo"]["url"] = 7
        malformed_run = run()
        malformed_run["pull_requests"] = [malformed_relation]
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [malformed_run]}, "runs"
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        stale = status(201, context="same", state="pending")
        current = status(202, context="same")
        duplicated = combined([current])
        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "runs"
            ),
            response(duplicated, "statuses"),
            response([stale, current], "status-history"),
        )
        _checks, statuses = read(value)
        self.assertEqual([item["id"] for item in statuses.items], [202])
        self.assertEqual(statuses.items[0]["state"], "success")

        value, _transport = reader(
            response(
                {"total_count": 1, "check_suites": [suite()]}, "suites"
            ),
            response(
                {"total_count": 1, "check_runs": [run()]}, "reused"
            ),
            response(combined([status()]), "reused"),
            response([status()], "status-history"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_duplicate_required_or_current_check_identity_fails_closed(self):
        value, transport = reader()
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                owner="owner",
                name="repo",
                repository_id=123,
                sha=SHA,
                required_checks=[
                    {"context": "preflight", "app_id": 15368},
                    {"context": "preflight", "app_id": 15368},
                ],
                pull_request={
                    "id": 987654321,
                    "number": 72,
                    "head_repository_id": 123,
                    "head_ref": "pathfinder/goal",
                    "head_sha": SHA,
                    "base_repository_id": 123,
                    "base_ref": "main",
                    "base_sha": "b" * 40,
                },
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertEqual(transport.calls, [])

        value, _transport = reader(
            response(
                {"total_count": 2, "check_suites": [suite(11), suite(12)]},
                "suites",
            ),
            response(
                {"total_count": 1, "check_runs": [run(101, suite_id=11)]},
                "runs-11",
            ),
            response(
                {"total_count": 1, "check_runs": [run(102, suite_id=12)]},
                "runs-12",
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            read(value)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
