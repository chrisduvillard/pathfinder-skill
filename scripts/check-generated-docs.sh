#!/usr/bin/env bash
# Verify committed generated documentation matches its canonical data source.

set -uo pipefail

root="${1:-.}"

if [ -n "${PATHFINDER_DOCS_PYTHON:-}" ]; then
  python_bin="$PATHFINDER_DOCS_PYTHON"
elif [ -n "${PATHFINDER_CONTROLLER_PYTHON:-}" ]; then
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
  echo "::error::Python 3.11+ is required to check generated documentation"
  exit 1
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "::error::Python 3.11+ is required to check generated documentation"
  exit 1
fi

"$python_bin" "$root/scripts/render_protected_surfaces.py" "$root" --check
