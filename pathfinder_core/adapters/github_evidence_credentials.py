from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Sequence

from ..merge_time import parse_aware_timestamp


EVIDENCE_BOUNDARY = "github-evidence-get-only"
REQUIRED_READ_PERMISSIONS = frozenset({
    "administration", "checks", "contents", "deployments", "metadata",
    "members", "pull_requests", "statuses",
})
_BOT_LOGIN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\[bot\]$"
)
_RECEIPT_ID = re.compile(
    r"^evidence_credential_receipt_[a-z0-9][a-z0-9_-]{7,63}$"
)
_CREDENTIAL_ID = re.compile(
    r"^evidence_credential_[a-z0-9][a-z0-9_-]{7,63}$"
)
_NODE_ID = re.compile(r"^[A-Za-z0-9_-]{4,128}={0,2}$")
_RECEIPT_FIELDS = frozenset({
    "schema_version", "credential_receipt_id", "source", "credential_id",
    "kind", "boundary", "permissions", "repository_selection",
    "repository_ids", "app_id", "app_node_id", "installation_id",
    "installation_account_id", "actor_id", "actor_node_id", "login",
    "issued_at", "expires_at", "verified_at", "suspended",
    "receipt_sha256",
})


class GitHubEvidenceCredential:
    __slots__ = ("_token", "kind", "permissions")

    def __init__(
        self,
        token: str,
        *,
        kind: str,
        permissions: Mapping[str, str],
        boundary: str,
    ):
        if boundary != EVIDENCE_BOUNDARY:
            raise ValueError("GitHub evidence credential requires the GET-only boundary")
        if kind not in {"app-jwt", "installation-token"}:
            raise ValueError("GitHub evidence credential kind is unsupported")
        if not isinstance(token, str) or not 20 <= len(token) <= 4096:
            raise ValueError("GitHub evidence credential is missing or malformed")
        if any(character in token for character in "\r\n\0"):
            raise ValueError("GitHub evidence credential contains a forbidden character")
        normalized = dict(permissions)
        if any(value != "read" for value in normalized.values()):
            raise ValueError("GitHub evidence credential may declare read permissions only")
        if kind == "installation-token" and normalized.keys() != REQUIRED_READ_PERMISSIONS:
            raise ValueError("GitHub installation evidence permissions must be exact")
        if kind == "app-jwt" and normalized:
            raise ValueError("GitHub App JWT must not declare repository permissions")
        self._token = token
        self.kind = kind
        self.permissions = MappingProxyType(normalized)

    def _authorization(self) -> str:
        return f"Bearer {self._token}"

    def __repr__(self) -> str:
        return f"GitHubEvidenceCredential(kind={self.kind!r}, token=<redacted>)"


