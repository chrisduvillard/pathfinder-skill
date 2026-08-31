import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import PolicyError
from pathfinder_core.repository import (
    GitRunner,
    goal_scope,
    inspect_repository,
    probe_repository,
)


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True)


def make_repository(path: Path):
    git(path.parent, "init", str(path))
    git(path, "config", "user.name", "Pathfinder Test")
    git(path, "config", "user.email", "pathfinder@example.invalid")
    (path / "tracked.txt").write_text("initial\n")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-m", "initial")


class RepositoryTests(unittest.TestCase):
    def test_non_git_degrades_to_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            result = probe_repository(Path(directory))
            self.assertEqual(result.kind, "non-git")
            self.assertIsNone(result.base_commit)
            scope = goal_scope(Path(directory))
            self.assertEqual(scope["repository_kind"], "non-git")
            self.assertIsNone(scope["base_commit"])
            self.assertEqual(scope["dirty_policy"], "not-applicable")

    def test_clean_git_probe_binds_exact_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            result = probe_repository(root)
            self.assertEqual(result.kind, "git")
            self.assertEqual(result.base_commit, git(root, "rev-parse", "HEAD").stdout.strip())
            self.assertFalse(result.custom_hooks_configured)

    def test_repository_local_hooks_configuration_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            git(root, "config", "core.hooksPath", ".githooks")
            self.assertTrue(probe_repository(root).custom_hooks_configured)

    def test_worktree_specific_hooks_configuration_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            git(root, "config", "extensions.worktreeConfig", "true")
            git(root, "config", "--worktree", "core.hooksPath", ".worktree-hooks")
            self.assertTrue(probe_repository(root).custom_hooks_configured)

    def test_clean_crlf_checkout_respects_effective_autocrlf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            git(Path(directory), "init", str(root))
            git(root, "config", "user.name", "Pathfinder Test")
            git(root, "config", "user.email", "pathfinder@example.invalid")
            git(root, "config", "core.autocrlf", "true")
            (root / "tracked.txt").write_bytes(b"initial\r\n")
            git(root, "add", "tracked.txt")
            git(root, "commit", "-m", "initial")
            self.assertEqual(probe_repository(root).kind, "git")

    def test_dirty_tree_blocks_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            (root / "tracked.txt").write_text("dirty\n")
            self.assertEqual(probe_repository(root).kind, "git-dirty-blocked")
            self.assertEqual(probe_repository(root, committed_base=True).kind, "git")
            self.assertEqual(goal_scope(root)["dirty_policy"], "block")
            self.assertEqual(
                goal_scope(root, committed_base=True)["dirty_policy"],
                "committed-base",
            )

    def test_goal_scope_fingerprint_is_controller_derived_and_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            first = goal_scope(root)
            second = goal_scope(root)
            self.assertEqual(first, second)
            self.assertEqual(first["repository_kind"], "git")
            self.assertEqual(first["base_commit"], git(root, "rev-parse", "HEAD").stdout.strip())
            self.assertRegex(first["repository_id"], r"^repository_[0-9a-f]{24}$")
            self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")

    def test_goal_scope_rejects_missing_paths_and_regular_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular_file = root / "file.txt"
            regular_file.write_text("not a folder\n")
            for invalid in (root / "missing", regular_file):
                with self.subTest(path=invalid), self.assertRaisesRegex(
                    PolicyError, "existing directory"
                ):
                    goal_scope(invalid)

    def test_repository_inspection_derives_capabilities_and_scope_from_one_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            observed = probe_repository(root)
            with mock.patch(
                "pathfinder_core.repository.probe_repository",
                return_value=observed,
            ) as probe:
                result = inspect_repository(root)
            probe.assert_called_once_with(root.resolve(), committed_base=False)
            self.assertEqual(result["capabilities"], observed.as_dict())
            self.assertEqual(result["goal_scope"]["base_commit"], observed.base_commit)

    def test_malicious_filename_remains_inert_git_status_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            filename = "--config=$(touch PATHFINDER_PWNED)"
            malicious = root / filename
            malicious.write_text("untrusted filename data\n")

            capabilities = probe_repository(root, committed_base=True)
            status = GitRunner(root).run(["status", "--porcelain=v1", "-z"]).stdout

            self.assertTrue(capabilities.dirty)
            self.assertIn(filename, status)
            self.assertTrue(malicious.exists())
            self.assertFalse((root / "PATHFINDER_PWNED").exists())

    def test_git_runner_neutralizes_hooks_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            with mock.patch("pathfinder_core.repository.subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                GitRunner(root).run(["status"])
            command = run.call_args.args[0]
            self.assertIn(f"core.hooksPath={os.devnull}", command)
            self.assertIn("credential.helper=", command)

            environment = run.call_args.kwargs["env"]
            self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")

    def test_repository_inspection_does_not_refresh_git_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            git(root, "read-tree", "HEAD")
            index_output = git(
                root,
                "rev-parse",
                "--path-format=absolute",
                "--git-path",
                "index",
            ).stdout.strip()
            index = Path(index_output)
            self.assertTrue(index.is_file(), index)
            before = (index.read_bytes(), index.stat().st_size, index.stat().st_mtime_ns)
            inspect_repository(root)
            after = (index.read_bytes(), index.stat().st_size, index.stat().st_mtime_ns)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
