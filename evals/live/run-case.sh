#!/usr/bin/env bash
set -uo pipefail

root="$1"
case_file="$2"

if [ -x "$root/.venv/bin/python" ]; then
  python_bin="$root/.venv/bin/python"
elif [ -x "$root/.venv/Scripts/python.exe" ]; then
  python_bin="$root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
else
  echo "::error::Python 3.11 is required for bounded live evals"
  exit 1
fi

"$python_bin" "$root/evals/live/run-case.py" "$case_file"
