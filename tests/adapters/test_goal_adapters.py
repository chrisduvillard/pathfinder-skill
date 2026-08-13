import unittest

from pathfinder_core.adapters.claude import ClaudeGoalAdapter
from pathfinder_core.adapters.codex import CodexGoalAdapter
from pathfinder_core.adapters.generic import GenericGoalAdapter
from pathfinder_core.adapters.types import GoalRecord, GoalStatus
from pathfinder_core.errors import CapabilityError, StateError


class FakeCodexBackend:
    def __init__(self, current=None):
        self.current = current or GoalRecord(None, None, GoalStatus.NONE)
        self.created = 0

    def inspect(self): return self.current
    def observe(self): return self.current
    def create(self, objective):
        self.created += 1
        self.current = GoalRecord("goal_native123", objective, GoalStatus.ACTIVE)
        return self.current
    def complete(self, goal_id):
        self.current = GoalRecord(goal_id, self.current.objective, GoalStatus.COMPLETE)
        return self.current
    def block(self, goal_id):
        self.current = GoalRecord(goal_id, self.current.objective, GoalStatus.BLOCKED)
        return self.current


class GoalAdapterTests(unittest.TestCase):
    def test_codex_does_not_overwrite_unfinished_goal(self):
        backend = FakeCodexBackend(GoalRecord("goal_existing", "old", GoalStatus.ACTIVE))
        with self.assertRaisesRegex(StateError, "unfinished"):
            CodexGoalAdapter(backend).create("new")
        self.assertEqual(backend.created, 0)

    def test_codex_reuses_same_active_goal(self):
        backend = FakeCodexBackend(GoalRecord("goal_existing", "same", GoalStatus.ACTIVE))
        result = CodexGoalAdapter(backend).create("same")
        self.assertEqual(result.mode, "native-reused")
        self.assertEqual(backend.created, 0)

    def test_codex_completion_requires_validated_evidence(self):
        backend = FakeCodexBackend(GoalRecord("goal_existing", "same", GoalStatus.ACTIVE))
        with self.assertRaisesRegex(StateError, "validated evidence"):
            CodexGoalAdapter(backend).complete("goal_existing", evidence_validated=False)

    def test_codex_block_respects_host_threshold(self):
        with self.assertRaises(CapabilityError):
            CodexGoalAdapter(FakeCodexBackend()).block(
                "goal_existing", consecutive_blocked_turns=1
            )

    def test_codex_without_backend_returns_manual_goal_command(self):
        result = CodexGoalAdapter().create("finish with proof")
        self.assertEqual(result.mode, "manual")
        self.assertEqual(result.instruction, "/goal finish with proof")

    def test_claude_launcher_and_manual_modes(self):
        launched = []
        manual = ClaudeGoalAdapter().create("objective")
        self.assertEqual(manual.mode, "manual")
        self.assertEqual(manual.record.status, GoalStatus.NONE)
        self.assertEqual(manual.instruction, "/goal objective")
        result = ClaudeGoalAdapter(launched.append).create("objective")
        self.assertEqual(result.mode, "native-launched")
        self.assertEqual(result.record.status, GoalStatus.ACTIVE)
        self.assertEqual(launched, ["/goal objective"])

    def test_generic_fallback_is_labeled_non_persistent(self):
        result = GenericGoalAdapter().create("objective")
        self.assertEqual(result.mode, "non-persistent-fallback")
        self.assertIn("non-persistent", result.instruction)


if __name__ == "__main__":
    unittest.main()
