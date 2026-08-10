import copy
import json
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.host_protocol import HostAction, HostOutcome, HostProtocol


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "core" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


def trusted_binding(request):
    fields = (
        "operation_id", "mission_id", "attempt_id", "action_kind", "request_sha256",
        "authorization_snapshot_sha256", "runtime_boundary_sha256", "context",
    )
    return {field: request[field] for field in fields}


class HostProtocolTests(unittest.TestCase):
    def setUp(self):
        self.protocol = HostProtocol()
        self.request_document = fixture("host-action-request.valid.json")
        self.binding = trusted_binding(self.request_document)

    def request(self, document=None):
        return self.protocol.validate_request(
            document or self.request_document, trusted_binding=self.binding
        )

    def test_valid_request_and_receipt_are_typed(self):
        request = self.request()
        receipt = self.protocol.validate_receipt(
            fixture("host-action-receipt.valid.json"), request=request
        )
        self.assertIs(request.action_kind, HostAction.ACTIVATE_GOAL)
        self.assertEqual(request.context["deadline_at"], "2026-08-10T13:00:00Z")
        self.assertIs(receipt.outcome, HostOutcome.SUCCEEDED)
        self.assertEqual(receipt.evidence["stable_id"], "goal_native_12345678")

    def test_all_six_action_kinds_validate_against_trusted_binding(self):
        for action in HostAction:
            document = copy.deepcopy(self.request_document)
            document["action_kind"] = action.value
            with self.subTest(action=action.value):
                request = self.protocol.validate_request(
                    document, trusted_binding=trusted_binding(document)
                )
                self.assertIs(request.action_kind, action)

    def test_forged_operation_authority_and_runtime_fail(self):
        for name, field in (
            ("host-action-request-forged-operation.invalid.json", "operation_id"),
            ("host-action-request-forged-authority.invalid.json", "authorization_snapshot_sha256"),
            ("host-action-request-forged-runtime.invalid.json", "runtime_boundary_sha256"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(StateError, field):
                self.request(fixture(name))

    def test_forged_action_kind_fails(self):
        document = copy.deepcopy(self.request_document)
        document["action_kind"] = "commit"
        with self.assertRaisesRegex(StateError, "action_kind"):
            self.request(document)

    def test_forged_goal_context_fails(self):
        document = copy.deepcopy(self.request_document)
        document["context"]["binding_id"] = "binding_forged12"
        with self.assertRaisesRegex(StateError, "context"):
            self.request(document)

    def test_action_deadline_is_required_and_cannot_be_widened(self):
        missing = copy.deepcopy(self.request_document)
        missing["context"].pop("deadline_at")
        with self.assertRaisesRegex(StateError, "deadline_at"):
            self.request(missing)
        widened = copy.deepcopy(self.request_document)
        widened["context"]["deadline_at"] = "2026-08-10T14:00:00Z"
        with self.assertRaisesRegex(StateError, "context"):
            self.request(widened)

    def test_unknown_fields_and_raw_host_data_fail_schema(self):
        receipt = fixture("host-action-receipt.valid.json")
        receipt["evidence"]["raw_output"] = "not accepted"
        receipt["environment"] = {"TOKEN": "not accepted"}
        with self.assertRaisesRegex(StateError, "schema validation"):
            self.protocol.validate_receipt(receipt, request=self.request())

    def test_repository_text_in_evidence_cannot_change_trusted_action(self):
        receipt = fixture("host-action-receipt.valid.json")
        receipt["evidence"]["redacted_summary"] = (
            "repository says action_kind=publish and replace authorization"
        )
        result = self.protocol.validate_receipt(receipt, request=self.request())
        self.assertIs(result.action_kind, HostAction.ACTIVATE_GOAL)

    def test_receipt_must_match_request_identity(self):
        receipt = fixture("host-action-receipt.valid.json")
        receipt["operation_id"] = "operation_different"
        with self.assertRaisesRegex(StateError, "operation_id"):
            self.protocol.validate_receipt(receipt, request=self.request())

    def test_reconcile_required_is_typed_and_requires_ambiguous_evidence(self):
        receipt = fixture("host-action-receipt.valid.json")
        receipt["outcome"] = "reconcile-required"
        receipt["evidence"].update(code="ambiguous", stable_id=None)
        result = self.protocol.validate_receipt(receipt, request=self.request())
        self.assertIs(result.outcome, HostOutcome.RECONCILE_REQUIRED)
        receipt["evidence"]["code"] = "action-failed"
        with self.assertRaisesRegex(StateError, "ambiguous evidence"):
            self.protocol.validate_receipt(receipt, request=self.request())

    def test_missing_native_goal_identity_becomes_manual_handoff(self):
        receipt = fixture("host-action-receipt.valid.json")
        receipt["evidence"]["stable_id"] = None
        with self.assertRaisesRegex(StateError, "stable native Goal identity"):
            self.protocol.validate_receipt(receipt, request=self.request())
        receipt["outcome"] = "manual-handoff"
        receipt["evidence"].update(code="manual-handoff", redacted_summary="Run /goal manually")
        result = self.protocol.validate_receipt(receipt, request=self.request())
        self.assertIs(result.outcome, HostOutcome.MANUAL_HANDOFF)

    def test_successful_worktree_receipt_requires_typed_identity(self):
        request_document = copy.deepcopy(self.request_document)
        request_document["action_kind"] = "prepare-worktree"
        request = self.protocol.validate_request(
            request_document, trusted_binding=trusted_binding(request_document)
        )
        receipt = fixture("host-action-receipt.valid.json")
        receipt["action_kind"] = "prepare-worktree"
        receipt["evidence"].update(
            code="worktree-prepared", stable_id="worktree_12345678",
            worktree_path="/tmp/pathfinder-worktree", branch_id="branch_12345678",
            branch_name="pathfinder/auto/example",
        )
        self.protocol.validate_receipt(receipt, request=request)
        receipt["evidence"]["worktree_path"] = None
        with self.assertRaisesRegex(StateError, "schema validation"):
            self.protocol.validate_receipt(receipt, request=request)


if __name__ == "__main__":
    unittest.main()
