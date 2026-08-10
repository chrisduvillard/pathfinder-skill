from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .policy import CommandSpec, ExecutionPolicy


TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+|token[=:]\s*|api[_-]?key[=:]\s*|password[=:]\s*)([^\s,;]+)"
)


def _hash(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def redact_output(value: str) -> str:
    redacted = TOKEN_PATTERN.sub(lambda match: match.group(1) + "[REDACTED]", value)
    home = str(Path.home())
    if home and home != "/":
        redacted = redacted.replace(home, "[HOME]")
    return redacted


@dataclass(frozen=True)
class ExecutionResult:
    argv_sha256: str
    environment_policy_sha256: str
    working_directory: str
    timeout_seconds: int
    exit_status: int | None
    timed_out: bool
    stdout: str
    stderr: str


class Executor:
    def __init__(self, policy: ExecutionPolicy):
        self.policy = policy

    def run(self, spec: CommandSpec, boundary: dict) -> ExecutionResult:
        self.policy.validate(spec, boundary)
        environment = {key: value for key, value in spec.environment.items()}
        environment.setdefault("PATH", os.environ.get("PATH", ""))
        try:
            completed = subprocess.run(
                list(spec.argv), cwd=str(Path(spec.cwd).resolve()), env=environment,
                capture_output=True, text=True, shell=False,
                timeout=spec.timeout_seconds, check=False,
            )
            status = completed.returncode
            timed_out = False
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as error:
            status = None
            timed_out = True
            stdout = error.stdout or ""
            stderr = error.stderr or "command timed out"
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
        return ExecutionResult(
            argv_sha256=_hash(spec.argv),
            environment_policy_sha256=_hash(sorted(environment)),
            working_directory=str(Path(spec.cwd).resolve()),
            timeout_seconds=spec.timeout_seconds,
            exit_status=status,
            timed_out=timed_out,
            stdout=redact_output(stdout),
            stderr=redact_output(stderr),
        )
