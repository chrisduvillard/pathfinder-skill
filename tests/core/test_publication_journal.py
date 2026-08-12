import copy
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.merge_policy import canonical_sha256
from pathfinder_core.publication_journal import PublicationJournal


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)


class PublicationJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.journal = PublicationJournal(Path(self.temporary.name))
        self.bundle = json.loads(FIXTURE.read_text())

    def claim(self, request=None):
        return self.journal.claim_request(request or self.bundle["request"])

    def dispatch(self, claim, journal=None):
        return (journal or self.journal).dispatch_once(
            claim,
            started_at=self.bundle["dispatch"]["started_at"],
            send=lambda: "sent",
        )[0]

    def test_request_is_write_once_and_authority_cannot_be_repackaged(self):
        self.assertIsNotNone(self.claim())
        self.assertIsNone(self.claim())
        changed = copy.deepcopy(self.bundle["request"])
        changed["publication_request_id"] = "publication_request_example2"
        changed["request_sha256"] = canonical_sha256(
            changed, "request_sha256"
        )
        with self.assertRaisesRegex(StateError, "already claimed"):
            self.claim(changed)

    def test_only_creator_can_dispatch_and_dispatch_is_one_use(self):
        claim = self.claim()
        self.assertIsNotNone(claim)
        second = PublicationJournal(Path(self.temporary.name))
        with self.assertRaisesRegex(StateError, "not owned"):
            self.dispatch(claim, second)
        self.dispatch(claim)
        with self.assertRaisesRegex(StateError, "not owned"):
            self.dispatch(claim)

    def test_concurrent_dispatch_cannot_send_twice(self):
        claim = self.claim()
        self.assertIsNotNone(claim)
        entered = threading.Event()
        release = threading.Event()
        sends = []
        errors = []

        def send():
            sends.append("sent")
            entered.set()
            release.wait(5)
            return "sent"

        def dispatch():
            try:
                self.journal.dispatch_once(
                    claim,
                    started_at=self.bundle["dispatch"]["started_at"],
                    send=send,
                )
            except Exception as error:  # pragma: no cover - assertion reports it
                errors.append(error)

        worker = threading.Thread(target=dispatch)
        worker.start()
        self.assertTrue(entered.wait(5))
        try:
            with self.assertRaisesRegex(StateError, "not owned"):
                self.dispatch(claim)
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(sends, ["sent"])

    def test_remote_send_runs_after_the_journal_lock_is_released(self):
        claim = self.claim()
        self.assertIsNotNone(claim)

        def send():
            self.assertFalse(self.journal.lock_path.exists())
            return "sent"

        _dispatch, result = self.journal.dispatch_once(
            claim,
            started_at=self.bundle["dispatch"]["started_at"],
            send=send,
        )
        self.assertEqual(result, "sent")

    @unittest.skipUnless(hasattr(os, "fork"), "requires POSIX process death")
    def test_process_death_during_send_does_not_strand_recovery_lock(self):
        claim = self.claim()
        self.assertIsNotNone(claim)
        child = os.fork()
        if child == 0:
            try:
                self.journal.dispatch_once(
                    claim,
                    started_at=self.bundle["dispatch"]["started_at"],
                    send=lambda: os._exit(17),
                )
            finally:
                os._exit(99)
        _pid, status = os.waitpid(child, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 17)
        self.assertFalse(self.journal.lock_path.exists())
        self.assertIsNotNone(
            self.journal.load(claim.publication_request_id)["dispatch"]
        )
        recorded = self.journal.record_receipt(self.bundle["receipt"])
        self.assertEqual(recorded, self.bundle["receipt"])

    def test_receipt_requires_dispatch_and_exact_request_binding(self):
        claim = self.claim()
        self.assertIsNotNone(claim)
        with self.assertRaisesRegex(StateError, "requires request and dispatch"):
            self.journal.record_receipt(self.bundle["receipt"])
        self.dispatch(claim)
        recorded = self.journal.record_receipt(self.bundle["receipt"])
        self.assertEqual(recorded, self.journal.record_receipt(recorded))
        loaded = self.journal.load(claim.publication_request_id)
        self.assertEqual(loaded["state"], "awaiting-review")
        self.assertEqual(loaded["receipt"], recorded)

        changed = copy.deepcopy(self.bundle["receipt"])
        changed["pull_request"]["head_sha"] = "a" * 40
        changed["receipt_sha256"] = canonical_sha256(
            changed, "receipt_sha256"
        )
        with self.assertRaisesRegex(StateError, "request binding"):
            self.journal.record_receipt(changed)

    def test_rehashed_dispatch_outside_request_window_fails_closed(self):
        claim = self.claim()
        self.assertIsNotNone(claim)
        self.dispatch(claim)
        path = (
            Path(self.temporary.name)
            / "publication-operations"
            / f"{claim.publication_request_id}.dispatch.json"
        )
        changed = json.loads(path.read_text())
        changed["started_at"] = self.bundle["request"]["expires_at"]
        changed["dispatch_sha256"] = canonical_sha256(
            changed, "dispatch_sha256"
        )
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(StateError, "dispatch request binding"):
            self.journal.load(claim.publication_request_id)

    def test_authorization_snapshot_and_identity_are_bound(self):
        cases = (
            ("hash", "authorization snapshot hash"),
            ("identity", "authorization identity"),
            ("window", "authorization window"),
        )
        for mutation, message in cases:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as root:
                changed = copy.deepcopy(self.bundle["request"])
                if mutation == "hash":
                    changed["authorization"]["snapshot_sha256"] = "5" * 64
                elif mutation == "identity":
                    changed["authorization"]["authorization_id"] = (
                        "authorization_other123"
                    )
                    changed["mission"]["authorization_snapshot_sha256"] = (
                        canonical_sha256(changed["authorization"])
                    )
                else:
                    changed["authorization"]["authorized_at"] = (
                        "2026-08-11T10:00:00+00:00"
                    )
                    changed["authorization"]["limits"]["max_wall_seconds"] = 60
                    changed["mission"]["authorization_snapshot_sha256"] = (
                        canonical_sha256(changed["authorization"])
                    )
                changed["request_sha256"] = canonical_sha256(
                    changed, "request_sha256"
                )
                journal = PublicationJournal(Path(root))
                with self.assertRaisesRegex(StateError, message):
                    journal.claim_request(changed)

    def test_namespace_is_separate_from_mission_and_merge_journals(self):
        self.claim()
        root = Path(self.temporary.name)
        self.assertTrue((root / "publication-operations").is_dir())
        self.assertFalse((root / "operations").exists())
        self.assertFalse((root / "merge-operations").exists())


if __name__ == "__main__":
    unittest.main()
