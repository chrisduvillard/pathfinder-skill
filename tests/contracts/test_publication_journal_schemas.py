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
    "evidence": "evidence_sha256",
    "intent": "intent_sha256",
    "result": "result_sha256",
}


def load_json(path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)


def validate_schema(name, document):
    schema = load_json(SCHEMA_ROOT / f"merge-{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


def _subset(document, keys):
    return {key: document[key] for key in keys}


def validate_journal(journal, authority):
    evidence, intent, result = (
        journal.get("evidence"),
        journal.get("intent"),
        journal.get("result"),
    )
    if intent is None:
        if result is not None:
            raise ValidationError("merge result cannot exist without its intent")
        raise ValidationError("merge intent is required")

    validate_contract_pair(authority["policy"], authority["authorization"])
    validate_schema("evidence", evidence)
    validate_schema("intent", intent)
    for name, document in (("evidence", evidence), ("intent", intent)):
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

    expected_intent_bindings = {
        "evidence_id": evidence["evidence_id"],
        "evidence_sha256": evidence["evidence_sha256"],
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

    if result is None:
        return {"state": "pending", "disposition": "reconcile-required"}
    validate_schema("result", result)
    if result["result_sha256"] != canonical_sha256(result, "result_sha256"):
        raise ValidationError("result_sha256 does not match canonical document")
    expected_result_binding = {
        "evidence_sha256": evidence["evidence_sha256"],
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
    return {"state": "terminal", "disposition": result["outcome"]}


def mutate_journal(bundle, case):
    changed = {name: copy.deepcopy(bundle[name]) for name in HASH_FIELDS}
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

    evidence, intent, result = changed["evidence"], changed["intent"], changed["result"]
    if evidence is not None:
        evidence["evidence_sha256"] = canonical_sha256(evidence, "evidence_sha256")
    if intent is not None:
        if evidence is not None:
            intent["bindings"]["evidence_sha256"] = evidence["evidence_sha256"]
        intent["intent_sha256"] = canonical_sha256(intent, "intent_sha256")
    if result is not None:
        if evidence is not None:
            result["binding"]["evidence_sha256"] = evidence["evidence_sha256"]
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
                schema = load_json(SCHEMA_ROOT / f"merge-{name}.schema.json")
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])

    def test_valid_evidence_intent_and_result_are_exactly_bound(self):
        self.assertEqual(
            validate_journal(self.bundle, self.authority),
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
        for outcome in (
            "not-merged", "reconcile-required", "policy-blocked", "auth-error",
            "rate-limited", "permission-missing", "api-unavailable",
        ):
            with self.subTest(outcome=outcome):
                journal = copy.deepcopy(self.bundle)
                journal["result"]["outcome"] = outcome
                journal["result"]["merge_proof"] = None
                journal["result"]["result_sha256"] = canonical_sha256(
                    journal["result"], "result_sha256"
                )
                self.assertEqual(
                    validate_journal(journal, self.authority)["disposition"], outcome
                )

    def test_new_contracts_have_no_production_caller_or_merge_call(self):
        production = "\n".join(
            path.read_text() for path in (ROOT / "pathfinder_core").rglob("*.py")
        )
        for schema_name in ("merge-evidence", "merge-intent", "merge-result"):
            self.assertNotIn(schema_name, production)
        self.assertNotIn(".merge(", production)

    def test_fixture_loader_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads(
                '{"result":{"outcome":"merged","outcome":"not-merged"}}',
                object_pairs_hook=reject_duplicate_keys,
            )


if __name__ == "__main__":
    unittest.main()
