import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tests.contracts.test_intent_schemas import reject_duplicate_keys


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-08-10T12:00:00+00:00"
HASH = "a" * 64
COMMIT = "b" * 40


def schema(path):
    return json.loads((ROOT / "schemas" / path).read_text(), object_pairs_hook=reject_duplicate_keys)


def validate(path, instance):
    document = schema(path)
    Draft202012Validator.check_schema(document)
    Draft202012Validator(document, format_checker=FormatChecker()).validate(instance)


STATE = {
    "schema_version": 1, "mission_id": "mission_12345678", "goal_id": "goal_12345678",
    "binding_id": "binding_12345678", "authorization_id": None, "attempt_id": None,
    "state": "planned", "revision": 0, "base_commit": COMMIT, "dirty_policy": "block",
    "worktree_id": None, "worktree_path": None, "branch_id": None, "branch_name": None,
    "commit_ids": [], "pr_id": None, "pr_url": None, "created_at": NOW, "updated_at": NOW,
}

AUTHORIZATION = {
    "schema_version": 1, "authorization_id": "authorization_12345678", "mission_id": "mission_12345678",
    "binding_id": "binding_12345678", "explicit_request": True, "trusted_source": "current-user-turn",
    "authorized_at": NOW, "base_commit": COMMIT,
    "intent_hashes": {"charter": HASH, "roadmap": HASH, "doctrine": HASH},
    "limits": {"max_goals": 1, "max_attempts": 2, "max_wall_seconds": 3600, "max_total_prs": 1},
    "publication_target": "github-awaiting-review", "snapshot_sha256": HASH,
}

BOUNDARY = {
    "schema_version": 1, "boundary_id": "boundary_12345678", "primary_runtime": "test",
    "filesystem": "enforced", "process": "enforced", "network": "denied", "credentials": "isolated",
    "repo_code_execution": "allowlisted", "tool_allowlist_enforced": True, "pre_execution_consent": True,
    "execution_eligible": True, "blocking_reasons": [], "observed_at": NOW,
}

EVENT = {
    "schema_version": 1, "event_id": "event_12345678", "mission_id": "mission_12345678", "sequence": 1,
    "event_type": "transition", "from_state": "planned", "to_state": "authorized", "attempt_id": None,
    "recorded_at": NOW, "changes": {}, "payload_sha256": HASH,
}


class MissionSchemaTests(unittest.TestCase):
    def test_all_schemas_are_valid_json_schema(self):
        for folder in ("artifacts", "cache", "intent", "mission", "replays"):
            for path in (ROOT / "schemas" / folder).glob("*.json"):
                with self.subTest(path=path.name):
                    Draft202012Validator.check_schema(schema(f"{folder}/{path.name}"))

    def test_valid_mission_documents(self):
        for path, instance in [("mission/mission-state.schema.json", STATE), ("mission/authorization-snapshot.schema.json", AUTHORIZATION), ("mission/event.schema.json", EVENT), ("artifacts/runtime-boundary.schema.json", BOUNDARY)]:
            with self.subTest(path=path):
                validate(path, instance)

    def test_unknown_state_fails(self):
        instance = copy.deepcopy(STATE)
        instance["state"] = "mostly-done"
        with self.assertRaises(Exception):
            validate("mission/mission-state.schema.json", instance)

    def test_authorization_requires_explicit_request(self):
        instance = copy.deepcopy(AUTHORIZATION)
        instance["explicit_request"] = False
        with self.assertRaises(Exception):
            validate("mission/authorization-snapshot.schema.json", instance)

    def test_unknown_runtime_boundary_is_not_eligible(self):
        instance = copy.deepcopy(BOUNDARY)
        instance["filesystem"] = "unknown"
        instance["execution_eligible"] = False
        instance["blocking_reasons"] = ["filesystem enforcement unknown"]
        validate("artifacts/runtime-boundary.schema.json", instance)

    def test_prompt_goal_binding_accepts_unloaded_intent(self):
        instance = json.loads((ROOT / "evals/fixtures/good-goal/artifacts/06-goal-binding.json").read_text())
        instance["objective_source"] = "user-prompt"
        instance["selected_candidate_ids"] = []
        instance["intent_snapshot"] = {"charter": None, "roadmap": None, "doctrine": None}
        validate("artifacts/goal-binding.schema.json", instance)

    def test_malformed_timestamp_fails(self):
        instance = copy.deepcopy(EVENT)
        instance["recorded_at"] = "yesterday"
        with self.assertRaises(Exception):
            validate("mission/event.schema.json", instance)

    def test_stale_version_fails(self):
        instance = copy.deepcopy(STATE)
        instance["schema_version"] = 0
        with self.assertRaises(Exception):
            validate("mission/mission-state.schema.json", instance)


if __name__ == "__main__":
    unittest.main()
