import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pathfinder_core.adapters.github import (
    CheckObservation,
    CheckState,
    GitHubPublisher,
    PublicationTarget,
    PullRequest,
    PullRequestIdentity,
)
from pathfinder_core.errors import PolicyError, StateError
from pathfinder_core.publication_controller import (
    PublicationController,
    VerifiedPublicationEnvelope,
)
from pathfinder_core.publication_journal import PublicationJournal


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)
STARTED = datetime.fromisoformat("2026-08-11T12:05:00+00:00")
OBSERVED = datetime.fromisoformat("2026-08-11T12:06:00+00:00")
AFTER_EXPIRY = datetime.fromisoformat("2026-08-11T13:00:00+00:00")


class EnvelopeReader:
    def __init__(self, envelope):
        self.envelope = envelope
        self.calls = []

    def read_fresh_verified(self, envelope_id, *, now):
        self.calls.append((envelope_id, now))
        return self.envelope


class ExactBackend:
    def __init__(
        self, *, checks=None, lose_create_response=False, preflight=None
    ):
        self.checks = list(checks or [CheckState.SUCCESS])
        self.lose_create_response = lose_create_response
        self.pr = None
        self.finds = 0
        self.pushes = 0
        self.creates = 0
        self.polls = 0
        self.preflight_result = preflight
        self.targets = []

    @staticmethod
    def exact_pull(head, base, mission_id):
        return PullRequest(
            "pr_example1",
            "https://github.com/example-owner/example-repo/pull/72",
            head,
            base,
            mission_id,
            PullRequestIdentity(
                123456789,
                "R_kgDOExample1",
                987654321,
                "PR_kwDOExample1",
                72,
                "c" * 40,
                "b" * 40,
            ),
        )

    def find_pull_request(self, head, base, mission_id):
        self.finds += 1
        if self.pr and (self.pr.head, self.pr.base, self.pr.mission_id) == (
            head,
            base,
            mission_id,
        ):
            return self.pr
        return None

    def push(self, branch):
        self.pushes += 1

    def create_pull_request(self, head, base, mission_id, title, body):
        del title, body
        self.creates += 1
        self.pr = self.exact_pull(head, base, mission_id)
        if self.lose_create_response:
            self.lose_create_response = False
            raise RuntimeError("lost create response")
        return self.pr

    def check_state(self, pull_request):
        del pull_request
        self.polls += 1
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
        return self.find_pull_request(
            target.head_ref, target.base_ref, target.mission_id
        )

    def create_pull_request_exact(self, target, title, body):
        self.targets.append(target)
        return self.create_pull_request(
            target.head_ref,
            target.base_ref,
            target.mission_id,
            title,
            body,
        )

    def check_observations_exact(self, pull_request, target):
        state = self.check_state(pull_request)
        return tuple(
            CheckObservation(check.context, check.app_id, target.head_sha, state)
            for check in target.required_checks
        )


class NoIdentityBackend(ExactBackend):
    @staticmethod
    def exact_pull(head, base, mission_id):
        return PullRequest(
            "pr_example1",
            "https://github.com/example-owner/example-repo/pull/72",
            head,
            base,
            mission_id,
        )


class DispatchWriteCrashJournal(PublicationJournal):
    def _write_once(self, path, document, label):
        recorded = super()._write_once(path, document, label)
        if label == "publication dispatch":
            raise RuntimeError("crash after durable dispatch")
        return recorded


class PublicationControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.bundle = json.loads(FIXTURE.read_text())
        self.request = self.bundle["request"]
        self.envelope = VerifiedPublicationEnvelope(
            "publication_envelope_example1",
            "authenticated-host-storage",
            STARTED.isoformat(),
            self.request,
        )

    def controller(self, backend, *, envelope=None, journal=None, times=None):
        reader = EnvelopeReader(envelope or self.envelope)
        moments = iter(times or (STARTED, OBSERVED))
        controller = PublicationController(
            journal or PublicationJournal(Path(self.temporary.name)),
            reader,
            GitHubPublisher(backend),
            clock=lambda: next(moments),
        )
        return controller, reader

    def test_success_persists_exact_receipt_and_replay_has_zero_calls(self):
        backend = ExactBackend()
        controller, reader = self.controller(backend)
        first = controller.publish(
            self.request["publication_request_id"],
            self.envelope.envelope_id,
        )
        second = controller.publish(
            self.request["publication_request_id"],
            "unused-on-replay",
        )
        self.assertEqual(first, second)
        self.assertEqual(first.state, "awaiting-review")
        self.assertEqual(first.receipt, self.bundle["receipt"])
        self.assertEqual((backend.pushes, backend.creates), (1, 1))
        self.assertEqual(reader.calls, [(self.envelope.envelope_id, STARTED)])

    def test_lost_create_response_reconciles_read_only(self):
        backend = ExactBackend(lose_create_response=True)
        controller, _reader = self.controller(backend)
        with self.assertRaisesRegex(RuntimeError, "lost create"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
            )
        self.assertEqual((backend.pushes, backend.creates), (1, 1))
        pending = controller.publish(
            self.request["publication_request_id"],
            self.envelope.envelope_id,
        )
        self.assertEqual(pending.state, "reconcile-required")
        self.assertEqual((backend.pushes, backend.creates), (1, 1))

        result = controller.reconcile(self.request["publication_request_id"])
        self.assertEqual(result.state, "awaiting-review")
        self.assertTrue(result.receipt["reused"])
        self.assertEqual((backend.pushes, backend.creates), (1, 1))

    def test_late_reconciliation_is_read_only_and_records_actual_time(self):
        backend = ExactBackend(lose_create_response=True)
        controller, _reader = self.controller(
            backend, times=(STARTED, AFTER_EXPIRY)
        )
        with self.assertRaisesRegex(RuntimeError, "lost create"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
            )
        result = controller.reconcile(self.request["publication_request_id"])
        self.assertEqual(result.state, "awaiting-review")
        self.assertEqual(
            result.receipt["observed_at"], AFTER_EXPIRY.isoformat()
        )
        self.assertEqual((backend.pushes, backend.creates), (1, 1))

    def test_crash_after_dispatch_marker_never_blindly_publishes(self):
        backend = ExactBackend()
        root = Path(self.temporary.name)
        crashing = DispatchWriteCrashJournal(root)
        controller, _reader = self.controller(backend, journal=crashing)
        with self.assertRaisesRegex(RuntimeError, "durable dispatch"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
            )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates, backend.polls),
            (0, 0, 0, 0),
        )

        restarted, _reader = self.controller(
            backend, journal=PublicationJournal(root)
        )
        result = restarted.reconcile(self.request["publication_request_id"])
        self.assertEqual(
            (result.state, result.reason),
            ("reconcile-required", "exact pull request not found"),
        )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates, backend.polls),
            (1, 0, 0, 0),
        )

    def test_request_without_dispatch_reconciles_without_network(self):
        backend = ExactBackend()
        journal = PublicationJournal(Path(self.temporary.name))
        self.assertIsNotNone(journal.claim_request(self.request))
        controller, _reader = self.controller(backend, journal=journal)
        result = controller.reconcile(self.request["publication_request_id"])
        self.assertEqual(result.reason, "dispatch-not-started")
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates, backend.polls),
            (0, 0, 0, 0),
        )

    def test_definitive_check_failure_is_not_replayed(self):
        backend = ExactBackend(checks=[CheckState.FAILURE])
        controller, _reader = self.controller(backend)
        first = controller.publish(
            self.request["publication_request_id"],
            self.envelope.envelope_id,
        )
        self.assertEqual(first.state, "checks-failed")
        counts = (backend.finds, backend.pushes, backend.creates, backend.polls)
        second = controller.publish(
            self.request["publication_request_id"],
            self.envelope.envelope_id,
        )
        self.assertEqual(
            (second.state, second.reason),
            ("reconcile-required", "pending-publication"),
        )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates, backend.polls),
            counts,
        )

    def test_reconcile_missing_exact_pr_never_mutates(self):
        backend = ExactBackend()
        journal = PublicationJournal(Path(self.temporary.name))
        claim = journal.claim_request(self.request)
        self.assertIsNotNone(claim)
        journal.dispatch_once(
            claim,
            started_at=STARTED.isoformat(),
            send=lambda: None,
        )
        controller, _reader = self.controller(backend, journal=journal)
        result = controller.reconcile(self.request["publication_request_id"])
        self.assertEqual(
            (result.state, result.reason),
            ("reconcile-required", "exact pull request not found"),
        )
        self.assertEqual((backend.pushes, backend.creates), (0, 0))

    def test_incomplete_or_wrong_object_identity_never_writes_receipt(self):
        for backend in (NoIdentityBackend(), ExactBackend()):
            with self.subTest(backend=type(backend).__name__), tempfile.TemporaryDirectory() as root:
                if isinstance(backend, ExactBackend) and not isinstance(
                    backend, NoIdentityBackend
                ):
                    original = backend.exact_pull

                    def wrong(head, base, mission_id):
                        value = original(head, base, mission_id)
                        return PullRequest(
                            value.pr_id,
                            value.url,
                            value.head,
                            value.base,
                            value.mission_id,
                            PullRequestIdentity(
                                1,
                                value.identity.repository_node_id,
                                value.identity.id,
                                value.identity.node_id,
                                value.identity.number,
                                value.identity.head_sha,
                                value.identity.base_sha,
                            ),
                        )

                    backend.exact_pull = wrong
                journal = PublicationJournal(Path(root))
                controller, _reader = self.controller(backend, journal=journal)
                with self.assertRaisesRegex(PolicyError, "identity"):
                    controller.publish(
                        self.request["publication_request_id"],
                        self.envelope.envelope_id,
                    )
                self.assertIsNone(
                    journal.load(self.request["publication_request_id"])["receipt"]
                )

    def test_wrong_preflight_target_stops_before_remote_effects(self):
        target = PublicationController._target(self.request)
        wrong = PublicationTarget(
            1,
            target.repository_node_id,
            target.repository_owner,
            target.repository_name,
            target.head_ref,
            target.head_sha,
            target.base_ref,
            target.base_sha,
            target.mission_id,
            target.diff_sha256,
            target.changed_files_sha256,
            target.object_evidence_sha256,
            target.required_checks,
        )
        backend = ExactBackend(preflight=wrong)
        controller, _reader = self.controller(backend)
        with self.assertRaisesRegex(PolicyError, "preflight target"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
            )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates, backend.polls),
            (0, 0, 0, 0),
        )

    def test_wrong_check_identity_never_writes_receipt(self):
        cases = (
            (
                "context/app",
                "ci/untrusted",
                999,
                self.request["candidate"]["head_sha"],
            ),
            ("sha", "ci/pathfinder", 24680, "d" * 40),
        )
        for name, context, app_id, sha in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                backend = ExactBackend()

                def wrong_checks(pull_request, target):
                    del pull_request, target
                    backend.polls += 1
                    return (
                        CheckObservation(
                            context, app_id, sha, CheckState.SUCCESS
                        ),
                    )

                backend.check_observations_exact = wrong_checks
                journal = PublicationJournal(Path(root))
                controller, _reader = self.controller(backend, journal=journal)
                with self.assertRaisesRegex(PolicyError, "check identity"):
                    controller.publish(
                        self.request["publication_request_id"],
                        self.envelope.envelope_id,
                    )
                self.assertIsNone(
                    journal.load(
                        self.request["publication_request_id"]
                    )["receipt"]
                )

    def test_untrusted_stale_or_mismatched_envelope_fails_before_backend(self):
        cases = []
        untrusted = copy.copy(self.envelope)
        object.__setattr__(untrusted, "source", "repository-file")
        cases.append((untrusted, STARTED, "authenticated host"))
        stale = copy.copy(self.envelope)
        object.__setattr__(
            stale, "authenticated_at", "2026-08-11T12:04:59+00:00"
        )
        cases.append((stale, STARTED, "stale"))
        changed = copy.deepcopy(self.request)
        changed["mission"]["commit_sha"] = "a" * 40
        mismatched = copy.copy(self.envelope)
        object.__setattr__(mismatched, "request", changed)
        cases.append((mismatched, STARTED, "commit and head"))

        for envelope, _now, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as root:
                backend = ExactBackend()
                controller, _reader = self.controller(
                    backend,
                    envelope=envelope,
                    journal=PublicationJournal(Path(root)),
                )
                with self.assertRaisesRegex(StateError, message):
                    controller.publish(
                        self.request["publication_request_id"],
                        envelope.envelope_id,
                    )
                self.assertEqual(
                    (backend.finds, backend.pushes, backend.creates),
                    (0, 0, 0),
                )

    def test_expired_authorization_cannot_be_backdated_by_caller(self):
        backend = ExactBackend()
        controller, _reader = self.controller(
            backend, times=(AFTER_EXPIRY,)
        )
        with self.assertRaisesRegex(TypeError, "unexpected keyword"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
                now=STARTED,
            )
        with self.assertRaisesRegex(StateError, "stale"):
            controller.publish(
                self.request["publication_request_id"],
                self.envelope.envelope_id,
            )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates),
            (0, 0, 0),
        )

    def test_non_publication_authorization_fails_before_backend(self):
        changed = copy.deepcopy(self.request)
        changed["authorization"]["publication_target"] = "local-branch"
        envelope = copy.copy(self.envelope)
        object.__setattr__(envelope, "request", changed)
        backend = ExactBackend()
        controller, _reader = self.controller(backend, envelope=envelope)
        with self.assertRaisesRegex(StateError, "explicitly authorized"):
            controller.publish(
                self.request["publication_request_id"],
                envelope.envelope_id,
            )
        self.assertEqual(
            (backend.finds, backend.pushes, backend.creates),
            (0, 0, 0),
        )


if __name__ == "__main__":
    unittest.main()
