#!/usr/bin/env bash
set -uo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
plugin_root="$(cd "$script_dir/.." && pwd)"

if [ -n "${PATHFINDER_PYTHON:-}" ]; then
  python_bin="$PATHFINDER_PYTHON"
elif [ -x "$plugin_root/.venv/bin/python" ]; then
  python_bin="$plugin_root/.venv/bin/python"
elif [ -x "$plugin_root/.venv/Scripts/python.exe" ]; then
  python_bin="$plugin_root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
else
  echo '{"error":{"code":"controller_unavailable","message":"Python 3.11+ is not available"}}' >&2
  exit 3
fi

PYTHONPATH="$plugin_root" exec "$python_bin" -m pathfinder_core "$@"
