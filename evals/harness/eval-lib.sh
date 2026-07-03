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

run_assertion() {  # <assertion-name>
  local assertion="$1"
  case "$assertion" in
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
