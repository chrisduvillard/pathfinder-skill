from __future__ import annotations

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
    DenyCode.EVIDENCE_MISSING, DenyCode.INPUT_INVALID, DenyCode.POLICY_EXPIRED,
    DenyCode.AUTHORIZATION_EXPIRED, DenyCode.EVIDENCE_EXPIRED,
    DenyCode.IDENTITY_DRIFT, DenyCode.DIFF_DRIFT, DenyCode.API_VERSION_UNKNOWN,
    DenyCode.PAGINATION_INCOMPLETE, DenyCode.CLASSIC_PROTECTION_UNKNOWN,
    DenyCode.RULESET_EVIDENCE_INCOMPLETE, DenyCode.RULESET_DRIFT,
    DenyCode.BYPASS_VISIBILITY_UNKNOWN, DenyCode.ACTOR_IDENTITY_UNKNOWN,
    DenyCode.REVIEW_STATE_UNKNOWN, DenyCode.CHECK_EVIDENCE_INCOMPLETE,
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
