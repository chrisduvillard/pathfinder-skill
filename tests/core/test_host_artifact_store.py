import base64
import copy
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from pathfinder_core.errors import StateError
from pathfinder_core.host_artifact_store import HostArtifactCollectionStore
from pathfinder_core.storage import canonical_sha256
from tests.adapters import test_github_evidence_composer as composer_fixtures
from tests.adapters.test_github_branch_ownership import credential_receipt


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)
NOW = datetime(2026, 8, 11, 12, 8, 30, tzinfo=timezone.utc)
STORE_ID = "host_artifact_store_example1"


class FakeHostAuthenticator:
    def __init__(self, key=b"test-only-host-attestation-key"):
        self.key = key
        self.attest_calls = 0
        self.verify_calls = 0

    def _proof(self, payload):
        digest = hmac.new(self.key, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    def attest(self, payload, *, authenticated_at):
        self.attest_calls += 1
        return {
            "source": "external-host-authenticator",
            "authenticator_id": "host_authenticator_example1",
            "key_id": "host_key_example1",
            "method": "external-host-authenticator-v1",
            "authenticated_at": authenticated_at,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "proof": self._proof(payload),
        }

    def verify(self, payload, attestation):
        self.verify_calls += 1
        return hmac.compare_digest(attestation["proof"], self._proof(payload))


@unittest.skipIf(os.name == "nt", "host ACL verification is POSIX-only")
class HostArtifactCollectionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.repo_root = root / "repository"
        self.host_root = root / "operator-host"
        self.repo_root.mkdir(mode=0o755)
        self.host_root.mkdir(mode=0o700)
        self.authenticator = FakeHostAuthenticator()

        helper = composer_fixtures.GitHubCompleteEvidenceComposerTests()
        helper.setUp()
        snapshot = helper.compose()
        publication = json.loads(FIXTURE.read_text())
        self.documents = {
            "publication_request": publication["request"],
            "publication_dispatch": publication["dispatch"],
            "publication_receipt": publication["receipt"],
            "publication_credential_receipt": credential_receipt(),
            "observer_credential_receipt": helper.identity.credential_receipt,
            "branch_ownership": helper.branch_ownership,
            "evidence": snapshot.evidence,
            "provenance": snapshot.provenance,
        }

    def store(self, **overrides):
        values = {**self.documents, **overrides}
        return HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: NOW,
        ), values

    def persist(self, **overrides):
        store, values = self.store(**overrides)
        return store, store.persist(**values)

    def collection_path(self, evidence_id=None):
        evidence_id = evidence_id or self.documents["evidence"]["evidence_id"]
        suffix = evidence_id.removeprefix("merge_evidence_")
        return (
            self.host_root
            / "artifact-collections"
            / f"host_artifact_collection_{suffix}.json"
        )

    def test_persists_loads_and_idempotently_reuses_one_exact_envelope(self):
        store, first = self.persist()
        second = store.persist(**self.documents)
        loaded = store.load(self.documents["evidence"]["evidence_id"])

        self.assertEqual(first, second)
        self.assertEqual(second, loaded)
        self.assertEqual(loaded["payload"]["documents"], self.documents)
        self.assertEqual(loaded["payload"]["store_id"], STORE_ID)
        self.assertEqual(
            loaded["attestation"]["payload_sha256"],
            canonical_sha256(loaded["payload"]),
        )
        self.assertEqual(self.authenticator.attest_calls, 1)
        self.assertGreaterEqual(self.authenticator.verify_calls, 4)
        self.assertEqual(self.collection_path().stat().st_mode & 0o777, 0o600)

    def test_rehashed_tampering_still_fails_external_authentication(self):
        store, _envelope = self.persist()
        path = self.collection_path()
        changed = json.loads(path.read_text())
        evidence = changed["payload"]["documents"]["evidence"]
        provenance = changed["payload"]["documents"]["provenance"]
        evidence["pull_request"]["number"] += 1
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )
        provenance["evidence_sha256"] = evidence["evidence_sha256"]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        changed["attestation"]["payload_sha256"] = canonical_sha256(
            changed["payload"]
        )
        changed["envelope_sha256"] = canonical_sha256(
            changed, "envelope_sha256"
        )
        path.write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")

        with self.assertRaisesRegex(StateError, "attestation verification"):
            store.load(self.documents["evidence"]["evidence_id"])

    def test_split_document_identity_fails_before_persistence(self):
        ownership = copy.deepcopy(self.documents["branch_ownership"])
        ownership["head_sha"] = "d" * 40
        ownership["ownership_sha256"] = canonical_sha256(
            ownership, "ownership_sha256"
        )
        provenance = copy.deepcopy(self.documents["provenance"])
        provenance["branch_ownership_sha256"] = ownership["ownership_sha256"]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )

        store, values = self.store(
            branch_ownership=ownership, provenance=provenance
        )
        with self.assertRaisesRegex(StateError, "document bindings differ"):
            store.persist(**values)
        self.assertFalse(self.collection_path().exists())
        self.assertEqual(self.authenticator.attest_calls, 0)

        observer = copy.deepcopy(self.documents["observer_credential_receipt"])
        observer["actor_id"] += 1
        observer["receipt_sha256"] = canonical_sha256(
            observer, "receipt_sha256"
        )
        provenance = copy.deepcopy(self.documents["provenance"])
        provenance["observer_credential_receipt_sha256"] = observer[
            "receipt_sha256"
        ]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        store, values = self.store(
            observer_credential_receipt=observer, provenance=provenance
        )
        with self.assertRaisesRegex(StateError, "document bindings differ"):
            store.persist(**values)

    def test_wrong_store_and_renamed_replay_fail_closed(self):
        _store, _envelope = self.persist()
        other_id = "merge_evidence_replayed1"
        other_path = self.collection_path(other_id)
        shutil.copyfile(self.collection_path(), other_path)
        other_path.chmod(0o600)
        store = HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: NOW,
        )
        with self.assertRaisesRegex(StateError, "identity binding differs"):
            store.load(other_id)

        wrong_store = HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id="host_artifact_store_different1",
            authenticator=self.authenticator,
            clock=lambda: NOW,
        )
        with self.assertRaisesRegex(StateError, "identity binding differs"):
            wrong_store.load(self.documents["evidence"]["evidence_id"])

    def test_missing_load_is_read_only_and_wrong_authenticator_fails(self):
        store, _values = self.store()
        with self.assertRaisesRegex(StateError, "pinned non-symlink directory"):
            store.load(self.documents["evidence"]["evidence_id"])
        self.assertFalse((self.host_root / "artifact-collections").exists())

        self.persist()
        wrong_authenticator = FakeHostAuthenticator(b"different-test-key")
        untrusted = HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id=STORE_ID,
            authenticator=wrong_authenticator,
            clock=lambda: NOW,
        )
        with self.assertRaisesRegex(StateError, "attestation verification"):
            untrusted.load(self.documents["evidence"]["evidence_id"])

    def test_interrupted_atomic_link_leaves_no_trusted_collection(self):
        store, values = self.store()
        with patch(
            "pathfinder_core.host_artifact_store.os.link",
            side_effect=OSError("injected interruption"),
        ), self.assertRaisesRegex(StateError, "written atomically"):
            store.persist(**values)

        collections = self.host_root / "artifact-collections"
        self.assertFalse(self.collection_path().exists())
        self.assertEqual(list(collections.glob(".*.tmp")), [])
        recorded = store.persist(**values)
        self.assertEqual(recorded["payload"]["documents"], self.documents)

    def test_concurrent_writers_create_one_collection_and_drift_cannot_replace_it(self):
        store, values = self.store()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _item: store.persist(**values), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(list(self.collection_path().parent.glob("*.json"))), 1)

        evidence = copy.deepcopy(self.documents["evidence"])
        evidence["reviews"][0]["submitted_at"] = "2026-08-11T12:07:01+00:00"
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )
        provenance = copy.deepcopy(self.documents["provenance"])
        provenance["evidence_sha256"] = evidence["evidence_sha256"]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        with self.assertRaisesRegex(StateError, "different host artifact"):
            store.persist(**{
                **values,
                "evidence": evidence,
                "provenance": provenance,
            })

    def test_host_path_owner_symlink_overlap_and_clock_checks_fail_closed(self):
        store, values = self.store()
        self.host_root.chmod(0o755)
        with self.assertRaisesRegex(StateError, "owner-only"):
            store.persist(**values)
        self.host_root.chmod(0o700)

        symlink = Path(self.temporary.name) / "host-link"
        symlink.symlink_to(self.host_root, target_is_directory=True)
        linked = HostArtifactCollectionStore(
            self.repo_root,
            symlink,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: NOW,
        )
        with self.assertRaisesRegex(StateError, "non-symlink"):
            linked.persist(**values)

        overlap = self.repo_root / "operator-host"
        overlap.mkdir(mode=0o700)
        inside = HostArtifactCollectionStore(
            self.repo_root,
            overlap,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: NOW,
        )
        with self.assertRaisesRegex(StateError, "overlap"):
            inside.persist(**values)

        invalid_clock = HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: datetime(2026, 8, 11, 12, 8, 30),
        )
        with self.assertRaisesRegex(StateError, "UTC offset"):
            invalid_clock.persist(**values)

        early_clock = HostArtifactCollectionStore(
            self.repo_root,
            self.host_root,
            store_id=STORE_ID,
            authenticator=self.authenticator,
            clock=lambda: datetime(
                2026, 8, 11, 12, 8, 21, tzinfo=timezone.utc
            ),
        )
        with self.assertRaisesRegex(StateError, "predates its collection"):
            early_clock.persist(**values)

    def test_schema_is_closed_and_store_has_no_packaged_caller(self):
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "publication"
                / "host-artifact-collection.schema.json"
            ).read_text()
        )
        Draft202012Validator.check_schema(schema)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["payload"]["additionalProperties"])
        self.assertFalse(
            schema["properties"]["payload"]["properties"]["documents"][
                "additionalProperties"
            ]
        )
        self.assertFalse(
            schema["properties"]["attestation"]["additionalProperties"]
        )

        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "host_artifact_store.py":
                continue
            if "HostArtifactCollectionStore(" in path.read_text():
                callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])
        source = (ROOT / "pathfinder_core" / "host_artifact_store.py").read_text()
        for forbidden in (
            "os.environ",
            "subprocess",
            "urllib",
            "http.client",
            "GitHubGETClient",
            "GitHubGraphQLClient",
            "MergeExecutor(",
            "PublicationController(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
