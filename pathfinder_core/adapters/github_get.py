from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.client import HTTPException
from typing import Callable, Mapping

from .github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
    GitHubEvidenceCredentialReceipt,
)
from .github_get_transport import (
    API_HOST,
    GETTransport,
    GitHubHTTPSGETTransport,
    RawGETResponse,
)
from .github_get_policy import (
    MAX_PAGES,
    redirect_evidence_target,
    validate_evidence_target,
)
from .github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)


API_VERSION = "2026-03-10"
ACCEPT = "application/vnd.github+json"
USER_AGENT = "pathfinder-github-get/3"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_UPGRADE_REQUIRED = (
    "Upgrade to GitHub Pro or make this repository public to enable this feature."
)
_FEATURE_PERMISSIONS = {
    "classic-protection": "administration=read",
    "active-rules": "metadata=read",
    "source-rulesets": "metadata=read",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class JSONGETResponse:
    data: object = field(repr=False)
    audit: RequestAudit
    headers: Mapping[str, str]
    status: int


@dataclass(frozen=True)
class QualifiedFeatureResponse:
    data: object = field(repr=False)
    status: int
    audit: RequestAudit


class GitHubGETClient:
    def __init__(
        self,
        credential: GitHubEvidenceCredential,
        *,
        transport: GETTransport | None = None,
        timeout: float = 10.0,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        max_pages: int = MAX_PAGES,
        max_retries: int = 1,
        max_redirects: int = 2,
        clock: Callable[[], str] = _utc_now,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if not 0.1 <= timeout <= 30:
            raise ValueError("GitHub GET timeout must be between 0.1 and 30 seconds")
        if not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("GitHub GET response ceiling is out of bounds")
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError("GitHub GET page ceiling is out of bounds")
        if not 0 <= max_retries <= 1 or not 0 <= max_redirects <= 2:
            raise ValueError("GitHub GET retry or redirect ceiling is out of bounds")
        self.credential = credential
        self.transport = transport or GitHubHTTPSGETTransport()
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.max_redirects = max_redirects
        self.clock = clock
        self.sleeper = sleeper

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": ACCEPT,
            "Authorization": self.credential._authorization(),
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }

    @staticmethod
    def _headers_lower(headers: Mapping[str, str]) -> dict[str, str]:
        return {str(key).lower(): str(value) for key, value in headers.items()}

    def _response(
        self,
        surface: str,
        target: str,
        *,
        allowed_statuses: frozenset[int] = frozenset(),
    ) -> RawGETResponse:
        retries = redirects = 0
        current = validate_evidence_target(target)
        while True:
            try:
                response = self.transport.get(
                    current, self._headers(), timeout=self.timeout,
                    max_bytes=self.max_response_bytes,
                )
            except TimeoutError:
                if retries < self.max_retries:
                    retries += 1
                    self.sleeper(0.25)
                    continue
                raise GitHubObservationError(
                    ObservationOutcome.TIMEOUT, surface, "GitHub GET timed out"
                ) from None
            except (OSError, HTTPException):
                if retries < self.max_retries:
                    retries += 1
                    self.sleeper(0.25)
                    continue
                raise GitHubObservationError(
                    ObservationOutcome.API_UNAVAILABLE, surface,
                    "GitHub GET transport unavailable",
                ) from None
            except ValueError:
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE, surface,
                    "GitHub GET response exceeded a safety bound",
                ) from None
            if len(response.body) > self.max_response_bytes:
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE, surface,
                    "GitHub GET response exceeded the byte ceiling",
                )
            headers = self._headers_lower(response.headers)
            if response.status in {301, 302, 307, 308}:
                if redirects >= self.max_redirects or "location" not in headers:
                    raise GitHubObservationError(
                        ObservationOutcome.API_UNAVAILABLE, surface,
                        "GitHub GET redirect could not be followed safely",
                    )
                try:
                    current = redirect_evidence_target(headers["location"])
                except ValueError:
                    raise GitHubObservationError(
                        ObservationOutcome.API_UNAVAILABLE, surface,
                        "GitHub GET redirect left the fixed TLS boundary",
                    ) from None
                redirects += 1
                continue
            if response.status in {500, 502, 503, 504} and retries < self.max_retries:
                retries += 1
                self.sleeper(0.25)
                continue
            if response.status not in allowed_statuses:
                self._raise_status(surface, response.status, headers)
            return RawGETResponse(response.status, headers, response.body)

    @staticmethod
    def _raise_status(surface: str, status: int, headers: Mapping[str, str]) -> None:
        candidate = headers.get("x-github-request-id", "")
        request_id = candidate if _REQUEST_ID.fullmatch(candidate) else "unavailable"
        detail = f"GitHub GET failed with status {status}; request id {request_id}"
        if 200 <= status < 300:
            return
        if status == 401:
            outcome = ObservationOutcome.AUTH_ERROR
        elif status == 429 or (
            status == 403
            and ("retry-after" in headers or headers.get("x-ratelimit-remaining") == "0")
        ):
            outcome = ObservationOutcome.RATE_LIMITED
        elif status == 403:
            outcome = ObservationOutcome.PERMISSION_MISSING
        elif status == 404:
            outcome = ObservationOutcome.NOT_FOUND
        elif status == 410 or status >= 500:
            outcome = ObservationOutcome.API_UNAVAILABLE
        else:
            outcome = ObservationOutcome.MALFORMED_RESPONSE
        raise GitHubObservationError(outcome, surface, detail)

    def get_json(self, surface: str, target: str) -> JSONGETResponse:
        response = self._response(surface, target)
        decoded = self._decode_json(surface, response)
        if decoded.status != 200:
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                surface,
                "GitHub GET returned an unexpected success status",
            )
        return decoded

    def _decode_json(
        self, surface: str, response: RawGETResponse
    ) -> JSONGETResponse:
        headers = self._headers_lower(response.headers)
        request_id = headers.get("x-github-request-id")
        if not request_id or not _REQUEST_ID.fullmatch(request_id):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE, surface,
                "GitHub GET response omitted its request id",
            )
        try:
            data = json.loads(response.body, object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE, surface,
                "GitHub GET returned malformed JSON",
            ) from None
        return JSONGETResponse(
            data,
            RequestAudit(request_id, self.clock(), headers.get("etag")),
            headers,
            response.status,
        )

    def get_qualified_feature(
        self,
        surface: str,
        target: str,
        *,
        feature: str,
    ) -> QualifiedFeatureResponse:
        """Read one plan-gated feature, accepting only a qualified upgrade 403."""
        required_permission = _FEATURE_PERMISSIONS.get(feature)
        if surface != feature or required_permission is None:
            raise ValueError("GitHub feature absence surface is unsupported")
        if (
            feature == "classic-protection"
            and not re.fullmatch(
                r"/repos/[^/]+/[^/]+/branches/[^/]+/protection", target
            )
        ) or (
            feature == "active-rules"
            and not re.fullmatch(
                r"/repos/[^/]+/[^/]+/rules/branches/[^/]+", target
            )
        ) or (
            feature == "source-rulesets"
            and not re.fullmatch(
                r"/repos/[^/]+/[^/]+/rulesets(?:\?includes_parents=true)?",
                target,
            )
        ):
            raise ValueError("GitHub feature absence target does not match its surface")
        response = self._response(surface, target, allowed_statuses=frozenset({403}))
        decoded = self._decode_json(surface, response)
        accepted = {
            item.strip()
            for item in decoded.headers.get(
                "x-accepted-github-permissions", ""
            ).split(";")
            if item.strip()
        }
        qualified = required_permission in accepted
        audit = RequestAudit(
            decoded.audit.request_id,
            decoded.audit.observed_at,
            decoded.audit.etag,
            target,
            response.status,
            qualified,
        )
        if response.status not in {200, 403}:
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                surface,
                "GitHub feature response returned an unexpected status",
            )
        if response.status == 200:
            if not qualified:
                raise GitHubObservationError(
                    ObservationOutcome.PERMISSION_MISSING,
                    surface,
                    "GitHub feature response did not qualify the required permission",
                )
            return QualifiedFeatureResponse(decoded.data, response.status, audit)
        error = decoded.data
        if (
            not qualified
            or not isinstance(error, Mapping)
            or set(error) != {"message", "documentation_url", "status"}
            or error["message"] != _UPGRADE_REQUIRED
            or error["status"] != "403"
            or not isinstance(error["documentation_url"], str)
            or not error["documentation_url"].startswith(
                "https://docs.github.com/rest/"
            )
        ):
            raise GitHubObservationError(
                ObservationOutcome.PERMISSION_MISSING,
                surface,
                "GitHub feature access was denied without qualified absence proof",
            )
        return QualifiedFeatureResponse(None, response.status, audit)

    def get_qualified_repository_permission(
        self, surface: str, target: str
    ) -> QualifiedFeatureResponse:
        """Read one exact collaborator permission with positive scope evidence."""
        if surface not in {"bypass-memberships", "reviews"} or re.fullmatch(
            r"/repos/[^/]+/[^/]+/collaborators/[^/]+/permission", target
        ) is None:
            raise ValueError("GitHub repository permission target is unsupported")
        response = self._response(surface, target)
        decoded = self._decode_json(surface, response)
        if response.status != 200:
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                surface,
                "GitHub repository permission returned an unexpected status",
            )
        accepted = {
            item.strip().lower()
            for item in decoded.headers.get(
                "x-accepted-github-permissions", ""
            ).split(";")
            if item.strip()
        }
        if "metadata=read" not in accepted:
            raise GitHubObservationError(
                ObservationOutcome.PERMISSION_MISSING,
                surface,
                "GitHub repository permission response did not qualify Metadata read",
            )
        if not isinstance(decoded.data, Mapping):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                surface,
                "GitHub repository permission response is not an object",
            )
        return QualifiedFeatureResponse(
            decoded.data,
            response.status,
            RequestAudit(
                decoded.audit.request_id,
                decoded.audit.observed_at,
                decoded.audit.etag,
                target,
                response.status,
                True,
            ),
        )

    def get_endpoint(self, surface: str, target: str) -> EndpointResponse:
        response = self.get_json(surface, target)
        if not isinstance(response.data, Mapping):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE, surface,
                "GitHub GET endpoint did not return an object",
            )
        return EndpointResponse(response.data, response.audit)

    def get_pages(
        self,
        surface: str,
        target: str,
        *,
        item_key: str | None = None,
        total_key: str | None = None,
        page_limit: int | None = None,
    ) -> PageResponse:
        limit = self.max_pages if page_limit is None else page_limit
        if not 1 <= limit <= self.max_pages:
            raise ValueError("GitHub GET page limit is out of bounds")
        separator = "&" if "?" in target else "?"
        current = f"{target}{separator}per_page=100"
        items: list[Mapping[str, object]] = []
        audits = []
        expected_total = None
        last_cursor = None
        for page_number in range(1, limit + 1):
            response = self.get_json(surface, current)
            if any(
                audit.request_id == response.audit.request_id
                for audit in audits
            ):
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    surface,
                    "GitHub GET request id was reused during pagination",
                )
            audits.append(response.audit)
            payload = response.data
            if item_key is not None:
                if not isinstance(payload, Mapping) or not isinstance(payload.get(item_key), list):
                    raise GitHubObservationError(
                        ObservationOutcome.MALFORMED_RESPONSE, surface,
                        "GitHub GET page shape is malformed",
                    )
                page_items = payload[item_key]
                if total_key and page_number == 1:
                    expected_total = payload.get(total_key)
                    if (
                        not isinstance(expected_total, int)
                        or isinstance(expected_total, bool)
                        or expected_total < 0
                    ):
                        raise GitHubObservationError(
                            ObservationOutcome.MALFORMED_RESPONSE,
                            surface,
                            "GitHub GET page total is malformed",
                        )
            else:
                page_items = payload
            if not isinstance(page_items, list) or any(not isinstance(item, Mapping) for item in page_items):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE, surface,
                    "GitHub GET page items are malformed",
                )
            items.extend(page_items)
            try:
                next_target = self._next_link(response.headers.get("link"))
            except ValueError:
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE, surface,
                    "GitHub GET pagination link is malformed or unsafe",
                ) from None
            if next_target is None:
                total = expected_total if isinstance(expected_total, int) else len(items)
                if total_key and not isinstance(expected_total, int):
                    raise GitHubObservationError(
                        ObservationOutcome.MALFORMED_RESPONSE, surface,
                        "GitHub GET page omitted its total count",
                    )
                if total != len(items):
                    return PageResponse(
                        tuple(items), page_number, total, False, True,
                        current, tuple(audits),
                    )
                return PageResponse(
                    tuple(items), page_number, total, True, False, None, tuple(audits)
                )
            current = next_target
            last_cursor = next_target
        total = expected_total if isinstance(expected_total, int) else len(items)
        return PageResponse(
            tuple(items), limit, total, False, True, last_cursor, tuple(audits)
        )

    @classmethod
    def _next_link(cls, header: str | None) -> str | None:
        if not header:
            return None
        for part in header.split(","):
            section = part.strip()
            if 'rel="next"' in section:
                if not section.startswith("<") or ">" not in section:
                    raise ValueError("malformed next link")
                return redirect_evidence_target(section[1:section.index(">")])
        return None

    def verify_api_version(self) -> RequestAudit:
        response = self.get_json("api-version", "/versions")
        if not isinstance(response.data, list) or API_VERSION not in response.data:
            raise GitHubObservationError(
                ObservationOutcome.API_UNAVAILABLE, "api-version",
                "pinned GitHub REST API version is not supported",
            )
        return response.audit

    @staticmethod
    def graphql_unavailable(surface: str) -> None:
        raise GitHubObservationError(
            ObservationOutcome.API_UNAVAILABLE, surface,
            "GitHub GraphQL evidence requires POST and is outside the GET-only boundary",
        )
