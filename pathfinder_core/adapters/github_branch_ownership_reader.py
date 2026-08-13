from __future__ import annotations

import hashlib
import re
from typing import Mapping

from .github_branch_ownership import GitHubControllerBranchOwnershipProver
from .github_get import GitHubGETClient
from .github_merge_observer import GitHubObservationError, ObservationOutcome
from .github_publication_reconciliation import ControllerPusherProof


_REPOSITORY_PART = re.compile(r"[A-Za-z0-9_.-]+")
_BRANCH = re.compile(r"pathfinder/auto/[A-Za-z0-9._/-]{1,220}")


def _fail(detail: str) -> GitHubObservationError:
    return GitHubObservationError(
        ObservationOutcome.FIELD_UNKNOWN,
        "branch-ownership",
        detail,
    )


class GitHubControllerBranchOwnershipReader:
    """Read and prove controller-branch ownership with one observer credential."""

    def __init__(self, client: GitHubGETClient, *, ruleset_id: int):
        if not isinstance(client, GitHubGETClient):
            raise TypeError("GitHub branch ownership reader requires a fixed GET client")
        if client.credential.kind != "installation-token":
            raise ValueError(
                "GitHub branch ownership reader requires an installation credential"
            )
        if (
            not isinstance(ruleset_id, int)
            or isinstance(ruleset_id, bool)
            or ruleset_id < 1
        ):
            raise ValueError("GitHub branch ownership ruleset id is malformed")
        self.client = client
        self.ruleset_id = ruleset_id

    @property
    def credential(self):
        return self.client.credential

    @staticmethod
    def _repository_path(controller_pusher: ControllerPusherProof) -> str:
        if not isinstance(controller_pusher, ControllerPusherProof):
            raise _fail("controller pusher proof is missing")
        owner = controller_pusher.repository_owner
        name = controller_pusher.repository_name
        head_ref = controller_pusher.head_ref
        if (
            not all(isinstance(value, str) for value in (owner, name, head_ref))
            or _REPOSITORY_PART.fullmatch(owner) is None
            or _REPOSITORY_PART.fullmatch(name) is None
            or _BRANCH.fullmatch(head_ref) is None
        ):
            raise _fail("controller repository or branch identity is malformed")
        return f"/repos/{owner}/{name}"

    @staticmethod
    def _ownership_id(
        controller_pusher: ControllerPusherProof,
        request_ids: tuple[str, ...],
    ) -> str:
        binding = "\n".join((
            controller_pusher.publication_receipt_sha256,
            str(controller_pusher.repository_id),
            controller_pusher.head_ref,
            controller_pusher.head_sha,
            *request_ids,
        ))
        suffix = hashlib.sha256(binding.encode()).hexdigest()[:24]
        return f"controller_branch_ownership_{suffix}"

    def prove(
        self,
        *,
        controller_pusher: ControllerPusherProof,
        publication_credential_receipt: Mapping[str, object],
        evidence_completed_at: str,
    ) -> Mapping[str, object]:
        repository_path = self._repository_path(controller_pusher)
        ruleset = self.client.get_qualified_branch_ownership_endpoint(
            "branch-ownership.ruleset",
            f"{repository_path}/rulesets/{self.ruleset_id}",
        )
        effective_rules = self.client.get_qualified_branch_ownership_pages(
            "branch-ownership.effective-rules",
            f"{repository_path}/rules/branches/{controller_pusher.head_ref}",
        )
        branch_ref = self.client.get_qualified_branch_ownership_endpoint(
            "branch-ownership.ref",
            f"{repository_path}/git/ref/heads/{controller_pusher.head_ref}",
        )
        request_ids = (
            ruleset.audit.request_id,
            *(audit.request_id for audit in effective_rules.audits),
            branch_ref.audit.request_id,
        )
        return GitHubControllerBranchOwnershipProver.prove(
            controller_pusher=controller_pusher,
            publication_credential_receipt=publication_credential_receipt,
            ruleset=ruleset,
            effective_rules=effective_rules,
            branch_ref=branch_ref,
            evidence_completed_at=evidence_completed_at,
            observed_at=ruleset.audit.observed_at,
            completed_at=branch_ref.audit.observed_at,
            ownership_id=self._ownership_id(controller_pusher, request_ids),
        )
