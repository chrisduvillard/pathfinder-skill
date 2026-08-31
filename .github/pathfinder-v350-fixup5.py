from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
release = ROOT / ".github/workflows/release.yml"
text = release.read_text(encoding="utf-8")
text = text.replace("requirements-controller.txt", "requirements-dev.txt")
if "requirements-dev.txt" not in text:
    raise RuntimeError("release workflow does not install the complete v3.5.0 gate dependencies")
if re.search(r"pip[^\n]*requirements-controller\.txt", text):
    raise RuntimeError("release workflow still installs the old dependency set")
release.write_text(text, encoding="utf-8")
