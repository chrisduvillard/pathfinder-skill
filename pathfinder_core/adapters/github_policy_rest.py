from __future__ import annotations

import json
import re
from typing import Mapping, Sequence
from urllib.parse import quote

from ..merge_time import parse_aware_timestamp
from .github_evidence_collector import GitHubNormalizedPolicySnapshot
from .github_get import GitHubGETClient, QualifiedFeatureResponse
from .github_memberships import GitHubBypassMembershipReader
from .github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)


_REPOSITORY_FIELDS = {
    "id", "node_id", "owner_id", "owner", "name", "base_branch",
}
_ACTOR_FIELDS = {"actor_id", "login"}
_RULE_FIELDS = {"type", "parameters"}
_ACTIVE_REQUIRED = {
    "type", "ruleset_source_type", "ruleset_source", "ruleset_id",
}
_SUMMARY_REQUIRED = {
    "id", "name", "target", "source_type", "source", "enforcement",
    "node_id", "updated_at",
}
_SUMMARY_OPTIONAL = {
    "_links", "bypass_actors", "conditions", "created_at",
    "current_user_can_bypass", "rules",
}
_DETAIL_REQUIRED = _SUMMARY_REQUIRED | {"conditions", "rules", "created_at"}
_DETAIL_OPTIONAL = {"_links", "bypass_actors", "current_user_can_bypass"}
_BYPASS_TYPES = {
    "Integration", "OrganizationAdmin", "RepositoryRole", "Team",
    "DeployKey", "User",
}
_BYPASS_MODES = {"always", "pull_request", "exempt"}
_SOURCE_TYPES = {"Repository", "Organization"}
_MERGE_METHODS = {"merge", "squash", "rebase"}
_CLASSIC_FIELDS = {
    "allow_deletions", "allow_force_pushes", "allow_fork_syncing",
    "block_creations", "enabled", "enforce_admins", "lock_branch", "name",
    "protection_url", "required_conversation_resolution",
    "required_linear_history", "required_pull_request_reviews",
    "required_signatures", "required_status_checks", "restrictions", "url",
}
_CLASSIC_CHECK_FIELDS = {
    "url", "strict", "contexts", "contexts_url", "checks",
    "enforcement_level",
}
_CLASSIC_REVIEW_FIELDS = {
    "url", "dismissal_restrictions", "bypass_pull_request_allowances",
    "dismiss_stale_reviews", "require_code_owner_reviews",
    "required_approving_review_count", "require_last_push_approval",
}
_REVIEW_REQUIRED = {
    "dismiss_stale_reviews", "require_code_owner_reviews",
    "required_approving_review_count", "require_last_push_approval",
}
_ACTOR_LIST_FIELDS = {"users", "teams", "apps"}
_DISMISSAL_FIELDS = _ACTOR_LIST_FIELDS | {
    "url", "users_url", "teams_url", "apps_url",
}


def _fail(
    surface: str,
    detail: str,
    outcome: ObservationOutcome = ObservationOutcome.FIELD_UNKNOWN,
) -> GitHubObservationError:
    return GitHubObservationError(outcome, surface, detail)


def _closed(
    value: object,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    surface: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(
            surface,
            "GitHub policy response is not an object",
            ObservationOutcome.MALFORMED_RESPONSE,
        )
    missing = required - set(value)
    if missing:
        raise _fail(
            surface,
            f"GitHub policy response omits {', '.join(sorted(missing))}",
            ObservationOutcome.MALFORMED_RESPONSE,
        )
    extras = set(value) - required - optional
    if extras:
        raise _fail(
            surface,
            f"GitHub policy response added {', '.join(sorted(extras))}",
        )
    return value


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "GitHub policy identity is malformed")
    return value


def _boolean(value: object, surface: str) -> bool:
    if not isinstance(value, bool):
        raise _fail(surface, "GitHub policy boolean is malformed")
    return value


