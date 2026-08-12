from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from .errors import PolicyError, StateError
from .merge_bypass import (
    AMBIGUOUS_MEMBERSHIP_TYPES,
    bypass_actor_type,
    bypass_membership_assessment,
    bypass_membership_endpoint,
    bypass_membership_key,
    bypass_membership_status,
    ruleset_bypass_actor_identity,
)
from .merge_diff import derive_special_files, object_evidence_sha256
from .merge_policy_freshness import compare_complete_reread, evaluate_snapshot_window
from .merge_policy_proofs import evaluate_checks, evaluate_reviews
from .merge_policy_types import (
    CheckRequirement,
    DenyCode,
    EligibilityBlock,
    EligibilityOutcome,
    MergeEligibilityVerdict,
    MergeReadinessEvaluation,
    MergeReadinessProof,
    UNKNOWN_CODES,
    UNSUPPORTED_CODES,
)
from .protected_surfaces import ProtectedSurfaceRegistry


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas" / "publication"
SHIPPED_DIFF_LIMITS = {
    "max_changed_files": 25,
    "max_total_line_changes": 1000,
    "max_single_file_line_changes": 500,
    "max_patch_bytes": 262144,
}
CONTROLLER_BRANCH = re.compile(r"^pathfinder/auto/[a-z0-9][a-z0-9-]{0,62}$")
REQUIRED_EVIDENCE_SURFACES = frozenset({
    "repository", "actor", "pull-request", "refs", "changed-files",
    "classic-protection", "active-rules", "source-rulesets", "bypass-actors",
    "reviews", "review-requests", "review-threads", "check-runs",
    "commit-statuses", "deployments", "merged-state",
})


class _Blocks:
    def __init__(self):
        self._items: list[EligibilityBlock] = []
        self._seen: set[tuple[DenyCode, str, str]] = set()

    def add(self, code: DenyCode, surface: str, detail: str) -> None:
        key = (code, surface, detail)
        if key not in self._seen:
            self._seen.add(key)
            self._items.append(EligibilityBlock(code, surface, detail))

    @property
    def items(self) -> tuple[EligibilityBlock, ...]:
        return tuple(sorted(
            self._items,
            key=lambda item: (item.code.value, item.surface, item.detail),
        ))


def canonical_sha256(document: object, hash_field: str | None = None) -> str:
    payload = document
    if hash_field is not None:
        payload = {key: value for key, value in document.items() if key != hash_field}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_ROOT / f"merge-{name}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


VALIDATORS = {name: _validator(name) for name in ("policy", "authorization", "evidence")}
READINESS_VALIDATOR = _validator("readiness-proof")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed


def _matches(path: str, pattern: str) -> bool:
    path_parts = tuple(path.split("/"))
    pattern_parts = tuple(pattern.split("/"))

    @lru_cache(maxsize=None)
    def walk(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        part = pattern_parts[pattern_index]
        if part == "**":
            return walk(pattern_index + 1, path_index) or (
                path_index < len(path_parts) and walk(pattern_index, path_index + 1)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], part)
            and walk(pattern_index + 1, path_index + 1)
        )

    return walk(0, 0)


def _requirements(raw: Sequence[Mapping[str, object]]) -> set[CheckRequirement]:
    return {CheckRequirement(str(item["context"]), int(item["app_id"])) for item in raw}


def _outcome(blocks: tuple[EligibilityBlock, ...]) -> EligibilityOutcome:
    codes = {block.code for block in blocks}
    if codes & UNKNOWN_CODES:
        return EligibilityOutcome.UNKNOWN
    if codes & UNSUPPORTED_CODES:
        return EligibilityOutcome.UNSUPPORTED
    return EligibilityOutcome.POLICY_BLOCKED if blocks else EligibilityOutcome.ELIGIBLE


