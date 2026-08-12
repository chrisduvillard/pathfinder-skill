from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from .adapters.github import (
    GitHubPublisher,
    PublicationResult,
    PublicationState,
    PullRequest,
)
from .errors import StateError
from .merge_time import parse_aware_timestamp
from .publication_journal import PublicationJournal
from .storage import canonical_sha256


@dataclass(frozen=True)
class VerifiedPublicationEnvelope:
    envelope_id: str
    source: str
    authenticated_at: str
    request: dict


class HostPublicationEnvelopeReader(Protocol):
    def read_fresh_verified(
        self, envelope_id: str, *, now: datetime
    ) -> VerifiedPublicationEnvelope: ...


@dataclass(frozen=True)
class PublicationDisposition:
    publication_request_id: str
    state: str
    reason: str
    receipt: dict | None


class PublicationController:
    """Explicit, uncomposed awaiting-review publication boundary."""

    def __init__(
        self,
        journal: PublicationJournal,
        envelopes: HostPublicationEnvelopeReader,
        publisher: GitHubPublisher,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.journal = journal
        self.envelopes = envelopes
        self.publisher = publisher
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _from_receipt(receipt: dict) -> PublicationDisposition:
        return PublicationDisposition(
            receipt["publication_request_id"],
            "awaiting-review",
            "publication-confirmed",
            receipt,
        )

    @staticmethod
    def _pending(request_id: str, reason: str) -> PublicationDisposition:
        return PublicationDisposition(
            request_id, "reconcile-required", reason, None
        )

    def _existing(self, request_id: str) -> PublicationDisposition | None:
        if not self.journal.request_exists(request_id):
            return None
        loaded = self.journal.load(request_id)
        if loaded["receipt"] is not None:
            return self._from_receipt(loaded["receipt"])
        return self._pending(request_id, "pending-publication")

    @staticmethod
    def _validate_envelope(
        envelope_id: str,
        envelope: VerifiedPublicationEnvelope,
        request_id: str,
        now: datetime,
    ) -> dict:
        if envelope.envelope_id != envelope_id:
            raise StateError("publication envelope identity differs")
        if envelope.source != "authenticated-host-storage":
            raise StateError(
                "publication envelope is not from authenticated host storage"
            )
        request = envelope.request
        try:
            issued = parse_aware_timestamp(request["issued_at"])
            expires = parse_aware_timestamp(request["expires_at"])
            current = parse_aware_timestamp(envelope.authenticated_at)
        except (KeyError, TypeError, ValueError) as error:
            raise StateError("publication envelope time is malformed") from error
        if current != now:
            raise StateError("publication envelope authentication time is stale")
        if not issued <= now < expires <= issued + timedelta(minutes=15):
            raise StateError("publication request is expired or exceeds 15 minutes")
        if request.get("publication_request_id") != request_id:
            raise StateError("publication request identity differs")
        mission = request.get("mission", {})
        candidate = request.get("candidate", {})
        if mission.get("commit_sha") != candidate.get("head_sha"):
            raise StateError("publication request commit and head SHA differ")
        if not str(candidate.get("head_ref", "")).startswith("pathfinder/auto/"):
            raise StateError("publication request head is not a controller branch")
        return request

    @staticmethod
    def _validate_pull_request(request: dict, pull_request: PullRequest) -> None:
        identity = pull_request.identity
        if identity is None:
            raise StateError("publisher returned no exact pull request identity")
        expected = {
            "repository_id": request["repository"]["id"],
            "repository_node_id": request["repository"]["node_id"],
            "head_sha": request["candidate"]["head_sha"],
            "base_sha": request["candidate"]["base_sha"],
        }
        if any(getattr(identity, key) != value for key, value in expected.items()):
            raise StateError("published pull request object identity differs")
        if (
            pull_request.head != request["candidate"]["head_ref"]
            or pull_request.base != request["candidate"]["base_ref"]
            or pull_request.mission_id != request["mission"]["mission_id"]
        ):
            raise StateError("published pull request mission or ref identity differs")

    @staticmethod
    def _receipt(
        request: dict,
        result: PublicationResult,
        *,
        observed_at: datetime,
    ) -> dict:
        pull_request = result.pull_request
        if pull_request is None or pull_request.identity is None:
            raise StateError("publication success lacks exact pull request identity")
        PublicationController._validate_pull_request(request, pull_request)
        identity = pull_request.identity
        suffix = request["publication_request_id"].removeprefix(
            "publication_request_"
        )
        receipt = {
            "schema_version": 1,
            "publication_receipt_id": f"publication_receipt_{suffix}",
            "publication_request_id": request["publication_request_id"],
            "request_sha256": request["request_sha256"],
            "source": "authenticated-controller-publication",
            "state": "awaiting-review",
            "mission": {
                key: request["mission"][key]
                for key in (
                    "mission_id",
                    "binding_id",
                    "mission_authorization_id",
                    "mission_state_sha256",
                )
            },
            "repository": request["repository"],
            "pull_request": {
                "id": identity.id,
                "node_id": identity.node_id,
                "number": identity.number,
                "url": pull_request.url,
                "head_ref": pull_request.head,
                "head_sha": identity.head_sha,
                "base_ref": pull_request.base,
                "base_sha": identity.base_sha,
            },
            "diff": request["candidate"]["diff"],
            "checks": {"state": "success", "polls": result.polls},
            "reused": result.reused,
            "observed_at": observed_at.isoformat(),
            "receipt_sha256": "0" * 64,
        }
        receipt["receipt_sha256"] = canonical_sha256(
            receipt, "receipt_sha256"
        )
        return receipt

    def _record_success(
        self,
        request: dict,
        result: PublicationResult,
        *,
        observed_at: datetime | None = None,
    ) -> PublicationDisposition:
        if result.state is not PublicationState.AWAITING_REVIEW:
            return PublicationDisposition(
                request["publication_request_id"],
                result.state.value,
                result.detail,
                None,
            )
        observed_at = observed_at or self.clock()
        if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
            raise StateError("publication observation time requires a UTC offset")
        receipt = self._receipt(request, result, observed_at=observed_at)
        return self._from_receipt(self.journal.record_receipt(receipt))

    def publish(
        self,
        request_id: str,
        envelope_id: str,
        *,
        now: datetime | None = None,
    ) -> PublicationDisposition:
        existing = self._existing(request_id)
        if existing is not None:
            return existing
        current = now or self.clock()
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise StateError("publication time requires a UTC offset")
        envelope = self.envelopes.read_fresh_verified(envelope_id, now=current)
        request = self._validate_envelope(
            envelope_id, envelope, request_id, current
        )
        claim = self.journal.claim_request(request)
        if claim is None:
            existing = self._existing(request_id)
            if existing is None:
                raise StateError("publication request claim disappeared")
            return existing
        _dispatch, result = self.journal.dispatch_once(
            claim,
            started_at=current.isoformat(),
            send=lambda: self.publisher.publish(
                head=request["candidate"]["head_ref"],
                base=request["candidate"]["base_ref"],
                mission_id=request["mission"]["mission_id"],
                title=request["title"],
                body=request["body"],
                max_check_polls=request["max_check_polls"],
                credential_boundary=request["credential_boundary"],
            ),
        )
        return self._record_success(request, result)

    def reconcile(
        self,
        request_id: str,
        *,
        now: datetime | None = None,
    ) -> PublicationDisposition:
        loaded = self.journal.load(request_id)
        if loaded["receipt"] is not None:
            return self._from_receipt(loaded["receipt"])
        if loaded["dispatch"] is None:
            return self._pending(request_id, "dispatch-not-started")
        current = now or self.clock()
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise StateError("publication reconciliation time requires a UTC offset")
        request = loaded["request"]
        result = self.publisher.observe(
            head=request["candidate"]["head_ref"],
            base=request["candidate"]["base_ref"],
            mission_id=request["mission"]["mission_id"],
            credential_boundary=request["credential_boundary"],
        )
        if result.state is PublicationState.AWAITING_REVIEW:
            return self._record_success(request, result, observed_at=current)
        return self._pending(request_id, result.detail)
