from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import PolicyError
from .repository import GitRunner, validate_branch_name


@dataclass(frozen=True)
class Worktree:
    worktree_id: str
    path: str
    branch: str
    base_commit: str


@dataclass(frozen=True)
class CleanupStatus:
    eligible: bool
    dirty: bool
    merged: bool
    active_mission_references: bool
    reasons: tuple[str, ...]


class WorktreeManager:
    def __init__(self, repository_root: Path, allowed_parent: Path):
        self.repository_root = Path(repository_root).resolve()
        self.allowed_parent = Path(allowed_parent).resolve()
        self.git = GitRunner(self.repository_root)

    def _safe_target(self, target: Path) -> Path:
        target = Path(target)
        if target.exists() or target.is_symlink():
            raise PolicyError(f"worktree target already exists: {target}")
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(self.allowed_parent)
        except ValueError as error:
            raise PolicyError("worktree target escapes the allowed parent") from error
        if resolved.parent != self.allowed_parent and not resolved.parent.is_dir():
            raise PolicyError("worktree target parent must already exist")
        return resolved

    def _owned_target(self, target: Path) -> Path:
        resolved = Path(target).resolve()
        try:
            relative = resolved.relative_to(self.allowed_parent)
        except ValueError as error:
            raise PolicyError("worktree target escapes the allowed parent") from error
        if not relative.parts:
            raise PolicyError("worktree target cannot be the allowed parent itself")
        return resolved

    def create(self, target: Path, branch: str, base_commit: str, worktree_id: str) -> Worktree:
        validate_branch_name(branch)
        target = Path(target)
        if target.exists() and not target.is_symlink():
            resolved = target.resolve()
            try:
                resolved.relative_to(self.allowed_parent)
            except ValueError as error:
                raise PolicyError("existing worktree escapes the allowed parent") from error
            existing_git = GitRunner(resolved)
            actual = existing_git.run(["rev-parse", "HEAD"]).stdout.strip()
            branch_result = existing_git.run(
                ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False
            )
            if actual == base_commit and branch_result.stdout.strip() == branch:
                return Worktree(worktree_id, str(resolved), branch, base_commit)
            raise PolicyError("existing worktree does not match mission branch and base")
        resolved = self._safe_target(target)
        branch_exists = self.git.run(
            ["show-ref", "--verify", f"refs/heads/{branch}"], check=False
        ).returncode == 0
        if branch_exists:
            actual_branch_base = self.git.run(["rev-parse", branch]).stdout.strip()
            if actual_branch_base != base_commit:
                raise PolicyError("existing mission branch does not match the bound base commit")
            self.git.run(["worktree", "add", str(resolved), branch])
        else:
            self.git.run(["worktree", "add", "-b", branch, str(resolved), base_commit])
        actual = GitRunner(resolved).run(["rev-parse", "HEAD"]).stdout.strip()
        if actual != base_commit:
            raise PolicyError("created worktree does not match the bound base commit")
        return Worktree(worktree_id, str(resolved), branch, base_commit)

    def cleanup_status(
        self, target: Path, branch: str, base_ref: str, *, active_mission_references: bool
    ) -> CleanupStatus:
        resolved = self._owned_target(target)
        dirty = bool(GitRunner(resolved).run(["status", "--porcelain=v1", "-z"]).stdout)
        merged_result = self.git.run(["merge-base", "--is-ancestor", branch, base_ref], check=False)
        merged = merged_result.returncode == 0
        reasons = []
        if dirty:
            reasons.append("worktree is dirty")
        if not merged:
            reasons.append("branch has unmerged commits")
        if active_mission_references:
            reasons.append("worktree is referenced by active mission state")
        return CleanupStatus(not reasons, dirty, merged, active_mission_references, tuple(reasons))

    def remove(self, target: Path, branch: str, base_ref: str, *, active_mission_references: bool):
        status = self.cleanup_status(
            target, branch, base_ref, active_mission_references=active_mission_references
        )
        if not status.eligible:
            raise PolicyError("unsafe worktree cleanup: " + "; ".join(status.reasons))
        self.git.run(["worktree", "remove", str(Path(target).resolve())])
        return status
