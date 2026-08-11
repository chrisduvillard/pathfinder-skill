import copy
import inspect
import json
import unittest
from datetime import datetime
from pathlib import Path

from pathfinder_core.merge_policy import (
    CheckRequirement,
    DenyCode,
    EligibilityOutcome,
    MergePolicyEvaluator,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_FIXTURE = ROOT / "tests" / "contracts" / "fixtures" / "publication-contracts.json"
EVIDENCE_FIXTURE = ROOT / "tests" / "contracts" / "fixtures" / "publication-journal-contracts.json"
CASE_FIXTURE = ROOT / "tests" / "core" / "fixtures" / "merge-policy-cases.json"
NOW = datetime.fromisoformat("2026-08-11T12:08:30+00:00")


def load_json(path):
    return json.loads(path.read_text())


def normalize_diff(evidence):
    diff = evidence["diff"]
    files = diff["changed_files"]
    files.sort(key=lambda item: item["path"])
    diff["changed_file_count"] = len(files)
    diff["total_line_changes"] = sum(item["changes"] for item in files)
    diff["protected_categories"] = sorted({
        value for item in files for value in item["protected_categories"]
    })
    diff["special_files"] = sorted({
        value for item in files for value in item["special_files"]
    })
    diff["changed_files_sha256"] = canonical_sha256(files)
    diff["diff_sha256"] = canonical_sha256(diff, "diff_sha256")


def rehash_evidence(evidence, *, diff=False):
    if diff:
        normalize_diff(evidence)
    for source in evidence["source_rulesets"]:
        signature = [
            {
                "rule_type": rule["rule_type"],
                "parameters_sha256": rule["parameters_sha256"],
            }
            for rule in evidence["active_rules"]
            if rule["ruleset_id"] == source["id"]
        ]
        signature.sort(key=lambda item: item["rule_type"])
        source["active_rules_sha256"] = canonical_sha256(signature)
    evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")


def rebind_authority(policy, authorization, evidence):
    policy["policy_sha256"] = canonical_sha256(policy, "policy_sha256")
    authorization["policy"] = {
        "policy_id": policy["policy_id"], "policy_sha256": policy["policy_sha256"],
    }
    authorization["repository"] = copy.deepcopy(policy["repository"])
    authorization["merge_method"] = policy["merge_method"]
    authorization["authorization_sha256"] = canonical_sha256(
        authorization, "authorization_sha256"
    )
    evidence["bindings"].update({
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
        "merge_authorization_id": authorization["merge_authorization_id"],
        "authorization_sha256": authorization["authorization_sha256"],
        "mission_id": authorization["mission"]["mission_id"],
        "binding_id": authorization["mission"]["binding_id"],
        "mission_authorization_id": authorization["mission"]["mission_authorization_id"],
        "protected_policy_sha256": policy["path_policy"]["protected_policy_sha256"],
    })
    rehash_evidence(evidence)


def codes(verdict):
    return {block.code for block in verdict.blocks}


class MergePolicyEvaluatorTests(unittest.TestCase):
    def setUp(self):
        authority = load_json(AUTHORITY_FIXTURE)
        self.policy = authority["policy"]
        self.authorization = authority["authorization"]
        self.evidence = load_json(EVIDENCE_FIXTURE)["evidence"]
        self.evaluator = MergePolicyEvaluator()

    def evaluate(self, policy=None, authorization=None, evidence=None, *, now=NOW):
        return self.evaluator.evaluate(
            self.policy if policy is None else policy,
            self.authorization if authorization is None else authorization,
            self.evidence if evidence is None else evidence,
            now=now,
        )

    def test_complete_layered_fixture_is_deterministically_eligible(self):
        original = copy.deepcopy((self.policy, self.authorization, self.evidence))
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first, second)
        self.assertEqual(first.outcome, EligibilityOutcome.ELIGIBLE)
        self.assertTrue(first.eligible)
        self.assertEqual(first.blocks, ())
        self.assertEqual(first.required_approvals, 1)
        self.assertEqual(first.approval_actor_ids, (44444,))
        self.assertEqual(first.required_checks, (
            CheckRequirement("preflight (ubuntu-latest)", 15368),
        ))
        self.assertEqual((self.policy, self.authorization, self.evidence), original)

    def test_missing_malformed_hash_and_clock_inputs_fail_closed(self):
        missing = (
            (None, self.authorization, self.evidence, DenyCode.POLICY_MISSING),
            (self.policy, None, self.evidence, DenyCode.AUTHORIZATION_MISSING),
            (self.policy, self.authorization, None, DenyCode.EVIDENCE_MISSING),
        )
        for policy, authorization, evidence, code in missing:
            with self.subTest(code=code):
                verdict = self.evaluator.evaluate(
                    policy, authorization, evidence, now=NOW
                )
                self.assertEqual(verdict.outcome, EligibilityOutcome.UNKNOWN)
                self.assertIn(code, codes(verdict))

        malformed = copy.deepcopy(self.policy)
        malformed["repository_override"] = True
        malformed["policy_sha256"] = canonical_sha256(malformed, "policy_sha256")
        verdict = self.evaluate(policy=malformed)
        self.assertEqual(verdict.outcome, EligibilityOutcome.UNKNOWN)
        self.assertIn(DenyCode.INPUT_INVALID, codes(verdict))

        changed = copy.deepcopy(self.evidence)
        changed["evidence_sha256"] = "0" * 64
        self.assertIn(DenyCode.IDENTITY_DRIFT, codes(self.evaluate(evidence=changed)))
        verdict = self.evaluate(now=datetime.fromisoformat("2026-08-11T12:08:30"))
        self.assertIn(DenyCode.INPUT_INVALID, codes(verdict))
        verdict = self.evaluate(now="2026-08-11T12:08:30+00:00")
        self.assertIn(DenyCode.INPUT_INVALID, codes(verdict))

    def test_authority_and_evidence_windows_are_independently_current(self):
        policy = copy.deepcopy(self.policy)
        authorization = copy.deepcopy(self.authorization)
        evidence = copy.deepcopy(self.evidence)
        policy["expires_at"] = "2026-08-11T12:08:00+00:00"
        rebind_authority(policy, authorization, evidence)
        self.assertIn(
            DenyCode.POLICY_EXPIRED,
            codes(self.evaluate(policy, authorization, evidence)),
        )

        policy = copy.deepcopy(self.policy)
        authorization = copy.deepcopy(self.authorization)
        evidence = copy.deepcopy(self.evidence)
        authorization["expires_at"] = "2026-08-11T12:08:00+00:00"
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        evidence["bindings"]["authorization_sha256"] = authorization["authorization_sha256"]
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.AUTHORIZATION_EXPIRED,
            codes(self.evaluate(policy, authorization, evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["observation"]["expires_at"] = "2026-08-11T12:08:25+00:00"
        rehash_evidence(evidence)
        self.assertIn(DenyCode.EVIDENCE_EXPIRED, codes(self.evaluate(evidence=evidence)))

    def test_fixture_driven_candidate_matrix_returns_exact_codes(self):
        for case in load_json(CASE_FIXTURE)["cases"]:
            with self.subTest(case=case["name"]):
                evidence = copy.deepcopy(self.evidence)
                for update in case["updates"]:
                    *path, value = update
                    parent = evidence
                    for segment in path[:-1]:
                        parent = parent[segment]
                    parent[path[-1]] = value
                rehash_evidence(evidence)
                verdict = self.evaluate(evidence=evidence)
                self.assertIn(DenyCode(case["code"]), codes(verdict))
                self.assertFalse(verdict.eligible)

    def test_identity_audit_and_repository_bindings_cannot_drift(self):
        cases = []
        evidence = copy.deepcopy(self.evidence)
        evidence["bindings"]["mission_id"] = "mission_different1"
        rehash_evidence(evidence)
        cases.append(evidence)

        evidence = copy.deepcopy(self.evidence)
        evidence["repository"]["owner"] = "different-owner"
        rehash_evidence(evidence)
        cases.append(evidence)

        evidence = copy.deepcopy(self.evidence)
        evidence["pull_request"]["base_ref"] = "develop"
        rehash_evidence(evidence)
        cases.append(evidence)

        evidence = copy.deepcopy(self.evidence)
        evidence["observation"]["request_ids_sha256"] = "0" * 64
        rehash_evidence(evidence)
        cases.append(evidence)

        for index, evidence in enumerate(cases):
            with self.subTest(case=index):
                self.assertIn(DenyCode.IDENTITY_DRIFT, codes(self.evaluate(evidence=evidence)))

    def test_diff_hash_paths_protected_surfaces_and_effective_limits(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["diff"]["changed_file_count"] = 99
        rehash_evidence(evidence)
        self.assertIn(DenyCode.DIFF_DRIFT, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["diff"]["changed_files"][0]["path"] = "README.md"
        rehash_evidence(evidence, diff=True)
        self.assertIn(DenyCode.PATH_NOT_ALLOWED, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["diff"]["changed_files"][0]["path"] = ".github/workflows/ci.yml"
        rehash_evidence(evidence, diff=True)
        self.assertIn(DenyCode.PATH_DENIED, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        item = evidence["diff"]["changed_files"][0]
        item["protected_categories"] = ["workflow-policy"]
        item["special_files"] = ["workflow"]
        rehash_evidence(evidence, diff=True)
        self.assertIn(DenyCode.PROTECTED_SURFACE, codes(self.evaluate(evidence=evidence)))

        policy = copy.deepcopy(self.policy)
        authorization = copy.deepcopy(self.authorization)
        evidence = copy.deepcopy(self.evidence)
        policy["diff_limits"]["max_changed_files"] = 1
        rebind_authority(policy, authorization, evidence)
        self.assertIn(
            DenyCode.DIFF_LIMIT_EXCEEDED,
            codes(self.evaluate(policy, authorization, evidence)),
        )

        limit_cases = (
            ("max_total_line_changes", 39),
            ("max_single_file_line_changes", 24),
            ("max_patch_bytes", 8191),
        )
        for field, value in limit_cases:
            with self.subTest(limit=field):
                policy = copy.deepcopy(self.policy)
                authorization = copy.deepcopy(self.authorization)
                evidence = copy.deepcopy(self.evidence)
                policy["diff_limits"][field] = value
                rebind_authority(policy, authorization, evidence)
                self.assertIn(
                    DenyCode.DIFF_LIMIT_EXCEEDED,
                    codes(self.evaluate(policy, authorization, evidence)),
                )

    def test_policy_layers_take_the_most_restrictive_review_floor(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["classic_protection"]["required_review_count"] = 2
        pull_rule = next(
            item for item in evidence["active_rules"]
            if item["rule_type"] == "pull_request"
        )
        pull_rule["approval_count"] = 3
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertEqual(verdict.required_approvals, 3)
        self.assertIn(DenyCode.INDEPENDENT_REVIEW_MISSING, codes(verdict))

        evidence = copy.deepcopy(self.evidence)
        classic = evidence["classic_protection"]
        classic.update({
            "status": "absent", "settings_sha256": None,
            "required_review_count": None, "required_checks": [],
            "bypass_visibility": "not-applicable", "bypass_actor_keys": [],
            "enforce_admins": None, "conversation_resolution_required": None,
            "last_push_approval_required": None,
        })
        evidence["active_rules"] = []
        evidence["source_rulesets"] = []
        for name in ("active_rules", "source_rulesets", "bypass_actors"):
            evidence["pagination"][name]["items"] = 0
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertIn(DenyCode.POLICY_UNENFORCED, codes(verdict))
        self.assertIn(DenyCode.INDEPENDENT_REVIEW_NOT_ENFORCED, codes(verdict))

        evidence = copy.deepcopy(self.evidence)
        evidence["classic_protection"]["required_review_count"] = 0
        pull_rule = next(
            item for item in evidence["active_rules"]
            if item["rule_type"] == "pull_request"
        )
        pull_rule["approval_count"] = 0
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.INDEPENDENT_REVIEW_NOT_ENFORCED,
            codes(self.evaluate(evidence=evidence)),
        )

    def test_ruleset_source_parameters_and_bypass_evidence_fail_closed(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["source_rulesets"] = []
        evidence["pagination"]["source_rulesets"]["items"] = 0
        rehash_evidence(evidence)
        self.assertIn(DenyCode.RULESET_DRIFT, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["source_rulesets"][0]["source_id"] = 1
        rehash_evidence(evidence)
        self.assertIn(DenyCode.RULESET_DRIFT, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        rule = next(item for item in evidence["active_rules"] if item["rule_type"] == "pull_request")
        rule["strict"] = True
        rehash_evidence(evidence)
        self.assertIn(DenyCode.RULESET_DRIFT, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["source_rulesets"][0]["bypass_actor_keys"] = ["Team:123"]
        evidence["pagination"]["bypass_actors"]["items"] = 1
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertIn(DenyCode.BYPASS_VISIBILITY_UNKNOWN, codes(verdict))
        self.assertEqual(verdict.outcome, EligibilityOutcome.UNKNOWN)

        evidence = copy.deepcopy(self.evidence)
        evidence["source_rulesets"][0]["active_rules_sha256"] = "0" * 64
        evidence["evidence_sha256"] = canonical_sha256(
            evidence, "evidence_sha256"
        )
        self.assertIn(DenyCode.RULESET_DRIFT, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        pull_rule = next(
            item for item in evidence["active_rules"]
            if item["rule_type"] == "pull_request"
        )
        pull_rule["allowed_merge_methods"] = ["merge"]
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.UNSUPPORTED_MERGE_METHOD,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["source_rulesets"][0]["bypass_actor_keys"] = ["Integration:24680"]
        evidence["pagination"]["bypass_actors"]["items"] = 1
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.MERGE_ACTOR_CAN_BYPASS,
            codes(self.evaluate(evidence=evidence)),
        )

    def test_unsupported_rule_types_are_typed_and_never_generic_success(self):
        mappings = {
            "merge_queue": "merge-queue-required",
            "required_deployments": "unsupported-required-deployments",
            "required_signatures": "unsupported-required-signatures",
            "code_scanning": "unsupported-code-scanning",
            "code_quality": "unsupported-code-quality",
            "file_path_restriction": "unsupported-file-restriction",
            "max_file_size": "unsupported-metadata-restriction",
        }
        for rule_type, reason in mappings.items():
            with self.subTest(rule_type=rule_type):
                evidence = copy.deepcopy(self.evidence)
                evidence["active_rules"].append({
                    "ruleset_id": 7001, "source_type": "Repository",
                    "source_id": 123456789, "rule_type": rule_type,
                    "parameters_sha256": "9" * 64, "approval_count": None,
                    "allowed_merge_methods": [], "required_checks": [], "strict": None,
                })
                evidence["active_rules"].sort(
                    key=lambda item: (item["ruleset_id"], item["rule_type"])
                )
                evidence["pagination"]["active_rules"]["items"] = len(
                    evidence["active_rules"]
                )
                evidence["unsupported_reasons"] = [reason]
                rehash_evidence(evidence)
                verdict = self.evaluate(evidence=evidence)
                self.assertIn(DenyCode(reason), codes(verdict))
                self.assertEqual(verdict.outcome, EligibilityOutcome.UNSUPPORTED)

        evidence = copy.deepcopy(self.evidence)
        evidence["unsupported_reasons"] = ["unsupported-active-rule"]
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertIn(DenyCode.UNSUPPORTED_ACTIVE_RULE, codes(verdict))
        self.assertEqual(verdict.outcome, EligibilityOutcome.UNSUPPORTED)

    def test_latest_effective_independent_human_review_only(self):
        mutations = (
            ("author", {"actor_id": 22222}),
            ("last-pusher", {"actor_id": 33333}),
            ("merge-actor", {"actor_id": 97531}),
            ("bot", {"actor_type": "Bot"}),
            ("read-only", {"repository_permission": "read"}),
            ("dismissed", {"dismissed": True}),
            ("stale", {"commit_sha": "a" * 40}),
            ("association", {"author_association": "NONE"}),
        )
        for name, updates in mutations:
            with self.subTest(case=name):
                evidence = copy.deepcopy(self.evidence)
                evidence["reviews"][0].update(updates)
                rehash_evidence(evidence)
                verdict = self.evaluate(evidence=evidence)
                self.assertEqual(verdict.approval_actor_ids, ())
                self.assertIn(DenyCode.INDEPENDENT_REVIEW_MISSING, codes(verdict))

        evidence = copy.deepcopy(self.evidence)
        evidence["reviews"].append({
            "id": 9002, "actor_id": 44444, "actor_login": "reviewer",
            "actor_type": "User", "repository_permission": "write",
            "state": "DISMISSED", "commit_sha": "c" * 40,
            "submitted_at": "2026-08-11T12:07:10+00:00",
            "author_association": "MEMBER", "dismissed": True,
        })
        evidence["pagination"]["reviews"]["items"] = 2
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.INDEPENDENT_REVIEW_MISSING,
            codes(self.evaluate(evidence=evidence)),
        )

    def test_review_changes_code_owner_and_threads_are_independent_blocks(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["reviews"][0]["state"] = "CHANGES_REQUESTED"
        rehash_evidence(evidence)
        self.assertIn(DenyCode.CHANGES_REQUESTED, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["review_requests"] = [{
            "actor_id": 55555, "actor_type": "Team", "as_code_owner": True,
        }]
        evidence["pagination"]["review_requests"]["items"] = 1
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.CODE_OWNER_REVIEW_MISSING,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["review_threads"][0]["resolved"] = False
        rehash_evidence(evidence)
        self.assertIn(DenyCode.UNRESOLVED_THREAD, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["reviews"][0].update({"state": "DISMISSED", "dismissed": False})
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.REVIEW_STATE_UNKNOWN,
            codes(self.evaluate(evidence=evidence)),
        )

    def test_required_check_matrix_proves_app_sha_status_and_conclusion(self):
        mutations = (
            ("wrong-app", {"app_id": 1}, DenyCode.UNEXPECTED_CHECK_APP),
            ("stale-sha", {"sha": "a" * 40}, DenyCode.CHECK_SHA_DRIFT),
            ("pending", {"status": "in_progress", "conclusion": None, "completed_at": None}, DenyCode.REQUIRED_CHECK_PENDING),
            ("failed", {"conclusion": "failure"}, DenyCode.REQUIRED_CHECK_FAILED),
        )
        for name, updates, code in mutations:
            with self.subTest(case=name):
                evidence = copy.deepcopy(self.evidence)
                evidence["checks"][0].update(updates)
                rehash_evidence(evidence)
                self.assertIn(code, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["checks"].append({
            "id": 8003, "source": "commit-status",
            "context": "preflight (ubuntu-latest)", "app_id": None,
            "sha": "c" * 40, "required": True, "status": "in_progress",
            "conclusion": None, "completed_at": None,
        })
        evidence["pagination"]["commit_statuses"]["items"] = 2
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.REQUIRED_CHECK_PENDING,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["checks"][0]["required"] = False
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.REQUIRED_CHECK_UNPROVEN,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["checks"][0]["completed_at"] = None
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.CHECK_EVIDENCE_INCOMPLETE,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["checks"].append({
            "id": 8003, "source": "check-run",
            "context": "preflight (ubuntu-latest)", "app_id": 15368,
            "sha": "c" * 40, "required": True, "status": "in_progress",
            "conclusion": None, "completed_at": None,
        })
        evidence["pagination"]["check_runs"]["items"] = 2
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.REQUIRED_CHECK_PENDING,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["checks"][0]["completed_at"] = "2026-08-11T12:08:25+00:00"
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.CHECK_EVIDENCE_INCOMPLETE,
            codes(self.evaluate(evidence=evidence)),
        )

    def test_classic_and_ruleset_check_requirements_are_unioned(self):
        evidence = copy.deepcopy(self.evidence)
        status_rule = next(
            item for item in evidence["active_rules"]
            if item["rule_type"] == "required_status_checks"
        )
        status_rule["required_checks"] = [{"context": "rules/scan", "app_id": 999}]
        evidence["checks"].append({
            "id": 8003, "source": "check-run", "context": "rules/scan",
            "app_id": 999, "sha": "c" * 40, "required": True,
            "status": "completed", "conclusion": "success",
            "completed_at": "2026-08-11T12:07:40+00:00",
        })
        evidence["pagination"]["check_runs"]["items"] = 2
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertTrue(verdict.eligible)
        self.assertEqual(verdict.required_checks, (
            CheckRequirement("preflight (ubuntu-latest)", 15368),
            CheckRequirement("rules/scan", 999),
        ))

    def test_pagination_request_audits_and_unknown_payloads_are_complete(self):
        evidence = copy.deepcopy(self.evidence)
        page = evidence["pagination"]["reviews"]
        page.update({"complete": False, "truncated": True, "last_cursor": "page-1"})
        evidence["observation"]["collection_complete"] = False
        evidence["unknown_reasons"] = ["pagination-incomplete"]
        rehash_evidence(evidence)
        self.assertIn(
            DenyCode.PAGINATION_INCOMPLETE,
            codes(self.evaluate(evidence=evidence)),
        )

        evidence = copy.deepcopy(self.evidence)
        evidence["observation"]["requests"] = [
            item for item in evidence["observation"]["requests"]
            if item["surface"] != "deployments"
        ]
        evidence["observation"]["request_ids_sha256"] = canonical_sha256([
            item["request_id"] for item in evidence["observation"]["requests"]
        ])
        rehash_evidence(evidence)
        self.assertIn(DenyCode.FIELD_UNKNOWN, codes(self.evaluate(evidence=evidence)))

        evidence = copy.deepcopy(self.evidence)
        evidence["observation"]["unknown_payloads_sha256"] = "a" * 64
        rehash_evidence(evidence)
        self.assertIn(DenyCode.FIELD_UNKNOWN, codes(self.evaluate(evidence=evidence)))

    def test_host_checks_are_additive_but_cannot_replace_github_enforcement(self):
        policy = copy.deepcopy(self.policy)
        authorization = copy.deepcopy(self.authorization)
        evidence = copy.deepcopy(self.evidence)
        policy["review_requirements"]["required_checks"].append({
            "context": "host/lint", "app_id": 999,
        })
        rebind_authority(policy, authorization, evidence)
        verdict = self.evaluate(policy, authorization, evidence)
        self.assertIn(DenyCode.REQUIRED_CHECK_UNPROVEN, codes(verdict))

        evidence["checks"].append({
            "id": 8003, "source": "check-run", "context": "host/lint",
            "app_id": 999, "sha": "c" * 40, "required": False,
            "status": "completed", "conclusion": "success",
            "completed_at": "2026-08-11T12:07:40+00:00",
        })
        evidence["pagination"]["check_runs"]["items"] = 2
        rehash_evidence(evidence)
        verdict = self.evaluate(policy, authorization, evidence)
        self.assertTrue(verdict.eligible)
        self.assertEqual(len(verdict.required_checks), 2)

    def test_unknown_precedes_unsupported_and_policy_blocks(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["unknown_reasons"] = ["field-unknown"]
        evidence["unsupported_reasons"] = ["unsupported-required-signatures"]
        evidence["observation"]["collection_complete"] = False
        evidence["pull_request"]["draft"] = True
        rehash_evidence(evidence)
        verdict = self.evaluate(evidence=evidence)
        self.assertEqual(verdict.outcome, EligibilityOutcome.UNKNOWN)
        self.assertTrue({
            DenyCode.FIELD_UNKNOWN, DenyCode.UNSUPPORTED_REQUIRED_SIGNATURES,
            DenyCode.DRAFT,
        } <= codes(verdict))

    def test_evaluator_has_zero_network_mutation_credentials_or_production_callers(self):
        sources = "\n".join(
            (ROOT / "pathfinder_core" / name).read_text()
            for name in (
                "merge_policy.py", "merge_policy_types.py", "merge_policy_proofs.py",
            )
        )
        for forbidden in (
            "import requests", "import urllib", "import http.client", "import subprocess",
            '"POST"', '"PUT"', '"PATCH"', '"DELETE"', "os.environ", "getenv(",
        ):
            self.assertNotIn(forbidden, sources)
        consumers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name.startswith("merge_policy"):
                continue
            if "merge_policy" in path.read_text():
                consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])
        public = {
            name for name, value in MergePolicyEvaluator.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(public, {"evaluate"})
        self.assertNotIn("network", inspect.signature(MergePolicyEvaluator.evaluate).parameters)


if __name__ == "__main__":
    unittest.main()
