from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()

structured = ROOT / "tests/core/test_structured_artifacts.py"
text = structured.read_text(encoding="utf-8")
text = text.replace("import json\n", "", 1)
structured.write_text(text, encoding="utf-8")

validators = ROOT / "scripts/test-validators.sh"
text = validators.read_text(encoding="utf-8")
text = text.replace(
    '"$python_bin" - <<\'PY\' "$fixture/skills/pathfinder/SKILL.md"\n',
    '"$python_bin" - "$fixture/skills/pathfinder/SKILL.md" <<\'PY\'\n',
)
text = text.replace(
    '"$python_bin" - <<\'PY\' "$fixture/policies/pathfinder-policy.json"\n',
    '"$python_bin" - "$fixture/policies/pathfinder-policy.json" <<\'PY\'\n',
)
validators.write_text(text, encoding="utf-8")
