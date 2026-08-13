import json
import unittest
from pathlib import Path

from pathfinder_core.adapters.github_check_policy import (
    GitHubRequiredCheckProjector,
)
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
from pathfinder_core.adapters.github_policy_rest import GitHubPolicyRESTReader
from tests.adapters.test_github_merge_observer import (
    FixtureObservationBackend,
)


ROOT = Path(__file__).resolve().parents[2]
OBSERVER_FIXTURE = (
    ROOT / "tests" / "adapters" / "fixtures" / "github-merge-observer.json"
)
JOURNAL_FIXTURE = (
    ROOT / "tests" / "contracts" / "fixtures"
    / "publication-journal-contracts.json"
)
NOW = "2026-08-11T12:08:10+00:00"
TOKEN = "fixture-policy-reader-token-abcdefghijklmnopqrstuvwxyz"
REPOSITORY = {
    "id": 123456789,
    "node_id": "R_kgDOExample1",
    "owner_id": 123456789,
    "owner": "example-owner",
    "name": "example-repo",
    "base_branch": "main",
}
MERGE_ACTOR = {"actor_id": 97531, "login": "pathfinder-merge[bot]"}


def response(data, request_id, permission, *, status=200, link=None):
    headers = {
        "X-GitHub-Request-Id": request_id,
        "X-Accepted-GitHub-Permissions": permission,
    }
    if link is not None:
        headers["Link"] = link
    return RawGETResponse(status, headers, json.dumps(data).encode())


class FixtureTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, headers, *, timeout, max_bytes):
        self.calls.append(path)
        return self.responses.pop(0)


def credential():
    return GitHubEvidenceCredential(
        TOKEN,
        kind="installation-token",
        permissions={name: "read" for name in REQUIRED_READ_PERMISSIONS},
        boundary=EVIDENCE_BOUNDARY,
    )


def classic():
    return {
        "url": "https://api.github.com/repos/example-owner/example-repo/branches/main/protection",
        "required_status_checks": {
            "url": "https://api.github.com/status-checks",
            "strict": True,
            "contexts": ["preflight (ubuntu-latest)"],
            "contexts_url": "https://api.github.com/contexts",
            "checks": [{
                "context": "preflight (ubuntu-latest)", "app_id": 15368,
            }],
        },
        "enforce_admins": {"enabled": True},
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
            "require_last_push_approval": True,
            "bypass_pull_request_allowances": {
                "users": [], "teams": [], "apps": [],
            },
            "dismissal_restrictions": {
                "users": [], "teams": [], "apps": [],
            },
        },
        "required_conversation_resolution": {"enabled": True},
        "required_linear_history": {"enabled": True},
        "required_signatures": {"enabled": False},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "block_creations": {"enabled": False},
        "lock_branch": {"enabled": False},
        "allow_fork_syncing": {"enabled": False},
    }


def parameters():
    return {
        "pull_request": {
            "allowed_merge_methods": ["squash"],
            "dismiss_stale_reviews_on_push": True,
            "require_code_owner_review": False,
            "require_last_push_approval": True,
            "required_approving_review_count": 1,
            "required_review_thread_resolution": True,
        },
        "required_status_checks": {
            "required_status_checks": [{
                "context": "preflight (ubuntu-latest)",
                "integration_id": 15368,
            }],
            "strict_required_status_checks_policy": True,
        },
    }


def active_rules():
    values = parameters()
    return [
        {
            "type": name,
            "ruleset_source_type": "Repository",
            "ruleset_source": "example-owner/example-repo",
            "ruleset_id": 7001,
            "parameters": values[name],
        }
        for name in ("pull_request", "required_status_checks")
    ]


def summary():
    return {
        "id": 7001,
        "name": "main protection",
        "target": "branch",
        "source_type": "Repository",
        "source": "example-owner/example-repo",
        "enforcement": "active",
        "node_id": "RRS_kgDORule1",
        "created_at": "2026-08-11T11:00:00+00:00",
        "updated_at": "2026-08-11T12:00:00+00:00",
    }


