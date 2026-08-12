import json
import unittest
from datetime import datetime

from pathfinder_core.adapters.github_merge_writer import (
    GitHubMergeBackend,
    MergeResponseLost,
    RawMergeHTTPResponse,
)
from pathfinder_core.merge_credentials import (
    MERGE_EXECUTOR_BOUNDARY,
    REQUIRED_MERGE_PERMISSIONS,
    GitHubMergeCredential,
)


def credential():
    return GitHubMergeCredential(
        "ghs_fixture_token_1234567890",
        credential_receipt_id="merge_credential_receipt_example1",
        source="authenticated-host-credential-store",
        credential_id="merge_credential_example1",
        kind="installation-token",
        boundary=MERGE_EXECUTOR_BOUNDARY,
        permissions=REQUIRED_MERGE_PERMISSIONS,
        repository_ids=[123456789],
        app_id=24680,
        app_node_id="A_kgDOApp1234",
        installation_id=13579,
        installation_account_id=123456789,
        actor_id=97531,
        actor_node_id="U_kgDOBot1234",
        login="pathfinder-merge[bot]",
        issued_at="2026-08-11T12:00:00+00:00",
        expires_at="2026-08-11T13:00:00+00:00",
        verified_at="2026-08-11T12:08:30+00:00",
        repository_selection="selected",
        suspended=False,
    )


INTENT = {
    "repository": {
        "id": 123456789,
        "node_id": "R_kgDOExample1",
        "owner": "example-owner",
        "name": "example-repo",
        "base_branch": "main",
    },
    "pull_request": {
        "id": 987654321,
        "node_id": "PR_kwDOExample1",
        "number": 72,
        "head_sha": "c" * 40,
        "base_sha": "b" * 40,
    },
}


class FixtureTransport:
    def __init__(self, put_response=None, get_responses=()):
        self.put_response = put_response
        self.get_responses = list(get_responses)
        self.put_calls = []
        self.get_calls = []

    def put_merge(self, path, headers, body, *, timeout, max_bytes):
        self.put_calls.append((path, headers, body, timeout, max_bytes))
        if isinstance(self.put_response, BaseException):
            raise self.put_response
        return self.put_response

    def get_observation(self, path, headers, *, timeout, max_bytes):
        self.get_calls.append((path, headers, timeout, max_bytes))
        return self.get_responses.pop(0)


def response(status, body=b"", request_id="request_fixture_1234"):
    return RawMergeHTTPResponse(
        status, {"X-GitHub-Request-Id": request_id}, body
    )


def json_response(status, document, request_id):
    return response(
        status,
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode(),
        request_id,
    )


def observation_responses():
    pull = {
        "id": 987654321,
        "node_id": "PR_kwDOExample1",
        "number": 72,
        "state": "closed",
        "merged": True,
        "merge_commit_sha": "d" * 40,
        "merged_at": "2026-08-11T12:08:38+00:00",
        "merged_by": {
            "id": 97531,
            "node_id": "U_kgDOBot1234",
            "login": "pathfinder-merge[bot]",
        },
        "head": {"sha": "c" * 40, "repo": {"id": 123456789}},
        "base": {
            "ref": "main",
            "repo": {"id": 123456789, "node_id": "R_kgDOExample1"},
        },
    }
    return (
        json_response(200, pull, "request_pr_followup_example1"),
        response(204, request_id="request_merged_followup_example1"),
        json_response(
            200,
            {"object": {"sha": "d" * 40}},
            "request_base_followup_example1",
        ),
        json_response(
            200,
            {"sha": "d" * 40, "parents": [{"sha": "b" * 40}]},
            "request_commit_followup_example1",
        ),
    )


class GitHubMergeWriterTests(unittest.TestCase):
    def test_merge_is_one_exact_sha_bound_squash_put(self):
        transport = FixtureTransport(
            json_response(
                200,
                {"sha": "d" * 40, "merged": True, "message": "merged"},
                "request_merge_response_example1",
            )
        )
        backend = GitHubMergeBackend(transport)
        dispatches = []
        result = backend.merge(
            INTENT, credential(), dispatch=lambda: dispatches.append(True)
        )
        self.assertEqual(dispatches, [True])
        self.assertFalse(result.malformed)
        self.assertEqual(result.status, 200)
        self.assertEqual(len(transport.put_calls), 1)
        path, headers, body, timeout, max_bytes = transport.put_calls[0]
        self.assertEqual(
            path, "/repos/example-owner/example-repo/pulls/72/merge"
        )
        self.assertEqual(
            json.loads(body), {"sha": "c" * 40, "merge_method": "squash"}
        )
        self.assertEqual(headers["X-GitHub-Api-Version"], "2026-03-10")
        self.assertNotIn("ghs_fixture", repr(result))
        self.assertGreater(timeout, 0)
        self.assertGreater(max_bytes, 0)

    def test_timeout_is_ambiguous_and_no_redirect_is_followed(self):
        backend = GitHubMergeBackend(FixtureTransport(TimeoutError("lost")))
        with self.assertRaises(MergeResponseLost):
            backend.merge(INTENT, credential(), dispatch=lambda: None)

        transport = FixtureTransport(response(302))
        result = GitHubMergeBackend(transport).merge(
            INTENT, credential(), dispatch=lambda: None
        )
        self.assertEqual(result.status, 302)
        self.assertEqual(len(transport.put_calls), 1)
        self.assertEqual(transport.get_calls, [])

    def test_malformed_success_is_typed_and_never_trusted(self):
        duplicate = b'{"merged":true,"merged":false,"sha":"' + b"d" * 40 + b'","message":"x"}'
        result = GitHubMergeBackend(
            FixtureTransport(response(200, duplicate))
        ).merge(INTENT, credential(), dispatch=lambda: None)
        self.assertTrue(result.malformed)

    def test_followup_observation_uses_only_four_exact_gets(self):
        transport = FixtureTransport(get_responses=observation_responses())
        backend = GitHubMergeBackend(
            transport,
            clock=lambda: datetime.fromisoformat("2026-08-11T12:08:39+00:00"),
        )
        observed = backend.observe(INTENT, credential())
        self.assertTrue(observed.complete)
        self.assertEqual(observed.document["merge_commit_parent_shas"], ["b" * 40])
        self.assertEqual(
            [call[0] for call in transport.get_calls],
            [
                "/repos/example-owner/example-repo/pulls/72",
                "/repos/example-owner/example-repo/pulls/72/merge",
                "/repos/example-owner/example-repo/git/ref/heads/main",
                "/repos/example-owner/example-repo/git/commits/" + "d" * 40,
            ],
        )

    def test_followup_rejects_a_commit_document_for_another_sha(self):
        responses = list(observation_responses())
        responses[-1] = json_response(
            200,
            {"sha": "e" * 40, "parents": [{"sha": "b" * 40}]},
            "request_commit_followup_example1",
        )
        observed = GitHubMergeBackend(
            FixtureTransport(get_responses=responses)
        ).observe(INTENT, credential())
        self.assertFalse(observed.complete)


if __name__ == "__main__":
    unittest.main()
