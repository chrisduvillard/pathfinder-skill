from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from ..merge_time import parse_aware_timestamp
from .github_evidence_credentials import GitHubEvidenceCredentialReceipt
from .github_get import GitHubGETClient
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)


MERGE_RECEIPT_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "publication"
    / "merge-credential-receipt.schema.json"
)


def _error(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(
        ObservationOutcome.ACTOR_IDENTITY_UNKNOWN, surface, detail
    )


def _mapping(value: object, surface: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _error(surface, "GitHub identity response is not an object")
    return value


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _error(surface, "GitHub identity response has an invalid integer")
    return value


def _string(value: object, surface: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(surface, "GitHub identity response has an invalid string")
    return value


def _canonical_sha256(document: Mapping[str, object], field: str) -> str:
    payload = {key: value for key, value in document.items() if key != field}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class VerifiedObserverIdentity:
    repository: Mapping[str, object]
    credential_receipt: Mapping[str, object]
    requests: tuple[RequestAudit, ...]


@dataclass(frozen=True)
class VerifiedMergeActorIdentity:
    actor: Mapping[str, object]
    credential_receipt: Mapping[str, object]
    requests: tuple[RequestAudit, ...]


class GitHubIdentityVerifier:
    """Cross-check host credential receipts against exact live GitHub identities."""

    def __init__(
        self,
        *,
        observer_app: GitHubGETClient,
        observer_installation: GitHubGETClient,
        merge_app: GitHubGETClient,
    ):
        if observer_app.credential.kind != "app-jwt":
            raise ValueError("observer identity requires its App JWT boundary")
        if observer_installation.credential.kind != "installation-token":
            raise ValueError("observer identity requires its installation boundary")
        if merge_app.credential.kind != "app-jwt":
            raise ValueError("merge actor identity requires its App JWT boundary")
        self.observer_app = observer_app
        self.observer_installation = observer_installation
        self.merge_app = merge_app

    @staticmethod
    def _app(
        response: Mapping[str, object],
        *,
        app_id: int,
        app_node_id: str,
        surface: str,
    ) -> None:
        if (
            _positive_int(response.get("id"), surface) != app_id
            or _string(response.get("node_id"), surface) != app_node_id
            or not _string(response.get("slug"), surface)
        ):
            raise _error(surface, "GitHub App identity differs from the host receipt")

    @staticmethod
    def _installation(
        response: Mapping[str, object],
        *,
        app_id: int,
        installation_id: int,
        account_id: int,
        permissions: Mapping[str, str],
        surface: str,
    ) -> None:
        account = _mapping(response.get("account"), f"{surface}.account")
        observed_permissions = _mapping(
            response.get("permissions"), f"{surface}.permissions"
        )
        if (
            _positive_int(response.get("id"), surface) != installation_id
            or _positive_int(response.get("app_id"), surface) != app_id
            or _positive_int(account.get("id"), f"{surface}.account") != account_id
            or response.get("repository_selection") != "selected"
            or dict(observed_permissions) != dict(permissions)
            or response.get("suspended_at") is not None
        ):
            raise _error(
                surface,
                "GitHub installation identity or permission boundary differs",
            )

    @staticmethod
    def _actor(
        response: Mapping[str, object],
        *,
        actor_id: int,
        actor_node_id: str,
        login: str,
        surface: str,
    ) -> None:
        if (
            _positive_int(response.get("id"), surface) != actor_id
            or _string(response.get("node_id"), surface) != actor_node_id
            or response.get("login") != login
            or response.get("type") != "Bot"
            or response.get("site_admin") is not False
        ):
            raise _error(surface, "GitHub bot identity differs from the host receipt")

    @staticmethod
    def _repository(
        response: Mapping[str, object],
        *,
        repository_id: int,
        owner: str,
        name: str,
        account_id: int,
        expected_node_id: str | None,
    ) -> dict:
        surface = "observer-repository"
        account = _mapping(response.get("owner"), f"{surface}.owner")
        node_id = _string(response.get("node_id"), surface)
        if (
            _positive_int(response.get("id"), surface) != repository_id
            or (expected_node_id is not None and node_id != expected_node_id)
            or response.get("name") != name
            or response.get("full_name") != f"{owner}/{name}"
            or account.get("login") != owner
            or _positive_int(account.get("id"), f"{surface}.owner") != account_id
        ):
            raise _error(surface, "GitHub repository identity differs from the host receipt")
        boolean_fields = (
            "archived", "disabled", "allow_squash_merge",
            "allow_merge_commit", "allow_rebase_merge",
        )
        if any(not isinstance(response.get(field), bool) for field in boolean_fields):
            raise _error(surface, "GitHub repository settings are incomplete")
        default_branch = _string(response.get("default_branch"), surface)
        return {
            "id": repository_id,
            "node_id": node_id,
            "owner": {"login": owner},
            "name": name,
            "default_branch": default_branch,
            "archived": response["archived"],
            "disabled": response["disabled"],
            "allow_squash_merge": response["allow_squash_merge"],
            "allow_merge_commit": response["allow_merge_commit"],
            "allow_rebase_merge": response["allow_rebase_merge"],
        }

    def verify_observer(
        self,
        receipt: GitHubEvidenceCredentialReceipt,
        *,
        owner: str,
        name: str,
        repository_node_id: str | None,
        observed_at: datetime,
    ) -> VerifiedObserverIdentity:
        receipt.validate_binding(
            self.observer_installation.credential,
            repository_id=receipt.repository_ids[0],
            observed_at=observed_at,
        )
        app = self.observer_app.get_endpoint("actor", "/app")
        installation = self.observer_app.get_endpoint(
            "actor", f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/installation"
        )
        actor = self.observer_installation.get_endpoint(
            "actor", f"/users/{quote(receipt.login, safe='')}"
        )
        repository = self.observer_installation.get_endpoint(
            "repository", f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        )
        self._app(
            app.data,
            app_id=receipt.app_id,
            app_node_id=receipt.app_node_id,
            surface="observer-app",
        )
        self._installation(
            installation.data,
            app_id=receipt.app_id,
            installation_id=receipt.installation_id,
            account_id=receipt.installation_account_id,
            permissions=receipt.permissions,
            surface="observer-installation",
        )
        self._actor(
            actor.data,
            actor_id=receipt.actor_id,
            actor_node_id=receipt.actor_node_id,
            login=receipt.login,
            surface="observer-actor",
        )
        normalized_repository = self._repository(
            repository.data,
            repository_id=receipt.repository_ids[0],
            owner=owner,
            name=name,
            account_id=receipt.installation_account_id,
            expected_node_id=repository_node_id,
        )
        return VerifiedObserverIdentity(
            normalized_repository,
            receipt.receipt_document(),
            (app.audit, installation.audit, actor.audit, repository.audit),
        )

    def verify_merge_actor(
        self,
        credential_receipt: Mapping[str, object],
        *,
        owner: str,
        name: str,
        repository_id: int,
        observed_at: datetime,
    ) -> VerifiedMergeActorIdentity:
        try:
            schema = json.loads(MERGE_RECEIPT_SCHEMA.read_text())
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).validate(credential_receipt)
        except (OSError, json.JSONDecodeError, SchemaError, ValidationError) as error:
            raise _error(
                "merge-actor-receipt",
                "merge actor credential receipt is invalid",
            ) from error
        if credential_receipt["receipt_sha256"] != _canonical_sha256(
            credential_receipt, "receipt_sha256"
        ):
            raise _error(
                "merge-actor-receipt",
                "merge actor credential receipt hash differs",
            )
        try:
            current = (
                parse_aware_timestamp(credential_receipt["issued_at"])
                <= observed_at
                == parse_aware_timestamp(credential_receipt["verified_at"])
                < parse_aware_timestamp(credential_receipt["expires_at"])
            )
        except (KeyError, TypeError, ValueError):
            current = False
        if not current or credential_receipt["repository_ids"] != [repository_id]:
            raise _error(
                "merge-actor-receipt",
                "merge actor credential receipt is not current for the repository",
            )

        app = self.merge_app.get_endpoint("actor", "/app")
        installation = self.merge_app.get_endpoint(
            "actor", f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}/installation"
        )
        actor = self.observer_installation.get_endpoint(
            "actor",
            f"/users/{quote(str(credential_receipt['login']), safe='')}",
        )
        self._app(
            app.data,
            app_id=credential_receipt["app_id"],
            app_node_id=credential_receipt["app_node_id"],
            surface="merge-app",
        )
        self._installation(
            installation.data,
            app_id=credential_receipt["app_id"],
            installation_id=credential_receipt["installation_id"],
            account_id=credential_receipt["installation_account_id"],
            permissions=credential_receipt["permissions"],
            surface="merge-installation",
        )
        self._actor(
            actor.data,
            actor_id=credential_receipt["actor_id"],
            actor_node_id=credential_receipt["actor_node_id"],
            login=credential_receipt["login"],
            surface="merge-actor",
        )
        return VerifiedMergeActorIdentity(
            {
                "app": {
                    "id": credential_receipt["app_id"],
                    "node_id": credential_receipt["app_node_id"],
                },
                "installation": {
                    "id": credential_receipt["installation_id"],
                    "account_id": credential_receipt["installation_account_id"],
                },
                "user": {
                    "id": credential_receipt["actor_id"],
                    "node_id": credential_receipt["actor_node_id"],
                    "login": credential_receipt["login"],
                    "suspended": credential_receipt["suspended"],
                },
                "permissions": {"administration": "none"},
            },
            dict(credential_receipt),
            (app.audit, installation.audit, actor.audit),
        )
