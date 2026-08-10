from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import CapabilityError, PolicyError


@dataclass(frozen=True)
class RepositoryCapabilities:
    kind: str
    root: str | None
    scoped_root: str
    branch: str | None
    base_commit: str | None
    dirty: bool
    remote_type: str | None
    default_branch: str | None
    custom_hooks_configured: bool
    worktrees: bool

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class GitResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class GitRunner:
    """Run controller-owned Git commands with hooks and credentials disabled."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        binary = shutil.which("git")
        if not binary:
            raise CapabilityError("git is unavailable")
        self.binary = binary
        config_environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT")
            if key in os.environ
        }
        config_environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
        try:
            configured = subprocess.run(
                [self.binary, "-C", str(self.root), "config", "--get", "core.autocrlf"],
                capture_output=True,
                text=True,
                env=config_environment,
                timeout=3,
                check=False,
            )
            value = configured.stdout.strip().lower() if configured.returncode == 0 else "false"
        except (OSError, subprocess.SubprocessError):
            value = "false"
        self.autocrlf = value if value in {"true", "false", "input"} else "false"

    def run(self, args, *, check: bool = True, cwd: Path | None = None) -> GitResult:
        if not args or any(not isinstance(item, str) or "\0" in item for item in args):
            raise PolicyError("git arguments must be non-empty strings without NUL bytes")
        working = Path(cwd or self.root).resolve()
        command = [
            self.binary,
            "-C",
            str(working),
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "credential.helper=",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.autocrlf={self.autocrlf}",
            *args,
        ]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": os.environ.get("LANG", "C"),
            "LC_ALL": os.environ.get("LC_ALL", "C"),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        completed = subprocess.run(
            command, capture_output=True, text=True, env=environment, timeout=30, check=False
        )
        result = GitResult(tuple(args), completed.returncode, completed.stdout, completed.stderr)
        if check and result.returncode != 0:
            message = result.stderr.strip().splitlines()
            detail = message[-1] if message else f"exit {result.returncode}"
            raise CapabilityError(f"git {' '.join(args[:2])} failed: {detail[:240]}")
        return result


def _remote_type(value: str) -> str:
    lowered = value.lower()
    if "github.com" in lowered:
        return "github"
    if "gitlab" in lowered:
        return "gitlab"
    if lowered.startswith(("http://", "https://", "ssh://", "git@")):
        return "other-forge"
    parsed = urlparse(value)
    if parsed.scheme == "file" or value.startswith(("/", "../", "./")):
        return "local"
    return "unknown"


def probe_repository(start: Path, *, committed_base: bool = False) -> RepositoryCapabilities:
    start = Path(start).resolve()
    try:
        discovery = GitRunner(start)
    except CapabilityError:
        return RepositoryCapabilities("non-git", None, str(start), None, None, False, None, None, False, False)
    top = discovery.run(["rev-parse", "--show-toplevel"], check=False)
    if top.returncode != 0:
        return RepositoryCapabilities("non-git", None, str(start), None, None, False, None, None, False, False)
    root = Path(top.stdout.strip()).resolve()
    try:
        start.relative_to(root)
    except ValueError as error:
        raise PolicyError("scoped root escaped the discovered Git repository") from error
    git = GitRunner(root)
    base_commit = git.run(["rev-parse", "HEAD"]).stdout.strip()
    status = git.run(["status", "--porcelain=v1", "-z"]).stdout
    dirty = bool(status)
    if dirty and not committed_base:
        dirty_policy = "block"
    else:
        dirty_policy = "committed-base" if dirty else "block"
    branch_result = git.run(["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    remote_result = git.run(["remote", "get-url", "origin"], check=False)
    remote_type = _remote_type(remote_result.stdout.strip()) if remote_result.returncode == 0 else None
    default_result = git.run(
        ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], check=False
    )
    default_branch = default_result.stdout.strip() if default_result.returncode == 0 else None
    hooks = git.run(["config", "--get", "core.hooksPath"], check=False).returncode == 0
    kind = "git"
    if dirty and dirty_policy == "block":
        kind = "git-dirty-blocked"
    return RepositoryCapabilities(
        kind, str(root), str(start), branch, base_commit, dirty, remote_type,
        default_branch, hooks, True,
    )


BRANCH_PATTERN = re.compile(r"^pathfinder/auto/[a-z0-9][a-z0-9-]{0,62}$")


def validate_branch_name(branch: str) -> None:
    if not BRANCH_PATTERN.fullmatch(branch):
        raise PolicyError("branch must match pathfinder/auto/<lowercase-slug>")
