#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def load(path: Path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class FixtureTransport:
    def __init__(self, put_response, get_responses):
        self.put_response = put_response
        self.get_responses = list(get_responses)
        self.put_calls = []
        self.get_calls = []

    def put_merge(self, path, headers, body, *, timeout, max_bytes):
        self.put_calls.append((path, headers, body, timeout, max_bytes))
        return self.put_response

    def get_observation(self, path, headers, *, timeout, max_bytes):
        self.get_calls.append((path, headers, timeout, max_bytes))
        return self.get_responses.pop(0)


def main() -> int:
    expected = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))

    from pathfinder_core.adapters.github_merge_writer import (
        API_HOST,
        API_VERSION,
        GitHubMergeBackend,
        RawMergeHTTPResponse,
    )
    from pathfinder_core.merge_credentials import GitHubMergeCredential

    journal = load(
        root / "tests/contracts/fixtures/publication-journal-contracts.json"
    )
    intent = journal["intent"]

    for name in ("intent", "result"):
        document = journal[name]
        schema = load(root / f"schemas/publication/merge-{name}.schema.json")
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(document)
        require(
            document["schema_version"]
            == expected["artifact_contract"][f"{name}_schema_version"],
            f"merge {name} schema version drift",
        )
    require(
        journal["result"]["reason"]
        == expected["artifact_contract"]["result_reason"]
        and journal["result"]["merge_proof"]["proof_source"]
        == expected["artifact_contract"]["proof_source"],
        "terminal result contract drift",
    )

    credential_spec = expected["credential"]
    credential = GitHubMergeCredential(
        "ghs_fixture_token_1234567890",
        credential_receipt_id="merge_credential_receipt_example1",
        source="authenticated-host-credential-store",
        credential_id="merge_credential_example1",
        kind=credential_spec["kind"],
        boundary=credential_spec["boundary"],
        permissions=credential_spec["permissions"],
        repository_ids=credential_spec["repository_ids"],
        app_id=24680,
        app_node_id="A_kgDOApp1234",
        installation_id=13579,
        installation_account_id=123456789,
        actor_id=97531,
        actor_node_id="U_kgDOBot1234",
        login="pathfinder-merge[bot]",
        issued_at="2026-08-11T12:00:00+00:00",
        expires_at="2026-08-11T13:00:00+00:00",
        verified_at="2026-08-11T12:08:30+00:00",
        repository_selection="selected",
        suspended=False,
    )
    credential_schema = load(
        root / "schemas/publication/merge-credential-receipt.schema.json"
    )
    Draft202012Validator(
        credential_schema, format_checker=FormatChecker()
    ).validate(credential.receipt_document())
    require(
        intent["bindings"]["credential_receipt_id"]
        == credential.receipt_document()["credential_receipt_id"]
        and intent["bindings"]["credential_receipt_sha256"]
        == credential.receipt_document()["receipt_sha256"],
        "intent does not bind the authenticated credential receipt",
    )

    def raw(status, document, request_id):
        body = b"" if document is None else json.dumps(
            document, sort_keys=True, separators=(",", ":")
        ).encode()
        return RawMergeHTTPResponse(
            status, {"X-GitHub-Request-Id": request_id}, body
        )

    pull = {
        "id": 987654321,
        "node_id": "PR_kwDOExample1",
        "number": 72,
        "state": "closed",
        "merged": True,
        "merge_commit_sha": "d" * 40,
        "merged_at": "2026-08-11T12:08:38+00:00",
        "merged_by": {
            "id": 97531,
            "node_id": "U_kgDOBot1234",
            "login": "pathfinder-merge[bot]",
        },
        "head": {"sha": "c" * 40, "repo": {"id": 123456789}},
        "base": {
            "ref": "main",
            "repo": {"id": 123456789, "node_id": "R_kgDOExample1"},
        },
    }
    transport = FixtureTransport(
        raw(
            200,
            {"sha": "d" * 40, "merged": True, "message": "fixture"},
            "request_merge_response_example1",
        ),
        (
            raw(200, pull, "request_pr_followup_example1"),
            raw(204, None, "request_merged_followup_example1"),
            raw(
                200,
                {"object": {"sha": "d" * 40}},
                "request_base_followup_example1",
            ),
            raw(
                200,
                {"sha": "d" * 40, "parents": [{"sha": "b" * 40}]},
                "request_commit_followup_example1",
            ),
        ),
    )
    backend = GitHubMergeBackend(
        transport,
        clock=lambda: datetime.fromisoformat("2026-08-11T12:08:39+00:00"),
    )
    merge_response = backend.merge(intent, credential, dispatch=lambda: None)
    observation = backend.observe(intent, credential)

    require(API_HOST == expected["api_host"], "merge API host drift")
    require(API_VERSION == expected["api_version"], "merge API version drift")
    require(
        len(transport.put_calls) == 1
        and transport.put_calls[0][0] == expected["request"]["path"]
        and json.loads(transport.put_calls[0][2]) == expected["request"]["body"],
        "writer did not issue exactly the expected SHA-bound squash PUT",
    )
    require(
        [call[0] for call in transport.get_calls]
        == expected["follow_up_paths"],
        "writer follow-up endpoint set drift",
    )
    require(
        not merge_response.malformed
        and observation.complete
        and observation.document["merge_commit_parent_shas"] == ["b" * 40]
        and observation.document["base_sha_after"] == "d" * 40,
        "writer did not produce exact squash observation evidence",
    )
    require("ghs_fixture" not in repr(credential), "credential repr leaked token")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, IndexError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
