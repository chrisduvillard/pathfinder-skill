import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from pathfinder_core.adapters.github_branch_ownership import (
    GitHubControllerBranchOwnershipProver,
)
from pathfinder_core.adapters.github_evidence_composer import (
    GitHubCompleteEvidenceComposer,
)
from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredentialReceipt,
)
from pathfinder_core.adapters.github_get import QualifiedFeatureResponse
from pathfinder_core.adapters.github_graphql import (
    GraphQLConnection,
    GraphQLPullRequestSnapshot,
)
from pathfinder_core.adapters.github_identity import VerifiedObserverIdentity
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    PageResponse,
    RequestAudit,
)
from pathfinder_core.adapters.github_publication_reconciliation import (
    GitHubPublicationReconciler,
)
from pathfinder_core.storage import canonical_sha256
from tests.adapters.test_github_branch_ownership import (
    COMPLETED as OWNERSHIP_COMPLETED,
    OBSERVED as OWNERSHIP_OBSERVED,
    branch_ref,
    credential_receipt,
    effective_rules,
    ruleset_response,
)
from tests.adapters.test_github_merge_observer import (
    FixtureObservationBackend,
    audit,
)


ROOT = Path(__file__).resolve().parents[2]
OBSERVER_FIXTURE = (
    ROOT / "tests" / "adapters" / "fixtures" / "github-merge-observer.json"
)
PUBLICATION_FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)
JOURNAL_FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-journal-contracts.json"
)


def connection(*items):
    return GraphQLConnection(items, 1, len(items), True, False, None)


