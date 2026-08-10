import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.repository import GitRunner, probe_repository


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

    def test_clean_git_probe_binds_exact_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            result = probe_repository(root)
            self.assertEqual(result.kind, "git")
            self.assertEqual(result.base_commit, git(root, "rev-parse", "HEAD").stdout.strip())

    def test_dirty_tree_blocks_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            make_repository(root)
            (root / "tracked.txt").write_text("dirty\n")
            self.assertEqual(probe_repository(root).kind, "git-dirty-blocked")
            self.assertEqual(probe_repository(root, committed_base=True).kind, "git")

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


if __name__ == "__main__":
    unittest.main()
