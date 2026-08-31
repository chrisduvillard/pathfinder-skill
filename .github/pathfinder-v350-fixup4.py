from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
release = ROOT / ".github/workflows/release.yml"
text = release.read_text(encoding="utf-8")
old = "requirements-controller.txt"
if old not in text:
    raise RuntimeError("release workflow does not install controller dependencies")
release.write_text(text.replace(old, "requirements-dev.txt", 1), encoding="utf-8")
