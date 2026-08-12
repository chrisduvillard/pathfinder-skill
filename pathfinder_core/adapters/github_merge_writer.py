from __future__ import annotations

import http.client
import json
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Protocol
from urllib.parse import quote

from ..merge_credentials import GitHubMergeCredential


API_HOST = "api.github.com"
API_VERSION = "2026-03-10"
MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 10.0


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


@dataclass(frozen=True)
class RawMergeHTTPResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes = field(repr=False)


class MergeHTTPTransport(Protocol):
    def put_merge(
        self, path: str, headers: Mapping[str, str], body: bytes, *, timeout: float,
        max_bytes: int,
    ) -> RawMergeHTTPResponse: ...

    def get_observation(
        self, path: str, headers: Mapping[str, str], *, timeout: float,
        max_bytes: int,
    ) -> RawMergeHTTPResponse: ...


class GitHubHTTPSMergeTransport:
    """Fixed-host TLS transport exposing only merge PUT and observation GET."""

    @staticmethod
    def _request(
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: bytes | None,
        *,
        timeout: float,
        max_bytes: int,
    ) -> RawMergeHTTPResponse:
        connection = http.client.HTTPSConnection(
            API_HOST, 443, timeout=timeout, context=ssl.create_default_context()
        )
        try:
            connection.request(method, path, body=body, headers=dict(headers))
            response = connection.getresponse()
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ConnectionError("GitHub merge response exceeded the byte ceiling")
            return RawMergeHTTPResponse(
                response.status, dict(response.getheaders()), payload
            )
        finally:
            connection.close()

    def put_merge(
        self, path: str, headers: Mapping[str, str], body: bytes, *, timeout: float,
        max_bytes: int,
    ) -> RawMergeHTTPResponse:
        return self._request(
            "PUT", path, headers, body, timeout=timeout, max_bytes=max_bytes
        )

    def get_observation(
        self, path: str, headers: Mapping[str, str], *, timeout: float,
        max_bytes: int,
    ) -> RawMergeHTTPResponse:
        return self._request(
            "GET", path, headers, None, timeout=timeout, max_bytes=max_bytes
        )


class MergeResponseLost(ConnectionError):
    """The caller cannot prove whether the merge mutation took effect."""


@dataclass(frozen=True)
class MergeAPIResponse:
    status: int
    request_id: str | None
    headers: Mapping[str, str]
    document: Mapping[str, object] | None
    malformed: bool


@dataclass(frozen=True)
class MergeObservation:
    document: Mapping[str, object] | None
    complete: bool


