from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from ..storage import canonical_sha256, read_json
from .github_branch_ownership import GitHubControllerBranchOwnershipProver
from .github_check_policy import GitHubRequiredCheckProjector
from .github_evidence_credentials import GitHubEvidenceCredentialReceipt
from .github_get import QualifiedFeatureResponse
from .github_graphql import GraphQLPullRequestSnapshot
from .github_graphql_projection import (
    GitHubGraphQLProjector,
    GraphQLPullRequestProjection,
)
from .github_identity import VerifiedMergeActorIdentity, VerifiedObserverIdentity
from .github_merge_observer import (
    EndpointResponse,
    GitHubMergeObservationBackend,
    GitHubMergeObserver,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)
from .github_publication_reconciliation import (
    ControllerPusherProof,
    GitHubPublicationReconciler,
)
from .github_review_reconciliation import GitHubReviewReconciler


PROVENANCE_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "publication"
    / "merge-evidence-provenance.schema.json"
)
MERGE_RECEIPT_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "publication"
    / "merge-credential-receipt.schema.json"
)


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _time(value: object, surface: str) -> datetime:
    if not isinstance(value, str):
        raise _fail(surface, "evidence composition time is malformed")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(surface, "evidence composition time is malformed") from None
    if result.utcoffset() is None:
        raise _fail(surface, "evidence composition time has no UTC offset")
    return result


def _request_ids(audits: Sequence[RequestAudit], surface: str) -> tuple[str, ...]:
    if any(not isinstance(audit, RequestAudit) for audit in audits):
        raise _fail(surface, "request audit is malformed")
    result = tuple(audit.request_id for audit in audits)
    if (
        not result
        or any(not isinstance(value, str) or not value for value in result)
        or len(result) != len(set(result))
    ):
        raise _fail(surface, "request audit identity is missing or duplicated")
    return result


def _copy_page(page: PageResponse, items: Sequence[Mapping[str, object]]) -> PageResponse:
    return PageResponse(
        tuple(items), page.pages, len(items), page.complete, page.truncated,
        page.last_cursor, page.audits,
    )


@dataclass(frozen=True)
class ComposedEvidenceSnapshot:
    evidence: Mapping[str, object]
    provenance: Mapping[str, object]


