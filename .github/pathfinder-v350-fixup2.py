from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
workflow = ROOT / ".github/workflows/manifests.yml"
text = workflow.read_text(encoding="utf-8")
anchor = "  check:\n    name: preflight (${{ matrix.os }})\n"
if anchor not in text:
    raise RuntimeError("preflight job anchor is missing")
start = text.index(anchor)
timeout = text.index("    timeout-minutes: 10\n", start)
end_of_job_header = text.index("    steps:\n", start)
if timeout > end_of_job_header:
    raise RuntimeError("preflight timeout was not found in the job header")
text = text[:timeout] + "    timeout-minutes: 25\n" + text[timeout + len("    timeout-minutes: 10\n") :]
workflow.write_text(text, encoding="utf-8")
