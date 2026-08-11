from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import PolicyError


SHELL_EXECUTABLES = {"sh", "bash", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}
SHELL_METACHARACTERS = (";", "&&", "||", "`", "$(`", "\n", "\r", "\0")
DENIED_ACTIONS = {
    "publish", "release", "deploy", "destroy", "migrate", "migration",
    "reset --hard", "clean -f", "push --force", "push -f", "branch -d", "tag -d",
}
SECRET_NAME = re.compile(
    r"(^|[/\\])(\.env(?:\.[^/\\]+)?|\.git-credentials|credentials?|id_rsa|id_ed25519|[^/\\]+\.(pem|key|p12|pfx))$",
    re.IGNORECASE,
)
SENSITIVE_ENV = re.compile(
    r"(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|AUTH|COOKIE|CREDENTIAL|SSH_AUTH_SOCK|GIT_ASKPASS)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    environment: dict[str, str]


class ExecutionPolicy:
    def __init__(self, root: Path, allowed_executables):
        self.root = Path(root).resolve()
        self.allowed_executables = {str(Path(item).resolve()) for item in allowed_executables}

    def validate_boundary(self, boundary: dict) -> None:
        requirements = {
            "filesystem": "enforced",
            "process": "enforced",
            "credentials": "isolated",
            "repo_code_execution": "allowlisted",
            "tool_allowlist_enforced": True,
            "pre_execution_consent": True,
            "execution_eligible": True,
        }
        for field, expected in requirements.items():
            if boundary.get(field) != expected:
                raise PolicyError(f"runtime boundary blocks execution: {field} is not {expected}")
        if boundary.get("network") not in {"denied", "restricted"}:
            raise PolicyError("runtime boundary blocks execution: network is open or unknown")

    def validate(self, spec: CommandSpec, boundary: dict) -> None:
        self.validate_boundary(boundary)
        if not spec.argv or any(not isinstance(item, str) for item in spec.argv):
            raise PolicyError("command argv must be a non-empty string tuple")
        executable = Path(spec.argv[0])
        if not executable.is_absolute():
            raise PolicyError("command executable must be an absolute allowlisted path")
        resolved_executable = str(executable.resolve())
        if executable.name.lower() in SHELL_EXECUTABLES:
            raise PolicyError("shell interpreters are not allowed for unattended execution")
        if resolved_executable not in self.allowed_executables:
            raise PolicyError("command executable is not allowlisted")
        cwd = Path(spec.cwd).resolve()
        try:
            cwd.relative_to(self.root)
        except ValueError as error:
            raise PolicyError("command working directory escapes mission worktree") from error
        if not 1 <= spec.timeout_seconds <= 3600:
            raise PolicyError("command timeout must be between 1 and 3600 seconds")
        joined = " ".join(spec.argv[1:]).lower()
        if any(marker in item for item in spec.argv for marker in SHELL_METACHARACTERS):
            raise PolicyError("shell metacharacters are not accepted in structured argv")
        if any(action in joined for action in DENIED_ACTIONS):
            raise PolicyError("command matches a destructive or external-side-effect deny rule")
        if any(SECRET_NAME.search(item) for item in spec.argv[1:]):
            raise PolicyError("command references a protected secret or credential path")
        if "credential.helper" in joined:
            raise PolicyError("credential helpers are forbidden during implementation")
        forbidden_keys = [key for key in spec.environment if SENSITIVE_ENV.search(key)]
        if forbidden_keys:
            raise PolicyError("credential-bearing environment keys are forbidden")
        allowed_environment = {"PATH", "LANG", "LC_ALL", "CI", "NO_COLOR"}
        unknown_keys = set(spec.environment) - allowed_environment
        if unknown_keys:
            raise PolicyError(f"environment key is not allowlisted: {sorted(unknown_keys)[0]}")
