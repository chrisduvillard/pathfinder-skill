#!/usr/bin/env bash
#
# Run deterministic artifact evals for Pathfinder run-trail contracts.
# Seeded fixtures are copied to a temporary workspace and read as data only.

set -uo pipefail

root="${1:-.}"
cases_dir="${2:-$root/evals/cases}"
lib="$root/evals/harness/eval-lib.sh"
fail=0

if [ -n "${PATHFINDER_EVAL_PYTHON:-}" ]; then
  eval_python="$PATHFINDER_EVAL_PYTHON"
elif [ -x "$root/.venv/bin/python" ]; then
  eval_python="$root/.venv/bin/python"
elif [ -x "$root/.venv/Scripts/python.exe" ]; then
  eval_python="$root/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  eval_python="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  eval_python="$(command -v python)"
else
  echo "::error::Python 3.11 with requirements-controller.txt is required for artifact schema validation"
  exit 1
fi
export PATHFINDER_EVAL_PYTHON="$eval_python"
export PATHFINDER_SCHEMA_ROOT="$root/schemas"
export PATHFINDER_EVAL_VALIDATOR="$root/evals/harness/validate-artifact.py"
export PATHFINDER_BUNDLE_VALIDATOR="$root/evals/harness/validate-bundle.py"

err() { echo "::error::$*"; fail=1; }
ok() { echo "ok: $*"; }

[ -f "$lib" ] || { echo "::error::missing eval harness: $lib"; exit 1; }
# shellcheck source=/dev/null
. "$lib"

[ -d "$cases_dir" ] || { echo "::error::missing eval cases directory: $cases_dir"; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

run_case_file() {
  local case_file="$1"
  local expected fixture expected_failure assertions workspace result_output

  CASE_ID=""
  expected=""
  fixture=""
  expected_failure=""
  assertions=""

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      case-id:*) CASE_ID="${line#case-id: }" ;;
      eval-id:*) CASE_ID="${line#eval-id: }" ;;
      expected:*) expected="${line#expected: }" ;;
      eval-expect:*) expected="${line#eval-expect: }" ;;
      eval-fixture:*) fixture="${line#eval-fixture: }" ;;
      expected-failure:*) expected_failure="${line#expected-failure: }" ;;
      eval-failure-pattern:*) expected_failure="${line#eval-failure-pattern: }" ;;
      assertion:*) assertions="${assertions}${line#assertion: }"$'\n' ;;
      eval-assertions:*)
        for assertion in ${line#eval-assertions: }; do
          assertions="${assertions}${assertion}"$'\n'
        done
        ;;
    esac
  done < "$case_file"

  [ -n "$CASE_ID" ] || { err "$(basename "$case_file") missing case-id"; return; }
  [ "$expected" = "pass" ] || [ "$expected" = "fail" ] || { err "$CASE_ID has invalid expected value: ${expected:-<missing>}"; return; }
  [ -n "$fixture" ] || { err "$CASE_ID missing eval-fixture"; return; }
  [ -d "$root/$fixture" ] || { err "$CASE_ID fixture missing: $fixture"; return; }
  [ -n "$assertions" ] || { err "$CASE_ID has no assertions"; return; }

  workspace="$tmp/$CASE_ID"
  mkdir -p "$workspace"
  cp -R "$root/$fixture/." "$workspace/"

  ARTIFACT_DIR="$workspace/artifacts"
  REPO_DIR="$workspace/repo"
  case_errors=""

  while IFS= read -r assertion; do
    [ -n "$assertion" ] || continue
    run_assertion "$assertion"
  done < <(printf '%s' "$assertions")

  result_output="$case_errors"
  if [ "$expected" = "pass" ]; then
    if [ -z "$result_output" ]; then
      ok "eval case $CASE_ID passed"
    else
      err "case $CASE_ID expected pass but failed"
      printf '%s' "$result_output"
    fi
  else
    if [ -z "$result_output" ]; then
      err "case $CASE_ID expected failure but passed cleanly"
    elif [ -n "$expected_failure" ] && ! printf '%s' "$result_output" | grep -Eq -- "$expected_failure"; then
      err "case $CASE_ID failed for the wrong reason; expected /$expected_failure/"
      printf '%s' "$result_output"
    else
      ok "eval case $CASE_ID failed for expected reason"
    fi
  fi
}

found=0
for case_file in "$cases_dir"/*.md; do
  [ -f "$case_file" ] || continue
  found=1
  run_case_file "$case_file"
done

if [ "$found" -eq 0 ]; then
  err "no eval cases found in $cases_dir"
fi

if [ "$fail" -eq 0 ]; then
  echo "check-evals: all artifact evals pass"
fi
exit "$fail"
