from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from .errors import StateError
from .host_artifact_store import HostArtifactCollectionStore
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
from .storage import canonical_sha256, load_json_stream, read_json


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
REPOSITORY_KEYS = ("id", "node_id", "owner", "name")
PULL_KEYS = (
    "id", "node_id", "number", "head_ref", "head_sha", "base_ref", "base_sha",
)
_MISSING = object()


class InputState(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"
    SHIPPED_BASELINE = "shipped-baseline"


@dataclass(frozen=True)
class InstalledMergeInputs:
    receipt: dict
    policy: object | None
    authorization: object | None
    protected_policy: object | None
    initial_evidence: object | None
    reread_evidence: object | None
    input_states: dict[str, InputState]


class MergeInputReader(Protocol):
    def load(self, request_id: str) -> InstalledMergeInputs: ...


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

    def _open_root(self) -> int:
        if os.name == "nt":
            raise StateError(
                "merge status is unavailable on Windows until host ACL ownership "
                "can be verified"
            )
        if not self.repo_root.is_dir() or self.repo_root.is_symlink():
            raise StateError("repository root must be an existing non-symlink directory")
        try:
            initial = self.host_root.lstat()
        except OSError as error:
            raise StateError("installed host root must be an existing directory") from error
        if not stat.S_ISDIR(initial.st_mode) or self.host_root.is_symlink():
            raise StateError("installed host root must be an existing non-symlink directory")
        repository = self.repo_root.resolve()
        host = self.host_root.resolve()
        try:
            host.relative_to(repository)
        except ValueError:
            pass
        else:
            raise StateError("installed host root must be outside repository trust")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            descriptor = os.open(self.host_root, flags)
        except OSError as error:
            raise StateError("installed host root could not be pinned safely") from error
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (initial.st_dev, initial.st_ino)
        ):
            os.close(descriptor)
            raise StateError("installed host root changed during validation")
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            os.close(descriptor)
            raise StateError("installed host root must be owned by the current user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            os.close(descriptor)
            raise StateError("installed host root must be owner-only")
        return descriptor

    @staticmethod
    def _open_directory(parent: int, name: str, label: str) -> int:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent,
            )
        except OSError as error:
            raise StateError(
                f"{label} must be a pinned non-symlink directory"
            ) from error
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise StateError(f"{label} must be a directory")
        return descriptor

    @staticmethod
    def _read_at(parent: int, name: str, *, required: bool) -> object:
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError:
            if required:
                raise StateError(f"required installed host input is missing: {name}")
            return _MISSING
        except OSError as error:
            raise StateError(f"installed host input could not be opened safely: {name}") from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise StateError(f"installed host input must be a regular file: {name}")
            with os.fdopen(descriptor, encoding="utf-8") as stream:
                descriptor = -1
                return load_json_stream(stream)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise StateError(f"installed host input is not valid JSON: {name}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _optional(
        self, host_descriptor: int, name: str
    ) -> tuple[object | None, InputState]:
        try:
            document = self._read_at(
                host_descriptor, self.FILES[name], required=False
            )
        except StateError:
            return {}, InputState.INVALID
        if document is _MISSING:
            return None, InputState.MISSING
        validator = INPUT_VALIDATORS.get(name)
        if validator is not None and next(validator.iter_errors(document), None):
            return document, InputState.INVALID
        return document, InputState.PRESENT

    def load(self, request_id: str) -> InstalledMergeInputs:
        if PUBLICATION_REQUEST_ID.fullmatch(request_id) is None:
            raise StateError(f"invalid publication request id: {request_id}")
        host_descriptor = self._open_root()
        try:
            journal_descriptor = self._open_directory(
                host_descriptor, "journal", "publication journal"
            )
            try:
                operations_descriptor = self._open_directory(
                    journal_descriptor,
                    "publication-operations",
                    "publication operations",
                )
                try:
                    records = {}
                    for label in ("request", "dispatch", "receipt"):
                        record = self._read_at(
                            operations_descriptor,
                            f"{request_id}.{label}.json",
                            required=label == "request",
                        )
                        records[label] = None if record is _MISSING else record
                finally:
                    os.close(operations_descriptor)
            finally:
                os.close(journal_descriptor)
            loaded = PublicationJournal(
                self.host_root / "journal"
            ).validate_records(
                records["request"], records["dispatch"], records["receipt"],
                expected_request_id=request_id,
            )
            receipt = loaded["receipt"]
            if receipt is None:
                raise StateError("exact awaiting-review publication receipt is required")

            values: dict[str, object | None] = {}
            states: dict[str, InputState] = {}
            for name in (
                "policy", "authorization", "initial_evidence", "reread_evidence",
            ):
                document, state = self._optional(host_descriptor, name)
                values[name] = document
                states[name] = state

            protected, protected_state = self._optional(
                host_descriptor, "protected_policy"
            )
            if protected_state is InputState.MISSING:
                protected = ProtectedSurfaceRegistry.load().to_document()
                protected_state = InputState.SHIPPED_BASELINE
            states["protected_policy"] = protected_state
        finally:
            os.close(host_descriptor)

        return InstalledMergeInputs(
            receipt,
            values["policy"],
            values["authorization"],
            protected,
            values["initial_evidence"],
            values["reread_evidence"],
            states,
        )


