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
class PullRequest:
    pr_id: str
    url: str
    head: str
    base: str
    mission_id: str


@dataclass(frozen=True)
class PublicationResult:
    state: PublicationState
    pull_request: PullRequest | None
    reused: bool
    polls: int
    detail: str


class GitHubBackend(Protocol):
    def push(self, branch: str) -> None: ...
    def find_pull_request(self, head: str, base: str, mission_id: str) -> PullRequest | None: ...
    def create_pull_request(
        self, head: str, base: str, mission_id: str, title: str, body: str
    ) -> PullRequest: ...
    def check_state(self, pull_request: PullRequest) -> CheckState: ...


class GitHubPublisher:
    """Credentialed publication boundary. It intentionally exposes no merge operation."""

    def __init__(self, backend: GitHubBackend):
        self.backend = backend

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
            existing = self.backend.find_pull_request(head, base, mission_id)
            self.backend.push(head)
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