class _ComposedObservationBackend:
    """Replace synthetic observer surfaces with independently proven inputs."""

    def __init__(
        self,
        *,
        base: GitHubMergeObservationBackend,
        observer_identity: VerifiedObserverIdentity,
        merge_actor_identity: VerifiedMergeActorIdentity,
        controller_pusher: ControllerPusherProof,
        graphql: GraphQLPullRequestSnapshot,
        projection: GraphQLPullRequestProjection,
        rest_reviews: PageResponse,
        check_runs: PageResponse,
        commit_statuses: PageResponse,
        classic_check_policy: QualifiedFeatureResponse,
        active_check_policy: PageResponse,
    ):
        self.base = base
        self.observer_identity = observer_identity
        self.merge_actor_identity = merge_actor_identity
        self.controller_pusher = controller_pusher
        self.graphql = graphql
        self.projection = projection
        self.rest_reviews = rest_reviews
        self.check_runs = check_runs
        self.commit_statuses = commit_statuses
        self.classic_check_policy = classic_check_policy
        self.active_check_policy = active_check_policy

    def read_repository(self) -> EndpointResponse:
        audits = self.observer_identity.requests
        return EndpointResponse(
            self.observer_identity.repository, audits[3], audits[:3]
        )

    def read_credential_actor(self) -> EndpointResponse:
        audits = self.merge_actor_identity.requests
        return EndpointResponse(
            self.merge_actor_identity.actor,
            audits[0],
            audits[1:],
        )

    def read_pull_request(self) -> EndpointResponse:
        response = self.base.read_pull_request()
        raw = response.data
        graph = self.projection.pull_request
        proof = self.controller_pusher
        try:
            exact = (
                raw["id"] == proof.pull_request_id
                and raw["node_id"] == proof.pull_request_node_id
                and raw["number"] == proof.pull_request_number
                and raw["head"]["repo"]["id"] == proof.repository_id
                and raw["head"]["repo"]["node_id"] == proof.repository_node_id
                and raw["head"]["ref"] == proof.head_ref
                and raw["head"]["sha"] == proof.head_sha
                and raw["base"]["repo"]["id"] == proof.repository_id
                and raw["base"]["repo"]["node_id"] == proof.repository_node_id
                and raw["base"]["ref"] == proof.base_ref
                and raw["base"]["sha"] == proof.base_sha
            )
        except (KeyError, TypeError):
            exact = False
        if not exact or graph["state"] != "open":
            raise _fail(
                "pull-request",
                "REST, GraphQL, and authenticated publication identities differ",
            )
        data = dict(raw)
        data.update({
            "state": graph["state"],
            "draft": graph["draft"],
            "last_pusher": {"id": proof.last_pusher_id},
            "mergeable": self.projection.mergeability["mergeable"],
            "merge_state_status": self.projection.mergeability[
                "merge_state_status"
            ],
            "review_decision": self.projection.mergeability["review_decision"],
            "merge_queue_entry": self.projection.mergeability["queue_entry"],
        })
        return EndpointResponse(data, response.audit, response.extra_audits)

    def read_graphql_pull_request(self) -> EndpointResponse:
        audits = self.graphql.requests
        return EndpointResponse(
            {"query_sha256": self.projection.query_sha256},
            audits[0],
            audits[1:],
        )

    def read_refs(self) -> EndpointResponse:
        return self.base.read_refs()

    def read_changed_files(self) -> PageResponse:
        return self.base.read_changed_files()

    def read_classic_protection(self) -> EndpointResponse:
        response = self.base.read_classic_protection()
        if response.audit != self.classic_check_policy.audit:
            raise _fail(
                "classic-protection",
                "classic policy normalization used a different request",
            )
        return response

    def read_active_rules(self) -> PageResponse:
        response = self.base.read_active_rules()
        if tuple(response.audits) != tuple(self.active_check_policy.audits):
            raise _fail(
                "active-rules",
                "active-rule normalization used different requests",
            )
        return response

    def read_source_rulesets(self) -> tuple[PageResponse, PageResponse]:
        return self.base.read_source_rulesets()

    def read_bypass_memberships(self) -> PageResponse:
        return self.base.read_bypass_memberships()

    def read_reviews(self) -> PageResponse:
        items = []
        for value in self.rest_reviews.items:
            user = value["user"]
            items.append({
                key: value[key]
                for key in (
                    "id", "repository_permission", "state", "commit_id",
                    "submitted_at", "author_association", "dismissed",
                )
            } | {
                "user": {
                    key: user[key] for key in ("id", "login", "type")
                }
            })
        return _copy_page(self.rest_reviews, items)

    def read_review_requests(self) -> PageResponse:
        items = tuple({
            "reviewer": {
                "id": value["actor_id"], "type": value["actor_type"]
            },
            "as_code_owner": value["as_code_owner"],
        } for value in self.projection.review_requests)
        page = self.projection.pagination["review_requests"]
        return PageResponse(
            items, page["pages"], page["items"], page["complete"],
            page["truncated"], page["last_cursor"], (),
        )

    def read_review_threads(self) -> PageResponse:
        items = tuple({
            "id": value["node_id"],
            "is_resolved": value["resolved"],
            "is_outdated": value["outdated"],
        } for value in self.projection.review_threads)
        page = self.projection.pagination["review_threads"]
        return PageResponse(
            items, page["pages"], page["items"], page["complete"],
            page["truncated"], page["last_cursor"], (),
        )

    def read_check_runs(self) -> PageResponse:
        return self.check_runs

    def read_commit_statuses(self) -> PageResponse:
        return self.commit_statuses

    def read_deployments(self) -> PageResponse:
        return self.base.read_deployments()

    def read_merged_state(self) -> EndpointResponse:
        return self.base.read_merged_state()


