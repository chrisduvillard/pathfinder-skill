#!/usr/bin/env bash
#
# Deterministic artifact evals for Pathfinder.
# Reads seeded fixtures as data only. Does not execute fixture repo code.

set -uo pipefail

root="${1:-.}"
fail=0
case_count=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

lib="$root/evals/harness/eval-lib.sh"
if [ ! -f "$lib" ]; then
  echo "::error::missing eval harness: $lib"
  exit 1
fi

# shellcheck source=/dev/null
. "$lib"

bad_suite() {
  echo "::error::$*"
  fail=1
}

run_case() {  # <case-file>
  local case_file="$1" id fixture expect assertions pattern fixture_path workspace out

  id="$(case_value "$case_file" "eval-id")"
  fixture="$(case_value "$case_file" "eval-fixture")"
  expect="$(case_value "$case_file" "eval-expect")"
  assertions="$(case_value "$case_file" "eval-assertions")"
  pattern="$(case_value "$case_file" "eval-failure-pattern")"

  if [ -z "$id" ] || [ -z "$fixture" ] || [ -z "$expect" ] || [ -z "$assertions" ]; then
    bad_suite "case metadata incomplete: $case_file"
    return
  fi

  fixture_path="$root/$fixture"
  if [ ! -d "$fixture_path" ]; then
    bad_suite "case $id fixture missing: $fixture"
    return
  fi

  workspace="$tmp/$id"
  mkdir -p "$workspace"
  cp -R "$fixture_path/." "$workspace/"

  CASE_ID="$id"
  CASE_FAIL=0
  ARTIFACT_DIR="$workspace/artifacts"
  EVAL_TMP="$tmp"
  out="$tmp/$id.out"

  {
    for assertion in $assertions; do
      run_assertion "$assertion"
    done
  } > "$out" 2>&1

  case "$expect" in
    pass)
      if [ "$CASE_FAIL" -eq 0 ]; then
        echo "ok: eval case passed: $id"
      else
        bad_suite "case $id expected pass but failed"
        cat "$out"
      fi
      ;;
    fail)
      if [ "$CASE_FAIL" -eq 0 ]; then
        bad_suite "case $id expected failure but passed"
      elif [ -n "$pattern" ] && ! grep -Eq "$pattern" "$out"; then
        bad_suite "case $id failed for the wrong reason; expected /$pattern/"
        cat "$out"
      else
        echo "ok: eval case caught expected failure: $id"
      fi
      ;;
    *)
      bad_suite "case $id has invalid eval-expect: $expect"
      ;;
  esac
}

for case_file in "$root"/evals/cases/*.md; do
  [ -f "$case_file" ] || continue
  case_count=$((case_count + 1))
  run_case "$case_file"
done

if [ "$case_count" -eq 0 ]; then
  bad_suite "no eval cases found under $root/evals/cases"
fi

if [ "$fail" -eq 0 ]; then
  echo "check-evals: all artifact evals pass"
fi
exit "$fail"
