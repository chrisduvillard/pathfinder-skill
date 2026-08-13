#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
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


class EvalAuthenticator:
    def __init__(self):
        self.key = b"deterministic-eval-only-host-key"
        self.attest_calls = 0

    def _proof(self, payload):
        digest = hmac.new(self.key, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def attest(self, payload, *, authenticated_at):
        self.attest_calls += 1
        return {
            "source": "external-host-authenticator",
            "authenticator_id": "host_authenticator_contract1",
            "key_id": "host_key_contract1",
            "method": "external-host-authenticator-v1",
            "authenticated_at": authenticated_at,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "proof": self._proof(payload),
        }

    def verify(self, payload, attestation):
        return hmac.compare_digest(attestation["proof"], self._proof(payload))


def main() -> int:
    expected = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))

    from pathfinder_core.host_artifact_store import HostArtifactCollectionStore
    from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
    from pathfinder_core.storage import canonical_sha256

    if os.name == "nt":
        try:
            HostArtifactCollectionStore(
                root,
                root.parent,
                store_id=expected["store_id"],
                authenticator=EvalAuthenticator(),
            ).load("merge_evidence_windows1")
        except Exception as error:
            require(
                "unavailable on Windows" in str(error),
                "Windows did not fail closed at the unproven ACL boundary",
            )
            return 0
        raise ValueError("Windows accepted an unproven host artifact ACL boundary")

    from tests.adapters import test_github_evidence_composer as composer_fixtures
    from tests.adapters.test_github_branch_ownership import credential_receipt

    helper = composer_fixtures.GitHubCompleteEvidenceComposerTests()
    helper.setUp()
    snapshot = helper.compose()
    publication = load(
        root / "tests/contracts/fixtures/publication-controller-contracts.json"
    )
    authority = load(
        root / "tests/contracts/fixtures/publication-contracts.json"
    )
    documents = {
        "publication_request": publication["request"],
        "publication_dispatch": publication["dispatch"],
        "publication_receipt": publication["receipt"],
        "publication_credential_receipt": credential_receipt(),
        "observer_credential_receipt": helper.identity.credential_receipt,
        "merge_credential_receipt": helper.merge_identity.credential_receipt,
        "policy": authority["policy"],
        "authorization": authority["authorization"],
        "protected_policy": ProtectedSurfaceRegistry.load().to_document(),
        "branch_ownership": helper.branch_ownership,
        "evidence": snapshot.evidence,
        "provenance": snapshot.provenance,
    }
    authenticator = EvalAuthenticator()
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        repository = workspace / "repository"
        host = workspace / "operator-host"
        repository.mkdir()
        host.mkdir(mode=0o700)
        os.chmod(host, 0o700)
        store = HostArtifactCollectionStore(
            repository,
            host,
            store_id=expected["store_id"],
            authenticator=authenticator,
            clock=lambda: datetime(
                2026, 8, 11, 12, 8, 30, tzinfo=timezone.utc
            ),
        )
        first = store.persist(**documents)
        second = store.persist(**documents)
        require(first == second, "repeat persistence changed the immutable envelope")
        require(authenticator.attest_calls == 1, "repeat persistence re-attested")

        schema = load(
            root / "schemas/publication/host-artifact-collection.schema.json"
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(first)
        payload = first["payload"]
        require(
            first["schema_version"] == expected["schema_version"]
            and payload["source"] == expected["source"]
            and payload["store_id"] == expected["store_id"],
            "host artifact envelope identity drift",
        )
        require(
            sorted(payload["documents"]) == expected["document_names"],
            "host artifact document set drift",
        )
        require(
            first["envelope_sha256"]
            == canonical_sha256(first, "envelope_sha256")
            and first["attestation"]["payload_sha256"]
            == canonical_sha256(payload),
            "host artifact canonical hashes differ",
        )

        path = next((host / "artifact-collections").glob("*.json"))
        changed = load(path)
        changed["payload"]["stored_at"] = "2026-08-11T12:08:31Z"
        changed["attestation"]["authenticated_at"] = "2026-08-11T12:08:31Z"
        changed["attestation"]["payload_sha256"] = canonical_sha256(
            changed["payload"]
        )
        changed["envelope_sha256"] = canonical_sha256(
            changed, "envelope_sha256"
        )
        path.write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")
        try:
            store.load(snapshot.evidence["evidence_id"])
        except Exception as error:
            require(
                "attestation verification failed" in str(error),
                "re-hashed tampering failed for the wrong reason",
            )
        else:
            raise ValueError("re-hashed tampering bypassed host authentication")

    callers = []
    for path in (root / "pathfinder_core").rglob("*.py"):
        if path.name == "host_artifact_store.py":
            continue
        if "HostArtifactCollectionStore(" in path.read_text():
            callers.append(path)
    require(
        len(callers) == expected["packaged_callers"],
        "host artifact store gained a packaged caller",
    )
    readers = []
    for path in (root / "pathfinder_core").rglob("*.py"):
        if path.name == "host_artifact_store.py":
            continue
        if "HostArtifactCollectionStore" in path.read_text():
            readers.append(path.relative_to(root).as_posix())
    require(
        sorted(readers) == expected["packaged_readers"],
        "host artifact store read-only consumer drift",
    )
    source = (root / "pathfinder_core/host_artifact_store.py").read_text()
    for forbidden in (
        "os.environ",
        "subprocess",
        "GitHubGETClient",
        "GitHubGraphQLClient",
        "PublicationController(",
        "MergeExecutor(",
    ):
        require(forbidden not in source, f"host artifact store gained {forbidden}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
