import copy
import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from pathfinder_core.adapters.github_checks import GitHubCheckEvidenceReader
from pathfinder_core.adapters.github_candidate_rest import GitHubCandidateRESTSnapshot
from pathfinder_core.adapters.github_evidence_collector import (
    GitHubAuthenticatedEvidenceCollector,
    GitHubNormalizedPolicySnapshot,
)
from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
)
from pathfinder_core.adapters.github_get import GitHubGETClient
from pathfinder_core.adapters.github_graphql import GitHubGraphQLClient
from pathfinder_core.adapters.github_identity import GitHubIdentityVerifier
from pathfinder_core.adapters.github_merge_observer import GitHubObservationError
from pathfinder_core.adapters.github_reviews import GitHubReviewReader
from pathfinder_core.errors import StateError
from pathfinder_core.host_artifact_store import HostArtifactCollectionStore
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
from pathfinder_core.storage import canonical_sha256
from tests.adapters.test_github_branch_ownership import credential_receipt
from tests.adapters.test_github_evidence_composer import (
    GitHubCompleteEvidenceComposerTests,
)
from tests.adapters.test_github_merge_observer import FixtureObservationBackend
from tests.core.test_host_artifact_store import (
    FakeHostAuthenticator,
    collection_input_envelope,
)


ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_FIXTURE = (
    ROOT
    / "tests"
    / "contracts"
    / "fixtures"
    / "publication-controller-contracts.json"
)
AUTHORITY_FIXTURE = (
    ROOT / "tests" / "contracts" / "fixtures" / "publication-contracts.json"
)
STARTED = datetime(2026, 8, 11, 12, 8, tzinfo=timezone.utc)
COMPLETED = datetime(2026, 8, 11, 12, 8, 20, tzinfo=timezone.utc)


def installation_credential(suffix="a"):
    return GitHubEvidenceCredential(
        f"test-observer-installation-token-{suffix}",
        kind="installation-token",
        permissions={name: "read" for name in REQUIRED_READ_PERMISSIONS},
        boundary=EVIDENCE_BOUNDARY,
    )


def app_credential(suffix):
    return GitHubEvidenceCredential(
        f"test-observer-app-token-{suffix}",
        kind="app-jwt",
        permissions={},
        boundary=EVIDENCE_BOUNDARY,
    )


class OwnershipProvider:
    def __init__(self, proof, credential, events=None):
        self.proof = proof
        self.credential = credential
        self.events = events
        self.calls = []

    def prove(self, **values):
        self.calls.append(values)
        if self.events is not None:
            self.events.append("ownership")
        return copy.deepcopy(self.proof)


class CandidateProvider:
    def __init__(self, snapshot, credential, events=None):
        self.snapshot = snapshot
        self.credential = credential
        self.events = events
        self.calls = []

    def read_all(self, **values):
        self.calls.append(values)
        if self.events is not None:
            self.events.append("candidate")
        return copy.deepcopy(self.snapshot)


class Store:
    def __init__(self, events=None):
        self.events = events
        self.calls = []
        self.input_calls = []

    def verify_collection_inputs(self, envelope, *, authenticated_at):
        self.input_calls.append((copy.deepcopy(envelope), authenticated_at))
        if self.events is not None:
            self.events.append("input-auth")
        if (
            envelope["payload"]["authenticated_at"] != authenticated_at
            or envelope["attestation"]["authenticated_at"] != authenticated_at
        ):
            raise StateError(
                "host artifact input was not authenticated at the trusted "
                "collection start"
            )
        return copy.deepcopy(envelope["payload"])

    def persist(self, **values):
        self.calls.append(copy.deepcopy(values))
        if self.events is not None:
            self.events.append("store")
        return {"authenticated": True, "evidence_id": values["evidence"]["evidence_id"]}


class InputProvider:
    def __init__(self, envelope):
        self.envelope = envelope
        self.calls = []

    def read_fresh_authenticated(
        self, *, publication_records, authenticated_at
    ):
        self.calls.append((copy.deepcopy(publication_records), authenticated_at))
        return copy.deepcopy(self.envelope)


class FailingInputProvider:
    def __init__(self):
        self.calls = 0

    def read_fresh_authenticated(self, **_values):
        self.calls += 1
        raise StateError("trusted host input unavailable")