class GitHubCompleteEvidenceComposerTests(unittest.TestCase):
    def setUp(self):
        observer = json.loads(OBSERVER_FIXTURE.read_text())
        publication = json.loads(PUBLICATION_FIXTURE.read_text())
        journal = json.loads(JOURNAL_FIXTURE.read_text())
        self.context = observer["context"]
        self.responses = observer["responses"]
        self.bindings = journal["evidence"]["bindings"]
        self.publication_request = publication["request"]
        self.publication_receipt = publication["receipt"]
        self.responses["classic-protection"]["audit"].update({
            "target": (
                "/repos/example-owner/example-repo/branches/main/protection"
            ),
            "status": 200,
            "permission_qualified": True,
        })
        self.graphql = self._graphql()
        self.branch_ownership = self._branch_ownership()
        self.rest_reviews = self._reviews()
        self.identity = self._identity()
        self.classic_policy = self._classic_policy()
        self.active_policy = self._active_policy()

    def _branch_ownership(self):
        pusher = GitHubPublicationReconciler.reconcile(
            publication_request=self.publication_request,
            publication_receipt=self.publication_receipt,
            graphql=self.graphql,
        )
        return GitHubControllerBranchOwnershipProver.prove(
            controller_pusher=pusher,
            publication_credential_receipt=credential_receipt(),
            ruleset=ruleset_response(),
            effective_rules=effective_rules(),
            branch_ref=branch_ref(),
            evidence_completed_at=self.context["completed_at"],
            observed_at=OWNERSHIP_OBSERVED,
            completed_at=OWNERSHIP_COMPLETED,
            ownership_id="controller_branch_ownership_composer1",
        )

    def _graphql(self):
        repository = copy.deepcopy(self.publication_receipt["repository"])
        pull = self.publication_receipt["pull_request"]
        review = self.responses["reviews"]["items"][0]
        latest = {
            "id": review["id"],
            "node_id": "PRR_review9001",
            "state": review["state"],
            "submitted_at": review["submitted_at"],
            "commit_sha": review["commit_id"],
            "author_association": review["author_association"],
            "actor_id": review["user"]["id"],
            "actor_node_id": "U_reviewer44444",
            "actor_login": review["user"]["login"],
            "actor_type": review["user"]["type"],
        }
        return GraphQLPullRequestSnapshot(
            repository=repository,
            pull_request={
                "id": pull["id"],
                "node_id": pull["node_id"],
                "number": pull["number"],
                "state": "open",
                "draft": False,
                "head_ref": pull["head_ref"],
                "head_sha": pull["head_sha"],
                "head_repository_id": repository["id"],
                "head_repository_node_id": repository["node_id"],
                "base_ref": pull["base_ref"],
                "base_sha": pull["base_sha"],
                "base_repository_id": repository["id"],
                "base_repository_node_id": repository["node_id"],
                "mergeable": "MERGEABLE",
                "merge_state_status": "CLEAN",
                "review_decision": "APPROVED",
                "merge_queue_entry": False,
            },
            latest_reviews=connection(latest),
            review_requests=connection(),
            review_threads=connection({
                "id": "PRRT_kwDOThread1",
                "is_resolved": True,
                "is_outdated": False,
            }),
            requests=(RequestAudit(
                "req-graphql-pull-request-1",
                "2026-08-11T12:08:10+00:00",
            ),),
            rate_limits=({
                "cost": 1,
                "remaining": 4999,
                "resetAt": "2026-08-11T13:00:00+00:00",
            },),
        )

    def _reviews(self):
        item = copy.deepcopy(self.responses["reviews"]["items"][0])
        item["node_id"] = "PRR_review9001"
        item["user"]["node_id"] = "U_reviewer44444"
        raw = self.responses["reviews"]
        page = raw["page"]
        return PageResponse(
            (item,), page["pages"], page["total_count"], page["complete"],
            page["truncated"], page["last_cursor"],
            tuple(audit(value) for value in raw["audits"]),
        )

    def _identity(self):
        receipt = GitHubEvidenceCredentialReceipt(
            credential_receipt_id="evidence_credential_receipt_composer1",
            source="authenticated-host-credential-store",
            credential_id="evidence_credential_composer1",
            kind="installation-token",
            boundary=EVIDENCE_BOUNDARY,
            permissions={name: "read" for name in REQUIRED_READ_PERMISSIONS},
            repository_selection="selected",
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
            verified_at=self.context["observed_at"],
            suspended=False,
        )
        repository = copy.deepcopy(self.responses["repository"]["data"])
        requests = tuple(
            RequestAudit(value, "2026-08-11T12:08:10+00:00")
            for value in (
                "req-observer-app-1",
                "req-observer-installation-1",
                "req-observer-actor-1",
                "req-observer-repository-1",
            )
        )
        return VerifiedObserverIdentity(
            repository, receipt.receipt_document(), requests
        )

    def _classic_policy(self):
        check = {"context": "preflight (ubuntu-latest)", "app_id": 15368}
        return QualifiedFeatureResponse(
            {
                "url": "https://api.github.com/protection",
                "required_status_checks": {
                    "url": "https://api.github.com/status-checks",
                    "strict": True,
                    "contexts": [check["context"]],
                    "contexts_url": "https://api.github.com/contexts",
                    "checks": [check],
                },
            },
            200,
            audit(self.responses["classic-protection"]["audit"]),
        )

    def _active_policy(self):
        raw = self.responses["active-rules"]
        items = tuple({
            "type": value["rule_type"],
            "ruleset_source_type": value["source_type"],
            "ruleset_source": "example-owner/example-repo",
            "ruleset_id": value["ruleset_id"],
            "parameters": copy.deepcopy(value["parameters"]),
        } for value in raw["items"])
        page = raw["page"]
        return PageResponse(
            items, page["pages"], page["total_count"], page["complete"],
            page["truncated"], page["last_cursor"],
            tuple(audit(value) for value in raw["audits"]),
        )

    def _page(self, name):
        raw = self.responses[name]
        page = raw["page"]
        return PageResponse(
            tuple(copy.deepcopy(raw["items"])), page["pages"],
            page["total_count"], page["complete"], page["truncated"],
            page["last_cursor"], tuple(audit(value) for value in raw["audits"]),
        )

    def compose(self, **overrides):
        values = {
            "base_backend": FixtureObservationBackend(
                copy.deepcopy(self.responses)
            ),
            "observer_identity": self.identity,
            "publication_request": self.publication_request,
            "publication_receipt": self.publication_receipt,
            "branch_ownership": self.branch_ownership,
            "graphql": self.graphql,
            "rest_reviews": self.rest_reviews,
            "host_policy_checks": [{
                "context": "preflight (ubuntu-latest)", "app_id": 15368,
            }],
            "classic_check_policy": self.classic_policy,
            "active_check_policy": self.active_policy,
            "check_runs": self._page("check-runs"),
            "commit_statuses": self._page("commit-statuses"),
            "bindings": self.bindings,
            **self.context,
        }
        values.pop("graphql_query_sha256")
        values.update(overrides)
        return GitHubCompleteEvidenceComposer.compose(**values)

    def test_composes_one_schema_valid_provenance_bound_snapshot(self):
        result = self.compose()
        evidence = result.evidence
        provenance = result.provenance
        self.assertTrue(evidence["observation"]["collection_complete"])
        self.assertEqual(evidence["actor"]["app_id"], 24680)
        self.assertEqual(evidence["pull_request"]["last_pusher_id"], 97531)
        self.assertEqual(evidence["reviews"][0]["id"], 9001)
        self.assertEqual(evidence["review_threads"][0]["node_id"], "PRRT_kwDOThread1")
        self.assertEqual(provenance["reconciled_review_ids"], [9001])
        self.assertEqual(provenance["required_checks"], [{
            "context": "preflight (ubuntu-latest)", "app_id": 15368,
        }])
        self.assertEqual(provenance["evidence_sha256"], evidence["evidence_sha256"])
        self.assertEqual(
            provenance["branch_ownership_sha256"],
            self.branch_ownership["ownership_sha256"],
        )
        self.assertEqual(
            provenance["provenance_sha256"],
            canonical_sha256(provenance, "provenance_sha256"),
        )
        request_ids = [
            value["request_id"] for value in evidence["observation"]["requests"]
        ]
        self.assertEqual(len(request_ids), len(set(request_ids)))
        self.assertIn("req-observer-installation-1", request_ids)
        self.assertNotIn("req-review-threads-1", request_ids)

    def test_identity_review_policy_and_check_drift_fail_closed(self):
        receipt = copy.deepcopy(self.identity.credential_receipt)
        receipt["repository_ids"] = [1]
        receipt["receipt_sha256"] = canonical_sha256(receipt, "receipt_sha256")
        wrong_identity = replace(self.identity, credential_receipt=receipt)
        with self.assertRaises(GitHubObservationError):
            self.compose(observer_identity=wrong_identity)

        graph = copy.deepcopy(self.graphql)
        graph.latest_reviews.items[0]["commit_sha"] = "d" * 40
        with self.assertRaises(GitHubObservationError):
            self.compose(graphql=graph)

        checks = self._page("check-runs")
        checks.items[0]["required"] = False
        with self.assertRaisesRegex(GitHubObservationError, "required checks"):
            self.compose(check_runs=checks)

        different_audit = replace(
            self.classic_policy,
            audit=replace(self.classic_policy.audit, request_id="different"),
        )
        with self.assertRaises(GitHubObservationError):
            self.compose(classic_check_policy=different_audit)

        ownership = copy.deepcopy(self.branch_ownership)
        ownership["head_sha"] = "d" * 40
        ownership["ownership_sha256"] = canonical_sha256(
            ownership, "ownership_sha256"
        )
        with self.assertRaisesRegex(GitHubObservationError, "ownership"):
            self.compose(branch_ownership=ownership)

    def test_duplicate_cross_surface_request_identity_fails_closed(self):
        graph = replace(
            self.graphql,
            requests=(RequestAudit(
                "req-pull-request-1", "2026-08-11T12:08:10+00:00"
            ),),
        )
        with self.assertRaisesRegex(GitHubObservationError, "duplicated"):
            self.compose(graphql=graph)

        ownership = copy.deepcopy(self.branch_ownership)
        ownership["observation"]["request_ids"][0] = "req-pull-request-1"
        ownership["observation"]["request_ids_sha256"] = canonical_sha256(
            ownership["observation"]["request_ids"]
        )
        ownership["ownership_sha256"] = canonical_sha256(
            ownership, "ownership_sha256"
        )
        with self.assertRaisesRegex(GitHubObservationError, "duplicated"):
            self.compose(branch_ownership=ownership)

    def test_malformed_identity_and_out_of_window_audit_fail_closed(self):
        malformed = replace(
            self.identity,
            requests=("bad", "bad2", "bad3", "bad4"),
        )
        with self.assertRaises(GitHubObservationError):
            self.compose(observer_identity=malformed)

        repository = copy.deepcopy(self.identity.repository)
        repository["owner"] = "example-owner"
        with self.assertRaises(GitHubObservationError):
            self.compose(observer_identity=replace(
                self.identity, repository=repository
            ))

        graph = replace(
            self.graphql,
            requests=(RequestAudit(
                "req-graphql-pull-request-1",
                "2026-08-11T12:09:00+00:00",
            ),),
        )
        with self.assertRaisesRegex(GitHubObservationError, "collection window"):
            self.compose(graphql=graph)

    def test_inputs_are_not_mutated_and_composer_owns_no_client(self):
        inputs = copy.deepcopy((
            self.responses,
            self.identity,
            self.publication_request,
            self.publication_receipt,
            self.branch_ownership,
            self.graphql,
            self.rest_reviews,
        ))
        self.compose()
        self.assertEqual(inputs, (
            self.responses,
            self.identity,
            self.publication_request,
            self.publication_receipt,
            self.branch_ownership,
            self.graphql,
            self.rest_reviews,
        ))
        source = (
            ROOT
            / "pathfinder_core"
            / "adapters"
            / "github_evidence_composer.py"
        ).read_text()
        for forbidden in (
            "GitHubGETClient", "GitHubGraphQLClient", "GitHubEvidenceCredential(",
            "GitHubHTTPS", "os.environ", "merge(", "publish(",
        ):
            self.assertNotIn(forbidden, source)
        consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_evidence_composer.py":
                continue
            if "GitHubCompleteEvidenceComposer." in path.read_text():
                consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