class AuthenticatedHostMergeReader:
    """Loads two explicit externally authenticated collections without discovery."""

    SHARED_DOCUMENTS = (
        "publication_request",
        "publication_dispatch",
        "publication_receipt",
        "publication_credential_receipt",
        "policy",
        "authorization",
        "protected_policy",
    )

    def __init__(
        self,
        store: HostArtifactCollectionStore,
        *,
        initial_evidence_id: str,
        reread_evidence_id: str,
    ):
        if initial_evidence_id == reread_evidence_id:
            raise StateError("authenticated snapshots require distinct evidence ids")
        self.store = store
        self.initial_evidence_id = initial_evidence_id
        self.reread_evidence_id = reread_evidence_id

    def load(self, request_id: str) -> InstalledMergeInputs:
        if PUBLICATION_REQUEST_ID.fullmatch(request_id) is None:
            raise StateError(f"invalid publication request id: {request_id}")
        initial = self.store.load(self.initial_evidence_id)
        reread = self.store.load(self.reread_evidence_id)
        initial_payload = initial["payload"]
        reread_payload = reread["payload"]
        initial_documents = initial_payload["documents"]
        reread_documents = reread_payload["documents"]
        if (
            initial_payload["publication_request_id"] != request_id
            or reread_payload["publication_request_id"] != request_id
            or initial["envelope_sha256"] == reread["envelope_sha256"]
            or any(
                initial["attestation"][name] != reread["attestation"][name]
                for name in ("source", "authenticator_id", "key_id", "method")
            )
            or any(
                initial_documents[name] != reread_documents[name]
                for name in self.SHARED_DOCUMENTS
            )
        ):
            raise StateError("authenticated snapshot pair bindings differ")

        receipt = initial_documents["publication_receipt"]
        PublicationJournal(Path(".")).validate_records(
            initial_documents["publication_request"],
            initial_documents["publication_dispatch"],
            receipt,
            expected_request_id=request_id,
        )
        states = {
            name: InputState.PRESENT
            for name in (
                "policy",
                "authorization",
                "protected_policy",
                "initial_evidence",
                "reread_evidence",
            )
        }
        return InstalledMergeInputs(
            receipt,
            initial_documents["policy"],
            initial_documents["authorization"],
            initial_documents["protected_policy"],
            initial_documents["evidence"],
            reread_documents["evidence"],
            states,
        )


def _publication(receipt: Mapping[str, object]) -> dict:
    pull = receipt["pull_request"]
    repository = receipt["repository"]
    return {
        "publication_request_id": receipt["publication_request_id"],
        "publication_receipt_id": receipt["publication_receipt_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "repository": {key: repository[key] for key in REPOSITORY_KEYS},
        "pull_request": {
            key: pull[key]
            for key in (*PULL_KEYS[:3], "url", *PULL_KEYS[3:])
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
            for key in PULL_KEYS
        },
        "diff": receipt["diff"],
    }
    if (
        inputs.input_states["authorization"] is InputState.PRESENT
        and inputs.authorization["candidate"] != expected_candidate
    ):
        blocks.append(EligibilityBlock(
            DenyCode.IDENTITY_DRIFT,
            "authorization.publication_receipt",
            "authorization candidate differs from the persisted publication receipt",
        ))

    expected_repository = {
        key: receipt["repository"][key] for key in REPOSITORY_KEYS
    }
    expected_pull = expected_candidate["pull_request"]
    expected_mission = {
        key: receipt["mission"][key]
        for key in ("mission_id", "binding_id", "mission_authorization_id")
    }
    for name in ("initial_evidence", "reread_evidence"):
        if inputs.input_states[name] is not InputState.PRESENT:
            continue
        evidence = getattr(inputs, name)
        observed_repository = {
            key: evidence["repository"][key] for key in REPOSITORY_KEYS
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


def _input_bindings(inputs: InstalledMergeInputs) -> dict:
    id_fields = {
        "policy": "policy_id",
        "authorization": "merge_authorization_id",
        "initial_evidence": "evidence_id",
        "reread_evidence": "evidence_id",
        "protected_policy": "policy_id",
    }
    hash_fields = {
        "policy": "policy_sha256",
        "authorization": "authorization_sha256",
        "initial_evidence": "evidence_sha256",
        "reread_evidence": "evidence_sha256",
    }
    bindings = {}
    for name in id_fields:
        document = getattr(inputs, name)
        document_id = document.get(id_fields[name]) if isinstance(document, dict) else None
        declared = (
            document.get(hash_fields[name])
            if isinstance(document, dict) and name in hash_fields
            else None
        )
        bindings[name] = {
            "state": inputs.input_states[name].value,
            "document_id": (
                document_id
                if isinstance(document_id, str) and 1 <= len(document_id) <= 128
                else None
            ),
            "document_sha256": (
                None
                if inputs.input_states[name] is InputState.MISSING
                else canonical_sha256(document)
            ),
            "declared_sha256": (
                declared
                if isinstance(declared, str)
                and len(declared) == 64
                and all(character in "0123456789abcdef" for character in declared)
                else None
            ),
        }
    return bindings


def _evaluation_document(document: object | None, state: InputState):
    """Keep JSON null distinct from a missing input for evaluator typing."""
    return {} if state is InputState.INVALID and document is None else document


class MergeStatusController:
    """K5.1 observation-only composition; it cannot create an intent or load a writer."""

    def __init__(
        self,
        reader: MergeInputReader,
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
            _evaluation_document(inputs.policy, inputs.input_states["policy"]),
            _evaluation_document(
                inputs.authorization, inputs.input_states["authorization"]
            ),
            _evaluation_document(
                inputs.protected_policy, inputs.input_states["protected_policy"]
            ),
            _evaluation_document(
                inputs.initial_evidence, inputs.input_states["initial_evidence"]
            ),
            _evaluation_document(
                inputs.reread_evidence, inputs.input_states["reread_evidence"]
            ),
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
            "inputs": _input_bindings(inputs),
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
