import json
import unittest

from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
)
from pathfinder_core.adapters.github_get import GitHubGETClient
from pathfinder_core.adapters.github_get_transport import RawGETResponse
from pathfinder_core.adapters.github_memberships import (
    GitHubBypassMembershipReader,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
)


TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
NOW = "2026-08-12T10:00:00+00:00"


def response(data, request_id, permission, *, status=200):
    return RawGETResponse(
        status,
        {
            "X-GitHub-Request-Id": request_id,
            "X-Accepted-GitHub-Permissions": permission,
        },
        json.dumps(data).encode(),
    )


class FixtureTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, headers, *, timeout, max_bytes):
        self.calls.append(path)
        return self.responses.pop(0)


def reader(*responses):
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
    )
    return GitHubBypassMembershipReader(client), transport


def target(actor_type, *, actor_id, actor_name, ruleset_id=81, mode="always"):
    return {
        "policy_source": "ruleset",
        "ruleset_id": ruleset_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "bypass_mode": mode,
        "actor_name": actor_name,
    }


class GitHubBypassMembershipReaderTests(unittest.TestCase):
    def test_classic_team_target_keeps_null_ruleset_and_bypass_mode(self):
        value, _transport = reader(response(
            {"url": "https://api.github.com/membership", "state": "active",
             "role": "maintainer"},
            "classic-team-request", "members=read",
        ))
        observed = value.read_all(
            [{
                "policy_source": "classic-protection",
                "ruleset_id": None,
                "actor_type": "Team",
                "actor_id": 71,
                "bypass_mode": None,
                "actor_name": "release-engineering",
            }],
            repository={"owner": "owner", "name": "repo"},
            subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
        )
        self.assertEqual(observed.items[0]["policy_source"], "classic-protection")
        self.assertIsNone(observed.items[0]["ruleset_id"])
        self.assertIsNone(observed.items[0]["bypass_mode"])
        self.assertEqual(observed.items[0]["membership_role"], "maintainer")

    def test_all_membership_types_bind_exact_subject_endpoints_and_audits(self):
        absent = {
            "message": "Not Found",
            "documentation_url": (
                "https://docs.github.com/rest/teams/members"
                "#get-team-membership-for-a-user"
            ),
            "status": "404",
        }
        value, transport = reader(
            response(absent, "team-request", "members=read", status=404),
            response(
                {"url": "https://api.github.com/membership", "state": "active",
                 "role": "member",
                 "user": {"id": 9001, "login": "pathfinder-merge[bot]"}},
                "organization-request", "members=read",
            ),
            response(
                {
                    "permission": "maintain",
                    "role_name": "release-manager",
                    "user": {"id": 9001, "login": "pathfinder-merge[bot]"},
                },
                "role-request", "metadata=read",
            ),
        )
        observed = value.read_all(
            [
                target("Team", actor_id=71, actor_name="release-engineering"),
                target("OrganizationAdmin", actor_id=None, actor_name=None),
                target(
                    "RepositoryRole", actor_id=73,
                    actor_name="release-manager",
                ),
            ],
            repository={"owner": "owner", "name": "repo"},
            subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
        )
        self.assertTrue(observed.complete)
        self.assertEqual(observed.pages, 3)
        self.assertEqual(observed.items[0]["membership_state"], "absent")
        self.assertIsNone(observed.items[0]["membership_role"])
        self.assertEqual(observed.items[1]["organization_role"], "member")
        self.assertEqual(observed.items[2]["subject_permission"], "maintain")
        self.assertEqual(observed.items[2]["subject_role_name"], "release-manager")
        self.assertEqual(
            transport.calls,
            [
                "/orgs/owner/teams/release-engineering/memberships/"
                "pathfinder-merge%5Bbot%5D",
                "/orgs/owner/memberships/pathfinder-merge%5Bbot%5D",
                "/repos/owner/repo/collaborators/"
                "pathfinder-merge%5Bbot%5D/permission",
            ],
        )
        self.assertEqual(
            [audit.request_id for audit in observed.audits],
            ["team-request", "organization-request", "role-request"],
        )
        self.assertTrue(all(audit.permission_qualified for audit in observed.audits))

    def test_unknown_fields_unqualified_absence_and_identity_drift_fail_closed(self):
        changed = {"url": "https://api.github.com/membership", "state": "active",
                   "role": "member", "future": True}
        value, _transport = reader(response(changed, "team-request", "members=read"))
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                [target("Team", actor_id=71, actor_name="release-engineering")],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        absent = {
            "message": "Not Found",
            "documentation_url": "https://docs.github.com/rest/teams/members",
            "status": "404",
        }
        value, _transport = reader(response(absent, "team-request", "", status=404))
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                [target("Team", actor_id=71, actor_name="release-engineering")],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PERMISSION_MISSING
        )

        value, _transport = reader(response(
            {
                "permission": "none", "role_name": None,
                "user": {"id": 7, "login": "someone-else[bot]"},
            },
            "role-request", "metadata=read",
        ))
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                [target(
                    "RepositoryRole", actor_id=73,
                    actor_name="release-manager",
                )],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_duplicate_targets_and_request_ids_fail_closed(self):
        item = target("Team", actor_id=71, actor_name="release-engineering")
        value, _transport = reader()
        with self.assertRaises(GitHubObservationError):
            value.read_all(
                [item, item],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )

        team = {"url": "https://api.github.com/membership", "state": "active",
                "role": "member"}
        value, _transport = reader(
            response(team, "reused-request", "members=read"),
            response(team, "reused-request", "members=read"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                [
                    item,
                    target("Team", actor_id=72, actor_name="security"),
                ],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        value, transport = reader()
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(
                [
                    target(
                        "Team", actor_id=index + 1,
                        actor_name=f"team-{index + 1}",
                    )
                    for index in range(31)
                ],
                repository={"owner": "owner", "name": "repo"},
                subject={"actor_id": 9001, "login": "pathfinder-merge[bot]"},
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE
        )
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
