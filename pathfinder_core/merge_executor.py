from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol

from .adapters.github_merge_writer import (
    GitHubMergeBackend,
    MergeAPIResponse,
    MergeObservation,
    MergeResponseLost,
)
from .errors import StateError
from .merge_credentials import GitHubMergeCredential
from .merge_journal import MergeOperationJournal
from .merge_policy import MergePolicyEvaluator, canonical_sha256
from .merge_time import parse_aware_timestamp


@dataclass(frozen=True)
class VerifiedMergeEnvelope:
    envelope_id: str
    source: str
    authenticated_at: str
    policy: dict
    authorization: dict
    protected_policy: dict
    initial_evidence: dict
    reread_evidence: dict
    readiness_proof: dict
    intent: dict


class HostMergeEnvelopeReader(Protocol):
    def read_fresh_verified(
        self, envelope_id: str, *, now: datetime
    ) -> VerifiedMergeEnvelope: ...


class HostMergeCredentialReader(Protocol):
    def read_fresh_verified(
        self, credential_id: str, *, now: datetime
    ) -> GitHubMergeCredential: ...


class MergeBackend(Protocol):
    def merge(
        self,
        intent: Mapping[str, object],
        credential: GitHubMergeCredential,
        *,
        dispatch: Callable[[], None],
    ) -> MergeAPIResponse: ...

    def observe(
        self, intent: Mapping[str, object], credential: GitHubMergeCredential
    ) -> MergeObservation: ...


@dataclass(frozen=True)
class MergeExecutionDisposition:
    operation_id: str
    outcome: str
    reason: str
    result: Mapping[str, object] | None


