from __future__ import annotations

import http.client
import ssl
from dataclasses import dataclass, field
from typing import Mapping, Protocol


API_HOST = "api.github.com"


@dataclass(frozen=True)
class RawGETResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes = field(repr=False)


class GETTransport(Protocol):
    def get(
        self, path: str, headers: Mapping[str, str], *, timeout: float, max_bytes: int
    ) -> RawGETResponse: ...


class GitHubHTTPSGETTransport:
    """Fixed-host TLS transport exposing only GET."""

    def get(
        self, path: str, headers: Mapping[str, str], *, timeout: float, max_bytes: int
    ) -> RawGETResponse:
        connection = http.client.HTTPSConnection(
            API_HOST, 443, timeout=timeout, context=ssl.create_default_context()
        )
        try:
            connection.request("GET", path, headers=dict(headers))
            response = connection.getresponse()
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError("GitHub response exceeded the byte ceiling")
            return RawGETResponse(response.status, dict(response.getheaders()), body)
        finally:
            connection.close()
