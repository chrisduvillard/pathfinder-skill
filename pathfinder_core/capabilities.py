from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Capability:
    status: Availability
    detail: str


def _version(binary: str, args: Iterable[str] = ("--version",)) -> Capability:
    path = shutil.which(binary)
    if not path:
        return Capability(Availability.UNAVAILABLE, f"{binary} not found")
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=3, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return Capability(Availability.UNKNOWN, f"{binary} version probe failed")
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0][:160] if output else f"{binary} returned {result.returncode}"
    status = Availability.AVAILABLE if result.returncode == 0 else Availability.UNKNOWN
    return Capability(status, detail)


def probe_capabilities() -> dict:
    python_ok = sys.version_info >= (3, 11)
    schema_ok = importlib.util.find_spec("jsonschema") is not None
    date_format_ok = importlib.util.find_spec("rfc3339_validator") is not None
    dependencies_ok = python_ok and schema_ok and date_format_ok

    controller_dependencies = Capability(
        Availability.AVAILABLE if dependencies_ok else Availability.UNAVAILABLE,
        "Python 3.11+, jsonschema, and RFC 3339 validation are available"
        if dependencies_ok
        else "install Python 3.11+ and requirements-controller.txt",
    )
    mission_protocol = Capability(
        Availability.AVAILABLE if dependencies_ok else Availability.UNAVAILABLE,
        "local start/next/record/resume protocol is callable; host attestation is separate"
        if dependencies_ok
        else "controller dependencies are unavailable",
    )

    capabilities = {
        "controller_importable": Capability(
            Availability.AVAILABLE, "pathfinder_core is importable"
        ),
        "controller_dependencies": controller_dependencies,
        "python": Capability(
            Availability.AVAILABLE if python_ok else Availability.UNAVAILABLE,
            platform.python_version(),
        ),
        "schema_validation": Capability(
            Availability.AVAILABLE
            if schema_ok and date_format_ok
            else Availability.UNAVAILABLE,
            "jsonschema and RFC 3339 validation are importable"
            if schema_ok and date_format_ok
            else "install requirements-controller.txt",
        ),
        "git": _version("git"),
        "github_cli": _version("gh"),
        "native_goal": Capability(
            Availability.UNKNOWN, "requires host adapter negotiation"
        ),
        "mission_protocol": mission_protocol,
        "host_runtime_attestation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "filesystem_sandbox": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "process_isolation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "network_policy": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "credential_isolation": Capability(
            Availability.UNKNOWN, "requires host-provided enforcement evidence"
        ),
        "installed_publication": Capability(
            Availability.UNAVAILABLE,
            "the installed controller has no push, pull-request, merge, release, or deploy command",
        ),
        "source_publication_primitives": Capability(
            Availability.AVAILABLE,
            "default-off source components are present but have no installed caller or credentials",
        ),
        "unattended_execution": Capability(
            Availability.UNAVAILABLE,
            "host enforcement is not attested by the local capability probe",
        ),
        # Compatibility aliases retained for existing consumers. Their details
        # explicitly describe the narrower fact represented by each alias.
        "controller": controller_dependencies,
        "mission_runner": mission_protocol,
        "publication": Capability(
            Availability.UNAVAILABLE,
            "installed publication is intentionally unavailable",
        ),
    }

    unattended = all(
        capabilities[name].status is Availability.AVAILABLE
        for name in (
            "controller_dependencies",
            "mission_protocol",
            "git",
            "host_runtime_attestation",
            "filesystem_sandbox",
            "process_isolation",
            "network_policy",
            "credential_isolation",
        )
    )
    return {
        "schema_version": 1,
        "controller_available": dependencies_ok,
        # Compatibility alias retained for existing consumers. This reports only
        # that local controller dependencies can load, not that a host can run a
        # mission unattended.
        "runner_available": dependencies_ok,
        "mission_runner_available": (
            mission_protocol.status is Availability.AVAILABLE
        ),
        "unattended_execution_eligible": unattended,
        "capabilities": {
            name: asdict(value) for name, value in capabilities.items()
        },
    }


def capabilities_json() -> str:
    return json.dumps(probe_capabilities(), indent=2, sort_keys=True)