class GitHubMergeBackend:
    """Exact GitHub squash endpoint plus bounded post-mutation observation."""

    def __init__(
        self,
        transport: MergeHTTPTransport | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.transport = transport or GitHubHTTPSMergeTransport()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _base_target(intent: Mapping[str, object]) -> str:
        repository = intent["repository"]
        pull_request = intent["pull_request"]
        owner = quote(str(repository["owner"]), safe="")
        name = quote(str(repository["name"]), safe="")
        return f"/repos/{owner}/{name}/pulls/{pull_request['number']}"

    @staticmethod
    def _headers(credential: GitHubMergeCredential, *, json_body: bool = False) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": credential._authorization(),
            "User-Agent": "pathfinder-merge-executor/1",
            "X-GitHub-Api-Version": API_VERSION,
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def _json(response: RawMergeHTTPResponse) -> Mapping[str, object] | None:
        try:
            value = json.loads(
                response.body.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (UnicodeDecodeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def merge(
        self,
        intent: Mapping[str, object],
        credential: GitHubMergeCredential,
        *,
        dispatch: Callable[[], None],
    ) -> MergeAPIResponse:
        target = self._base_target(intent) + "/merge"
        body = json.dumps(
            {
                "sha": intent["pull_request"]["head_sha"],
                "merge_method": "squash",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        headers = self._headers(credential, json_body=True)
        try:
            dispatch()
            response = self.transport.put_merge(
                target,
                headers,
                body,
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_bytes=MAX_RESPONSE_BYTES,
            )
        except (ConnectionError, OSError, TimeoutError, http.client.HTTPException) as error:
            raise MergeResponseLost("GitHub merge response was not observed") from error
        document = self._json(response) if response.body else None
        malformed = response.status == 200 and (
            document is None
            or not isinstance(document.get("merged"), bool)
            or not isinstance(document.get("message"), str)
            or (
                document.get("merged") is True
                and (
                    not isinstance(document.get("sha"), str)
                    or len(document["sha"]) != 40
                    or any(character not in "0123456789abcdef" for character in document["sha"])
                )
            )
        )
        return MergeAPIResponse(
            response.status,
            _header(response.headers, "X-GitHub-Request-Id"),
            response.headers,
            document,
            malformed,
        )

    def _get(
        self, target: str, credential: GitHubMergeCredential
    ) -> tuple[RawMergeHTTPResponse, Mapping[str, object] | None, str | None]:
        response = self.transport.get_observation(
            target,
            self._headers(credential),
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_bytes=MAX_RESPONSE_BYTES,
        )
        document = self._json(response) if response.body else None
        return response, document, _header(response.headers, "X-GitHub-Request-Id")

    def observe(
        self, intent: Mapping[str, object], credential: GitHubMergeCredential
    ) -> MergeObservation:
        base_target = self._base_target(intent)
        repository = intent["repository"]
        base_ref = quote(str(repository["base_branch"]), safe="/._-")
        prefix = base_target.rsplit("/pulls/", 1)[0]
        request_ids: list[str] = []
        try:
            pr_response, pull, request_id = self._get(base_target, credential)
            if request_id:
                request_ids.append(request_id)
            if pr_response.status != 200 or pull is None:
                return MergeObservation(None, False)
            merge_sha = pull.get("merge_commit_sha")
            if not isinstance(merge_sha, str) or len(merge_sha) != 40:
                return MergeObservation(None, False)

            merged_response, _empty, request_id = self._get(
                base_target + "/merge", credential
            )
            if request_id:
                request_ids.append(request_id)
            ref_response, ref_document, request_id = self._get(
                f"{prefix}/git/ref/heads/{base_ref}", credential
            )
            if request_id:
                request_ids.append(request_id)
            commit_response, commit, request_id = self._get(
                f"{prefix}/git/commits/{merge_sha}", credential
            )
            if request_id:
                request_ids.append(request_id)

            head = pull.get("head")
            base = pull.get("base")
            merged_by = pull.get("merged_by")
            ref_object = ref_document.get("object") if isinstance(ref_document, dict) else None
            parents = commit.get("parents") if isinstance(commit, dict) else None
            complete = (
                merged_response.status == 204
                and ref_response.status == 200
                and commit_response.status == 200
                and len(request_ids) == 4
                and len(set(request_ids)) == 4
                and isinstance(head, dict)
                and isinstance(head.get("repo"), dict)
                and isinstance(base, dict)
                and isinstance(base.get("repo"), dict)
                and isinstance(merged_by, dict)
                and isinstance(ref_object, dict)
                and isinstance(parents, list)
                and all(isinstance(parent, dict) for parent in parents)
                and commit.get("sha") == merge_sha
            )
            if not complete:
                return MergeObservation(None, False)
            document = {
                "repository_id": base["repo"].get("id"),
                "repository_node_id": base["repo"].get("node_id"),
                "pull_request_id": pull.get("id"),
                "pull_request_node_id": pull.get("node_id"),
                "pull_request_number": pull.get("number"),
                "state": pull.get("state"),
                "merged": pull.get("merged"),
                "head_sha": head.get("sha"),
                "head_repository_id": head["repo"].get("id"),
                "base_ref": base.get("ref"),
                "base_repository_id": base["repo"].get("id"),
                "merge_commit_sha": merge_sha,
                "merged_at": pull.get("merged_at"),
                "merged_by": {
                    "actor_id": merged_by.get("id"),
                    "actor_node_id": merged_by.get("node_id"),
                    "login": merged_by.get("login"),
                },
                "merge_endpoint_status": merged_response.status,
                "base_sha_after": ref_object.get("sha"),
                "merge_commit_parent_shas": [parent.get("sha") for parent in parents],
                "request_ids": request_ids,
                "observed_at": self.clock().isoformat(),
            }
            return MergeObservation(document, True)
        except (ConnectionError, OSError, TimeoutError, http.client.HTTPException, TypeError):
            return MergeObservation(None, False)
