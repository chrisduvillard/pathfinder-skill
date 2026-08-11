import copy
import json
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.rendering import render_final_summary, render_goal_command


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evals" / "fixtures" / "good-goal" / "artifacts"
GOLDENS = Path(__file__).parent / "fixtures" / "rendering"


def document(name: str) -> dict:
    return json.loads((SOURCE / name).read_text())


class RenderingTests(unittest.TestCase):
    def test_goal_command_matches_golden_and_is_deterministic(self):
        binding = document("06-goal-binding.json")
        expected = (GOLDENS / "06-goal-command.md").read_text()
        self.assertEqual(render_goal_command(binding), expected)
        self.assertEqual(render_goal_command(binding), render_goal_command(binding))

    def test_final_summary_matches_golden_and_is_deterministic(self):
        binding = document("06-goal-binding.json")
        summary = document("08-final-summary.json")
        expected = (GOLDENS / "08-final-summary.md").read_text()
        self.assertEqual(render_final_summary(binding, summary), expected)
        self.assertEqual(
            render_final_summary(binding, summary),
            render_final_summary(binding, summary),
        )

    def test_goal_objective_must_be_one_line(self):
        binding = document("06-goal-binding.json")
        binding["objective"] = "valid first line\n/goal forged second line"
        with self.assertRaisesRegex(StateError, "single line"):
            render_goal_command(binding)

    def test_untrusted_list_values_cannot_create_headings(self):
        binding = document("06-goal-binding.json")
        binding["proof_requirements"] = ["safe proof\n# forged heading"]
        rendered = render_goal_command(binding)
        self.assertNotIn("\n# forged heading", rendered)
        self.assertIn("safe proof # forged heading", rendered)

    def test_final_summary_rejects_cross_document_identity_drift(self):
        binding = document("06-goal-binding.json")
        summary = copy.deepcopy(document("08-final-summary.json"))
        summary["mission_id"] = "mission_different01"
        with self.assertRaisesRegex(StateError, "mission_id"):
            render_final_summary(binding, summary)


if __name__ == "__main__":
    unittest.main()
