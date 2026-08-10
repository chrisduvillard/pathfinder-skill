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
            result = subprocess.run(
                [sys.executable, str(BUNDLE_VALIDATOR), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown candidate_id", result.stdout)


if __name__ == "__main__":
    unittest.main()
