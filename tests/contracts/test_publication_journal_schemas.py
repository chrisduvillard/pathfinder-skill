import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from tests.contracts.test_intent_schemas import reject_duplicate_keys
from tests.contracts.test_publication_schemas import (
    canonical_sha256,
    validate_contract_pair,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = ROOT / "schemas" / "publication"
FIXTURE_ROOT = ROOT / "tests" / "contracts" / "fixtures"
HASH_FIELDS = {
    "initial_evidence": "evidence_sha256",
    "evidence": "evidence_sha256",
    "readiness_proof": "proof_sha256",
    "intent": "intent_sha256",
    "result": "result_sha256",
}
SCHEMA_NAMES = {
    "initial_evidence": "evidence",
    "readiness_proof": "readiness-proof",
}


def load_json(path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)


def validate_schema(name, document):
    schema_name = SCHEMA_NAMES.get(name, name)
    schema = load_json(SCHEMA_ROOT / f"merge-{schema_name}.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


def _subset(document, keys):
    return {key: document[key] for key in keys}


def validate_journal(journal, authority, protected_policy=None):
    initial_evidence, evidence, readiness, intent, result = (
        journal.get("initial_evidence"),
        journal.get("evidence"),
        journal.get("readiness_proof"),
        journal.get("intent"),
        journal.get("result"),
    )
    dispatch = journal.get("dispatch")
    if intent is None:
        if result is not None:
            raise ValidationError("merge result cannot exist without its intent")
        raise ValidationError("merge intent is required")

    validate_contract_pair(authority["policy"], authority["authorization"])
    validate_schema("initial_evidence", initial_evidence)
    validate_schema("evidence", evidence)
    validate_schema("readiness_proof", readiness)
    validate_schema("intent", intent)
    credential_schema = load_json(
        SCHEMA_ROOT / "merge-credential-receipt.schema.json"
    )
    Draft202012Validator(
        credential_schema, format_checker=FormatChecker()
    ).validate(journal["credential_receipt"])
    if journal["credential_receipt"]["receipt_sha256"] != canonical_sha256(
        journal["credential_receipt"], "receipt_sha256"
    ):
        raise ValidationError("credential receipt hash does not match canonical document")
    for name, document in (
        ("initial_evidence", initial_evidence), ("evidence", evidence),
        ("readiness_proof", readiness), ("intent", intent)
    ):
        field = HASH_FIELDS[name]
        if document[field] != canonical_sha256(document, field):
            raise ValidationError(f"{field} does not match canonical document")

    policy, authorization = authority["policy"], authority["authorization"]
    if evidence["bindings"] != {
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
        "merge_authorization_id": authorization["merge_authorization_id"],
        "authorization_sha256": authorization["authorization_sha256"],
        "mission_id": authorization["mission"]["mission_id"],
        "binding_id": authorization["mission"]["binding_id"],
        "mission_authorization_id": authorization["mission"]["mission_authorization_id"],
        "protected_policy_sha256": policy["path_policy"]["protected_policy_sha256"],
    }:
        raise ValidationError("evidence authority binding drift")
    repository_keys = ("id", "node_id", "owner", "name", "base_branch")
    if _subset(evidence["repository"], repository_keys) != policy["repository"]:
        raise ValidationError("evidence repository binding drift")
    expected_candidate_pull = _subset(
        evidence["pull_request"],
        ("id", "node_id", "number", "head_ref", "head_sha", "base_ref", "base_sha"),
    )
    expected_candidate_diff = {
        "diff_sha256": evidence["diff"]["diff_sha256"],
        "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
        "object_evidence_sha256": evidence["diff"]["object_evidence"][
            "files_sha256"
        ],
    }
    if (
        authorization["candidate"]["pull_request"] != expected_candidate_pull
        or authorization["candidate"]["diff"] != expected_candidate_diff
    ):
        raise ValidationError("evidence controller candidate binding drift")

    pages = evidence["pagination"].values()
    if (
        not evidence["observation"]["collection_complete"]
        or any(not page["complete"] or page["truncated"] for page in pages)
        or evidence["unsupported_reasons"]
        or evidence["unknown_reasons"]
    ):
        raise ValidationError("evidence is incomplete or unsupported")
    observed = datetime.fromisoformat(evidence["observation"]["observed_at"])
    completed = datetime.fromisoformat(evidence["observation"]["completed_at"])
    expires = datetime.fromisoformat(evidence["observation"]["expires_at"])
    started = datetime.fromisoformat(intent["started_at"])
    if not observed <= completed <= started < expires:
        raise ValidationError("evidence is expired or has an invalid observation window")

    def expected_snapshot(document):
        observation = document["observation"]
        return {
            "evidence_id": document["evidence_id"],
            "evidence_sha256": document["evidence_sha256"],
            "policy_read_receipt_id": observation["policy_read"]["receipt_id"],
            "request_ids_sha256": observation["request_ids_sha256"],
            "observed_at": observation["observed_at"],
            "completed_at": observation["completed_at"],
            "expires_at": observation["expires_at"],
        }

    expected_initial = expected_snapshot(initial_evidence)
    expected_reread = expected_snapshot(evidence)
    initial_snapshot = readiness["initial_snapshot"]
    reread_snapshot = readiness["reread_snapshot"]
    if (
        readiness["policy"] != {
            "policy_id": policy["policy_id"],
            "policy_sha256": policy["policy_sha256"],
        }
        or readiness["authorization"] != {
            "merge_authorization_id": authorization["merge_authorization_id"],
            "authorization_sha256": authorization["authorization_sha256"],
        }
        or readiness["protected_policy_sha256"]
        != policy["path_policy"]["protected_policy_sha256"]
        or initial_snapshot != expected_initial
        or reread_snapshot != expected_reread
    ):
        raise ValidationError("readiness proof authority or evidence binding drift")
    initial_completed = datetime.fromisoformat(initial_snapshot["completed_at"])
    reread_observed = datetime.fromisoformat(reread_snapshot["observed_at"])
    if (
        initial_snapshot["evidence_id"] == reread_snapshot["evidence_id"]
        or initial_snapshot["evidence_sha256"] == reread_snapshot["evidence_sha256"]
        or initial_snapshot["policy_read_receipt_id"]
        == reread_snapshot["policy_read_receipt_id"]
        or not initial_completed < reread_observed
    ):
        raise ValidationError("readiness proof does not bind a disjoint ordered reread")

    expected_intent_bindings = {
        "readiness_proof_sha256": readiness["proof_sha256"],
        "initial_evidence_id": initial_snapshot["evidence_id"],
        "initial_evidence_sha256": initial_snapshot["evidence_sha256"],
        "reread_evidence_id": reread_snapshot["evidence_id"],
        "reread_evidence_sha256": reread_snapshot["evidence_sha256"],
        **authorization["candidate"]["diff"],
        "credential_receipt_id": journal["credential_receipt"][
            "credential_receipt_id"
        ],
        "credential_receipt_sha256": journal["credential_receipt"][
            "receipt_sha256"
        ],
        **{key: evidence["bindings"][key] for key in (
            "policy_id", "policy_sha256", "merge_authorization_id",
            "authorization_sha256", "mission_id", "binding_id",
            "mission_authorization_id",
        )},
    }
    if intent["bindings"] != expected_intent_bindings:
        raise ValidationError("intent authority or evidence binding drift")
    expected_pr = _subset(
        evidence["pull_request"], ("id", "node_id", "number", "head_sha", "base_sha")
    )
    expected_actor = _subset(
        evidence["actor"],
        ("app_id", "installation_id", "actor_id", "actor_node_id", "login"),
    )
    if intent["repository"] != policy["repository"]:
        raise ValidationError("intent repository binding drift")
    if intent["pull_request"] != expected_pr or intent["actor"] != expected_actor:
        raise ValidationError("intent PR or actor binding drift")
    if intent["merge_method"] != policy["merge_method"]:
        raise ValidationError("intent merge method drift")

    from pathfinder_core.merge_policy import MergePolicyEvaluator
    from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry

    effective_protected_policy = (
        ProtectedSurfaceRegistry.load().to_document()
        if protected_policy is None else protected_policy
    )
    evaluation = MergePolicyEvaluator().evaluate_reread(
        policy,
        authorization,
        effective_protected_policy,
        initial_evidence,
        evidence,
        now=started,
    )
    if not evaluation.intent_ready or evaluation.proof is None:
        raise ValidationError("persisted evidence does not replay as intent-ready")
    if evaluation.proof.to_document() != readiness:
        raise ValidationError("readiness proof differs from evaluator replay")

    if result is None:
        return {"state": "pending", "disposition": "reconcile-required"}
    dispatch_schema = load_json(SCHEMA_ROOT / "merge-dispatch.schema.json")
    Draft202012Validator(
        dispatch_schema, format_checker=FormatChecker()
    ).validate(dispatch)
    if dispatch["dispatch_sha256"] != canonical_sha256(
        dispatch, "dispatch_sha256"
    ):
        raise ValidationError("dispatch hash does not match canonical document")
    if (
        dispatch["operation_id"] != intent["operation_id"]
        or dispatch["intent_sha256"] != intent["intent_sha256"]
        or not started
        <= datetime.fromisoformat(dispatch["dispatch_started_at"])
    ):
        raise ValidationError("dispatch does not match its intent")
    validate_schema("result", result)
    if result["result_sha256"] != canonical_sha256(result, "result_sha256"):
        raise ValidationError("result_sha256 does not match canonical document")
    expected_result_binding = {
        "readiness_proof_sha256": readiness["proof_sha256"],
        "policy_sha256": policy["policy_sha256"],
        "authorization_sha256": authorization["authorization_sha256"],
        "repository": _subset(policy["repository"], ("id", "node_id")),
        "pull_request": expected_pr,
        "actor": expected_actor,
        "merge_method": "squash",
    }
    if (
        result["operation_id"] != intent["operation_id"]
        or result["intent_sha256"] != intent["intent_sha256"]
        or result["binding"] != expected_result_binding
    ):
        raise ValidationError("result does not match its intent")
    if datetime.fromisoformat(result["completed_at"]) < started:
        raise ValidationError("result predates intent")

    if result["outcome"] == "merged":
        proof = result["merge_proof"]
        expected_proof_binding = {
            "repository_id": policy["repository"]["id"],
            "pull_request_id": expected_pr["id"],
            "pull_request_node_id": expected_pr["node_id"],
            "pull_request_number": expected_pr["number"],
            "head_sha": expected_pr["head_sha"],
            "base_sha_before": expected_pr["base_sha"],
        }
        if any(proof[key] != value for key, value in expected_proof_binding.items()):
            raise ValidationError("merged proof does not match intended PR")
        if proof["merged_by"] != _subset(
            expected_actor, ("actor_id", "actor_node_id", "login")
        ):
            raise ValidationError("merged proof actor drift")
        if (
            proof["base_ref"] != policy["repository"]["base_branch"]
            or proof["base_sha_after"] != proof["merge_commit_sha"]
            or proof["merge_commit_parent_shas"] != [expected_pr["base_sha"]]
            or proof["merge_endpoint_status"] != 204
            or len(proof["request_ids"]) != len(set(proof["request_ids"]))
        ):
            raise ValidationError("merged proof does not prove exact squash semantics")
        merged_at = datetime.fromisoformat(proof["merged_at"])
        observed_at = datetime.fromisoformat(proof["observed_at"])
        completed_at = datetime.fromisoformat(result["completed_at"])
        dispatched_at = datetime.fromisoformat(dispatch["dispatch_started_at"])
        if not started <= dispatched_at <= merged_at <= observed_at <= completed_at:
            raise ValidationError("merged proof timeline is invalid")
    return {"state": "terminal", "disposition": result["outcome"]}


def mutate_journal(bundle, case):
    changed = {name: copy.deepcopy(bundle[name]) for name in HASH_FIELDS}
    changed["credential_receipt"] = copy.deepcopy(bundle["credential_receipt"])
    changed["dispatch"] = copy.deepcopy(bundle["dispatch"])
    if case["operation"] == "remove-document":
        changed[case["document"]] = None
    else:
        parent = changed[case["document"]]
        for segment in case["path"][:-1]:
            parent = parent[segment]
        final = case["path"][-1]
        if case["operation"] == "remove":
            del parent[final]
        else:
            parent[final] = case["value"]

    evidence = changed["evidence"]
    initial_evidence = changed["initial_evidence"]
    readiness = changed["readiness_proof"]
    intent = changed["intent"]
    result = changed["result"]
    if initial_evidence is not None:
        initial_evidence["evidence_sha256"] = canonical_sha256(
            initial_evidence, "evidence_sha256"
        )
    if evidence is not None:
        evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")
    if readiness is not None:
        if initial_evidence is not None and case["document"] == "initial_evidence":
            observation = initial_evidence["observation"]
            readiness["initial_snapshot"].update({
                "evidence_id": initial_evidence["evidence_id"],
                "evidence_sha256": initial_evidence["evidence_sha256"],
                "policy_read_receipt_id": observation["policy_read"]["receipt_id"],
                "request_ids_sha256": observation["request_ids_sha256"],
                "observed_at": observation["observed_at"],
                "completed_at": observation["completed_at"],
                "expires_at": observation["expires_at"],
            })
        if evidence is not None and case["document"] == "evidence":
            observation = evidence["observation"]
            readiness["reread_snapshot"].update({
                "evidence_id": evidence["evidence_id"],
                "evidence_sha256": evidence["evidence_sha256"],
                "policy_read_receipt_id": observation["policy_read"]["receipt_id"],
                "request_ids_sha256": observation["request_ids_sha256"],
                "observed_at": observation["observed_at"],
                "completed_at": observation["completed_at"],
                "expires_at": observation["expires_at"],
            })
        readiness["proof_sha256"] = canonical_sha256(
            readiness, "proof_sha256"
        )
    if intent is not None:
        if readiness is not None:
            initial = readiness["initial_snapshot"]
            reread = readiness["reread_snapshot"]
            intent["bindings"].update({
                "readiness_proof_sha256": readiness["proof_sha256"],
                "initial_evidence_id": initial["evidence_id"],
                "initial_evidence_sha256": initial["evidence_sha256"],
                "reread_evidence_id": reread["evidence_id"],
                "reread_evidence_sha256": reread["evidence_sha256"],
            })
        intent["intent_sha256"] = canonical_sha256(intent, "intent_sha256")
    if result is not None:
        if readiness is not None:
            result["binding"]["readiness_proof_sha256"] = readiness[
                "proof_sha256"
            ]
        if intent is not None:
            result["intent_sha256"] = intent["intent_sha256"]
        result["result_sha256"] = canonical_sha256(result, "result_sha256")
    return changed


class PublicationJournalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.authority = load_json(FIXTURE_ROOT / "publication-contracts.json")
        self.bundle = load_json(FIXTURE_ROOT / "publication-journal-contracts.json")

    def test_journal_schemas_are_valid_and_closed(self):
        for name in HASH_FIELDS:
            with self.subTest(name=name):
                schema_name = SCHEMA_NAMES.get(name, name)
                schema = load_json(SCHEMA_ROOT / f"merge-{schema_name}.schema.json")
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])

    def test_valid_evidence_intent_and_result_are_exactly_bound(self):
        self.assertEqual(
            validate_journal(self.bundle, self.authority),
            {"state": "terminal", "disposition": "merged"},
        )

    def test_uncomposed_v1_intent_and_result_previews_are_rejected(self):
        for name in ("intent", "result"):
            with self.subTest(name=name), self.assertRaises(ValidationError):
                document = copy.deepcopy(self.bundle[name])
                document["schema_version"] = 1
                validate_schema(name, document)

    def test_journal_replay_accepts_an_additive_protected_policy(self):
        from pathfinder_core.merge_policy import MergePolicyEvaluator
        from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry

        authority = copy.deepcopy(self.authority)
        journal = copy.deepcopy(self.bundle)
        baseline = ProtectedSurfaceRegistry.load().to_document()
        additive = {
            "schema_version": 1,
            "policy_id": "protected-policy-example-additive",
            "mode": "additive",
            "base_policy_id": baseline["policy_id"],
            "rules": [{
                "rule_id": "protected-rule-example-extra",
                "category": "example-extra",
                "description": "Additional host-owned protected surface.",
                "patterns": ["extra-protected/**"],
            }],
        }
        effective = ProtectedSurfaceRegistry(baseline, additive)
        policy = authority["policy"]
        authorization = authority["authorization"]
        policy["path_policy"]["protected_policy_sha256"] = effective.sha256
        policy["policy_sha256"] = canonical_sha256(policy, "policy_sha256")
        authorization["policy"]["policy_sha256"] = policy["policy_sha256"]
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        for evidence in (journal["initial_evidence"], journal["evidence"]):
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
        started = datetime.fromisoformat(journal["intent"]["started_at"])
        evaluation = MergePolicyEvaluator().evaluate_reread(
            policy, authorization, additive,
            journal["initial_evidence"], journal["evidence"], now=started,
        )
        self.assertTrue(evaluation.intent_ready)
        journal["readiness_proof"] = evaluation.proof.to_document()
        intent = journal["intent"]
        intent["bindings"].update({
            "readiness_proof_sha256": evaluation.proof.proof_sha256,
            "initial_evidence_sha256": journal["initial_evidence"][
                "evidence_sha256"
            ],
            "reread_evidence_sha256": journal["evidence"]["evidence_sha256"],
            "policy_sha256": policy["policy_sha256"],
            "authorization_sha256": authorization["authorization_sha256"],
        })
        intent["intent_sha256"] = canonical_sha256(intent, "intent_sha256")
        dispatch = journal["dispatch"]
        dispatch["intent_sha256"] = intent["intent_sha256"]
        dispatch["dispatch_sha256"] = canonical_sha256(
            dispatch, "dispatch_sha256"
        )
        result = journal["result"]
        result["intent_sha256"] = intent["intent_sha256"]
        result["binding"].update({
            "readiness_proof_sha256": evaluation.proof.proof_sha256,
            "policy_sha256": policy["policy_sha256"],
            "authorization_sha256": authorization["authorization_sha256"],
        })
        result["result_sha256"] = canonical_sha256(result, "result_sha256")
        self.assertEqual(
            validate_journal(journal, authority, additive),
            {"state": "terminal", "disposition": "merged"},
        )

    def test_negative_journal_fixtures_fail_closed(self):
        for case in self.bundle["negative_cases"]:
            with self.subTest(case=case["name"]), self.assertRaises(ValidationError):
                validate_journal(mutate_journal(self.bundle, case), self.authority)

    def test_pending_intent_requires_reconciliation_and_is_not_replayed(self):
        pending = copy.deepcopy(self.bundle)
        pending["result"] = None
        self.assertEqual(
            validate_journal(pending, self.authority),
            {"state": "pending", "disposition": "reconcile-required"},
        )

    def test_every_nonmerged_outcome_has_no_merge_proof(self):
        reasons = {
            "not-merged": "unmergeable",
            "reconcile-required": "transport-ambiguous",
            "policy-blocked": "policy-ineligible",
            "auth-error": "authentication-failed",
            "rate-limited": "rate-limit-exceeded",
            "permission-missing": "permission-denied",
            "api-unavailable": "server-error",
        }
        for outcome, reason in reasons.items():
            with self.subTest(outcome=outcome):
                journal = copy.deepcopy(self.bundle)
                journal["result"]["outcome"] = outcome
                journal["result"]["reason"] = reason
                journal["result"]["merge_proof"] = None
                journal["result"]["result_sha256"] = canonical_sha256(
                    journal["result"], "result_sha256"
                )
                self.assertEqual(
                    validate_journal(journal, self.authority)["disposition"], outcome
                )

    def test_result_reason_must_match_its_outcome(self):
        journal = copy.deepcopy(self.bundle)
        journal["result"]["reason"] = "head-mismatch"
        journal["result"]["result_sha256"] = canonical_sha256(
            journal["result"], "result_sha256"
        )
        with self.assertRaises(ValidationError):
            validate_journal(journal, self.authority)

    def test_k4_writer_is_isolated_and_has_no_enabled_caller(self):
        sources = {
            path.relative_to(ROOT).as_posix(): path.read_text()
            for path in (ROOT / "pathfinder_core").rglob("*.py")
        }
        evidence_consumers = {
            path for path, source in sources.items() if "merge-evidence" in source
        }
        self.assertEqual(
            evidence_consumers,
            {"pathfinder_core/adapters/github_merge_observer.py"},
        )
        merge_callers = {
            path for path, source in sources.items() if ".merge(" in source
        }
        self.assertEqual(merge_callers, {"pathfinder_core/merge_executor.py"})
        executor_callers = {
            path for path, source in sources.items()
            if "MergeExecutor(" in source
            and path != "pathfinder_core/merge_executor.py"
        }
        self.assertEqual(executor_callers, set())
        enabled = "\n".join(
            source for path, source in sources.items()
            if path in {
                "pathfinder_core/__main__.py",
                "pathfinder_core/mission_host.py",
                "pathfinder_core/goal_pack.py",
                "pathfinder_core/adapters/github.py",
            }
        )
        for forbidden in (
            "MergeExecutor", "GitHubMergeBackend", "GitHubMergeCredential",
            "MergeOperationJournal",
        ):
            self.assertNotIn(forbidden, enabled)
        executor_source = sources["pathfinder_core/merge_executor.py"]
        for forbidden in (
            ".push(", "create_pull_request", "delete", "release", "deploy",
            "subprocess", "os.environ", "getenv(", "GoalAdapter",
        ):
            self.assertNotIn(forbidden, executor_source)
        credential_sources = "\n".join(
            sources[path] for path in (
                "pathfinder_core/merge_credentials.py",
                "pathfinder_core/adapters/github_merge_writer.py",
            )
        )
        self.assertNotIn("os.environ", credential_sources)
        self.assertNotIn("getenv(", credential_sources)

    def test_fixture_loader_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads(
                '{"result":{"outcome":"merged","outcome":"not-merged"}}',
                object_pairs_hook=reject_duplicate_keys,
            )


if __name__ == "__main__":
    unittest.main()
