from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum


class EligibilityOutcome(str, Enum):
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    POLICY_BLOCKED = "policy-blocked"
    ELIGIBLE = "eligible"


class DenyCode(str, Enum):
    POLICY_MISSING = "policy-missing"
    AUTHORIZATION_MISSING = "authorization-missing"
    EVIDENCE_MISSING = "evidence-missing"
    PROTECTED_POLICY_MISSING = "protected-policy-missing"
    INPUT_INVALID = "input-invalid"
    POLICY_EXPIRED = "policy-expired"
    AUTHORIZATION_EXPIRED = "authorization-expired"
    EVIDENCE_EXPIRED = "evidence-expired"
    IDENTITY_DRIFT = "identity-drift"
    DIFF_DRIFT = "diff-drift"
    API_VERSION_UNKNOWN = "api-version-unknown"
    PAGINATION_INCOMPLETE = "pagination-incomplete"
    CLASSIC_PROTECTION_UNKNOWN = "classic-protection-unknown"
    RULESET_EVIDENCE_INCOMPLETE = "ruleset-evidence-incomplete"
    RULESET_DRIFT = "ruleset-drift"
    BYPASS_VISIBILITY_UNKNOWN = "bypass-visibility-unknown"
    ACTOR_IDENTITY_UNKNOWN = "actor-identity-unknown"
    REVIEW_STATE_UNKNOWN = "review-state-unknown"
    CHECK_EVIDENCE_INCOMPLETE = "check-evidence-incomplete"
    MERGE_STATE_UNKNOWN = "merge-state-unknown"
    DIFF_INCOMPLETE = "diff-incomplete"
    FIELD_UNKNOWN = "field-unknown"
    MERGE_QUEUE_REQUIRED = "merge-queue-required"
    UNSUPPORTED_REQUIRED_DEPLOYMENTS = "unsupported-required-deployments"
    UNSUPPORTED_REQUIRED_SIGNATURES = "unsupported-required-signatures"
    UNSUPPORTED_CODE_SCANNING = "unsupported-code-scanning"
    UNSUPPORTED_CODE_QUALITY = "unsupported-code-quality"
    UNSUPPORTED_FILE_RESTRICTION = "unsupported-file-restriction"
    UNSUPPORTED_METADATA_RESTRICTION = "unsupported-metadata-restriction"
    UNSUPPORTED_ACTIVE_RULE = "unsupported-active-rule"
    UNSUPPORTED_MERGE_METHOD = "unsupported-merge-method"
    REPOSITORY_UNAVAILABLE = "repository-unavailable"
    PULL_REQUEST_NOT_OPEN = "pull-request-not-open"
    DRAFT = "draft"
    FORK = "fork"
    CONTROLLER_BRANCH_UNPROVEN = "controller-branch-unproven"
    PROTECTED_SURFACE = "protected-surface"
    PATH_NOT_ALLOWED = "path-not-allowed"
    PATH_DENIED = "path-denied"
    DIFF_LIMIT_EXCEEDED = "diff-limit-exceeded"
    POLICY_UNENFORCED = "policy-unenforced"
    INDEPENDENT_REVIEW_NOT_ENFORCED = "independent-review-not-enforced"
    MERGE_ACTOR_CAN_BYPASS = "merge-actor-can-bypass"
    INDEPENDENT_REVIEW_MISSING = "independent-review-missing"
    CHANGES_REQUESTED = "changes-requested"
    CODE_OWNER_REVIEW_MISSING = "code-owner-review-missing"
    UNRESOLVED_THREAD = "unresolved-thread"
    REVIEW_DRIFT = "review-drift"
    REQUIRED_CHECK_UNPROVEN = "required-check-unproven"
    REQUIRED_CHECK_PENDING = "required-check-pending"
    REQUIRED_CHECK_FAILED = "required-check-failed"
    UNEXPECTED_CHECK_APP = "unexpected-check-app"
    CHECK_SHA_DRIFT = "check-sha-drift"
    BASE_BEHIND = "base-behind"
    MERGE_CONFLICT = "merge-conflict"


