#!/usr/bin/env bash
#
# Optional live-model eval runner for tiny fixture repositories.
# This is deliberately disabled by default so required CI remains deterministic
# and performs no live model calls.

set -uo pipefail

root="${1:-.}"
cases_dir="${2:-$root/evals/live/cases}"
runner="${PATHFINDER_LIVE_EVAL_RUNNER:-$root/evals/live/run-case.sh}"
fail=0

if [ "${PATHFINDER_LIVE_EVALS:-}" != "1" ]; then
  echo "check-live-evals: skipped; set PATHFINDER_LIVE_EVALS=1 to enable local live-model evals"
  exit 0
fi

if [ ! -d "$cases_dir" ]; then
  echo "::error::live evals enabled but cases directory is missing: $cases_dir"
  exit 1
fi

if [ ! -f "$runner" ]; then
  echo "::error::live evals enabled but runner is missing: $runner"
  exit 1
fi

found=0
for case_file in "$cases_dir"/*.md; do
  [ -f "$case_file" ] || continue
  found=1
  echo "==> live eval $(basename "$case_file")"
  if bash "$runner" "$root" "$case_file"; then
    echo "ok: live eval $(basename "$case_file")"
  else
    status=$?
    echo "::error::live eval $(basename "$case_file") failed with exit $status"
    fail=1
  fi
done

if [ "$found" -eq 0 ]; then
  echo "::error::live evals enabled but no cases found in $cases_dir"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "check-live-evals: all enabled live evals pass"
fi
exit "$fail"
