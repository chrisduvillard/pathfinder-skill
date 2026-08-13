import copy
import json
import os
import tempfile
import unittest
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
from pathfinder_core.host_artifact_store import HostArtifactCollectionStore
from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
from tests.adapters.test_github_branch_ownership import credential_receipt
from tests.adapters.test_github_evidence_composer import (
    GitHubCompleteEvidenceComposerTests,
)
from tests.adapters.test_github_merge_observer import FixtureObservationBackend
from tests.core.test_host_artifact_store import FakeHostAuthenticator


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

    def persist(self, **values):
        self.calls.append(copy.deepcopy(values))
        if self.events is not None:
            self.events.append("store")
        return {"authenticated": True, "evidence_id": values["evidence"]["evidence_id"]}


class PolicyBackend(FixtureObservationBackend):
    def __init__(self, responses, credential, classic_policy, active_policy):
        super().__init__(responses)
        self.credential = credential
        self.classic_policy = classic_policy
        self.active_policy = active_policy

    def read_all(self):
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
        self.policy = authority["policy"]
        self.authorization = authority["authorization"]
        self.dispatch = publication["dispatch"]
        self.installation = installation_credential()
        observer_client = GitHubGETClient(self.installation)
        self.identity = GitHubIdentityVerifier(
            observer_app=GitHubGETClient(app_credential("observer")),
            observer_installation=observer_client,
        )
        self.graphql = GitHubGraphQLClient(self.installation)
        self.reviews = GitHubReviewReader(observer_client)
        self.checks = GitHubCheckEvidenceReader(observer_client)
        self.identity.verify_observer = Mock(return_value=helper.identity)
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

    def inputs(self, *, backend=None):
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
            "observer_credential_receipt": self.helper.identity.credential_receipt,
            "publication_request": self.helper.publication_request,
            "publication_dispatch": self.dispatch,
            "publication_receipt": self.helper.publication_receipt,
            "publication_credential_receipt": credential_receipt(),
            "policy": self.policy,
            "authorization": self.authorization,
            "protected_policy": ProtectedSurfaceRegistry.load().to_document(),
            "policy_read": self.helper.context["policy_read"],
            "object_evidence": self.helper.context["object_evidence"],
            "evidence_id": self.helper.context["evidence_id"],
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
            before,
            {key: value for key, value in inputs.items() if key != "policy_backend"},
        )

    def test_eagerly_materializes_every_remaining_base_surface_before_ownership(self):
        backend = RecordingBackend(
            copy.deepcopy(self.helper.responses),
            self.events,
            self.installation,
            self.helper.classic_policy,
            self.helper.active_policy,
        )
        original_identity = self.identity.verify_observer
        original_graphql = self.graphql.read_pull_request
        original_reviews = self.reviews.read_all
        original_checks = self.checks.read_all
        self.identity.verify_observer = Mock(
            side_effect=lambda *args, **kwargs: (
                self.events.append("reader:identity"), original_identity(*args, **kwargs)
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

    def test_rejects_stale_receipt_before_any_read_or_persist(self):
        collector = self.collector(clock=lambda: STARTED.replace(second=1))
        with self.assertRaisesRegex(GitHubObservationError, "trusted collection start"):
            collector.collect_and_persist(**self.inputs())
        self.identity.verify_observer.assert_not_called()
        self.assertEqual(self.ownership.calls, [])
        self.assertEqual(self.store.calls, [])

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

            result = collector.collect_and_persist(**self.inputs())
            loaded = store.load(self.helper.context["evidence_id"])

            self.assertEqual(result.envelope, loaded)
            self.assertEqual(
                loaded["payload"]["documents"]["evidence"],
                result.snapshot.evidence,
            )
            self.assertEqual(authenticator.attest_calls, 1)
            self.assertGreaterEqual(authenticator.verify_calls, 2)

    def test_module_has_no_secret_loader_command_publication_or_merge_route(self):
        source = (
            ROOT
            / "pathfinder_core"
            / "adapters"
            / "github_evidence_collector.py"
        ).read_text()
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


if __name__ == "__main__":
    unittest.main()
