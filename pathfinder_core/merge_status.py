from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker

from .errors import StateError
from .merge_policy import MergePolicyEvaluator
from .merge_policy_types import (
    DenyCode,
    EligibilityBlock,
    EligibilityOutcome,
    UNKNOWN_CODES,
    UNSUPPORTED_CODES,
)
from .protected_surfaces import ProtectedSurfaceRegistry
from .publication_journal import PUBLICATION_REQUEST_ID, PublicationJournal
from .storage import canonical_sha256, read_json


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas" / "publication"
INPUT_SCHEMAS = {
    "policy": "merge-policy.schema.json",
    "authorization": "merge-authorization.schema.json",
    "initial_evidence": "merge-evidence.schema.json",
    "reread_evidence": "merge-evidence.schema.json",
}


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        read_json(SCHEMA_ROOT / name), format_checker=FormatChecker()
    )


INPUT_VALIDATORS = {
    name: _validator(schema) for name, schema in INPUT_SCHEMAS.items()
}
INPUT_VALIDATORS["protected_policy"] = Draft202012Validator(
    read_json(ROOT / "schemas" / "policy" / "protected-surfaces.schema.json"),
    format_checker=FormatChecker(),
)
REPORT_VALIDATOR = _validator("merge-status-report.schema.json")


@dataclass(frozen=True)
class InstalledMergeInputs:
    receipt: dict
    policy: dict | None
    authorization: dict | None
    protected_policy: dict | None
    initial_evidence: dict | None
    reread_evidence: dict | None
    input_states: dict[str, str]


class InstalledHostMergeReader:
    """Reads status inputs from an operator-owned directory without credentials."""

    FILES = {
        "policy": "merge-policy.json",
        "authorization": "merge-authorization.json",
        "initial_evidence": "merge-evidence-initial.json",
        "reread_evidence": "merge-evidence-reread.json",
        "protected_policy": "protected-policy.json",
    }

    def __init__(self, repo_root: Path | str, host_root: Path | str):
        self.repo_root = Path(repo_root)
        self.host_root = Path(host_root)

    def _validate_root(self) -> None:
        if not self.repo_root.is_dir() or self.repo_root.is_symlink():
            raise StateError("repository root must be an existing non-symlink directory")
        if not self.host_root.is_dir() or self.host_root.is_symlink():
            raise StateError("installed host root must be an existing non-symlink directory")
        repository = self.repo_root.resolve()
        host = self.host_root.resolve()
        try:
            host.relative_to(repository)
        except ValueError:
            pass
        else:
            raise StateError("installed host root must be outside repository trust")
        if os.name != "nt":
            metadata = host.stat()
            if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
                raise StateError("installed host root must be owned by the current user")
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise StateError("installed host root must be owner-only")

    def _optional(self, name: str) -> tuple[dict | None, str]:
        path = self.host_root / self.FILES[name]
        if not path.exists():
            return None, "missing"
        if path.is_symlink() or not path.is_file():
            return {}, "invalid"
        try:
            document = read_json(path)
        except (StateError, UnicodeError):
            return {}, "invalid"
        validator = INPUT_VALIDATORS.get(name)
        if validator is not None and next(validator.iter_errors(document), None):
            return document, "invalid"
        return document, "present"

    def load(self, request_id: str) -> InstalledMergeInputs:
        self._validate_root()
        if PUBLICATION_REQUEST_ID.fullmatch(request_id) is None:
            raise StateError(f"invalid publication request id: {request_id}")
        journal_root = self.host_root / "journal"
        operations_root = journal_root / "publication-operations"
        for path, label in (
            (journal_root, "publication journal"),
            (operations_root, "publication operations"),
        ):
            if path.is_symlink() or not path.is_dir():
                raise StateError(f"{label} must be a regular non-symlink directory")
        for label in ("request", "dispatch", "receipt"):
            path = operations_root / f"{request_id}.{label}.json"
            if path.exists() and (path.is_symlink() or not path.is_file()):
                raise StateError(
                    f"publication {label} must be a regular non-symlink JSON file"
                )
        loaded = PublicationJournal(journal_root).load(request_id)
        receipt = loaded["receipt"]
        if receipt is None:
            raise StateError("exact awaiting-review publication receipt is required")

        values: dict[str, dict | None] = {}
        states: dict[str, str] = {}
        for name in ("policy", "authorization", "initial_evidence", "reread_evidence"):
            document, state = self._optional(name)
            values[name] = document
            states[name] = state

        protected, protected_state = self._optional("protected_policy")
        if protected_state == "missing":
            protected = ProtectedSurfaceRegistry.load().to_document()
            protected_state = "shipped-baseline"
        states["protected_policy"] = protected_state

        return InstalledMergeInputs(
            receipt,
            values["policy"],
            values["authorization"],
            protected,
            values["initial_evidence"],
            values["reread_evidence"],
            states,
        )


def _publication(receipt: Mapping[str, object]) -> dict:
    pull = receipt["pull_request"]
    repository = receipt["repository"]
    return {
        "publication_request_id": receipt["publication_request_id"],
        "publication_receipt_id": receipt["publication_receipt_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "repository": {
            key: repository[key] for key in ("id", "node_id", "owner", "name")
        },
        "pull_request": {
            key: pull[key]
            for key in (
                "id",
                "node_id",
                "number",
                "url",
                "head_ref",
                "head_sha",
                "base_ref",
                "base_sha",
            )
        },
    }


