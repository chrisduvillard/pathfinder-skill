#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
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


def main() -> int:
    expected = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))

    from pathfinder_core.merge_policy import canonical_sha256
    from pathfinder_core.merge_status import (
        InstalledHostMergeReader,
        MergeStatusController,
    )
    from pathfinder_core.publication_journal import PublicationJournal
    from pathfinder_core.storage import write_atomic

    if os.name == "nt":
        try:
            InstalledHostMergeReader(root, root.parent).load(
                expected["publication_request_id"]
            )
        except Exception as error:
            require(
                "unavailable on Windows" in str(error),
                "Windows did not fail closed at the unproven ACL boundary",
            )
            return 0
        raise ValueError("Windows accepted an unproven installed-host ACL boundary")

    authority = load(root / "tests/contracts/fixtures/publication-contracts.json")
    evidence = load(
        root / "tests/contracts/fixtures/publication-journal-contracts.json"
    )
    publication = load(
        root / "tests/contracts/fixtures/publication-controller-contracts.json"
    )
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        repository = workspace / "repository"
        host = workspace / "host"
        repository.mkdir()
        host.mkdir(mode=0o700)
        os.chmod(host, 0o700)
        journal = PublicationJournal(host / "journal")
        claim = journal.claim_request(publication["request"])
        require(claim is not None, "publication request was not newly claimed")
        journal.dispatch_once(
            claim,
            started_at=publication["dispatch"]["started_at"],
            send=lambda: None,
        )
        journal.record_receipt(publication["receipt"])
        for name, document in (
            ("merge-policy.json", authority["policy"]),
            ("merge-authorization.json", authority["authorization"]),
            ("merge-evidence-initial.json", evidence["initial_evidence"]),
            ("merge-evidence-reread.json", evidence["evidence"]),
        ):
            write_atomic(host / name, document)
        report = MergeStatusController(
            InstalledHostMergeReader(repository, host),
            clock=lambda: datetime.fromisoformat("2026-08-11T12:08:30+00:00"),
        ).inspect(expected["publication_request_id"], operation="evaluate")

    schema = load(root / "schemas/publication/merge-status-report.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(report)
    for field in (
        "schema_version", "operation", "source", "state", "outcome", "eligible",
        "intent_ready", "execution_available", "writer_credential_loaded",
        "merge_intent_created",
    ):
        require(report[field] == expected[field], f"merge status {field} drift")
    require(
        report["publication"]["publication_request_id"]
        == expected["publication_request_id"]
        and report["publication"]["publication_receipt_id"]
        == expected["publication_receipt_id"],
        "merge status publication identity drift",
    )
    require(
        report["inputs"]["policy"]["declared_sha256"]
        == authority["policy"]["policy_sha256"]
        and report["inputs"]["authorization"]["declared_sha256"]
        == authority["authorization"]["authorization_sha256"]
        and report["inputs"]["initial_evidence"]["document_sha256"]
        == canonical_sha256(evidence["initial_evidence"])
        and report["inputs"]["reread_evidence"]["document_sha256"]
        == canonical_sha256(evidence["evidence"]),
        "merge status does not bind the exact evaluated inputs",
    )
    require(
        report["report_sha256"] == canonical_sha256(report, "report_sha256"),
        "merge status report hash differs from its canonical document",
    )
    require(
        "proof" not in json.dumps(report).lower(),
        "merge status exposed a readiness proof",
    )
    source = (root / "pathfinder_core/merge_status.py").read_text()
    for forbidden in (
        "MergeExecutor", "GitHubMergeCredential", "MergeOperationJournal",
        "github_merge_writer", "merge_credentials", ".merge(", "record_intent(",
        "dispatch_once(", "os.environ", "getenv(", "subprocess", "requests.",
    ):
        require(forbidden not in source, f"merge status gained forbidden {forbidden}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
