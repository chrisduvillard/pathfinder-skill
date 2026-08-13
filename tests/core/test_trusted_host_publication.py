import copy
import unittest
from dataclasses import dataclass
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.trusted_host_publication import (
    TrustedHostPublicationEvidenceController,
)


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PublicationResult:
    publication_request_id: str
    state: str
    reason: str
    receipt: dict | None


class Journal:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def load(self, request_id):
        self.calls.append(request_id)
        return copy.deepcopy(self.records)


class PublicationBoundary:
    def __init__(self, result, records):
        self.result = result
        self.journal = Journal(records)
        self.publish_calls = []
        self.reconcile_calls = []

    def publish(self, request_id, envelope_id):
        self.publish_calls.append((request_id, envelope_id))
        return self.result

    def reconcile(self, request_id):
        self.reconcile_calls.append(request_id)
        return self.result


class Collector:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def collect_from_verified_host(self, **values):
        self.calls.append(
            {
                **values,
                "publication_records": copy.deepcopy(
                    values["publication_records"]
                ),
            }
        )
        return self.result


class Snapshot:
    def __init__(self, evidence_id):
        self.evidence = {"evidence_id": evidence_id}


class Collection:
    def __init__(self, evidence_id):
        self.snapshot = Snapshot(evidence_id)
        self.envelope = {"authenticated": True}


class TrustedHostPublicationEvidenceControllerTests(unittest.TestCase):
    def setUp(self):
        self.request_id = "publication_request_example1"
        self.receipt = {
            "publication_request_id": self.request_id,
            "publication_receipt_id": "publication_receipt_example1",
        }
        self.records = {
            "state": "awaiting-review",
            "disposition": "awaiting-review",
            "request": {"publication_request_id": self.request_id},
            "dispatch": {"publication_request_id": self.request_id},
            "receipt": self.receipt,
        }
        self.publication_result = PublicationResult(
            self.request_id,
            "awaiting-review",
            "publication-confirmed",
            self.receipt,
        )
        self.collection = Collection("merge_evidence_example1")
        self.publication = PublicationBoundary(
            self.publication_result, self.records
        )
        self.collector = Collector(self.collection)
        self.inputs = object()
        self.policy = object()
        self.controller = TrustedHostPublicationEvidenceController(
            publication=self.publication,
            collector=self.collector,
            collection_inputs=self.inputs,
            policy_backend=self.policy,
        )

    def test_publish_then_collects_for_the_exact_terminal_journal(self):
        result = self.controller.publish_and_collect(
            self.request_id, "publication_envelope_example1"
        )

        self.assertEqual(
            self.publication.publish_calls,
            [(self.request_id, "publication_envelope_example1")],
        )
        self.assertEqual(self.publication.reconcile_calls, [])
        self.assertEqual(self.publication.journal.calls, [self.request_id])
        self.assertEqual(len(self.collector.calls), 1)
        self.assertIs(self.collector.calls[0]["policy_backend"], self.policy)
        self.assertIs(self.collector.calls[0]["input_provider"], self.inputs)
        self.assertEqual(
            self.collector.calls[0]["publication_records"], self.records
        )
        self.assertEqual(result.state, "awaiting-review")
        self.assertEqual(result.reason, "publication-and-evidence-confirmed")
        self.assertEqual(result.receipt, self.receipt)
        self.assertEqual(result.evidence_id, "merge_evidence_example1")
        self.assertIs(result.collection, self.collection)

    def test_read_only_reconcile_can_collect_without_calling_publish(self):
        result = self.controller.reconcile_and_collect(self.request_id)

        self.assertEqual(self.publication.publish_calls, [])
        self.assertEqual(
            self.publication.reconcile_calls, [self.request_id]
        )
        self.assertEqual(len(self.collector.calls), 1)
        self.assertEqual(result.evidence_id, "merge_evidence_example1")

    def test_nonterminal_publication_never_requests_collection_inputs(self):
        pending = PublicationResult(
            self.request_id, "reconcile-required", "pending-publication", None
        )
        publication = PublicationBoundary(pending, self.records)
        collector = Collector(self.collection)
        controller = TrustedHostPublicationEvidenceController(
            publication=publication,
            collector=collector,
            collection_inputs=self.inputs,
            policy_backend=self.policy,
        )

        result = controller.publish_and_collect(
            self.request_id, "publication_envelope_example1"
        )

        self.assertEqual(result.state, "reconcile-required")
        self.assertEqual(result.reason, "pending-publication")
        self.assertIsNone(result.receipt)
        self.assertIsNone(result.evidence_id)
        self.assertIsNone(result.collection)
        self.assertEqual(publication.journal.calls, [])
        self.assertEqual(collector.calls, [])

    def test_journal_receipt_drift_blocks_before_evidence_reads(self):
        records = copy.deepcopy(self.records)
        records["receipt"]["publication_receipt_id"] = (
            "publication_receipt_different1"
        )
        publication = PublicationBoundary(self.publication_result, records)
        collector = Collector(self.collection)
        controller = TrustedHostPublicationEvidenceController(
            publication=publication,
            collector=collector,
            collection_inputs=self.inputs,
            policy_backend=self.policy,
        )

        with self.assertRaisesRegex(StateError, "terminal journal differs"):
            controller.publish_and_collect(
                self.request_id, "publication_envelope_example1"
            )

        self.assertEqual(collector.calls, [])

    def test_source_adds_no_secret_loader_command_or_merge_reachability(self):
        source = (
            ROOT / "pathfinder_core" / "trusted_host_publication.py"
        ).read_text()
        for forbidden in (
            "os.environ",
            "subprocess",
            "GitHubEvidenceCredential(",
            "GitHubMergeCredential(",
            "MergeExecutor",
            "GitHubMergeBackend",
            "def merge(",
            "def execute(",
        ):
            self.assertNotIn(forbidden, source)
        cli = (ROOT / "pathfinder_core" / "__main__.py").read_text()
        self.assertNotIn("TrustedHostPublicationEvidenceController", cli)
        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "trusted_host_publication.py":
                continue
            if "TrustedHostPublicationEvidenceController(" in path.read_text():
                callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])
        collection_callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "github_evidence_collector.py":
                continue
            if ".collect_from_verified_host(" in path.read_text():
                collection_callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            collection_callers,
            ["pathfinder_core/trusted_host_publication.py"],
        )


if __name__ == "__main__":
    unittest.main()
