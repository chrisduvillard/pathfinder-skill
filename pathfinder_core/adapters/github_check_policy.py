from __future__ import annotations

import re
from typing import Mapping, Sequence

from .github_get import QualifiedFeatureResponse
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)


_CONTEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/()@,+-]{0,99}")
_CLASSIC_CHECK_FIELDS = {"context", "app_id"}
_CLASSIC_STATUS_FIELDS = {"url", "strict", "contexts", "contexts_url", "checks"}
_ACTIVE_RULE_FIELDS = {
    "type", "ruleset_source_type", "ruleset_source", "ruleset_id", "parameters",
}
_RULESET_STATUS_FIELDS = {
    "required_status_checks", "strict_required_status_checks_policy",
    "do_not_enforce_on_create",
}
_RULESET_CHECK_FIELDS = {"context", "integration_id"}
_SOURCE_TYPES = {"Repository", "Organization", "Enterprise"}
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "required check App identity is not pinned")
    return value


def _context(value: object, surface: str) -> str:
    if not isinstance(value, str) or _CONTEXT.fullmatch(value) is None:
        raise _fail(surface, "required check context is malformed")
    return value


def _check(
    value: object,
    *,
    surface: str,
    fields: set[str],
    app_field: str,
) -> tuple[str, int]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _fail(surface, "required check fields are missing or unknown")
    return (
        _context(value["context"], surface),
        _positive_int(value[app_field], surface),
    )


def _unique(values: list[tuple[str, int]], surface: str) -> set[tuple[str, int]]:
    if len(values) != len(set(values)):
        raise _fail(surface, "required check identity is duplicated")
    return set(values)


class GitHubRequiredCheckProjector:
    """Derive one closed context/App union from host, classic, and ruleset policy."""

    @staticmethod
    def _host(values: Sequence[Mapping[str, object]]) -> set[tuple[str, int]]:
        checks = [
            _check(
                value,
                surface=f"host-policy.required-checks[{index}]",
                fields=_CLASSIC_CHECK_FIELDS,
                app_field="app_id",
            )
            for index, value in enumerate(values)
        ]
        if not checks:
            raise _fail(
                "host-policy.required-checks",
                "host policy must pin at least one required check",
            )
        return _unique(checks, "host-policy.required-checks")

    @staticmethod
    def _classic(response: QualifiedFeatureResponse) -> set[tuple[str, int]]:
        audit = response.audit
        if (
            response.status not in {200, 403}
            or audit.status != response.status
            or audit.permission_qualified is not True
            or not isinstance(audit.target, str)
            or re.fullmatch(
                r"/repos/[^/]+/[^/]+/branches/.+/protection", audit.target
            )
            is None
        ):
            raise _fail(
                "classic-protection", "classic protection read is not qualified"
            )
        if response.status == 403:
            if response.data is not None:
                raise _fail(
                    "classic-protection", "qualified feature absence carried data"
                )
            return set()
        data = response.data
        if not isinstance(data, Mapping) or "required_status_checks" not in data:
            raise _fail(
                "classic-protection", "classic protection check field is missing"
            )
        status = data["required_status_checks"]
        if status is None:
            return set()
        if not isinstance(status, Mapping) or set(status) != _CLASSIC_STATUS_FIELDS:
            raise _fail(
                "classic-protection.required-status-checks",
                "classic status-check policy is not closed",
            )
        if not isinstance(status["strict"], bool):
            raise _fail(
                "classic-protection.required-status-checks",
                "classic strict policy is malformed",
            )
        contexts = status["contexts"]
        checks = status["checks"]
        if not isinstance(contexts, list) or not isinstance(checks, list):
            raise _fail(
                "classic-protection.required-status-checks",
                "classic required checks are not complete lists",
            )
        context_values = [
            _context(value, f"classic-protection.contexts[{index}]")
            for index, value in enumerate(contexts)
        ]
        projected = [
            _check(
                value,
                surface=f"classic-protection.checks[{index}]",
                fields=_CLASSIC_CHECK_FIELDS,
                app_field="app_id",
            )
            for index, value in enumerate(checks)
        ]
        result = _unique(projected, "classic-protection.checks")
        if (
            len(context_values) != len(set(context_values))
            or set(context_values) != {context for context, _app_id in result}
        ):
            raise _fail(
                "classic-protection.required-status-checks",
                "classic context and pinned-check views differ",
            )
        return result

    @staticmethod
    def _active(page: PageResponse) -> set[tuple[str, int]]:
        if (
            not page.complete
            or page.truncated
            or page.last_cursor is not None
            or page.pages < 1
            or page.total_count != len(page.items)
            or len(page.audits) != page.pages
            or any(
                not isinstance(audit.request_id, str)
                or _REQUEST_ID.fullmatch(audit.request_id) is None
                for audit in page.audits
            )
            or len({audit.request_id for audit in page.audits}) != len(page.audits)
        ):
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "active-rules",
                "active rules are not a complete unique-request page set",
            )
        requirements: set[tuple[str, int]] = set()
        seen_rules = set()
        for index, value in enumerate(page.items):
            surface = f"active-rules[{index}]"
            if not isinstance(value, Mapping) or set(value) != _ACTIVE_RULE_FIELDS:
                raise _fail(surface, "active rule fields are missing or unknown")
            rule_id = _positive_int(value["ruleset_id"], surface)
            rule_type = value["type"]
            source_type = value["ruleset_source_type"]
            source = value["ruleset_source"]
            parameters = value["parameters"]
            if (
                not isinstance(rule_type, str)
                or not rule_type
                or source_type not in _SOURCE_TYPES
                or not isinstance(source, str)
                or not source
                or not isinstance(parameters, Mapping)
            ):
                raise _fail(surface, "active rule identity or source is malformed")
            rule_key = (rule_id, rule_type)
            if rule_key in seen_rules:
                raise _fail("active-rules", "active rule identity is duplicated")
            seen_rules.add(rule_key)
            if rule_type != "required_status_checks":
                continue
            if not {"required_status_checks", "strict_required_status_checks_policy"} <= set(parameters) or set(parameters) - _RULESET_STATUS_FIELDS:
                raise _fail(surface, "ruleset status-check policy is not closed")
            if not isinstance(parameters["strict_required_status_checks_policy"], bool):
                raise _fail(surface, "ruleset strict policy is malformed")
            create_policy = parameters.get("do_not_enforce_on_create")
            if create_policy is not None and not isinstance(create_policy, bool):
                raise _fail(surface, "ruleset create policy is malformed")
            raw_checks = parameters["required_status_checks"]
            if not isinstance(raw_checks, list) or not raw_checks:
                raise _fail(surface, "ruleset required checks are missing")
            projected = [
                _check(
                    item,
                    surface=f"{surface}.required-checks[{check_index}]",
                    fields=_RULESET_CHECK_FIELDS,
                    app_field="integration_id",
                )
                for check_index, item in enumerate(raw_checks)
            ]
            requirements |= _unique(projected, f"{surface}.required-checks")
        return requirements

    @classmethod
    def project(
        cls,
        *,
        host_policy_checks: Sequence[Mapping[str, object]],
        classic_protection: QualifiedFeatureResponse,
        active_rules: PageResponse,
    ) -> tuple[dict[str, object], ...]:
        requirements = (
            cls._host(host_policy_checks)
            | cls._classic(classic_protection)
            | cls._active(active_rules)
        )
        return tuple(
            {"context": context, "app_id": app_id}
            for context, app_id in sorted(requirements)
        )
