#!/usr/bin/env bash
#
# Shared assertions for Pathfinder artifact evals.

case_value() {  # <case-file> <metadata-key>
  awk -v key="$2" '
    index($0, key ":") == 1 {
      value = substr($0, length(key) + 2)
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      print value
      exit
    }
  ' "$1"
}

case_error() {  # <message>
  echo "::error::case $CASE_ID: $*"
  CASE_FAIL=1
}

artifact_path() {  # <relative-artifact-path>
  printf '%s/%s' "$ARTIFACT_DIR" "$1"
}

assert_artifact_exists() {  # <relative-artifact-path>
  local rel="$1" path
  path="$(artifact_path "$rel")"
  if [ -f "$path" ]; then
    echo "ok: $CASE_ID: artifact exists: $rel"
  else
    case_error "$rel missing"
  fi
}

assert_goal_contract() {
  local rel path
  rel="06-goal-command.md"
  path="$(artifact_path "$rel")"

  assert_artifact_exists "$rel"
  [ -f "$path" ] || return

  if ! awk 'NF { found = 1 } END { exit found ? 0 : 1 }' "$path"; then
    case_error "$rel is empty"
  fi

  if ! awk '
    {
      line = tolower($0)
      if (line ~ /(^|[^a-z])(goal|implementation goal|\/goal)([^a-z]|$)/) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$path"; then
    case_error "$rel missing measurable end state"
  fi

  if ! awk '
    {
      line = tolower($0)
      if (line ~ /(proof|verified by|exits 0|test|check|benchmark|git status)/) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$path"; then
    case_error "$rel missing proof surface"
  fi

  if ! awk '
    {
      line = tolower($0)
      if (line ~ /(constraint|no schema|no new dependency|no public api|scoped|only)/) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$path"; then
    case_error "$rel missing constraints"
  fi

  if ! awk '
    {
      line = tolower($0)
      if (line ~ /(stop after|blocked|next input needed|turns?)/) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$path"; then
    case_error "$rel missing stop condition"
  fi
}

run_assertion() {  # <assertion-name>
  local assertion="$1"
  case "$assertion" in
    goal_contract)
      assert_goal_contract
      ;;
    artifact_exists:*)
      assert_artifact_exists "${assertion#artifact_exists:}"
      ;;
    "")
      ;;
    *)
      case_error "unknown assertion \"$assertion\""
      ;;
  esac
}