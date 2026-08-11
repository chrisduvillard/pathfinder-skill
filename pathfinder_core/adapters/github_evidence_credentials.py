from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


EVIDENCE_BOUNDARY = "github-evidence-get-only"
REQUIRED_READ_PERMISSIONS = frozenset({
    "administration", "checks", "contents", "deployments", "metadata",
    "pull_requests", "statuses",
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