class PolicyBackend(FixtureObservationBackend):
    def __init__(self, responses, credential, classic_policy, active_policy):
        super().__init__(responses)
        self.credential = credential
        self.classic_policy = classic_policy
        self.active_policy = active_policy
        self.actor_calls = []

    def read_all(self, *, merge_actor):
        self.actor_calls.append(copy.deepcopy(merge_actor))
        source, bypass = self.read_source_rulesets()
        return GitHubNormalizedPolicySnapshot(
            self.read_classic_protection(),
            self.read_active_rules(),
            source,
            bypass,
            self.read_bypass_memberships(),
            self.classic_policy,
            self.active_policy,
        )


class RecordingBackend(PolicyBackend):
    def __init__(
        self, responses, events, credential, classic_policy, active_policy
    ):
        super().__init__(responses, credential, classic_policy, active_policy)
        self.events = events

    def _record(self, name, value):
        self.events.append(f"base:{name}")
        return value

    def read_pull_request(self):
        return self._record("pull-request", super().read_pull_request())

    def read_refs(self):
        return self._record("refs", super().read_refs())

    def read_changed_files(self):
        return self._record("changed-files", super().read_changed_files())

    def read_classic_protection(self):
        return self._record("classic-protection", super().read_classic_protection())

    def read_active_rules(self):
        return self._record("active-rules", super().read_active_rules())

    def read_source_rulesets(self):
        return self._record("source-rulesets", super().read_source_rulesets())

    def read_bypass_memberships(self):
        return self._record("bypass-memberships", super().read_bypass_memberships())

    def read_deployments(self):
        return self._record("deployments", super().read_deployments())

    def read_merged_state(self):
        return self._record("merged-state", super().read_merged_state())


