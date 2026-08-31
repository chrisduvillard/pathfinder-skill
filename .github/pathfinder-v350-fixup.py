from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence in {relative}, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


replace_once(
    "scripts/validate-skill-policy.py",
    '        if stack and fence == stack[-1][0]:\n'
    '            stack.pop()\n'
    '        elif not stack:\n'
    '            stack.append((fence, number))\n'
    '        else:\n'
    '            fail(f"mis-nested code fence in {path}:{number}")\n',
    '        if stack:\n'
    '            if fence == stack[-1][0]:\n'
    '                stack.pop()\n'
    '            continue\n'
    '        stack.append((fence, number))\n',
)

check_all = ROOT / "scripts/check-all.sh"
text = check_all.read_text(encoding="utf-8")
text = text.replace(
    '"$PATHFINDER_CONTROLLER_PYTHON"',
    '"${PATHFINDER_CONTROLLER_PYTHON:-python3}"',
)
check_all.write_text(text, encoding="utf-8")

quality = r'''#!/usr/bin/env bash
set -uo pipefail
root="${1:-.}"
python_bin="${PATHFINDER_CONTROLLER_PYTHON:-python3}"
files=(
  "$root/pathfinder_core/goals.py"
  "$root/pathfinder_core/live_eval.py"
  "$root/pathfinder_core/outcome_lab.py"
  "$root/pathfinder_core/policy_source.py"
  "$root/pathfinder_core/recommendations.py"
  "$root/pathfinder_core/state.py"
  "$root/pathfinder_labs/__init__.py"
  "$root/tests/core/test_concurrency.py"
  "$root/tests/core/test_outcome_lab.py"
  "$root/tests/core/test_semantic_goals.py"
  "$root/tests/core/test_state_properties.py"
  "$root/tests/core/test_structured_artifacts.py"
)
"$python_bin" -m ruff check "${files[@]}"
"$python_bin" -m ruff format --check "${files[@]}"
(
  cd "$root" || exit 1
  "$python_bin" -m mypy
)
'''
write("scripts/check-python-quality.sh", quality)

pyproject = ROOT / "pyproject.toml"
text = pyproject.read_text(encoding="utf-8")
start = text.index('files = [\n', text.index('[tool.mypy]'))
end = text.index(']\n', start) + 2
replacement = '''files = [
  "pathfinder_core/goals.py",
  "pathfinder_core/live_eval.py",
  "pathfinder_core/outcome_lab.py",
  "pathfinder_core/policy_source.py",
  "pathfinder_core/recommendations.py",
  "pathfinder_core/state.py",
]
'''
pyproject.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

replace_once(
    "scripts/check-wheel.sh",
    '"$vpy" - <<\'PY\' "$tmp/doctor.json"\n',
    '"$vpy" - "$tmp/doctor.json" <<\'PY\'\n',
)

format_script = r'''#!/usr/bin/env bash
set -euo pipefail
root="${1:-.}"
python_bin="${PATHFINDER_CONTROLLER_PYTHON:-python3}"
files=(
  "$root/pathfinder_core/goals.py"
  "$root/pathfinder_core/live_eval.py"
  "$root/pathfinder_core/outcome_lab.py"
  "$root/pathfinder_core/policy_source.py"
  "$root/pathfinder_core/recommendations.py"
  "$root/pathfinder_core/state.py"
  "$root/pathfinder_labs/__init__.py"
  "$root/tests/core/test_concurrency.py"
  "$root/tests/core/test_outcome_lab.py"
  "$root/tests/core/test_semantic_goals.py"
  "$root/tests/core/test_state_properties.py"
  "$root/tests/core/test_structured_artifacts.py"
)
"$python_bin" -m ruff format "${files[@]}"
'''
write("scripts/format-python-quality-surface.sh", format_script)
