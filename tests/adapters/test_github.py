import unittest
from dataclasses import replace

from pathfinder_core.adapters.github import (
    AuthenticationError,
    CheckObservation,
    CheckState,
    GitHubPublisher,
    PublicationState,
    PublicationTarget,
    PullRequest,
    PullRequestIdentity,
    RateLimitError,
    RequiredCheck,
)
from pathfinder_core.errors import PolicyError


class FixtureBackend:
    def __init__(
        self,
        checks=None,
        error=None,
        api_observations=None,
        preflight_result=None,
    ):
        self.checks = list(checks or [CheckState.SUCCESS])
        self.error = error
        self.api_observations = dict(api_observations or {})
        self.pr = None
        self.created = 0
        self.pushed = 0
        self.merge_attempts = 0
        self.preflight_result = preflight_result
        self.targets = []

    def _raise(self):
        if self.error:
            raise self.error("fixture error")

    def push(self, branch):
        self._raise()
        self.pushed += 1

    def find_pull_request(self, head, base, mission_id):
        self._raise()
        if self.pr and (self.pr.head, self.pr.base, self.pr.mission_id) == (head, base, mission_id):
            return self.pr
        return None

    def create_pull_request(self, head, base, mission_id, title, body):
        self._raise()
        self.created += 1
        self.pr = PullRequest("pr_12345678", "https://github.com/example/repo/pull/1", head, base, mission_id)
        return self.pr

    def check_state(self, pull_request):
        self._raise()
        if len(self.checks) > 1:
            return self.checks.pop(0)
        return self.checks[0]

    def preflight(self, target):
        self.targets.append(target)
        return self.preflight_result or target

    def push_exact(self, target):
        self.targets.append(target)
        self.push(target.head_ref)

    def find_pull_request_exact(self, target):
        self.targets.append(target)
        if self.pr and (
            self.pr.head,
            self.pr.base,
            self.pr.mission_id,
        ) == (target.head_ref, target.base_ref, target.mission_id):
            return self.pr
        return None

    def create_pull_request_exact(self, target, title, body):
        del title, body
        self.targets.append(target)
        self.created += 1
        self.pr = PullRequest(
            "pr_12345678",
            "https://github.com/example/repo/pull/1",
            target.head_ref,
            target.base_ref,
            target.mission_id,
            PullRequestIdentity(
                target.repository_id,
                target.repository_node_id,
                1,
                "PR_node_1",
                1,
                target.head_sha,
                target.base_sha,
            ),
        )
        return self.pr

    def check_observations_exact(self, pull_request, target):
        state = self.check_state(pull_request)
        return tuple(
            CheckObservation(
                check.context, check.app_id, target.head_sha, state
            )
            for check in target.required_checks
        )

    def merge(self, pull_request):
        self.merge_attempts += 1
        raise AssertionError("awaiting-review publisher must never merge")


def publish(backend, **overrides):
    arguments = {
        "head": "pathfinder/auto/test-goal", "base": "main",
        "mission_id": "mission_12345678", "title": "Test", "body": "Mission mission_12345678",
        "max_check_polls": 3, "credential_boundary": "publication-only",
    }
    arguments.update(overrides)
    return GitHubPublisher(backend).publish(**arguments)


def exact_target():
    return PublicationTarget(
        123,
        "R_repo123",
        "example-owner",
        "example-repo",
        "pathfinder/auto/test-goal",
        "a" * 40,
        "main",
        "b" * 40,
        "mission_12345678",
        "1" * 64,
        "2" * 64,
        "3" * 64,
        (RequiredCheck("ci/pathfinder", 24680),),
        97531,
        "U_publication_bot",
        "pathfinder-publication[bot]",
    )


def publish_exact(backend, **overrides):
    arguments = {
        "target": exact_target(),
        "title": "Test",
        "body": "Mission mission_12345678",
        "max_check_polls": 3,
        "credential_boundary": "publication-only",
    }
    arguments.update(overrides)
    return GitHubPublisher(backend).publish_exact(**arguments)