class MergeExecutor:
    """Uncomposed one-use K4 executor. It never discovers work or credentials."""

    def __init__(
        self,
        journal: MergeOperationJournal,
        envelopes: HostMergeEnvelopeReader,
        credentials: HostMergeCredentialReader,
        backend: MergeBackend | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.journal = journal
        self.envelopes = envelopes
        self.credentials = credentials
        self.backend = backend or GitHubMergeBackend()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _pending(operation_id: str) -> MergeExecutionDisposition:
        return MergeExecutionDisposition(
            operation_id, "reconcile-required", "pending-intent", None
        )

    @staticmethod
    def _from_result(result: Mapping[str, object]) -> MergeExecutionDisposition:
        return MergeExecutionDisposition(
            str(result["operation_id"]),
            str(result["outcome"]),
            str(result["reason"]),
            result,
        )

    def _existing(self, operation_id: str) -> MergeExecutionDisposition | None:
        if not self.journal.intent_exists(operation_id):
            return None
        loaded = self.journal.load(operation_id)
        if loaded["result"] is None:
            return self._pending(operation_id)
        return self._from_result(loaded["result"])

    @staticmethod
    def _validate_envelope(
        envelope_id: str,
        envelope: VerifiedMergeEnvelope,
        operation_id: str,
        now: datetime,
    ) -> None:
        if envelope.envelope_id != envelope_id:
            raise StateError("merge envelope identity differs")
        if envelope.source != "authenticated-host-storage":
            raise StateError("merge envelope is not from authenticated host storage")
        try:
            envelope_current = (
                parse_aware_timestamp(envelope.authenticated_at) == now
            )
            intent_current = parse_aware_timestamp(envelope.intent["started_at"]) == now
        except (KeyError, TypeError, ValueError):
            envelope_current = False
            intent_current = False
        if not envelope_current:
            raise StateError("merge envelope authentication time is invalid")
        if not intent_current:
            raise StateError("merge intent must be created at execution time")
        if envelope.intent.get("operation_id") != operation_id:
            raise StateError("merge operation identity differs from its envelope")
        evaluation = MergePolicyEvaluator().evaluate_reread(
            envelope.policy,
            envelope.authorization,
            envelope.protected_policy,
            envelope.initial_evidence,
            envelope.reread_evidence,
            now=now,
        )
        if not evaluation.intent_ready or evaluation.proof is None:
            reasons = ",".join(block.code.value for block in evaluation.verdict.blocks)
            raise StateError(f"merge envelope is not intent-ready: {reasons}")
        if envelope.readiness_proof != evaluation.proof.to_document():
            raise StateError("merge envelope readiness proof differs from fresh replay")

    @staticmethod
    def _proof(
        intent: Mapping[str, object],
        observation: MergeObservation,
        *,
        proof_source: str,
        response: MergeAPIResponse | None,
        completed_at: datetime,
        dispatch_started_at: str,
    ) -> dict | None:
        if not observation.complete or observation.document is None:
            return None
        value = observation.document
        repository = intent["repository"]
        pull_request = intent["pull_request"]
        actor = intent["actor"]
        expected = {
            "repository_id": repository["id"],
            "repository_node_id": repository["node_id"],
            "pull_request_id": pull_request["id"],
            "pull_request_node_id": pull_request["node_id"],
            "pull_request_number": pull_request["number"],
            "state": "closed",
            "merged": True,
            "head_sha": pull_request["head_sha"],
            "head_repository_id": repository["id"],
            "base_ref": repository["base_branch"],
            "base_repository_id": repository["id"],
            "base_sha_after": value.get("merge_commit_sha"),
            "merge_commit_parent_shas": [pull_request["base_sha"]],
            "merged_by": {
                "actor_id": actor["actor_id"],
                "actor_node_id": actor["actor_node_id"],
                "login": actor["login"],
            },
            "merge_endpoint_status": 204,
        }
        if any(
            value.get(key) != expected_value
            for key, expected_value in expected.items()
        ):
            return None
        merge_sha = value.get("merge_commit_sha")
        if (
            not isinstance(merge_sha, str)
            or len(merge_sha) != 40
            or any(character not in "0123456789abcdef" for character in merge_sha)
        ):
            return None
        request_ids = value.get("request_ids")
        if (
            not isinstance(request_ids, list)
            or len(request_ids) != 4
            or len(set(request_ids)) != 4
            or any(not isinstance(item, str) or not item for item in request_ids)
        ):
            return None
        if proof_source == "response-and-reread":
            if (
                response is None
                or response.request_id is None
                or response.document is None
                or response.document.get("sha") != merge_sha
            ):
                return None
            request_ids = [response.request_id, *request_ids]
        try:
            timeline = (
                parse_aware_timestamp(intent["started_at"])
                <= parse_aware_timestamp(dispatch_started_at)
                <= parse_aware_timestamp(value["merged_at"])
                <= parse_aware_timestamp(value["observed_at"])
                <= completed_at
            )
        except (KeyError, TypeError, ValueError):
            timeline = False
        if not timeline or len(set(request_ids)) != len(request_ids):
            return None
        return {
            "proof_source": proof_source,
            "repository_id": repository["id"],
            "pull_request_id": pull_request["id"],
            "pull_request_node_id": pull_request["node_id"],
            "pull_request_number": pull_request["number"],
            "head_sha": pull_request["head_sha"],
            "base_ref": repository["base_branch"],
            "base_sha_before": pull_request["base_sha"],
            "base_sha_after": merge_sha,
            "merge_commit_sha": merge_sha,
            "merge_commit_parent_shas": [pull_request["base_sha"]],
            "merged_at": value["merged_at"],
            "merged_by": expected["merged_by"],
            "merge_endpoint_status": 204,
            "request_ids": request_ids,
            "observed_at": value["observed_at"],
        }

    @staticmethod
    def _result(
        envelope: VerifiedMergeEnvelope,
        outcome: str,
        reason: str,
        *,
        completed_at: datetime,
        merge_proof: dict | None = None,
    ) -> dict:
        intent = envelope.intent
        operation_suffix = str(intent["operation_id"]).removeprefix("merge_operation_")
        result = {
            "schema_version": 2,
            "result_id": f"merge_result_{operation_suffix}",
            "operation_id": intent["operation_id"],
            "intent_sha256": intent["intent_sha256"],
            "outcome": outcome,
            "reason": reason,
            "binding": {
                "readiness_proof_sha256": envelope.readiness_proof["proof_sha256"],
                "policy_sha256": envelope.policy["policy_sha256"],
                "authorization_sha256": envelope.authorization["authorization_sha256"],
                "repository": {
                    key: intent["repository"][key] for key in ("id", "node_id")
                },
                "pull_request": intent["pull_request"],
                "actor": intent["actor"],
                "merge_method": "squash",
            },
            "merge_proof": merge_proof,
            "completed_at": completed_at.isoformat(),
            "result_sha256": "0" * 64,
        }
        result["result_sha256"] = canonical_sha256(result, "result_sha256")
        return result

    def _record(
        self,
        envelope: VerifiedMergeEnvelope,
        outcome: str,
        reason: str,
        *,
        merge_proof: dict | None = None,
    ) -> MergeExecutionDisposition:
        result = self._result(
            envelope,
            outcome,
            reason,
            completed_at=self.clock(),
            merge_proof=merge_proof,
        )
        return self._from_result(self.journal.record_result(result))

    def _observe_after_ambiguity(
        self,
        envelope: VerifiedMergeEnvelope,
        credential: GitHubMergeCredential,
        *,
        allow_merged: bool,
        dispatch_started_at: str,
        credit_merged: bool = True,
        unresolved_outcome: str = "reconcile-required",
        unresolved_reason: str | None = None,
    ) -> MergeExecutionDisposition:
        observation = self.backend.observe(envelope.intent, credential)
        completed = self.clock()
        proof = self._proof(
            envelope.intent,
            observation,
            proof_source="reconciliation-reread",
            response=None,
            completed_at=completed,
            dispatch_started_at=dispatch_started_at,
        )
        if allow_merged and credit_merged and proof is not None:
            result = self._result(
                envelope,
                "merged",
                "confirmed-after-response-loss",
                completed_at=completed,
                merge_proof=proof,
            )
            return self._from_result(self.journal.record_result(result))
        reason = unresolved_reason or (
            "transport-ambiguous"
            if not observation.complete
            else "merge-proof-incomplete"
        )
        result = self._result(
            envelope,
            unresolved_outcome,
            reason,
            completed_at=completed,
        )
        return self._from_result(self.journal.record_result(result))

    def _classify_method_not_allowed(
        self,
        envelope: VerifiedMergeEnvelope,
        credential: GitHubMergeCredential,
        dispatch_started_at: str,
    ) -> MergeExecutionDisposition:
        """Distinguish an already-merged PR without trusting response text."""
        observation = self.backend.observe(envelope.intent, credential)
        completed = self.clock()
        proof = self._proof(
            envelope.intent,
            observation,
            proof_source="reconciliation-reread",
            response=None,
            completed_at=completed,
            dispatch_started_at=dispatch_started_at,
        )
        reason = "already-merged" if proof is not None else "unmergeable"
        result = self._result(
            envelope,
            "not-merged",
            reason,
            completed_at=completed,
        )
        return self._from_result(self.journal.record_result(result))

    def execute(
        self,
        operation_id: str,
        envelope_id: str,
        credential_id: str,
        *,
        now: datetime | None = None,
    ) -> MergeExecutionDisposition:
        existing = self._existing(operation_id)
        if existing is not None:
            return existing
        current = now or self.clock()
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise StateError("merge execution time requires a UTC offset")
        envelope = self.envelopes.read_fresh_verified(envelope_id, now=current)
        self._validate_envelope(envelope_id, envelope, operation_id, current)
        credential = self.credentials.read_fresh_verified(
            credential_id, now=current
        )
        if credential.credential_id != credential_id:
            raise StateError("merge credential identity differs")
        credential.validate_binding(
            envelope.intent["repository"], envelope.intent["actor"], now=current
        )
        claim = self.journal.claim_intent(
            policy=envelope.policy,
            authorization=envelope.authorization,
            credential_receipt=credential.receipt_document(),
            protected_policy=envelope.protected_policy,
            initial_evidence=envelope.initial_evidence,
            reread_evidence=envelope.reread_evidence,
            readiness_proof=envelope.readiness_proof,
            intent=envelope.intent,
        )
        if claim is None:
            existing = self._existing(operation_id)
            if existing is None:
                raise StateError("merge intent claim disappeared after persistence")
            return existing
        try:
            dispatch, response = self.journal.dispatch_once(
                claim,
                started_at=current.isoformat(),
                send=lambda dispatch: self.backend.merge(
                    envelope.intent, credential, dispatch=dispatch
                ),
            )
        except MergeResponseLost:
            dispatch = self.journal.load(operation_id)["dispatch"]
            if dispatch is None:
                raise StateError("merge response was lost before dispatch persistence")
            return self._observe_after_ambiguity(
                envelope,
                credential,
                allow_merged=True,
                dispatch_started_at=dispatch["dispatch_started_at"],
            )

        if response.status == 200 and not response.malformed:
            if response.document["merged"] is False:
                return self._record(
                    envelope, "not-merged", "remote-reported-not-merged"
                )
            observation = self.backend.observe(envelope.intent, credential)
            completed = self.clock()
            proof = self._proof(
                envelope.intent,
                observation,
                proof_source="response-and-reread",
                response=response,
                completed_at=completed,
                dispatch_started_at=dispatch["dispatch_started_at"],
            )
            if proof is None:
                result = self._result(
                    envelope,
                    "reconcile-required",
                    "merge-proof-incomplete",
                    completed_at=completed,
                )
            else:
                result = self._result(
                    envelope,
                    "merged",
                    "confirmed-merged",
                    completed_at=completed,
                    merge_proof=proof,
                )
            return self._from_result(self.journal.record_result(result))
        if response.malformed:
            return self._observe_after_ambiguity(
                envelope,
                credential,
                allow_merged=False,
                dispatch_started_at=dispatch["dispatch_started_at"],
                unresolved_reason="malformed-response",
            )
        if response.status >= 500 or response.status not in {
            401, 403, 404, 405, 409, 422, 429
        }:
            return self._observe_after_ambiguity(
                envelope,
                credential,
                allow_merged=False,
                dispatch_started_at=dispatch["dispatch_started_at"],
                unresolved_outcome="api-unavailable",
                unresolved_reason="server-error",
            )
        if response.status == 401:
            return self._record(envelope, "auth-error", "authentication-failed")
        response_headers = {
            str(key).lower(): str(value) for key, value in response.headers.items()
        }
        if response.status == 403 and (
            response_headers.get("x-ratelimit-remaining") == "0"
            or "retry-after" in response_headers
        ):
            return self._record(envelope, "rate-limited", "rate-limit-exceeded")
        if response.status == 405:
            return self._classify_method_not_allowed(
                envelope,
                credential,
                dispatch["dispatch_started_at"],
            )
        outcomes = {
            403: ("permission-missing", "permission-denied"),
            404: ("permission-missing", "not-found"),
            409: ("not-merged", "head-mismatch"),
            422: ("not-merged", "validation-failed"),
            429: ("rate-limited", "rate-limit-exceeded"),
        }
        outcome, reason = outcomes[response.status]
        return self._record(envelope, outcome, reason)

    def reconcile(
        self,
        operation_id: str,
        credential_id: str,
        *,
        now: datetime | None = None,
    ) -> MergeExecutionDisposition:
        if not self.journal.intent_exists(operation_id):
            raise StateError(f"merge operation not found: {operation_id}")
        loaded = self.journal.load(operation_id)
        if loaded["result"] is not None:
            return self._from_result(loaded["result"])
        intent = loaded["intent"]
        current = now or self.clock()
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise StateError("merge reconciliation time requires a UTC offset")
        envelope = VerifiedMergeEnvelope(
            envelope_id="persisted-merge-journal",
            source="authenticated-host-storage",
            authenticated_at=intent["started_at"],
            policy=loaded["inputs"]["policy"],
            authorization=loaded["inputs"]["authorization"],
            protected_policy=loaded["inputs"]["protected-policy"],
            initial_evidence=loaded["inputs"]["initial-evidence"],
            reread_evidence=loaded["inputs"]["reread-evidence"],
            readiness_proof=loaded["inputs"]["readiness-proof"],
            intent=intent,
        )
        if loaded["dispatch"] is None:
            return self._record(
                envelope, "reconcile-required", "dispatch-not-started"
            )
        credential = self.credentials.read_fresh_verified(
            credential_id, now=current
        )
        if credential.credential_id != credential_id:
            raise StateError("merge credential identity differs")
        credential.validate_binding(
            intent["repository"], intent["actor"], now=current
        )
        current_receipt = credential.receipt_document()
        persisted_receipt = loaded["inputs"]["credential-receipt"]
        stable_receipt_fields = (
            "source",
            "credential_id",
            "kind",
            "boundary",
            "permissions",
            "repository_selection",
            "repository_ids",
            "app_id",
            "app_node_id",
            "installation_id",
            "installation_account_id",
            "actor_id",
            "actor_node_id",
            "login",
            "suspended",
        )
        if any(
            current_receipt[field] != persisted_receipt[field]
            for field in stable_receipt_fields
        ):
            raise StateError("merge credential receipt differs from persisted intent")
        return self._observe_after_ambiguity(
            envelope,
            credential,
            allow_merged=True,
            dispatch_started_at=loaded["dispatch"]["dispatch_started_at"],
            credit_merged=False,
            unresolved_reason="transport-ambiguous",
        )
