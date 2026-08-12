from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable, TypeVar

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import StateError
from .merge_time import parse_aware_timestamp
from .storage import MissionLock, canonical_sha256, read_json, write_atomic


PUBLICATION_REQUEST_ID = re.compile(
    r"^publication_request_[a-z0-9][a-z0-9_-]{7,63}$"
)
DispatchResult = TypeVar("DispatchResult")


@dataclass(frozen=True)
class PublicationClaim:
    """Process-local capability returned only for a newly persisted request."""

    publication_request_id: str
    request_sha256: str


class PublicationJournal:
    """Write-once publication request, dispatch, and exact PR receipt store."""

    def __init__(self, root: Path, schema_root: Path | None = None):
        self.root = Path(root)
        self.operations_path = self.root / "publication-operations"
        self.lock_path = self.root / "publication-operations.lock"
        self.schema_root = schema_root or Path(__file__).resolve().parents[1] / "schemas"
        self._claims: dict[str, PublicationClaim] = {}

    def _path(self, request_id: str, label: str) -> Path:
        if PUBLICATION_REQUEST_ID.fullmatch(request_id) is None:
            raise StateError(f"invalid publication request id: {request_id}")
        return self.operations_path / f"{request_id}.{label}.json"

    def _validate(self, label: str, document: dict) -> None:
        schema = read_json(
            self.schema_root / "publication" / f"publication-{label}.schema.json"
        )
        try:
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).validate(document)
        except (SchemaError, ValidationError) as error:
            location = ".".join(str(part) for part in getattr(error, "path", ()))
            suffix = f" at {location}" if location else ""
            raise StateError(
                f"schema validation failed for publication-{label}{suffix}: "
                f"{error.message}"
            ) from error

    @staticmethod
    def _validate_hash(document: dict, field: str) -> None:
        if document[field] != canonical_sha256(document, field):
            raise StateError(f"{field} does not match canonical document")

    @staticmethod
    def _write_once(path: Path, document: dict, label: str) -> dict:
        if path.exists():
            existing = read_json(path)
            if existing == document:
                return existing
            raise StateError(f"different {label} already exists: {path.name}")
        write_atomic(path, document)
        return document

    def _assert_unclaimed(self, request: dict) -> None:
        for path in self.operations_path.glob("publication_request_*.request.json"):
            existing = read_json(path)
            self._validate("request", existing)
            self._validate_hash(existing, "request_sha256")
            self._validate_request_binding(existing)
            if existing["publication_request_id"] == request["publication_request_id"]:
                continue
            same_authority = (
                existing["mission"]["mission_authorization_id"]
                == request["mission"]["mission_authorization_id"]
                or existing["mission"]["mission_state_sha256"]
                == request["mission"]["mission_state_sha256"]
                or existing["candidate"]["head_sha"]
                == request["candidate"]["head_sha"]
            )
            if same_authority:
                raise StateError(
                    "publication authority or candidate was already claimed by "
                    f"{existing['publication_request_id']}"
                )

    @staticmethod
    def _validate_request_binding(request: dict) -> None:
        try:
            issued = parse_aware_timestamp(request["issued_at"])
            expires = parse_aware_timestamp(request["expires_at"])
        except (KeyError, TypeError, ValueError) as error:
            raise StateError("publication request window is malformed") from error
        if not issued < expires <= issued + timedelta(minutes=15):
            raise StateError("publication request window exceeds 15 minutes")
        if request["mission"]["commit_sha"] != request["candidate"]["head_sha"]:
            raise StateError("publication request commit and head SHA differ")
        if not request["candidate"]["head_ref"].startswith("pathfinder/auto/"):
            raise StateError("publication request head is not a controller branch")

    @staticmethod
    def _validate_dispatch_binding(request: dict, dispatch: dict) -> None:
        try:
            ordered = (
                parse_aware_timestamp(request["issued_at"])
                <= parse_aware_timestamp(dispatch["started_at"])
                < parse_aware_timestamp(request["expires_at"])
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StateError("publication dispatch time is malformed") from error
        if (
            dispatch["publication_request_id"]
            != request["publication_request_id"]
            or dispatch["request_sha256"] != request["request_sha256"]
            or not ordered
        ):
            raise StateError("publication dispatch request binding differs")

    def claim_request(self, request: dict) -> PublicationClaim | None:
        self._validate("request", request)
        self._validate_hash(request, "request_sha256")
        self._validate_request_binding(request)
        request_id = request["publication_request_id"]
        with MissionLock(self.lock_path):
            path = self._path(request_id, "request")
            if path.exists():
                self._write_once(path, request, "publication request")
                return None
            self._assert_unclaimed(request)
            self._write_once(path, request, "publication request")
            claim = PublicationClaim(request_id, request["request_sha256"])
            self._claims[request_id] = claim
            return claim

    def dispatch_once(
        self,
        claim: PublicationClaim,
        *,
        started_at: str,
        send: Callable[[], DispatchResult],
    ) -> tuple[dict, DispatchResult]:
        if not isinstance(claim, PublicationClaim):
            raise StateError("publication dispatch requires its creator capability")
        request_id = claim.publication_request_id
        with MissionLock(self.lock_path):
            if self._claims.get(request_id) is not claim:
                raise StateError("publication dispatch is not owned by the request creator")
            request = read_json(self._path(request_id, "request"))
            self._validate("request", request)
            self._validate_hash(request, "request_sha256")
            self._validate_request_binding(request)
            if claim.request_sha256 != request["request_sha256"]:
                raise StateError("publication dispatch request binding differs")
            if self._path(request_id, "receipt").exists():
                raise StateError("terminal publication receipt already exists")
            dispatch_path = self._path(request_id, "dispatch")
            if dispatch_path.exists():
                raise StateError("publication dispatch already started")
            try:
                ordered = (
                    parse_aware_timestamp(request["issued_at"])
                    <= parse_aware_timestamp(started_at)
                    < parse_aware_timestamp(request["expires_at"])
                )
            except (TypeError, ValueError):
                ordered = False
            if not ordered:
                raise StateError("publication dispatch predates its request")
            dispatch = {
                "schema_version": 1,
                "publication_request_id": request_id,
                "request_sha256": request["request_sha256"],
                "started_at": started_at,
                "dispatch_sha256": "0" * 64,
            }
            dispatch["dispatch_sha256"] = canonical_sha256(
                dispatch, "dispatch_sha256"
            )
            self._validate("dispatch", dispatch)
            self._validate_hash(dispatch, "dispatch_sha256")
            recorded = self._write_once(
                dispatch_path, dispatch, "publication dispatch"
            )
            self._claims.pop(request_id, None)
            return recorded, send()

    def record_receipt(self, receipt: dict) -> dict:
        self._validate("receipt", receipt)
        self._validate_hash(receipt, "receipt_sha256")
        request_id = receipt["publication_request_id"]
        with MissionLock(self.lock_path):
            request_path = self._path(request_id, "request")
            dispatch_path = self._path(request_id, "dispatch")
            if not request_path.exists() or not dispatch_path.exists():
                raise StateError(
                    "publication receipt requires request and dispatch records"
                )
            request = read_json(request_path)
            dispatch = read_json(dispatch_path)
            self._validate_binding(request, dispatch, receipt)
            return self._write_once(
                self._path(request_id, "receipt"),
                receipt,
                "publication receipt",
            )

    def _validate_binding(self, request: dict, dispatch: dict, receipt: dict) -> None:
        self._validate("request", request)
        self._validate("dispatch", dispatch)
        self._validate_hash(request, "request_sha256")
        self._validate_hash(dispatch, "dispatch_sha256")
        self._validate_request_binding(request)
        self._validate_dispatch_binding(request, dispatch)
        expected_mission = {
            key: request["mission"][key]
            for key in (
                "mission_id",
                "binding_id",
                "mission_authorization_id",
                "mission_state_sha256",
            )
        }
        expected_pull = {
            "head_ref": request["candidate"]["head_ref"],
            "head_sha": request["candidate"]["head_sha"],
            "base_ref": request["candidate"]["base_ref"],
            "base_sha": request["candidate"]["base_sha"],
        }
        if (
            receipt["request_sha256"] != request["request_sha256"]
            or dispatch["publication_request_id"]
            != request["publication_request_id"]
            or dispatch["request_sha256"] != request["request_sha256"]
            or receipt["mission"] != expected_mission
            or receipt["repository"] != request["repository"]
            or any(
                receipt["pull_request"][key] != value
                for key, value in expected_pull.items()
            )
            or receipt["diff"] != request["candidate"]["diff"]
        ):
            raise StateError("publication receipt request binding differs")
        suffix = request["publication_request_id"].removeprefix(
            "publication_request_"
        )
        expected_url = (
            f"https://github.com/{request['repository']['owner']}/"
            f"{request['repository']['name']}/pull/"
            f"{receipt['pull_request']['number']}"
        )
        if (
            receipt["publication_receipt_id"] != f"publication_receipt_{suffix}"
            or receipt["pull_request"]["url"] != expected_url
            or receipt["checks"]["polls"] > request["max_check_polls"]
        ):
            raise StateError("publication receipt identity or check binding differs")
        try:
            ordered = (
                parse_aware_timestamp(request["issued_at"])
                <= parse_aware_timestamp(dispatch["started_at"])
                <= parse_aware_timestamp(receipt["observed_at"])
            )
        except (TypeError, ValueError):
            ordered = False
        if not ordered:
            raise StateError("publication receipt timeline is invalid")

    def request_exists(self, request_id: str) -> bool:
        return self._path(request_id, "request").exists()

    def load(self, request_id: str) -> dict:
        request_path = self._path(request_id, "request")
        if not request_path.exists():
            raise StateError(f"publication request not found: {request_id}")
        request = read_json(request_path)
        self._validate("request", request)
        self._validate_hash(request, "request_sha256")
        self._validate_request_binding(request)
        dispatch_path = self._path(request_id, "dispatch")
        dispatch = read_json(dispatch_path) if dispatch_path.exists() else None
        if dispatch is not None:
            self._validate("dispatch", dispatch)
            self._validate_hash(dispatch, "dispatch_sha256")
            self._validate_dispatch_binding(request, dispatch)
        receipt_path = self._path(request_id, "receipt")
        receipt = read_json(receipt_path) if receipt_path.exists() else None
        if receipt is not None:
            if dispatch is None:
                raise StateError("publication journal has receipt without dispatch")
            self._validate("receipt", receipt)
            self._validate_hash(receipt, "receipt_sha256")
            self._validate_binding(request, dispatch, receipt)
        return {
            "state": "awaiting-review" if receipt is not None else "pending",
            "disposition": "awaiting-review" if receipt is not None else "reconcile-required",
            "request": request,
            "dispatch": dispatch,
            "receipt": receipt,
        }
