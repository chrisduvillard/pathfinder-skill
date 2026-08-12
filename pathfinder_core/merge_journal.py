from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, TypeVar

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .merge_policy import MergePolicyEvaluator, canonical_sha256
from .merge_time import parse_aware_timestamp
from .storage import MissionLock, read_json, write_atomic


MERGE_OPERATION_ID = re.compile(
    r"^merge_operation_[a-z0-9][a-z0-9_-]{7,63}$"
)
INPUT_FILES = (
    "policy",
    "authorization",
    "credential-receipt",
    "protected-policy",
    "initial-evidence",
    "reread-evidence",
    "readiness-proof",
)
SCHEMA_NAMES = {
    "policy": "policy",
    "authorization": "authorization",
    "credential-receipt": "credential-receipt",
    "initial-evidence": "evidence",
    "reread-evidence": "evidence",
    "readiness-proof": "readiness-proof",
    "dispatch": "dispatch",
    "intent": "intent",
    "result": "result",
}
HASH_FIELDS = {
    "policy": "policy_sha256",
    "authorization": "authorization_sha256",
    "credential-receipt": "receipt_sha256",
    "initial-evidence": "evidence_sha256",
    "reread-evidence": "evidence_sha256",
    "readiness-proof": "proof_sha256",
    "dispatch": "dispatch_sha256",
    "intent": "intent_sha256",
    "result": "result_sha256",
}

DispatchResult = TypeVar("DispatchResult")


@dataclass(frozen=True)
class MergeIntentClaim:
    """Process-local capability owned only by the creator of a fresh intent."""

    operation_id: str
    intent_sha256: str


