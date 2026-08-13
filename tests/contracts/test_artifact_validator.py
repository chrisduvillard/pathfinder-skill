import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "evals/harness/validate-artifact.py"
BUNDLE_VALIDATOR = ROOT / "evals/harness/validate-bundle.py"
PROMPT_REPLAY_VALIDATOR = ROOT / "evals/harness/validate-prompt-replay.py"
SCHEMA = ROOT / "schemas/artifacts/candidates.schema.json"


class ArtifactValidatorTests(unittest.TestCase):
    def prompt_replay_module(self):
        spec = importlib.util.spec_from_file_location(
            "pathfinder_validate_prompt_replay", PROMPT_REPLAY_VALIDATOR
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

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

    def run_prompt_replay_validator(self, directory):
        return subprocess.run(
            [
                sys.executable,
                str(PROMPT_REPLAY_VALIDATOR),
                str(directory),
                str(ROOT),
            ],
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

    def test_prompt_replay_validates_actual_controller_rendered_artifacts(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        self.assertEqual(self.run_prompt_replay_validator(source).returncode, 0)

    def test_prompt_replay_rejects_a_claimed_missing_artifact(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            (target / "01-blind-discovery.md").unlink()
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing or symlinked", result.stdout)

    def test_prompt_replay_rejects_a_tampered_deterministic_view(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            (target / "06-goal-command.md").write_text("looks plausible\n")
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not the deterministic controller rendering", result.stdout)

    def test_prompt_replay_rejects_an_undeclared_extra_artifact(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            (target / "07-run-log.md").write_text("undeclared lifecycle state\n")
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("undeclared extra artifacts", result.stdout)

    def test_prompt_replay_rejects_contradictory_session_facts(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            session_path = target / "00-session.md"
            session_path.write_text(
                session_path.read_text() + "- explicit execution approval: yes\n"
            )
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate replay fact", result.stdout)

    def test_prompt_replay_requires_exact_completion_field_tokens(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            binding_path = target / "06-goal-binding.json"
            binding = json.loads(binding_path.read_text())
            binding["objective"] = binding["objective"].replace(
                "changed_files", "not_changed_files"
            )
            binding_path.write_text(json.dumps(binding))
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("omits exact completion field: changed_files", result.stdout)

    def test_actual_writer_oracle_rejects_four_fabricated_read_only_files(self):
        module = self.prompt_replay_module()
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        binding = json.loads((source / "06-goal-binding.json").read_text())

        def fabricated_writer(_root, output, request_path, *, consume_request=False):
            if consume_request:
                request_path.unlink()
            names = (
                "06-goal-command.md",
                "06-goal-binding.json",
                "08-final-summary.md",
                "08-final-summary.json",
            )
            artifacts = []
            for name in names:
                path = Path(output) / name
                path.write_text("fabricated but read-only\n")
                path.chmod(0o444)
                artifacts.append(str(path))
            return {
                "mission_id": "mission_fabricated1",
                "goal_id": "goal_fabricated0001",
                "binding_id": "binding_fabricated1",
                "artifacts": artifacts,
            }

        with self.assertRaises(ValueError):
            module.exercise_actual_writer(binding, ROOT, writer=fabricated_writer)

    def test_prompt_replay_rejects_cross_artifact_identity_drift(self):
        source = ROOT / "evals/replays/fixtures/prompt-fast-path/artifacts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifacts"
            shutil.copytree(source, target)
            summary_path = target / "08-final-summary.json"
            summary = json.loads(summary_path.read_text())
            summary["mission_id"] = "mission_driftfixture1"
            summary_path.write_text(json.dumps(summary))
            result = self.run_prompt_replay_validator(target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("mission identity drift", result.stdout)


if __name__ == "__main__":
    unittest.main()
