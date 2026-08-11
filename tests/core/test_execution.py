import sys
import tempfile
import unittest
from pathlib import Path

from pathfinder_core.errors import PolicyError
from pathfinder_core.execution import Executor
from pathfinder_core.policy import CommandSpec, ExecutionPolicy


BOUNDARY = {
    "filesystem": "enforced", "process": "enforced", "network": "denied",
    "credentials": "isolated", "repo_code_execution": "allowlisted",
    "tool_allowlist_enforced": True, "pre_execution_consent": True,
    "execution_eligible": True,
}


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.python = str(Path(sys.executable).resolve())
        self.executor = Executor(ExecutionPolicy(self.root, {self.python}))

    def tearDown(self):
        self.directory.cleanup()

    def spec(self, *args, timeout=5, environment=None):
        return CommandSpec((self.python, *args), self.root, timeout, environment or {})

    def test_runs_structured_allowlisted_argv(self):
        result = self.executor.run(self.spec("-c", "print('ok')"), BOUNDARY)
        self.assertEqual(result.exit_status, 0)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertEqual(len(result.argv_sha256), 64)

    def test_shell_metacharacter_is_rejected(self):
        with self.assertRaisesRegex(PolicyError, "metacharacters"):
            self.executor.run(self.spec("-c", "print('x'); print('y')"), BOUNDARY)

    def test_credential_helper_and_secret_paths_are_rejected(self):
        for argument in ("credential.helper=osxkeychain", ".env.production"):
            with self.subTest(argument=argument):
                with self.assertRaises(PolicyError):
                    self.executor.run(self.spec(argument), BOUNDARY)

    def test_credential_environment_is_rejected(self):
        with self.assertRaisesRegex(PolicyError, "credential-bearing"):
            self.executor.run(self.spec("--version", environment={"API_TOKEN": "secret"}), BOUNDARY)

    def test_unknown_network_blocks_execution(self):
        boundary = dict(BOUNDARY, network="unknown", execution_eligible=False)
        with self.assertRaisesRegex(PolicyError, "execution_eligible|network"):
            self.executor.run(self.spec("--version"), boundary)

    def test_timeout_is_bounded_and_reported(self):
        result = self.executor.run(
            self.spec("-c", "__import__('time').sleep(2)", timeout=1), BOUNDARY
        )
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_status)

    def test_malicious_output_is_redacted(self):
        result = self.executor.run(
            self.spec("-c", "print('token=super-secret')"), BOUNDARY
        )
        self.assertNotIn("super-secret", result.stdout)
        self.assertIn("[REDACTED]", result.stdout)


if __name__ == "__main__":
    unittest.main()