def detail(*, bypass=True):
    value = {
        **summary(),
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
        "rules": [
            {"type": name, "parameters": value}
            for name, value in parameters().items()
        ],
    }
    if bypass:
        value["bypass_actors"] = [{
            "actor_id": 86420,
            "actor_type": "Integration",
            "bypass_mode": "always",
        }]
    return value


def upgrade_absence():
    return {
        "message": (
            "Upgrade to GitHub Pro or make this repository public to enable this feature."
        ),
        "documentation_url": "https://docs.github.com/rest/repos/rules",
        "status": "403",
    }


def reader(*responses, max_pages=30):
    transport = FixtureTransport(*responses)
    client = GitHubGETClient(
        credential(),
        transport=transport,
        max_pages=max_pages,
        clock=lambda: NOW,
        sleeper=lambda _seconds: None,
    )
    return GitHubPolicyRESTReader(client, repository=REPOSITORY), transport


def complete_responses(*, source_detail=None):
    return (
        response(classic(), "classic-1", "administration=read"),
        response(active_rules(), "active-1", "metadata=read"),
        response([summary()], "source-index-1", "metadata=read"),
        response(
            source_detail if source_detail is not None else detail(),
            "source-detail-1",
            "metadata=read",
        ),
    )


class SnapshotObservationBackend(FixtureObservationBackend):
    def __init__(self, responses, snapshot):
        super().__init__(responses)
        self.snapshot = snapshot

    def read_classic_protection(self):
        return self.snapshot.classic_protection

    def read_active_rules(self):
        return self.snapshot.active_rules

    def read_source_rulesets(self):
        return self.snapshot.source_rulesets, self.snapshot.bypass_actors

    def read_bypass_memberships(self):
        return self.snapshot.bypass_memberships


