from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping, NoReturn, Protocol

from ..host_artifact_store import HostArtifactCollectionStore
from ..merge_time import parse_aware_timestamp
from .github_candidate_rest import GitHubCandidateRESTSnapshot
from .github_check_policy import GitHubRequiredCheckProjector
from .github_checks import GitHubCheckEvidenceReader
from .github_evidence_composer import (
    ComposedEvidenceSnapshot,
    GitHubCompleteEvidenceComposer,
)
from .github_evidence_credentials import (
    GitHubEvidenceCredentialReceipt,
)
from .github_get import QualifiedFeatureResponse
from .github_graphql import GitHubGraphQLClient
from .github_identity import GitHubIdentityVerifier
from .github_merge_observer import (
    EndpointResponse,
    GitHubMergeObservationBackend,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)
from .github_publication_reconciliation import (
    ControllerPusherProof,
    GitHubPublicationReconciler,
)
from .github_reviews import GitHubReviewReader


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise _fail("collection-window", "trusted collector clock has no UTC offset")
    return value.astimezone(timezone.utc).isoformat()


def _time(value: object, surface: str) -> datetime:
    try:
        return parse_aware_timestamp(value)
    except (TypeError, ValueError):
        raise _fail(surface, "authenticated document time is malformed") from None


def _mapping(value: object, surface: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(surface, "authenticated document is not an object")
    return value


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "authenticated identity is malformed")
    return value


class BranchOwnershipProvider(Protocol):
    """Read-only proof boundary sharing the collector's observer credential."""

    @property
    def credential(self) -> object: ...

    def prove(
        self,
        *,
        controller_pusher: ControllerPusherProof,
        publication_credential_receipt: Mapping[str, object],
        evidence_completed_at: str,
    ) -> Mapping[str, object]: ...


class CandidateRESTProvider(Protocol):
    """Exact candidate/diff/deployment reader using the observer credential."""

    @property
    def credential(self) -> object: ...

    def read_all(
        self,
        *,
        controller_pusher: ControllerPusherProof,
        object_evidence: Mapping[str, object],
    ) -> GitHubCandidateRESTSnapshot: ...


class NormalizedPolicyBackend(Protocol):
    """Remaining closed projection for protection, rulesets, and memberships."""

    @property
    def credential(self) -> object: ...

    def read_all(self) -> GitHubNormalizedPolicySnapshot: ...


@dataclass(frozen=True)
class GitHubNormalizedPolicySnapshot:
    """One physical policy read projected for evidence and required checks."""

    classic_protection: EndpointResponse
    active_rules: PageResponse
    source_rulesets: PageResponse
    bypass_actors: PageResponse
    bypass_memberships: PageResponse
    classic_check_policy: QualifiedFeatureResponse
    active_check_policy: PageResponse


@dataclass(frozen=True)
class AuthenticatedEvidenceCollection:
    snapshot: ComposedEvidenceSnapshot
    envelope: Mapping[str, object]


@dataclass(frozen=True)
class _PreparedObservationBackend:
    """Eager base reads prevent network work after the evidence window closes."""

    pull_request: EndpointResponse
    refs: EndpointResponse
    changed_files: PageResponse
    classic_protection: EndpointResponse
    active_rules: PageResponse
    source_rulesets: PageResponse
    bypass_actors: PageResponse
    bypass_memberships: PageResponse
    deployments: PageResponse
    merged_state: EndpointResponse

    @staticmethod
    def _replaced() -> NoReturn:
        raise _fail(
            "evidence-composition",
            "composer requested a surface that must come from a fixed reader",
        )

    def read_repository(self) -> EndpointResponse:
        return self._replaced()

    def read_credential_actor(self) -> EndpointResponse:
        return self._replaced()

    def read_pull_request(self) -> EndpointResponse:
        return self.pull_request

    def read_graphql_pull_request(self) -> EndpointResponse:
        return self._replaced()

    def read_refs(self) -> EndpointResponse:
        return self.refs

    def read_changed_files(self) -> PageResponse:
        return self.changed_files

    def read_classic_protection(self) -> EndpointResponse:
        return self.classic_protection

    def read_active_rules(self) -> PageResponse:
        return self.active_rules

    def read_source_rulesets(self) -> tuple[PageResponse, PageResponse]:
        return self.source_rulesets, self.bypass_actors

    def read_bypass_memberships(self) -> PageResponse:
        return self.bypass_memberships

    def read_reviews(self) -> PageResponse:
        return self._replaced()

    def read_review_requests(self) -> PageResponse:
        return self._replaced()

    def read_review_threads(self) -> PageResponse:
        return self._replaced()

    def read_check_runs(self) -> PageResponse:
        return self._replaced()

    def read_commit_statuses(self) -> PageResponse:
        return self._replaced()

    def read_deployments(self) -> PageResponse:
        return self.deployments

    def read_merged_state(self) -> EndpointResponse:
        return self.merged_state


