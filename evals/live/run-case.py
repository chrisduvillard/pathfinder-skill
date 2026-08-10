from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def metadata(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if ": " in line and not line.startswith("#"):
            key, value = line.split(": ", 1)
            result[key] = value
    return result


def main() -> int:
    case_path = Path(sys.argv[1]).resolve()
    case = metadata(case_path)
    binary_text = os.environ.get("PATHFINDER_LIVE_AGENT_BIN", "")
    binary = Path(binary_text)
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        print("::error::PATHFINDER_LIVE_AGENT_BIN must be an absolute executable path")
        return 2
    limit = int(case.get("max-seconds", "120"))
    if limit < 1 or limit > 300:
        print("::error::live case max-seconds must be between 1 and 300")
        return 2
    with tempfile.TemporaryDirectory(prefix="pathfinder-live-") as directory:
        workspace = Path(directory) / "synthetic-repo"
        workspace.mkdir()
        (workspace / "app.py").write_text("def status():\n    return 'ready'\n")
        (workspace / "test_app.py").write_text("from app import status\n\ndef test_status():\n    assert status() == 'ready'\n")
        transcript = Path(directory) / "transcript.txt"
        try:
            completed = subprocess.run(
                [str(binary), str(case_path), str(workspace), str(transcript)],
                cwd=workspace,
                timeout=limit,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"::error::{case.get('case-id', case_path.stem)} exceeded {limit}s")
            return 1
        if completed.returncode != 0 or not transcript.is_file():
            print("::error::live adapter failed or did not write a transcript")
            return 1
        text = transcript.read_text(errors="replace")
        expected = case.get("expected-pattern")
        forbidden = case.get("forbidden-pattern")
        if expected and not re.search(expected, text, re.IGNORECASE):
            print(f"::error::transcript missing expected pattern: {expected}")
            return 1
        if forbidden and re.search(forbidden, text, re.IGNORECASE):
            print(f"::error::transcript contains forbidden pattern: {forbidden}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