def _nonempty(value: object, surface: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(surface, "GitHub policy string is malformed")
    return value


def _unique_audits(audits: Sequence[RequestAudit]) -> None:
    request_ids = [audit.request_id for audit in audits]
    if len(request_ids) != len(set(request_ids)):
        raise _fail("policy", "GitHub policy request id was reused")


class GitHubPolicyRESTReader:
    """Project classic and layered GitHub policy through one GET-only snapshot."""

    def __init__(
        self,
        client: GitHubGETClient,
        *,
        repository: Mapping[str, object],
        merge_actor: Mapping[str, object],
    ):
        if not isinstance(client, GitHubGETClient):
            raise TypeError("GitHub policy reader requires a fixed GET client")
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub policy reads require an installation token")
        if set(repository) != _REPOSITORY_FIELDS or set(merge_actor) != _ACTOR_FIELDS:
            raise ValueError("GitHub policy repository or merge actor is not closed")
        self.repository = {
            "id": _positive_int(repository["id"], "policy.repository"),
            "node_id": _nonempty(repository["node_id"], "policy.repository"),
            "owner_id": _positive_int(
                repository["owner_id"], "policy.repository.owner"
            ),
            "owner": _nonempty(repository["owner"], "policy.repository.owner"),
            "name": _nonempty(repository["name"], "policy.repository.name"),
            "base_branch": _nonempty(
                repository["base_branch"], "policy.repository.base-branch"
            ),
        }
        self.merge_actor = {
            "actor_id": _positive_int(
                merge_actor["actor_id"], "policy.merge-actor"
            ),
            "login": _nonempty(merge_actor["login"], "policy.merge-actor"),
        }
        owner = self.repository["owner"]
        name = self.repository["name"]
        branch = self.repository["base_branch"]
        if (
            re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", str(owner)) is None
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", str(name)) is None
            or re.fullmatch(r"[A-Za-z0-9_.~/-]{1,255}", str(branch)) is None
            or re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\[bot\]",
                str(self.merge_actor["login"]),
            )
            is None
        ):
            raise ValueError("GitHub policy repository or merge actor is malformed")
        self.client = client
        self.memberships = GitHubBypassMembershipReader(client)
        self.repository_path = (
            f"/repos/{quote(str(owner), safe='')}/{quote(str(name), safe='')}"
        )
        self.branch_path = quote(str(branch), safe="/")

    @property
    def credential(self):
        return self.client.credential

    @staticmethod
    def _enabled(
        data: Mapping[str, object], key: str, *, default: bool = False
    ) -> bool:
        value = data.get(key)
        if value is None:
            return default
        raw = _closed(
            value,
            required={"enabled"},
            optional={"url"},
            surface=f"classic-protection.{key}",
        )
        return _boolean(raw["enabled"], f"classic-protection.{key}")

    @staticmethod
    def _actor_lists(
        value: object,
        *,
        surface: str,
        allowed_fields: set[str],
    ) -> Mapping[str, list[object]]:
        raw = _closed(
            value,
            required=_ACTOR_LIST_FIELDS,
            optional=allowed_fields - _ACTOR_LIST_FIELDS,
            surface=surface,
        )
        result = {}
        for name in _ACTOR_LIST_FIELDS:
            items = raw.get(name, [])
            if not isinstance(items, list):
                raise _fail(surface, f"GitHub {name} actor list is malformed")
            result[name] = items
        return result

    @staticmethod
    def _classic_bypass(
        review: Mapping[str, object],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        allowances = review.get("bypass_pull_request_allowances")
        if allowances is None:
            return [], []
        groups = GitHubPolicyRESTReader._actor_lists(
            allowances,
            surface="classic-protection.bypass",
            allowed_fields=_ACTOR_LIST_FIELDS,
        )
        actors: list[dict[str, object]] = []
        targets: list[dict[str, object]] = []
        mapping = {"users": "User", "teams": "Team", "apps": "Integration"}
        for group, actor_type in mapping.items():
            for index, value in enumerate(groups[group]):
                surface = f"classic-protection.bypass.{group}[{index}]"
                if not isinstance(value, Mapping):
                    raise _fail(surface, "GitHub classic bypass actor is malformed")
                actor_id = _positive_int(value.get("id"), surface)
                actor_name = None
                if actor_type == "Team":
                    actor_name = _nonempty(value.get("slug"), surface)
                actor = {"actor_type": actor_type, "actor_id": actor_id}
                if actor_name is not None:
                    actor["actor_name"] = actor_name
                actors.append(actor)
                if actor_type == "Team":
                    targets.append({
                        "policy_source": "classic-protection",
                        "ruleset_id": None,
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "bypass_mode": None,
                        "actor_name": actor_name,
                    })
        keys = [(item["actor_type"], item["actor_id"]) for item in actors]
        if len(keys) != len(set(keys)):
            raise _fail("classic-protection.bypass", "classic bypass actor is duplicated")
        return actors, targets

    @staticmethod
    def _classic_checks(
        data: Mapping[str, object], audit: RequestAudit
    ) -> tuple[list[dict[str, object]], QualifiedFeatureResponse]:
        value = data.get("required_status_checks")
        if value is None:
            return [], QualifiedFeatureResponse(
                {"required_status_checks": None}, 200, audit
            )
        raw = _closed(
            value,
            required={"url", "strict", "contexts", "contexts_url", "checks"},
            optional={"enforcement_level"},
            surface="classic-protection.required-status-checks",
        )
        if (
            not isinstance(raw["contexts"], list)
            or not isinstance(raw["checks"], list)
        ):
            raise _fail(
                "classic-protection.required-status-checks",
                "GitHub classic required checks are not complete lists",
            )
        checks = []
        for index, value in enumerate(raw["checks"]):
            item = _closed(
                value,
                required={"context", "app_id"},
                surface=f"classic-protection.checks[{index}]",
            )
            checks.append({
                "context": _nonempty(
                    item["context"], f"classic-protection.checks[{index}]"
                ),
                "app_id": _positive_int(
                    item["app_id"], f"classic-protection.checks[{index}]"
                ),
            })
        contexts = [
            _nonempty(value, f"classic-protection.contexts[{index}]")
            for index, value in enumerate(raw["contexts"])
        ]
        if (
            len(contexts) != len(set(contexts))
            or set(contexts) != {item["context"] for item in checks}
            or len(checks)
            != len({(item["context"], item["app_id"]) for item in checks})
        ):
            raise _fail(
                "classic-protection.required-status-checks",
                "GitHub classic check identities are duplicated or contradictory",
            )
        projected = {
            "required_status_checks": {
                "url": _nonempty(raw["url"], "classic-protection.checks.url"),
                "strict": _boolean(
                    raw["strict"], "classic-protection.checks.strict"
                ),
                "contexts": contexts,
                "contexts_url": _nonempty(
                    raw["contexts_url"], "classic-protection.checks.contexts-url"
                ),
                "checks": checks,
            }
        }
        return checks, QualifiedFeatureResponse(projected, 200, audit)

    def _classic(
        self, response: QualifiedFeatureResponse
    ) -> tuple[
        EndpointResponse,
        QualifiedFeatureResponse,
        list[dict[str, object]],
    ]:
        if response.status == 403:
            nulls = {
                "required_review_count": None,
                "required_checks": [],
                "enforce_admins": None,
                "conversation_resolution_required": None,
                "last_push_approval_required": None,
                "dismiss_stale_reviews": None,
                "code_owner_review_required": None,
                "required_linear_history": None,
                "required_signatures": None,
                "restrictions_present": None,
                "dismissal_restrictions_present": None,
            }
            normalized = {
                "status": "absent",
                "settings": None,
                **nulls,
                "bypass_visibility": "not-applicable",
                "bypass_actors": [],
                "absence_proof": {
                    "endpoint": "classic-protection",
                    "repository_id": self.repository["id"],
                    "repository_node_id": self.repository["node_id"],
                    "permission_confirmed": True,
                },
            }
            return (
                EndpointResponse(normalized, response.audit),
                response,
                [],
            )
        data = _closed(
            response.data,
            required={"url"},
            optional=_CLASSIC_FIELDS - {"url"},
            surface="classic-protection",
        )
        for key in (
            "allow_deletions", "allow_force_pushes", "allow_fork_syncing",
            "block_creations",
        ):
            self._enabled(data, key)
        if self._enabled(data, "lock_branch"):
            raise _fail(
                "classic-protection.lock-branch",
                "a locked base branch is outside the supported merge policy",
            )
        checks, check_policy = self._classic_checks(data, response.audit)
        review_value = data.get("required_pull_request_reviews")
        targets: list[dict[str, object]] = []
        if review_value is None:
            review_count = 0
            dismiss_stale = code_owner = last_push = False
            dismissal_present = False
            bypass = []
        else:
            review = _closed(
                review_value,
                required=_REVIEW_REQUIRED,
                optional=_CLASSIC_REVIEW_FIELDS - _REVIEW_REQUIRED,
                surface="classic-protection.required-reviews",
            )
            review_count = review["required_approving_review_count"]
            if (
                not isinstance(review_count, int)
                or isinstance(review_count, bool)
                or not 0 <= review_count <= 6
            ):
                raise _fail(
                    "classic-protection.required-reviews",
                    "GitHub classic review count is malformed",
                )
            dismiss_stale = _boolean(
                review["dismiss_stale_reviews"],
                "classic-protection.dismiss-stale-reviews",
            )
            code_owner = _boolean(
                review["require_code_owner_reviews"],
                "classic-protection.code-owner-reviews",
            )
            last_push = _boolean(
                review["require_last_push_approval"],
                "classic-protection.last-push-approval",
            )
            dismissal = review.get("dismissal_restrictions")
            if dismissal is None:
                dismissal_present = False
            else:
                groups = self._actor_lists(
                    dismissal,
                    surface="classic-protection.dismissal-restrictions",
                    allowed_fields=_DISMISSAL_FIELDS,
                )
                dismissal_present = any(groups.values())
            bypass, targets = self._classic_bypass(review)
        semantic = {
            "required_review_count": review_count,
            "required_checks": checks,
            "enforce_admins": self._enabled(data, "enforce_admins"),
            "conversation_resolution_required": self._enabled(
                data, "required_conversation_resolution"
            ),
            "last_push_approval_required": last_push,
            "dismiss_stale_reviews": dismiss_stale,
            "code_owner_review_required": code_owner,
            "required_linear_history": self._enabled(
                data, "required_linear_history"
            ),
            "required_signatures": self._enabled(data, "required_signatures"),
            "restrictions_present": data.get("restrictions") is not None,
            "dismissal_restrictions_present": dismissal_present,
        }
        normalized = {
            "status": "present",
            "settings": dict(semantic),
            **semantic,
            "bypass_visibility": "complete",
            "bypass_actors": bypass,
        }
        return EndpointResponse(normalized, response.audit), check_policy, targets

    def _source_id(self, source_type: object, source: object, surface: str) -> int:
        if source_type not in _SOURCE_TYPES or not isinstance(source, str):
            raise _fail(surface, "GitHub ruleset source type is unsupported")
        if source_type == "Repository":
            if source != f"{self.repository['owner']}/{self.repository['name']}":
                raise _fail(surface, "GitHub repository ruleset source differs")
            return int(self.repository["id"])
        if source != self.repository["owner"]:
            raise _fail(surface, "GitHub organization ruleset source differs")
        return int(self.repository["owner_id"])

    @staticmethod
    def _rule_parameters(
        rule_type: str, parameters: Mapping[str, object], surface: str
    ) -> tuple[object, list[dict[str, object]], object]:
        approval_count = None
        checks: list[dict[str, object]] = []
        strict = None
        if rule_type == "pull_request":
            required = {
                "allowed_merge_methods", "dismiss_stale_reviews_on_push",
                "require_code_owner_review", "require_last_push_approval",
                "required_approving_review_count",
                "required_review_thread_resolution",
            }
            _closed(
                parameters,
                required=required,
                optional={"dismissal_restriction", "required_reviewers"},
                surface=f"{surface}.parameters",
            )
            methods = parameters["allowed_merge_methods"]
            if (
                not isinstance(methods, list)
                or not methods
                or any(value not in _MERGE_METHODS for value in methods)
                or len(methods) != len(set(methods))
            ):
                raise _fail(surface, "GitHub allowed merge methods are malformed")
            approval_count = parameters["required_approving_review_count"]
            if (
                not isinstance(approval_count, int)
                or isinstance(approval_count, bool)
                or not 0 <= approval_count <= 10
            ):
                raise _fail(surface, "GitHub ruleset review count is malformed")
            for key in required - {
                "allowed_merge_methods", "required_approving_review_count"
            }:
                _boolean(parameters[key], f"{surface}.parameters.{key}")
        elif rule_type == "required_status_checks":
            _closed(
                parameters,
                required={
                    "required_status_checks",
                    "strict_required_status_checks_policy",
                },
                optional={"do_not_enforce_on_create"},
                surface=f"{surface}.parameters",
            )
            values = parameters["required_status_checks"]
            if not isinstance(values, list) or not values:
                raise _fail(surface, "GitHub ruleset required checks are malformed")
            for index, value in enumerate(values):
                item = _closed(
                    value,
                    required={"context", "integration_id"},
                    surface=f"{surface}.parameters.checks[{index}]",
                )
                checks.append({
                    "context": _nonempty(
                        item["context"], f"{surface}.parameters.checks[{index}]"
                    ),
                    "app_id": _positive_int(
                        item["integration_id"],
                        f"{surface}.parameters.checks[{index}]",
                    ),
                })
            if len(checks) != len({
                (item["context"], item["app_id"]) for item in checks
            }):
                raise _fail(surface, "GitHub ruleset check identity is duplicated")
            strict = _boolean(
                parameters["strict_required_status_checks_policy"], surface
            )
            create = parameters.get("do_not_enforce_on_create")
            if create is not None:
                _boolean(create, f"{surface}.parameters.do-not-enforce-on-create")
        elif rule_type == "required_linear_history" and parameters:
            raise _fail(
                surface,
                "GitHub linear-history rule added unsupported parameters",
            )
        return approval_count, checks, strict

    def _active(
        self, page: PageResponse
    ) -> tuple[PageResponse, PageResponse, set[int]]:
        if not page.complete or page.truncated or page.last_cursor is not None:
            raise _fail(
                "active-rules",
                "GitHub active rules pagination is incomplete",
                ObservationOutcome.PAGINATION_INCOMPLETE,
            )
        normalized = []
        projected = []
        ruleset_ids: set[int] = set()
        seen = set()
        for index, value in enumerate(page.items):
            surface = f"active-rules[{index}]"
            raw = _closed(
                value,
                required=_ACTIVE_REQUIRED,
                optional={"parameters"},
                surface=surface,
            )
            rule_type = _nonempty(raw["type"], surface)
            ruleset_id = _positive_int(raw["ruleset_id"], surface)
            source_type = raw["ruleset_source_type"]
            source_id = self._source_id(
                source_type, raw["ruleset_source"], surface
            )
            parameters = raw.get("parameters", {})
            if not isinstance(parameters, Mapping):
                raise _fail(surface, "GitHub active rule parameters are malformed")
            key = (ruleset_id, rule_type)
            if key in seen:
                raise _fail("active-rules", "GitHub active rule is duplicated")
            seen.add(key)
            ruleset_ids.add(ruleset_id)
            approval_count, checks, strict = self._rule_parameters(
                rule_type, parameters, surface
            )
            normalized.append({
                "ruleset_id": ruleset_id,
                "source_type": source_type,
                "source_id": source_id,
                "rule_type": rule_type,
                "parameters": dict(parameters),
                "approval_count": approval_count,
                "required_checks": checks,
                "strict": strict,
            })
            projected.append({
                "type": rule_type,
                "ruleset_source_type": source_type,
                "ruleset_source": raw["ruleset_source"],
                "ruleset_id": ruleset_id,
                "parameters": dict(parameters),
            })
        return (
            PageResponse(
                tuple(normalized), page.pages, len(normalized), True, False,
                None, page.audits,
            ),
            PageResponse(
                tuple(projected), page.pages, len(projected), True, False,
                None, page.audits,
            ),
            ruleset_ids,
        )

    @staticmethod
    def _summary(value: object, index: int) -> Mapping[str, object]:
        raw = _closed(
            value,
            required=_SUMMARY_REQUIRED,
            optional=_SUMMARY_OPTIONAL,
            surface=f"source-rulesets.index[{index}]",
        )
        _positive_int(raw["id"], f"source-rulesets.index[{index}]")
        return raw

    def _ruleset_bypass(
        self, raw: Mapping[str, object], ruleset_id: int
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
        if "bypass_actors" not in raw:
            return [], [], "unknown"
        values = raw["bypass_actors"]
        if not isinstance(values, list):
            raise _fail(
                f"source-rulesets[{ruleset_id}].bypass",
                "GitHub ruleset bypass actors are malformed",
            )
        actors = []
        targets = []
        seen = set()
        for index, value in enumerate(values):
            surface = f"source-rulesets[{ruleset_id}].bypass[{index}]"
            item = _closed(
                value,
                required={"actor_id", "actor_type", "bypass_mode"},
                surface=surface,
            )
            actor_type = item["actor_type"]
            bypass_mode = item["bypass_mode"]
            if actor_type not in _BYPASS_TYPES or bypass_mode not in _BYPASS_MODES:
                raise _fail(surface, "GitHub ruleset bypass actor is unsupported")
            actor_id = item["actor_id"]
            if actor_type in {"OrganizationAdmin", "DeployKey"}:
                if actor_id is not None:
                    raise _fail(surface, "GitHub idless bypass actor carried an id")
            else:
                actor_id = _positive_int(actor_id, surface)
            key = (actor_type, actor_id, bypass_mode)
            if key in seen:
                raise _fail(surface, "GitHub ruleset bypass actor is duplicated")
            seen.add(key)
            actor = {
                "ruleset_id": ruleset_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "bypass_mode": bypass_mode,
            }
            actors.append(actor)
            if actor_type == "OrganizationAdmin":
                targets.append({
                    "policy_source": "ruleset",
                    "ruleset_id": ruleset_id,
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "bypass_mode": bypass_mode,
                    "actor_name": None,
                })
            # REST exposes only Team/RepositoryRole ids. Without source-owned names,
            # the observer deliberately leaves those membership facts unresolved.
        return actors, targets, "complete"

    def _sources(
        self,
        index: PageResponse,
        ruleset_ids: set[int],
        active_rules: PageResponse,
    ) -> tuple[PageResponse, PageResponse, list[dict[str, object]]]:
        if not index.complete or index.truncated or index.last_cursor is not None:
            raise _fail(
                "source-rulesets",
                "GitHub source ruleset pagination is incomplete",
                ObservationOutcome.PAGINATION_INCOMPLETE,
            )
        summaries = {}
        for position, value in enumerate(index.items):
            summary = self._summary(value, position)
            ruleset_id = int(summary["id"])
            if ruleset_id in summaries:
                raise _fail("source-rulesets", "GitHub source ruleset is duplicated")
            summaries[ruleset_id] = summary
        if ruleset_ids - set(summaries):
            raise _fail(
                "source-rulesets",
                "an active ruleset is absent from the complete source index",
                ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE,
            )
        if index.pages + len(ruleset_ids) > self.client.max_pages:
            raise _fail(
                "source-rulesets",
                "GitHub source ruleset request ceiling would be exceeded",
                ObservationOutcome.PAGINATION_INCOMPLETE,
            )
        normalized = []
        bypass_actors = []
        membership_targets = []
        audits = list(index.audits)
        for ruleset_id in sorted(ruleset_ids):
            endpoint = (
                f"{self.repository_path}/rulesets/{ruleset_id}"
                "?includes_parents=true"
            )
            response = self.client.get_qualified_source_ruleset(
                "source-rulesets", endpoint
            )
            audits.append(response.audit)
            raw = _closed(
                response.data,
                required=_DETAIL_REQUIRED,
                optional=_DETAIL_OPTIONAL,
                surface=f"source-rulesets[{ruleset_id}]",
            )
            summary = summaries[ruleset_id]
            common = (
                "id", "name", "target", "source_type", "source",
                "enforcement", "node_id", "updated_at",
            )
            if any(raw[key] != summary[key] for key in common):
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "GitHub source index and detail differ",
                    ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE,
                )
            if raw["target"] != "branch":
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "an active branch rule came from a non-branch ruleset",
                    ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE,
                )
            if raw["enforcement"] != "active":
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "an aggregate active rule came from a non-active ruleset",
                    ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE,
                )
            try:
                parse_aware_timestamp(raw["updated_at"])
                parse_aware_timestamp(raw["created_at"])
            except (TypeError, ValueError):
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "GitHub ruleset time is malformed",
                    ObservationOutcome.MALFORMED_RESPONSE,
                ) from None
            conditions = raw["conditions"]
            rules = raw["rules"]
            if not isinstance(conditions, Mapping) or not isinstance(rules, list):
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "GitHub ruleset conditions or rules are malformed",
                )
            projected_rules = []
            for index_value, value in enumerate(rules):
                rule = _closed(
                    value,
                    required={"type"},
                    optional={"parameters"},
                    surface=(
                        f"source-rulesets[{ruleset_id}].rules[{index_value}]"
                    ),
                )
                parameters = rule.get("parameters", {})
                if not isinstance(parameters, Mapping):
                    raise _fail(
                        f"source-rulesets[{ruleset_id}].rules[{index_value}]",
                        "GitHub source rule parameters are malformed",
                    )
                projected_rules.append({
                    "type": _nonempty(
                        rule["type"],
                        f"source-rulesets[{ruleset_id}].rules[{index_value}]",
                    ),
                    "parameters": dict(parameters),
                })
            active_signature = sorted(
                (
                    {
                        "type": item["rule_type"],
                        "parameters": item["parameters"],
                    }
                    for item in active_rules.items
                    if item["ruleset_id"] == ruleset_id
                ),
                key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":")
                ),
            )
            source_signature = sorted(
                projected_rules,
                key=lambda item: json.dumps(
                    item, sort_keys=True, separators=(",", ":")
                ),
            )
            if source_signature != active_signature:
                raise _fail(
                    f"source-rulesets[{ruleset_id}]",
                    "GitHub aggregate and source rule parameters differ",
                    ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE,
                )
            actors, targets, visibility = self._ruleset_bypass(raw, ruleset_id)
            bypass_actors.extend(actors)
            membership_targets.extend(targets)
            normalized.append({
                "id": ruleset_id,
                "node_id": raw["node_id"],
                "target": raw["target"],
                "source_type": raw["source_type"],
                "source_id": self._source_id(
                    raw["source_type"], raw["source"],
                    f"source-rulesets[{ruleset_id}]",
                ),
                "enforcement": raw["enforcement"],
                "conditions": dict(conditions),
                "rules": projected_rules,
                "updated_at": raw["updated_at"],
                "bypass_visibility": visibility,
            })
        _unique_audits(audits)
        return (
            PageResponse(
                tuple(normalized), len(audits), len(normalized), True, False,
                None, tuple(audits),
            ),
            PageResponse(
                tuple(bypass_actors), 0, len(bypass_actors), True, False,
                None, (),
            ),
            membership_targets,
        )

    def read_all(self) -> GitHubNormalizedPolicySnapshot:
        classic_raw = self.client.get_qualified_feature(
            "classic-protection",
            f"{self.repository_path}/branches/{self.branch_path}/protection",
            feature="classic-protection",
        )
        active_raw = self.client.get_qualified_feature_pages(
            "active-rules",
            f"{self.repository_path}/rules/branches/{self.branch_path}",
            feature="active-rules",
        )
        source_index = self.client.get_qualified_feature_pages(
            "source-rulesets",
            f"{self.repository_path}/rulesets?includes_parents=true",
            feature="source-rulesets",
        )
        classic, classic_checks, classic_targets = self._classic(classic_raw)
        active, active_checks, ruleset_ids = self._active(active_raw)
        sources, bypass, ruleset_targets = self._sources(
            source_index, ruleset_ids, active
        )
        memberships = self.memberships.read_all(
            [*classic_targets, *ruleset_targets],
            repository={
                "owner": self.repository["owner"],
                "name": self.repository["name"],
            },
            subject=self.merge_actor,
        )
        _unique_audits((
            classic.audit,
            *active.audits,
            *sources.audits,
            *memberships.audits,
        ))
        return GitHubNormalizedPolicySnapshot(
            classic,
            active,
            sources,
            bypass,
            memberships,
            classic_checks,
            active_checks,
        )