class GitHubPolicyRESTReaderTests(unittest.TestCase):
    def test_verified_merge_actor_is_required_per_snapshot_before_any_read(self):
        value, transport = reader(*complete_responses())
        self.assertFalse(hasattr(value, "merge_actor"))
        for actor in (
            {},
            {**MERGE_ACTOR, "future": True},
            {"actor_id": MERGE_ACTOR["actor_id"], "login": "not-a-bot"},
        ):
            with self.subTest(actor=actor):
                with self.assertRaises(GitHubObservationError):
                    value.read_all(merge_actor=actor)
        self.assertEqual(transport.calls, [])

    def test_one_snapshot_owns_normalized_policy_and_required_check_views(self):
        value, transport = reader(*complete_responses())
        observed = value.read_all(merge_actor=MERGE_ACTOR)

        self.assertEqual(observed.classic_protection.data["status"], "present")
        self.assertEqual(
            observed.classic_protection.audit,
            observed.classic_check_policy.audit,
        )
        self.assertEqual(
            observed.active_rules.audits, observed.active_check_policy.audits
        )
        self.assertEqual(observed.source_rulesets.pages, 2)
        self.assertEqual(
            [audit.request_id for audit in observed.source_rulesets.audits],
            ["source-index-1", "source-detail-1"],
        )
        self.assertEqual(observed.source_rulesets.items[0]["source_id"], 123456789)
        self.assertEqual(observed.bypass_actors.pages, 0)
        self.assertEqual(observed.bypass_actors.items, ({
            "ruleset_id": 7001,
            "actor_type": "Integration",
            "actor_id": 86420,
            "bypass_mode": "always",
        },))
        self.assertEqual(observed.bypass_memberships.items, ())
        self.assertEqual(
            GitHubRequiredCheckProjector.project(
                host_policy_checks=[{"context": "host", "app_id": 1}],
                classic_protection=observed.classic_check_policy,
                active_rules=observed.active_check_policy,
            ),
            (
                {"context": "host", "app_id": 1},
                {"context": "preflight (ubuntu-latest)", "app_id": 15368},
            ),
        )
        self.assertEqual(transport.calls, [
            "/repos/example-owner/example-repo/branches/main/protection",
            "/repos/example-owner/example-repo/rules/branches/main?per_page=100",
            (
                "/repos/example-owner/example-repo/rulesets"
                "?includes_parents=true&per_page=100"
            ),
            (
                "/repos/example-owner/example-repo/rulesets/7001"
                "?includes_parents=true"
            ),
        ])

    def test_snapshot_composes_as_complete_observer_evidence_without_shared_audits(self):
        value, _transport = reader(*complete_responses())
        snapshot = value.read_all(merge_actor=MERGE_ACTOR)
        fixture = json.loads(OBSERVER_FIXTURE.read_text())
        journal = json.loads(JOURNAL_FIXTURE.read_text())
        backend = SnapshotObservationBackend(fixture["responses"], snapshot)
        result = GitHubMergeObserver(backend).observe(
            bindings=journal["evidence"]["bindings"], **fixture["context"]
        )

        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.evidence["pagination"]["source_rulesets"]["pages"], 2)
        self.assertEqual(result.evidence["pagination"]["bypass_actors"]["pages"], 0)
        request_ids = [
            item["request_id"] for item in result.evidence["observation"]["requests"]
        ]
        self.assertEqual(len(request_ids), len(set(request_ids)))

    def test_qualified_plan_absence_is_preserved_without_interpreting_bare_403(self):
        absent = upgrade_absence()
        value, transport = reader(
            response(absent, "classic-1", "administration=read", status=403),
            response(absent, "active-1", "metadata=read", status=403),
            response(absent, "sources-1", "metadata=read", status=403),
        )
        observed = value.read_all(merge_actor=MERGE_ACTOR)

        self.assertEqual(observed.classic_protection.data["status"], "absent")
        self.assertEqual(observed.classic_check_policy.status, 403)
        self.assertEqual(observed.active_rules.items, ())
        self.assertEqual(observed.source_rulesets.items, ())
        self.assertEqual(observed.source_rulesets.pages, 1)
        self.assertEqual(len(transport.calls), 3)

        value, _transport = reader(
            response(absent, "classic-1", "", status=403),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.PERMISSION_MISSING)

    def test_omitted_ruleset_bypass_actors_remain_unknown(self):
        value, transport = reader(*complete_responses(source_detail=detail(bypass=False)))
        snapshot = value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(
            snapshot.source_rulesets.items[0]["bypass_visibility"], "unknown"
        )
        self.assertEqual(snapshot.bypass_actors.items, ())
        self.assertEqual(len(transport.calls), 4)

        fixture = json.loads(OBSERVER_FIXTURE.read_text())
        journal = json.loads(JOURNAL_FIXTURE.read_text())
        result = GitHubMergeObserver(
            SnapshotObservationBackend(fixture["responses"], snapshot)
        ).observe(bindings=journal["evidence"]["bindings"], **fixture["context"])
        self.assertEqual(result.outcome, ObservationOutcome.BYPASS_VISIBILITY_UNKNOWN)

    def test_team_id_without_source_owned_slug_never_triggers_guessed_membership(self):
        changed = detail()
        changed["bypass_actors"] = [{
            "actor_id": 71, "actor_type": "Team", "bypass_mode": "always",
        }]
        value, transport = reader(*complete_responses(source_detail=changed))
        snapshot = value.read_all(merge_actor=MERGE_ACTOR)

        self.assertNotIn("actor_name", snapshot.bypass_actors.items[0])
        self.assertEqual(snapshot.bypass_memberships.items, ())
        self.assertEqual(len(transport.calls), 4)

        fixture = json.loads(OBSERVER_FIXTURE.read_text())
        journal = json.loads(JOURNAL_FIXTURE.read_text())
        result = GitHubMergeObserver(
            SnapshotObservationBackend(fixture["responses"], snapshot)
        ).observe(bindings=journal["evidence"]["bindings"], **fixture["context"])
        self.assertEqual(result.outcome, ObservationOutcome.BYPASS_VISIBILITY_UNKNOWN)

    def test_organization_admin_membership_uses_exact_qualified_subject(self):
        changed = detail()
        changed["bypass_actors"] = [{
            "actor_id": None,
            "actor_type": "OrganizationAdmin",
            "bypass_mode": "always",
        }]
        membership = {
            "url": "https://api.github.com/org-membership",
            "state": "active",
            "role": "member",
            "user": {"id": 97531, "login": "pathfinder-merge[bot]"},
        }
        value, transport = reader(
            *complete_responses(source_detail=changed),
            response(membership, "membership-1", "members=read"),
        )
        snapshot = value.read_all(merge_actor=MERGE_ACTOR)

        self.assertEqual(
            snapshot.bypass_memberships.items[0]["organization_role"], "member"
        )
        self.assertEqual(
            transport.calls[-1],
            "/orgs/example-owner/memberships/pathfinder-merge%5Bbot%5D",
        )

    def test_unknown_fields_source_drift_and_request_ceiling_fail_closed(self):
        incomplete_classic = classic()
        del incomplete_classic[
            "required_pull_request_reviews"
        ]["bypass_pull_request_allowances"]["apps"]
        value, _transport = reader(
            response(
                incomplete_classic, "classic-1", "administration=read"
            ),
            response(active_rules(), "active-1", "metadata=read"),
            response([summary()], "source-index-1", "metadata=read"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE
        )

        changed_active = active_rules()
        changed_active[0]["future_requirement"] = True
        value, _transport = reader(
            response(classic(), "classic-1", "administration=read"),
            response(changed_active, "active-1", "metadata=read"),
            response([summary()], "source-index-1", "metadata=read"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        missing = {**summary(), "id": 7002}
        value, _transport = reader(
            response(classic(), "classic-1", "administration=read"),
            response(active_rules(), "active-1", "metadata=read"),
            response([missing], "source-index-1", "metadata=read"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE
        )

        drifted = detail()
        drifted["rules"][0]["parameters"]["required_approving_review_count"] = 2
        value, _transport = reader(
            *complete_responses(source_detail=drifted)
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE
        )

        value, transport = reader(*complete_responses(), max_pages=1)
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.PAGINATION_INCOMPLETE)
        self.assertEqual(len(transport.calls), 3)

    def test_parameterless_linear_history_is_closed_but_future_parameters_block(self):
        active = active_rules() + [{
            "type": "required_linear_history",
            "ruleset_source_type": "Repository",
            "ruleset_source": "example-owner/example-repo",
            "ruleset_id": 7001,
        }]
        source = detail()
        source["rules"].append({"type": "required_linear_history"})
        value, _transport = reader(
            response(classic(), "classic-1", "administration=read"),
            response(active, "active-1", "metadata=read"),
            response([summary()], "source-index-1", "metadata=read"),
            response(source, "source-detail-1", "metadata=read"),
        )
        snapshot = value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(
            snapshot.active_rules.items[-1]["parameters"], {}
        )

        active[-1]["parameters"] = {"future": True}
        value, _transport = reader(
            response(classic(), "classic-1", "administration=read"),
            response(active, "active-1", "metadata=read"),
            response([summary()], "source-index-1", "metadata=read"),
        )
        with self.assertRaises(GitHubObservationError) as caught:
            value.read_all(merge_actor=MERGE_ACTOR)
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_reader_is_source_only_and_has_no_constructor_or_write_primitive(self):
        source = (
            ROOT / "pathfinder_core" / "adapters" / "github_policy_rest.py"
        ).read_text()
        for forbidden in (
            "GitHubEvidenceCredential(", "GitHubHTTPS", "os.environ",
            "subprocess", "PublicationController", "MergeExecutor",
            "def publish(", "def merge(", "def put(", "def post(",
        ):
            self.assertNotIn(forbidden, source)
        consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_policy_rest.py":
                continue
            if "GitHubPolicyRESTReader(" in path.read_text():
                consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
