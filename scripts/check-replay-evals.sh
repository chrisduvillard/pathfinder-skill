#!/usr/bin/env bash
#
# Optional replay eval runner for recorded Pathfinder transcripts/artifacts.
# Required CI uses scripts/check-evals.sh only; this runner is opt-in and
# reuses the deterministic artifact assertion format when replay cases exist.

set -uo pipefail

root="${1:-.}"
cases_dir="${2:-$root/evals/replays/cases}"

if [ ! -d "$cases_dir" ]; then
  echo "check-replay-evals: no replay cases directory found; skipped ($cases_dir)"
  exit 0
fi

found=0
for case_file in "$cases_dir"/*.md; do
  [ -f "$case_file" ] || continue
  found=1
  break
done

if [ "$found" -eq 0 ]; then
  echo "check-replay-evals: no replay cases found; skipped ($cases_dir)"
  exit 0
fi

bash "$root/scripts/check-evals.sh" "$root" "$cases_dir"
