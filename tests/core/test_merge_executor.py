import copy
import json
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

from pathfinder_core.adapters.github_merge_writer import (
    MergeAPIResponse,
    MergeObservation,
    MergeResponseLost,
)
from pathfinder_core.errors import StateError
from pathfinder_core.merge_credentials import (
    MERGE_EXECUTOR_BOUNDARY,
    REQUIRED_MERGE_PERMISSIONS,
    GitHubMergeCredential,
)
from pathfinder_core.merge_executor import MergeExecutor, VerifiedMergeEnvelope
from pathfinder_core.merge_journal import MergeOperationJournal
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"
STARTED = datetime.fromisoformat("2026-08-11T12:08:30+00:00")
COMPLETED = datetime.fromisoformat("2026-08-11T12:08:40+00:00")
CREDENTIAL_ID = "merge_credential_example1"


def load(name):
    return json.loads((FIXTURES / name).read_text())


def credential():
    return GitHubMergeCredential(
        "ghs_fixture_token_1234567890",
        credential_receipt_id="merge_credential_receipt_example1",
        source="authenticated-host-credential-store",
        credential_id=CREDENTIAL_ID,
        kind="installation-token",
        boundary=MERGE_EXECUTOR_BOUNDARY,
        permissions=REQUIRED_MERGE_PERMISSIONS,
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
        verified_at="2026-08-11T12:08:30+00:00",
        repository_selection="selected",
        suspended=False,
    )


class EnvelopeReader:
    def __init__(self, envelope):
        self.envelope = envelope
        self.calls = []

    def read_fresh_verified(self, envelope_id, *, now):
        self.calls.append((envelope_id, now))
        return self.envelope


class CredentialReader:
    def __init__(self):
        self.calls = []

    def read_fresh_verified(self, credential_id, *, now):
        self.calls.append((credential_id, now))
        value = credential()
        object.__setattr__(value, "verified_at", now.isoformat())
        return value


class FixtureBackend:
    def __init__(self, response=None, observation=None, merge_error=None):
        self.response = response
        self.observation = observation or MergeObservation(None, False)
        self.merge_error = merge_error
        self.merge_calls = 0
        self.observe_calls = 0

    def merge(self, intent, merge_credential, *, dispatch):
        self.merge_calls += 1
        dispatch()
        if self.merge_error is not None:
            raise self.merge_error
        return self.response

    def observe(self, intent, merge_credential):
        self.observe_calls += 1
        return self.observation


class CrashBeforeIntentJournal(MergeOperationJournal):
    def claim_intent(self, **documents):
        raise RuntimeError("crash before intent")


class CrashAfterIntentJournal(MergeOperationJournal):
    def claim_intent(self, **documents):
        super().claim_intent(**documents)
        raise RuntimeError("crash after intent")


class CrashBeforeDispatchJournal(MergeOperationJournal):
    def dispatch_once(self, claim, *, started_at, send):
        del claim, started_at, send
        raise RuntimeError("crash before dispatch")


class CrashAfterDispatchPersistenceJournal(MergeOperationJournal):
    def _write_once(self, path, document, label):
        recorded = super()._write_once(path, document, label)
        if label == "merge dispatch":
            raise RuntimeError("crash after dispatch persistence")
        return recorded


class CrashBeforeResultJournal(MergeOperationJournal):
    def __init__(self, root):
        super().__init__(root)
        self.crash = True

    def record_result(self, result):
        if self.crash:
            self.crash = False
            raise RuntimeError("crash before result")
        return super().record_result(result)


class CrashAfterResultJournal(MergeOperationJournal):
    def __init__(self, root):
        super().__init__(root)
        self.crash = True

    def record_result(self, result):
        recorded = super().record_result(result)
        if self.crash:
            self.crash = False
            raise RuntimeError("crash after result")
        return recorded