class GitHubPublisherTests(unittest.TestCase):
    def test_exact_publication_binds_target_and_check_identity(self):
        backend = FixtureBackend()
        result = publish_exact(backend)
        self.assertEqual(result.state, PublicationState.AWAITING_REVIEW)
        self.assertEqual(result.checks[0].sha, exact_target().head_sha)
        self.assertTrue(all(target == exact_target() for target in backend.targets))

    def test_exact_preflight_mismatch_stops_before_mutation(self):
        target = exact_target()
        wrong = replace(target, repository_id=999)
        backend = FixtureBackend(preflight_result=wrong)
        with self.assertRaisesRegex(PolicyError, "preflight target"):
            publish_exact(backend, target=target)
        self.assertEqual((backend.pushed, backend.created), (0, 0))

    def test_invalid_publication_actor_stops_before_mutation(self):
        cases = (
            replace(exact_target(), publication_actor_id=0),
            replace(exact_target(), publication_actor_id=True),
            replace(exact_target(), publication_actor_node_id=""),
            replace(exact_target(), publication_actor_node_id="not a node"),
            replace(exact_target(), publication_actor_login="human-user"),
        )
        for target in cases:
            with self.subTest(target=target):
                backend = FixtureBackend()
                with self.assertRaisesRegex(
                    PolicyError, "invalid exact publication target"
                ):
                    publish_exact(backend, target=target)
                self.assertEqual((backend.pushed, backend.created), (0, 0))

    def test_exact_check_context_app_and_sha_must_match(self):
        cases = (
            CheckObservation("ci/untrusted", 999, "a" * 40, CheckState.SUCCESS),
            CheckObservation("ci/pathfinder", 24680, "c" * 40, CheckState.SUCCESS),
            CheckObservation("ci/pathfinder", 24680, "a" * 40, "success"),
        )
        for observation in cases:
            with self.subTest(observation=observation):
                backend = FixtureBackend()
                backend.check_observations_exact = (
                    lambda pull_request, target: (observation,)
                )
                with self.assertRaisesRegex(PolicyError, "check identity"):
                    publish_exact(backend)

    def test_success_stops_at_awaiting_review(self):
        result = publish(FixtureBackend())
        self.assertEqual(result.state, PublicationState.AWAITING_REVIEW)
        self.assertIn("human review", result.detail)

    def test_resume_reuses_existing_pull_request(self):
        backend = FixtureBackend()
        first = publish(backend)
        second = publish(backend)
        self.assertEqual(first.pull_request.url, second.pull_request.url)
        self.assertTrue(second.reused)
        self.assertEqual(backend.created, 1)

    def test_auth_and_rate_limit_are_explicit(self):
        for error, state in [
            (AuthenticationError, PublicationState.AUTH_ERROR),
            (RateLimitError, PublicationState.RATE_LIMITED),
        ]:
            with self.subTest(state=state):
                self.assertEqual(publish(FixtureBackend(error=error)).state, state)

    def test_pending_checks_time_out_with_bound(self):
        result = publish(FixtureBackend([CheckState.PENDING]), max_check_polls=2)
        self.assertEqual(result.state, PublicationState.CHECK_TIMEOUT)
        self.assertEqual(result.polls, 2)

    def test_failed_checks_do_not_publish_success(self):
        result = publish(FixtureBackend([CheckState.FAILURE]))
        self.assertEqual(result.state, PublicationState.CHECKS_FAILED)

    def test_forge_policy_and_mergeability_fixtures_never_trigger_merge(self):
        scenarios = {
            "branch-protection-enabled": {
                "branch_protection": {"required_status_checks": {"strict": True}},
            },
            "branch-protection-absent": {"branch_protection": None},
            "repository-ruleset-active": {
                "rulesets": [{"id": 123, "enforcement": "active"}],
            },
            "merge-conflict": {"mergeable": False, "mergeable_state": "dirty"},
        }
        for name, observations in scenarios.items():
            with self.subTest(scenario=name):
                backend = FixtureBackend(api_observations=observations)
                result = publish(backend)
                self.assertEqual(backend.api_observations, observations)
                self.assertEqual(result.state, PublicationState.AWAITING_REVIEW)
                self.assertEqual(backend.created, 1)
                self.assertEqual(backend.merge_attempts, 0)

    def test_credentials_must_be_publication_only(self):
        with self.assertRaisesRegex(PolicyError, "publication-only"):
            publish(FixtureBackend(), credential_boundary="shared-with-tests")

    def test_observe_is_read_only_and_never_creates_missing_pull_request(self):
        backend = FixtureBackend()
        result = GitHubPublisher(backend).observe(
            head="pathfinder/auto/test-goal",
            base="main",
            mission_id="mission_12345678",
            credential_boundary="publication-only",
        )
        self.assertEqual(result.state, PublicationState.API_UNAVAILABLE)
        self.assertEqual((backend.pushed, backend.created), (0, 0))

        backend.pr = PullRequest(
            "pr_12345678",
            "https://github.com/example/repo/pull/1",
            "pathfinder/auto/test-goal",
            "main",
            "mission_12345678",
        )
        result = GitHubPublisher(backend).observe(
            head="pathfinder/auto/test-goal",
            base="main",
            mission_id="mission_12345678",
            credential_boundary="publication-only",
        )
        self.assertEqual(result.state, PublicationState.AWAITING_REVIEW)
        self.assertEqual((backend.pushed, backend.created), (0, 0))


if __name__ == "__main__":
    unittest.main()
