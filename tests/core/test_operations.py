import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import StateError
from pathfinder_core.operations import OperationJournal


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class OperationJournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.journal = OperationJournal(self.root)
        self.intent = fixture("operation-intent.valid.json")
        self.result = fixture("operation-result.valid.json")

    def tearDown(self):
        self.temporary.cleanup()

    def test_identical_retries_are_noops(self):
        self.assertEqual(self.journal.record_intent(self.intent), self.intent)
        self.assertEqual(self.journal.record_intent(copy.deepcopy(self.intent)), self.intent)
        self.assertEqual(self.journal.record_result(self.result), self.result)
        self.assertEqual(self.journal.record_result(copy.deepcopy(self.result)), self.result)
        self.assertEqual(len(list((self.root / "operations").glob("*.json"))), 2)

    def test_different_intent_retry_fails(self):
        self.journal.record_intent(self.intent)
        changed = copy.deepcopy(self.intent)
        changed["request_sha256"] = "f" * 64
        with self.assertRaisesRegex(StateError, "different operation intent"):
            self.journal.record_intent(changed)

    def test_different_result_retry_fails(self):
        self.journal.record_intent(self.intent)
        self.journal.record_result(self.result)
        changed = copy.deepcopy(self.result)
        changed["outcome"] = "failed"
        changed["evidence"].update(
            summary_code="command-failed", exit_status=1, output_sha256=None
        )
        with self.assertRaisesRegex(StateError, "different operation result"):
            self.journal.record_result(changed)

    def test_result_before_intent_fails(self):
        with self.assertRaisesRegex(StateError, "before its intent"):
            self.journal.record_result(self.result)

    def test_result_binding_drift_fails(self):
        self.journal.record_intent(self.intent)
        changed = copy.deepcopy(self.result)
        changed.update(stage="verification", action_kind="verify")
        with self.assertRaisesRegex(StateError, "does not match intent field"):
            self.journal.record_result(changed)

    def test_intent_without_result_requires_reconciliation(self):
        self.journal.record_intent(self.intent)
        loaded = OperationJournal(self.root).load(self.intent["operation_id"])
        self.assertEqual(loaded["state"], "pending")
        self.assertEqual(loaded["disposition"], "reconcile-required")
        self.assertIsNone(loaded["result"])

    def test_terminal_result_loads_after_restart(self):
        self.journal.record_intent(self.intent)
        self.journal.record_result(self.result)
        loaded = OperationJournal(self.root).load(self.intent["operation_id"])
        self.assertEqual(loaded["state"], "terminal")
        self.assertEqual(loaded["disposition"], "succeeded")
        self.assertEqual(loaded["result"], self.result)

    def test_crash_before_intent_write_leaves_no_operation(self):
        with mock.patch.object(
            self.journal, "_write_once", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.journal.record_intent(self.intent)
        with self.assertRaisesRegex(StateError, "operation not found"):
            self.journal.load(self.intent["operation_id"])

    def test_atomic_replace_crash_leaves_no_partial_intent(self):
        with mock.patch("pathfinder_core.storage.os.replace", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                self.journal.record_intent(self.intent)
        with self.assertRaisesRegex(StateError, "operation not found"):
            self.journal.load(self.intent["operation_id"])
        self.assertEqual(list((self.root / "operations").glob("*.tmp")), [])

    def test_atomic_result_crash_preserves_pending_intent(self):
        self.journal.record_intent(self.intent)
        with mock.patch("pathfinder_core.storage.os.replace", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                self.journal.record_result(self.result)
        loaded = self.journal.load(self.intent["operation_id"])
        self.assertEqual(loaded["state"], "pending")
        self.assertEqual(loaded["disposition"], "reconcile-required")

    def test_invalid_operation_id_cannot_escape_journal(self):
        with self.assertRaisesRegex(StateError, "invalid operation id"):
            self.journal.load("../../outside")

    def test_duplicate_keys_in_persisted_intent_fail_closed(self):
        path = self.root / "operations" / "operation_12345678.intent.json"
        path.parent.mkdir(parents=True)
        serialized = json.dumps(self.intent).replace(
            '"schema_version": 1', '"schema_version": 1, "schema_version": 1'
        )
        path.write_text(serialized)
        with self.assertRaisesRegex(StateError, "duplicate JSON key"):
            self.journal.load(self.intent["operation_id"])


if __name__ == "__main__":
    unittest.main()