class MergePolicyEvaluator:
    """Pure, additive conditional-merge policy evaluator with no network or mutation access."""

    def evaluate(
        self,
        policy: Mapping[str, object] | None,
        authorization: Mapping[str, object] | None,
        protected_policy: Mapping[str, object] | None,
        evidence: Mapping[str, object] | None,
        *,
        now: datetime,
    ) -> MergeEligibilityVerdict:
        blocks = _Blocks()
        missing = (
            (policy, DenyCode.POLICY_MISSING, "policy"),
            (authorization, DenyCode.AUTHORIZATION_MISSING, "authorization"),
            (
                protected_policy,
                DenyCode.PROTECTED_POLICY_MISSING,
                "protected_policy",
            ),
            (evidence, DenyCode.EVIDENCE_MISSING, "evidence"),
        )
        for document, code, surface in missing:
            if document is None:
                blocks.add(code, surface, f"{surface} input is required")
        if blocks.items:
            return self._verdict(blocks, policy, authorization, evidence)
        if not isinstance(now, datetime) or now.utcoffset() is None:
            blocks.add(DenyCode.INPUT_INVALID, "clock", "evaluation time requires a UTC offset")
            return self._verdict(blocks, policy, authorization, evidence)

        documents = {"policy": policy, "authorization": authorization, "evidence": evidence}
        for name, document in documents.items():
            error = next(VALIDATORS[name].iter_errors(document), None)
            if error is not None:
                blocks.add(DenyCode.INPUT_INVALID, name, f"{name} does not match its closed schema")
        if blocks.items:
            return self._verdict(blocks, policy, authorization, evidence)

        try:
            if not isinstance(protected_policy, dict):
                raise TypeError("protected policy must be an object")
            shipped_registry = ProtectedSurfaceRegistry.load()
            if protected_policy["mode"] == "baseline":
                if protected_policy != shipped_registry.to_document():
                    raise StateError(
                        "protected baseline differs from the shipped policy"
                    )
                protected_registry = shipped_registry
            else:
                protected_registry = ProtectedSurfaceRegistry(
                    shipped_registry.to_document(), protected_policy
                )
        except (KeyError, PolicyError, StateError, TypeError, ValueError):
            blocks.add(
                DenyCode.INPUT_INVALID,
                "protected_policy",
                "protected policy does not match its closed schema",
            )
            return self._verdict(blocks, policy, authorization, evidence)

        self._authority(
            policy, authorization, protected_registry, evidence, now, blocks
        )
        self._evidence_integrity(policy, evidence, now, blocks)
        self._candidate(policy, authorization, protected_registry, evidence, blocks)
        required_approvals, required_checks, enforced_checks = self._rules(
            policy, evidence, blocks
        )
        approval_actor_ids = evaluate_reviews(
            policy, authorization, evidence, required_approvals, blocks
        )
        evaluate_checks(evidence, required_checks, enforced_checks, blocks)
        return self._verdict(
            blocks, policy, authorization, evidence,
            required_approvals=required_approvals,
            approval_actor_ids=approval_actor_ids,
            required_checks=required_checks,
        )

    def evaluate_reread(
        self,
        policy: Mapping[str, object] | None,
        authorization: Mapping[str, object] | None,
        protected_policy: Mapping[str, object] | None,
        initial_evidence: Mapping[str, object] | None,
        reread_evidence: Mapping[str, object] | None,
        *,
        now: datetime,
    ) -> MergeReadinessEvaluation:
        """Evaluate two complete observations and reject all intervening drift."""
        initial = self.evaluate(
            policy, authorization, protected_policy, initial_evidence, now=now
        )
        reread = self.evaluate(
            policy, authorization, protected_policy, reread_evidence, now=now
        )
        blocks = _Blocks()
        for block in (*initial.blocks, *reread.blocks):
            blocks.add(block.code, block.surface, block.detail)
        if reread_evidence is None:
            blocks.add(DenyCode.EVIDENCE_MISSING, "reread", "complete reread is required")
        elif (
            initial_evidence is not None
            and next(VALIDATORS["evidence"].iter_errors(initial_evidence), None) is None
            and next(VALIDATORS["evidence"].iter_errors(reread_evidence), None) is None
        ):
            compare_complete_reread(initial_evidence, reread_evidence, blocks)
        verdict = self._verdict(
            blocks,
            policy,
            authorization,
            reread_evidence,
            required_approvals=reread.required_approvals,
            approval_actor_ids=reread.approval_actor_ids,
            required_checks=set(reread.required_checks),
        )
        if (
            not verdict.eligible
            or policy is None
            or authorization is None
            or initial_evidence is None
            or reread_evidence is None
        ):
            return MergeReadinessEvaluation(verdict, None)
        proof = MergeReadinessProof.build(
            policy, authorization, initial_evidence, reread_evidence
        )
        if next(READINESS_VALIDATOR.iter_errors(proof.to_document()), None) is not None:
            blocks.add(
                DenyCode.INPUT_INVALID,
                "readiness_proof",
                "generated readiness proof does not match its closed schema",
            )
            verdict = self._verdict(
                blocks,
                policy,
                authorization,
                reread_evidence,
                required_approvals=reread.required_approvals,
                approval_actor_ids=reread.approval_actor_ids,
                required_checks=set(reread.required_checks),
            )
            return MergeReadinessEvaluation(verdict, None)
        return MergeReadinessEvaluation(verdict, proof)

    @staticmethod
    def _verdict(
        blocks: _Blocks,
        policy: Mapping[str, object] | None,
        authorization: Mapping[str, object] | None,
        evidence: Mapping[str, object] | None,
        *,
        required_approvals: int = 0,
        approval_actor_ids: tuple[int, ...] = (),
        required_checks: set[CheckRequirement] | None = None,
    ) -> MergeEligibilityVerdict:
        items = blocks.items
        return MergeEligibilityVerdict(
            _outcome(items), items, required_approvals, approval_actor_ids,
            tuple(sorted(required_checks or ())),
            policy.get("policy_sha256") if isinstance(policy, Mapping) else None,
            authorization.get("authorization_sha256")
            if isinstance(authorization, Mapping) else None,
            evidence.get("evidence_sha256") if isinstance(evidence, Mapping) else None,
        )

    @staticmethod
    def _authority(
        policy, authorization, protected_registry, evidence, now, blocks: _Blocks
    ) -> None:
        for document, field, surface in (
            (policy, "policy_sha256", "policy"),
            (authorization, "authorization_sha256", "authorization"),
            (evidence, "evidence_sha256", "evidence"),
        ):
            if document[field] != canonical_sha256(document, field):
                blocks.add(DenyCode.IDENTITY_DRIFT, surface, f"{surface} hash does not match")
        for document, code, surface in (
            (policy, DenyCode.POLICY_EXPIRED, "policy"),
            (authorization, DenyCode.AUTHORIZATION_EXPIRED, "authorization"),
        ):
            try:
                current = _time(document["issued_at"]) <= now < _time(document["expires_at"])
            except (TypeError, ValueError):
                current = False
            if not current:
                blocks.add(code, surface, f"{surface} validity window is not current")
        try:
            timeline_current = (
                _time(policy["issued_at"])
                <= _time(policy["workflow_side_effects"]["acknowledged_at"])
                <= _time(authorization["issued_at"])
                <= _time(evidence["observation"]["observed_at"])
            )
        except (TypeError, ValueError):
            timeline_current = False
        if not timeline_current:
            blocks.add(DenyCode.IDENTITY_DRIFT, "authority.timeline", "authority and evidence timeline differs")

        if authorization["policy"] != {
            "policy_id": policy["policy_id"], "policy_sha256": policy["policy_sha256"],
        }:
            blocks.add(DenyCode.IDENTITY_DRIFT, "authorization.policy", "policy binding differs")
        policy_read = evidence["observation"]["policy_read"]
        if (
            policy_read["policy_id"] != policy["policy_id"]
            or policy_read["policy_sha256"] != policy["policy_sha256"]
        ):
            blocks.add(
                DenyCode.IDENTITY_DRIFT,
                "observation.policy_read",
                "host policy reread differs from the evaluated policy",
            )
        if authorization["repository"] != policy["repository"]:
            blocks.add(DenyCode.IDENTITY_DRIFT, "authorization.repository", "repository binding differs")
        if authorization["merge_method"] != policy["merge_method"]:
            blocks.add(DenyCode.UNSUPPORTED_MERGE_METHOD, "authorization", "merge method differs")
        if protected_registry.sha256 != policy["path_policy"]["protected_policy_sha256"]:
            blocks.add(
                DenyCode.IDENTITY_DRIFT,
                "protected_policy",
                "effective protected policy hash differs",
            )

        expected_bindings = {
            "policy_id": policy["policy_id"],
            "policy_sha256": policy["policy_sha256"],
            "merge_authorization_id": authorization["merge_authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
            "mission_id": authorization["mission"]["mission_id"],
            "binding_id": authorization["mission"]["binding_id"],
            "mission_authorization_id": authorization["mission"]["mission_authorization_id"],
            "protected_policy_sha256": policy["path_policy"]["protected_policy_sha256"],
        }
        if evidence["bindings"] != expected_bindings:
            blocks.add(DenyCode.IDENTITY_DRIFT, "evidence.bindings", "authority binding differs")
        repository_keys = ("id", "node_id", "owner", "name", "base_branch")
        observed_repository = {key: evidence["repository"][key] for key in repository_keys}
        if observed_repository != policy["repository"]:
            blocks.add(DenyCode.IDENTITY_DRIFT, "evidence.repository", "repository identity differs")

    @staticmethod
    def _evidence_integrity(policy, evidence, now, blocks: _Blocks) -> None:
        observation = evidence["observation"]
        evaluate_snapshot_window(policy, evidence, now, blocks)
        try:
            observed = _time(observation["observed_at"])
            completed = _time(observation["completed_at"])
            policy_read = _time(observation["policy_read"]["observed_at"])
            audits_current = all(
                observed <= _time(item["observed_at"]) <= completed
                for item in observation["requests"]
            ) and observed <= policy_read <= completed
        except (TypeError, ValueError):
            audits_current = False
        if not audits_current:
            blocks.add(DenyCode.EVIDENCE_EXPIRED, "observation.requests", "request audit is outside the snapshot window")
        request_ids = [item["request_id"] for item in observation["requests"]]
        if observation["request_ids_sha256"] != canonical_sha256(request_ids):
            blocks.add(DenyCode.IDENTITY_DRIFT, "observation.requests", "request audit hash differs")
        request_surfaces = {item["surface"] for item in observation["requests"]}
        if (
            not REQUIRED_EVIDENCE_SURFACES <= request_surfaces
            or len(request_ids) != len(set(request_ids))
        ):
            blocks.add(DenyCode.FIELD_UNKNOWN, "observation.requests", "required request audit is missing or ambiguous")
        if observation["unknown_payloads_sha256"] is not None:
            blocks.add(DenyCode.FIELD_UNKNOWN, "observation", "unknown response payload was observed")
        if not observation["collection_complete"]:
            blocks.add(DenyCode.FIELD_UNKNOWN, "observation", "evidence collection is incomplete")

        unknown_map = {
            code.value: code for code in UNKNOWN_CODES
            if code.value not in {"policy-missing", "authorization-missing", "evidence-missing"}
        }
        for reason in evidence["unknown_reasons"]:
            blocks.add(unknown_map.get(reason, DenyCode.FIELD_UNKNOWN), "evidence", reason)
        unsupported_map = {code.value: code for code in UNSUPPORTED_CODES}
        for reason in evidence["unsupported_reasons"]:
            blocks.add(unsupported_map.get(reason, DenyCode.UNSUPPORTED_ACTIVE_RULE), "evidence", reason)

        pages = evidence["pagination"]
        for name, page in pages.items():
            if not page["complete"] or page["truncated"] or page["last_cursor"] is not None:
                blocks.add(DenyCode.PAGINATION_INCOMPLETE, f"pagination.{name}", "page is incomplete")
        expected_counts = {
            "pull_files": len(evidence["diff"]["changed_files"]),
            "active_rules": len(evidence["active_rules"]),
            "source_rulesets": len(evidence["source_rulesets"]),
            "bypass_actors": sum(
                len(item["bypass_actor_keys"]) for item in evidence["source_rulesets"]
            ),
            "bypass_memberships": len(evidence["bypass_memberships"]),
            "reviews": len(evidence["reviews"]),
            "review_requests": len(evidence["review_requests"]),
            "review_threads": len(evidence["review_threads"]),
            "check_runs": sum(item["source"] == "check-run" for item in evidence["checks"]),
            "commit_statuses": sum(item["source"] == "commit-status" for item in evidence["checks"]),
        }
        for name, count in expected_counts.items():
            if pages[name]["items"] != count:
                blocks.add(DenyCode.PAGINATION_INCOMPLETE, f"pagination.{name}", "item count differs")

    @staticmethod
    def _candidate(
        policy, authorization, protected_registry, evidence, blocks: _Blocks
    ) -> None:
        repository = evidence["repository"]
        pull = evidence["pull_request"]
        mergeability = evidence["mergeability"]
        if repository["archived"] or repository["disabled"]:
            blocks.add(DenyCode.REPOSITORY_UNAVAILABLE, "repository", "repository is archived or disabled")
        if not repository["merge_methods"]["squash"] or policy["merge_method"] != "squash":
            blocks.add(DenyCode.UNSUPPORTED_MERGE_METHOD, "repository", "squash is not available")
        if pull["state"] != "open":
            blocks.add(DenyCode.PULL_REQUEST_NOT_OPEN, "pull_request.state", "pull request is not open")
        if pull["draft"]:
            blocks.add(DenyCode.DRAFT, "pull_request.draft", "pull request is a draft")
        repository_id = repository["id"]
        repository_node_id = repository["node_id"]
        if not pull["same_repository"] or any(
            pull[key] != expected for key, expected in (
                ("head_repository_id", repository_id),
                ("base_repository_id", repository_id),
                ("head_repository_node_id", repository_node_id),
                ("base_repository_node_id", repository_node_id),
            )
        ):
            blocks.add(DenyCode.FORK, "pull_request.repository", "head and base are not the bound repository")
        if pull["base_ref"] != repository["base_branch"]:
            blocks.add(DenyCode.IDENTITY_DRIFT, "pull_request.base_ref", "base branch differs")
        if not CONTROLLER_BRANCH.fullmatch(pull["head_ref"]):
            blocks.add(DenyCode.CONTROLLER_BRANCH_UNPROVEN, "pull_request.head_ref", "head is not a controller branch")
        candidate = authorization["candidate"]
        expected_pull = candidate["pull_request"]
        observed_pull = {
            key: pull[key]
            for key in (
                "id", "node_id", "number", "head_ref", "head_sha", "base_ref",
                "base_sha",
            )
        }
        if observed_pull != expected_pull:
            blocks.add(
                DenyCode.IDENTITY_DRIFT,
                "pull_request.controller_candidate",
                "pull request differs from the authenticated controller candidate",
            )
        observed_diff = {
            "diff_sha256": evidence["diff"]["diff_sha256"],
            "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
            "object_evidence_sha256": evidence["diff"]["object_evidence"][
                "files_sha256"
            ],
        }
        if candidate["diff"] != observed_diff:
            blocks.add(
                DenyCode.DIFF_DRIFT,
                "diff.controller_candidate",
                "diff differs from the authenticated controller candidate",
            )
        if any(pull[key] is not None for key in ("merge_commit_sha", "merged_at", "merged_by")):
            blocks.add(DenyCode.IDENTITY_DRIFT, "pull_request", "open pull request contains merge proof")
        if mergeability["required_sha"] != pull["head_sha"]:
            blocks.add(DenyCode.CHECK_SHA_DRIFT, "mergeability.required_sha", "required SHA differs from head")
        if mergeability["queue_entry"]:
            blocks.add(DenyCode.MERGE_QUEUE_REQUIRED, "mergeability.queue_entry", "pull request is queued")
        if mergeability["mergeable"] == "CONFLICTING" or mergeability["merge_state_status"] == "DIRTY":
            blocks.add(DenyCode.MERGE_CONFLICT, "mergeability", "pull request conflicts")
        elif mergeability["mergeable"] != "MERGEABLE":
            blocks.add(DenyCode.MERGE_STATE_UNKNOWN, "mergeability.mergeable", "mergeability is unknown")
        if mergeability["merge_state_status"] == "BEHIND":
            blocks.add(DenyCode.BASE_BEHIND, "mergeability.merge_state_status", "base branch is ahead")
        elif mergeability["merge_state_status"] != "CLEAN":
            blocks.add(DenyCode.MERGE_STATE_UNKNOWN, "mergeability.merge_state_status", "merge state is not clean")
        MergePolicyEvaluator._diff(
            policy, protected_registry, evidence["diff"], blocks
        )

    @staticmethod
    def _diff(policy, protected_registry, diff, blocks: _Blocks) -> None:
        files = diff["changed_files"]
        if diff["object_evidence"]["files_sha256"] != object_evidence_sha256(files):
            blocks.add(
                DenyCode.DIFF_DRIFT,
                "diff.object_evidence",
                "controller Git object evidence hash differs",
            )
        if diff["changed_files_sha256"] != canonical_sha256(files):
            blocks.add(DenyCode.DIFF_DRIFT, "diff.changed_files", "changed-file hash differs")
        if diff["diff_sha256"] != canonical_sha256(diff, "diff_sha256"):
            blocks.add(DenyCode.DIFF_DRIFT, "diff", "diff hash differs")
        paths = [item["path"] for item in files]
        if (
            not files or paths != sorted(paths) or len(paths) != len(set(paths))
            or diff["changed_file_count"] != len(files)
            or diff["total_line_changes"] != sum(item["changes"] for item in files)
            or any(item["changes"] != item["additions"] + item["deletions"] for item in files)
            or any(item["status"] == "unchanged" for item in files)
        ):
            blocks.add(DenyCode.DIFF_DRIFT, "diff", "diff totals or ordering differ")
        claimed_categories = {
            value for item in files for value in item["protected_categories"]
        }
        derived_categories: set[str] = set()
        for item in files:
            item_paths = tuple(
                path for path in (item["path"], item["previous_path"])
                if path is not None
            )
            try:
                classified = protected_registry.classify(item_paths)
            except PolicyError:
                blocks.add(
                    DenyCode.DIFF_DRIFT,
                    "diff.changed_files",
                    "changed path cannot be classified by the protected policy",
                )
                continue
            expected = sorted({
                category
                for values in classified.values()
                for category in values
            })
            derived_categories.update(expected)
            if item["protected_categories"] != expected:
                blocks.add(
                    DenyCode.DIFF_DRIFT,
                    item["path"],
                    "protected classification differs from the effective registry",
                )
        categories = sorted(claimed_categories | derived_categories)
        claimed_special = {value for item in files for value in item["special_files"]}
        derived_special: set[str] = set()
        for item in files:
            expected_special = list(derive_special_files(item))
            derived_special.update(expected_special)
            if item["special_files"] != expected_special:
                blocks.add(
                    DenyCode.DIFF_DRIFT,
                    item["path"],
                    "special-file classification differs from controller Git evidence",
                )
        special = sorted(claimed_special | derived_special)
        if (
            sorted(claimed_categories) != diff["protected_categories"]
            or sorted(claimed_special) != diff["special_files"]
        ):
            blocks.add(DenyCode.DIFF_DRIFT, "diff", "protected classifications differ")
        if categories or special:
            blocks.add(DenyCode.PROTECTED_SURFACE, "diff", "diff touches a protected or special surface")
        denied_categories = set(policy["path_policy"]["additional_denied_categories"])
        if denied_categories & set(categories):
            blocks.add(DenyCode.PROTECTED_SURFACE, "diff.protected_categories", "host-denied category is present")

        allowed = policy["path_policy"]["allowed_paths"]
        denied = policy["path_policy"]["additional_denied_paths"]
        for item in files:
            for path in (item["path"], item["previous_path"]):
                if path is None:
                    continue
                if not any(_matches(path, pattern) for pattern in allowed):
                    blocks.add(DenyCode.PATH_NOT_ALLOWED, path, "path is outside the host allowlist")
                if any(_matches(path, pattern) for pattern in denied):
                    blocks.add(DenyCode.PATH_DENIED, path, "path matches a host deny pattern")
        limits = {
            key: min(policy["diff_limits"][key], shipped)
            for key, shipped in SHIPPED_DIFF_LIMITS.items()
        }
        if (
            len(files) > limits["max_changed_files"]
            or diff["total_line_changes"] > limits["max_total_line_changes"]
            or diff["patch_bytes"] > limits["max_patch_bytes"]
            or any(item["changes"] > limits["max_single_file_line_changes"] for item in files)
        ):
            blocks.add(DenyCode.DIFF_LIMIT_EXCEEDED, "diff", "effective diff ceiling is exceeded")

    @staticmethod
    def _rules(policy, evidence, blocks: _Blocks):
        classic = evidence["classic_protection"]
        active = evidence["active_rules"]
        sources = {item["id"]: item for item in evidence["source_rulesets"]}
        active_ids = {item["ruleset_id"] for item in active}
        rule_keys = [(item["ruleset_id"], item["rule_type"]) for item in active]
        if (
            set(sources) != active_ids
            or len(sources) != len(evidence["source_rulesets"])
            or len(rule_keys) != len(set(rule_keys))
        ):
            blocks.add(DenyCode.RULESET_DRIFT, "source_rulesets", "source and aggregate ruleset ids differ")
        unsupported = {
            "merge_queue": DenyCode.MERGE_QUEUE_REQUIRED,
            "required_deployments": DenyCode.UNSUPPORTED_REQUIRED_DEPLOYMENTS,
            "required_signatures": DenyCode.UNSUPPORTED_REQUIRED_SIGNATURES,
            "code_scanning": DenyCode.UNSUPPORTED_CODE_SCANNING,
            "code_quality": DenyCode.UNSUPPORTED_CODE_QUALITY,
            "file_path_restriction": DenyCode.UNSUPPORTED_FILE_RESTRICTION,
            "max_file_size": DenyCode.UNSUPPORTED_METADATA_RESTRICTION,
        }
        approvals = [1, policy["review_requirements"]["independent_approval_floor"]]
        required_checks = _requirements(policy["review_requirements"]["required_checks"])
        enforced_checks: set[CheckRequirement] = set()
        review_enforced = False

        if classic["status"] == "unknown":
            blocks.add(DenyCode.CLASSIC_PROTECTION_UNKNOWN, "classic_protection", "classic protection is unknown")
        elif classic["status"] == "present":
            semantic_values = (
                classic["settings_sha256"], classic["required_review_count"],
                classic["enforce_admins"], classic["conversation_resolution_required"],
                classic["last_push_approval_required"],
                classic["dismiss_stale_reviews"],
                classic["code_owner_review_required"],
                classic["required_linear_history"],
                classic["required_signatures"],
                classic["restrictions_present"],
                classic["dismissal_restrictions_present"],
            )
            if any(value is None for value in semantic_values):
                blocks.add(DenyCode.CLASSIC_PROTECTION_UNKNOWN, "classic_protection", "classic settings are incomplete")
            else:
                approvals.append(classic["required_review_count"])
                review_enforced = classic["required_review_count"] >= 1
                if classic["required_signatures"]:
                    blocks.add(
                        DenyCode.UNSUPPORTED_REQUIRED_SIGNATURES,
                        "classic_protection.required_signatures",
                        "classic protection requires signed commits",
                    )
                for field, detail in (
                    (
                        "code_owner_review_required",
                        "classic code-owner approval cannot be attributed",
                    ),
                    (
                        "restrictions_present",
                        "classic push restrictions are active",
                    ),
                    (
                        "dismissal_restrictions_present",
                        "classic review-dismissal restrictions are active",
                    ),
                ):
                    if classic[field]:
                        blocks.add(
                            DenyCode.UNSUPPORTED_ACTIVE_RULE,
                            f"classic_protection.{field}",
                            detail,
                        )
            enforced_checks |= _requirements(classic["required_checks"])
            required_checks |= enforced_checks
            if classic["bypass_visibility"] != "complete":
                blocks.add(DenyCode.BYPASS_VISIBILITY_UNKNOWN, "classic_protection", "classic bypass visibility is incomplete")
        elif (
            classic["settings_sha256"] is not None
            or classic["required_review_count"] is not None
            or classic["required_checks"]
            or classic["bypass_visibility"] != "not-applicable"
            or classic["bypass_actor_keys"]
            or classic["bypass_actor_metadata"]
            or any(classic[key] is not None for key in (
                "enforce_admins", "conversation_resolution_required",
                "last_push_approval_required", "dismiss_stale_reviews",
                "code_owner_review_required", "required_linear_history",
                "required_signatures", "restrictions_present",
                "dismissal_restrictions_present",
            ))
        ):
            blocks.add(DenyCode.CLASSIC_PROTECTION_UNKNOWN, "classic_protection", "absent protection has settings")

        for rule in active:
            source = sources.get(rule["ruleset_id"])
            if source is None or any(
                source[key] != rule[key] for key in ("source_type", "source_id")
            ) or source["enforcement"] != "active":
                blocks.add(DenyCode.RULESET_DRIFT, f"active_rules.{rule['ruleset_id']}", "rule source differs")
            rule_type = rule["rule_type"]
            if rule_type in unsupported:
                blocks.add(unsupported[rule_type], f"active_rules.{rule['ruleset_id']}", rule_type)
            elif rule_type == "pull_request":
                if (
                    rule["approval_count"] is None or not rule["allowed_merge_methods"]
                    or rule["required_checks"] or rule["strict"] is not None
                    or rule["code_owner_review_required"] is None
                ):
                    blocks.add(DenyCode.RULESET_DRIFT, f"active_rules.{rule['ruleset_id']}", "pull-request parameters differ")
                else:
                    approvals.append(rule["approval_count"])
                    review_enforced = review_enforced or rule["approval_count"] >= 1
                if rule["code_owner_review_required"]:
                    blocks.add(
                        DenyCode.UNSUPPORTED_ACTIVE_RULE,
                        f"active_rules.{rule['ruleset_id']}.code_owner_review_required",
                        "ruleset code-owner approval cannot be attributed",
                    )
                if "squash" not in rule["allowed_merge_methods"]:
                    blocks.add(
                        DenyCode.UNSUPPORTED_MERGE_METHOD,
                        f"active_rules.{rule['ruleset_id']}",
                        "ruleset does not allow squash",
                    )
            elif rule_type == "required_status_checks":
                values = _requirements(rule["required_checks"])
                if (
                    rule["approval_count"] is not None or rule["allowed_merge_methods"]
                    or not values or rule["strict"] is None
                    or rule["code_owner_review_required"] is not None
                ):
                    blocks.add(DenyCode.RULESET_DRIFT, f"active_rules.{rule['ruleset_id']}", "check parameters differ")
                enforced_checks |= values
                required_checks |= values
            elif rule_type == "required_linear_history":
                if (
                    rule["approval_count"] is not None or rule["allowed_merge_methods"]
                    or rule["required_checks"] or rule["strict"] is not None
                    or rule["code_owner_review_required"] is not None
                ):
                    blocks.add(DenyCode.RULESET_DRIFT, f"active_rules.{rule['ruleset_id']}", "linear-history parameters differ")
            else:
                blocks.add(DenyCode.UNSUPPORTED_ACTIVE_RULE, f"active_rules.{rule['ruleset_id']}", rule_type)

        for source in evidence["source_rulesets"]:
            signature = [
                {
                    "rule_type": rule["rule_type"],
                    "parameters_sha256": rule["parameters_sha256"],
                }
                for rule in active if rule["ruleset_id"] == source["id"]
            ]
            signature.sort(key=lambda item: item["rule_type"])
            if source["active_rules_sha256"] != canonical_sha256(signature):
                blocks.add(
                    DenyCode.RULESET_DRIFT,
                    f"source_rulesets.{source['id']}",
                    "source and aggregate rule parameters differ",
                )
            if source["bypass_visibility"] != "complete":
                blocks.add(DenyCode.BYPASS_VISIBILITY_UNKNOWN, f"source_rulesets.{source['id']}", "ruleset bypass visibility is incomplete")
            try:
                if _time(source["updated_at"]) > _time(evidence["observation"]["completed_at"]):
                    blocks.add(DenyCode.RULESET_DRIFT, f"source_rulesets.{source['id']}", "ruleset update postdates observation")
            except (TypeError, ValueError):
                blocks.add(DenyCode.RULESET_DRIFT, f"source_rulesets.{source['id']}", "ruleset update time is invalid")
        if classic["status"] == "absent" and not active:
            blocks.add(DenyCode.POLICY_UNENFORCED, "protection", "GitHub enforces no merge policy")
        if not review_enforced:
            blocks.add(DenyCode.INDEPENDENT_REVIEW_NOT_ENFORCED, "reviews", "GitHub does not enforce a human approval")
        if not enforced_checks:
            blocks.add(DenyCode.REQUIRED_CHECK_UNPROVEN, "checks", "GitHub does not enforce a pinned check")

        actor = evidence["actor"]
        classic_metadata_keys = [
            item["key"] for item in classic["bypass_actor_metadata"]
        ]
        if (
            len(classic_metadata_keys) != len(set(classic_metadata_keys))
            or any(key not in classic["bypass_actor_keys"] for key in classic_metadata_keys)
        ):
            blocks.add(
                DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                "classic_protection.bypass_actor_metadata",
                "classic bypass metadata differs from actor keys",
            )
        for source in evidence["source_rulesets"]:
            metadata_keys = [
                item["key"] for item in source["bypass_actor_metadata"]
            ]
            if (
                len(metadata_keys) != len(set(metadata_keys))
                or any(key not in source["bypass_actor_keys"] for key in metadata_keys)
            ):
                blocks.add(
                    DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                    f"source_rulesets.{source['id']}.bypass_actor_metadata",
                    "ruleset bypass metadata differs from actor keys",
                )
        direct_bypass_keys = {
            key for key in classic["bypass_actor_keys"]
            if bypass_actor_type(key) not in AMBIGUOUS_MEMBERSHIP_TYPES
        }
        direct_bypass_keys.update(
            ruleset_bypass_actor_identity(key)
            for source in evidence["source_rulesets"]
            for key in source["bypass_actor_keys"]
            if bypass_actor_type(key) not in AMBIGUOUS_MEMBERSHIP_TYPES
        )
        expected_memberships = {
            ("classic-protection", None, key, None)
            for key in classic["bypass_actor_keys"]
            if bypass_actor_type(key) in AMBIGUOUS_MEMBERSHIP_TYPES
        }
        expected_memberships.update(
            (
                "ruleset", source["id"], ruleset_bypass_actor_identity(key),
                key.rsplit(":", 1)[1],
            )
            for source in evidence["source_rulesets"]
            for key in source["bypass_actor_keys"]
            if bypass_actor_type(key) in AMBIGUOUS_MEMBERSHIP_TYPES
        )
        source_names: dict[tuple[object, ...], list[object]] = {}
        for metadata in classic["bypass_actor_metadata"]:
            key = ("classic-protection", None, metadata["key"], None)
            if key in expected_memberships:
                source_names.setdefault(key, []).append(metadata["actor_name"])
        for source in evidence["source_rulesets"]:
            for metadata in source["bypass_actor_metadata"]:
                key = (
                    "ruleset", source["id"],
                    ruleset_bypass_actor_identity(metadata["key"]),
                    metadata["key"].rsplit(":", 1)[1],
                )
                if key in expected_memberships:
                    source_names.setdefault(key, []).append(metadata["actor_name"])
        seen_memberships = set()
        seen_membership_requests = set()
        membership_assessments = []
        membership_unknown = False
        membership_audits = {
            item["request_id"]: item for item in evidence["observation"]["requests"]
            if item["surface"] == "bypass-memberships"
        }
        for index, membership in enumerate(evidence["bypass_memberships"]):
            key = bypass_membership_key(membership)
            names = source_names.get(key, [])
            audit = membership_audits.get(membership["request_id"])
            if (
                membership["subject_actor_id"] != actor["actor_id"]
                or membership["subject_login"] != actor["login"]
                or (
                    membership["actor_type"]
                    in {"Team", "OrganizationAdmin"}
                    and membership["organization_login"]
                    != evidence["repository"]["owner"]
                )
                or key not in expected_memberships
                or key in seen_memberships
                or len(names) != 1
                or (
                    membership["actor_type"] == "Team"
                    and membership["team_slug"] != names[0]
                )
                or (
                    membership["actor_type"] == "RepositoryRole"
                    and membership["bypass_role_name"] != names[0]
                )
                or membership["request_id"] in seen_membership_requests
                or audit is None
                or (
                    audit is not None
                    and (
                        audit.get("target")
                        != bypass_membership_endpoint(
                            membership, evidence["repository"]
                        )
                        or audit.get("status") != bypass_membership_status(membership)
                        or audit.get("permission_qualified") is not True
                    )
                )
            ):
                membership_unknown = True
                blocks.add(
                    DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                    f"bypass_memberships.{index}",
                    "membership resolution identity or coverage differs",
                )
            seen_memberships.add(key)
            seen_membership_requests.add(membership["request_id"])
            membership_assessments.append(
                bypass_membership_assessment(membership)
            )
        if seen_memberships != expected_memberships:
            membership_unknown = True
            blocks.add(
                DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                "bypass_memberships",
                "membership resolution coverage is incomplete",
            )
        if seen_membership_requests != set(membership_audits):
            membership_unknown = True
            blocks.add(
                DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                "observation.requests",
                "membership request audits do not have exact resolution coverage",
            )
        if "unknown" in membership_assessments:
            membership_unknown = True
            blocks.add(
                DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                "bypass_memberships",
                "membership state is not authoritative",
            )
        membership_match = "match" in membership_assessments
        actor_keys = {f"Integration:{actor['app_id']}", f"User:{actor['actor_id']}"}
        direct_match = bool(actor_keys & direct_bypass_keys)
        if membership_unknown:
            derived_assessment = "unknown"
        elif membership_match or direct_match:
            derived_assessment = "match"
        else:
            derived_assessment = "no-match"
        if actor["bypass_assessment"] != derived_assessment:
            blocks.add(
                DenyCode.BYPASS_VISIBILITY_UNKNOWN,
                "actor.bypass_assessment",
                "actor bypass assessment differs from typed evidence",
            )
        if (
            membership_match or direct_match
            or actor["administration_permission"] != "none"
        ):
            blocks.add(DenyCode.MERGE_ACTOR_CAN_BYPASS, "actor", "merge actor may bypass policy")
        elif derived_assessment != "no-match":
            blocks.add(DenyCode.BYPASS_VISIBILITY_UNKNOWN, "actor", "actor bypass assessment is unknown")
        if actor["suspended"]:
            blocks.add(DenyCode.ACTOR_IDENTITY_UNKNOWN, "actor", "merge actor is suspended")
        return max(approvals), required_checks, enforced_checks