class GitHubEvidenceCredentialReceipt:
    """Host-authenticated identity and issuance facts for one observer token."""

    __slots__ = (
        "credential_receipt_id", "source", "credential_id", "permissions",
        "repository_selection", "repository_ids", "app_id", "app_node_id",
        "installation_id", "installation_account_id", "actor_id",
        "actor_node_id", "login", "issued_at", "expires_at", "verified_at",
        "suspended",
    )

    def __init__(
        self,
        *,
        credential_receipt_id: str,
        source: str,
        credential_id: str,
        kind: str,
        boundary: str,
        permissions: Mapping[str, str],
        repository_selection: str,
        repository_ids: Sequence[int],
        app_id: int,
        app_node_id: str,
        installation_id: int,
        installation_account_id: int,
        actor_id: int,
        actor_node_id: str,
        login: str,
        issued_at: str,
        expires_at: str,
        verified_at: str,
        suspended: bool,
    ):
        if source != "authenticated-host-credential-store":
            raise ValueError("GitHub evidence credential receipt source is not authenticated")
        if (
            not isinstance(credential_receipt_id, str)
            or _RECEIPT_ID.fullmatch(credential_receipt_id) is None
        ):
            raise ValueError("GitHub evidence credential receipt identity is malformed")
        if (
            not isinstance(credential_id, str)
            or _CREDENTIAL_ID.fullmatch(credential_id) is None
        ):
            raise ValueError("GitHub evidence credential identity is malformed")
        if kind != "installation-token" or boundary != EVIDENCE_BOUNDARY:
            raise ValueError("GitHub evidence credential receipt boundary is invalid")
        normalized_permissions = dict(permissions)
        if normalized_permissions != {
            name: "read" for name in REQUIRED_READ_PERMISSIONS
        }:
            raise ValueError("GitHub evidence credential receipt permissions must be exact")
        repositories = tuple(repository_ids)
        if (
            repository_selection != "selected"
            or len(repositories) != 1
            or not isinstance(repositories[0], int)
            or isinstance(repositories[0], bool)
            or repositories[0] < 1
        ):
            raise ValueError("GitHub evidence credential must select exactly one repository")
        identifiers = (
            app_id, installation_id, installation_account_id, actor_id,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in identifiers
        ):
            raise ValueError("GitHub evidence credential identity is malformed")
        if any(
            not isinstance(value, str) or _NODE_ID.fullmatch(value) is None
            for value in (app_node_id, actor_node_id)
        ):
            raise ValueError("GitHub evidence credential node identity is malformed")
        if not isinstance(login, str) or _BOT_LOGIN.fullmatch(login) is None:
            raise ValueError("GitHub evidence credential actor must be a bot")
        if suspended is not False:
            raise ValueError("GitHub evidence credential installation is suspended")
        try:
            issued = parse_aware_timestamp(issued_at)
            expires = parse_aware_timestamp(expires_at)
            verified = parse_aware_timestamp(verified_at)
        except (TypeError, ValueError) as error:
            raise ValueError("GitHub evidence credential window is malformed") from error
        if not issued < expires <= issued + timedelta(hours=1):
            raise ValueError("GitHub evidence credential window exceeds one hour")
        if not issued <= verified < expires:
            raise ValueError("GitHub evidence credential verification time is invalid")

        self.credential_receipt_id = credential_receipt_id
        self.source = source
        self.credential_id = credential_id
        self.permissions = MappingProxyType(normalized_permissions)
        self.repository_selection = repository_selection
        self.repository_ids = repositories
        self.app_id = app_id
        self.app_node_id = app_node_id
        self.installation_id = installation_id
        self.installation_account_id = installation_account_id
        self.actor_id = actor_id
        self.actor_node_id = actor_node_id
        self.login = login
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.verified_at = verified_at
        self.suspended = suspended

    @classmethod
    def from_document(cls, document: Mapping[str, object]):
        if not isinstance(document, Mapping) or set(document) != _RECEIPT_FIELDS:
            raise ValueError("GitHub evidence credential receipt shape is invalid")
        payload = {
            key: value for key, value in document.items() if key != "receipt_sha256"
        }
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if document["receipt_sha256"] != expected:
            raise ValueError("GitHub evidence credential receipt hash differs")
        if document["schema_version"] != 1:
            raise ValueError("GitHub evidence credential receipt version is unsupported")
        return cls(**{
            key: value for key, value in document.items()
            if key not in {"schema_version", "receipt_sha256"}
        })

    def receipt_document(self) -> dict:
        document = {
            "schema_version": 1,
            "credential_receipt_id": self.credential_receipt_id,
            "source": self.source,
            "credential_id": self.credential_id,
            "kind": "installation-token",
            "boundary": EVIDENCE_BOUNDARY,
            "permissions": dict(self.permissions),
            "repository_selection": self.repository_selection,
            "repository_ids": list(self.repository_ids),
            "app_id": self.app_id,
            "app_node_id": self.app_node_id,
            "installation_id": self.installation_id,
            "installation_account_id": self.installation_account_id,
            "actor_id": self.actor_id,
            "actor_node_id": self.actor_node_id,
            "login": self.login,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "verified_at": self.verified_at,
            "suspended": self.suspended,
            "receipt_sha256": "0" * 64,
        }
        payload = {
            key: value for key, value in document.items() if key != "receipt_sha256"
        }
        document["receipt_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return document

    def validate_binding(
        self,
        credential: GitHubEvidenceCredential,
        *,
        repository_id: int,
        observed_at: datetime,
    ) -> None:
        if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
            raise ValueError("GitHub evidence observation time requires a UTC offset")
        if credential.kind != "installation-token" or dict(credential.permissions) != dict(
            self.permissions
        ):
            raise ValueError("GitHub evidence credential declaration differs from its receipt")
        if repository_id != self.repository_ids[0]:
            raise ValueError("GitHub evidence credential repository binding differs")
        if parse_aware_timestamp(self.verified_at) != observed_at:
            raise ValueError("GitHub evidence credential receipt is not fresh")
        if not (
            parse_aware_timestamp(self.issued_at)
            <= observed_at
            < parse_aware_timestamp(self.expires_at)
        ):
            raise ValueError("GitHub evidence credential is not current")

    def __repr__(self) -> str:
        return (
            "GitHubEvidenceCredentialReceipt("
            f"app_id={self.app_id}, installation_id={self.installation_id}, "
            f"repository_id={self.repository_ids[0]})"
        )
