from __future__ import annotations

import hashlib
import json
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
        # Read only the effective line-ending enum before entering the neutralized
        # environment. Git for Windows commonly defines it in system config.
        config_environment["GIT_TERMINAL_PROMPT"] = "0"
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
            "GIT_OPTIONAL_LOCKS": "0",
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
    # Restrict these queries to persisted repository/worktree configuration. A
    # normal unscoped query would report GitRunner's command-only /dev/null safety
    # override as if the user configured it. Worktree config can override local
    # config when extensions.worktreeConfig is enabled, so inspect both stores.
    hooks = any(
        git.run(
            ["config", scope, "--get", "core.hooksPath"], check=False
        ).returncode == 0
        for scope in ("--local", "--worktree")
    )
    kind = "git"
    if dirty and dirty_policy == "block":
        kind = "git-dirty-blocked"
    return RepositoryCapabilities(
        kind, str(root), str(start), branch, base_commit, dirty, remote_type,
        default_branch, hooks, True,
    )


def _goal_scope_from_probe(
    selected: Path,
    capabilities: RepositoryCapabilities,
    *,
    committed_base: bool,
) -> dict:
    selected = Path(selected).resolve()
    if capabilities.kind == "non-git":
        repository_kind = "non-git"
        root = selected
        scoped_root = "."
        base_commit = None
        dirty_policy = "not-applicable"
    else:
        repository_kind = "git"
        root = Path(capabilities.root).resolve()
        scoped_root = selected.relative_to(root).as_posix() or "."
        base_commit = capabilities.base_commit
        dirty_policy = "committed-base" if capabilities.dirty and committed_base else "block"
    identity_payload = json.dumps(
        {"kind": repository_kind, "root": str(root)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    repository_id = f"repository_{hashlib.sha256(identity_payload).hexdigest()[:24]}"
    scope = {
        "repository_kind": repository_kind,
        "repository_id": repository_id,
        "scoped_root": scoped_root,
        "base_commit": base_commit,
        "dirty_policy": dirty_policy,
    }
    scope["fingerprint"] = hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return scope


def inspect_repository(start: Path, *, committed_base: bool = False) -> dict:
    """Probe repository facts once and derive the matching saved-Goal scope."""
    selected = Path(start).resolve()
    if not selected.is_dir():
        raise PolicyError("repository scope must be an existing directory")
    if not os.access(selected, os.R_OK | os.X_OK):
        raise PolicyError("repository scope must be readable")
    capabilities = probe_repository(selected, committed_base=committed_base)
    return {
        "capabilities": capabilities.as_dict(),
        "goal_scope": _goal_scope_from_probe(
            selected,
            capabilities,
            committed_base=committed_base,
        ),
    }


def goal_scope(start: Path, *, committed_base: bool = False) -> dict:
    """Return the controller-derived scope used by saved prompt Goals.

    The fingerprint binds local repository identity, selected scope, committed
    base, and dirty-tree policy. It deliberately does not crawl or execute
    repository content; discovery caches own separate content fingerprints.
    """
    return inspect_repository(start, committed_base=committed_base)["goal_scope"]


BRANCH_PATTERN = re.compile(r"^pathfinder/auto/[a-z0-9][a-z0-9-]{0,62}$")


def validate_branch_name(branch: str) -> None:
    if not BRANCH_PATTERN.fullmatch(branch):
        raise PolicyError("branch must match pathfinder/auto/<lowercase-slug>")
