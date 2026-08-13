from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from ..merge_time import parse_aware_timestamp
from ..storage import canonical_sha256, read_json
from .github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)
from .github_publication_reconciliation import ControllerPusherProof


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas" / "publication"
PUBLICATION_CREDENTIAL_SCHEMA = SCHEMA_ROOT / "publication-credential-receipt.schema.json"
OWNERSHIP_SCHEMA = SCHEMA_ROOT / "controller-branch-ownership.schema.json"
REQUIRED_RULES = ("creation", "deletion", "update")


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _closed(
    value: object,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    surface: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not required <= set(value):
        raise _fail(surface, "GitHub branch ownership response is incomplete")
    if set(value) - required - optional:
        raise _fail(surface, "GitHub branch ownership response has unknown fields")
    return value


def _time(value: object, surface: str):
    try:
        return parse_aware_timestamp(value)
    except (TypeError, ValueError):
        raise _fail(surface, "GitHub branch ownership time is malformed") from None


def _audit(
    value: object,
    *,
    surface: str,
    target: str,
) -> tuple[RequestAudit, object]:
    if (
        not isinstance(value, RequestAudit)
        or not value.request_id
        or value.target != target
        or value.status != 200
        or value.permission_qualified is not True
    ):
        raise _fail(surface, "GitHub branch ownership request is not qualified")
    return value, _time(value.observed_at, surface)


def _rule_signature(value: object, surface: str) -> tuple[str, object]:
    raw = _closed(
        value,
        required={"type"},
        optional={"parameters"},
        surface=surface,
    )
    rule_type = raw["type"]
    if rule_type in {"creation", "deletion"}:
        if "parameters" in raw:
            raise _fail(surface, "restricted ref rule has unexpected parameters")
        return str(rule_type), None
    if rule_type == "update":
        parameters = _closed(
            raw.get("parameters"),
            required={"update_allows_fetch_and_merge"},
            surface=f"{surface}.parameters",
        )
        if parameters["update_allows_fetch_and_merge"] is not False:
            raise _fail(surface, "restricted update permits fetch-and-merge")
        return "update", False
    raise _fail(surface, "ownership ruleset contains an unsupported rule")


class GitHubControllerBranchOwnershipProver:
    """Prove sole publisher-App branch control from already-read GitHub facts."""

    _credential_validator = Draft202012Validator(
        read_json(PUBLICATION_CREDENTIAL_SCHEMA), format_checker=FormatChecker()
    )
    _ownership_validator = Draft202012Validator(
        read_json(OWNERSHIP_SCHEMA), format_checker=FormatChecker()
    )

    @classmethod
    def validate_document(cls, document: Mapping[str, object]) -> None:
        try:
            cls._ownership_validator.validate(document)
        except ValidationError as error:
            raise _fail("branch-ownership", "branch ownership proof is invalid") from error
        if document["ownership_sha256"] != canonical_sha256(
            document, "ownership_sha256"
        ):
            raise _fail("branch-ownership", "branch ownership proof hash differs")
        observation = document["observation"]
        if observation["request_ids_sha256"] != canonical_sha256(
            observation["request_ids"]
        ):
            raise _fail(
                "branch-ownership", "branch ownership request hash differs"
            )
        if not (
            _time(observation["evidence_completed_at"], "branch-ownership")
            <= _time(observation["observed_at"], "branch-ownership")
            <= _time(observation["completed_at"], "branch-ownership")
        ):
            raise _fail(
                "branch-ownership", "branch ownership proof window is invalid"
            )

    @classmethod
    def prove(
        cls,
        *,
        controller_pusher: ControllerPusherProof,
        publication_credential_receipt: Mapping[str, object],
        ruleset: EndpointResponse,
        effective_rules: PageResponse,
        branch_ref: EndpointResponse,
        evidence_completed_at: str,
        observed_at: str,
        completed_at: str,
        ownership_id: str,
    ) -> Mapping[str, object]:
        if not isinstance(controller_pusher, ControllerPusherProof):
            raise _fail("branch-ownership", "controller pusher proof is missing")
        try:
            cls._credential_validator.validate(publication_credential_receipt)
        except ValidationError as error:
            raise _fail(
                "publication-credential",
                "publication credential receipt is invalid",
            ) from error
        if publication_credential_receipt["receipt_sha256"] != canonical_sha256(
            publication_credential_receipt, "receipt_sha256"
        ):
            raise _fail(
                "publication-credential",
                "publication credential receipt hash differs",
            )
        publisher = publication_credential_receipt
        if (
            publisher["repository_ids"] != [controller_pusher.repository_id]
            or publisher["actor_id"] != controller_pusher.last_pusher_id
            or publisher["actor_node_id"] != controller_pusher.actor_node_id
            or publisher["login"] != controller_pusher.actor_login
        ):
            raise _fail(
                "publication-credential",
                "publication credential and controller pusher identities differ",
            )
        receipt_time = _time(controller_pusher.receipt_observed_at, "publication")
        issued_at = _time(publisher["issued_at"], "publication-credential")
        expires_at = _time(publisher["expires_at"], "publication-credential")
        if not (
            issued_at
            <= _time(publisher["verified_at"], "publication-credential")
            <= receipt_time
            < expires_at
            <= issued_at + timedelta(hours=1)
        ):
            raise _fail(
                "publication-credential",
                "publication credential was not current for publication",
            )

        repository_path = (
            f"/repos/{controller_pusher.repository_owner}/"
            f"{controller_pusher.repository_name}"
        )
        ruleset_raw = _closed(
            ruleset.data,
            required={
                "id", "node_id", "name", "target", "source_type", "source",
                "enforcement", "bypass_actors", "conditions", "rules",
                "created_at", "updated_at",
            },
            optional={"_links"},
            surface="branch-ownership.ruleset",
        )
        ruleset_id = ruleset_raw["id"]
        if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id < 1:
            raise _fail("branch-ownership.ruleset", "ruleset identity is malformed")
        expected_source = (
            f"{controller_pusher.repository_owner}/"
            f"{controller_pusher.repository_name}"
        )
        if (
            ruleset_raw["target"] != "branch"
            or ruleset_raw["source_type"] != "Repository"
            or ruleset_raw["source"] != expected_source
            or ruleset_raw["enforcement"] != "active"
        ):
            raise _fail(
                "branch-ownership.ruleset",
                "ruleset is not active for the exact repository branch target",
            )
        conditions = _closed(
            ruleset_raw["conditions"],
            required={"ref_name"},
            surface="branch-ownership.ruleset.conditions",
        )
        ref_name = _closed(
            conditions["ref_name"],
            required={"include", "exclude"},
            surface="branch-ownership.ruleset.conditions.ref_name",
        )
        if (
            not isinstance(ref_name["include"], list)
            or not ref_name["include"]
            or not all(isinstance(item, str) and item for item in ref_name["include"])
            or not isinstance(ref_name["exclude"], list)
            or not all(isinstance(item, str) and item for item in ref_name["exclude"])
        ):
            raise _fail(
                "branch-ownership.ruleset.conditions",
                "ruleset ref conditions are malformed",
            )
        bypass = ruleset_raw["bypass_actors"]
        if not isinstance(bypass, list) or len(bypass) != 1:
            raise _fail(
                "branch-ownership.ruleset",
                "publication App is not the sole ruleset bypass actor",
            )
        bypass_actor = _closed(
            bypass[0],
            required={"actor_id", "actor_type", "bypass_mode"},
            surface="branch-ownership.ruleset.bypass",
        )
        if bypass_actor != {
            "actor_id": publisher["app_id"],
            "actor_type": "Integration",
            "bypass_mode": "always",
        }:
            raise _fail(
                "branch-ownership.ruleset",
                "publication App is not the sole always-bypass actor",
            )
        source_rules = ruleset_raw["rules"]
        if not isinstance(source_rules, list) or len(source_rules) != len(REQUIRED_RULES):
            raise _fail(
                "branch-ownership.ruleset",
                "ownership ruleset is not a dedicated closed rule set",
            )
        source_signatures = tuple(sorted(
            _rule_signature(value, f"branch-ownership.ruleset.rules[{index}]")
            for index, value in enumerate(source_rules)
        ))
        if tuple(value[0] for value in source_signatures) != REQUIRED_RULES:
            raise _fail(
                "branch-ownership.ruleset",
                "ownership ruleset is missing a restricted ref operation",
            )

        if (
            not isinstance(effective_rules, PageResponse)
            or not effective_rules.complete
            or effective_rules.truncated
            or effective_rules.total_count != len(effective_rules.items)
            or effective_rules.pages != len(effective_rules.audits)
            or effective_rules.pages < 1
            or effective_rules.last_cursor is not None
        ):
            raise _fail(
                "branch-ownership.effective-rules",
                "effective branch rules are incomplete",
            )
        effective_signatures = []
        for index, value in enumerate(effective_rules.items):
            raw = _closed(
                value,
                required={
                    "type", "ruleset_source_type", "ruleset_source", "ruleset_id",
                },
                optional={"parameters"},
                surface=f"branch-ownership.effective-rules[{index}]",
            )
            if raw["ruleset_id"] != ruleset_id:
                continue
            if (
                raw["ruleset_source_type"] != "Repository"
                or raw["ruleset_source"] != expected_source
            ):
                raise _fail(
                    "branch-ownership.effective-rules",
                    "effective ownership rule source differs",
                )
            effective_signatures.append(_rule_signature(
                {key: raw[key] for key in ("type", "parameters") if key in raw},
                f"branch-ownership.effective-rules[{index}]",
            ))
        if tuple(sorted(effective_signatures)) != source_signatures:
            raise _fail(
                "branch-ownership.effective-rules",
                "dedicated ownership rules are not all active for the branch",
            )

        ref_raw = _closed(
            branch_ref.data,
            required={"ref", "node_id", "url", "object"},
            surface="branch-ownership.ref",
        )
        ref_object = _closed(
            ref_raw["object"],
            required={"type", "sha", "url"},
            surface="branch-ownership.ref.object",
        )
        if (
            ref_raw["ref"] != f"refs/heads/{controller_pusher.head_ref}"
            or ref_object["type"] != "commit"
            or ref_object["sha"] != controller_pusher.head_sha
        ):
            raise _fail(
                "branch-ownership.ref",
                "controller branch no longer points to the published commit",
            )

        expected_targets = (
            f"{repository_path}/rulesets/{ruleset_id}",
            f"{repository_path}/rules/branches/{controller_pusher.head_ref}",
            f"{repository_path}/git/ref/heads/{controller_pusher.head_ref}",
        )
        ordered_audits: list[RequestAudit] = []
        rule_audit, rule_time = _audit(
            ruleset.audit, surface="branch-ownership.ruleset",
            target=expected_targets[0],
        )
        ordered_audits.append(rule_audit)
        if not (
            _time(ruleset_raw["created_at"], "branch-ownership.ruleset")
            <= _time(ruleset_raw["updated_at"], "branch-ownership.ruleset")
            <= rule_time
        ):
            raise _fail(
                "branch-ownership.ruleset",
                "ruleset timestamps are malformed or from the future",
            )
        effective_times = []
        for value in effective_rules.audits:
            checked, checked_time = _audit(
                value, surface="branch-ownership.effective-rules",
                target=expected_targets[1],
            )
            ordered_audits.append(checked)
            effective_times.append(checked_time)
        ref_audit, ref_time = _audit(
            branch_ref.audit, surface="branch-ownership.ref",
            target=expected_targets[2],
        )
        ordered_audits.append(ref_audit)
        request_ids = [value.request_id for value in ordered_audits]
        if len(request_ids) != len(set(request_ids)):
            raise _fail("branch-ownership", "branch ownership request id was reused")
        evidence_completed = _time(evidence_completed_at, "branch-ownership")
        observed = _time(observed_at, "branch-ownership")
        completed = _time(completed_at, "branch-ownership")
        if (
            not evidence_completed <= observed == rule_time
            or not rule_time <= min(effective_times)
            or max(effective_times) > ref_time
            or ref_time != completed
            or completed < observed
        ):
            raise _fail(
                "branch-ownership",
                "branch ownership requests are stale or out of order",
            )

        document = {
            "schema_version": 1,
            "ownership_id": ownership_id,
            "source": "github-active-controller-branch-rules",
            "publication_receipt_id": controller_pusher.publication_receipt_id,
            "publication_receipt_sha256": controller_pusher.publication_receipt_sha256,
            "publication_credential_receipt_id": publisher[
                "credential_receipt_id"
            ],
            "publication_credential_receipt_sha256": publisher["receipt_sha256"],
            "repository": {
                "id": controller_pusher.repository_id,
                "node_id": controller_pusher.repository_node_id,
                "owner": controller_pusher.repository_owner,
                "name": controller_pusher.repository_name,
            },
            "head_ref": controller_pusher.head_ref,
            "head_sha": controller_pusher.head_sha,
            "publisher": {
                "app_id": publisher["app_id"],
                "app_node_id": publisher["app_node_id"],
                "actor_id": publisher["actor_id"],
                "actor_node_id": publisher["actor_node_id"],
                "login": publisher["login"],
            },
            "ruleset": {
                "id": ruleset_id,
                "node_id": ruleset_raw["node_id"],
                "source_type": "Repository",
                "source": expected_source,
                "updated_at": ruleset_raw["updated_at"],
                "bypass_mode": "always",
                "required_rules": list(REQUIRED_RULES),
            },
            "observation": {
                "evidence_completed_at": evidence_completed_at,
                "observed_at": observed_at,
                "completed_at": completed_at,
                "request_ids": request_ids,
                "request_ids_sha256": canonical_sha256(request_ids),
            },
            "ownership_sha256": "0" * 64,
        }
        document["ownership_sha256"] = canonical_sha256(
            document, "ownership_sha256"
        )
        cls.validate_document(document)
        return document
