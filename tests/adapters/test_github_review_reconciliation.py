import copy
import unittest

from pathfinder_core.adapters.github_graphql import (
    GraphQLConnection,
    GraphQLPullRequestSnapshot,
)
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)
from pathfinder_core.adapters.github_review_reconciliation import (
    GitHubReviewReconciler,
)


def audit(request_id):
    return RequestAudit(request_id, "2026-08-12T12:00:00+00:00")


def rest_review(
    review_id,
    actor_id,
    *,
    state="APPROVED",
    submitted_at="2026-08-12T11:00:00Z",
):
    return {
        "id": review_id,
        "node_id": f"PRR_{review_id}",
        "user": {
            "id": actor_id,
            "node_id": f"U_{actor_id}",
            "login": f"reviewer-{actor_id}",
            "type": "User",
        },
        "repository_permission": {
            "permission": "write",
            "user": {"id": actor_id, "login": f"reviewer-{actor_id}"},
        },
        "state": state,
        "commit_id": "c" * 40,
        "submitted_at": submitted_at,
        "author_association": "MEMBER",
        "dismissed": state == "DISMISSED",
    }


def graph_review(rest):
    return {
        "id": rest["id"],
        "node_id": rest["node_id"],
        "state": rest["state"],
        "submitted_at": rest["submitted_at"].replace("Z", "+00:00"),
        "commit_sha": rest["commit_id"],
        "author_association": rest["author_association"],
        "actor_id": rest["user"]["id"],
        "actor_node_id": rest["user"]["node_id"],
        "actor_login": rest["user"]["login"],
        "actor_type": rest["user"]["type"],
    }


def rest_page(*items, complete=True):
    return PageResponse(
        items,
        1,
        len(items),
        complete,
        not complete,
        "next" if not complete else None,
        (audit("rest-1"),),
    )


def snapshot(*reviews, complete=True, request_id="graph-1"):
    connection = GraphQLConnection(
        reviews,
        1,
        len(reviews),
        complete,
        not complete,
        "next" if not complete else None,
    )
    empty = GraphQLConnection((), 1, 0, True, False, None)
    return GraphQLPullRequestSnapshot(
        repository={"id": 123},
        pull_request={"id": 72},
        latest_reviews=connection,
        review_requests=empty,
        review_threads=empty,
        requests=(audit(request_id),),
        rate_limits=(),
    )


class GitHubReviewReconcilerTests(unittest.TestCase):
    def test_matches_latest_opinionated_review_per_actor(self):
        old = rest_review(81, 44, submitted_at="2026-08-12T10:00:00Z")
        comment = rest_review(
            82,
            44,
            state="COMMENTED",
            submitted_at="2026-08-12T10:30:00Z",
        )
        current = rest_review(
            83,
            44,
            state="CHANGES_REQUESTED",
            submitted_at="2026-08-12T11:00:00Z",
        )
        other = rest_review(
            84, 55, submitted_at="2026-08-12T11:30:00Z"
        )
        matched = GitHubReviewReconciler.reconcile(
            rest_reviews=rest_page(old, comment, current, other),
            graphql=snapshot(graph_review(current), graph_review(other)),
        )
        self.assertEqual(matched, (83, 84))

    def test_exact_review_actor_and_commit_drift_fail_closed(self):
        rest = rest_review(81, 44)
        for field, value in (
            ("node_id", "PRR_other"),
            ("state", "CHANGES_REQUESTED"),
            ("commit_sha", "d" * 40),
            ("author_association", "COLLABORATOR"),
            ("actor_node_id", "U_other"),
            ("actor_login", "other"),
        ):
            graph = graph_review(rest)
            graph[field] = value
            with self.assertRaises(GitHubObservationError) as caught:
                GitHubReviewReconciler.reconcile(
                    rest_reviews=rest_page(rest), graphql=snapshot(graph)
                )
            self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

    def test_missing_extra_and_duplicate_latest_actor_fail_closed(self):
        first = rest_review(81, 44)
        second = rest_review(
            82, 55, submitted_at="2026-08-12T11:30:00Z"
        )
        variants = (
            snapshot(graph_review(first)),
            snapshot(
                graph_review(first), graph_review(second),
                {**graph_review(second), "id": 83},
            ),
        )
        for graph in variants:
            with self.assertRaises(GitHubObservationError):
                GitHubReviewReconciler.reconcile(
                    rest_reviews=rest_page(first, second), graphql=graph
                )

    def test_incomplete_reused_request_and_nonchronological_views_fail_closed(self):
        first = rest_review(81, 44, submitted_at="2026-08-12T11:00:00Z")
        earlier = rest_review(82, 55, submitted_at="2026-08-12T10:00:00Z")
        cases = (
            (rest_page(first, complete=False), snapshot(graph_review(first))),
            (rest_page(first), snapshot(graph_review(first), complete=False)),
            (
                rest_page(first),
                snapshot(graph_review(first), request_id="rest-1"),
            ),
            (
                rest_page(first, earlier),
                snapshot(graph_review(first), graph_review(earlier)),
            ),
        )
        for rest, graph in cases:
            with self.assertRaises(GitHubObservationError):
                GitHubReviewReconciler.reconcile(
                    rest_reviews=rest, graphql=graph
                )

    def test_input_documents_are_not_mutated(self):
        rest = rest_review(81, 44)
        graph = graph_review(rest)
        rest_document = rest_page(rest)
        graph_document = snapshot(graph)
        before_rest = copy.deepcopy(rest_document)
        before_graph = copy.deepcopy(graph_document)
        GitHubReviewReconciler.reconcile(
            rest_reviews=rest_document, graphql=graph_document
        )
        self.assertEqual(rest_document, before_rest)
        self.assertEqual(graph_document, before_graph)


if __name__ == "__main__":
    unittest.main()
