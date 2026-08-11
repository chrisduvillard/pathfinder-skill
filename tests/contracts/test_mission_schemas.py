import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tests.contracts.test_intent_schemas import reject_duplicate_keys


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"
NOW = "2026-08-10T12:00:00+00:00"
HASH = "a" * 64
COMMIT = "b" * 40


def schema(path):
    return json.loads((ROOT / "schemas" / path).read_text(), object_pairs_hook=reject_duplicate_keys)


def validate(path, instance):
    document = schema(path)
    Draft202012Validator.check_schema(document)
    Draft202012Validator(document, format_checker=FormatChecker()).validate(instance)


def fixture(name):
    return json.loads(
        (FIXTURES / name).read_text(), object_pairs_hook=reject_duplicate_keys
    )


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

GOAL_PACK_AUTHORIZATION = {
    "schema_version": 1,
    "authorization_id": "authorization_pack1234",
    "pack_id": "pack_12345678",
    "explicit_request": True,
    "trusted_source": "current-user-turn",
    "authorized_at": NOW,
    "base_commit": COMMIT,
    "intent_hashes": {"charter": HASH, "roadmap": HASH, "doctrine": HASH},
    "goal_bindings": [
        {
            "position": position,
            "mission_id": f"mission_packgoal{position:02d}",
            "binding_id": f"binding_packgoal{position:02d}",
            "goal_id": f"goal_packgoal{position:02d}",
            "sha256": HASH,
        }
        for position in (1, 2)
    ],
    "limits": {
        "max_goals": 2,
        "max_attempts_per_goal": 2,
        "max_wall_seconds": 3600,
        "max_total_prs": 0,
    },
    "publication_target": "local-branch",
    "snapshot_sha256": HASH,
}

GOAL_PACK_STATE = {
    "schema_version": 1,
    "pack_id": "pack_12345678",
    "authorization_id": "authorization_pack1234",
    "state": "authorized",
    "revision": 0,
    "current_goal_index": 0,
    "goals": [
        {
            "position": position,
            "mission_id": f"mission_packgoal{position:02d}",
            "binding_id": f"binding_packgoal{position:02d}",
            "goal_id": f"goal_packgoal{position:02d}",
            "binding_sha256": HASH,
            "status": "active" if position == 1 else "queued",
            "child_state_dir": f"goals/{position:04d}",
            "activated_at": NOW if position == 1 else None,
            "completed_at": None,
            "final_state": None,
        }
        for position in (1, 2)
    ],
    "terminal_reason": None,
    "deadline_at": "2026-08-10T13:00:00+00:00",
    "created_at": NOW,
    "updated_at": NOW,
}

EVENT = {
    "schema_version": 1, "event_id": "event_12345678", "mission_id": "mission_12345678", "sequence": 1,
    "event_type": "transition", "from_state": "planned", "to_state": "authorized", "attempt_id": None,
    "recorded_at": NOW, "changes": {}, "payload_sha256": HASH,
}


class MissionSchemaTests(unittest.TestCase):
    def test_all_schemas_are_valid_json_schema(self):
        for folder in ("artifacts", "cache", "intent", "mission", "policy", "replays"):
            for path in (ROOT / "schemas" / folder).glob("*.json"):
                with self.subTest(path=path.name):
                    Draft202012Validator.check_schema(schema(f"{folder}/{path.name}"))

    def test_valid_mission_documents(self):
        for path, instance in [("mission/mission-state.schema.json", STATE), ("mission/authorization-snapshot.schema.json", AUTHORIZATION), ("mission/goal-pack-authorization.schema.json", GOAL_PACK_AUTHORIZATION), ("mission/goal-pack-state.schema.json", GOAL_PACK_STATE), ("mission/event.schema.json", EVENT), ("artifacts/runtime-boundary.schema.json", BOUNDARY), ("mission/operation-intent.schema.json", fixture("operation-intent.valid.json")), ("mission/operation-result.schema.json", fixture("operation-result.valid.json"))]:
            with self.subTest(path=path):
                validate(path, instance)

    def test_all_operation_fixtures_are_duplicate_safe_json(self):
        for path in FIXTURES.glob("*.json"):
            with self.subTest(path=path.name):
                fixture(path.name)

    def test_injection_replay_requires_every_untrusted_surface(self):
        path = ROOT / "evals" / "replays" / "fixtures" / "injection-blocked" / "artifacts" / "replay.json"
        replay = json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)
        validate("replays/replay.schema.json", replay)
        for mutation in (replay["injection_sources"][:-1], [*replay["injection_sources"], "unknown"]):
            with self.subTest(mutation=mutation), self.assertRaises(Exception):
                changed = copy.deepcopy(replay)
                changed["injection_sources"] = mutation
                validate("replays/replay.schema.json", changed)

    def test_operation_result_rejects_raw_output(self):
        with self.assertRaises(Exception):
            validate(
                "mission/operation-result.schema.json",
                fixture("operation-result-secret.invalid.json"),
            )

    def test_operation_contract_rejects_unknown_enums_and_fields(self):
        intent = fixture("operation-intent.valid.json")
        intent["action_kind"] = "run-anything"
        with self.assertRaises(Exception):
            validate("mission/operation-intent.schema.json", intent)
        result = fixture("operation-result.valid.json")
        result["outcome"] = "still-running"
        result["environment"] = {"TOKEN": "not-recorded"}
        with self.assertRaises(Exception):
            validate("mission/operation-result.schema.json", result)

    def test_operation_fixture_loader_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads(
                '{"operation_id":"first","operation_id":"second"}',
                object_pairs_hook=reject_duplicate_keys,
            )

    def test_one_receipt_shape_covers_host_git_and_reconciliation(self):
        result = fixture("operation-result.valid.json")
        result.update(stage="goal-activation", action_kind="activate-goal")
        result["evidence"].update(
            external_id="goal_native_12345678", exit_status=None, output_sha256=None
        )
        validate("mission/operation-result.schema.json", result)

        result.update(stage="commit", action_kind="commit")
        result["evidence"]["external_id"] = "e" * 40
        validate("mission/operation-result.schema.json", result)

        result.update(stage="publication", action_kind="push", outcome="reconcile-required")
        result["evidence"].update(summary_code="ambiguous", external_id=None)
        validate("mission/operation-result.schema.json", result)

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

        pack = copy.deepcopy(GOAL_PACK_AUTHORIZATION)
        pack["explicit_request"] = False
        with self.assertRaises(Exception):
            validate("mission/goal-pack-authorization.schema.json", pack)

    def test_goal_pack_schemas_reject_single_item_and_unknown_queue_status(self):
        authorization = copy.deepcopy(GOAL_PACK_AUTHORIZATION)
        authorization["goal_bindings"] = authorization["goal_bindings"][:1]
        authorization["limits"]["max_goals"] = 1
        with self.assertRaises(Exception):
            validate("mission/goal-pack-authorization.schema.json", authorization)
        state = copy.deepcopy(GOAL_PACK_STATE)
        state["goals"][0]["status"] = "maybe-running"
        with self.assertRaises(Exception):
            validate("mission/goal-pack-state.schema.json", state)

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
