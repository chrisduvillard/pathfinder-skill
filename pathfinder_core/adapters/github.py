from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ..errors import CapabilityError, PolicyError


class PublicationState(str, Enum):
    AWAITING_REVIEW = "awaiting-review"
    CHECKS_FAILED = "checks-failed"
    CHECK_TIMEOUT = "check-timeout"
    AUTH_ERROR = "auth-error"
    RATE_LIMITED = "rate-limited"
    PERMISSION_MISSING = "permission-missing"
    API_UNAVAILABLE = "api-unavailable"


class CheckState(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    UNAVAILABLE = "unavailable"


class GitHubError(Exception):
    state = PublicationState.API_UNAVAILABLE


class AuthenticationError(GitHubError):
    state = PublicationState.AUTH_ERROR


class RateLimitError(GitHubError):
    state = PublicationState.RATE_LIMITED


class PermissionError(GitHubError):
    state = PublicationState.PERMISSION_MISSING


@dataclass(frozen=True)
class PullRequestIdentity:
    repository_id: int
    repository_node_id: str
    id: int
    node_id: str
    number: int
    head_sha: str
    base_sha: str


@dataclass(frozen=True)
class RequiredCheck:
    context: str
    app_id: int


@dataclass(frozen=True)
class CheckObservation:
    context: str
    app_id: int
    sha: str
    state: CheckState


@dataclass(frozen=True)
class PublicationTarget:
    repository_id: int
    repository_node_id: str
    repository_owner: str
    repository_name: str
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    mission_id: str
    diff_sha256: str
    changed_files_sha256: str
    object_evidence_sha256: str
    required_checks: tuple[RequiredCheck, ...]


@dataclass(frozen=True)
class PullRequest:
    pr_id: str
    url: str
    head: str
    base: str
    mission_id: str
    identity: PullRequestIdentity | None = None


@dataclass(frozen=True)
class PublicationResult:
    state: PublicationState
    pull_request: PullRequest | None
    reused: bool
    polls: int
    detail: str
    checks: tuple[CheckObservation, ...] = ()


class GitHubBackend(Protocol):
    def push(self, branch: str) -> None: ...
    def find_pull_request(self, head: str, base: str, mission_id: str) -> PullRequest | None: ...
    def create_pull_request(
        self, head: str, base: str, mission_id: str, title: str, body: str
    ) -> PullRequest: ...
    def check_state(self, pull_request: PullRequest) -> CheckState: ...


class ExactGitHubBackend(Protocol):
    """Trusted host adapter; preflight and check observation are read-only."""

    def preflight(self, target: PublicationTarget) -> PublicationTarget: ...
    def push_exact(self, target: PublicationTarget) -> None: ...
    def find_pull_request_exact(
        self, target: PublicationTarget
    ) -> PullRequest | None: ...
    def create_pull_request_exact(
        self, target: PublicationTarget, title: str, body: str
    ) -> PullRequest: ...
    def check_observations_exact(
        self, pull_request: PullRequest, target: PublicationTarget
    ) -> tuple[CheckObservation, ...]: ...


class GitHubPublisher:
    """Credentialed publication boundary. It intentionally exposes no merge operation."""

    def __init__(self, backend: GitHubBackend | ExactGitHubBackend):
        self.backend = backend

    @staticmethod
    def _validate_exact_target(target: PublicationTarget) -> None:
        if (
            target.repository_id < 1
            or not target.repository_node_id
            or not target.repository_owner
            or not target.repository_name
            or not target.head_ref.startswith("pathfinder/auto/")
            or not target.base_ref
            or not target.mission_id.startswith("mission_")
            or len(target.head_sha) != 40
            or len(target.base_sha) != 40
            or any(len(value) != 64 for value in (
                target.diff_sha256,
                target.changed_files_sha256,
                target.object_evidence_sha256,
            ))
            or not target.required_checks
            or len({
                (check.context, check.app_id)
                for check in target.required_checks
            }) != len(target.required_checks)
            or any(
                not check.context or check.app_id < 1
                for check in target.required_checks
            )
        ):
            raise PolicyError("invalid exact publication target")

    @staticmethod
    def _exact_check_state(
        target: PublicationTarget,
        observations: tuple[CheckObservation, ...],
    ) -> CheckState:
        expected = {
            (check.context, check.app_id)
            for check in target.required_checks
        }
        observed = {
            (check.context, check.app_id)
            for check in observations
        }
        if (
            len(observed) != len(observations)
            or observed != expected
            or any(check.sha != target.head_sha for check in observations)
            or any(
                not isinstance(check.state, CheckState)
                for check in observations
            )
        ):
            raise PolicyError("exact publication check identity differs")
        states = {check.state for check in observations}
        if CheckState.FAILURE in states:
            return CheckState.FAILURE
        if CheckState.UNAVAILABLE in states:
            return CheckState.UNAVAILABLE
        if CheckState.PENDING in states:
            return CheckState.PENDING
        if states == {CheckState.SUCCESS}:
            return CheckState.SUCCESS
        raise PolicyError("exact publication check state is invalid")

    @staticmethod
    def _validate_exact_pull_request(
        target: PublicationTarget, pull_request: PullRequest
    ) -> None:
        identity = pull_request.identity
        if identity is None or (
            identity.repository_id != target.repository_id
            or identity.repository_node_id != target.repository_node_id
            or identity.head_sha != target.head_sha
            or identity.base_sha != target.base_sha
            or pull_request.head != target.head_ref
            or pull_request.base != target.base_ref
            or pull_request.mission_id != target.mission_id
        ):
            raise PolicyError("exact pull request identity differs")

    def publish_exact(
        self,
        *,
        target: PublicationTarget,
        title: str,
        body: str,
        max_check_polls: int,
        credential_boundary: str,
    ) -> PublicationResult:
        if credential_boundary != "publication-only":
            raise PolicyError(
                "GitHub credentials must be confined to publication-only boundary"
            )
        self._validate_exact_target(target)
        if not 1 <= max_check_polls <= 100:
            raise PolicyError("max_check_polls must be between 1 and 100")
        backend: ExactGitHubBackend = self.backend  # type: ignore[assignment]
        try:
            if backend.preflight(target) != target:
                raise PolicyError("publication preflight target differs")
            backend.push_exact(target)
            existing = backend.find_pull_request_exact(target)
            pull_request = existing or backend.create_pull_request_exact(
                target, title, body
            )
            self._validate_exact_pull_request(target, pull_request)
            for poll in range(1, max_check_polls + 1):
                observations = backend.check_observations_exact(
                    pull_request, target
                )
                state = self._exact_check_state(target, observations)
                if state is CheckState.SUCCESS:
                    return PublicationResult(
                        PublicationState.AWAITING_REVIEW,
                        pull_request,
                        existing is not None,
                        poll,
                        "required checks passed; human review required",
                        observations,
                    )
                if state is CheckState.FAILURE:
                    return PublicationResult(
                        PublicationState.CHECKS_FAILED,
                        pull_request,
                        existing is not None,
                        poll,
                        "required checks failed",
                        observations,
                    )
                if state is CheckState.UNAVAILABLE:
                    return PublicationResult(
                        PublicationState.API_UNAVAILABLE,
                        pull_request,
                        existing is not None,
                        poll,
                        "check state unavailable",
                        observations,
                    )
            return PublicationResult(
                PublicationState.CHECK_TIMEOUT,
                pull_request,
                existing is not None,
                max_check_polls,
                "required checks remained pending",
                observations,
            )
        except GitHubError as error:
            return PublicationResult(error.state, None, False, 0, str(error))

    def observe_exact(
        self,
        *,
        target: PublicationTarget,
        credential_boundary: str,
    ) -> PublicationResult:
        if credential_boundary != "publication-only":
            raise PolicyError(
                "GitHub credentials must be confined to publication-only boundary"
            )
        self._validate_exact_target(target)
        backend: ExactGitHubBackend = self.backend  # type: ignore[assignment]
        try:
            if backend.preflight(target) != target:
                raise PolicyError("publication preflight target differs")
            pull_request = backend.find_pull_request_exact(target)
            if pull_request is None:
                return PublicationResult(
                    PublicationState.API_UNAVAILABLE,
                    None,
                    False,
                    0,
                    "exact pull request not found",
                )
            self._validate_exact_pull_request(target, pull_request)
            observations = backend.check_observations_exact(
                pull_request, target
            )
            state = self._exact_check_state(target, observations)
            outcomes = {
                CheckState.SUCCESS: (
                    PublicationState.AWAITING_REVIEW,
                    "required checks passed; human review required",
                ),
                CheckState.FAILURE: (
                    PublicationState.CHECKS_FAILED,
                    "required checks failed",
                ),
                CheckState.PENDING: (
                    PublicationState.CHECK_TIMEOUT,
                    "required checks remain pending",
                ),
                CheckState.UNAVAILABLE: (
                    PublicationState.API_UNAVAILABLE,
                    "check state unavailable",
                ),
            }
            outcome, detail = outcomes[state]
            return PublicationResult(
                outcome, pull_request, True, 1, detail, observations
            )
        except GitHubError as error:
            return PublicationResult(error.state, None, False, 0, str(error))

    def publish(
        self, *, head: str, base: str, mission_id: str, title: str, body: str,
        max_check_polls: int = 10, credential_boundary: str,
    ) -> PublicationResult:
        if credential_boundary != "publication-only":
            raise PolicyError("GitHub credentials must be confined to publication-only boundary")
        if not head.startswith("pathfinder/auto/") or not base or not mission_id.startswith("mission_"):
            raise PolicyError("invalid idempotent publication identity")
        if not 1 <= max_check_polls <= 100:
            raise PolicyError("max_check_polls must be between 1 and 100")
        try:
            self.backend.push(head)
            existing = self.backend.find_pull_request(head, base, mission_id)
            pull_request = existing or self.backend.create_pull_request(
                head, base, mission_id, title, body
            )
            for poll in range(1, max_check_polls + 1):
                state = self.backend.check_state(pull_request)
                if state is CheckState.SUCCESS:
                    return PublicationResult(
                        PublicationState.AWAITING_REVIEW, pull_request, existing is not None,
                        poll, "required checks passed; human review required",
                    )
                if state is CheckState.FAILURE:
                    return PublicationResult(
                        PublicationState.CHECKS_FAILED, pull_request, existing is not None,
                        poll, "required checks failed",
                    )
                if state is CheckState.UNAVAILABLE:
                    return PublicationResult(
                        PublicationState.API_UNAVAILABLE, pull_request, existing is not None,
                        poll, "check state unavailable",
                    )
            return PublicationResult(
                PublicationState.CHECK_TIMEOUT, pull_request, existing is not None,
                max_check_polls, "required checks remained pending",
            )
        except GitHubError as error:
            return PublicationResult(error.state, None, False, 0, str(error))

    def observe(
        self,
        *,
        head: str,
        base: str,
        mission_id: str,
        credential_boundary: str,
    ) -> PublicationResult:
        """Observe one exact publication identity without push or PR creation."""
        if credential_boundary != "publication-only":
            raise PolicyError(
                "GitHub credentials must be confined to publication-only boundary"
            )
        if (
            not head.startswith("pathfinder/auto/")
            or not base
            or not mission_id.startswith("mission_")
        ):
            raise PolicyError("invalid idempotent publication identity")
        try:
            pull_request = self.backend.find_pull_request(head, base, mission_id)
            if pull_request is None:
                return PublicationResult(
                    PublicationState.API_UNAVAILABLE,
                    None,
                    False,
                    0,
                    "exact pull request not found",
                )
            state = self.backend.check_state(pull_request)
            if state is CheckState.SUCCESS:
                return PublicationResult(
                    PublicationState.AWAITING_REVIEW,
                    pull_request,
                    True,
                    1,
                    "required checks passed; human review required",
                )
            outcomes = {
                CheckState.FAILURE: (
                    PublicationState.CHECKS_FAILED,
                    "required checks failed",
                ),
                CheckState.PENDING: (
                    PublicationState.CHECK_TIMEOUT,
                    "required checks remain pending",
                ),
                CheckState.UNAVAILABLE: (
                    PublicationState.API_UNAVAILABLE,
                    "check state unavailable",
                ),
            }
            outcome, detail = outcomes[state]
            return PublicationResult(outcome, pull_request, True, 1, detail)
        except GitHubError as error:
            return PublicationResult(error.state, None, False, 0, str(error))