class MergeOperationJournal:
    """Write-once K4 merge journal, separate from mission operations."""

    def __init__(self, root: Path, schema_root: Path | None = None):
        self.root = Path(root)
        self.operations_path = self.root / "merge-operations"
        self.lock_path = self.root / "merge-operations.lock"
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"
        self._claims: dict[str, MergeIntentClaim] = {}

    def _path(self, operation_id: str, label: str) -> Path:
        if MERGE_OPERATION_ID.fullmatch(operation_id) is None:
            raise StateError(f"invalid merge operation id: {operation_id}")
        return self.operations_path / f"{operation_id}.{label}.json"

    def _validate_schema(self, label: str, document: Mapping[str, object]) -> None:
        schema_name = SCHEMA_NAMES[label]
        schema = read_json(
            self.schema_root / "publication" / f"merge-{schema_name}.schema.json"
        )
        try:
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for merge-{schema_name}{suffix}: {error.message}"
            ) from error

    def _validate_hash(self, label: str, document: Mapping[str, object]) -> None:
        field = HASH_FIELDS[label]
        if document[field] != canonical_sha256(document, field):
            raise StateError(f"{field} does not match canonical document")

    def _write_once(self, path: Path, document: dict, label: str) -> dict:
        if path.exists():
            existing = read_json(path)
            if existing == document:
                return existing
            raise StateError(f"different {label} already exists: {path.name}")
        write_atomic(path, document)
        return document

    def _assert_authorization_unspent(self, intent: Mapping[str, object]) -> None:
        binding = intent["bindings"]
        spend_keys = {
            "merge_authorization_id": binding["merge_authorization_id"],
            "authorization_sha256": binding["authorization_sha256"],
            "readiness_proof_sha256": binding["readiness_proof_sha256"],
        }
        for path in self.operations_path.glob("merge_operation_*.intent.json"):
            try:
                existing = read_json(path)
                existing_id = existing["operation_id"]
                existing_binding = existing["bindings"]
            except (KeyError, TypeError, ValueError) as error:
                raise StateError(
                    f"existing merge intent is malformed: {path.name}"
                ) from error
            if existing_id == intent["operation_id"]:
                continue
            reused = [
                key for key, value in spend_keys.items()
                if existing_binding.get(key) == value
            ]
            if reused:
                raise StateError(
                    "merge authorization or readiness proof was already claimed "
                    f"by {existing_id}: {','.join(reused)}"
                )

    def _validate_inputs(self, documents: Mapping[str, dict], intent: dict) -> None:
        for label in INPUT_FILES:
            if label == "protected-policy":
                continue
            self._validate_schema(label, documents[label])
            self._validate_hash(label, documents[label])
        self._validate_schema("intent", intent)
        self._validate_hash("intent", intent)

        try:
            started = parse_aware_timestamp(intent["started_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise StateError("merge intent start time is malformed") from error
        credential_receipt = documents["credential-receipt"]
        try:
            credential_current = (
                parse_aware_timestamp(credential_receipt["issued_at"])
                <= started
                == parse_aware_timestamp(credential_receipt["verified_at"])
                < parse_aware_timestamp(credential_receipt["expires_at"])
            )
        except (KeyError, TypeError, ValueError):
            credential_current = False
        if not credential_current:
            raise StateError(
                "merge credential receipt is not current at intent time"
            )
        evaluation = MergePolicyEvaluator().evaluate_reread(
            documents["policy"],
            documents["authorization"],
            documents["protected-policy"],
            documents["initial-evidence"],
            documents["reread-evidence"],
            now=started,
        )
        if not evaluation.intent_ready or evaluation.proof is None:
            reasons = ",".join(block.code.value for block in evaluation.verdict.blocks)
            raise StateError(f"merge inputs do not replay as intent-ready: {reasons}")
        readiness = documents["readiness-proof"]
        if readiness != evaluation.proof.to_document():
            raise StateError("readiness proof differs from evaluator replay")

        policy = documents["policy"]
        authorization = documents["authorization"]
        initial = documents["initial-evidence"]
        reread = documents["reread-evidence"]
        expected_bindings = {
            "readiness_proof_sha256": readiness["proof_sha256"],
            "initial_evidence_id": initial["evidence_id"],
            "initial_evidence_sha256": initial["evidence_sha256"],
            "reread_evidence_id": reread["evidence_id"],
            "reread_evidence_sha256": reread["evidence_sha256"],
            "diff_sha256": authorization["candidate"]["diff"]["diff_sha256"],
            "changed_files_sha256": authorization["candidate"]["diff"][
                "changed_files_sha256"
            ],
            "object_evidence_sha256": authorization["candidate"]["diff"][
                "object_evidence_sha256"
            ],
            "policy_id": policy["policy_id"],
            "policy_sha256": policy["policy_sha256"],
            "merge_authorization_id": authorization["merge_authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
            "credential_receipt_id": documents["credential-receipt"][
                "credential_receipt_id"
            ],
            "credential_receipt_sha256": documents["credential-receipt"][
                "receipt_sha256"
            ],
            "mission_id": authorization["mission"]["mission_id"],
            "binding_id": authorization["mission"]["binding_id"],
            "mission_authorization_id": authorization["mission"][
                "mission_authorization_id"
            ],
        }
        expected_pr = {
            key: reread["pull_request"][key]
            for key in ("id", "node_id", "number", "head_sha", "base_sha")
        }
        expected_actor = {
            key: reread["actor"][key]
            for key in (
                "app_id", "installation_id", "actor_id", "actor_node_id", "login"
            )
        }
        credential_actor = {
            key: documents["credential-receipt"][key]
            for key in (
                "app_id",
                "app_node_id",
                "installation_id",
                "installation_account_id",
                "actor_id",
                "actor_node_id",
                "login",
                "suspended",
            )
        }
        if intent["bindings"] != expected_bindings:
            raise StateError("merge intent authority or evidence binding differs")
        if intent["repository"] != policy["repository"]:
            raise StateError("merge intent repository binding differs")
        if intent["pull_request"] != expected_pr:
            raise StateError("merge intent pull request binding differs")
        if intent["actor"] != expected_actor:
            raise StateError("merge intent actor binding differs")
        if credential_actor != {
            key: reread["actor"][key] for key in credential_actor
        }:
            raise StateError("merge credential receipt actor binding differs")
        if documents["credential-receipt"]["repository_ids"] != [
            policy["repository"]["id"]
        ]:
            raise StateError("merge credential receipt repository binding differs")
        if intent["merge_method"] != policy["merge_method"]:
            raise StateError("merge intent method binding differs")

    def _record_intent(
        self,
        *,
        policy: dict,
        authorization: dict,
        credential_receipt: dict,
        protected_policy: dict,
        initial_evidence: dict,
        reread_evidence: dict,
        readiness_proof: dict,
        intent: dict,
    ) -> tuple[dict, bool]:
        documents = {
            "policy": policy,
            "authorization": authorization,
            "credential-receipt": credential_receipt,
            "protected-policy": protected_policy,
            "initial-evidence": initial_evidence,
            "reread-evidence": reread_evidence,
            "readiness-proof": readiness_proof,
        }
        self._validate_inputs(documents, intent)
        operation_id = intent["operation_id"]
        with MissionLock(self.lock_path):
            intent_path = self._path(operation_id, "intent")
            created = not intent_path.exists()
            if created:
                self._assert_authorization_unspent(intent)
            for label in INPUT_FILES:
                self._write_once(
                    self._path(operation_id, label), documents[label], label
                )
            recorded = self._write_once(intent_path, intent, "merge intent")
            return recorded, created

    def record_intent(
        self,
        *,
        policy: dict,
        authorization: dict,
        credential_receipt: dict,
        protected_policy: dict,
        initial_evidence: dict,
        reread_evidence: dict,
        readiness_proof: dict,
        intent: dict,
    ) -> dict:
        recorded, _created = self._record_intent(
            policy=policy,
            authorization=authorization,
            credential_receipt=credential_receipt,
            protected_policy=protected_policy,
            initial_evidence=initial_evidence,
            reread_evidence=reread_evidence,
            readiness_proof=readiness_proof,
            intent=intent,
        )
        return recorded

    def claim_intent(
        self,
        *,
        policy: dict,
        authorization: dict,
        credential_receipt: dict,
        protected_policy: dict,
        initial_evidence: dict,
        reread_evidence: dict,
        readiness_proof: dict,
        intent: dict,
    ) -> MergeIntentClaim | None:
        """Persist an intent and return a process-local capability only once."""
        recorded, created = self._record_intent(
            policy=policy,
            authorization=authorization,
            credential_receipt=credential_receipt,
            protected_policy=protected_policy,
            initial_evidence=initial_evidence,
            reread_evidence=reread_evidence,
            readiness_proof=readiness_proof,
            intent=intent,
        )
        if not created:
            return None
        claim = MergeIntentClaim(
            operation_id=recorded["operation_id"],
            intent_sha256=recorded["intent_sha256"],
        )
        self._claims[claim.operation_id] = claim
        return claim

    def _load_inputs(self, operation_id: str) -> tuple[dict, dict]:
        intent_path = self._path(operation_id, "intent")
        result_path = self._path(operation_id, "result")
        if result_path.exists() and not intent_path.exists():
            raise StateError("merge journal contains a result without an intent")
        if not intent_path.exists():
            partial = any(self._path(operation_id, label).exists() for label in INPUT_FILES)
            if partial:
                raise StateError("merge journal contains an incomplete pre-intent write")
            raise StateError(f"merge operation not found: {operation_id}")
        documents = {}
        for label in INPUT_FILES:
            path = self._path(operation_id, label)
            if not path.exists():
                raise StateError(f"merge journal is missing {label}")
            documents[label] = read_json(path)
        intent = read_json(intent_path)
        self._validate_inputs(documents, intent)
        return documents, intent

    def _validate_result(
        self,
        documents: Mapping[str, dict],
        intent: dict,
        dispatch: dict | None,
        result: dict,
    ) -> None:
        self._validate_schema("result", result)
        self._validate_hash("result", result)
        policy = documents["policy"]
        readiness = documents["readiness-proof"]
        expected_binding = {
            "readiness_proof_sha256": readiness["proof_sha256"],
            "policy_sha256": policy["policy_sha256"],
            "authorization_sha256": documents["authorization"]["authorization_sha256"],
            "repository": {
                key: intent["repository"][key] for key in ("id", "node_id")
            },
            "pull_request": intent["pull_request"],
            "actor": intent["actor"],
            "merge_method": intent["merge_method"],
        }
        if result["operation_id"] != intent["operation_id"]:
            raise StateError("merge result operation binding differs")
        if result["intent_sha256"] != intent["intent_sha256"]:
            raise StateError("merge result intent binding differs")
        if result["binding"] != expected_binding:
            raise StateError("merge result authority binding differs")
        if result["reason"] == "dispatch-not-started":
            if dispatch is not None:
                raise StateError(
                    "dispatch-not-started result conflicts with persisted dispatch"
                )
        elif dispatch is None:
            raise StateError("merge result requires a persisted dispatch")
        try:
            ordered = parse_aware_timestamp(
                result["completed_at"]
            ) >= parse_aware_timestamp(intent["started_at"])
        except (TypeError, ValueError):
            ordered = False
        if not ordered:
            raise StateError("merge result predates its intent")
        if dispatch is not None:
            if (
                dispatch["operation_id"] != intent["operation_id"]
                or dispatch["intent_sha256"] != intent["intent_sha256"]
            ):
                raise StateError("merge dispatch intent binding differs")
            try:
                dispatch_ordered = parse_aware_timestamp(
                    intent["started_at"]
                ) <= parse_aware_timestamp(
                    dispatch["dispatch_started_at"]
                ) <= parse_aware_timestamp(result["completed_at"])
            except (TypeError, ValueError):
                dispatch_ordered = False
            if not dispatch_ordered:
                raise StateError("merge result dispatch timeline is invalid")
        if result["outcome"] == "merged":
            proof = result["merge_proof"]
            expected = {
                "repository_id": intent["repository"]["id"],
                "pull_request_id": intent["pull_request"]["id"],
                "pull_request_node_id": intent["pull_request"]["node_id"],
                "pull_request_number": intent["pull_request"]["number"],
                "head_sha": intent["pull_request"]["head_sha"],
                "base_sha_before": intent["pull_request"]["base_sha"],
            }
            if any(proof[key] != value for key, value in expected.items()):
                raise StateError("merge proof pull request binding differs")
            expected_actor = {
                key: intent["actor"][key]
                for key in ("actor_id", "actor_node_id", "login")
            }
            if proof["merged_by"] != expected_actor:
                raise StateError("merge proof actor binding differs")
            method_compatible = (
                proof["base_ref"] == intent["repository"]["base_branch"]
                and proof["base_sha_after"] == proof["merge_commit_sha"]
                and proof["merge_commit_parent_shas"]
                == [intent["pull_request"]["base_sha"]]
                and proof["merge_endpoint_status"] == 204
            )
            try:
                timeline_valid = (
                    parse_aware_timestamp(intent["started_at"])
                    <= parse_aware_timestamp(proof["merged_at"])
                    <= parse_aware_timestamp(proof["observed_at"])
                    <= parse_aware_timestamp(result["completed_at"])
                )
            except (TypeError, ValueError):
                timeline_valid = False
            if not method_compatible or not timeline_valid:
                raise StateError("merge proof does not prove the exact squash operation")

    def record_result(self, result: dict) -> dict:
        operation_id = result.get("operation_id")
        if not isinstance(operation_id, str):
            raise StateError("merge result operation id is missing")
        with MissionLock(self.lock_path):
            documents, intent = self._load_inputs(operation_id)
            dispatch_path = self._path(operation_id, "dispatch")
            dispatch = read_json(dispatch_path) if dispatch_path.exists() else None
            if dispatch is not None:
                self._validate_schema("dispatch", dispatch)
                self._validate_hash("dispatch", dispatch)
            self._validate_result(documents, intent, dispatch, result)
            return self._write_once(
                self._path(operation_id, "result"), result, "merge result"
            )

    def dispatch_once(
        self,
        claim: MergeIntentClaim,
        *,
        started_at: str,
        send: Callable[[Callable[[], None]], DispatchResult],
    ) -> tuple[dict, DispatchResult]:
        """Let the backend mark dispatch at its final pre-transport boundary."""
        if not isinstance(claim, MergeIntentClaim):
            raise StateError("merge dispatch requires an intent creator capability")
        operation_id = claim.operation_id
        with MissionLock(self.lock_path):
            if self._claims.get(operation_id) is not claim:
                raise StateError("merge dispatch is not owned by the intent creator")
            documents, intent = self._load_inputs(operation_id)
            del documents
            if claim.intent_sha256 != intent["intent_sha256"]:
                raise StateError("merge dispatch capability intent binding differs")
            if self._path(operation_id, "result").exists():
                raise StateError("terminal merge result already exists")
            try:
                ordered = parse_aware_timestamp(
                    started_at
                ) >= parse_aware_timestamp(intent["started_at"])
            except (TypeError, ValueError):
                ordered = False
            if not ordered:
                raise StateError("merge dispatch predates its intent")
            dispatch_path = self._path(operation_id, "dispatch")
            if dispatch_path.exists():
                raise StateError("merge dispatch already started")
            recorded = None

            def mark_dispatch() -> None:
                nonlocal recorded
                if recorded is not None:
                    raise StateError("merge backend entered dispatch more than once")
                dispatch = {
                    "schema_version": 1,
                    "operation_id": operation_id,
                    "intent_sha256": intent["intent_sha256"],
                    "dispatch_started_at": started_at,
                    "dispatch_sha256": "0" * 64,
                }
                dispatch["dispatch_sha256"] = canonical_sha256(
                    dispatch, "dispatch_sha256"
                )
                self._validate_schema("dispatch", dispatch)
                self._validate_hash("dispatch", dispatch)
                recorded = self._write_once(
                    dispatch_path, dispatch, "merge dispatch"
                )

            try:
                response = send(mark_dispatch)
            finally:
                self._claims.pop(operation_id, None)
            if recorded is None:
                raise StateError("merge backend returned before entering dispatch")
            return recorded, response

    def intent_exists(self, operation_id: str) -> bool:
        return self._path(operation_id, "intent").exists()

    def load(self, operation_id: str) -> dict:
        documents, intent = self._load_inputs(operation_id)
        result_path = self._path(operation_id, "result")
        dispatch_path = self._path(operation_id, "dispatch")
        dispatch = None
        if dispatch_path.exists():
            dispatch = read_json(dispatch_path)
            self._validate_schema("dispatch", dispatch)
            self._validate_hash("dispatch", dispatch)
            if (
                dispatch["operation_id"] != operation_id
                or dispatch["intent_sha256"] != intent["intent_sha256"]
            ):
                raise StateError("merge dispatch intent binding differs")
        if not result_path.exists():
            return {
                "state": "pending",
                "disposition": "reconcile-required",
                "inputs": documents,
                "intent": intent,
                "dispatch": dispatch,
                "result": None,
            }
        result = read_json(result_path)
        self._validate_result(documents, intent, dispatch, result)
        return {
            "state": "terminal",
            "disposition": result["outcome"],
            "inputs": documents,
            "intent": intent,
            "dispatch": dispatch,
            "result": result,
        }
