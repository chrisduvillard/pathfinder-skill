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
from pathfinder_core.merge_policy_types import DenyCode
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


@unittest.skipIf(os.name == "nt", "K5.1 host ACL verification is POSIX-only")
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
        self.assertEqual(
            first["inputs"]["protected_policy"]["state"], "shipped-baseline"
        )
        self.assertEqual(
            first["inputs"]["policy"]["declared_sha256"],
            self.authority["policy"]["policy_sha256"],
        )
        self.assertEqual(
            first["inputs"]["initial_evidence"]["document_sha256"],
            canonical_sha256(self.evidence["initial_evidence"]),
        )
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
        invented = copy.deepcopy(first)
        invented["outcome"] = "unknown"
        invented["eligible"] = False
        invented["blocks"] = [{
            "code": "invented-block", "surface": "test", "detail": "invalid",
        }]
        with self.assertRaises(ValidationError):
            REPORT_VALIDATOR.validate(invented)

        impossible_policy_state = copy.deepcopy(first)
        impossible_policy_state["inputs"]["policy"]["state"] = "shipped-baseline"
        with self.assertRaises(ValidationError):
            REPORT_VALIDATOR.validate(impossible_policy_state)
        impossible_protected_state = copy.deepcopy(first)
        impossible_protected_state["inputs"]["protected_policy"]["state"] = "missing"
        with self.assertRaises(ValidationError):
            REPORT_VALIDATOR.validate(impossible_protected_state)

        for name in ("policy", "authorization", "initial_evidence", "reread_evidence"):
            for field in ("document_id", "declared_sha256"):
                with self.subTest(name=name, missing_present_binding=field):
                    incomplete = copy.deepcopy(first)
                    incomplete["inputs"][name][field] = None
                    with self.assertRaises(ValidationError):
                        REPORT_VALIDATOR.validate(incomplete)
        invented_protected_hash = copy.deepcopy(first)
        invented_protected_hash["inputs"]["protected_policy"][
            "declared_sha256"
        ] = "a" * 64
        with self.assertRaises(ValidationError):
            REPORT_VALIDATOR.validate(invented_protected_hash)

    def test_missing_authority_is_typed_without_changing_state(self):
        self.write_publication()
        self.write_inputs(policy=False, authorization=False)

        report = self.controller().inspect(self.request_id, operation="status")

        self.assertEqual(report["outcome"], "unknown")
        self.assertEqual(report["state"], "awaiting-review")
        self.assertEqual(report["inputs"]["policy"]["state"], "missing")
        self.assertEqual(report["inputs"]["authorization"]["state"], "missing")
        self.assertIsNone(report["inputs"]["policy"]["document_sha256"])
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

    def test_report_hash_binds_both_exact_evidence_documents(self):
        self.write_publication()
        self.write_inputs()
        original = self.controller().inspect(self.request_id, operation="evaluate")
        changed_documents = []
        for key, filename, suffix in (
            ("initial_evidence", "merge-evidence-initial.json", "changed"),
            ("evidence", "merge-evidence-reread.json", "changed-reread"),
        ):
            document = copy.deepcopy(self.evidence[key])
            document["evidence_id"] = f"merge_evidence_example1_{suffix}"
            document["evidence_sha256"] = canonical_sha256(
                document, "evidence_sha256"
            )
            write_atomic(self.host / filename, document)
            changed_documents.append(document)

        changed = self.controller().inspect(self.request_id, operation="evaluate")

        self.assertEqual(changed["outcome"], "eligible")
        self.assertNotEqual(changed["report_sha256"], original["report_sha256"])
        self.assertEqual(
            changed["inputs"]["initial_evidence"]["document_sha256"],
            canonical_sha256(changed_documents[0]),
        )
        self.assertEqual(
            changed["inputs"]["reread_evidence"]["document_sha256"],
            canonical_sha256(changed_documents[1]),
        )

    def test_malformed_input_returns_a_typed_block(self):
        self.write_publication()
        self.write_inputs()
        (self.host / "merge-policy.json").write_text("{")

        report = self.controller().inspect(self.request_id, operation="status")

        self.assertEqual(report["outcome"], "unknown")
        self.assertEqual(report["inputs"]["policy"]["state"], "invalid")
        self.assertIn("input-invalid", {
            block["code"] for block in report["blocks"]
        })

        (self.host / "merge-policy.json").write_bytes(b"\xff")
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(report["inputs"]["policy"]["state"], "invalid")

        write_atomic(self.host / "merge-policy.json", self.authority["policy"])
        write_atomic(self.host / "protected-policy.json", {"mode": "additive"})
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(
            report["inputs"]["protected_policy"]["state"], "invalid"
        )
        self.assertIn("input-invalid", {
            block["code"] for block in report["blocks"]
        })

        malformed_policy = copy.deepcopy(self.authority["policy"])
        malformed_policy["policy_id"] = "x" * 1000
        malformed_policy["policy_sha256"] = "not-a-hash"
        write_atomic(self.host / "merge-policy.json", malformed_policy)
        report = self.controller().inspect(self.request_id, operation="status")
        self.assertEqual(report["inputs"]["policy"]["state"], "invalid")
        self.assertIsNone(report["inputs"]["policy"]["document_id"])
        self.assertIsNone(report["inputs"]["policy"]["declared_sha256"])
        REPORT_VALIDATOR.validate(report)

    def test_non_object_json_is_invalid_and_bound_in_the_report(self):
        self.write_publication()
        self.write_inputs()

        for document in ([], "wrong", 7, None):
            with self.subTest(document=document):
                write_atomic(self.host / "merge-policy.json", document)
                report = self.controller().inspect(
                    self.request_id, operation="status"
                )

                self.assertEqual(report["outcome"], "unknown")
                self.assertEqual(report["inputs"]["policy"]["state"], "invalid")
                self.assertEqual(
                    report["inputs"]["policy"]["document_sha256"],
                    canonical_sha256(document),
                )
                self.assertIn(
                    "input-invalid", {block["code"] for block in report["blocks"]}
                )
                REPORT_VALIDATOR.validate(report)

    def test_selected_journal_name_must_match_embedded_request_identity(self):
        self.write_publication()
        self.write_inputs()
        alternate = "publication_request_other999"
        operations = self.host / "journal" / "publication-operations"
        for label in ("request", "dispatch", "receipt"):
            (operations / f"{self.request_id}.{label}.json").rename(
                operations / f"{alternate}.{label}.json"
            )

        with self.assertRaisesRegex(
            StateError, "identity differs from selected journal record"
        ):
            self.controller().inspect(alternate, operation="status")

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
        self.assertEqual(report["inputs"]["policy"]["state"], "invalid")
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
        with self.assertRaisesRegex(StateError, "opened safely"):
            self.controller().inspect(self.request_id, operation="status")

    def test_root_descriptor_prevents_post_validation_path_swap(self):
        self.write_publication()
        self.write_inputs()
        repository_host = self.repository / "attacker-host"
        repository_host.mkdir()
        pinned_host = self.host.with_name("pinned-host")

        class SwappingReader(InstalledHostMergeReader):
            def _open_root(inner_self):
                descriptor = super()._open_root()
                inner_self.host_root.rename(pinned_host)
                inner_self.host_root.symlink_to(
                    repository_host, target_is_directory=True
                )
                return descriptor

        report = MergeStatusController(
            SwappingReader(self.repository, self.host), clock=lambda: NOW
        ).inspect(self.request_id, operation="evaluate")

        self.assertEqual(report["outcome"], "eligible")
        self.assertEqual(
            report["publication"]["receipt_sha256"],
            self.publication["receipt"]["receipt_sha256"],
        )

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


class MergeStatusPlatformTests(unittest.TestCase):
    def test_windows_fails_closed_without_acl_ownership_proof(self):
        with patch("pathfinder_core.merge_status.os.name", "nt"):
            with self.assertRaisesRegex(StateError, "unavailable on Windows"):
                InstalledHostMergeReader("repository", "host").load(
                    "publication_request_example1"
                )

    def test_report_block_code_schema_tracks_the_closed_domain(self):
        codes = REPORT_VALIDATOR.schema["$defs"]["block"]["properties"][
            "code"
        ]["enum"]
        self.assertEqual(set(codes), {code.value for code in DenyCode})


if __name__ == "__main__":
    unittest.main()