UNKNOWN_CODES = frozenset({
    DenyCode.POLICY_MISSING, DenyCode.AUTHORIZATION_MISSING,
    DenyCode.EVIDENCE_MISSING, DenyCode.PROTECTED_POLICY_MISSING,
    DenyCode.INPUT_INVALID, DenyCode.POLICY_EXPIRED,
    DenyCode.AUTHORIZATION_EXPIRED, DenyCode.EVIDENCE_EXPIRED,
    DenyCode.IDENTITY_DRIFT, DenyCode.DIFF_DRIFT, DenyCode.API_VERSION_UNKNOWN,
    DenyCode.PAGINATION_INCOMPLETE, DenyCode.CLASSIC_PROTECTION_UNKNOWN,
    DenyCode.RULESET_EVIDENCE_INCOMPLETE, DenyCode.RULESET_DRIFT,
    DenyCode.BYPASS_VISIBILITY_UNKNOWN, DenyCode.ACTOR_IDENTITY_UNKNOWN,
    DenyCode.REVIEW_STATE_UNKNOWN, DenyCode.REVIEW_DRIFT,
    DenyCode.CHECK_EVIDENCE_INCOMPLETE, DenyCode.CHECK_SHA_DRIFT,
    DenyCode.MERGE_STATE_UNKNOWN, DenyCode.DIFF_INCOMPLETE, DenyCode.FIELD_UNKNOWN,
})
UNSUPPORTED_CODES = frozenset({
    DenyCode.MERGE_QUEUE_REQUIRED, DenyCode.UNSUPPORTED_REQUIRED_DEPLOYMENTS,
    DenyCode.UNSUPPORTED_REQUIRED_SIGNATURES, DenyCode.UNSUPPORTED_CODE_SCANNING,
    DenyCode.UNSUPPORTED_CODE_QUALITY, DenyCode.UNSUPPORTED_FILE_RESTRICTION,
    DenyCode.UNSUPPORTED_METADATA_RESTRICTION, DenyCode.UNSUPPORTED_ACTIVE_RULE,
    DenyCode.UNSUPPORTED_MERGE_METHOD,
})


@dataclass(frozen=True, order=True)
class CheckRequirement:
    context: str
    app_id: int


@dataclass(frozen=True)
class EligibilityBlock:
    code: DenyCode
    surface: str
    detail: str


@dataclass(frozen=True)
class MergeEligibilityVerdict:
    outcome: EligibilityOutcome
    blocks: tuple[EligibilityBlock, ...]
    required_approvals: int
    approval_actor_ids: tuple[int, ...]
    required_checks: tuple[CheckRequirement, ...]
    policy_sha256: str | None
    authorization_sha256: str | None
    evidence_sha256: str | None

    @property
    def eligible(self) -> bool:
        return self.outcome is EligibilityOutcome.ELIGIBLE

    @property
    def intent_ready(self) -> bool:
        """A single snapshot is advisory and can never authorize merge intent."""
        return False


@dataclass(frozen=True)
class EvidenceSnapshotBinding:
    evidence_id: str
    evidence_sha256: str
    policy_read_receipt_id: str
    request_ids_sha256: str
    observed_at: str
    completed_at: str
    expires_at: str

    @classmethod
    def from_evidence(cls, evidence) -> "EvidenceSnapshotBinding":
        observation = evidence["observation"]
        return cls(
            evidence["evidence_id"],
            evidence["evidence_sha256"],
            observation["policy_read"]["receipt_id"],
            observation["request_ids_sha256"],
            observation["observed_at"],
            observation["completed_at"],
            observation["expires_at"],
        )

    def to_document(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "evidence_sha256": self.evidence_sha256,
            "policy_read_receipt_id": self.policy_read_receipt_id,
            "request_ids_sha256": self.request_ids_sha256,
            "observed_at": self.observed_at,
            "completed_at": self.completed_at,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class MergeReadinessProof:
    policy_id: str
    policy_sha256: str
    merge_authorization_id: str
    authorization_sha256: str
    protected_policy_sha256: str
    initial_snapshot: EvidenceSnapshotBinding
    reread_snapshot: EvidenceSnapshotBinding
    proof_sha256: str

    @classmethod
    def build(cls, policy, authorization, initial, reread) -> "MergeReadinessProof":
        values = {
            "policy_id": policy["policy_id"],
            "policy_sha256": policy["policy_sha256"],
            "merge_authorization_id": authorization["merge_authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
            "protected_policy_sha256": policy["path_policy"][
                "protected_policy_sha256"
            ],
            "initial_snapshot": EvidenceSnapshotBinding.from_evidence(initial),
            "reread_snapshot": EvidenceSnapshotBinding.from_evidence(reread),
        }
        provisional = cls(**values, proof_sha256="0" * 64)
        payload = provisional.to_document()
        del payload["proof_sha256"]
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()
        return cls(
            **values,
            proof_sha256=hashlib.sha256(encoded).hexdigest(),
        )

    def to_document(self) -> dict:
        return {
            "schema_version": 1,
            "outcome": "intent-ready",
            "policy": {
                "policy_id": self.policy_id,
                "policy_sha256": self.policy_sha256,
            },
            "authorization": {
                "merge_authorization_id": self.merge_authorization_id,
                "authorization_sha256": self.authorization_sha256,
            },
            "protected_policy_sha256": self.protected_policy_sha256,
            "initial_snapshot": self.initial_snapshot.to_document(),
            "reread_snapshot": self.reread_snapshot.to_document(),
            "proof_sha256": self.proof_sha256,
        }


@dataclass(frozen=True)
class MergeReadinessEvaluation:
    verdict: MergeEligibilityVerdict
    proof: MergeReadinessProof | None

    @property
    def intent_ready(self) -> bool:
        return self.verdict.eligible and self.proof is not None
