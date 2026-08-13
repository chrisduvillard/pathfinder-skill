from __future__ import annotations

import copy
from dataclasses import dataclass

from .adapters.github_evidence_collector import (
    AuthenticatedEvidenceCollection,
    GitHubAuthenticatedEvidenceCollector,
    HostEvidenceCollectionInputProvider,
    NormalizedPolicyBackend,
)
from .errors import StateError
from .publication_controller import (
    PublicationController,
    PublicationDisposition,
)


@dataclass(frozen=True)
class TrustedHostPublicationEvidenceDisposition:
    publication_request_id: str
    state: str
    reason: str
    receipt: dict | None
    evidence_id: str | None
    collection: AuthenticatedEvidenceCollection | None


class TrustedHostPublicationEvidenceController:
    """Explicit awaiting-review publication plus read-only evidence collection."""

    def __init__(
        self,
        *,
        publication: PublicationController,
        collector: GitHubAuthenticatedEvidenceCollector,
        collection_inputs: HostEvidenceCollectionInputProvider,
        policy_backend: NormalizedPolicyBackend,
    ):
        self.publication = publication
        self.collector = collector
        self.collection_inputs = collection_inputs
        self.policy_backend = policy_backend

    @staticmethod
    def _without_collection(
        disposition: PublicationDisposition,
    ) -> TrustedHostPublicationEvidenceDisposition:
        return TrustedHostPublicationEvidenceDisposition(
            disposition.publication_request_id,
            disposition.state,
            disposition.reason,
            None,
            None,
            None,
        )

    def _collect(
        self,
        request_id: str,
        disposition: PublicationDisposition,
    ) -> TrustedHostPublicationEvidenceDisposition:
        if disposition.publication_request_id != request_id:
            raise StateError("publication disposition identity differs")
        if disposition.state != "awaiting-review":
            if disposition.receipt is not None:
                raise StateError("nonterminal publication returned a receipt")
            return self._without_collection(disposition)
        if not isinstance(disposition.receipt, dict):
            raise StateError("awaiting-review publication requires a receipt")

        records = self.publication.journal.load(request_id)
        if (
            records.get("state") != "awaiting-review"
            or records.get("disposition") != "awaiting-review"
            or records.get("receipt") != disposition.receipt
        ):
            raise StateError("publication terminal journal differs from disposition")
        collection = self.collector.collect_from_verified_host(
            policy_backend=self.policy_backend,
            input_provider=self.collection_inputs,
            publication_records=copy.deepcopy(records),
        )
        try:
            evidence_id = collection.snapshot.evidence["evidence_id"]
        except (AttributeError, KeyError, TypeError) as error:
            raise StateError(
                "authenticated evidence collection is malformed"
            ) from error
        if not isinstance(evidence_id, str) or not evidence_id:
            raise StateError("authenticated evidence identity is malformed")
        return TrustedHostPublicationEvidenceDisposition(
            request_id,
            "awaiting-review",
            "publication-and-evidence-confirmed",
            copy.deepcopy(disposition.receipt),
            evidence_id,
            collection,
        )

    def publish_and_collect(
        self, request_id: str, envelope_id: str
    ) -> TrustedHostPublicationEvidenceDisposition:
        return self._collect(
            request_id, self.publication.publish(request_id, envelope_id)
        )

    def reconcile_and_collect(
        self, request_id: str
    ) -> TrustedHostPublicationEvidenceDisposition:
        return self._collect(
            request_id, self.publication.reconcile(request_id)
        )
