import copy
import tempfile
import unittest
from pathlib import Path

from pathfinder_core.adapters.github import CheckState, GitHubPublisher, PullRequest
from pathfinder_core.errors import StateError
from pathfinder_core.operations import OperationJournal
from tests.adapters.test_github import FixtureBackend, publish
from tests.contracts.test_mission_schemas import fixture


class LostCreateResponseBackend(FixtureBackend):
    def __init__(self):
        super().__init__()
        self.lost = False

    def create_pull_request(self, head, base, mission_id, title, body):
        self.created += 1
        self.pr = PullRequest(
            "pr_12345678", "https://github.com/example/repo/pull/1",
            head, base, mission_id,
        )
        if not self.lost:
            self.lost = True
            raise RuntimeError("response lost after PR creation")
        return self.pr


class PersistentSideEffectBackend:
    def __init__(self):
        self.pushes = 0
        self.polls = 0

    def push_with_lost_response(self):
        self.pushes += 1
        raise RuntimeError("response lost after push")

    def poll_with_lost_response(self):
        self.polls += 1
        raise RuntimeError("response lost after poll")


def intent(action_kind, stage, operation_id):
    document = copy.deepcopy(fixture("operation-intent.valid.json"))
    document.update(
        operation_id=operation_id, action_kind=action_kind, stage=stage
    )
    return document


def refuse_pending(journal, operation_id, callback):
    loaded = journal.load(operation_id)
    if loaded["state"] == "pending":
        raise StateError("reconcile-required before publication retry")
    callback()


class PublicationCrashTests(unittest.TestCase):
    def test_lost_pr_create_response_reuses_exact_existing_pr(self):
        backend = LostCreateResponseBackend()
        with self.assertRaises(RuntimeError):
            publish(backend)
        result = publish(backend)
        self.assertTrue(result.reused)
        self.assertEqual(result.pull_request.pr_id, "pr_12345678")
        self.assertEqual(backend.created, 1)

    def test_ambiguous_push_and_poll_are_not_blindly_replayed(self):
        for action_kind, stage, method in (
            ("push", "publication", "push_with_lost_response"),
            ("poll-checks", "publication", "poll_with_lost_response"),
        ):
            with self.subTest(action=action_kind), tempfile.TemporaryDirectory() as directory:
                journal = OperationJournal(Path(directory))
                operation_id = f"operation_{action_kind.replace('-', '_')}_12345678"
                journal.record_intent(intent(action_kind, stage, operation_id))
                backend = PersistentSideEffectBackend()
                with self.assertRaises(RuntimeError):
                    getattr(backend, method)()
                with self.assertRaisesRegex(StateError, "reconcile-required"):
                    refuse_pending(journal, operation_id, getattr(backend, method))
                count = backend.pushes if action_kind == "push" else backend.polls
                self.assertEqual(count, 1)

    def test_check_polling_remains_bounded(self):
        backend = FixtureBackend([CheckState.PENDING])
        result = GitHubPublisher(backend).publish(
            head="pathfinder/auto/test-goal", base="main",
            mission_id="mission_12345678", title="Test", body="fixture",
            max_check_polls=2, credential_boundary="publication-only",
        )
        self.assertEqual(result.polls, 2)


if __name__ == "__main__":
    unittest.main()