class GitHubAuthenticatedEvidenceCollector:
    """Collect, compose, and attest one snapshot through injected read-only seams."""

    def __init__(
        self,
        *,
        identity: GitHubIdentityVerifier,
        graphql: GitHubGraphQLClient,
        reviews: GitHubReviewReader,
        checks: GitHubCheckEvidenceReader,
        candidate: CandidateRESTProvider,
        ownership: BranchOwnershipProvider,
        store: HostArtifactCollectionStore,
        clock: Callable[[], datetime],
    ):
        installation_credential = identity.observer_installation.credential
        readers = (
            graphql.credential,
            reviews.client.credential,
            checks.client.credential,
            candidate.credential,
            ownership.credential,
        )
        if any(credential is not installation_credential for credential in readers):
            raise ValueError(
                "GitHub collector readers must share one observer installation credential"
            )
        self.identity = identity
        self.graphql = graphql
        self.reviews = reviews
        self.checks = checks
        self.candidate = candidate
        self.ownership = ownership
        self.store = store
        self.clock = clock

    @staticmethod
    def _prepare(
        backend: NormalizedPolicyBackend,
        candidate: GitHubCandidateRESTSnapshot,
    ) -> tuple[_PreparedObservationBackend, GitHubNormalizedPolicySnapshot]:
        policy = backend.read_all()
        if not isinstance(policy, GitHubNormalizedPolicySnapshot):
            raise _fail("policy-backend", "normalized policy snapshot is malformed")
        prepared = _PreparedObservationBackend(
            candidate.pull_request,
            candidate.refs,
            candidate.changed_files,
            policy.classic_protection,
            policy.active_rules,
            policy.source_rulesets,
            policy.bypass_actors,
            policy.bypass_memberships,
            candidate.deployments,
            candidate.merged_state,
        )
        return prepared, policy

    @staticmethod
    def _exact_candidate(
        publication_receipt: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        repository = _mapping(
            publication_receipt.get("repository"), "publication.repository"
        )
        pull = _mapping(
            publication_receipt.get("pull_request"), "publication.pull-request"
        )
        try:
            exact_repository = {
                key: repository[key]
                for key in ("id", "node_id", "owner", "name")
            }
            candidate = {
                "id": pull["id"],
                "number": pull["number"],
                "head_repository_id": repository["id"],
                "head_ref": pull["head_ref"],
                "head_sha": pull["head_sha"],
                "base_repository_id": repository["id"],
                "base_ref": pull["base_ref"],
                "base_sha": pull["base_sha"],
            }
        except KeyError:
            raise _fail(
                "publication", "publication receipt omits exact candidate identity"
            ) from None
        return exact_repository, candidate

    @staticmethod
    def _bindings(
        *,
        publication_receipt: Mapping[str, object],
        policy: Mapping[str, object],
        authorization: Mapping[str, object],
    ) -> dict[str, object]:
        mission = _mapping(publication_receipt.get("mission"), "publication.mission")
        path_policy = _mapping(policy.get("path_policy"), "policy.path-policy")
        try:
            return {
                "policy_id": policy["policy_id"],
                "policy_sha256": policy["policy_sha256"],
                "merge_authorization_id": authorization["merge_authorization_id"],
                "authorization_sha256": authorization["authorization_sha256"],
                "mission_id": mission["mission_id"],
                "binding_id": mission["binding_id"],
                "mission_authorization_id": mission["mission_authorization_id"],
                "protected_policy_sha256": path_policy[
                    "protected_policy_sha256"
                ],
            }
        except KeyError:
            raise _fail(
                "authority", "authenticated authority binding is incomplete"
            ) from None

    def collect_and_persist(
        self,
        *,
        policy_backend: NormalizedPolicyBackend,
        observer_credential_receipt: Mapping[str, object],
        publication_request: Mapping[str, object],
        publication_dispatch: Mapping[str, object],
        publication_receipt: Mapping[str, object],
        publication_credential_receipt: Mapping[str, object],
        policy: Mapping[str, object],
        authorization: Mapping[str, object],
        protected_policy: Mapping[str, object],
        policy_read: Mapping[str, object],
        object_evidence: Mapping[str, object],
        evidence_id: str,
    ) -> AuthenticatedEvidenceCollection:
        if (
            policy_backend.credential
            is not self.identity.observer_installation.credential
        ):
            raise _fail(
                "policy-backend",
                "normalized policy reader does not share the observer credential",
            )
        documents = copy.deepcopy({
            "observer_credential_receipt": observer_credential_receipt,
            "publication_request": publication_request,
            "publication_dispatch": publication_dispatch,
            "publication_receipt": publication_receipt,
            "publication_credential_receipt": publication_credential_receipt,
            "policy": policy,
            "authorization": authorization,
            "protected_policy": protected_policy,
            "policy_read": policy_read,
            "object_evidence": object_evidence,
        })
        try:
            observer_receipt = GitHubEvidenceCredentialReceipt.from_document(
                documents["observer_credential_receipt"]
            )
        except (KeyError, TypeError, ValueError):
            raise _fail(
                "observer-credential", "observer credential receipt is invalid"
            ) from None

        observed_time = self.clock()
        observed_at = _timestamp(observed_time)
        if observed_time != _time(observer_receipt.verified_at, "observer-credential"):
            raise _fail(
                "collection-window",
                "observer credential was not verified at the trusted collection start",
            )

        receipt = _mapping(documents["publication_receipt"], "publication")
        repository, candidate = self._exact_candidate(receipt)
        owner = repository["owner"]
        name = repository["name"]
        node_id = repository["node_id"]
        number = _positive_int(candidate["number"], "publication.pull-request")
        repository_id = _positive_int(
            repository["id"], "publication.repository"
        )
        head_sha = candidate["head_sha"]
        if (
            not isinstance(owner, str)
            or not isinstance(name, str)
            or not isinstance(node_id, str)
            or not node_id
            or not isinstance(head_sha, str)
        ):
            raise _fail("publication.repository", "repository identity is malformed")

        observer_identity = self.identity.verify_observer(
            observer_receipt,
            owner=owner,
            name=name,
            repository_node_id=node_id,
            observed_at=observed_time,
        )
        graphql = self.graphql.read_pull_request(
            owner=owner,
            name=name,
            number=number,
        )
        pusher = GitHubPublicationReconciler.reconcile(
            publication_request=documents["publication_request"],
            publication_receipt=receipt,
            graphql=graphql,
        )
        candidate = self.candidate.read_all(
            controller_pusher=pusher,
            object_evidence=documents["object_evidence"],
        )
        prepared, policy_snapshot = self._prepare(policy_backend, candidate)
        rest_reviews = self.reviews.read_all(
            repository={"owner": owner, "name": name},
            pull_number=number,
        )
        policy_document = _mapping(documents["policy"], "policy")
        review_requirements = _mapping(
            policy_document.get("review_requirements"),
            "policy.review-requirements",
        )
        host_checks = review_requirements.get("required_checks")
        if not isinstance(host_checks, list):
            raise _fail(
                "policy.review-requirements", "required check policy is malformed"
            )
        required_checks = GitHubRequiredCheckProjector.project(
            host_policy_checks=host_checks,
            classic_protection=policy_snapshot.classic_check_policy,
            active_rules=policy_snapshot.active_check_policy,
        )
        check_runs, commit_statuses = self.checks.read_all(
            owner=owner,
            name=name,
            repository_id=repository_id,
            sha=head_sha,
            required_checks=required_checks,
            pull_request=candidate,
        )

        completed_time = self.clock()
        completed_at = _timestamp(completed_time)
        authority = _mapping(documents["authorization"], "authorization")
        expiry_values = (
            observer_receipt.expires_at,
            policy_document.get("expires_at"),
            authority.get("expires_at"),
        )
        expiries = tuple(_time(value, "collection-window") for value in expiry_values)
        expires_at = expiry_values[expiries.index(min(expiries))]
        if not observed_time <= completed_time < min(expiries):
            raise _fail(
                "collection-window", "evidence collection exceeded its trusted window"
            )
        policy_read_time = _time(
            _mapping(documents["policy_read"], "policy-read").get("observed_at"),
            "policy-read",
        )
        if not observed_time <= policy_read_time <= completed_time:
            raise _fail(
                "policy-read", "host policy read falls outside the collection window"
            )

        ownership = self.ownership.prove(
            controller_pusher=pusher,
            publication_credential_receipt=documents[
                "publication_credential_receipt"
            ],
            evidence_completed_at=completed_at,
        )
        snapshot = GitHubCompleteEvidenceComposer.compose(
            base_backend=prepared,
            observer_identity=observer_identity,
            publication_request=documents["publication_request"],
            publication_receipt=receipt,
            branch_ownership=ownership,
            graphql=graphql,
            rest_reviews=rest_reviews,
            host_policy_checks=host_checks,
            classic_check_policy=policy_snapshot.classic_check_policy,
            active_check_policy=policy_snapshot.active_check_policy,
            check_runs=check_runs,
            commit_statuses=commit_statuses,
            evidence_id=evidence_id,
            bindings=self._bindings(
                publication_receipt=receipt,
                policy=policy_document,
                authorization=authority,
            ),
            observed_at=observed_at,
            completed_at=completed_at,
            expires_at=str(expires_at),
            policy_read=documents["policy_read"],
            object_evidence=documents["object_evidence"],
        )
        envelope = self.store.persist(
            publication_request=documents["publication_request"],
            publication_dispatch=documents["publication_dispatch"],
            publication_receipt=receipt,
            publication_credential_receipt=documents[
                "publication_credential_receipt"
            ],
            observer_credential_receipt=documents[
                "observer_credential_receipt"
            ],
            policy=policy_document,
            authorization=authority,
            protected_policy=documents["protected_policy"],
            branch_ownership=ownership,
            evidence=snapshot.evidence,
            provenance=snapshot.provenance,
        )
        return AuthenticatedEvidenceCollection(snapshot, envelope)
