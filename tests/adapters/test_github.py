import unittest

from pathfinder_core.adapters.github import (
    AuthenticationError,
    CheckState,
    GitHubPublisher,
    PublicationState,
    PullRequest,
    RateLimitError,
)
from pathfinder_core.errors import PolicyError


class FixtureBackend:
    def __init__(self, checks=None, error=None, api_observations=None):
        self.checks = list(checks or [CheckState.SUCCESS])
        self.error = error
        self.api_observations = dict(api_observations or {})
        self.pr = None
        self.created = 0
        self.pushed = 0
        self.merge_attempts = 0

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


class GitHubPublisherTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