class GitHubCompleteEvidenceComposer:
    """Compose already-read exact sources; this class owns no client or credential."""

    _provenance_validator = Draft202012Validator(
        read_json(PROVENANCE_SCHEMA), format_checker=FormatChecker()
    )
    _merge_receipt_validator = Draft202012Validator(
        read_json(MERGE_RECEIPT_SCHEMA), format_checker=FormatChecker()
    )

    @classmethod
    def compose(
        cls,
        *,
        base_backend: GitHubMergeObservationBackend,
        observer_identity: VerifiedObserverIdentity,
        merge_actor_identity: VerifiedMergeActorIdentity,
        publication_request: Mapping[str, object],
        publication_receipt: Mapping[str, object],
        branch_ownership: Mapping[str, object],
        graphql: GraphQLPullRequestSnapshot,
        rest_reviews: PageResponse,
        host_policy_checks: Sequence[Mapping[str, object]],
        classic_check_policy: QualifiedFeatureResponse,
        active_check_policy: PageResponse,
        check_runs: PageResponse,
        commit_statuses: PageResponse,
        evidence_id: str,
        bindings: Mapping[str, object],
        observed_at: str,
        completed_at: str,
        expires_at: str,
        policy_read: Mapping[str, object],
        object_evidence: Mapping[str, object],
    ) -> ComposedEvidenceSnapshot:
        if not isinstance(observer_identity, VerifiedObserverIdentity):
            raise _fail("observer-identity", "verified observer identity is missing")
        if not isinstance(merge_actor_identity, VerifiedMergeActorIdentity):
            raise _fail("merge-actor", "verified merge actor identity is missing")
        if (
            not isinstance(rest_reviews, PageResponse)
            or not isinstance(classic_check_policy, QualifiedFeatureResponse)
            or not isinstance(active_check_policy, PageResponse)
            or not isinstance(check_runs, PageResponse)
            or not isinstance(commit_statuses, PageResponse)
        ):
            raise _fail(
                "evidence-composition", "one or more composed inputs are malformed"
            )
        try:
            observer_receipt = GitHubEvidenceCredentialReceipt.from_document(
                observer_identity.credential_receipt
            )
        except (TypeError, ValueError, KeyError):
            raise _fail(
                "observer-identity", "observer credential receipt is invalid"
            ) from None
        merge_receipt = merge_actor_identity.credential_receipt
        try:
            cls._merge_receipt_validator.validate(merge_receipt)
        except (SchemaError, ValidationError):
            raise _fail("merge-actor", "merge credential receipt is invalid") from None
        if merge_receipt["receipt_sha256"] != canonical_sha256(
            merge_receipt, "receipt_sha256"
        ):
            raise _fail("merge-actor", "merge credential receipt hash differs")
        observed = _time(observed_at, "observation")
        completed = _time(completed_at, "observation")
        expires = _time(expires_at, "observation")
        if not observed <= completed < expires:
            raise _fail("observation", "evidence collection window is invalid")
        if _time(observer_receipt.verified_at, "observer-identity") != observed:
            raise _fail(
                "observer-identity",
                "observer credential receipt is not fresh at collection start",
            )
        if completed >= _time(observer_receipt.expires_at, "observer-identity"):
            raise _fail(
                "observer-identity",
                "observer credential expires before collection completes",
            )
        merge_issued = _time(merge_receipt["issued_at"], "merge-actor")
        merge_expiry = _time(merge_receipt["expires_at"], "merge-actor")
        if (
            not merge_issued <= observed
            or _time(merge_receipt["verified_at"], "merge-actor") != observed
            or completed >= merge_expiry
            or merge_expiry > merge_issued + timedelta(hours=1)
            or expires > merge_expiry
            or expires > _time(observer_receipt.expires_at, "observer-identity")
        ):
            raise _fail(
                "merge-actor",
                "merge credential receipt is not fresh for the collection window",
            )
        identity_requests = observer_identity.requests
        if len(identity_requests) != 4:
            raise _fail(
                "observer-identity", "observer identity audit coverage is incomplete"
            )
        _request_ids(identity_requests, "observer-identity")
        merge_requests = merge_actor_identity.requests
        if len(merge_requests) != 3:
            raise _fail("merge-actor", "merge actor audit coverage is incomplete")
        _request_ids(merge_requests, "merge-actor")

        pusher = GitHubPublicationReconciler.reconcile(
            publication_request=publication_request,
            publication_receipt=publication_receipt,
            graphql=graphql,
        )
        projection = GitHubGraphQLProjector.project(
            graphql=graphql, controller_pusher=pusher
        )
        GitHubControllerBranchOwnershipProver.validate_document(branch_ownership)
        ownership_repository = branch_ownership["repository"]
        ownership_publisher = branch_ownership["publisher"]
        ownership_observation = branch_ownership["observation"]
        if (
            branch_ownership["publication_receipt_id"]
            != pusher.publication_receipt_id
            or branch_ownership["publication_receipt_sha256"]
            != pusher.publication_receipt_sha256
            or ownership_repository != {
                "id": pusher.repository_id,
                "node_id": pusher.repository_node_id,
                "owner": pusher.repository_owner,
                "name": pusher.repository_name,
            }
            or branch_ownership["head_ref"] != pusher.head_ref
            or branch_ownership["head_sha"] != pusher.head_sha
            or ownership_publisher["actor_id"] != pusher.last_pusher_id
            or ownership_publisher["actor_node_id"] != pusher.actor_node_id
            or ownership_publisher["login"] != pusher.actor_login
            or ownership_observation["evidence_completed_at"] != completed_at
        ):
            raise _fail(
                "branch-ownership",
                "branch ownership and composed publication identities differ",
            )
        reconciled_reviews = GitHubReviewReconciler.reconcile(
            rest_reviews=rest_reviews, graphql=graphql
        )
        required_checks = GitHubRequiredCheckProjector.project(
            host_policy_checks=host_policy_checks,
            classic_protection=classic_check_policy,
            active_rules=active_check_policy,
        )
        required_run_keys = {
            (value.get("name"), value.get("app", {}).get("id"))
            for value in check_runs.items
            if value.get("required") is True and isinstance(value.get("app"), Mapping)
        }
        expected_run_keys = {
            (value["context"], value["app_id"]) for value in required_checks
        }
        if required_run_keys != expected_run_keys:
            raise _fail(
                "required-checks",
                "policy-required checks and exact check evidence differ",
            )
        repository = observer_identity.repository
        owner = repository.get("owner") if isinstance(repository, Mapping) else None
        if (
            not isinstance(owner, Mapping)
            or observer_receipt.repository_ids != (pusher.repository_id,)
            or repository.get("id") != pusher.repository_id
            or repository.get("node_id") != pusher.repository_node_id
            or owner.get("login") != pusher.repository_owner
            or repository.get("name") != pusher.repository_name
        ):
            raise _fail(
                "observer-identity",
                "observer, publication, and repository identities differ",
            )
        try:
            expected_merge_actor = {
                "app": {
                    "id": merge_receipt["app_id"],
                    "node_id": merge_receipt["app_node_id"],
                },
                "installation": {
                    "id": merge_receipt["installation_id"],
                    "account_id": merge_receipt["installation_account_id"],
                },
                "user": {
                    "id": merge_receipt["actor_id"],
                    "node_id": merge_receipt["actor_node_id"],
                    "login": merge_receipt["login"],
                    "suspended": merge_receipt["suspended"],
                },
                "permissions": {"administration": "none"},
            }
            separate_credentials = all(
                observer_identity.credential_receipt[field]
                != merge_receipt[field]
                for field in ("app_id", "installation_id", "actor_id")
            )
        except (KeyError, TypeError):
            raise _fail("merge-actor", "verified merge actor is malformed") from None
        if (
            merge_actor_identity.actor != expected_merge_actor
            or merge_receipt["repository_ids"] != [pusher.repository_id]
            or not separate_credentials
        ):
            raise _fail(
                "merge-actor",
                "merge actor, repository, or credential boundary differs",
            )

        backend = _ComposedObservationBackend(
            base=base_backend,
            observer_identity=observer_identity,
            merge_actor_identity=merge_actor_identity,
            controller_pusher=pusher,
            graphql=graphql,
            projection=projection,
            rest_reviews=rest_reviews,
            check_runs=check_runs,
            commit_statuses=commit_statuses,
            classic_check_policy=classic_check_policy,
            active_check_policy=active_check_policy,
        )
        result = GitHubMergeObserver(backend).observe(
            evidence_id=evidence_id,
            bindings=bindings,
            observed_at=observed_at,
            completed_at=completed_at,
            expires_at=expires_at,
            graphql_query_sha256=projection.query_sha256,
            policy_read=policy_read,
            object_evidence=object_evidence,
        )
        if result.outcome is not ObservationOutcome.OBSERVED or result.evidence is None:
            raise GitHubObservationError(
                result.outcome,
                result.surface or "evidence-composition",
                result.detail,
            )
        evidence = result.evidence
        expected_diff = publication_receipt["diff"]
        observed_diff = {
            "diff_sha256": evidence["diff"]["diff_sha256"],
            "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
            "object_evidence_sha256": evidence["diff"]["object_evidence"][
                "files_sha256"
            ],
        }
        expected_mission = {
            key: publication_receipt["mission"][key]
            for key in ("mission_id", "binding_id", "mission_authorization_id")
        }
        if (
            observed_diff != expected_diff
            or any(
                evidence["bindings"].get(key) != value
                for key, value in expected_mission.items()
            )
        ):
            raise _fail(
                "evidence-composition",
                "composed diff or mission binding differs from publication",
            )
        requests = evidence["observation"]["requests"]
        request_ids = [value["request_id"] for value in requests]
        ownership_request_ids = ownership_observation["request_ids"]
        if (
            len(request_ids) != len(set(request_ids))
            or set(request_ids) & set(ownership_request_ids)
        ):
            raise _fail("evidence-composition", "composed requests are duplicated")
        request_times = [
            _time(value["observed_at"], "evidence-composition")
            for value in requests
        ]
        if any(value < observed or value > completed for value in request_times):
            raise _fail(
                "evidence-composition",
                "a composed request falls outside the collection window",
            )
        suffix = evidence_id.removeprefix("merge_evidence_")
        provenance = {
            "schema_version": 2,
            "provenance_id": f"merge_evidence_provenance_{suffix}",
            "evidence_id": evidence_id,
            "evidence_sha256": evidence["evidence_sha256"],
            "observer_credential_receipt_id": (
                observer_receipt.credential_receipt_id
            ),
            "observer_credential_receipt_sha256": observer_identity.credential_receipt[
                "receipt_sha256"
            ],
            "merge_credential_receipt_id": merge_receipt[
                "credential_receipt_id"
            ],
            "merge_credential_receipt_sha256": merge_receipt["receipt_sha256"],
            "publication_receipt_id": pusher.publication_receipt_id,
            "publication_receipt_sha256": pusher.publication_receipt_sha256,
            "branch_ownership_id": branch_ownership["ownership_id"],
            "branch_ownership_sha256": branch_ownership["ownership_sha256"],
            "graphql_query_sha256": projection.query_sha256,
            "reconciled_review_ids": list(reconciled_reviews),
            "required_checks": list(required_checks),
            "request_ids_sha256": evidence["observation"]["request_ids_sha256"],
            "observed_at": observed_at,
            "completed_at": completed_at,
            "provenance_sha256": "0" * 64,
        }
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        cls._provenance_validator.validate(provenance)
        return ComposedEvidenceSnapshot(evidence, provenance)
