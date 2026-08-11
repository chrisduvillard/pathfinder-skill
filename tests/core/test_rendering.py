import copy
import json
import unittest
from pathlib import Path

from pathfinder_core.errors import StateError
from pathfinder_core.rendering import (
    CANDIDATES_BEGIN,
    CANDIDATES_END,
    VERIFICATION_BEGIN,
    VERIFICATION_END,
    render_candidates_block,
    render_final_summary,
    render_goal_command,
    render_verification_block,
    repair_candidates_markdown,
    repair_verification_markdown,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "evals" / "fixtures" / "good-goal" / "artifacts"
GOLDENS = Path(__file__).parent / "fixtures" / "rendering"


def document(name: str) -> dict:
    return json.loads((SOURCE / name).read_text())


class RenderingTests(unittest.TestCase):
    def test_candidate_section_matches_golden_and_preserves_narrative(self):
        candidates = document("03-candidates.json")
        source = (GOLDENS / "03-synthesis.source.md").read_text()
        expected = (GOLDENS / "03-synthesis.md").read_text()
        rendered = repair_candidates_markdown(source, candidates)
        self.assertEqual(rendered, expected)
        self.assertEqual(repair_candidates_markdown(rendered, candidates), rendered)
        self.assertEqual(render_candidates_block(candidates), render_candidates_block(candidates))

    def test_verification_section_matches_golden_and_preserves_narrative(self):
        verification = document("03b-verification.json")
        source = (GOLDENS / "03b-verification.source.md").read_text()
        expected = (GOLDENS / "03b-verification.md").read_text()
        rendered = repair_verification_markdown(source, verification)
        self.assertEqual(rendered, expected)
        self.assertEqual(repair_verification_markdown(rendered, verification), rendered)
        self.assertEqual(
            render_verification_block(verification),
            render_verification_block(verification),
        )

    def test_generated_values_are_flattened_and_markdown_escaped(self):
        candidates = copy.deepcopy(document("03-candidates.json"))
        candidates["candidates"][0]["title"] = (
            "[linked](https://invalid) & <tag>\n"
            "<!-- pathfinder:generated:verification:v1:begin --> *bold*"
        )
        rendered = render_candidates_block(candidates)
        self.assertIn(r"\[linked\](https://invalid) &amp; &lt;tag&gt;", rendered)
        self.assertIn(r"\*bold\*", rendered)
        self.assertNotIn("\n<!-- pathfinder:generated:verification", rendered)

    def test_generated_block_changes_when_json_changes(self):
        candidates = document("03-candidates.json")
        changed = copy.deepcopy(candidates)
        changed["candidates"][0]["evidence_grade"] = "verified"
        self.assertNotEqual(render_candidates_block(candidates), render_candidates_block(changed))

        verification = document("03b-verification.json")
        changed = copy.deepcopy(verification)
        changed["results"][0]["verdict"] = "downgraded"
        self.assertNotEqual(
            render_verification_block(verification),
            render_verification_block(changed),
        )

    def test_generated_markers_reject_malformed_duplicate_and_nested_regions(self):
        candidates = document("03-candidates.json")
        cases = {
            "missing": "# Synthesis\n",
            "duplicate": (
                f"{CANDIDATES_BEGIN}\nold\n{CANDIDATES_END}\n"
                f"{CANDIDATES_BEGIN}\nold\n{CANDIDATES_END}\n"
            ),
            "nested": (
                f"{CANDIDATES_BEGIN}\n{VERIFICATION_BEGIN}\n"
                f"{VERIFICATION_END}\n{CANDIDATES_END}\n"
            ),
            "mismatched": f"{CANDIDATES_BEGIN}\nold\n{VERIFICATION_END}\n",
            "partial": f"prefix {CANDIDATES_BEGIN}\nold\n{CANDIDATES_END}\n",
        }
        for name, markdown in cases.items():
            with self.subTest(name=name), self.assertRaises(StateError):
                repair_candidates_markdown(markdown, candidates)

    def test_generated_repair_preserves_crlf_narrative_bytes(self):
        candidates = document("03-candidates.json")
        source = f"before\r\n{CANDIDATES_BEGIN}\r\ntampered\r\n{CANDIDATES_END}\r\nafter\r\n"
        rendered = repair_candidates_markdown(source, candidates)
        self.assertTrue(rendered.startswith("before\r\n"))
        self.assertTrue(rendered.endswith("\r\nafter\r\n"))

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
