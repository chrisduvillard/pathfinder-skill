#!/usr/bin/env bash
#
# Local preflight wrapper for the checks CI runs.

set -uo pipefail

root="${1:-.}"
fail=0

run_check() {
  label="$1"
  shift

  echo "==> $label"
  if "$@"; then
    echo "ok: $label"
  else
    status=$?
    echo "::error::$label failed with exit $status"
    fail=1
  fi
}

run_check "skill consistency" bash "$root/scripts/check-skill-consistency.sh" "$root"
run_check "skill behavior invariants" bash "$root/scripts/check-skill-behavior.sh" "$root"
run_check "manifest consistency" bash "$root/scripts/check-manifests.sh" "$root"
run_check "portability" bash "$root/scripts/check-portability.sh" "$root"
run_check "validator meta-tests" bash "$root/scripts/test-validators.sh" "$root"
run_check "unstaged diff whitespace/conflict markers" git -C "$root" diff --check
run_check "staged diff whitespace/conflict markers" git -C "$root" diff --cached --check

if [ "$fail" -eq 0 ]; then
  echo "check-all: all checks pass"
fi
exit "$fail"
