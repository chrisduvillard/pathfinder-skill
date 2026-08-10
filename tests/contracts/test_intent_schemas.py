import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "intent"


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text(), object_pairs_hook=reject_duplicate_keys)


def validate(name, instance):
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


NOW = "2026-08-10T12:00:00+00:00"

CHARTER = {
    "schema_version": 1, "charter_id": "charter_12345678", "completion": "complete",
    "intent_clarity": "resolved", "established_at": NOW, "refreshed_at": NOW,
    "source_basis": ["creator interview"],
    "purpose": {"north_star": "Safe autonomous goals", "primary_promise": "Evidence-backed work"},
    "users": {"primary": ["maintainers"], "secondary": [], "excluded": [], "key_journeys": ["prepare a goal"]},
    "success": {"durable_metrics": [], "quality_bars": ["safe"], "tradeoffs": []},
    "constraints": {"technical": ["Python 3.11"], "product": [], "protected_surfaces": ["releases"]},
    "non_goals": ["self merge"], "finished_state": "one safe sequential controller",
    "autonomy_policy": {"may_derive": ["tests"], "human_review_required": ["CI"], "never_unattended": ["releases"]},
}

DOCTRINE = {
    "schema_version": 1, "doctrine_id": "doctrine_12345678", "completion": "complete",
    "intent_clarity": "resolved", "created_at": NOW, "refreshed_at": NOW,
    "source_basis": ["creator interview"], "end_goal": "Safe useful goals",
    "product_philosophy": ["Evidence first"], "user_intent": ["Reduce steering"],
    "quality_bars": ["Fail closed"], "improvement_heuristics": ["Prefer verified value"],
    "autonomous_mission_policy": {"may_derive_and_edit": ["tests"], "requires_extra_proof": ["CI"], "human_review_required": ["protected code"], "never_unattended": ["releases"]},
    "hard_stops": ["secrets-or-credentials", "destructive-data-operations", "releases", "repository-administration", "force-push", "branch-or-tag-deletion", "external-side-effects"],
}

ROADMAP = {
    "schema_version": 1, "roadmap_id": "roadmap_12345678", "completion": "complete",
    "intent_clarity": "resolved", "created_at": NOW, "refreshed_at": NOW,
    "source_basis": ["creator interview"], "future_state": ["One safe runner"],
    "items": [{"item_id": "R1", "status": "not-started", "priority": "high", "rationale": "needed",
               "depends_on": [], "evidence": ["repo audit"], "safety": "autonomous-eligible",
               "desired_outcome": "runner passes tests",
               "execution_eligibility": {"status": "eligible", "reasons": ["proof found"], "evaluated_at": NOW, "base_commit": "a" * 40}}],
    "open_questions": [],
}


class IntentSchemaTests(unittest.TestCase):
    def test_valid_intent_documents(self):
        for schema, instance in [("charter.schema.json", CHARTER), ("doctrine.schema.json", DOCTRINE), ("roadmap.schema.json", ROADMAP)]:
            with self.subTest(schema=schema):
                validate(schema, instance)

    def test_missing_required_field_fails(self):
        instance = copy.deepcopy(CHARTER)
        del instance["purpose"]
        with self.assertRaises(Exception):
            validate("charter.schema.json", instance)

    def test_bad_safety_enum_fails(self):
        instance = copy.deepcopy(ROADMAP)
        instance["items"][0]["safety"] = "probably-safe"
        with self.assertRaises(Exception):
            validate("roadmap.schema.json", instance)

    def test_stale_schema_version_fails(self):
        instance = copy.deepcopy(DOCTRINE)
        instance["schema_version"] = 0
        with self.assertRaises(Exception):
            validate("doctrine.schema.json", instance)

    def test_intent_clarity_does_not_replace_item_eligibility(self):
        instance = copy.deepcopy(ROADMAP)
        del instance["items"][0]["execution_eligibility"]
        with self.assertRaises(Exception):
            validate("roadmap.schema.json", instance)

    def test_duplicate_keys_fail_during_parse(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            json.loads('{"schema_version": 1, "schema_version": 1}', object_pairs_hook=reject_duplicate_keys)


if __name__ == "__main__":
    unittest.main()
