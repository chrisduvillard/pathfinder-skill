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

assert_rejected_not_selectable() {
  local verification funnel ids id
  verification="$(artifact_path "03b-verification.md")"
  funnel="$(artifact_path "04-question-funnel.md")"

  assert_artifact_exists "03b-verification.md"
  assert_artifact_exists "04-question-funnel.md"
  [ -f "$verification" ] && [ -f "$funnel" ] || return

  ids="$(awk -F':[[:space:]]*' '
    tolower($1) == "rejected-candidate-id" { print $2 }
  ' "$verification")"

  if [ -z "$ids" ]; then
    case_error "03b-verification.md has no rejected-candidate-id lines"
    return
  fi

  for id in $ids; do
    if awk -F':[[:space:]]*' -v id="$id" '
      tolower($1) == "selectable-candidate-id" && $2 == id { found = 1 }
      END { exit found ? 0 : 1 }
    ' "$funnel"; then
      case_error "04-question-funnel.md rejected candidate $id appears selectable"
    fi
  done
}

assert_downgrade_reflected() {
  local verification funnel pairs pair id grade
  verification="$(artifact_path "03b-verification.md")"
  funnel="$(artifact_path "04-question-funnel.md")"

  assert_artifact_exists "03b-verification.md"
  assert_artifact_exists "04-question-funnel.md"
  [ -f "$verification" ] && [ -f "$funnel" ] || return

  pairs="$(awk '
    tolower($1) == "downgrade:" && tolower($3) == "to" { print $2 ":" tolower($4) }
  ' "$verification")"

  if [ -z "$pairs" ]; then
    case_error "03b-verification.md has no downgrade lines"
    return
  fi

  for pair in $pairs; do
    id="${pair%%:*}"
    grade="${pair#*:}"
    if ! awk -v id="$id" -v grade="$grade" '
      tolower($1) == "candidate-grade:" && $2 == id && tolower($3) == grade { found = 1 }
      END { exit found ? 0 : 1 }
    ' "$funnel"; then
      case_error "04-question-funnel.md missing reflected downgrade for $id to $grade"
    fi
  done
}

assert_protected_surface_boundary() {
  local combined surfaces surface
  combined="$EVAL_TMP/$CASE_ID.combined.md"

  if ! find "$ARTIFACT_DIR" -type f -name '*.md' -exec cat {} + > "$combined"; then
    case_error "could not read artifact markdown files"
    return
  fi

  surfaces="$(awk -F':[[:space:]]*' '
    tolower($1) == "protected-surface" { print tolower($2) }
  ' "$combined")"

  if [ -z "$surfaces" ]; then
    case_error "no protected-surface lines found"
    return
  fi

  if awk '
    {
      line = tolower($0)
      if (line ~ /^(manual-review-boundary|doctrine-proof-boundary|safety-boundary):[[:space:]]*yes$/) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$combined"; then
    echo "ok: $CASE_ID: protected surface boundary present"
    return
  fi

  for surface in $surfaces; do
    case_error "missing manual/proof/safety boundary for $surface surface"
  done
}

assert_track_b_phase4b_not_applicable() {
  local verification
  verification="$(artifact_path "03b-verification.md")"

  assert_artifact_exists "03b-verification.md"
  [ -f "$verification" ] || return

  if ! awk '
    {
      line = tolower($0)
      if (index(line, "not applicable: track b")) found = 1
    }
    END { exit found ? 0 : 1 }
  ' "$verification"; then
    case_error "03b-verification.md missing Track B not-applicable marker"
  fi
}

run_assertion() {  # <assertion-name>
  local assertion="$1"
  case "$assertion" in
    goal_contract)
      assert_goal_contract
      ;;
    protected_surface_boundary)
      assert_protected_surface_boundary
      ;;
    track_b_phase4b_not_applicable)
      assert_track_b_phase4b_not_applicable
      ;;
    rejected_not_selectable)
      assert_rejected_not_selectable
      ;;
    downgrade_reflected)
      assert_downgrade_reflected
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
