import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "evals/harness/validate-artifact.py"
BUNDLE_VALIDATOR = ROOT / "evals/harness/validate-bundle.py"
SCHEMA = ROOT / "schemas/artifacts/candidates.schema.json"


class ArtifactValidatorTests(unittest.TestCase):
    def run_bundle_validator(self, directory, *options):
        return subprocess.run(
            [sys.executable, str(BUNDLE_VALIDATOR), str(directory), *options],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_validator(self, text):
        with tempfile.TemporaryDirectory() as directory:
            instance = Path(directory) / "instance.json"
            instance.write_text(text)
            return subprocess.run(
                [sys.executable, str(VALIDATOR), str(SCHEMA), str(instance)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_duplicate_key_is_rejected_as_invalid_json(self):
        result = self.run_validator('{"schema_version":1,"schema_version":1}')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"], "invalid_json")

    def test_stale_schema_version_is_rejected(self):
        result = self.run_validator('{"schema_version":0}')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"], "schema_validation")

    def test_cross_artifact_candidate_mismatch_is_rejected(self):
        source = ROOT / "evals/fixtures/good-goal/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            binding_path = target / "06-goal-binding.json"
            binding = json.loads(binding_path.read_text())
            binding["selected_candidate_ids"] = ["C99"]
            binding_path.write_text(json.dumps(binding))
            result = self.run_bundle_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown candidate_id", result.stdout)

    def test_bundle_loader_rejects_duplicate_json_keys(self):
        source = ROOT / "evals/fixtures/good-goal/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            candidates_path = target / "03-candidates.json"
            candidates_path.write_text(
                candidates_path.read_text().replace(
                    '"schema_version":1',
                    '"schema_version":1,"schema_version":1',
                    1,
                )
            )
            result = self.run_bundle_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["error"], "invalid_json")

    def test_structured_verification_results_are_machine_readable(self):
        source = ROOT / "evals/fixtures/good-goal/artifacts"
        result = self.run_bundle_validator(source, "--verification-results")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "C1\taccepted\tstrong\n")

    def test_goal_binding_cannot_select_rejected_candidate(self):
        source = ROOT / "evals/fixtures/good-goal/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            verification_path = target / "03b-verification.json"
            verification = json.loads(verification_path.read_text())
            verification["results"][0]["verdict"] = "rejected"
            verification["results"][0]["final_grade"] = "rejected"
            verification_path.write_text(json.dumps(verification))
            result = self.run_bundle_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("selects a rejected candidate_id", result.stdout)


if __name__ == "__main__":
    unittest.main()
