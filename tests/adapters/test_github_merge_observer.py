import copy
import hashlib
import json
import unittest
from pathlib import Path

from pathfinder_core.adapters.github_merge_observer import (
    EndpointResponse,
    GitHubMergeObservationBackend,
    GitHubMergeObserver,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "adapters" / "fixtures" / "github-merge-observer.json"
JOURNAL = ROOT / "tests" / "contracts" / "fixtures" / "publication-journal-contracts.json"


def load_json(path):
    return json.loads(path.read_text())


def audit(raw):
    return RequestAudit(raw["request_id"], raw["observed_at"], raw["etag"])


class FixtureObservationBackend:
    def __init__(self, responses, *, failure=None, timeout_surface=None):
        self.responses = responses
        self.failure = failure
        self.timeout_surface = timeout_surface
        self.calls = []

    def _raise(self, surface):
        self.calls.append(surface)
        if surface == self.timeout_surface:
            raise TimeoutError("fixture timeout")
        if self.failure and surface == self.failure[0]:
            raise GitHubObservationError(self.failure[1], surface, "fixture failure")

    def _endpoint(self, surface):
        self._raise(surface)
        raw = self.responses[surface]
        return EndpointResponse(raw["data"], audit(raw["audit"]))

    def _page(self, surface):
        self._raise(surface)
        raw = self.responses[surface]
        page = raw["page"]
        return PageResponse(
            tuple(raw["items"]), page["pages"], page["total_count"],
            page["complete"], page["truncated"], page["last_cursor"],
            tuple(audit(item) for item in raw["audits"]),
        )

    def read_repository(self): return self._endpoint("repository")
    def read_credential_actor(self): return self._endpoint("actor")
    def read_pull_request(self): return self._endpoint("pull-request")
    def read_refs(self): return self._endpoint("refs")
    def read_changed_files(self): return self._page("changed-files")
    def read_classic_protection(self): return self._endpoint("classic-protection")
    def read_active_rules(self): return self._page("active-rules")
    def read_source_rulesets(self):
        return self._page("source-rulesets"), self._page("bypass-actors")
    def read_reviews(self): return self._page("reviews")
    def read_review_requests(self): return self._page("review-requests")
    def read_review_threads(self): return self._page("review-threads")
    def read_check_runs(self): return self._page("check-runs")
    def read_commit_statuses(self): return self._page("commit-statuses")
    def read_deployments(self): return self._page("deployments")
    def read_merged_state(self): return self._endpoint("merged-state")


class GitHubMergeObserverTests(unittest.TestCase):
    def setUp(self):
        fixture = load_json(FIXTURE)
        self.context = fixture["context"]
        self.responses = fixture["responses"]
        self.bindings = load_json(JOURNAL)["evidence"]["bindings"]

    def observe(self, responses=None, **backend_options):
        backend = FixtureObservationBackend(
            responses or copy.deepcopy(self.responses), **backend_options
        )
        result = GitHubMergeObserver(backend).observe(
            bindings=self.bindings, **self.context
        )
        return result, backend

    def test_complete_fixture_is_deterministic_and_schema_valid(self):
        first, backend = self.observe()
        second, _ = self.observe()
        self.assertEqual(first.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(first.evidence, second.evidence)
        evidence = first.evidence
        self.assertTrue(evidence["observation"]["collection_complete"])
        self.assertEqual(evidence["repository"]["merge_methods"], {
            "squash": True, "merge_commit": False, "rebase": False,
        })
        self.assertEqual(evidence["pull_request"]["head_repository_id"], 123456789)
        self.assertEqual(evidence["diff"]["changed_file_count"], 2)
        self.assertEqual(evidence["diff"]["patch_bytes"], 8192)
        self.assertEqual(evidence["mergeability"]["review_decision"], "APPROVED")
        self.assertEqual(len(evidence["active_rules"]), 2)
        self.assertEqual(evidence["active_rules"][0]["allowed_merge_methods"], ["squash"])
        self.assertEqual(
            evidence["source_rulesets"][0]["active_rules_sha256"],
            "23eb0b4836e84033625300b4750d459130d2d612ea3b4fd33d087125d8443365",
        )
        self.assertEqual(len(evidence["reviews"]), 1)
        self.assertEqual(len(evidence["checks"]), 2)
        self.assertEqual(evidence["actor"]["bypass_assessment"], "no-match")
        self.assertEqual(len(evidence["observation"]["requests"]), 16)
        request_ids = [item["request_id"] for item in evidence["observation"]["requests"]]
        encoded = json.dumps(request_ids, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(
            evidence["observation"]["request_ids_sha256"],
            hashlib.sha256(encoded).hexdigest(),
        )
        self.assertEqual(len(backend.calls), 16)

    def test_transport_failures_are_distinct_typed_outcomes(self):
        cases = (
            ObservationOutcome.AUTH_ERROR,
            ObservationOutcome.PERMISSION_MISSING,
            ObservationOutcome.NOT_FOUND,
            ObservationOutcome.RATE_LIMITED,
            ObservationOutcome.API_UNAVAILABLE,
        )
        for outcome in cases:
            with self.subTest(outcome=outcome):
                result, _ = self.observe(failure=("repository", outcome))
                self.assertEqual(result.outcome, outcome)
                self.assertEqual(result.surface, "repository")
                self.assertIsNone(result.evidence)
        result, _ = self.observe(timeout_surface="repository")
        self.assertEqual(result.outcome, ObservationOutcome.TIMEOUT)
        self.assertIsNone(result.evidence)

    def test_404_is_not_inferred_as_unprotected(self):
        result, _ = self.observe(
            failure=("classic-protection", ObservationOutcome.NOT_FOUND)
        )
        self.assertEqual(result.outcome, ObservationOutcome.NOT_FOUND)
        self.assertIsNone(result.evidence)

        responses = copy.deepcopy(self.responses)
        classic = responses["classic-protection"]["data"]
        classic.update({
            "status": "absent", "settings": None, "required_review_count": None,
            "required_checks": [], "bypass_visibility": "not-applicable",
            "enforce_admins": None, "conversation_resolution_required": None,
            "last_push_approval_required": None,
            "absence_proof": {
                "endpoint": "classic-protection", "repository_id": 123456789,
                "repository_node_id": "R_kgDOExample1", "permission_confirmed": True,
            },
        })
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.evidence["classic_protection"]["status"], "absent")

        responses["classic-protection"]["data"]["absence_proof"]["repository_id"] = 1
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertEqual(result.evidence["classic_protection"]["status"], "unknown")

    def test_incomplete_page_preserves_cursor_and_fails_closed(self):
        responses = copy.deepcopy(self.responses)
        responses["changed-files"]["page"].update({
            "complete": False, "truncated": True, "last_cursor": "cursor-page-1",
        })
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.PAGINATION_INCOMPLETE)
        self.assertFalse(result.evidence["observation"]["collection_complete"])
        self.assertEqual(
            result.evidence["pagination"]["pull_files"]["last_cursor"],
            "cursor-page-1",
        )
        self.assertIn("pagination-incomplete", result.evidence["unknown_reasons"])

    def test_merged_state_reconciles_and_ref_drift_stops(self):
        responses = copy.deepcopy(self.responses)
        responses["pull-request"]["data"]["state"] = "closed"
        responses["merged-state"]["data"] = {
            "merged": True,
            "merge_commit_sha": "dddddddddddddddddddddddddddddddddddddddd",
            "merged_at": "2026-08-11T12:08:15+00:00",
            "merged_by": {
                "id": 97531, "node_id": "U_kgDOBot1234",
                "login": "pathfinder-merge[bot]",
            },
        }
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.evidence["pull_request"]["state"], "merged")
        self.assertEqual(
            result.evidence["pull_request"]["merge_commit_sha"],
            "dddddddddddddddddddddddddddddddddddddddd",
        )

        responses = copy.deepcopy(self.responses)
        responses["refs"]["data"]["head"]["sha"] = "a" * 40
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertIsNone(result.evidence)

    def test_missing_bypass_visibility_is_a_typed_unknown(self):
        responses = copy.deepcopy(self.responses)
        del responses["source-rulesets"]["items"][0]["bypass_visibility"]
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.BYPASS_VISIBILITY_UNKNOWN)
        self.assertEqual(
            result.evidence["source_rulesets"][0]["bypass_visibility"], "unknown"
        )
        self.assertEqual(result.evidence["actor"]["bypass_assessment"], "unknown")

    def test_bypass_actor_match_and_unsupported_rule_are_explicit(self):
        responses = copy.deepcopy(self.responses)
        responses["bypass-actors"]["items"] = [{
            "ruleset_id": 7001, "actor_type": "Integration", "actor_id": 24680,
        }]
        responses["bypass-actors"]["page"]["total_count"] = 1
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.OBSERVED)
        self.assertEqual(result.evidence["actor"]["bypass_assessment"], "match")
        self.assertEqual(
            result.evidence["source_rulesets"][0]["bypass_actor_keys"],
            ["Integration:24680"],
        )

        responses = copy.deepcopy(self.responses)
        responses["active-rules"]["items"].append({
            "ruleset_id": 7001, "source_type": "Repository",
            "source_id": 123456789, "rule_type": "future_metadata_rule",
            "parameters": {"pattern": "future"}, "approval_count": None,
            "required_checks": [], "strict": None,
        })
        responses["active-rules"]["page"]["total_count"] = 3
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertIn("unsupported-active-rule", result.evidence["unsupported_reasons"])
        self.assertIn("field-unknown", result.evidence["unknown_reasons"])

    def test_unattributed_ruleset_and_ambiguous_actor_stop_without_evidence(self):
        responses = copy.deepcopy(self.responses)
        responses["source-rulesets"]["items"][0]["source_id"] = None
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.RULESET_EVIDENCE_INCOMPLETE)
        self.assertIsNone(result.evidence)

        responses = copy.deepcopy(self.responses)
        responses["actor"]["data"]["user"]["login"] = "ambiguous-user"
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.ACTOR_IDENTITY_UNKNOWN)
        self.assertIsNone(result.evidence)

    def test_malformed_and_future_fields_never_look_complete(self):
        responses = copy.deepcopy(self.responses)
        del responses["repository"]["data"]["id"]
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.MALFORMED_RESPONSE)
        self.assertIsNone(result.evidence)

        responses = copy.deepcopy(self.responses)
        responses["repository"]["data"]["future_field"] = {"enabled": True}
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertFalse(result.evidence["observation"]["collection_complete"])
        self.assertIsNotNone(result.evidence["observation"]["unknown_payloads_sha256"])
        self.assertIn("field-unknown", result.evidence["unknown_reasons"])

    def test_backend_protocol_exposes_read_methods_only(self):
        methods = {
            name for name, value in GitHubMergeObservationBackend.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertTrue(methods)
        self.assertTrue(all(name.startswith("read_") for name in methods))
        for forbidden in ("post", "put", "patch", "delete", "push", "merge"):
            self.assertNotIn(forbidden, methods)
        source = (
            ROOT / "pathfinder_core" / "adapters" / "github_merge_observer.py"
        ).read_text()
        for network_primitive in (
            "import requests", "import urllib", "import http.client", "import subprocess",
        ):
            self.assertNotIn(network_primitive, source)

    def test_rule_parameter_cross_checks_fail_closed(self):
        responses = copy.deepcopy(self.responses)
        status = responses["active-rules"]["items"][1]
        status["parameters"]["required_status_checks"][0]["integration_id"] = 1
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertIn("field-unknown", result.evidence["unknown_reasons"])

        responses = copy.deepcopy(self.responses)
        responses["active-rules"]["items"][0]["parameters"]["future_setting"] = True
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertIn("field-unknown", result.evidence["unknown_reasons"])

        responses = copy.deepcopy(self.responses)
        responses["reviews"]["items"][0]["repository_permission"]["user"]["id"] = 1
        result, _ = self.observe(responses)
        self.assertEqual(result.outcome, ObservationOutcome.FIELD_UNKNOWN)
        self.assertIsNone(result.evidence)


if __name__ == "__main__":
    unittest.main()
