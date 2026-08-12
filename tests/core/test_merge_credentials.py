import unittest
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from pathfinder_core.errors import StateError
from pathfinder_core.merge_credentials import (
    MERGE_EXECUTOR_BOUNDARY,
    REQUIRED_MERGE_PERMISSIONS,
    GitHubMergeCredential,
)


NOW = datetime.fromisoformat("2026-08-11T12:08:30+00:00")


def credential(**updates):
    values = {
        "token": "ghs_fixture_token_1234567890",
        "credential_receipt_id": "merge_credential_receipt_example1",
        "source": "authenticated-host-credential-store",
        "credential_id": "merge_credential_example1",
        "kind": "installation-token",
        "boundary": MERGE_EXECUTOR_BOUNDARY,
        "permissions": REQUIRED_MERGE_PERMISSIONS,
        "repository_ids": [123456789],
        "app_id": 24680,
        "app_node_id": "A_kgDOApp1234",
        "installation_id": 13579,
        "installation_account_id": 123456789,
        "actor_id": 97531,
        "actor_node_id": "U_kgDOBot1234",
        "login": "pathfinder-merge[bot]",
        "issued_at": "2026-08-11T12:00:00+00:00",
        "expires_at": "2026-08-11T13:00:00+00:00",
        "verified_at": "2026-08-11T12:08:30+00:00",
        "repository_selection": "selected",
        "suspended": False,
    }
    values.update(updates)
    return GitHubMergeCredential(**values)


class MergeCredentialTests(unittest.TestCase):
    def test_exact_one_repository_app_credential_binds_actor(self):
        value = credential()
        value.validate_binding(
            {"id": 123456789},
            {
                "app_id": 24680,
                "installation_id": 13579,
                "actor_id": 97531,
                "actor_node_id": "U_kgDOBot1234",
                "login": "pathfinder-merge[bot]",
            },
            now=NOW,
        )
        self.assertNotIn("ghs_fixture", repr(value))
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "schemas/publication/merge-credential-receipt.schema.json"
            ).read_text()
        )
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(value.receipt_document())

    def test_user_tokens_extra_permissions_and_multiple_repositories_fail(self):
        cases = (
            {"kind": "user-token"},
            {"permissions": {**REQUIRED_MERGE_PERMISSIONS, "administration": "write"}},
            {"repository_ids": [123456789, 987654321]},
            {"boundary": "github-evidence-get-only"},
            {"source": "caller-declaration"},
            {"repository_selection": "all"},
            {"suspended": True},
        )
        for updates in cases:
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                credential(**updates)

    def test_wrong_repository_actor_and_expired_token_fail_closed(self):
        value = credential()
        actor = {
            "app_id": 24680,
            "installation_id": 13579,
            "actor_id": 97531,
            "actor_node_id": "U_kgDOBot1234",
            "login": "pathfinder-merge[bot]",
        }
        with self.assertRaisesRegex(StateError, "repository binding"):
            value.validate_binding({"id": 1}, actor, now=NOW)
        with self.assertRaisesRegex(StateError, "actor binding"):
            value.validate_binding(
                {"id": 123456789}, {**actor, "actor_id": 1}, now=NOW
            )
        with self.assertRaisesRegex(StateError, "not current"):
            value.validate_binding(
                {"id": 123456789}, actor,
                now=datetime.fromisoformat("2026-08-11T13:00:00+00:00"),
            )


if __name__ == "__main__":
    unittest.main()
