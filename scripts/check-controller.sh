#!/usr/bin/env bash
# Run deterministic controller contracts and integration tests.

set -uo pipefail

root="${1:-.}"

if [ -n "${PATHFINDER_CONTROLLER_PYTHON:-}" ]; then
  python_bin="$PATHFINDER_CONTROLLER_PYTHON"
elif [ -x "$root/.venv/bin/python" ]; then
  python_bin="$root/.venv/bin/python"
elif [ -x "$root/.venv/Scripts/python.exe" ]; then
  python_bin="$root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
else
  echo "::error::Python 3.11+ is required for controller tests"
  exit 1
fi

if ! "$python_bin" -c 'import jsonschema, rfc3339_validator; import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "::error::install Python 3.11+ dependencies from requirements-controller.txt"
  exit 1
fi

"$python_bin" -m unittest discover -s "$root/tests" -t "$root" -p 'test_*.py'
