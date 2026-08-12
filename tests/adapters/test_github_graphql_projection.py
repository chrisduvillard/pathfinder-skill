import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from pathfinder_core.adapters.github_graphql import (
    GraphQLConnection,
    GraphQLPullRequestSnapshot,
)
from pathfinder_core.adapters.github_graphql_projection import (
    GitHubGraphQLProjector,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)
from pathfinder_core.adapters.github_publication_reconciliation import (
    GitHubPublicationReconciler,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)


def connection(*items, pages=1, complete=True):
    return GraphQLConnection(
        items,
        pages,
        len(items),
        complete,
        not complete,
        None if complete else "next",
    )


def snapshot(receipt):
    repository = copy.deepcopy(receipt["repository"])
    pull = receipt["pull_request"]
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
        latest_reviews=connection(),
        review_requests=connection({
            "id": 91,
            "node_id": "PRRQ_node1",
            "reviewer": {"id": 44, "type": "Team"},
            "as_code_owner": True,
        }),
        review_threads=connection({
            "id": "PRRT_node1",
            "is_resolved": True,
            "is_outdated": False,
        }),
        requests=(
            RequestAudit(
                "graph-1", "2026-08-12T12:00:00+00:00", 'W/"graph-1"'
            ),
        ),
        rate_limits=({
            "cost": 1,
            "remaining": 4999,
            "resetAt": "2026-08-12T13:00:00+00:00",
        },),
    )


class GitHubGraphQLProjectorTests(unittest.TestCase):
    def setUp(self):
        bundle = json.loads(FIXTURE.read_text())
        self.request = bundle["request"]
        self.receipt = bundle["receipt"]
        self.graphql = snapshot(self.receipt)
        self.pusher = GitHubPublicationReconciler.reconcile(
            publication_request=self.request,
            publication_receipt=self.receipt,
            graphql=self.graphql,
        )

    def test_projects_complete_review_and_mergeability_evidence(self):
        projection = GitHubGraphQLProjector.project(
            graphql=self.graphql,
            controller_pusher=self.pusher,
        )
        self.assertEqual(projection.review_requests, ({
            "actor_id": 44,
            "actor_type": "Team",
            "as_code_owner": True,
        },))
        self.assertEqual(projection.review_threads, ({
            "node_id": "PRRT_node1",
            "resolved": True,
            "outdated": False,
        },))
        self.assertEqual(projection.mergeability, {
            "mergeable": "MERGEABLE",
            "merge_state_status": "CLEAN",
            "review_decision": "APPROVED",
            "queue_entry": False,
            "required_sha": "c" * 40,
        })
        self.assertEqual(
            projection.audits[0]["surface"], "graphql-pull-request"
        )
        self.assertEqual(projection.pagination["review_threads"]["items"], 1)

    def test_each_connection_must_be_complete_and_audit_covered(self):
        for field in ("latest_reviews", "review_requests", "review_threads"):
            with self.subTest(field=field):
                graph = replace(self.graphql, **{field: connection(complete=False)})
                with self.assertRaises(GitHubObservationError) as caught:
                    GitHubGraphQLProjector.project(
                        graphql=graph, controller_pusher=self.pusher
                    )
                self.assertEqual(
                    caught.exception.outcome,
                    ObservationOutcome.PAGINATION_INCOMPLETE,
                )

        graph = replace(self.graphql, rate_limits=())
        with self.assertRaises(GitHubObservationError):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

        graph = replace(
            self.graphql,
            review_threads=connection(
                *self.graphql.review_threads.items, pages=2
            ),
        )
        with self.assertRaises(GitHubObservationError):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

    def test_duplicate_reviewer_thread_and_request_id_fail_closed(self):
        review_request = self.graphql.review_requests.items[0]
        graph = replace(
            self.graphql,
            review_requests=connection(
                review_request,
                {**review_request, "id": 92, "node_id": "PRRQ_node2"},
            ),
        )
        with self.assertRaisesRegex(GitHubObservationError, "duplicated"):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

        graph = replace(
            self.graphql,
            review_requests=connection({**review_request, "node_id": "bad node"}),
        )
        with self.assertRaises(GitHubObservationError):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

        thread = self.graphql.review_threads.items[0]
        graph = replace(
            self.graphql,
            review_threads=connection(thread, copy.deepcopy(thread)),
        )
        with self.assertRaisesRegex(GitHubObservationError, "duplicated"):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

        graph = replace(
            self.graphql,
            requests=self.graphql.requests + self.graphql.requests,
            rate_limits=self.graphql.rate_limits + self.graphql.rate_limits,
        )
        with self.assertRaises(GitHubObservationError):
            GitHubGraphQLProjector.project(
                graphql=graph, controller_pusher=self.pusher
            )

    def test_exact_identity_state_and_publication_audit_drift_fail_closed(self):
        cases = (
            ("repository", "id", 1),
            ("pull_request", "head_sha", "d" * 40),
            ("pull_request", "mergeable", "FUTURE"),
        )
        for section, field, value in cases:
            with self.subTest(section=section, field=field):
                graph = copy.deepcopy(self.graphql)
                getattr(graph, section)[field] = value
                with self.assertRaises(GitHubObservationError):
                    GitHubGraphQLProjector.project(
                        graphql=graph, controller_pusher=self.pusher
                    )

        stale_proof = replace(
            self.pusher, graphql_observed_at="2026-08-12T12:01:00+00:00"
        )
        with self.assertRaises(GitHubObservationError):
            GitHubGraphQLProjector.project(
                graphql=self.graphql, controller_pusher=stale_proof
            )

    def test_inputs_are_not_mutated(self):
        graph = copy.deepcopy(self.graphql)
        pusher = copy.deepcopy(self.pusher)
        before = copy.deepcopy((graph, pusher))
        GitHubGraphQLProjector.project(
            graphql=graph, controller_pusher=pusher
        )
        self.assertEqual((graph, pusher), before)


if __name__ == "__main__":
    unittest.main()
