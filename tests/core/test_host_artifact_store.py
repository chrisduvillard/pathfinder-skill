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
from pathfinder_core.merge_status import (
    AuthenticatedHostMergeReader,
    MergeStatusController,
)
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
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
AUTHORITY_FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-contracts.json"
)
NOW = datetime(2026, 8, 11, 12, 8, 30, tzinfo=timezone.utc)
COLLECTION_STARTED = "2026-08-11T12:08:00+00:00"
STORE_ID = "host_artifact_store_example1"


class FakeHostAuthenticator:
    def __init__(self, key=b"test-only-host-attestation-key"):
        self.key = key
        self.key_id = "host_key_example1"
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
            "key_id": self.key_id,
            "method": "external-host-authenticator-v1",
            "authenticated_at": authenticated_at,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "proof": self._proof(payload),
        }

    def verify(self, payload, attestation):
        self.verify_calls += 1
        return hmac.compare_digest(attestation["proof"], self._proof(payload))


def collection_input_envelope(
    documents, authenticator, *, store_id=STORE_ID,
    authenticated_at=COLLECTION_STARTED,
    policy_read=None,
    object_evidence=None,
):
    evidence = documents["evidence"]
    evidence_id = evidence["evidence_id"]
    suffix = evidence_id.removeprefix("merge_evidence_")
    input_documents = {
        key: copy.deepcopy(documents[key])
        for key in (
            "publication_request",
            "publication_dispatch",
            "publication_receipt",
            "publication_credential_receipt",
            "observer_credential_receipt",
            "merge_credential_receipt",
            "policy",
            "authorization",
            "protected_policy",
        )
    }
    input_documents.update({
        "policy_read": copy.deepcopy(
            policy_read
            if policy_read is not None
            else evidence["observation"]["policy_read"]
        ),
        "object_evidence": copy.deepcopy(
            object_evidence
            if object_evidence is not None
            else evidence["diff"]["object_evidence"]
        ),
    })
    payload = {
        "input_id": f"host_artifact_input_{suffix}",
        "store_id": store_id,
        "source": "authenticated-host-collection-input",
        "publication_request_id": input_documents["publication_request"][
            "publication_request_id"
        ],
        "evidence_id": evidence_id,
        "repository": copy.deepcopy(
            input_documents["publication_receipt"]["repository"]
        ),
        "authenticated_at": authenticated_at,
        "documents": input_documents,
    }
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    envelope = {
        "schema_version": 1,
        "payload": payload,
        "attestation": dict(authenticator.attest(
            payload_bytes, authenticated_at=authenticated_at
        )),
        "envelope_sha256": "0" * 64,
    }
    envelope["envelope_sha256"] = canonical_sha256(
        envelope, "envelope_sha256"
    )
    return envelope


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
        authority = json.loads(AUTHORITY_FIXTURE.read_text())
        self.documents = {
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
        self.input_policy_read = helper.context["policy_read"]
        self.input_object_evidence = helper.context["object_evidence"]

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

    def snapshot_variant(self, suffix):
        documents = copy.deepcopy(self.documents)
        observed_at = "2026-08-11T12:07:31+00:00"
        completed_at = "2026-08-11T12:07:50+00:00"
        evidence = documents["evidence"]
        evidence["evidence_id"] = f"merge_evidence_{suffix}"
        observation = evidence["observation"]
        observation["policy_read"].update({
            "receipt_id": f"policy_read_{suffix}",
            "observed_at": "2026-08-11T12:07:32+00:00",
        })
        for request in observation["requests"]:
            request["request_id"] = f"{request['request_id']}-{suffix}"
            request["observed_at"] = "2026-08-11T12:07:40+00:00"
        observation.update({
            "request_ids_sha256": canonical_sha256([
                request["request_id"] for request in observation["requests"]
            ]),
            "observed_at": observed_at,
            "completed_at": completed_at,
            "expires_at": "2026-08-11T12:09:00+00:00",
        })
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )

        observer = documents["observer_credential_receipt"]
        observer.update({
            "credential_receipt_id": f"evidence_credential_receipt_{suffix}",
            "credential_id": f"evidence_credential_{suffix}",
            "verified_at": observed_at,
        })
        observer["receipt_sha256"] = canonical_sha256(
            observer, "receipt_sha256"
        )

        merge = documents["merge_credential_receipt"]
        merge.update({
            "credential_receipt_id": f"merge_credential_receipt_{suffix}",
            "credential_id": f"merge_credential_{suffix}",
            "verified_at": observed_at,
        })
        merge["receipt_sha256"] = canonical_sha256(
            merge, "receipt_sha256"
        )

        ownership = documents["branch_ownership"]
        ownership["ownership_id"] = f"controller_branch_ownership_{suffix}"
        ownership_observation = ownership["observation"]
        ownership_observation.update({
            "evidence_completed_at": completed_at,
            "observed_at": "2026-08-11T12:07:51+00:00",
            "completed_at": "2026-08-11T12:07:53+00:00",
            "request_ids": [
                f"{request_id}-{suffix}"
                for request_id in ownership_observation["request_ids"]
            ],
        })
        ownership_observation["request_ids_sha256"] = canonical_sha256(
            ownership_observation["request_ids"]
        )
        ownership["ownership_sha256"] = canonical_sha256(
            ownership, "ownership_sha256"
        )

        provenance = documents["provenance"]
        provenance.update({
            "provenance_id": f"merge_evidence_provenance_{suffix}",
            "evidence_id": evidence["evidence_id"],
            "evidence_sha256": evidence["evidence_sha256"],
            "observer_credential_receipt_id": observer["credential_receipt_id"],
            "observer_credential_receipt_sha256": observer["receipt_sha256"],
            "merge_credential_receipt_id": merge["credential_receipt_id"],
            "merge_credential_receipt_sha256": merge["receipt_sha256"],
            "branch_ownership_id": ownership["ownership_id"],
            "branch_ownership_sha256": ownership["ownership_sha256"],
            "request_ids_sha256": observation["request_ids_sha256"],
            "observed_at": observed_at,
            "completed_at": completed_at,
        })
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        return documents

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

    def test_verifies_one_authenticated_collection_input_before_use(self):
        store, _values = self.store()
        envelope = collection_input_envelope(
            self.documents,
            self.authenticator,
            policy_read=self.input_policy_read,
            object_evidence=self.input_object_evidence,
        )

        payload = store.verify_collection_inputs(
            envelope, authenticated_at=COLLECTION_STARTED
        )

        self.assertEqual(payload, envelope["payload"])
        self.assertEqual(payload["documents"]["policy"], self.documents["policy"])
        self.assertEqual(self.authenticator.verify_calls, 1)

    def test_collection_input_rejects_rehashed_tamper_stale_time_and_wrong_store(self):
        store, _values = self.store()
        envelope = collection_input_envelope(
            self.documents,
            self.authenticator,
            policy_read=self.input_policy_read,
            object_evidence=self.input_object_evidence,
        )

        changed = copy.deepcopy(envelope)
        changed["payload"]["documents"]["policy"]["authority"]["issuer"] = (
            "attacker@example"
        )
        changed["attestation"]["payload_sha256"] = canonical_sha256(
            changed["payload"]
        )
        changed["envelope_sha256"] = canonical_sha256(
            changed, "envelope_sha256"
        )
        with self.assertRaisesRegex(StateError, "attestation verification"):
            store.verify_collection_inputs(
                changed, authenticated_at=COLLECTION_STARTED
            )

        with self.assertRaisesRegex(StateError, "trusted collection start"):
            store.verify_collection_inputs(
                envelope, authenticated_at="2026-08-11T12:08:01+00:00"
            )

        wrong_store = copy.deepcopy(envelope)
        wrong_store["payload"]["store_id"] = "host_artifact_store_different1"
        wrong_store["envelope_sha256"] = canonical_sha256(
            wrong_store, "envelope_sha256"
        )
        with self.assertRaisesRegex(StateError, "identity binding differs"):
            store.verify_collection_inputs(
                wrong_store, authenticated_at=COLLECTION_STARTED
            )

    def test_collection_input_rejects_malformed_nested_shape_before_authentication(self):
        store, _values = self.store()
        envelope = collection_input_envelope(
            self.documents,
            self.authenticator,
            policy_read=self.input_policy_read,
            object_evidence=self.input_object_evidence,
        )
        malformed = copy.deepcopy(envelope)
        malformed["payload"]["documents"]["policy"] = []
        malformed["attestation"]["payload_sha256"] = canonical_sha256(
            malformed["payload"]
        )
        malformed["envelope_sha256"] = canonical_sha256(
            malformed, "envelope_sha256"
        )

        with self.assertRaisesRegex(
            StateError, "schema validation failed for host artifact collection input"
        ):
            store.verify_collection_inputs(
                malformed, authenticated_at=COLLECTION_STARTED
            )
        self.assertEqual(self.authenticator.verify_calls, 0)

    def test_authenticated_pair_reader_requires_exact_shared_authority(self):
        initial = self.snapshot_variant("authpairinitial1")
        store, _values = self.store()
        store.persist(**initial)
        store.persist(**self.documents)
        reader = AuthenticatedHostMergeReader(
            store,
            initial_evidence_id=initial["evidence"]["evidence_id"],
            reread_evidence_id=self.documents["evidence"]["evidence_id"],
        )

        report = MergeStatusController(
            reader, clock=lambda: NOW
        ).inspect(
            self.documents["publication_request"]["publication_request_id"],
            operation="evaluate",
        )

        self.assertEqual(report["outcome"], "eligible")
        self.assertEqual(report["blocks"], [])
        self.assertFalse(report["intent_ready"])
        self.assertFalse(report["execution_available"])
        with self.assertRaisesRegex(StateError, "distinct evidence ids"):
            AuthenticatedHostMergeReader(
                store,
                initial_evidence_id=initial["evidence"]["evidence_id"],
                reread_evidence_id=initial["evidence"]["evidence_id"],
            )

        changed_initial = self.snapshot_variant("authpairdrift1")
        policy = changed_initial["policy"]
        policy["authority"]["issuer"] = "different-host-admin@example"
        policy["policy_sha256"] = canonical_sha256(policy, "policy_sha256")
        authorization = changed_initial["authorization"]
        authorization["policy"]["policy_sha256"] = policy["policy_sha256"]
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        evidence = changed_initial["evidence"]
        evidence["observation"]["policy_read"]["policy_sha256"] = policy[
            "policy_sha256"
        ]
        evidence["bindings"]["policy_sha256"] = policy["policy_sha256"]
        evidence["bindings"]["authorization_sha256"] = authorization[
            "authorization_sha256"
        ]
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )
        provenance = changed_initial["provenance"]
        provenance["evidence_sha256"] = evidence["evidence_sha256"]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        store.persist(**changed_initial)
        drifted = AuthenticatedHostMergeReader(
            store,
            initial_evidence_id=evidence["evidence_id"],
            reread_evidence_id=self.documents["evidence"]["evidence_id"],
        )
        with self.assertRaisesRegex(StateError, "pair bindings differ"):
            drifted.load(
                self.documents["publication_request"]["publication_request_id"]
            )

    def test_authenticated_pair_reader_rejects_key_identity_drift(self):
        initial = self.snapshot_variant("authpairkeyinitial1")
        host_root = Path(self.temporary.name) / "rotating-key-host"
        host_root.mkdir(mode=0o700)
        authenticator = FakeHostAuthenticator()
        store = HostArtifactCollectionStore(
            self.repo_root,
            host_root,
            store_id=STORE_ID,
            authenticator=authenticator,
            clock=lambda: NOW,
        )
        store.persist(**initial)
        authenticator.key_id = "host_key_rotated1"
        store.persist(**self.documents)

        reader = AuthenticatedHostMergeReader(
            store,
            initial_evidence_id=initial["evidence"]["evidence_id"],
            reread_evidence_id=self.documents["evidence"]["evidence_id"],
        )
        with self.assertRaisesRegex(StateError, "pair bindings differ"):
            reader.load(
                self.documents["publication_request"]["publication_request_id"]
            )

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

    def test_additive_protected_policy_uses_the_effective_baseline_hash(self):
        documents = copy.deepcopy(self.documents)
        baseline = ProtectedSurfaceRegistry.load().to_document()
        additive = {
            "schema_version": 1,
            "policy_id": "protected-policy-host-extra",
            "mode": "additive",
            "base_policy_id": baseline["policy_id"],
            "rules": [{
                "rule_id": "protected-rule-host-extra",
                "category": "host-extra",
                "description": "Additional operator-owned protected surface.",
                "patterns": ["operator-protected/**"],
            }],
        }
        effective = ProtectedSurfaceRegistry(baseline, additive)
        documents["protected_policy"] = additive
        policy = documents["policy"]
        policy["path_policy"]["protected_policy_sha256"] = effective.sha256
        policy["policy_sha256"] = canonical_sha256(policy, "policy_sha256")
        authorization = documents["authorization"]
        authorization["policy"]["policy_sha256"] = policy["policy_sha256"]
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        evidence = documents["evidence"]
        evidence["bindings"].update({
            "policy_sha256": policy["policy_sha256"],
            "authorization_sha256": authorization["authorization_sha256"],
            "protected_policy_sha256": effective.sha256,
        })
        evidence["observation"]["policy_read"]["policy_sha256"] = policy[
            "policy_sha256"
        ]
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )
        provenance = documents["provenance"]
        provenance["evidence_sha256"] = evidence["evidence_sha256"]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )

        store, _values = self.store()
        envelope = store.persist(**documents)

        self.assertEqual(
            envelope["payload"]["documents"]["protected_policy"], additive
        )

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

        overlong = copy.deepcopy(self.documents["merge_credential_receipt"])
        overlong["expires_at"] = "2026-08-11T13:00:01+00:00"
        overlong["receipt_sha256"] = canonical_sha256(
            overlong, "receipt_sha256"
        )
        provenance = copy.deepcopy(self.documents["provenance"])
        provenance["merge_credential_receipt_sha256"] = overlong[
            "receipt_sha256"
        ]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        store, values = self.store(
            merge_credential_receipt=overlong, provenance=provenance
        )
        with self.assertRaisesRegex(StateError, "document bindings differ"):
            store.persist(**values)

        merge = copy.deepcopy(self.documents["merge_credential_receipt"])
        merge["actor_id"] += 1
        merge["receipt_sha256"] = canonical_sha256(
            merge, "receipt_sha256"
        )
        provenance = copy.deepcopy(self.documents["provenance"])
        provenance["merge_credential_receipt_sha256"] = merge[
            "receipt_sha256"
        ]
        provenance["provenance_sha256"] = canonical_sha256(
            provenance, "provenance_sha256"
        )
        store, values = self.store(
            merge_credential_receipt=merge, provenance=provenance
        )
        with self.assertRaisesRegex(StateError, "document bindings differ"):
            store.persist(**values)

        authorization = copy.deepcopy(self.documents["authorization"])
        authorization["candidate"]["pull_request"]["number"] += 1
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        store, values = self.store(authorization=authorization)
        with self.assertRaisesRegex(StateError, "document bindings differ"):
            store.persist(**values)

        policy = copy.deepcopy(self.documents["policy"])
        policy["path_policy"]["protected_policy_sha256"] = "a" * 64
        policy["policy_sha256"] = canonical_sha256(policy, "policy_sha256")
        authorization = copy.deepcopy(self.documents["authorization"])
        authorization["policy"]["policy_sha256"] = policy["policy_sha256"]
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        store, values = self.store(policy=policy, authorization=authorization)
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

    def test_schema_is_closed_and_store_has_only_source_boundary_consumers(self):
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
        self.assertEqual(schema["properties"]["schema_version"]["const"], 3)
        input_schema = json.loads(
            (
                ROOT
                / "schemas"
                / "publication"
                / "host-artifact-collection-input.schema.json"
            ).read_text()
        )
        Draft202012Validator.check_schema(input_schema)
        self.assertFalse(input_schema["additionalProperties"])
        self.assertFalse(
            input_schema["properties"]["payload"]["additionalProperties"]
        )
        self.assertFalse(
            input_schema["properties"]["payload"]["properties"]["documents"][
                "additionalProperties"
            ]
        )
        self.assertFalse(
            input_schema["$defs"]["attestation"]["additionalProperties"]
        )
        self.assertEqual(
            input_schema["properties"]["schema_version"]["const"], 1
        )
        provenance_schema = json.loads(
            (
                ROOT
                / "schemas"
                / "publication"
                / "merge-evidence-provenance.schema.json"
            ).read_text()
        )
        Draft202012Validator.check_schema(provenance_schema)
        self.assertEqual(
            provenance_schema["properties"]["schema_version"]["const"], 2
        )
        self.assertIn(
            "merge_credential_receipt_sha256", provenance_schema["required"]
        )

        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "host_artifact_store.py":
                continue
            if "HostArtifactCollectionStore(" in path.read_text():
                callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])
        readers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "host_artifact_store.py":
                continue
            if "HostArtifactCollectionStore" in path.read_text():
                readers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(sorted(readers), [
            "pathfinder_core/adapters/github_evidence_collector.py",
            "pathfinder_core/merge_status.py",
        ])
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