def _receipt_blocks(inputs: InstalledMergeInputs) -> tuple[EligibilityBlock, ...]:
    receipt = inputs.receipt
    blocks: list[EligibilityBlock] = []
    expected_candidate = {
        "source": "authenticated-controller-publication",
        "mission_state_sha256": receipt["mission"]["mission_state_sha256"],
        "publication_receipt_id": receipt["publication_receipt_id"],
        "pull_request": {
            key: receipt["pull_request"][key]
            for key in (
                "id", "node_id", "number", "head_ref", "head_sha",
                "base_ref", "base_sha",
            )
        },
        "diff": receipt["diff"],
    }
    if (
        inputs.input_states["authorization"] == "present"
        and inputs.authorization["candidate"] != expected_candidate
    ):
        blocks.append(EligibilityBlock(
            DenyCode.IDENTITY_DRIFT,
            "authorization.publication_receipt",
            "authorization candidate differs from the persisted publication receipt",
        ))

    expected_repository = {
        key: receipt["repository"][key]
        for key in ("id", "node_id", "owner", "name")
    }
    expected_pull = expected_candidate["pull_request"]
    expected_mission = {
        key: receipt["mission"][key]
        for key in ("mission_id", "binding_id", "mission_authorization_id")
    }
    for name in ("initial_evidence", "reread_evidence"):
        if inputs.input_states[name] != "present":
            continue
        evidence = getattr(inputs, name)
        observed_repository = {
            key: evidence["repository"][key]
            for key in ("id", "node_id", "owner", "name")
        }
        observed_pull = {
            key: evidence["pull_request"][key] for key in expected_pull
        }
        observed_diff = {
            "diff_sha256": evidence["diff"]["diff_sha256"],
            "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
            "object_evidence_sha256": evidence["diff"]["object_evidence"][
                "files_sha256"
            ],
        }
        observed_mission = {
            key: evidence["bindings"][key] for key in expected_mission
        }
        if (
            observed_repository != expected_repository
            or observed_pull != expected_pull
            or observed_diff != receipt["diff"]
            or observed_mission != expected_mission
        ):
            blocks.append(EligibilityBlock(
                DenyCode.IDENTITY_DRIFT,
                f"{name}.publication_receipt",
                "evidence differs from the persisted publication receipt",
            ))
    return tuple(blocks)


def _outcome(blocks: tuple[EligibilityBlock, ...]) -> EligibilityOutcome:
    codes = {block.code for block in blocks}
    if codes & UNKNOWN_CODES:
        return EligibilityOutcome.UNKNOWN
    if codes & UNSUPPORTED_CODES:
        return EligibilityOutcome.UNSUPPORTED
    return EligibilityOutcome.POLICY_BLOCKED if blocks else EligibilityOutcome.ELIGIBLE


class MergeStatusController:
    """K5.1 observation-only composition; it cannot create an intent or load a writer."""

    def __init__(
        self,
        reader: InstalledHostMergeReader,
        *,
        clock=None,
    ):
        self.reader = reader
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def inspect(self, request_id: str, *, operation: str) -> dict:
        if operation not in {"status", "evaluate"}:
            raise StateError("merge status operation must be status or evaluate")
        current = self.clock()
        if not isinstance(current, datetime) or current.utcoffset() is None:
            raise StateError("merge status time requires a UTC offset")
        inputs = self.reader.load(request_id)
        evaluation = MergePolicyEvaluator().evaluate_reread(
            inputs.policy,
            inputs.authorization,
            inputs.protected_policy,
            inputs.initial_evidence,
            inputs.reread_evidence,
            now=current,
        )
        combined = {
            (block.code, block.surface, block.detail): block
            for block in (
                *evaluation.verdict.blocks,
                *_receipt_blocks(inputs),
            )
        }
        blocks = tuple(sorted(
            combined.values(),
            key=lambda block: (block.code.value, block.surface, block.detail),
        ))
        outcome = _outcome(blocks)
        report = {
            "schema_version": 1,
            "operation": operation,
            "source": "installed-host-read-only-composition",
            "state": "awaiting-review",
            "outcome": outcome.value,
            "eligible": outcome is EligibilityOutcome.ELIGIBLE,
            "intent_ready": False,
            "execution_available": False,
            "writer_credential_loaded": False,
            "merge_intent_created": False,
            "publication": _publication(inputs.receipt),
            "inputs": inputs.input_states,
            "blocks": [
                {
                    "code": block.code.value,
                    "surface": block.surface,
                    "detail": block.detail,
                }
                for block in blocks
            ],
            "required_approvals": evaluation.verdict.required_approvals,
            "approval_actor_ids": list(evaluation.verdict.approval_actor_ids),
            "required_checks": [
                {"context": check.context, "app_id": check.app_id}
                for check in evaluation.verdict.required_checks
            ],
            "observed_at": current.isoformat(),
            "report_sha256": "0" * 64,
        }
        report["report_sha256"] = canonical_sha256(report, "report_sha256")
        error = next(REPORT_VALIDATOR.iter_errors(report), None)
        if error is not None:
            raise StateError("generated merge status report is invalid")
        return report


def render_merge_status(report: Mapping[str, object]) -> str:
    pull = report["publication"]["pull_request"]
    lines = [
        "# Pathfinder merge status",
        "",
        f"- state: `{report['state']}`",
        f"- outcome: `{report['outcome']}`",
        f"- eligible: `{str(report['eligible']).lower()}`",
        "- execution available: `false` (K5.1 observation-only)",
        f"- pull request: [{pull['number']}]({pull['url']})",
        f"- head: `{pull['head_sha']}`",
        f"- report: `{report['report_sha256']}`",
        "",
        "## Blocks",
        "",
    ]
    if report["blocks"]:
        lines.extend(
            f"- `{block['code']}` — {block['detail']} (`{block['surface']}`)"
            for block in report["blocks"]
        )
    else:
        lines.append("- None. Execution remains unavailable in K5.1.")
    return "\n".join(lines) + "\n"