class CrashAfterRemoteEffectBackend(FixtureBackend):
    def merge(self, intent, merge_credential, *, dispatch):
        self.merge_calls += 1
        dispatch()
        raise RuntimeError("crash after remote effect")


class CrashDuringPreparationBackend(FixtureBackend):
    def merge(self, intent, merge_credential, *, dispatch):
        del intent, merge_credential, dispatch
        self.merge_calls += 1
        raise RuntimeError("crash during request preparation")


class FinalTransportBoundaryBackend(FixtureBackend):
    def merge(self, intent, merge_credential, *, dispatch):
        del intent, merge_credential
        dispatch()
        self.merge_calls += 1
        return self.response


def response(status=200, *, merged=True, sha="d" * 40, malformed=False, headers=None):
    return MergeAPIResponse(
        status,
        "request_merge_response_example1",
        headers or {},
        {"merged": merged, "sha": sha, "message": "fixture"},
        malformed,
    )


def observation(**updates):
    document = {
        "repository_id": 123456789,
        "repository_node_id": "R_kgDOExample1",
        "pull_request_id": 987654321,
        "pull_request_node_id": "PR_kwDOExample1",
        "pull_request_number": 72,
        "state": "closed",
        "merged": True,
        "head_sha": "c" * 40,
        "head_repository_id": 123456789,
        "base_ref": "main",
        "base_repository_id": 123456789,
        "merge_commit_sha": "d" * 40,
        "merged_at": "2026-08-11T12:08:38+00:00",
        "merged_by": {
            "actor_id": 97531,
            "actor_node_id": "U_kgDOBot1234",
            "login": "pathfinder-merge[bot]",
        },
        "merge_endpoint_status": 204,
        "base_sha_after": "d" * 40,
        "merge_commit_parent_shas": ["b" * 40],
        "request_ids": [
            "request_pr_followup_example1",
            "request_merged_followup_example1",
            "request_base_followup_example1",
            "request_commit_followup_example1",
        ],
        "observed_at": "2026-08-11T12:08:39+00:00",
    }
    document.update(updates)
    return MergeObservation(document, True)


class MergeExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        authority = load("publication-contracts.json")
        bundle = load("publication-journal-contracts.json")
        self.envelope = VerifiedMergeEnvelope(
            envelope_id="merge_envelope_example1",
            source="authenticated-host-storage",
            authenticated_at="2026-08-11T12:08:30+00:00",
            policy=authority["policy"],
            authorization=authority["authorization"],
            protected_policy=ProtectedSurfaceRegistry.load().to_document(),
            initial_evidence=bundle["initial_evidence"],
            reread_evidence=bundle["evidence"],
            readiness_proof=bundle["readiness_proof"],
            intent=bundle["intent"],
        )
        self.operation_id = self.envelope.intent["operation_id"]

    def executor(self, backend, envelope=None, journal=None):
        reader = EnvelopeReader(envelope or self.envelope)
        executor = MergeExecutor(
            journal or MergeOperationJournal(Path(self.temporary.name)),
            reader,
            CredentialReader(),
            backend,
            clock=lambda: COMPLETED,
        )
        return executor, reader

    def test_confirmed_merge_is_terminal_and_second_call_has_zero_network(self):
        backend = FixtureBackend(response(), observation())
        executor, reader = self.executor(backend)
        first = executor.execute(
            self.operation_id, self.envelope.envelope_id, CREDENTIAL_ID, now=STARTED
        )
        second = executor.execute(
            self.operation_id, "unused-on-replay", CREDENTIAL_ID, now=STARTED
        )
        self.assertEqual(first.outcome, "merged")
        self.assertEqual(first.reason, "confirmed-merged")
        self.assertEqual(second.result, first.result)
        self.assertEqual(backend.merge_calls, 1)
        self.assertEqual(backend.observe_calls, 1)
        self.assertEqual(reader.calls, [(self.envelope.envelope_id, STARTED)])

    def test_concurrent_execution_allows_at_most_one_put(self):
        backend = FixtureBackend(response(), observation())
        journal = MergeOperationJournal(Path(self.temporary.name))
        executors = [
            self.executor(backend, journal=journal)[0] for _ in range(2)
        ]
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []

        def run(executor):
            try:
                barrier.wait()
                outcomes.append(
                    executor.execute(
                        self.operation_id,
                        self.envelope.envelope_id,
                        CREDENTIAL_ID,
                        now=STARTED,
                    )
                )
            except BaseException as error:
                failures.append(error)

        threads = [
            threading.Thread(target=run, args=(executor,))
            for executor in executors
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(backend.merge_calls, 1)
        self.assertTrue(any(item.outcome == "merged" for item in outcomes))
        self.assertTrue(
            all(isinstance(error, StateError) for error in failures)
        )

    def test_definitive_http_failures_are_typed_and_never_retried(self):
        cases = {
            401: ("auth-error", "authentication-failed"),
            403: ("permission-missing", "permission-denied"),
            404: ("permission-missing", "not-found"),
            409: ("not-merged", "head-mismatch"),
            422: ("not-merged", "validation-failed"),
            429: ("rate-limited", "rate-limit-exceeded"),
        }
        for status, expected in cases.items():
            with self.subTest(status=status), tempfile.TemporaryDirectory() as root:
                backend = FixtureBackend(response(status))
                executor, _reader = self.executor(
                    backend, journal=MergeOperationJournal(Path(root))
                )
                result = executor.execute(
                    self.operation_id,
                    self.envelope.envelope_id,
                    CREDENTIAL_ID,
                    now=STARTED,
                )
                self.assertEqual((result.outcome, result.reason), expected)
                self.assertEqual(backend.merge_calls, 1)
                self.assertEqual(backend.observe_calls, 0)

    def test_405_uses_exact_state_to_distinguish_already_merged(self):
        for merge_observation, expected in (
            (observation(), "already-merged"),
            (MergeObservation(None, False), "unmergeable"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as root:
                backend = FixtureBackend(response(405), merge_observation)
                executor, _reader = self.executor(
                    backend, journal=MergeOperationJournal(Path(root))
                )
                result = executor.execute(
                    self.operation_id,
                    self.envelope.envelope_id,
                    CREDENTIAL_ID,
                    now=STARTED,
                )
                self.assertEqual(
                    (result.outcome, result.reason), ("not-merged", expected)
                )
                self.assertIsNone(result.result["merge_proof"])
                self.assertEqual(backend.merge_calls, 1)
                self.assertEqual(backend.observe_calls, 1)

    def test_malformed_execution_time_fails_closed(self):
        backend = FixtureBackend(response())
        executor, _reader = self.executor(backend)
        with self.assertRaisesRegex(StateError, "execution time"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now="not-a-time",
            )
        self.assertEqual(backend.merge_calls, 0)

    def test_rate_limited_403_is_not_permission_missing(self):
        backend = FixtureBackend(
            response(403, headers={"x-ratelimit-remaining": "0"})
        )
        executor, _reader = self.executor(backend)
        result = executor.execute(
            self.operation_id, self.envelope.envelope_id, CREDENTIAL_ID, now=STARTED
        )
        self.assertEqual((result.outcome, result.reason), (
            "rate-limited", "rate-limit-exceeded"
        ))

    def test_response_loss_can_merge_only_with_exact_reconciliation_proof(self):
        backend = FixtureBackend(
            observation=observation(), merge_error=MergeResponseLost("lost")
        )
        executor, _reader = self.executor(backend)
        result = executor.execute(
            self.operation_id, self.envelope.envelope_id, CREDENTIAL_ID, now=STARTED
        )
        self.assertEqual((result.outcome, result.reason), (
            "merged", "confirmed-after-response-loss"
        ))
        self.assertEqual(backend.merge_calls, 1)
        self.assertEqual(backend.observe_calls, 1)

    def test_malformed_or_server_response_never_becomes_success(self):
        for api_response, expected in (
            (response(malformed=True), ("reconcile-required", "malformed-response")),
            (response(500), ("api-unavailable", "server-error")),
        ):
            with self.subTest(status=api_response.status), tempfile.TemporaryDirectory() as root:
                backend = FixtureBackend(api_response, observation())
                executor, _reader = self.executor(
                    backend, journal=MergeOperationJournal(Path(root))
                )
                result = executor.execute(
                    self.operation_id,
                    self.envelope.envelope_id,
                    CREDENTIAL_ID,
                    now=STARTED,
                )
                self.assertEqual((result.outcome, result.reason), expected)
                self.assertNotEqual(result.reason, "confirmed-merged")
                self.assertEqual(backend.merge_calls, 1)
                self.assertEqual(backend.observe_calls, 1)

    def test_pending_intent_is_not_replayed_and_explicit_reconcile_sends_no_put(self):
        backend = FixtureBackend(response(), merge_error=RuntimeError("crash before send"))
        executor, _reader = self.executor(backend)
        with self.assertRaisesRegex(RuntimeError, "crash"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        pending = executor.execute(
            self.operation_id, self.envelope.envelope_id, CREDENTIAL_ID, now=STARTED
        )
        self.assertEqual((pending.outcome, pending.reason), (
            "reconcile-required", "pending-intent"
        ))
        self.assertEqual(backend.merge_calls, 1)

        with self.assertRaisesRegex(StateError, "reconciliation time"):
            executor.reconcile(
                self.operation_id, CREDENTIAL_ID, now="not-a-time"
            )
        self.assertEqual(backend.observe_calls, 0)

        backend.observation = observation()
        reconciled = executor.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (reconciled.outcome, reconciled.reason),
            ("reconcile-required", "transport-ambiguous"),
        )
        self.assertEqual(backend.merge_calls, 1)
        self.assertEqual(backend.observe_calls, 1)

    def test_crash_before_intent_has_zero_merge_calls(self):
        backend = FixtureBackend(response(), observation())
        journal = CrashBeforeIntentJournal(Path(self.temporary.name))
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "before intent"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertEqual(backend.merge_calls, 0)
        self.assertFalse(journal.intent_exists(self.operation_id))

    def test_crash_after_intent_before_send_leaves_pending_without_put(self):
        backend = FixtureBackend(response(), observation())
        journal = CrashAfterIntentJournal(Path(self.temporary.name))
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "after intent"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertEqual(backend.merge_calls, 0)
        self.assertTrue(journal.intent_exists(self.operation_id))
        result = executor.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (result.outcome, result.reason),
            ("reconcile-required", "dispatch-not-started"),
        )
        self.assertEqual(backend.observe_calls, 0)
        self.assertEqual(
            executor.credentials.calls, [(CREDENTIAL_ID, STARTED)]
        )

    def test_crash_before_capability_guarded_dispatch_cannot_be_credited(self):
        backend = FixtureBackend(response(), observation())
        journal = CrashBeforeDispatchJournal(Path(self.temporary.name))
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "before dispatch"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        loaded = journal.load(self.operation_id)
        self.assertIsNone(loaded["dispatch"])
        self.assertEqual(backend.merge_calls, 0)
        result = executor.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (result.outcome, result.reason),
            ("reconcile-required", "dispatch-not-started"),
        )
        self.assertEqual(backend.observe_calls, 0)

    def test_backend_preparation_crash_cannot_be_credited(self):
        backend = CrashDuringPreparationBackend(response(), observation())
        executor, _reader = self.executor(backend)
        with self.assertRaisesRegex(RuntimeError, "request preparation"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        loaded = executor.journal.load(self.operation_id)
        self.assertIsNone(loaded["dispatch"])
        result = executor.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(result.reason, "dispatch-not-started")
        self.assertEqual(backend.observe_calls, 0)

    def test_crash_after_marker_before_transport_is_never_credited(self):
        journal = CrashAfterDispatchPersistenceJournal(Path(self.temporary.name))
        backend = FinalTransportBoundaryBackend(response(), observation())
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "after dispatch persistence"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertIsNotNone(journal.load(self.operation_id)["dispatch"])
        self.assertEqual(backend.merge_calls, 0)

        restarted_backend = FixtureBackend(observation=observation())
        restarted, _reader = self.executor(restarted_backend, journal=journal)
        result = restarted.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (result.outcome, result.reason),
            ("reconcile-required", "transport-ambiguous"),
        )
        self.assertEqual(restarted_backend.merge_calls, 0)
        self.assertEqual(restarted_backend.observe_calls, 1)

    def test_restart_after_remote_effect_reconciles_without_second_put(self):
        journal = MergeOperationJournal(Path(self.temporary.name))
        crashing_backend = CrashAfterRemoteEffectBackend(observation=observation())
        executor, _reader = self.executor(crashing_backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "after remote effect"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertEqual(crashing_backend.merge_calls, 1)

        restarted_backend = FixtureBackend(observation=observation())
        restarted, _reader = self.executor(restarted_backend, journal=journal)
        pending = restarted.execute(
            self.operation_id,
            self.envelope.envelope_id,
            CREDENTIAL_ID,
            now=STARTED,
        )
        self.assertEqual(pending.reason, "pending-intent")
        result = restarted.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (result.outcome, result.reason),
            ("reconcile-required", "transport-ambiguous"),
        )
        self.assertEqual(restarted_backend.merge_calls, 0)
        self.assertEqual(restarted_backend.observe_calls, 1)

    def test_crash_after_response_before_result_reconciles_without_second_put(self):
        backend = FixtureBackend(response(), observation())
        journal = CrashBeforeResultJournal(Path(self.temporary.name))
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "before result"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertEqual(backend.merge_calls, 1)
        self.assertEqual(
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            ).reason,
            "pending-intent",
        )
        result = executor.reconcile(
            self.operation_id, CREDENTIAL_ID, now=COMPLETED
        )
        self.assertEqual(
            (result.outcome, result.reason),
            ("reconcile-required", "transport-ambiguous"),
        )
        self.assertEqual(backend.merge_calls, 1)

    def test_crash_after_result_replays_terminal_without_network(self):
        backend = FixtureBackend(response(), observation())
        journal = CrashAfterResultJournal(Path(self.temporary.name))
        executor, _reader = self.executor(backend, journal=journal)
        with self.assertRaisesRegex(RuntimeError, "after result"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        result = executor.execute(
            self.operation_id,
            self.envelope.envelope_id,
            CREDENTIAL_ID,
            now=STARTED,
        )
        self.assertEqual(result.reason, "confirmed-merged")
        self.assertEqual(backend.merge_calls, 1)
        self.assertEqual(backend.observe_calls, 1)

    def test_wrong_host_envelope_and_observation_identity_fail_closed(self):
        untrusted = copy.copy(self.envelope)
        object.__setattr__(untrusted, "source", "repository-file")
        backend = FixtureBackend(response(), observation())
        executor, _reader = self.executor(backend, envelope=untrusted)
        with self.assertRaisesRegex(StateError, "authenticated host storage"):
            executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
        self.assertEqual(backend.merge_calls, 0)

        with tempfile.TemporaryDirectory() as root:
            backend = FixtureBackend(response(), observation(repository_id=1))
            executor, _reader = self.executor(
                backend, journal=MergeOperationJournal(Path(root))
            )
            result = executor.execute(
                self.operation_id,
                self.envelope.envelope_id,
                CREDENTIAL_ID,
                now=STARTED,
            )
            self.assertEqual((result.outcome, result.reason), (
                "reconcile-required", "merge-proof-incomplete"
            ))


if __name__ == "__main__":
    unittest.main()
