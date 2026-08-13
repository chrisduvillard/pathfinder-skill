from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Sequence

from .errors import StateError
from .merge_time import parse_aware_timestamp


MERGE_EXECUTOR_BOUNDARY = "github-merge-executor"
REQUIRED_MERGE_PERMISSIONS = {
    "contents": "write",
    "metadata": "read",
    "pull_requests": "read",
}
BOT_LOGIN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\[bot\]$"
)


class GitHubMergeCredential:
    """One-repository GitHub App credential for the merge executor only."""

    __slots__ = (
        "_token",
        "credential_receipt_id",
        "source",
        "credential_id",
        "permissions",
        "repository_ids",
        "app_id",
        "app_node_id",
        "installation_id",
        "installation_account_id",
        "actor_id",
        "actor_node_id",
        "login",
        "issued_at",
        "expires_at",
        "verified_at",
        "repository_selection",
        "suspended",
    )

    def __init__(
        self,
        token: str,
        *,
        credential_receipt_id: str,
        source: str,
        credential_id: str,
        kind: str,
        boundary: str,
        permissions: Mapping[str, str],
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
        repository_selection: str,
        suspended: bool,
    ):
        if source != "authenticated-host-credential-store":
            raise ValueError("GitHub merge credential receipt source is not authenticated")
        if not credential_receipt_id.startswith("merge_credential_receipt_"):
            raise ValueError("GitHub merge credential receipt identity is malformed")
        if not credential_id.startswith("merge_credential_"):
            raise ValueError("GitHub merge credential identity is malformed")
        if boundary != MERGE_EXECUTOR_BOUNDARY:
            raise ValueError("GitHub merge credential requires the executor boundary")
        if kind != "installation-token":
            raise ValueError("GitHub merge credential must be an installation token")
        if not isinstance(token, str) or not 20 <= len(token) <= 4096:
            raise ValueError("GitHub merge credential is missing or malformed")
        if any(character in token for character in "\r\n\0"):
            raise ValueError("GitHub merge credential contains a forbidden character")
        normalized_permissions = dict(permissions)
        if normalized_permissions != REQUIRED_MERGE_PERMISSIONS:
            raise ValueError("GitHub merge credential permissions must be exact")
        normalized_repositories = tuple(repository_ids)
        if (
            len(normalized_repositories) != 1
            or not isinstance(normalized_repositories[0], int)
            or isinstance(normalized_repositories[0], bool)
            or normalized_repositories[0] < 1
        ):
            raise ValueError("GitHub merge credential must select exactly one repository")
        if repository_selection != "selected":
            raise ValueError("GitHub merge credential repository selection must be selected")
        if suspended is not False:
            raise ValueError("GitHub merge credential installation is suspended")
        identifiers = (app_id, installation_id, installation_account_id, actor_id)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in identifiers
        ):
            raise ValueError("GitHub merge credential identity is malformed")
        if any(
            not isinstance(value, str) or not 4 <= len(value) <= 128
            for value in (app_node_id, actor_node_id)
        ):
            raise ValueError("GitHub merge credential actor node id is malformed")
        if not isinstance(login, str) or BOT_LOGIN.fullmatch(login) is None:
            raise ValueError("GitHub merge credential actor must be a bot")
        try:
            issued = parse_aware_timestamp(issued_at)
            expires = parse_aware_timestamp(expires_at)
            verified = parse_aware_timestamp(verified_at)
        except (TypeError, ValueError) as error:
            raise ValueError("GitHub merge credential window is malformed") from error
        if not issued < expires <= issued + timedelta(hours=1):
            raise ValueError("GitHub merge credential window exceeds one hour")
        if not issued <= verified < expires:
            raise ValueError("GitHub merge credential verification time is invalid")

        self._token = token
        self.credential_receipt_id = credential_receipt_id
        self.source = source
        self.credential_id = credential_id
        self.permissions = MappingProxyType(normalized_permissions)
        self.repository_ids = normalized_repositories
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
        self.repository_selection = repository_selection
        self.suspended = suspended

    def receipt_document(self) -> dict:
        document = {
            "schema_version": 1,
            "credential_receipt_id": self.credential_receipt_id,
            "source": self.source,
            "credential_id": self.credential_id,
            "kind": "installation-token",
            "boundary": MERGE_EXECUTOR_BOUNDARY,
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
            key: value
            for key, value in document.items()
            if key != "receipt_sha256"
        }
        document["receipt_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return document

    def validate_binding(
        self,
        repository: Mapping[str, object],
        actor: Mapping[str, object],
        *,
        now: datetime,
    ) -> None:
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise StateError("merge credential validation time requires a UTC offset")
        try:
            current = (
                parse_aware_timestamp(self.issued_at)
                <= now
                < parse_aware_timestamp(self.expires_at)
            )
        except (TypeError, ValueError):
            current = False
        if not current:
            raise StateError("merge credential is not current")
        if parse_aware_timestamp(self.verified_at) != now:
            raise StateError("merge credential receipt is not fresh")
        if repository.get("id") != self.repository_ids[0]:
            raise StateError("merge credential repository binding differs")
        expected_actor = {
            "app_id": self.app_id,
            "installation_id": self.installation_id,
            "actor_id": self.actor_id,
            "actor_node_id": self.actor_node_id,
            "login": self.login,
        }
        if dict(actor) != expected_actor:
            raise StateError("merge credential actor binding differs")

    def _authorization(self) -> str:
        return f"Bearer {self._token}"

    def __repr__(self) -> str:
        return (
            "GitHubMergeCredential("
            f"app_id={self.app_id}, installation_id={self.installation_id}, "
            "token=<redacted>)"
        )