class GitHubAuthenticatedEvidenceCollectorTests(unittest.TestCase):
    def setUp(self):
        helper = GitHubCompleteEvidenceComposerTests()
        helper.setUp()
        publication = json.loads(PUBLICATION_FIXTURE.read_text())
        authority = json.loads(AUTHORITY_FIXTURE.read_text())
        self.helper = helper
        snapshot = helper.compose()
        self.policy = authority["policy"]
        self.authorization = authority["authorization"]
        self.dispatch = publication["dispatch"]
        self.installation = installation_credential()
        observer_client = GitHubGETClient(self.installation)
        self.identity = GitHubIdentityVerifier(
            observer_app=GitHubGETClient(app_credential("observer")),
            observer_installation=observer_client,
            merge_app=GitHubGETClient(app_credential("merge")),
        )
        self.graphql = GitHubGraphQLClient(self.installation)
        self.reviews = GitHubReviewReader(observer_client)
        self.checks = GitHubCheckEvidenceReader(observer_client)
        self.identity.verify_observer = Mock(return_value=helper.identity)
        self.identity.verify_merge_actor = Mock(
            return_value=helper.merge_identity
        )
        self.graphql.read_pull_request = Mock(return_value=helper.graphql)
        self.reviews.read_all = Mock(return_value=helper.rest_reviews)
        self.checks.read_all = Mock(
            return_value=(helper._page("check-runs"), helper._page("commit-statuses"))
        )
        self.events = []
        base = FixtureObservationBackend(copy.deepcopy(helper.responses))
        self.candidate = CandidateProvider(
            GitHubCandidateRESTSnapshot(
                base.read_pull_request(),
                base.read_refs(),
                base.read_changed_files(),
                base.read_deployments(),
                base.read_merged_state(),
            ),
            self.installation,
            self.events,
        )
        self.ownership = OwnershipProvider(
            helper.branch_ownership, self.installation, self.events
        )
        self.store = Store(self.events)
        self.input_authenticator = FakeHostAuthenticator()
        self.input_documents = {
            "publication_request": helper.publication_request,
            "publication_dispatch": self.dispatch,
            "publication_receipt": helper.publication_receipt,
            "publication_credential_receipt": credential_receipt(),
            "observer_credential_receipt": helper.identity.credential_receipt,
            "merge_credential_receipt": helper.merge_identity.credential_receipt,
            "policy": self.policy,
            "authorization": self.authorization,
            "protected_policy": ProtectedSurfaceRegistry.load().to_document(),
            "evidence": snapshot.evidence,
        }

    def collector(self, *, clock=None, graphql=None):
        values = iter((STARTED, COMPLETED))
        return GitHubAuthenticatedEvidenceCollector(
            identity=self.identity,
            graphql=graphql or self.graphql,
            reviews=self.reviews,
            checks=self.checks,
            candidate=self.candidate,
            ownership=self.ownership,
            store=self.store,
            clock=clock or (lambda: next(values)),
        )

    def inputs(self, *, backend=None, authenticator=None, store_id=None):
        if backend is None:
            policy_backend = PolicyBackend(
                copy.deepcopy(self.helper.responses),
                self.installation,
                self.helper.classic_policy,
                self.helper.active_policy,
            )
        else:
            policy_backend = backend
        return {
            "policy_backend": policy_backend,
            "input_envelope": collection_input_envelope(
                self.input_documents,
                authenticator or self.input_authenticator,
                policy_read=self.helper.context["policy_read"],
                object_evidence=self.helper.context["object_evidence"],
                **({"store_id": store_id} if store_id is not None else {}),
            ),
        }

    def test_collects_composes_and_persists_one_authenticated_snapshot(self):
        inputs = self.inputs()
        before = copy.deepcopy({
            key: value for key, value in inputs.items() if key != "policy_backend"
        })
        result = self.collector().collect_and_persist(**inputs)

        self.assertTrue(result.snapshot.evidence["observation"]["collection_complete"])
        self.assertEqual(result.envelope["authenticated"], True)
        self.assertEqual(len(self.store.calls), 1)
        persisted = self.store.calls[0]
        self.assertEqual(persisted["evidence"], result.snapshot.evidence)
        self.assertEqual(persisted["provenance"], result.snapshot.provenance)
        self.assertEqual(
            persisted["observer_credential_receipt"],
            self.helper.identity.credential_receipt,
        )
        self.assertEqual(
            persisted["merge_credential_receipt"],
            self.helper.merge_identity.credential_receipt,
        )
        self.assertEqual(
            inputs["policy_backend"].actor_calls,
            [{"actor_id": 112234, "login": "pathfinder-merge[bot]"}],
        )
        self.assertEqual(result.snapshot.evidence["actor"]["actor_id"], 112234)
        self.assertEqual(
            before,
            {key: value for key, value in inputs.items() if key != "policy_backend"},
        )
        self.assertEqual(len(self.store.input_calls), 1)

    def test_verified_host_input_is_bound_to_the_exact_publication_before_reads(self):
        inputs = self.inputs()
        provider = InputProvider(inputs["input_envelope"])
        records = {
            "state": "awaiting-review",
            "disposition": "awaiting-review",
            "request": copy.deepcopy(self.helper.publication_request),
            "dispatch": copy.deepcopy(self.dispatch),
            "receipt": copy.deepcopy(self.helper.publication_receipt),
        }

        result = self.collector().collect_from_verified_host(
            policy_backend=inputs["policy_backend"],
            input_provider=provider,
            publication_records=records,
        )

        self.assertEqual(provider.calls, [(records, STARTED.isoformat())])
        self.assertEqual(
            result.snapshot.evidence["evidence_id"],
            self.helper.context["evidence_id"],
        )

        changed = copy.deepcopy(records)
        changed["receipt"]["reused"] = not changed["receipt"]["reused"]
        changed["receipt"]["receipt_sha256"] = canonical_sha256(
            changed["receipt"], "receipt_sha256"
        )
        self.identity.verify_observer.reset_mock()
        self.identity.verify_merge_actor.reset_mock()
        self.graphql.read_pull_request.reset_mock()
        self.reviews.read_all.reset_mock()
        self.checks.read_all.reset_mock()
        self.candidate.calls.clear()
        self.ownership.calls.clear()
        self.store.calls.clear()

        with self.assertRaisesRegex(
            GitHubObservationError, "exact publication journal"
        ):
            self.collector(clock=lambda: STARTED).collect_from_verified_host(
                policy_backend=inputs["policy_backend"],
                input_provider=provider,
                publication_records=changed,
            )

        self.identity.verify_observer.assert_not_called()
        self.identity.verify_merge_actor.assert_not_called()
        self.graphql.read_pull_request.assert_not_called()
        self.reviews.read_all.assert_not_called()
        self.checks.read_all.assert_not_called()
        self.assertEqual(self.candidate.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.store.calls, [])

    def test_verified_host_rejects_nonterminal_or_unavailable_inputs_before_reads(self):
        inputs = self.inputs()
        provider = InputProvider(inputs["input_envelope"])
        pending = {
            "state": "pending",
            "disposition": "reconcile-required",
            "request": copy.deepcopy(self.helper.publication_request),
            "dispatch": copy.deepcopy(self.dispatch),
            "receipt": None,
        }

        with self.assertRaisesRegex(
            GitHubObservationError, "terminal publication journal"
        ):
            self.collector(clock=lambda: STARTED).collect_from_verified_host(
                policy_backend=inputs["policy_backend"],
                input_provider=provider,
                publication_records=pending,
            )
        self.assertEqual(provider.calls, [])

        failing = FailingInputProvider()
        terminal = {
            "state": "awaiting-review",
            "disposition": "awaiting-review",
            "request": copy.deepcopy(self.helper.publication_request),
            "dispatch": copy.deepcopy(self.dispatch),
            "receipt": copy.deepcopy(self.helper.publication_receipt),
        }
        with self.assertRaisesRegex(
            GitHubObservationError, "trusted host input unavailable"
        ):
            self.collector(clock=lambda: STARTED).collect_from_verified_host(
                policy_backend=inputs["policy_backend"],
                input_provider=failing,
                publication_records=terminal,
            )
        self.assertEqual(failing.calls, 1)
        self.identity.verify_observer.assert_not_called()
        self.identity.verify_merge_actor.assert_not_called()
        self.graphql.read_pull_request.assert_not_called()
        self.reviews.read_all.assert_not_called()
        self.checks.read_all.assert_not_called()
        self.assertEqual(self.candidate.calls, [])
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.store.calls, [])

    def test_verified_host_rejects_bad_policy_or_journal_before_input_provider(self):
        inputs = self.inputs()
        provider = InputProvider(inputs["input_envelope"])
        terminal = {
            "state": "awaiting-review",
            "disposition": "awaiting-review",
            "request": copy.deepcopy(self.helper.publication_request),
            "dispatch": copy.deepcopy(self.dispatch),
            "receipt": copy.deepcopy(self.helper.publication_receipt),
        }
        wrong_policy = PolicyBackend(
            copy.deepcopy(self.helper.responses),
            installation_credential("different"),
            self.helper.classic_policy,
            self.helper.active_policy,
        )

        with self.assertRaisesRegex(GitHubObservationError, "share the observer"):
            self.collector(clock=lambda: STARTED).collect_from_verified_host(
                policy_backend=wrong_policy,
                input_provider=provider,
                publication_records=terminal,
            )
        self.assertEqual(provider.calls, [])

        terminal["request"]["request_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            GitHubObservationError, "terminal publication journal is invalid"
        ):
            self.collector(clock=lambda: STARTED).collect_from_verified_host(
                policy_backend=inputs["policy_backend"],
                input_provider=provider,
                publication_records=terminal,
            )
        self.assertEqual(provider.calls, [])

    def test_eagerly_materializes_every_remaining_base_surface_before_ownership(self):
        backend = RecordingBackend(
            copy.deepcopy(self.helper.responses),
            self.events,
            self.installation,
            self.helper.classic_policy,
            self.helper.active_policy,
        )
        original_identity = self.identity.verify_observer
        original_merge_identity = self.identity.verify_merge_actor
        original_graphql = self.graphql.read_pull_request
        original_reviews = self.reviews.read_all
        original_checks = self.checks.read_all
        self.identity.verify_observer = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:identity"), original_identity(*args, **kwargs)
            )[1]
        )
        self.identity.verify_merge_actor = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:merge-identity"),
                original_merge_identity(*args, **kwargs),
            )[1]
        )
        self.graphql.read_pull_request = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:graphql"), original_graphql(*args, **kwargs)
            )[1]
        )
        self.reviews.read_all = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:reviews"), original_reviews(*args, **kwargs)
            )[1]
        )
        self.checks.read_all = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:checks"), original_checks(*args, **kwargs)
            )[1]
        )
        times = iter((STARTED, COMPLETED))

        def clock():
            value = next(times)
            self.events.append("clock:start" if value == STARTED else "clock:complete")
            return value

        self.collector(clock=clock).collect_and_persist(**self.inputs(backend=backend))

        completed_index = self.events.index("clock:complete")
        candidate_index = self.events.index("candidate")
        ownership_index = self.events.index("ownership")
        first_reader_index = min(
            index
            for index, event in enumerate(self.events)
            if event.startswith(("base:", "reader:"))
        )
        self.assertLess(self.events.index("input-auth"), first_reader_index)
        self.assertTrue(all(
            index < completed_index
            for index, event in enumerate(self.events)
            if event.startswith(("base:", "reader:"))
        ))
        self.assertLess(candidate_index, completed_index)
        self.assertLess(completed_index, ownership_index)
        self.assertLess(ownership_index, self.events.index("store"))
        self.assertEqual(
            self.ownership.calls[0]["evidence_completed_at"],
            "2026-08-11T12:08:20+00:00",
        )

    def test_rejects_reader_with_a_different_installation_credential(self):
        different = GitHubGraphQLClient(installation_credential("different"))
        with self.assertRaisesRegex(ValueError, "share one observer"):
            self.collector(graphql=different)

        self.ownership.credential = different.credential
        with self.assertRaisesRegex(ValueError, "share one observer"):
            self.collector()

        self.ownership.credential = self.installation
        self.candidate.credential = different.credential
        with self.assertRaisesRegex(ValueError, "share one observer"):
            self.collector()

    def test_rejects_policy_backend_with_a_different_credential_before_reads(self):
        backend = PolicyBackend(
            copy.deepcopy(self.helper.responses),
            installation_credential("different"),
            self.helper.classic_policy,
            self.helper.active_policy,
        )
        with self.assertRaisesRegex(GitHubObservationError, "share the observer"):
            self.collector().collect_and_persist(**self.inputs(backend=backend))
        self.graphql.read_pull_request.assert_not_called()

    def test_rejects_a_merge_identity_for_a_different_receipt_before_policy_reads(self):
        changed_receipt = copy.deepcopy(
            self.helper.merge_identity.credential_receipt
        )
        changed_receipt["credential_receipt_id"] = (
            "merge_credential_receipt_different1"
        )
        self.identity.verify_merge_actor.return_value = replace(
            self.helper.merge_identity,
            credential_receipt=changed_receipt,
        )
        inputs = self.inputs()

        with self.assertRaisesRegex(GitHubObservationError, "supplied receipt"):
            self.collector().collect_and_persist(**inputs)

        self.graphql.read_pull_request.assert_not_called()
        self.assertEqual(inputs["policy_backend"].actor_calls, [])
        self.assertEqual(self.store.calls, [])

    def test_rejects_stale_receipt_before_any_read_or_persist(self):
        collector = self.collector(clock=lambda: STARTED.replace(second=1))
        with self.assertRaisesRegex(GitHubObservationError, "trusted collection start"):
            collector.collect_and_persist(**self.inputs())
        self.identity.verify_observer.assert_not_called()
        self.identity.verify_merge_actor.assert_not_called()
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.store.calls, [])

    @unittest.skipIf(os.name == "nt", "host ACL verification is POSIX-only")
    def test_rejects_rehashed_or_split_input_before_any_github_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            host = root / "operator-host"
            repository.mkdir(mode=0o755)
            host.mkdir(mode=0o700)
            authenticator = FakeHostAuthenticator()
            store = HostArtifactCollectionStore(
                repository,
                host,
                store_id="host_artifact_store_collector1",
                authenticator=authenticator,
            )
            collector = GitHubAuthenticatedEvidenceCollector(
                identity=self.identity,
                graphql=self.graphql,
                reviews=self.reviews,
                checks=self.checks,
                candidate=self.candidate,
                ownership=self.ownership,
                store=store,
                clock=lambda: STARTED,
            )
            inputs = self.inputs(
                authenticator=authenticator,
                store_id="host_artifact_store_collector1",
            )
            envelope = inputs["input_envelope"]
            envelope["payload"]["documents"]["policy"]["authority"][
                "issuer"
            ] = "attacker@example"
            envelope["attestation"]["payload_sha256"] = canonical_sha256(
                envelope["payload"]
            )
            envelope["envelope_sha256"] = canonical_sha256(
                envelope, "envelope_sha256"
            )

            with self.assertRaisesRegex(
                GitHubObservationError, "input attestation verification"
            ):
                collector.collect_and_persist(**inputs)

            split_documents = copy.deepcopy(self.input_documents)
            split_documents["policy"]["repository"]["name"] = (
                "different-repo"
            )
            split_documents["policy"]["policy_sha256"] = canonical_sha256(
                split_documents["policy"], "policy_sha256"
            )
            split_envelope = collection_input_envelope(
                split_documents,
                authenticator,
                store_id="host_artifact_store_collector1",
                policy_read=self.helper.context["policy_read"],
                object_evidence=self.helper.context["object_evidence"],
            )
            with self.assertRaisesRegex(
                GitHubObservationError, "input document bindings differ"
            ):
                collector.collect_and_persist(
                    policy_backend=inputs["policy_backend"],
                    input_envelope=split_envelope,
                )

            self.identity.verify_observer.assert_not_called()
            self.identity.verify_merge_actor.assert_not_called()
            self.graphql.read_pull_request.assert_not_called()
            self.reviews.read_all.assert_not_called()
            self.checks.read_all.assert_not_called()
            self.assertEqual(inputs["policy_backend"].actor_calls, [])
            self.assertEqual(self.candidate.calls, [])
            self.assertEqual(self.ownership.calls, [])
            self.assertFalse((host / "artifact-collections").exists())

    def test_rejects_backwards_or_expired_completion_before_proof_and_store(self):
        for completed in (
            STARTED - timedelta(seconds=1),
            datetime(2026, 8, 11, 12, 15, tzinfo=timezone.utc),
        ):
            with self.subTest(completed=completed):
                self.ownership.calls.clear()
                self.store.calls.clear()
                times = iter((STARTED, completed))
                with self.assertRaisesRegex(GitHubObservationError, "trusted window"):
                    self.collector(clock=lambda: next(times)).collect_and_persist(
                        **self.inputs()
                    )
                self.assertEqual(self.ownership.calls, [])
                self.assertEqual(self.store.calls, [])

    @unittest.skipIf(os.name == "nt", "host ACL verification is POSIX-only")
    def test_real_store_attests_reloads_and_preserves_the_exact_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            host = root / "operator-host"
            repository.mkdir(mode=0o755)
            host.mkdir(mode=0o700)
            authenticator = FakeHostAuthenticator()
            store = HostArtifactCollectionStore(
                repository,
                host,
                store_id="host_artifact_store_collector1",
                authenticator=authenticator,
                clock=lambda: datetime(
                    2026, 8, 11, 12, 8, 30, tzinfo=timezone.utc
                ),
            )
            values = iter((STARTED, COMPLETED))
            collector = GitHubAuthenticatedEvidenceCollector(
                identity=self.identity,
                graphql=self.graphql,
                reviews=self.reviews,
                checks=self.checks,
                candidate=self.candidate,
                ownership=self.ownership,
                store=store,
                clock=lambda: next(values),
            )

            result = collector.collect_and_persist(**self.inputs(
                authenticator=authenticator,
                store_id="host_artifact_store_collector1",
            ))
            loaded = store.load(self.helper.context["evidence_id"])

            self.assertEqual(result.envelope, loaded)
            self.assertEqual(
                loaded["payload"]["documents"]["evidence"],
                result.snapshot.evidence,
            )
            self.assertEqual(authenticator.attest_calls, 2)
            self.assertGreaterEqual(authenticator.verify_calls, 3)

    def test_module_has_no_secret_loader_command_publication_or_merge_route(self):
        source_path = (
            ROOT
            / "pathfinder_core"
            / "adapters"
            / "github_evidence_collector.py"
        )
        source = source_path.read_text()
        for forbidden in (
            "GitHubEvidenceCredential(",
            "GitHubHTTPS",
            "os.environ",
            "subprocess",
            "MergeExecutor",
            "GitHubMergeBackend",
            "PublicationController",
            "def publish(",
            "def merge(",
        ):
            self.assertNotIn(forbidden, source)
        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path == source_path:
                continue
            if "GitHubAuthenticatedEvidenceCollector(" in path.read_text():
                callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
