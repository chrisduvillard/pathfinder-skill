from __future__ import annotations

import copy
import json
import os
import re
import secrets
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .merge_time import parse_aware_timestamp
from .protected_surfaces import ProtectedSurfaceRegistry
from .publication_journal import PublicationJournal
from .storage import canonical_sha256, load_json_stream, read_json


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas" / "publication"
STORE_ID = re.compile(r"^host_artifact_store_[a-z0-9][a-z0-9_-]{7,63}$")
EVIDENCE_ID = re.compile(r"^merge_evidence_([a-z0-9][a-z0-9_-]{7,63})$")
MAX_COLLECTION_BYTES = 8 * 1024 * 1024
DOCUMENT_SCHEMAS = {
    "publication_credential_receipt": "publication-credential-receipt.schema.json",
    "observer_credential_receipt": "evidence-credential-receipt.schema.json",
    "merge_credential_receipt": "merge-credential-receipt.schema.json",
    "policy": "merge-policy.schema.json",
    "authorization": "merge-authorization.schema.json",
    "branch_ownership": "controller-branch-ownership.schema.json",
    "evidence": "merge-evidence.schema.json",
    "provenance": "merge-evidence-provenance.schema.json",
}
REPOSITORY_KEYS = ("id", "node_id", "owner", "name")
PULL_KEYS = (
    "id",
    "node_id",
    "number",
    "head_ref",
    "head_sha",
    "base_ref",
    "base_sha",
)


class HostArtifactAuthenticator(Protocol):
    """External trusted-host authentication; implementations and keys are not shipped."""

    def attest(
        self, payload: bytes, *, authenticated_at: str
    ) -> Mapping[str, object]: ...

    def verify(
        self, payload: bytes, attestation: Mapping[str, object]
    ) -> bool: ...


