import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from jsonschema.exceptions import ValidationError

from pathfinder_core.__main__ import main
from pathfinder_core.errors import StateError
from pathfinder_core.merge_policy import canonical_sha256
from pathfinder_core.merge_status import (
    InstalledHostMergeReader,
    MergeStatusController,
    REPORT_VALIDATOR,
)
from pathfinder_core.publication_journal import PublicationJournal
from pathfinder_core.storage import write_atomic


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"
NOW = datetime.fromisoformat("2026-08-11T12:08:30+00:00")


def load(name):
    return json.loads((FIXTURES / name).read_text())


class MergeStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.repository = root / "repository"
        self.host = root / "host"
        self.repository.mkdir()
        self.host.mkdir(mode=0o700)
        os.chmod(self.host, 0o700)
        self.authority = load("publication-contracts.json")
        self.evidence = load("publication-journal-contracts.json")
        self.publication = load("publication-controller-contracts.json")
        self.request_id = self.publication["request"]["publication_request_id"]

    def write_inputs(self, *, policy=True, authorization=True):
        documents = {
            "merge-evidence-initial.json": self.evidence["initial_evidence"],
            "merge-evidence-reread.json": self.evidence["evidence"],
        }
        if policy:
            documents["merge-policy.json"] = self.authority["policy"]
        if authorization:
            documents["merge-authorization.json"] = self.authority[
                "authorization"
            ]
        for name, document in documents.items():
            write_atomic(self.host / name, document)

    def write_publication(self, *, receipt=True):
        journal = PublicationJournal(self.host / "journal")
        claim = journal.claim_request(self.publication["request"])
        self.assertIsNotNone(claim)
        journal.dispatch_once(
            claim,
            started_at=self.publication["dispatch"]["started_at"],
            send=lambda: None,
        )
        if receipt:
            journal.record_receipt(self.publication["receipt"])

    def controller(self):
        return MergeStatusController(
            InstalledHostMergeReader(self.repository, self.host),
            clock=lambda: NOW,
        )

    def test_eligible_report_remains_observation_only_and_discards_proof(self):
        self.write_publication()
        self.write_inputs()

        first = self.controller().inspect(self.request_id, operation="evaluate")
        second = self.controller().inspect(self.request_id, operation="evaluate")

        self.assertEqual(first, second)
        self.assertEqual(first["outcome"], "eligible")
        self.assertTrue(first["eligible"])
        self.assertEqual(first["state"], "awaiting-review")
        self.assertFalse(first["intent_ready"])
        self.assertFalse(first["execution_available"])
        self.assertFalse(first["writer_credential_loaded"])
        self.assertFalse(first["merge_intent_created"])
        self.assertEqual(first["inputs"]["protected_policy"], "shipped-baseline")
        self.assertNotIn("readiness_proof", first)
        self.assertNotIn("proof_sha256", json.dumps(first))
        self.assertEqual(
            first["report_sha256"], canonical_sha256(first, "report_sha256")
        )
        REPORT_VALIDATOR.validate(first)
        inconsistent = copy.deepcopy(first)
        inconsistent["outcome"] = "unknown"
        inconsistent["eligible"] = False
        with self.assertRaises(ValidationError):
            REPORT_VALIDATOR.validate(inconsistent)

    def test_missing_authority_is_typed_without_changing_state(self):
        self.write_publication()
        self.write_inputs(policy=False, authorization=False)

        report = self.controller().inspect(self.request_id, operation="status")

        self.assertEqual(report["outcome"], "unknown")
        self.assertEqual(report["state"], "awaiting-review")
        self.assertEqual(report["inputs"]["policy"], "missing")
        self.assertEqual(report["inputs"]["authorization"], "missing")
        self.assertEqual(
            {block["code"] for block in report["blocks"]},
            {"policy-missing", "authorization-missing"},
        )

    def test_receipt_identity_is_rechecked_against_both_snapshots(self):
        self.write_publication()
        self.write_inputs()
        changed = copy.deepcopy(self.evidence["evidence"])
        changed["pull_request"]["number"] += 1
        changed["evidence_sha256"] = canonical_sha256(
            changed, "evidence_sha256"
        )
        write_atomic(self.host / "merge-evidence-reread.json", changed)

        report = self.controller().inspect(self.request_id, operation="evaluate")

        self.assertEqual(report["outcome"], "unknown")
        self.assertIn("identity-drift", {
            block["code"] for block in report["blocks"]
        })
        self.assertFalse(report["intent_ready"])

    def test_malformed_input_returns_a_typed_block(self):
        self.write_publication()
        self.write_inputs()
        (self.host / "merge-policy.json").write_text("{")

        report = self.controller().inspect(self.request_id, operation="status")

        self.assertEqual(report["outcome"], "unknown")
        self.assertEqual(report["inputs"]["policy"], "invalid")
        self.assertIn("input-invalid", {
            block["code"] for block in report["blocks"]
        })

        (self.host / "merge-policy.json").write_bytes(b"\xff")
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(report["inputs"]["policy"], "invalid")

        write_atomic(self.host / "merge-policy.json", self.authority["policy"])
        write_atomic(self.host / "protected-policy.json", {"mode": "additive"})
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(report["inputs"]["protected_policy"], "invalid")
        self.assertIn("input-invalid", {
            block["code"] for block in report["blocks"]
        })

    def test_exact_publication_receipt_is_a_hard_prerequisite(self):
        self.write_publication(receipt=False)
        self.write_inputs()

        with self.assertRaisesRegex(StateError, "exact awaiting-review"):
            self.controller().inspect(self.request_id, operation="status")

    def test_installed_host_boundary_rejects_repository_and_symlink_trust(self):
        inside = self.repository / "host"
        inside.mkdir()
        with self.assertRaisesRegex(StateError, "outside repository"):
            InstalledHostMergeReader(self.repository, inside).load(self.request_id)

        link = Path(self.temporary.name) / "host-link"
        link.symlink_to(self.host, target_is_directory=True)
        with self.assertRaisesRegex(StateError, "non-symlink directory"):
            InstalledHostMergeReader(self.repository, link).load(self.request_id)

    @unittest.skipIf(os.name == "nt", "POSIX owner-only mode")
    def test_installed_host_boundary_rejects_group_or_world_access(self):
        os.chmod(self.host, 0o750)
        with self.assertRaisesRegex(StateError, "owner-only"):
            InstalledHostMergeReader(self.repository, self.host).load(
                self.request_id
            )

    @unittest.skipUnless(hasattr(os, "geteuid"), "POSIX directory ownership")
    def test_installed_host_boundary_requires_current_user_ownership(self):
        with patch("pathfinder_core.merge_status.os.geteuid", return_value=-1):
            with self.assertRaisesRegex(StateError, "owned by the current user"):
                InstalledHostMergeReader(self.repository, self.host).load(
                    self.request_id
                )

    def test_input_and_journal_symlinks_are_rejected(self):
        self.write_publication()
        self.write_inputs()
        real_policy = self.host / "real-policy.json"
        (self.host / "merge-policy.json").replace(real_policy)
        (self.host / "merge-policy.json").symlink_to(real_policy)
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(report["inputs"]["policy"], "invalid")
        self.assertIn("input-invalid", {
            block["code"] for block in report["blocks"]
        })

        receipt = (
            self.host
            / "journal"
            / "publication-operations"
            / f"{self.request_id}.receipt.json"
        )
        real_receipt = receipt.with_name("real-receipt.json")
        receipt.replace(real_receipt)
        receipt.symlink_to(real_receipt)
        with self.assertRaisesRegex(StateError, "regular non-symlink"):
            self.controller().inspect(self.request_id, operation="status")

    def test_cli_emits_canonical_json_or_a_markdown_view(self):
        self.write_publication()
        self.write_inputs()
        common = [
            "--repo-root", str(self.repository),
            "--host-dir", str(self.host),
            "--publication-request-id", self.request_id,
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["merge", "status", *common, "--json"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        REPORT_VALIDATOR.validate(report)
        self.assertFalse(report["execution_available"])

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["merge", "evaluate", *common])
        self.assertEqual(code, 0)
        rendered = output.getvalue()
        self.assertIn("# Pathfinder merge status", rendered)
        self.assertIn("execution available: `false`", rendered)
        self.assertNotIn("readiness_proof", rendered)


if __name__ == "__main__":
    unittest.main()
