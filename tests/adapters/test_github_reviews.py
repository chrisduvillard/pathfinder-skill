import json
import unittest

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
from pathfinder_core.adapters.github_reviews import GitHubReviewReader


TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
NOW = "2026-08-12T10:00:00+00:00"
SHA = "c" * 40


def response(data, request_id, *, permission=None, link=None):
    headers = {"X-GitHub-Request-Id": request_id}
    if permission is not None:
        headers["X-Accepted-GitHub-Permissions"] = permission
    if link is not None:
        headers["Link"] = f'<{link}>; rel="next"'
    return RawGETResponse(200, headers, json.dumps(data).encode())


def review(review_id, actor_id, login, *, state="APPROVED", actor_type="User"):
    return {
        "id": review_id,
        "node_id": f"PRR_node_{review_id}",
        "user": {
            "id": actor_id,
            "login": login,
            "type": actor_type,
            "node_id": f"U_node_{actor_id}",
            "site_admin": False,
        },
        "body": "fixture",
        "state": state,
        "html_url": f"https://github.com/owner/repo/pull/72#review-{review_id}",
        "pull_request_url": "https://api.github.com/repos/owner/repo/pulls/72",
        "_links": {},
        "submitted_at": "2026-08-12T09:59:00Z",
        "commit_id": SHA,
        "author_association": "MEMBER",
        "performed_via_github_app": None,
    }


def permission(actor_id, login, level="write"):
    return {
        "permission": level,
        "role_name": level,
        "user": {"id": actor_id, "login": login, "type": "User"},
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
    return GitHubReviewReader(client), transport


class GitHubReviewReaderTests(unittest.TestCase):
    def test_paginates_reviews_and_reads_one_permission_per_exact_actor(self):
        next_page = (
            "/repos/owner/repo/pulls/72/reviews?per_page=100&page=2"
        )
        value, transport = reader(
            response(
                [review(81, 44, "reviewer")], "reviews-page-1",
                link=next_page,
            ),
            response(
                [
                    review(82, 44, "reviewer", state="COMMENTED"),
                    review(
                        83, 55, "quality-bot[bot]", actor_type="Bot",
                    ),
                ],
                "reviews-page-2",
            ),
            response(
                permission(44, "reviewer"), "reviewer-permission",
                permission="metadata=read",
            ),
            response(
                permission(55, "quality-bot[bot]", "read"),
                "bot-permission", permission="metadata=read",
            ),
        )
        observed = value.read_all(
            repository={"owner": "owner", "name": "repo"}, pull_number=72
        )
        self.assertTrue(observed.complete)
        self.assertEqual(observed.pages, 2)
        self.assertEqual(observed.total_count, 3)
        self.assertEqual(len(observed.audits), 4)
        self.assertEqual(
            [item["repository_permission"]["permission"] for item in observed.items],
            ["write", "write", "read"],
        )
        self.assertFalse(observed.items[0]["dismissed"])
        self.assertEqual(
            transport.calls,
            [
                "/repos/owner/repo/pulls/72/reviews?per_page=100",
                next_page,
                "/repos/owner/repo/collaborators/reviewer/permission",
                "/repos/owner/repo/collaborators/quality-bot%5Bbot%5D/permission",
            ],
        )
        self.assertEqual(observed.audits[2].target, transport.calls[2])
        self.assertTrue(observed.audits[2].permission_qualified)
        unknowns = []
        normalized = GitHubMergeObserver._reviews(observed, unknowns)
        self.assertEqual(unknowns, [])
        self.assertEqual(normalized[0]["actor_id"], 44)
        self.assertEqual(normalized[0]["repository_permission"], "write")

    def test_unknown_fields_scope_and_permission_identity_fail_closed(self):
        changed = review(81, 44, "reviewer")
        changed["future_field"] = True
        value, _transport = reader(response([changed], "reviews-page"))
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        value, _transport = reader(
            response([review(81, 44, "reviewer")], "reviews-page"),
            response(
                permission(44, "reviewer"), "permission", permission="contents=read"
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PERMISSION_MISSING
        )

        value, _transport = reader(
            response([review(81, 44, "reviewer")], "reviews-page"),
            response(
                permission(45, "other"), "permission", permission="metadata=read"
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_incomplete_budget_duplicate_identity_and_request_ids_fail_closed(self):
        next_page = "/repos/owner/repo/pulls/72/reviews?per_page=100&page=2"
        value, transport = reader(
            response(
                [review(81, 44, "reviewer")], "reviews-page", link=next_page
            ),
            max_pages=1,
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE
        )
        self.assertEqual(len(transport.calls), 1)

        value, transport = reader(
            response(
                [
                    review(81, 44, "reviewer"),
                    review(82, 55, "second-reviewer"),
                ],
                "reviews-page",
            ),
            max_pages=2,
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE
        )
        self.assertEqual(len(transport.calls), 1)

        value, _transport = reader(response(
            [
                review(81, 44, "reviewer"),
                review(81, 44, "reviewer"),
            ],
            "reviews-page",
        ))
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        value, _transport = reader(
            response([review(81, 44, "reviewer")], "reused-request"),
            response(
                permission(44, "reviewer"), "reused-request",
                permission="metadata=read",
            ),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                repository={"owner": "owner", "name": "repo"}, pull_number=72
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)


if __name__ == "__main__":
    unittest.main()
