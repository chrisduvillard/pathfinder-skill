import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from pathfinder_core.errors import PolicyError
from pathfinder_core.worktrees import WorktreeManager

from tests.core.test_repository import git, make_repository


class WorktreeTests(unittest.TestCase):
    def test_create_uses_exact_base_and_does_not_run_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            worktrees = base / "worktrees"
            worktrees.mkdir()
            make_repository(root)
            hook = root / ".git" / "hooks" / "post-checkout"
            marker = base / "hook-ran"
            hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            commit = git(root, "rev-parse", "HEAD").stdout.strip()
            result = WorktreeManager(root, worktrees).create(
                worktrees / "goal", "pathfinder/auto/test-goal", commit, "worktree_12345678"
            )
            self.assertEqual(result.base_commit, commit)
            self.assertFalse(marker.exists())

    def test_symlink_escape_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            allowed = base / "allowed"
            outside = base / "outside"
            allowed.mkdir()
            outside.mkdir()
            make_repository(root)
            os.symlink(outside, allowed / "escape")
            manager = WorktreeManager(root, allowed)
            with self.assertRaisesRegex(PolicyError, "escapes"):
                manager.create(
                    allowed / "escape" / "goal", "pathfinder/auto/test-goal",
                    git(root, "rev-parse", "HEAD").stdout.strip(), "worktree_12345678",
                )

    def test_existing_exact_branch_is_reused_for_new_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            allowed = base / "worktrees"
            allowed.mkdir()
            make_repository(root)
            commit = git(root, "rev-parse", "HEAD").stdout.strip()
            git(root, "branch", "pathfinder/auto/test-goal", commit)
            tree = WorktreeManager(root, allowed).create(
                allowed / "goal", "pathfinder/auto/test-goal", commit, "worktree_12345678"
            )
            self.assertEqual(tree.base_commit, commit)
            self.assertEqual(
                git(Path(tree.path), "symbolic-ref", "--short", "HEAD").stdout.strip(),
                "pathfinder/auto/test-goal",
            )

    def test_cleanup_rejects_target_outside_owned_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            allowed = base / "worktrees"
            outside = base / "outside"
            allowed.mkdir()
            outside.mkdir()
            make_repository(root)
            with self.assertRaisesRegex(PolicyError, "escapes"):
                WorktreeManager(root, allowed).cleanup_status(
                    outside, "pathfinder/auto/test-goal", "HEAD",
                    active_mission_references=False,
                )

    def test_cleanup_refuses_dirty_unmerged_or_referenced_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repo"
            allowed = base / "worktrees"
            allowed.mkdir()
            make_repository(root)
            commit = git(root, "rev-parse", "HEAD").stdout.strip()
            manager = WorktreeManager(root, allowed)
            tree = manager.create(
                allowed / "goal", "pathfinder/auto/test-goal", commit, "worktree_12345678"
            )
            (Path(tree.path) / "tracked.txt").write_text("dirty\n")
            status = manager.cleanup_status(
                Path(tree.path), tree.branch, commit, active_mission_references=True
            )
            self.assertFalse(status.eligible)
            self.assertTrue(status.dirty)
            self.assertTrue(status.active_mission_references)


if __name__ == "__main__":
    unittest.main()