def _canonical_bytes(document: object) -> bytes:
    try:
        return json.dumps(
            document, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise StateError("host artifact collection is not canonical JSON") from error


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise StateError("host artifact store clock requires a UTC offset")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class HostArtifactCollectionStore:
    """Immutable evidence collections with no shipped key or network implementation."""

    def __init__(
        self,
        repo_root: Path | str,
        host_root: Path | str,
        *,
        store_id: str,
        authenticator: HostArtifactAuthenticator,
        clock=None,
    ):
        if STORE_ID.fullmatch(store_id) is None:
            raise StateError(f"invalid host artifact store id: {store_id}")
        self.repo_root = Path(repo_root)
        self.host_root = Path(host_root)
        self.store_id = store_id
        self.authenticator = authenticator
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._envelope_validator = Draft202012Validator(
            read_json(SCHEMA_ROOT / "host-artifact-collection.schema.json"),
            format_checker=FormatChecker(),
        )
        self._input_envelope_validator = Draft202012Validator(
            read_json(
                SCHEMA_ROOT / "host-artifact-collection-input.schema.json"
            ),
            format_checker=FormatChecker(),
        )
        self._document_validators = {
            label: Draft202012Validator(
                read_json(SCHEMA_ROOT / schema), format_checker=FormatChecker()
            )
            for label, schema in DOCUMENT_SCHEMAS.items()
        }
        self._document_validators["protected_policy"] = Draft202012Validator(
            read_json(ROOT / "schemas" / "policy" / "protected-surfaces.schema.json"),
            format_checker=FormatChecker(),
        )

    @staticmethod
    def _collection_identity(evidence_id: str) -> tuple[str, str]:
        match = EVIDENCE_ID.fullmatch(evidence_id)
        if match is None:
            raise StateError(f"invalid merge evidence id: {evidence_id}")
        collection_id = f"host_artifact_collection_{match.group(1)}"
        return collection_id, f"{collection_id}.json"

    @staticmethod
    def _input_identity(evidence_id: str) -> str:
        match = EVIDENCE_ID.fullmatch(evidence_id)
        if match is None:
            raise StateError(f"invalid merge evidence id: {evidence_id}")
        return f"host_artifact_input_{match.group(1)}"

    def _open_root(self) -> int:
        if os.name == "nt":
            raise StateError(
                "host artifact storage is unavailable on Windows until host ACL "
                "ownership can be verified"
            )
        if not self.repo_root.is_dir() or self.repo_root.is_symlink():
            raise StateError("repository root must be an existing non-symlink directory")
        try:
            initial = self.host_root.lstat()
        except OSError as error:
            raise StateError("host artifact root must be an existing directory") from error
        if not stat.S_ISDIR(initial.st_mode) or self.host_root.is_symlink():
            raise StateError("host artifact root must be an existing non-symlink directory")

        repository = self.repo_root.resolve()
        host = self.host_root.resolve()
        for child, parent in ((host, repository), (repository, host)):
            try:
                child.relative_to(parent)
            except ValueError:
                continue
            raise StateError("host artifact root must not overlap repository trust")

        try:
            descriptor = os.open(
                self.host_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
        except OSError as error:
            raise StateError("host artifact root could not be pinned safely") from error
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (initial.st_dev, initial.st_ino)
        ):
            os.close(descriptor)
            raise StateError("host artifact root changed during validation")
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            os.close(descriptor)
            raise StateError("host artifact root must be owned by the current user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            os.close(descriptor)
            raise StateError("host artifact root must be owner-only")
        return descriptor

    @staticmethod
    def _open_collections(root_descriptor: int, *, create: bool) -> int:
        if create:
            try:
                os.mkdir("artifact-collections", mode=0o700, dir_fd=root_descriptor)
            except FileExistsError:
                pass
            except OSError as error:
                raise StateError(
                    "host artifact collection directory could not be created"
                ) from error
        try:
            descriptor = os.open(
                "artifact-collections",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_descriptor,
            )
        except OSError as error:
            raise StateError(
                "host artifact collections must be a pinned non-symlink directory"
            ) from error
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            os.close(descriptor)
            raise StateError("host artifact collections must be a directory")
        if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
            os.close(descriptor)
            raise StateError("host artifact collections must be owned by the current user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            os.close(descriptor)
            raise StateError("host artifact collections must be owner-only")
        return descriptor

    @staticmethod
    def _read_at(parent: int, name: str, *, required: bool = True) -> dict | None:
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError:
            if not required:
                return None
            raise StateError(f"host artifact collection not found: {name}") from None
        except OSError as error:
            raise StateError(f"host artifact collection could not be opened: {name}") from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise StateError(f"host artifact collection must be a regular file: {name}")
            if metadata.st_size > MAX_COLLECTION_BYTES:
                raise StateError(f"host artifact collection exceeds the size limit: {name}")
            if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
                raise StateError(f"host artifact collection has the wrong owner: {name}")
            if stat.S_IMODE(metadata.st_mode) & 0o077:
                raise StateError(f"host artifact collection must be owner-only: {name}")
            with os.fdopen(descriptor, encoding="utf-8") as stream:
                descriptor = -1
                document = load_json_stream(stream)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise StateError(f"host artifact collection is not valid JSON: {name}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(document, dict):
            raise StateError(f"host artifact collection must be an object: {name}")
        return document

    @staticmethod
    def _write_once(parent: int, name: str, envelope: dict) -> dict:
        temporary = f".{name}.{secrets.token_hex(8)}.tmp"
        encoded = (json.dumps(envelope, indent=2, sort_keys=True) + "\n").encode()
        if len(encoded) > MAX_COLLECTION_BYTES:
            raise StateError("host artifact collection exceeds the size limit")
        descriptor = -1
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(
                    temporary,
                    name,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                    follow_symlinks=False,
                )
            except FileExistsError:
                return HostArtifactCollectionStore._read_at(parent, name)
            os.fsync(parent)
            return envelope
        except OSError as error:
            raise StateError("host artifact collection could not be written atomically") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary, dir_fd=parent)
                os.fsync(parent)
            except FileNotFoundError:
                pass

    @staticmethod
    def _validate_hash(document: Mapping[str, object], field: str, label: str) -> None:
        if document.get(field) != canonical_sha256(document, field):
            raise StateError(f"{label} canonical hash differs")

    def _validate_schema(self, label: str, document: object) -> None:
        validator = self._document_validators[label]
        try:
            validator.validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for {label}{suffix}: {error.message}"
            ) from error

    def _validate_input_documents(
        self, documents: Mapping[str, object]
    ) -> str:
        try:
            request = documents["publication_request"]
            dispatch = documents["publication_dispatch"]
            receipt = documents["publication_receipt"]
            publication_credential = documents[
                "publication_credential_receipt"
            ]
            observer_credential = documents["observer_credential_receipt"]
            merge_credential = documents["merge_credential_receipt"]
            policy = documents["policy"]
            authorization = documents["authorization"]
            protected_policy = documents["protected_policy"]
        except (KeyError, TypeError) as error:
            raise StateError("host artifact input document set is incomplete") from error

        PublicationJournal(Path(".")).validate_records(request, dispatch, receipt)
        for label, document in (
            ("publication_credential_receipt", publication_credential),
            ("observer_credential_receipt", observer_credential),
            ("merge_credential_receipt", merge_credential),
            ("policy", policy),
            ("authorization", authorization),
            ("protected_policy", protected_policy),
        ):
            self._validate_schema(label, document)
        self._validate_hash(
            publication_credential,
            "receipt_sha256",
            "publication credential receipt",
        )
        self._validate_hash(
            observer_credential, "receipt_sha256", "observer credential receipt"
        )
        self._validate_hash(
            merge_credential, "receipt_sha256", "merge credential receipt"
        )
        self._validate_hash(policy, "policy_sha256", "merge policy")
        self._validate_hash(
            authorization, "authorization_sha256", "merge authorization"
        )
        try:
            shipped_protected = ProtectedSurfaceRegistry.load()
            if protected_policy["mode"] == "baseline":
                if protected_policy != shipped_protected.to_document():
                    raise StateError(
                        "protected baseline differs from the shipped policy"
                    )
                return shipped_protected.sha256
            return ProtectedSurfaceRegistry(
                shipped_protected.to_document(), protected_policy
            ).sha256
        except (KeyError, StateError, TypeError, ValueError) as error:
            raise StateError(
                "host artifact protected policy is not a valid shipped baseline "
                "or additive override"
            ) from error

    @staticmethod
    def _validate_input_document_bindings(
        documents: Mapping[str, object],
        *,
        effective_protected_sha256: str,
        authenticated_at: str,
    ) -> None:
        try:
            receipt = documents["publication_receipt"]
            publication_credential = documents[
                "publication_credential_receipt"
            ]
            observer_credential = documents["observer_credential_receipt"]
            merge_credential = documents["merge_credential_receipt"]
            policy = documents["policy"]
            authorization = documents["authorization"]
            policy_read = documents["policy_read"]
            receipt_repository = receipt["repository"]
            receipt_pull = receipt["pull_request"]
            policy_repository = {
                **{
                    key: receipt_repository[key]
                    for key in REPOSITORY_KEYS
                },
                "base_branch": receipt_pull["base_ref"],
            }
            candidate = {
                "source": "authenticated-controller-publication",
                "mission_state_sha256": receipt["mission"][
                    "mission_state_sha256"
                ],
                "publication_receipt_id": receipt["publication_receipt_id"],
                "pull_request": {
                    key: receipt_pull[key] for key in PULL_KEYS
                },
                "diff": receipt["diff"],
            }
            bindings_differ = (
                policy["repository"] != policy_repository
                or authorization["repository"] != policy_repository
                or authorization["policy"] != {
                    "policy_id": policy["policy_id"],
                    "policy_sha256": policy["policy_sha256"],
                }
                or authorization["mission"] != {
                    **{
                        key: receipt["mission"][key]
                        for key in (
                            "mission_id",
                            "binding_id",
                            "mission_authorization_id",
                        )
                    },
                    "goal_scope": "single-goal",
                }
                or authorization["candidate"] != candidate
                or policy["path_policy"]["protected_policy_sha256"]
                != effective_protected_sha256
                or policy_read["policy_id"] != policy["policy_id"]
                or policy_read["policy_sha256"] != policy["policy_sha256"]
                or publication_credential["repository_ids"]
                != [receipt_repository["id"]]
                or publication_credential["actor_id"]
                != receipt["head_push"]["actor_id"]
                or publication_credential["actor_node_id"]
                != receipt["head_push"]["actor_node_id"]
                or publication_credential["login"]
                != receipt["head_push"]["login"]
                or observer_credential["repository_ids"]
                != [receipt_repository["id"]]
                or merge_credential["repository_ids"]
                != [receipt_repository["id"]]
                or len({
                    publication_credential["app_id"],
                    observer_credential["app_id"],
                    merge_credential["app_id"],
                }) != 3
                or len({
                    publication_credential["installation_id"],
                    observer_credential["installation_id"],
                    merge_credential["installation_id"],
                }) != 3
                or len({
                    publication_credential["actor_id"],
                    observer_credential["actor_id"],
                    merge_credential["actor_id"],
                }) != 3
            )
            current = parse_aware_timestamp(authenticated_at)
            authority_current = (
                parse_aware_timestamp(policy["issued_at"])
                <= current
                < parse_aware_timestamp(policy["expires_at"])
                and parse_aware_timestamp(authorization["issued_at"])
                <= current
                < parse_aware_timestamp(authorization["expires_at"])
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StateError(
                "host artifact input document bindings differ"
            ) from error
        if bindings_differ:
            raise StateError("host artifact input document bindings differ")
        if not authority_current:
            raise StateError("host artifact input authority is not current")

    def _validate_documents(self, documents: Mapping[str, object]) -> None:
        try:
            receipt = documents["publication_receipt"]
            publication_credential = documents["publication_credential_receipt"]
            observer_credential = documents["observer_credential_receipt"]
            merge_credential = documents["merge_credential_receipt"]
            policy = documents["policy"]
            authorization = documents["authorization"]
            ownership = documents["branch_ownership"]
            evidence = documents["evidence"]
            provenance = documents["provenance"]
        except (KeyError, TypeError) as error:
            raise StateError("host artifact document set is incomplete") from error

        effective_protected_sha256 = self._validate_input_documents(documents)
        for label, document in (
            ("branch_ownership", ownership),
            ("evidence", evidence),
            ("provenance", provenance),
        ):
            self._validate_schema(label, document)
        self._validate_hash(ownership, "ownership_sha256", "branch ownership")
        self._validate_hash(evidence, "evidence_sha256", "merge evidence")
        self._validate_hash(provenance, "provenance_sha256", "evidence provenance")

        receipt_repository = receipt["repository"]
        evidence_repository = {
            key: evidence["repository"][key] for key in REPOSITORY_KEYS
        }
        receipt_pull = receipt["pull_request"]
        evidence_pull = {key: evidence["pull_request"][key] for key in PULL_KEYS}
        evidence_diff = {
            "diff_sha256": evidence["diff"]["diff_sha256"],
            "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
            "object_evidence_sha256": evidence["diff"]["object_evidence"][
                "files_sha256"
            ],
        }
        required_checks = sorted(
            (check["context"], check["app_id"])
            for check in evidence["checks"]
            if check["required"]
        )
        provenance_checks = sorted(
            (check["context"], check["app_id"])
            for check in provenance["required_checks"]
        )
        merge_actor = evidence["actor"]
        policy_repository = {
            **{key: receipt_repository[key] for key in REPOSITORY_KEYS},
            "base_branch": receipt_pull["base_ref"],
        }
        candidate = {
            "source": "authenticated-controller-publication",
            "mission_state_sha256": receipt["mission"]["mission_state_sha256"],
            "publication_receipt_id": receipt["publication_receipt_id"],
            "pull_request": {key: receipt_pull[key] for key in PULL_KEYS},
            "diff": receipt["diff"],
        }
        try:
            credential_times_valid = (
                parse_aware_timestamp(observer_credential["issued_at"])
                <= parse_aware_timestamp(observer_credential["verified_at"])
                == parse_aware_timestamp(evidence["observation"]["observed_at"])
                <= parse_aware_timestamp(evidence["observation"]["completed_at"])
                < parse_aware_timestamp(evidence["observation"]["expires_at"])
                <= parse_aware_timestamp(observer_credential["expires_at"])
                <= parse_aware_timestamp(observer_credential["issued_at"])
                + timedelta(hours=1)
                and parse_aware_timestamp(merge_credential["issued_at"])
                <= parse_aware_timestamp(merge_credential["verified_at"])
                == parse_aware_timestamp(evidence["observation"]["observed_at"])
                <= parse_aware_timestamp(evidence["observation"]["completed_at"])
                < parse_aware_timestamp(evidence["observation"]["expires_at"])
                <= parse_aware_timestamp(merge_credential["expires_at"])
                <= parse_aware_timestamp(merge_credential["issued_at"])
                + timedelta(hours=1)
                and parse_aware_timestamp(publication_credential["issued_at"])
                <= parse_aware_timestamp(publication_credential["verified_at"])
                <= parse_aware_timestamp(receipt["observed_at"])
                <= parse_aware_timestamp(ownership["observation"]["observed_at"])
                <= parse_aware_timestamp(ownership["observation"]["completed_at"])
                < parse_aware_timestamp(publication_credential["expires_at"])
                <= parse_aware_timestamp(publication_credential["issued_at"])
                + timedelta(hours=1)
            )
            authority_times_valid = (
                parse_aware_timestamp(policy["issued_at"])
                <= parse_aware_timestamp(evidence["observation"]["observed_at"])
                <= parse_aware_timestamp(evidence["observation"]["completed_at"])
                < parse_aware_timestamp(evidence["observation"]["expires_at"])
                <= parse_aware_timestamp(policy["expires_at"])
                and parse_aware_timestamp(authorization["issued_at"])
                <= parse_aware_timestamp(evidence["observation"]["observed_at"])
                <= parse_aware_timestamp(evidence["observation"]["completed_at"])
                < parse_aware_timestamp(evidence["observation"]["expires_at"])
                <= parse_aware_timestamp(authorization["expires_at"])
            )
        except (TypeError, ValueError):
            credential_times_valid = False
            authority_times_valid = False
        if (
            ownership["publication_receipt_id"] != receipt["publication_receipt_id"]
            or ownership["publication_receipt_sha256"] != receipt["receipt_sha256"]
            or ownership["repository"] != receipt_repository
            or ownership["head_ref"] != receipt_pull["head_ref"]
            or ownership["head_sha"] != receipt_pull["head_sha"]
            or ownership["publisher"]["actor_id"] != receipt["head_push"]["actor_id"]
            or ownership["publisher"]["actor_node_id"]
            != receipt["head_push"]["actor_node_id"]
            or ownership["publisher"]["login"] != receipt["head_push"]["login"]
            or ownership["publisher"]["app_id"] != publication_credential["app_id"]
            or ownership["publisher"]["app_node_id"]
            != publication_credential["app_node_id"]
            or ownership["publication_credential_receipt_id"]
            != publication_credential["credential_receipt_id"]
            or ownership["publication_credential_receipt_sha256"]
            != publication_credential["receipt_sha256"]
            or publication_credential["repository_ids"] != [receipt_repository["id"]]
            or publication_credential["actor_id"] != receipt["head_push"]["actor_id"]
            or publication_credential["actor_node_id"]
            != receipt["head_push"]["actor_node_id"]
            or publication_credential["login"] != receipt["head_push"]["login"]
            or evidence_repository != receipt_repository
            or evidence_pull != {key: receipt_pull[key] for key in PULL_KEYS}
            or evidence_diff != receipt["diff"]
            or evidence["bindings"]["mission_id"] != receipt["mission"]["mission_id"]
            or evidence["bindings"]["binding_id"] != receipt["mission"]["binding_id"]
            or evidence["bindings"]["mission_authorization_id"]
            != receipt["mission"]["mission_authorization_id"]
            or evidence["bindings"]["policy_id"] != policy["policy_id"]
            or evidence["bindings"]["policy_sha256"] != policy["policy_sha256"]
            or evidence["bindings"]["merge_authorization_id"]
            != authorization["merge_authorization_id"]
            or evidence["bindings"]["authorization_sha256"]
            != authorization["authorization_sha256"]
            or evidence["bindings"]["protected_policy_sha256"]
            != effective_protected_sha256
            or evidence["pull_request"]["last_pusher_id"]
            != ownership["publisher"]["actor_id"]
            or provenance["evidence_id"] != evidence["evidence_id"]
            or provenance["evidence_sha256"] != evidence["evidence_sha256"]
            or provenance["publication_receipt_id"]
            != receipt["publication_receipt_id"]
            or provenance["publication_receipt_sha256"] != receipt["receipt_sha256"]
            or provenance["branch_ownership_id"] != ownership["ownership_id"]
            or provenance["branch_ownership_sha256"] != ownership["ownership_sha256"]
            or provenance["observer_credential_receipt_id"]
            != observer_credential["credential_receipt_id"]
            or provenance["observer_credential_receipt_sha256"]
            != observer_credential["receipt_sha256"]
            or provenance["merge_credential_receipt_id"]
            != merge_credential["credential_receipt_id"]
            or provenance["merge_credential_receipt_sha256"]
            != merge_credential["receipt_sha256"]
            or observer_credential["repository_ids"] != [receipt_repository["id"]]
            or merge_credential["repository_ids"] != [receipt_repository["id"]]
            or merge_credential["app_id"] != merge_actor["app_id"]
            or merge_credential["app_node_id"] != merge_actor["app_node_id"]
            or merge_credential["installation_id"]
            != merge_actor["installation_id"]
            or merge_credential["installation_account_id"]
            != merge_actor["installation_account_id"]
            or merge_credential["actor_id"] != merge_actor["actor_id"]
            or merge_credential["actor_node_id"]
            != merge_actor["actor_node_id"]
            or merge_credential["login"] != merge_actor["login"]
            or merge_credential["suspended"] != merge_actor["suspended"]
            or merge_actor["administration_permission"] != "none"
            or len({
                publication_credential["app_id"],
                observer_credential["app_id"],
                merge_credential["app_id"],
            }) != 3
            or len({
                publication_credential["installation_id"],
                observer_credential["installation_id"],
                merge_credential["installation_id"],
            }) != 3
            or len({
                publication_credential["actor_id"],
                observer_credential["actor_id"],
                merge_credential["actor_id"],
            }) != 3
            or not credential_times_valid
            or not authority_times_valid
            or policy["repository"] != policy_repository
            or authorization["repository"] != policy_repository
            or authorization["policy"] != {
                "policy_id": policy["policy_id"],
                "policy_sha256": policy["policy_sha256"],
            }
            or authorization["mission"] != {
                **{
                    key: receipt["mission"][key]
                    for key in (
                        "mission_id",
                        "binding_id",
                        "mission_authorization_id",
                    )
                },
                "goal_scope": "single-goal",
            }
            or authorization["candidate"] != candidate
            or policy["path_policy"]["protected_policy_sha256"]
            != effective_protected_sha256
            or evidence["observation"]["policy_read"]["policy_id"]
            != policy["policy_id"]
            or evidence["observation"]["policy_read"]["policy_sha256"]
            != policy["policy_sha256"]
            or ownership["observation"]["evidence_completed_at"]
            != evidence["observation"]["completed_at"]
            or provenance["graphql_query_sha256"]
            != evidence["observation"]["graphql_query_sha256"]
            or provenance["request_ids_sha256"]
            != evidence["observation"]["request_ids_sha256"]
            or provenance["observed_at"] != evidence["observation"]["observed_at"]
            or provenance["completed_at"] != evidence["observation"]["completed_at"]
            or provenance_checks != required_checks
            or not set(provenance["reconciled_review_ids"]).issubset(
                review["id"] for review in evidence["reviews"]
            )
        ):
            raise StateError("host artifact collection document bindings differ")

    def verify_collection_inputs(
        self,
        envelope: Mapping[str, object],
        *,
        authenticated_at: str,
    ) -> dict:
        """Authenticate one closed input bundle before any nested document is used."""

        document = copy.deepcopy(envelope)
        try:
            self._input_envelope_validator.validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                "schema validation failed for host artifact collection input"
                f"{suffix}: {error.message}"
            ) from error
        if document["envelope_sha256"] != canonical_sha256(
            document, "envelope_sha256"
        ):
            raise StateError("host artifact input envelope canonical hash differs")

        payload = document["payload"]
        attestation = document["attestation"]
        payload_bytes = _canonical_bytes(payload)
        payload_sha256 = canonical_sha256(payload)
        input_id = self._input_identity(payload["evidence_id"])
        if (
            payload["input_id"] != input_id
            or payload["store_id"] != self.store_id
            or attestation["payload_sha256"] != payload_sha256
        ):
            raise StateError("host artifact input identity binding differs")
        if (
            payload["authenticated_at"] != authenticated_at
            or attestation["authenticated_at"] != authenticated_at
        ):
            raise StateError(
                "host artifact input was not authenticated at the trusted "
                "collection start"
            )
        try:
            verified = self.authenticator.verify(
                payload_bytes, copy.deepcopy(attestation)
            )
        except Exception as error:
            raise StateError(
                "host artifact input attestation verification failed"
            ) from error
        if verified is not True:
            raise StateError("host artifact input attestation verification failed")

        documents = payload["documents"]
        effective_protected_sha256 = self._validate_input_documents(documents)
        if (
            payload["publication_request_id"]
            != documents["publication_request"]["publication_request_id"]
            or payload["repository"]
            != documents["publication_receipt"]["repository"]
        ):
            raise StateError("host artifact input document bindings differ")
        self._validate_input_document_bindings(
            documents,
            effective_protected_sha256=effective_protected_sha256,
            authenticated_at=authenticated_at,
        )
        return copy.deepcopy(payload)

    def _validate_envelope(
        self, envelope: dict, *, expected_evidence_id: str
    ) -> dict:
        try:
            self._envelope_validator.validate(envelope)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for host artifact collection{suffix}: "
                f"{error.message}"
            ) from error
        if envelope["envelope_sha256"] != canonical_sha256(
            envelope, "envelope_sha256"
        ):
            raise StateError("host artifact envelope canonical hash differs")

        payload = envelope["payload"]
        attestation = envelope["attestation"]
        collection_id, _name = self._collection_identity(expected_evidence_id)
        payload_bytes = _canonical_bytes(payload)
        payload_sha256 = canonical_sha256(payload)
        if (
            payload["collection_id"] != collection_id
            or payload["store_id"] != self.store_id
            or payload["evidence_id"] != expected_evidence_id
            or payload["publication_request_id"]
            != payload["documents"]["publication_request"]["publication_request_id"]
            or payload["repository"]
            != payload["documents"]["publication_receipt"]["repository"]
            or payload["stored_at"] != attestation["authenticated_at"]
            or attestation["payload_sha256"] != payload_sha256
        ):
            raise StateError("host artifact envelope identity binding differs")
        try:
            stored_after_collection = parse_aware_timestamp(
                payload["stored_at"]
            ) >= max(
                parse_aware_timestamp(
                    payload["documents"]["provenance"]["completed_at"]
                ),
                parse_aware_timestamp(
                    payload["documents"]["branch_ownership"]["observation"][
                        "completed_at"
                    ]
                ),
            )
        except (TypeError, ValueError):
            stored_after_collection = False
        if not stored_after_collection:
            raise StateError("host artifact envelope predates its collection")
        try:
            verified = self.authenticator.verify(
                payload_bytes, copy.deepcopy(attestation)
            )
        except Exception as error:
            raise StateError("host artifact attestation verification failed") from error
        if verified is not True:
            raise StateError("host artifact attestation verification failed")
        self._validate_documents(payload["documents"])
        return envelope

    def persist(
        self,
        *,
        publication_request: Mapping[str, object],
        publication_dispatch: Mapping[str, object],
        publication_receipt: Mapping[str, object],
        publication_credential_receipt: Mapping[str, object],
        observer_credential_receipt: Mapping[str, object],
        merge_credential_receipt: Mapping[str, object],
        policy: Mapping[str, object],
        authorization: Mapping[str, object],
        protected_policy: Mapping[str, object],
        branch_ownership: Mapping[str, object],
        evidence: Mapping[str, object],
        provenance: Mapping[str, object],
    ) -> dict:
        documents = copy.deepcopy({
            "publication_request": publication_request,
            "publication_dispatch": publication_dispatch,
            "publication_receipt": publication_receipt,
            "publication_credential_receipt": publication_credential_receipt,
            "observer_credential_receipt": observer_credential_receipt,
            "merge_credential_receipt": merge_credential_receipt,
            "policy": policy,
            "authorization": authorization,
            "protected_policy": protected_policy,
            "branch_ownership": branch_ownership,
            "evidence": evidence,
            "provenance": provenance,
        })
        self._validate_documents(documents)
        evidence_id = documents["evidence"]["evidence_id"]
        collection_id, name = self._collection_identity(evidence_id)
        root_descriptor = self._open_root()
        try:
            collections_descriptor = self._open_collections(
                root_descriptor, create=True
            )
            try:
                existing = self._read_at(
                    collections_descriptor, name, required=False
                )
                if existing is not None:
                    validated = self._validate_envelope(
                        existing, expected_evidence_id=evidence_id
                    )
                    if validated["payload"]["documents"] != documents:
                        raise StateError(
                            "different host artifact collection already exists: "
                            f"{name}"
                        )
                    return copy.deepcopy(validated)

                stored_at = _timestamp(self.clock())
                payload = {
                    "collection_id": collection_id,
                    "store_id": self.store_id,
                    "source": "authenticated-host-artifact-store",
                    "publication_request_id": documents["publication_request"][
                        "publication_request_id"
                    ],
                    "evidence_id": evidence_id,
                    "repository": {
                        key: documents["publication_receipt"]["repository"][key]
                        for key in REPOSITORY_KEYS
                    },
                    "stored_at": stored_at,
                    "documents": documents,
                }
                payload_bytes = _canonical_bytes(payload)
                try:
                    attestation = dict(
                        self.authenticator.attest(
                            payload_bytes, authenticated_at=stored_at
                        )
                    )
                except Exception as error:
                    raise StateError(
                        "host artifact attestation could not be created"
                    ) from error
                envelope = {
                    "schema_version": 3,
                    "payload": payload,
                    "attestation": attestation,
                    "envelope_sha256": "0" * 64,
                }
                envelope["envelope_sha256"] = canonical_sha256(
                    envelope, "envelope_sha256"
                )
                self._validate_envelope(
                    envelope, expected_evidence_id=evidence_id
                )
                recorded = self._write_once(collections_descriptor, name, envelope)
            finally:
                os.close(collections_descriptor)
        finally:
            os.close(root_descriptor)
        validated = self._validate_envelope(
            recorded, expected_evidence_id=evidence_id
        )
        if validated["payload"]["documents"] != documents:
            raise StateError(
                f"different host artifact collection already exists: {name}"
            )
        return copy.deepcopy(validated)

    def load(self, evidence_id: str) -> dict:
        _collection_id, name = self._collection_identity(evidence_id)
        root_descriptor = self._open_root()
        try:
            collections_descriptor = self._open_collections(
                root_descriptor, create=False
            )
            try:
                envelope = self._read_at(collections_descriptor, name)
            finally:
                os.close(collections_descriptor)
        finally:
            os.close(root_descriptor)
        return copy.deepcopy(
            self._validate_envelope(envelope, expected_evidence_id=evidence_id)
        )
