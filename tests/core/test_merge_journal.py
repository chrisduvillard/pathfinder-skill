import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.merge_journal import MergeOperationJournal
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "contracts" / "fixtures" / "publication-journal-contracts.json"
AUTHORITY = ROOT / "tests" / "contracts" / "fixtures" / "publication-contracts.json"


def load(path):
    return json.loads(path.read_text())


class MergeOperationJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.journal = MergeOperationJournal(Path(self.temporary.name))
        self.bundle = load(FIXTURE)
        self.authority = load(AUTHORITY)
        self.protected_policy = ProtectedSurfaceRegistry.load().to_document()

    def record_intent(self, *, intent=None):
        return self.journal.record_intent(
            policy=self.authority["policy"],
            authorization=self.authority["authorization"],
            credential_receipt=self.bundle["credential_receipt"],
            protected_policy=self.protected_policy,
            initial_evidence=self.bundle["initial_evidence"],
            reread_evidence=self.bundle["evidence"],
            readiness_proof=self.bundle["readiness_proof"],
            intent=intent or self.bundle["intent"],
        )

    def claim_intent(self, *, intent=None):
        return self.journal.claim_intent(
            policy=self.authority["policy"],
            authorization=self.authority["authorization"],
            credential_receipt=self.bundle["credential_receipt"],
            protected_policy=self.protected_policy,
            initial_evidence=self.bundle["initial_evidence"],
            reread_evidence=self.bundle["evidence"],
            readiness_proof=self.bundle["readiness_proof"],
            intent=intent or self.bundle["intent"],
        )

    def dispatch(self, claim, *, journal=None):
        return (journal or self.journal).dispatch_once(
            claim,
            started_at=self.bundle["dispatch"]["dispatch_started_at"],
            send=lambda mark_dispatch: (mark_dispatch(), "sent")[1],
        )[0]

    def test_intent_is_write_once_and_pending_requires_reconciliation(self):
        self.assertEqual(self.record_intent(), self.record_intent())
        loaded = self.journal.load(self.bundle["intent"]["operation_id"])
        self.assertEqual(loaded["state"], "pending")
        self.assertEqual(loaded["disposition"], "reconcile-required")

        different = copy.deepcopy(self.bundle["intent"])
        different["started_at"] = "2026-08-11T12:08:31+00:00"
        from pathfinder_core.merge_policy import canonical_sha256

        different["intent_sha256"] = canonical_sha256(different, "intent_sha256")
        with self.assertRaisesRegex(StateError, "not current at intent time"):
            self.record_intent(intent=different)

    def test_only_one_concurrent_caller_creates_the_intent_claim(self):
        barrier = threading.Barrier(2)
        claims = []
        failures = []

        def claim():
            try:
                barrier.wait()
                claims.append(self.claim_intent())
            except BaseException as error:
                failures.append(error)

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(len(claims), 1)
        self.assertIsNotNone(claims[0])
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], StateError)
        self.assertIn("lock is already held", str(failures[0]))
        self.assertIsNone(self.claim_intent())

    def test_authorization_and_readiness_proof_cannot_be_reclaimed(self):
        from pathfinder_core.merge_policy import canonical_sha256

        self.assertIsNotNone(self.claim_intent())
        second = copy.deepcopy(self.bundle["intent"])
        second["operation_id"] = "merge_operation_example2"
        second["intent_sha256"] = canonical_sha256(second, "intent_sha256")
        with self.assertRaisesRegex(StateError, "already claimed"):
            self.claim_intent(intent=second)

    def test_result_requires_intent_and_is_terminal_write_once(self):
        with self.assertRaisesRegex(StateError, "not found"):
            self.journal.record_result(self.bundle["result"])
        claim = self.claim_intent()
        self.assertIsNotNone(claim)
        with self.assertRaisesRegex(StateError, "requires a persisted dispatch"):
            self.journal.record_result(self.bundle["result"])
        self.dispatch(claim)
        self.assertEqual(
            self.journal.record_result(self.bundle["result"]),
            self.journal.record_result(self.bundle["result"]),
        )
        loaded = self.journal.load(self.bundle["intent"]["operation_id"])
        self.assertEqual(loaded["state"], "terminal")
        self.assertEqual(loaded["disposition"], "merged")

        changed = copy.deepcopy(self.bundle["result"])
        changed["outcome"] = "not-merged"
        changed["reason"] = "unmergeable"
        changed["merge_proof"] = None
        from pathfinder_core.merge_policy import canonical_sha256

        changed["result_sha256"] = canonical_sha256(changed, "result_sha256")
        with self.assertRaisesRegex(StateError, "different merge result"):
            self.journal.record_result(changed)

    def test_dispatch_not_started_result_prevents_late_dispatch(self):
        from pathfinder_core.merge_policy import canonical_sha256

        claim = self.claim_intent()
        self.assertIsNotNone(claim)
        result = copy.deepcopy(self.bundle["result"])
        result["outcome"] = "reconcile-required"
        result["reason"] = "dispatch-not-started"
        result["merge_proof"] = None
        result["result_sha256"] = canonical_sha256(
            result, "result_sha256"
        )
        self.journal.record_result(result)
        with self.assertRaisesRegex(StateError, "terminal merge result"):
            self.dispatch(claim)

    def test_only_intent_creator_can_enter_dispatch_boundary(self):
        claim = self.claim_intent()
        self.assertIsNotNone(claim)
        second = MergeOperationJournal(Path(self.temporary.name))
        with self.assertRaisesRegex(StateError, "not owned by the intent creator"):
            self.dispatch(claim, journal=second)
        self.assertIsNone(self.journal.load(claim.operation_id)["dispatch"])
        self.dispatch(claim)

    def test_rehashed_binding_drift_and_fabricated_proof_fail(self):
        from pathfinder_core.merge_policy import canonical_sha256

        changed_intent = copy.deepcopy(self.bundle["intent"])
        changed_intent["pull_request"]["head_sha"] = "a" * 40
        changed_intent["intent_sha256"] = canonical_sha256(
            changed_intent, "intent_sha256"
        )
        with self.assertRaisesRegex(StateError, "pull request binding"):
            self.record_intent(intent=changed_intent)

        changed_diff = copy.deepcopy(self.bundle["intent"])
        changed_diff["bindings"]["diff_sha256"] = "f" * 64
        changed_diff["intent_sha256"] = canonical_sha256(
            changed_diff, "intent_sha256"
        )
        with self.assertRaisesRegex(StateError, "authority or evidence binding"):
            self.record_intent(intent=changed_diff)

        claim = self.claim_intent()
        self.assertIsNotNone(claim)
        self.dispatch(claim)
        result = copy.deepcopy(self.bundle["result"])
        result["merge_proof"]["merged_by"]["actor_id"] = 1
        result["result_sha256"] = canonical_sha256(result, "result_sha256")
        with self.assertRaisesRegex(StateError, "actor binding"):
            self.journal.record_result(result)

    def test_credential_receipt_must_be_fresh_at_intent_time(self):
        changed = copy.deepcopy(self.bundle["credential_receipt"])
        changed["verified_at"] = "2026-08-11T12:08:29+00:00"
        from pathfinder_core.merge_policy import canonical_sha256

        changed["receipt_sha256"] = canonical_sha256(
            changed, "receipt_sha256"
        )
        intent = copy.deepcopy(self.bundle["intent"])
        intent["bindings"]["credential_receipt_sha256"] = changed[
            "receipt_sha256"
        ]
        intent["intent_sha256"] = canonical_sha256(
            intent, "intent_sha256"
        )
        with self.assertRaisesRegex(StateError, "not current at intent"):
            self.journal.record_intent(
                policy=self.authority["policy"],
                authorization=self.authority["authorization"],
                credential_receipt=changed,
                protected_policy=self.protected_policy,
                initial_evidence=self.bundle["initial_evidence"],
                reread_evidence=self.bundle["evidence"],
                readiness_proof=self.bundle["readiness_proof"],
                intent=intent,
            )

    def test_operation_namespace_is_separate_from_mission_operations(self):
        self.record_intent()
        root = Path(self.temporary.name)
        self.assertTrue((root / "merge-operations").is_dir())
        self.assertFalse((root / "operations").exists())


if __name__ == "__main__":
    unittest.main()
