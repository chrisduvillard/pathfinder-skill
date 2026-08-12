import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from pathfinder_core.adapters.github_graphql import (
    GraphQLConnection,
    GraphQLPullRequestSnapshot,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)
from pathfinder_core.adapters.github_publication_reconciliation import (
    GitHubPublicationReconciler,
)
from pathfinder_core.storage import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)


def snapshot(receipt):
    repository = receipt["repository"]
    pull = receipt["pull_request"]
    empty = GraphQLConnection((), 1, 0, True, False, None)
    return GraphQLPullRequestSnapshot(
        repository=copy.deepcopy(repository),
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
        latest_reviews=empty,
        review_requests=empty,
        review_threads=empty,
        requests=(
            RequestAudit("graph-1", "2026-08-12T12:00:00+00:00"),
        ),
        rate_limits=(),
    )


class GitHubPublicationReconcilerTests(unittest.TestCase):
    def setUp(self):
        bundle = json.loads(FIXTURE.read_text())
        self.request = bundle["request"]
        self.receipt = bundle["receipt"]

    def test_projects_exact_authenticated_controller_pusher(self):
        proof = GitHubPublicationReconciler.reconcile(
            publication_request=self.request,
            publication_receipt=self.receipt,
            graphql=snapshot(self.receipt),
        )
        self.assertEqual(proof.last_pusher_id, 97531)
        self.assertEqual(proof.actor_node_id, "U_kgDOBot1234")
        self.assertEqual(proof.actor_login, "pathfinder-publication[bot]")
        self.assertEqual(proof.repository_id, 123456789)
        self.assertEqual(proof.pull_request_number, 72)
        self.assertEqual(proof.head_sha, "c" * 40)
        self.assertEqual(
            proof.publication_receipt_sha256,
            self.receipt["receipt_sha256"],
        )

    def test_repository_pull_ref_and_sha_drift_fail_closed(self):
        cases = (
            ("repository", "id", 1),
            ("repository", "node_id", "R_other"),
            ("pull_request", "id", 1),
            ("pull_request", "node_id", "PR_other"),
            ("pull_request", "number", 73),
            ("pull_request", "head_ref", "pathfinder/auto/other"),
            ("pull_request", "head_sha", "d" * 40),
            ("pull_request", "base_ref", "release"),
            ("pull_request", "base_sha", "e" * 40),
            ("pull_request", "head_repository_id", 1),
            ("pull_request", "base_repository_node_id", "R_other"),
        )
        for section, field, value in cases:
            with self.subTest(section=section, field=field):
                graph = snapshot(self.receipt)
                getattr(graph, section)[field] = value
                with self.assertRaises(GitHubObservationError) as caught:
                    GitHubPublicationReconciler.reconcile(
                        publication_request=self.request,
                        publication_receipt=self.receipt,
                        graphql=graph,
                    )
                self.assertEqual(
                    caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN
                )

    def test_receipt_hash_push_and_graphql_audit_drift_fail_closed(self):
        changed = copy.deepcopy(self.receipt)
        changed["head_push"]["actor_id"] += 1
        with self.assertRaises(GitHubObservationError):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=changed,
                graphql=snapshot(self.receipt),
            )

        changed["receipt_sha256"] = canonical_sha256(
            changed, "receipt_sha256"
        )
        with self.assertRaisesRegex(
            GitHubObservationError, "request and receipt identities differ"
        ):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=changed,
                graphql=snapshot(self.receipt),
            )

        graph = snapshot(self.receipt)
        graph = replace(
            graph,
            requests=(
                RequestAudit("same", "2026-08-12T12:00:00+00:00"),
                RequestAudit("same", "2026-08-12T12:01:00+00:00"),
            ),
        )
        with self.assertRaises(GitHubObservationError):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=self.receipt,
                graphql=graph,
            )

        graph = replace(
            snapshot(self.receipt),
            requests=(
                RequestAudit("graph-1", "2026-08-11T12:05:00+00:00"),
            ),
        )
        with self.assertRaisesRegex(
            GitHubObservationError, "predates publication"
        ):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=self.receipt,
                graphql=graph,
            )

        graph = replace(
            snapshot(self.receipt),
            requests=(
                RequestAudit("graph-1", "2026-08-11T12:05:00+00:00"),
                RequestAudit("graph-2", "2026-08-12T12:00:00+00:00"),
            ),
        )
        with self.assertRaisesRegex(
            GitHubObservationError, "predates publication"
        ):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=self.receipt,
                graphql=graph,
            )

    def test_rehashed_mission_diff_check_and_url_drift_fail_closed(self):
        cases = (
            ("mission", "mission_state_sha256", "8" * 64),
            ("diff", "diff_sha256", "9" * 64),
            ("check", "app_id", 13579),
            ("pull_request", "url", "https://github.com/owner/repo/pull/72"),
        )
        for section, field, value in cases:
            with self.subTest(section=section, field=field):
                changed = copy.deepcopy(self.receipt)
                target = (
                    changed["checks"]["observations"][0]
                    if section == "check"
                    else changed[section]
                )
                target[field] = value
                changed["receipt_sha256"] = canonical_sha256(
                    changed, "receipt_sha256"
                )
                with self.assertRaises(GitHubObservationError):
                    GitHubPublicationReconciler.reconcile(
                        publication_request=self.request,
                        publication_receipt=changed,
                        graphql=snapshot(self.receipt),
                    )

    def test_query_hash_and_observation_order_fail_closed(self):
        graph = replace(snapshot(self.receipt), query_sha256="0" * 64)
        with self.assertRaises(GitHubObservationError):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=self.receipt,
                graphql=graph,
            )

        graph = replace(
            snapshot(self.receipt),
            requests=(
                RequestAudit("graph-1", "2026-08-12T12:01:00+00:00"),
                RequestAudit("graph-2", "2026-08-12T12:00:00+00:00"),
            ),
        )
        with self.assertRaises(GitHubObservationError):
            GitHubPublicationReconciler.reconcile(
                publication_request=self.request,
                publication_receipt=self.receipt,
                graphql=graph,
            )

    def test_inputs_are_not_mutated(self):
        receipt = copy.deepcopy(self.receipt)
        graph = snapshot(receipt)
        before_receipt = copy.deepcopy(receipt)
        before_graph = copy.deepcopy(graph)
        GitHubPublicationReconciler.reconcile(
            publication_request=self.request,
            publication_receipt=receipt,
            graphql=graph,
        )
        self.assertEqual(receipt, before_receipt)
        self.assertEqual(graph, before_graph)


if __name__ == "__main__":
    unittest.main()
