from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from ..merge_diff import derive_special_files, object_evidence_sha256

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "publication"
    / "merge-evidence.schema.json"
)


class ObservationOutcome(str, Enum):
    OBSERVED = "observed"
    AUTH_ERROR = "auth-error"
    PERMISSION_MISSING = "permission-missing"
    NOT_FOUND = "not-found"
    RATE_LIMITED = "rate-limited"
    API_UNAVAILABLE = "api-unavailable"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed-response"
    PAGINATION_INCOMPLETE = "pagination-incomplete"
    BYPASS_VISIBILITY_UNKNOWN = "bypass-visibility-unknown"
    ACTOR_IDENTITY_UNKNOWN = "actor-identity-unknown"
    RULESET_EVIDENCE_INCOMPLETE = "ruleset-evidence-incomplete"
    DIFF_INCOMPLETE = "diff-incomplete"
    FIELD_UNKNOWN = "field-unknown"


class GitHubObservationError(Exception):
    def __init__(self, outcome: ObservationOutcome, surface: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.surface = surface


@dataclass(frozen=True)
class RequestAudit:
    request_id: str
    observed_at: str
    etag: str | None = None


@dataclass(frozen=True)
class EndpointResponse:
    data: Mapping[str, object]
    audit: RequestAudit


@dataclass(frozen=True)
class PageResponse:
    items: tuple[Mapping[str, object], ...]
    pages: int
    total_count: int
    complete: bool
    truncated: bool
    last_cursor: str | None
    audits: tuple[RequestAudit, ...]


@dataclass(frozen=True)
class ObservationResult:
    outcome: ObservationOutcome
    evidence: dict | None
    surface: str | None
    detail: str


class GitHubMergeObservationBackend(Protocol):
    """Read-only seam. A live GET-only implementation belongs to K2.2."""

    def read_repository(self) -> EndpointResponse: ...
    def read_credential_actor(self) -> EndpointResponse: ...
    def read_pull_request(self) -> EndpointResponse: ...
    def read_refs(self) -> EndpointResponse: ...
    def read_changed_files(self) -> PageResponse: ...
    def read_classic_protection(self) -> EndpointResponse: ...
    def read_active_rules(self) -> PageResponse: ...
    def read_source_rulesets(self) -> tuple[PageResponse, PageResponse]: ...
    def read_reviews(self) -> PageResponse: ...
    def read_review_requests(self) -> PageResponse: ...
    def read_review_threads(self) -> PageResponse: ...
    def read_check_runs(self) -> PageResponse: ...
    def read_commit_statuses(self) -> PageResponse: ...
    def read_deployments(self) -> PageResponse: ...
    def read_merged_state(self) -> EndpointResponse: ...


class _Stop(Exception):
    def __init__(self, outcome: ObservationOutcome, surface: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome
        self.surface = surface


def _sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _document_sha256(document: Mapping[str, object], field: str) -> str:
    return _sha256({key: value for key, value in document.items() if key != field})


def _mapping(value: object, surface: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _Stop(
            ObservationOutcome.MALFORMED_RESPONSE, surface, "expected an object"
        )
    return value


def _take(
    value: object,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    surface: str,
    unknowns: list[dict],
) -> Mapping[str, object]:
    raw = _mapping(value, surface)
    missing = required - raw.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise _Stop(
            ObservationOutcome.MALFORMED_RESPONSE,
            surface,
            f"missing required field(s): {names}",
        )
    extras = set(raw) - required - optional
    if extras:
        unknowns.append(
            {"surface": surface, "fields": {key: raw[key] for key in sorted(extras)}}
        )
    return raw


def _page(page: PageResponse) -> dict:
    return {
        "complete": page.complete,
        "pages": page.pages,
        "items": page.total_count,
        "truncated": page.truncated,
        "last_cursor": page.last_cursor,
    }


def _checks(raw: object, surface: str, unknowns: list[dict]) -> list[dict]:
    if not isinstance(raw, list):
        raise _Stop(ObservationOutcome.MALFORMED_RESPONSE, surface, "checks must be a list")
    result = []
    for index, value in enumerate(raw):
        item = _take(
            value, required={"context", "app_id"},
            surface=f"{surface}[{index}]", unknowns=unknowns,
        )
        result.append({"context": item["context"], "app_id": item["app_id"]})
    return sorted(result, key=lambda item: (str(item["context"]), int(item["app_id"])))


class GitHubMergeObserver:
    def __init__(
        self,
        backend: GitHubMergeObservationBackend,
        *,
        schema_path: Path = SCHEMA_PATH,
    ):
        self.backend = backend
        self.validator = Draft202012Validator(
            json.loads(schema_path.read_text()), format_checker=FormatChecker()
        )

    def observe(
        self,
        *,
        evidence_id: str,
        bindings: Mapping[str, object],
        observed_at: str,
        completed_at: str,
        expires_at: str,
        graphql_query_sha256: str,
        policy_read: Mapping[str, object],
        object_evidence: Mapping[str, object],
    ) -> ObservationResult:
        try:
            raw = self._read_all()
            evidence, outcome, surface, detail = self._normalize(
                raw,
                evidence_id=evidence_id,
                bindings=bindings,
                observed_at=observed_at,
                completed_at=completed_at,
                expires_at=expires_at,
                graphql_query_sha256=graphql_query_sha256,
                policy_read=policy_read,
                object_evidence=object_evidence,
            )
            self.validator.validate(evidence)
            return ObservationResult(outcome, evidence, surface, detail)
        except GitHubObservationError as error:
            return ObservationResult(error.outcome, None, error.surface, str(error))
        except _Stop as error:
            return ObservationResult(error.outcome, None, error.surface, str(error))
        except TimeoutError as error:
            return ObservationResult(
                ObservationOutcome.TIMEOUT, None, "transport", str(error) or "read timed out"
            )
        except (SchemaError, ValidationError, TypeError, ValueError, KeyError) as error:
            return ObservationResult(
                ObservationOutcome.MALFORMED_RESPONSE,
                None,
                "normalization",
                str(error),
            )

    def _read_all(self) -> dict[str, object]:
        repository = self.backend.read_repository()
        actor = self.backend.read_credential_actor()
        pull_request = self.backend.read_pull_request()
        refs = self.backend.read_refs()
        changed_files = self.backend.read_changed_files()
        classic = self.backend.read_classic_protection()
        active_rules = self.backend.read_active_rules()
        source_rulesets, bypass_actors = self.backend.read_source_rulesets()
        return {
            "repository": repository,
            "actor": actor,
            "pull-request": pull_request,
            "refs": refs,
            "changed-files": changed_files,
            "classic-protection": classic,
            "active-rules": active_rules,
            "source-rulesets": source_rulesets,
            "bypass-actors": bypass_actors,
            "reviews": self.backend.read_reviews(),
            "review-requests": self.backend.read_review_requests(),
            "review-threads": self.backend.read_review_threads(),
            "check-runs": self.backend.read_check_runs(),
            "commit-statuses": self.backend.read_commit_statuses(),
            "deployments": self.backend.read_deployments(),
            "merged-state": self.backend.read_merged_state(),
        }

    def _normalize(self, raw: dict[str, object], **context: object):
        unknowns: list[dict] = []
        unsupported: list[str] = []
        unknown_reasons: list[str] = []
        audits = self._audits(raw)

        repository = self._repository(raw["repository"], unknowns)
        actor = self._actor(raw["actor"], unknowns)
        pull_request, mergeability = self._pull_request(
            raw["pull-request"], raw["refs"], raw["merged-state"], unknowns
        )
        changed_files = self._changed_files(raw["changed-files"], unknowns)
        object_evidence = self._bind_object_evidence(
            changed_files, context["object_evidence"], unknowns
        )
        patch_bytes = sum(int(item.pop("_patch_bytes")) for item in changed_files)
        diff = {
            "diff_sha256": "0" * 64,
            "changed_files_sha256": _sha256(changed_files),
            "object_evidence": object_evidence,
            "changed_files": changed_files,
            "changed_file_count": len(changed_files),
            "total_line_changes": sum(int(item["changes"]) for item in changed_files),
            "patch_bytes": patch_bytes,
            "protected_categories": sorted({
                category for item in changed_files for category in item["protected_categories"]
            }),
            "special_files": sorted({
                special for item in changed_files for special in item["special_files"]
            }),
        }
        diff["diff_sha256"] = _document_sha256(diff, "diff_sha256")

        active_rules = self._active_rules(raw["active-rules"], unknowns, unsupported)
        source_rulesets = self._source_rulesets(
            raw["source-rulesets"], raw["bypass-actors"], unknowns, unknown_reasons
        )
        classic = self._classic(
            raw["classic-protection"], raw["active-rules"], repository,
            unknowns, unknown_reasons,
        )
        bypass_keys = set(classic["bypass_actor_keys"])
        bypass_keys.update(
            key for ruleset in source_rulesets for key in ruleset["bypass_actor_keys"]
        )
        if any(ruleset["bypass_visibility"] == "unknown" for ruleset in source_rulesets):
            actor["bypass_assessment"] = "unknown"
        else:
            actor_keys = {f"Integration:{actor['app_id']}", f"User:{actor['actor_id']}"}
            actor["bypass_assessment"] = "match" if actor_keys & bypass_keys else "no-match"

        reviews = self._reviews(raw["reviews"], unknowns)
        review_requests = self._review_requests(raw["review-requests"], unknowns)
        review_threads = self._review_threads(raw["review-threads"], unknowns)
        checks = self._check_evidence(raw["check-runs"], raw["commit-statuses"], unknowns)

        paged = {
            key: value for key, value in raw.items() if isinstance(value, PageResponse)
        }
        pagination = {
            "pull_files": _page(paged["changed-files"]),
            "active_rules": _page(paged["active-rules"]),
            "source_rulesets": _page(paged["source-rulesets"]),
            "bypass_actors": _page(paged["bypass-actors"]),
            "reviews": _page(paged["reviews"]),
            "review_requests": _page(paged["review-requests"]),
            "review_threads": _page(paged["review-threads"]),
            "check_runs": _page(paged["check-runs"]),
            "commit_statuses": _page(paged["commit-statuses"]),
            "deployments": _page(paged["deployments"]),
        }
        if any(not page.complete or page.truncated for page in paged.values()):
            unknown_reasons.append("pagination-incomplete")
        if unknowns:
            unknown_reasons.append("field-unknown")

        request_ids = [item["request_id"] for item in audits]
        evidence = {
            "schema_version": 1,
            "evidence_id": context["evidence_id"],
            "observation": {
                "rest_api_version": "2026-03-10",
                "graphql_query_sha256": context["graphql_query_sha256"],
                "policy_read": dict(context["policy_read"]),
                "request_ids_sha256": _sha256(request_ids),
                "requests": audits,
                "unknown_payloads_sha256": _sha256(unknowns) if unknowns else None,
                "observed_at": context["observed_at"],
                "completed_at": context["completed_at"],
                "expires_at": context["expires_at"],
                "collection_complete": not unknown_reasons,
            },
            "repository": repository,
            "actor": actor,
            "pull_request": pull_request,
            "bindings": dict(context["bindings"]),
            "diff": diff,
            "pagination": pagination,
            "classic_protection": classic,
            "active_rules": active_rules,
            "source_rulesets": source_rulesets,
            "reviews": reviews,
            "review_requests": review_requests,
            "review_threads": review_threads,
            "checks": checks,
            "mergeability": mergeability,
            "unsupported_reasons": sorted(set(unsupported)),
            "unknown_reasons": sorted(set(unknown_reasons)),
            "evidence_sha256": "0" * 64,
        }
        evidence["evidence_sha256"] = _document_sha256(evidence, "evidence_sha256")
        if "pagination-incomplete" in unknown_reasons:
            return evidence, ObservationOutcome.PAGINATION_INCOMPLETE, "pagination", "one or more collections are incomplete"
        if "bypass-visibility-unknown" in unknown_reasons:
            return evidence, ObservationOutcome.BYPASS_VISIBILITY_UNKNOWN, "bypass-actors", "bypass visibility is incomplete"
        if unknown_reasons:
            return evidence, ObservationOutcome.FIELD_UNKNOWN, "normalization", "one or more response fields are unknown"
        return evidence, ObservationOutcome.OBSERVED, None, "complete read-only evidence snapshot"

    @staticmethod
    def _audits(raw: Mapping[str, object]) -> list[dict]:
        result = []
        for surface, response in raw.items():
            source = response.audits if isinstance(response, PageResponse) else (response.audit,)
            for audit in source:
                result.append({
                    "surface": surface,
                    "request_id": audit.request_id,
                    "etag": audit.etag,
                    "observed_at": audit.observed_at,
                })
        return result

    @staticmethod
    def _repository(response: EndpointResponse, unknowns: list[dict]) -> dict:
        raw = _take(
            response.data,
            required={"id", "node_id", "owner", "name", "default_branch", "archived", "disabled", "allow_squash_merge", "allow_merge_commit", "allow_rebase_merge"},
            surface="repository", unknowns=unknowns,
        )
        owner = _take(raw["owner"], required={"login"}, surface="repository.owner", unknowns=unknowns)
        return {
            "id": raw["id"], "node_id": raw["node_id"], "owner": owner["login"],
            "name": raw["name"], "base_branch": raw["default_branch"],
            "archived": raw["archived"], "disabled": raw["disabled"],
            "merge_methods": {
                "squash": raw["allow_squash_merge"],
                "merge_commit": raw["allow_merge_commit"],
                "rebase": raw["allow_rebase_merge"],
            },
        }

    @staticmethod
    def _actor(response: EndpointResponse, unknowns: list[dict]) -> dict:
        raw = _take(response.data, required={"app", "installation", "user", "permissions"}, surface="actor", unknowns=unknowns)
        app = _take(raw["app"], required={"id", "node_id"}, surface="actor.app", unknowns=unknowns)
        installation = _take(raw["installation"], required={"id", "account_id"}, surface="actor.installation", unknowns=unknowns)
        user = _take(raw["user"], required={"id", "node_id", "login", "suspended"}, surface="actor.user", unknowns=unknowns)
        permissions = _take(raw["permissions"], required={"administration"}, surface="actor.permissions", unknowns=unknowns)
        if not str(user["login"]).endswith("[bot]"):
            raise _Stop(ObservationOutcome.ACTOR_IDENTITY_UNKNOWN, "actor", "credential actor is not an unambiguous GitHub App bot")
        return {
            "app_id": app["id"], "app_node_id": app["node_id"],
            "installation_id": installation["id"],
            "installation_account_id": installation["account_id"],
            "actor_id": user["id"], "actor_node_id": user["node_id"],
            "login": user["login"], "administration_permission": permissions["administration"],
            "suspended": user["suspended"], "bypass_assessment": "unknown",
        }

    @staticmethod
    def _pull_request(
        response: EndpointResponse,
        refs_response: EndpointResponse,
        merged_response: EndpointResponse,
        unknowns: list[dict],
    ) -> tuple[dict, dict]:
        raw = _take(
            response.data,
            required={"id", "node_id", "number", "state", "draft", "user", "last_pusher", "head", "base", "mergeable", "merge_state_status", "review_decision", "merge_queue_entry"},
            surface="pull-request", unknowns=unknowns,
        )
        user = _take(raw["user"], required={"id"}, surface="pull-request.user", unknowns=unknowns)
        pusher = _take(raw["last_pusher"], required={"id"}, surface="pull-request.last-pusher", unknowns=unknowns)
        sides = {}
        for side in ("head", "base"):
            value = _take(raw[side], required={"repo", "ref", "sha"}, surface=f"pull-request.{side}", unknowns=unknowns)
            repo = _take(value["repo"], required={"id", "node_id"}, surface=f"pull-request.{side}.repo", unknowns=unknowns)
            sides[side] = {"repo": repo, "ref": value["ref"], "sha": value["sha"]}
        refs = _take(refs_response.data, required={"head", "base"}, surface="refs", unknowns=unknowns)
        for side in ("head", "base"):
            ref = _take(refs[side], required={"ref", "sha"}, surface=f"refs.{side}", unknowns=unknowns)
            if ref["ref"] != sides[side]["ref"] or ref["sha"] != sides[side]["sha"]:
                raise _Stop(ObservationOutcome.FIELD_UNKNOWN, "refs", f"{side} ref does not match the pull request")

        merged = _take(
            merged_response.data,
            required={"merged", "merge_commit_sha", "merged_at", "merged_by"},
            surface="merged-state", unknowns=unknowns,
        )
        merged_by = None
        if merged["merged_by"] is not None:
            value = _take(merged["merged_by"], required={"id", "node_id", "login"}, surface="merged-state.merged-by", unknowns=unknowns)
            merged_by = {key: value[key] for key in ("id", "node_id", "login")}
        if bool(merged["merged"]) != (raw["state"] == "merged"):
            if not (merged["merged"] and raw["state"] == "closed"):
                raise _Stop(ObservationOutcome.FIELD_UNKNOWN, "merged-state", "merged state does not reconcile with pull request state")
        if not merged["merged"] and any(merged[key] is not None for key in ("merge_commit_sha", "merged_at", "merged_by")):
            raise _Stop(ObservationOutcome.FIELD_UNKNOWN, "merged-state", "unmerged pull request has merge proof fields")
        state = "merged" if merged["merged"] else raw["state"]
        pull_request = {
            "id": raw["id"], "node_id": raw["node_id"], "number": raw["number"],
            "state": state, "draft": raw["draft"],
            "same_repository": sides["head"]["repo"]["id"] == sides["base"]["repo"]["id"],
            "author_id": user["id"], "last_pusher_id": pusher["id"],
            "head_repository_id": sides["head"]["repo"]["id"],
            "head_repository_node_id": sides["head"]["repo"]["node_id"],
            "head_ref": sides["head"]["ref"], "head_sha": sides["head"]["sha"],
            "base_repository_id": sides["base"]["repo"]["id"],
            "base_repository_node_id": sides["base"]["repo"]["node_id"],
            "base_ref": sides["base"]["ref"], "base_sha": sides["base"]["sha"],
            "merge_commit_sha": merged["merge_commit_sha"],
            "merged_at": merged["merged_at"], "merged_by": merged_by,
        }
        mergeability = {
            "mergeable": raw["mergeable"],
            "merge_state_status": raw["merge_state_status"],
            "review_decision": raw["review_decision"],
            "queue_entry": raw["merge_queue_entry"],
            "required_sha": sides["head"]["sha"],
        }
        return pull_request, mergeability

    @staticmethod
    def _changed_files(page: PageResponse, unknowns: list[dict]) -> list[dict]:
        result = []
        required = {"filename", "previous_filename", "status", "sha", "additions", "deletions", "changes", "patch_bytes"}
        for index, value in enumerate(page.items):
            raw = _take(value, required=required, surface=f"changed-files[{index}]", unknowns=unknowns)
            result.append({
                "path": raw["filename"], "previous_path": raw["previous_filename"],
                "status": raw["status"], "blob_sha": raw["sha"],
                "additions": raw["additions"], "deletions": raw["deletions"],
                "changes": raw["changes"],
                "protected_categories": [],
                "_patch_bytes": raw["patch_bytes"],
            })
        return sorted(result, key=lambda item: str(item["path"]))

    @staticmethod
    def _bind_object_evidence(
        changed_files: list[dict], receipt: object, unknowns: list[dict]
    ) -> dict:
        raw = _take(
            receipt,
            required={"source", "receipt_id", "files"},
            surface="controller-object-evidence",
            unknowns=unknowns,
        )
        if raw["source"] != "authenticated-controller-git-diff":
            raise _Stop(
                ObservationOutcome.DIFF_INCOMPLETE,
                "controller-object-evidence",
                "object evidence is not from the authenticated controller diff",
            )
        if not isinstance(raw["files"], list):
            raise _Stop(
                ObservationOutcome.DIFF_INCOMPLETE,
                "controller-object-evidence.files",
                "object evidence files must be a complete list",
            )
        records = []
        for index, value in enumerate(raw["files"]):
            record = _take(
                value,
                required={"path", "previous_path", "object_kind", "binary"},
                surface=f"controller-object-evidence.files[{index}]",
                unknowns=unknowns,
            )
            records.append(dict(record))
        records.sort(key=lambda item: str(item["path"]))
        paths = [(item["path"], item["previous_path"]) for item in changed_files]
        receipt_paths = [(item["path"], item["previous_path"]) for item in records]
        if paths != receipt_paths:
            raise _Stop(
                ObservationOutcome.DIFF_INCOMPLETE,
                "controller-object-evidence.files",
                "controller object evidence does not match the complete API path set",
            )
        for item, record in zip(changed_files, records, strict=True):
            item["object_kind"] = record["object_kind"]
            item["binary"] = record["binary"]
            item["special_files"] = list(derive_special_files(item))
        return {
            "source": raw["source"],
            "receipt_id": raw["receipt_id"],
            "files_sha256": object_evidence_sha256(changed_files),
        }

    @staticmethod
    def _active_rules(page: PageResponse, unknowns: list[dict], unsupported: list[str]) -> list[dict]:
        supported = {
            "pull_request", "required_status_checks", "required_linear_history",
            "merge_queue", "required_deployments", "required_signatures", "code_scanning",
            "code_quality", "file_path_restriction", "max_file_size",
        }
        unsupported_codes = {
            "merge_queue": "merge-queue-required",
            "required_deployments": "unsupported-required-deployments",
            "required_signatures": "unsupported-required-signatures",
            "code_scanning": "unsupported-code-scanning",
            "code_quality": "unsupported-code-quality",
            "file_path_restriction": "unsupported-file-restriction",
            "max_file_size": "unsupported-metadata-restriction",
        }
        result = []
        required = {"ruleset_id", "source_type", "source_id", "rule_type", "parameters", "approval_count", "required_checks", "strict"}
        for index, value in enumerate(page.items):
            raw = _take(value, required=required, surface=f"active-rules[{index}]", unknowns=unknowns)
            if not raw["source_id"] or not raw["source_type"]:
                raise _Stop(ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE, "active-rules", "active rule has no attributable source")
            rule_type = str(raw["rule_type"])
            if rule_type not in supported:
                unsupported.append("unsupported-active-rule")
                unknowns.append({"surface": f"active-rules[{index}].rule-type", "fields": {"rule_type": rule_type}})
                continue
            if rule_type in unsupported_codes:
                unsupported.append(unsupported_codes[rule_type])
            parameters = raw["parameters"]
            if not isinstance(parameters, Mapping):
                raise _Stop(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    f"active-rules[{index}].parameters",
                    "rule parameters must be an object",
                )
            allowed_merge_methods = []
            code_owner_review_required = None
            if rule_type == "pull_request":
                parsed = _take(
                    parameters,
                    required={
                        "allowed_merge_methods", "dismiss_stale_reviews_on_push",
                        "require_code_owner_review", "require_last_push_approval",
                        "required_approving_review_count",
                        "required_review_thread_resolution",
                    },
                    optional={"dismissal_restriction", "required_reviewers"},
                    surface=f"active-rules[{index}].parameters", unknowns=unknowns,
                )
                allowed_merge_methods = sorted(parsed["allowed_merge_methods"])
                code_owner_review_required = parsed[
                    "require_code_owner_review"
                ]
                if (
                    raw["approval_count"] != parsed["required_approving_review_count"]
                    or code_owner_review_required
                    or parsed.get("dismissal_restriction")
                    or parsed.get("required_reviewers")
                ):
                    unsupported.append("unsupported-active-rule")
            elif rule_type == "required_status_checks":
                parsed = _take(
                    parameters,
                    required={
                        "required_status_checks", "strict_required_status_checks_policy",
                    },
                    optional={"do_not_enforce_on_create"},
                    surface=f"active-rules[{index}].parameters", unknowns=unknowns,
                )
                parameter_checks = sorted((
                    {
                        "context": item["context"],
                        "app_id": item.get("integration_id"),
                    }
                    for item in parsed["required_status_checks"]
                ), key=lambda item: (item["context"], item["app_id"] or 0))
                if (
                    parameter_checks != sorted(raw["required_checks"], key=lambda item: (item["context"], item["app_id"]))
                    or raw["strict"] != parsed["strict_required_status_checks_policy"]
                ):
                    unknowns.append({
                        "surface": f"active-rules[{index}].parameters",
                        "fields": {"cross_check": "required status parameters differ"},
                    })
            result.append({
                "ruleset_id": raw["ruleset_id"], "source_type": raw["source_type"],
                "source_id": raw["source_id"], "rule_type": rule_type,
                "parameters_sha256": _sha256(raw["parameters"]),
                "approval_count": raw["approval_count"],
                "allowed_merge_methods": allowed_merge_methods,
                "code_owner_review_required": code_owner_review_required,
                "required_checks": _checks(raw["required_checks"], f"active-rules[{index}].required-checks", unknowns),
                "strict": raw["strict"],
            })
        return sorted(result, key=lambda item: (int(item["ruleset_id"]), str(item["rule_type"])))

    @staticmethod
    def _source_rulesets(
        page: PageResponse,
        bypass_page: PageResponse,
        unknowns: list[dict],
        unknown_reasons: list[str],
    ) -> list[dict]:
        bypass_by_ruleset: dict[object, list[str]] = {}
        for index, value in enumerate(bypass_page.items):
            raw = _take(
                value, required={"ruleset_id", "actor_type", "actor_id"},
                surface=f"bypass-actors[{index}]", unknowns=unknowns,
            )
            if raw["actor_type"] not in {
                "User", "Team", "RepositoryRole", "OrganizationAdmin", "DeployKey", "Integration",
            }:
                unknown_reasons.append("bypass-visibility-unknown")
                unknowns.append({"surface": f"bypass-actors[{index}]", "fields": {"actor_type": raw["actor_type"]}})
                continue
            bypass_by_ruleset.setdefault(raw["ruleset_id"], []).append(
                f"{raw['actor_type']}:{raw['actor_id']}"
            )

        result = []
        required = {"id", "source_type", "source_id", "enforcement", "conditions", "rules", "updated_at"}
        for index, value in enumerate(page.items):
            raw = _take(
                value, required=required, optional={"bypass_visibility"},
                surface=f"source-rulesets[{index}]", unknowns=unknowns,
            )
            if not raw["source_id"] or not raw["source_type"]:
                raise _Stop(ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE, "source-rulesets", "ruleset parent cannot be attributed")
            visibility = raw.get("bypass_visibility", "unknown")
            if visibility != "complete":
                visibility = "unknown"
                unknown_reasons.append("bypass-visibility-unknown")
            result.append({
                "id": raw["id"], "source_type": raw["source_type"],
                "source_id": raw["source_id"], "enforcement": raw["enforcement"],
                "conditions_sha256": _sha256(raw["conditions"]),
                "rules_sha256": _sha256(raw["rules"]),
                "active_rules_sha256": GitHubMergeObserver._source_rule_signature(
                    raw["rules"], f"source-rulesets[{index}].rules", unknowns
                ),
                "updated_at": raw["updated_at"],
                "bypass_visibility": visibility,
                "bypass_actor_keys": sorted(set(bypass_by_ruleset.get(raw["id"], []))),
            })
        known_ids = {item["id"] for item in result}
        if set(bypass_by_ruleset) - known_ids:
            raise _Stop(ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE, "bypass-actors", "bypass actor names an unattributed ruleset")
        return sorted(result, key=lambda item: int(item["id"]))

    @staticmethod
    def _source_rule_signature(rules, surface: str, unknowns: list[dict]) -> str:
        if not isinstance(rules, list):
            raise _Stop(
                ObservationOutcome.MALFORMED_RESPONSE, surface,
                "source rules must be a list",
            )
        signature = []
        for index, value in enumerate(rules):
            raw = _take(
                value, required={"type"}, optional={"parameters"},
                surface=f"{surface}[{index}]", unknowns=unknowns,
            )
            parameters = raw.get("parameters", {})
            if not isinstance(parameters, Mapping):
                raise _Stop(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    f"{surface}[{index}].parameters",
                    "source rule parameters must be an object",
                )
            signature.append({
                "rule_type": raw["type"],
                "parameters_sha256": _sha256(parameters),
            })
        return _sha256(sorted(signature, key=lambda item: item["rule_type"]))

    @staticmethod
    def _classic(
        response: EndpointResponse,
        active_page: PageResponse,
        repository: Mapping[str, object],
        unknowns: list[dict],
        unknown_reasons: list[str],
    ) -> dict:
        raw = _take(
            response.data,
            required={
                "status", "settings", "required_review_count", "required_checks",
                "bypass_actors", "enforce_admins",
                "conversation_resolution_required", "last_push_approval_required",
                "dismiss_stale_reviews", "code_owner_review_required",
                "required_linear_history", "required_signatures",
                "restrictions_present", "dismissal_restrictions_present",
            },
            optional={"bypass_visibility", "absence_proof"},
            surface="classic-protection", unknowns=unknowns,
        )
        status = raw["status"]
        semantic_fields = {
            "required_review_count", "required_checks", "enforce_admins",
            "conversation_resolution_required", "last_push_approval_required",
            "dismiss_stale_reviews", "code_owner_review_required",
            "required_linear_history", "required_signatures",
            "restrictions_present", "dismissal_restrictions_present",
        }
        if status == "present":
            if not isinstance(raw["settings"], Mapping):
                raise _Stop(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    "classic-protection.settings",
                    "present classic protection requires a settings object",
                )
            normalized_settings = _take(
                raw["settings"], required=semantic_fields,
                surface="classic-protection.settings", unknowns=unknowns,
            )
            mismatched = {
                field: "semantic cross-check differs"
                for field in sorted(semantic_fields)
                if normalized_settings[field] != raw[field]
            }
            if mismatched:
                unknowns.append({
                    "surface": "classic-protection.settings",
                    "fields": mismatched,
                })
        if status == "absent":
            proof = raw.get("absence_proof")
            valid_proof = False
            if isinstance(proof, Mapping):
                proof = _take(
                    proof,
                    required={"endpoint", "repository_id", "repository_node_id", "permission_confirmed"},
                    surface="classic-protection.absence-proof", unknowns=unknowns,
                )
                valid_proof = (
                    proof["endpoint"] == "classic-protection"
                    and proof["repository_id"] == repository["id"]
                    and proof["repository_node_id"] == repository["node_id"]
                    and proof["permission_confirmed"] is True
                    and active_page.complete
                    and not active_page.truncated
                )
            if not valid_proof:
                status = "unknown"
                unknown_reasons.append("classic-protection-unknown")
        if status == "unknown":
            unknown_reasons.append("classic-protection-unknown")
        visibility = raw.get("bypass_visibility", "unknown")
        if visibility not in {"complete", "not-applicable"}:
            visibility = "unknown"
            unknown_reasons.append("bypass-visibility-unknown")
        bypass = []
        if not isinstance(raw["bypass_actors"], list):
            raise _Stop(ObservationOutcome.MALFORMED_RESPONSE, "classic-protection", "bypass actors must be a list")
        for index, value in enumerate(raw["bypass_actors"]):
            item = _take(value, required={"actor_type", "actor_id"}, surface=f"classic-protection.bypass[{index}]", unknowns=unknowns)
            bypass.append(f"{item['actor_type']}:{item['actor_id']}")
        return {
            "status": status,
            "settings_sha256": _sha256(raw["settings"]) if raw["settings"] is not None else None,
            "required_review_count": raw["required_review_count"],
            "required_checks": _checks(raw["required_checks"], "classic-protection.required-checks", unknowns),
            "bypass_visibility": visibility, "bypass_actor_keys": sorted(set(bypass)),
            "enforce_admins": raw["enforce_admins"],
            "conversation_resolution_required": raw["conversation_resolution_required"],
            "last_push_approval_required": raw["last_push_approval_required"],
            "dismiss_stale_reviews": raw["dismiss_stale_reviews"],
            "code_owner_review_required": raw["code_owner_review_required"],
            "required_linear_history": raw["required_linear_history"],
            "required_signatures": raw["required_signatures"],
            "restrictions_present": raw["restrictions_present"],
            "dismissal_restrictions_present": raw[
                "dismissal_restrictions_present"
            ],
        }

    @staticmethod
    def _reviews(page: PageResponse, unknowns: list[dict]) -> list[dict]:
        result = []
        required = {"id", "user", "repository_permission", "state", "commit_id", "submitted_at", "author_association", "dismissed"}
        for index, value in enumerate(page.items):
            raw = _take(value, required=required, surface=f"reviews[{index}]", unknowns=unknowns)
            user = _take(raw["user"], required={"id", "login", "type"}, surface=f"reviews[{index}].user", unknowns=unknowns)
            permission = _take(
                raw["repository_permission"], required={"permission", "user"},
                surface=f"reviews[{index}].repository-permission", unknowns=unknowns,
            )
            permission_user = _take(
                permission["user"], required={"id", "login"},
                surface=f"reviews[{index}].repository-permission.user", unknowns=unknowns,
            )
            if (
                permission_user["id"] != user["id"]
                or permission_user["login"] != user["login"]
            ):
                raise _Stop(
                    ObservationOutcome.FIELD_UNKNOWN,
                    f"reviews[{index}].repository-permission",
                    "reviewer permission identity differs from review actor",
                )
            result.append({
                "id": raw["id"], "actor_id": user["id"], "actor_login": user["login"],
                "actor_type": user["type"],
                "repository_permission": permission["permission"],
                "state": raw["state"], "commit_sha": raw["commit_id"],
                "submitted_at": raw["submitted_at"], "author_association": raw["author_association"],
                "dismissed": raw["dismissed"],
            })
        return sorted(result, key=lambda item: int(item["id"]))

    @staticmethod
    def _review_requests(page: PageResponse, unknowns: list[dict]) -> list[dict]:
        result = []
        for index, value in enumerate(page.items):
            raw = _take(value, required={"reviewer", "as_code_owner"}, surface=f"review-requests[{index}]", unknowns=unknowns)
            reviewer = _take(raw["reviewer"], required={"id", "type"}, surface=f"review-requests[{index}].reviewer", unknowns=unknowns)
            result.append({"actor_id": reviewer["id"], "actor_type": reviewer["type"], "as_code_owner": raw["as_code_owner"]})
        return sorted(result, key=lambda item: (str(item["actor_type"]), int(item["actor_id"])))

    @staticmethod
    def _review_threads(page: PageResponse, unknowns: list[dict]) -> list[dict]:
        result = []
        for index, value in enumerate(page.items):
            raw = _take(value, required={"id", "is_resolved", "is_outdated"}, surface=f"review-threads[{index}]", unknowns=unknowns)
            result.append({"node_id": raw["id"], "resolved": raw["is_resolved"], "outdated": raw["is_outdated"]})
        return sorted(result, key=lambda item: str(item["node_id"]))

    @staticmethod
    def _check_evidence(
        check_page: PageResponse,
        status_page: PageResponse,
        unknowns: list[dict],
    ) -> list[dict]:
        result = []
        for index, value in enumerate(check_page.items):
            raw = _take(
                value,
                required={"id", "name", "app", "head_sha", "required", "status", "conclusion", "completed_at"},
                surface=f"check-runs[{index}]", unknowns=unknowns,
            )
            app = _take(raw["app"], required={"id"}, surface=f"check-runs[{index}].app", unknowns=unknowns)
            result.append({
                "id": raw["id"], "source": "check-run", "context": raw["name"],
                "app_id": app["id"], "creator_actor_id": app["id"],
                "creator_actor_type": "Integration", "sha": raw["head_sha"],
                "required": raw["required"],
                "status": raw["status"], "conclusion": raw["conclusion"],
                "completed_at": raw["completed_at"],
            })
        states = {
            "pending": ("in_progress", None), "success": ("completed", "success"),
            "failure": ("completed", "failure"), "error": ("completed", "failure"),
        }
        for index, value in enumerate(status_page.items):
            raw = _take(
                value, required={"id", "context", "creator", "sha", "required", "state", "updated_at"},
                surface=f"commit-statuses[{index}]", unknowns=unknowns,
            )
            creator = _take(
                raw["creator"], required={"id", "type"},
                surface=f"commit-statuses[{index}].creator", unknowns=unknowns,
            )
            if raw["state"] not in states:
                raise _Stop(ObservationOutcome.MALFORMED_RESPONSE, "commit-statuses", f"unknown status state: {raw['state']}")
            status, conclusion = states[raw["state"]]
            result.append({
                "id": raw["id"], "source": "commit-status", "context": raw["context"],
                "app_id": None, "creator_actor_id": creator["id"],
                "creator_actor_type": creator["type"], "sha": raw["sha"],
                "required": raw["required"],
                "status": status, "conclusion": conclusion,
                "completed_at": raw["updated_at"] if status == "completed" else None,
            })
        return sorted(result, key=lambda item: (str(item["source"]), int(item["id"])))
