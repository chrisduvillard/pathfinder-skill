#!/usr/bin/env bash
#
# Guards the markdown-only surface the manifest CI cannot see.
#
# SKILL.md is the canonical 9-phase spec; question-funnel-template.md and
# goal-best-practices.md re-specify its Phase 5 / Phase 6 screens and rules by
# hand. That duplication drifts — the VERSION.md changelog records the same
# "mirror the template" fix across v2.7.0, v2.8.0, v2.9.0, v2.9.1. The four JSON
# manifests are guarded by manifests.yml; nothing guarded these markdown files.
#
# This asserts (1) every references/<name>.md path cited in SKILL.md exists, and
# (2) a small set of invariants that must appear in BOTH the canonical SKILL.md
# and the named mirror, so deleting one from a single file (the usual drift)
# fails CI instead of shipping silently.
#
# Usage: bash scripts/check-skill-consistency.sh [ROOT]   (ROOT defaults to ".")
# Exit 0 when all invariants hold; non-zero otherwise.

set -uo pipefail

root="${1:-.}"
skill="$root/skills/pathfinder/SKILL.md"
funnel="$root/skills/pathfinder/references/question-funnel-template.md"
goal="$root/skills/pathfinder/references/goal-best-practices.md"
arts="$root/skills/pathfinder/references/artifact-structure.md"
charter="$root/skills/pathfinder/references/charter-template.md"
roadmap="$root/skills/pathfinder/references/roadmap-template.md"
scout="$root/skills/pathfinder/references/scout-brief-template.md"
contributing="$root/CONTRIBUTING.md"
fail=0

err() { echo "::error::$*"; fail=1; }

for f in "$skill" "$funnel" "$goal" "$arts" "$charter" "$roadmap" "$scout" "$contributing"; do
  [ -f "$f" ] || err "missing required file: $f"
done
if [ "$fail" -ne 0 ]; then exit "$fail"; fi

# (1) Reference-path contract: every references/<name>.md cited in SKILL.md must
#     exist on disk, and the cited set must include every required reference.
#     This catches both a renamed reference and a citation removed together with
#     its file.
cited_refs="$(grep -oE 'references/[a-z0-9-]+\.md' "$skill" | sort -u)"
expected_refs="$(printf '%s\n' \
  'references/artifact-structure.md' \
  'references/charter-template.md' \
  'references/goal-best-practices.md' \
  'references/question-funnel-template.md' \
  'references/roadmap-template.md' \
  'references/scout-brief-template.md' \
  | sort -u)"
while IFS= read -r ref; do
  [ -n "$ref" ] || continue
  if [ -f "$root/skills/pathfinder/$ref" ]; then
    echo "ok: cited reference exists: $ref"
  else
    err "SKILL.md cites a missing reference path: $ref"
  fi
done < <(printf '%s\n' "$cited_refs")
if [ "$cited_refs" = "$expected_refs" ]; then
  echo "ok: required reference citation set matches SKILL.md"
else
  err "required-reference citation drift: SKILL.md must cite exactly the required references"
  echo "  missing from SKILL.md:  $(comm -23 <(printf '%s\n' "$expected_refs") <(printf '%s\n' "$cited_refs") | tr '\n' ' ')"
  echo "  unexpected in SKILL.md: $(comm -13 <(printf '%s\n' "$expected_refs") <(printf '%s\n' "$cited_refs") | tr '\n' ' ')"
fi

# (2) Cross-file invariants. Each token must appear in BOTH the canonical
#     SKILL.md and the named mirror; present-in-one-only (drift) or absent-in-
#     both fails.
check_pair() {
  local token="$1" mirror="$2" label="$3" a b
  grep -qF -- "$token" "$skill" && a=1 || a=0
  grep -qF -- "$token" "$mirror" && b=1 || b=0
  if [ "$a" = 1 ] && [ "$b" = 1 ]; then
    echo "ok: $label consistent (SKILL.md + $(basename "$mirror"))"
  else
    err "$label drift: SKILL.md=$a $(basename "$mirror")=$b — token \"$token\""
  fi
}

check_skill_section() {
  local start="$1" end="$2" token="$3" label="$4"
  if awk -v start="$start" -v stop="$end" -v token="$token" '
    BEGIN { token = tolower(token); found = 0 }
    index($0, start) { in_section = 1 }
    in_section && index($0, stop) { exit }
    in_section && index(tolower($0), token) { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$skill"; then
    echo "ok: $label present in section \"$start\""
  else
    err "$label drift: token \"$token\" missing from section \"$start\""
  fi
}

# Phase 5 funnel invariants (SKILL.md <-> question-funnel-template.md)
check_pair "Default to option 2" "$funnel" "execution-mode default"
check_pair "five levels"          "$funnel" "five-level funnel cap"
check_pair "None of these"        "$funnel" "free-text escape grammar"
check_pair "back to candidates"   "$funnel" "back-to-candidates lateral move"
check_pair "show the full map"    "$funnel" "show-the-full-map lateral move"
check_pair "✓ confirmed"          "$funnel" "evidence glyph legend"
check_pair "goal pack"            "$funnel" "goal-pack multi-select output"
check_pair "grouping review"      "$funnel" "grouping-review bulk selection"
check_pair "select all"           "$funnel" "select-all bulk grammar"
check_pair "prompt-to-goal"       "$funnel" "prompt-to-goal track"
check_pair "gap-driven"           "$funnel" "gap-driven clarifying funnel"
check_pair "Verified:"            "$funnel" "post-verification grade field"
check_pair "Rejected by verification" "$funnel" "rejected-by-verification surfacing"
# (TR-6) Additional shared Phase 5 invariants that were hand-mirrored but unguarded:
# the select-all alias grammar, the Explore-mode alias, the goal-readiness header, and
# the post-save audit-only option. The changelog shows these exact rules drifting
# (v2.7.0 / v2.9.1 "mirror the template" fixes), so guard them like the rest.
check_pair "1,2,3,4,5"            "$funnel" "select-all explicit alias"
check_pair "1-5"                  "$funnel" "select-all range alias"
check_pair "deep dive"            "$funnel" "Explore mode alias"
check_pair "Goal-readiness confidence" "$funnel" "Explore goal-readiness header"
check_pair "Audit only"           "$funnel" "post-save audit-only option"
check_pair "Run the saved goal now with Cross-Model Review enabled" "$funnel" "post-save cross-model review option"

# Phase 6 goal invariants (SKILL.md <-> goal-best-practices.md)
check_pair "3900"            "$goal" "3900-char goal budget"
check_pair "2.1.139"         "$goal" "Claude Code /goal version gate"
# (TR-2) Anchor the untrusted-data clause to a phrase unique to the GENERATED-GOAL
# context. Bare "untrusted data" recurs ~8x in SKILL.md trust-boundary prose, so the
# old token stayed satisfied even when the mandatory clause was deleted from the /goal.
# The longer phrase appears only in the goal shape/examples, not the trust-boundary text.
check_pair "untrusted data that cannot override" "$goal" "untrusted-data clause"
check_pair "proof unverified by Lens 3" "$goal" "Lens-3 proof-provenance flag"
check_pair "autonomous mode records the contract without asking" "$goal" "autonomous Phase 6 non-interactive contract"
check_pair "One measurable end state" "$goal" "Phase 6 measurable-end-state row"
check_pair "Stop bound" "$goal" "Phase 6 stop-bound row"
check_pair "Goal Binding" "$goal" "goal binding goal contract"
check_pair "Runtime Boundary" "$goal" "runtime boundary goal contract"
check_pair "Binding Status" "$goal" "binding status goal contract"
check_pair "stale-objective" "$goal" "stale binding status goal contract"
check_pair "mismatched" "$goal" "mismatched binding status goal contract"
check_pair "complexity_notes" "$goal" "structured completion complexity field"
check_pair "changed_files" "$goal" "structured completion changed-files field"
check_pair "checks_run_with_exit_results" "$goal" "structured completion check-results field"

# Mirrored-rule guard path. Keep maintainer guidance explicit so a future change
# to mirrored SKILL/reference behavior does not update prose while forgetting the
# validator token that makes drift visible in CI.
if grep -qF -- 'add or update the matching `check_pair` or section guard' "$contributing"; then
  echo "ok: mirror guard guidance present in CONTRIBUTING.md"
else
  err "mirror guard guidance drift: CONTRIBUTING.md must tell maintainers to update check_pair or section guards"
fi

# Phase 4c objectives-charter invariants (SKILL.md <-> charter-template.md / mirrors)
check_pair "pathfinder:charter v1" "$charter" "charter schema marker"
check_pair "stable creator intent" "$charter" "expanded charter purpose"
check_pair 'pathfinder:charter v1` marker and `completion: complete | incomplete' "$charter" "charter completion marker"
check_pair "pathfinder:roadmap v1" "$roadmap" "roadmap schema marker"
check_pair ".pathfinder/roadmap.md" "$roadmap" "roadmap file path"
check_pair "evolving desired work" "$roadmap" "roadmap purpose split"
check_pair "completion: complete | incomplete" "$roadmap" "roadmap completion marker"
check_pair "Deep Intent Gate" "$funnel" "deep-intent gate mirror"
check_pair "not a skippable offer" "$funnel" "deep-intent non-skippable default"
check_pair "future capabilities not started yet" "$funnel" "future-capabilities question"
check_pair "8 to 12 compact screens" "$funnel" "deep-intent interview depth"
check_pair "continue later" "$funnel" "partial-intent continuation escape"
check_pair ".pathfinder/roadmap.md" "$arts" "artifact roadmap intent file"
check_pair "07b-cross-model-review.md" "$arts" "cross-model review artifact"
check_pair "outside the run folder" "$arts" "intent files outside run folder"
check_pair "Goal Binding" "$arts" "goal binding artifact contract"
check_pair "Runtime Boundary" "$arts" "runtime boundary artifact contract"
check_pair "Binding Status" "$arts" "binding status artifact contract"
check_pair "tool_allowlist_enforced" "$arts" "runtime tool-allowlist field"
check_pair "credential_exposure" "$arts" "runtime credential-exposure field"
check_pair "stale-objective" "$arts" "stale binding status artifact contract"
check_pair "mismatched" "$arts" "mismatched binding status artifact contract"
check_pair "not-run" "$arts" "not-run binding status artifact contract"
check_pair "Aligns:"           "$funnel" "objective alignment signal"
check_pair "ignore objectives" "$funnel" "ignore-objectives escape"
check_pair "Aligns:   ✓ north-star" "$funnel" "north-star alignment axis"
check_pair "in service of <north-star>" "$goal" "charter goal-direction framing"
check_pair "omit the Direction line when no charter is loaded" "$goal" "conditional charter Direction row"
check_pair "relevant charter plus roadmap direction" "$goal" "creator-model goal framing"
check_pair "roadmap item id in supporting notes" "$goal" "roadmap provenance notes"
check_pair "model-depth proof gate" "$goal" "autonomy model-depth proof gate"
check_pair "full code implementation" "$goal" "full implementation goal contract"
check_pair "deep verification/testing" "$goal" "deep verification goal contract"
check_pair "Cross-Model Review" "$goal" "cross-model review goal constraints"
check_pair "goal-bounded fixes and related polish" "$goal" "cross-model reviewer fix boundary"

# Good examples should demonstrate the same proof/safety obligations required by
# the checklist above them, not weaker shorthand that looks acceptable in docs
# while producing under-specified generated goals.
good_examples="$(awk '
  /^## Good examples/ { in_good = 1; next }
  /^## Bad examples/ { in_good = 0 }
  in_good && /^\/goal / { print }
' "$goal")"
good_example_count=$(printf '%s\n' "$good_examples" | sed '/^$/d' | wc -l | tr -d ' ')
if [ "$good_example_count" -ne 2 ]; then
  err "goal-best-practices.md should contain exactly 2 good /goal examples, found $good_example_count"
fi
good_example_i=0
while IFS= read -r example; do
  [ -n "$example" ] || continue
  good_example_i=$((good_example_i + 1))
  case "$example" in
    *"Final report must include"*) echo "ok: good goal example $good_example_i includes final-report proof language" ;;
    *) err "good goal example $good_example_i is missing final-report proof language" ;;
  esac
  case "$example" in
    *"deep verification/testing"*) echo "ok: good goal example $good_example_i includes deep verification/testing language" ;;
    *) err "good goal example $good_example_i is missing deep verification/testing language" ;;
  esac
  case "$example" in
    *"changed_files"*complexity_notes*) echo "ok: good goal example $good_example_i includes structured completion claim fields" ;;
    *) err "good goal example $good_example_i is missing structured completion claim fields" ;;
  esac
  if [[ "$example" == *"Stop before touching"* || "$example" == *"Do not touch"* ]]; then
    echo "ok: good goal example $good_example_i includes protected-area stop language"
  else
    err "good goal example $good_example_i is missing protected-area stop language"
  fi
done < <(printf '%s\n' "$good_examples")

check_pair "manual-handoff" "$arts" "cross-model manual handoff mode"
check_pair "failed-to-launch" "$arts" "cross-model failed-to-launch mode"
if grep -qF -- 'launch mode is `launched`, `manual-handoff`, `skipped`, or `failed-to-launch`' "$arts"; then
  echo "ok: cross-model launch-mode contract present in $(basename "$arts")"
else
  err "artifact-structure.md is missing the exact cross-model launch-mode contract"
fi
if grep -qF -- 'final disposition is `clean`, `fixed-clean`, `needs-primary-followup`, `needs-user-review`, `blocked`, or `skipped`' "$arts"; then
  echo "ok: cross-model final-disposition contract present in $(basename "$arts")"
else
  err "artifact-structure.md is missing the exact cross-model final-disposition contract"
fi
check_skill_section "## Cross-Model Review" "## Phase 8:" "two review/fix passes maximum" "cross-model two-pass bound"
check_skill_section "## Cross-Model Review" "## Phase 8:" 'clean` or `fixed-clean' "cross-model clean disposition gate"
check_skill_section "## Cross-Model Review" "## Phase 8:" "No API, OpenRouter, browser automation, or hidden credentials" "cross-model v1 backend boundary"
check_skill_section "### Phase 7-A:" "### Reporting" "Cross-Model Review" "autonomous cross-model review gate"
check_skill_section "### Phase 7-A:" "### Reporting" 'clean` or `fixed-clean' "autonomous clean review disposition gate"
check_skill_section "### Phase 7-A:" "### Reporting" "before commit or publication" "autonomous review before publication"

# (2b) Single-file presence: the Track B "How should I help?" entry-menu screen is
#      prompt-to-goal routing that lives only in SKILL.md (it is deliberately not
#      mirrored into the funnel template), so it cannot use check_pair. Assert it is
#      present so silently dropping the routing screen fails CI like any other drift.
if grep -qF -- "How should I help?" "$skill"; then
  echo "ok: Track B entry-menu screen present in SKILL.md"
else
  err "SKILL.md is missing the Track B \"How should I help?\" entry-menu screen"
fi

# (2c) Bare /pathfinder entry chooser invariants (SKILL-only presence). The chooser
#      is an entry-routing surface before Phase 0, so it deliberately is not mirrored
#      into the Phase 5 question-funnel template. Guard the fixed option labels and
#      status alias so the discoverability surface cannot silently regress.
entry_chooser_invariants=(
  "What do you want Pathfinder to do?"
  "Explore this repo and propose work"
  "Turn a prompt into a /goal"
  "Run autonomously"
  "Refresh creator model"
  "Show status/help"
  "Recommendation: 🟢 <1 | 2 | 3 | 4 | 5> — <selected option label>"
  "Recommend option 1 only when there is no supplied prompt, no usable complete charter/roadmap, and no visible prior Pathfinder run."
  "Recommend option 4 when the creator model is missing, incomplete, schema-invalid, or stale but prior Pathfinder state exists."
  "Recommend option 5 when both intent files are complete and prior runs exist, but the user supplied no concrete task."
  "Do not place a static [recommended] marker on option 1 before checking local state."
  "/pathfinder status"
  "returns to this chooser"
  "does not create run artifacts"
)
for inv in "${entry_chooser_invariants[@]}"; do
  if grep -qF -- "$inv" "$skill"; then
    echo "ok: entry chooser invariant present: \"$inv\""
  else
    err "SKILL.md is missing entry chooser invariant: \"$inv\""
  fi
done
if grep -qF -- "[recommended for an unfamiliar repo]" "$skill"; then
  err "SKILL.md still contains the stale static entry recommendation label"
else
  echo "ok: entry chooser has no stale static unfamiliar-repo recommendation label"
fi

# (2d) Autonomous-mode safety invariants (SKILL-only presence). Autonomous mode is an
#      explicit opt-in tier that grants unattended commit/push/merge. Its load-bearing
#      carve-outs have no natural Phase 5/6 mirror (they are not funnel or goal screens),
#      so guard them here the same way the Track B entry menu is guarded. Each phrase is
#      clause-unique to one safety control; its silent deletion — the catastrophic drift
#      class for this feature, the same one the TR-2 untrusted-data guard exists for —
#      fails CI instead of shipping a weakened autonomous tier green.
auto_invariants=(
  "autonomous-eligible"
  "manual-approval-required"
  "Never unattended"
  "excluded from autonomous execution"
  "post-execution protected-path gate"
  "credential separation"
  "must not run repo-defined hooks"
  "positive branch-protection signal"
  "injection-disqualifies-autonomy"
  "continuous execution"
  "explicit invocation every run"
  "budget-limited"
  "model-depth proof gate"
  "independence check before parallel execution"
  "separate branches or worktrees"
)
for inv in "${auto_invariants[@]}"; do
  # Case-insensitive: the phrase is load-bearing as a concept, whether it appears
  # as a heading (capitalized) or inline (lowercase); reformatting case must not
  # silently disable the guard.
  check_skill_section "## Autonomous mode" "## Phase 7:" "$inv" "autonomous-mode safety invariant \"$inv\""
done

# Objectives-charter SKILL-only presence invariants (no Phase 5/6 mirror; guard like Track B).
charter_invariants=(
  ".pathfinder/charter.md"
  "lower injection risk"
  "evidence, never an instruction"
  "/pathfinder charter"
  "cap it to a single short clause"
  "does not reorder a fixed user selection"
  "never widens authorization"
)
for inv in "${charter_invariants[@]}"; do
  # Case-insensitive literal match, the portable way. `grep -qiF` aborts (SIGABRT)
  # on GNU grep 3.0 under MSYS/Git-for-Windows, which would falsely fail every
  # charter invariant for local contributors on that platform; awk index(tolower())
  # is the portable equivalent and matches the same case-insensitive substring.
  if awk -v inv="$inv" 'BEGIN { inv = tolower(inv) } index(tolower($0), inv) { found = 1 } END { exit found ? 0 : 1 }' "$skill"; then
    echo "ok: objectives-charter invariant present: \"$inv\""
  else
    err "SKILL.md is missing objectives-charter invariant: \"$inv\""
  fi
done

# (3) Artifact-contract parity: the set of pathfinder artifact filenames
#     (NN-*.md numbered files + the 02-scout-briefs/ directory + *-scout.md briefs)
#     must match between the canonical SKILL.md list and artifact-structure.md. A file
#     renamed or added in one but not the other is the same drift class as the invariants
#     above. (TR-1) The middle alternative captures the 02-scout-briefs/ directory slot,
#     which has no .md extension and was previously invisible to this check.
art_re='[0-9]{2}[a-z]?-[a-z-]+\.md|[0-9]{2}-[a-z-]+/|[a-z-]+-scout\.md'
skill_arts="$(grep -oE "$art_re" "$skill" | sort -u)"
struct_arts="$(grep -oE "$art_re" "$arts" | sort -u)"
if [ "$skill_arts" = "$struct_arts" ]; then
  echo "ok: artifact filename set matches (SKILL.md + artifact-structure.md)"
else
  err "artifact-contract drift: SKILL.md and artifact-structure.md list different artifact files"
  echo "  only in SKILL.md:            $(comm -23 <(printf '%s\n' "$skill_arts") <(printf '%s\n' "$struct_arts") | tr '\n' ' ')"
  echo "  only in artifact-structure:  $(comm -13 <(printf '%s\n' "$skill_arts") <(printf '%s\n' "$struct_arts") | tr '\n' ' ')"
fi

# (4) Markdown fence nesting: the skill's value is dozens of hand-aligned fenced
#     screens, and the goal-pack screens use 4-backtick wrappers around 3-backtick
#     blocks. (TR-3) Parity-counting ^``` lines was blind to that nesting: downgrading
#     a 4-backtick wrapper to 3 keeps the count even but corrupts the render, and two
#     compensating odd defects also net even. Instead, track open/close state honoring
#     fence length: a block opened with N backticks closes only on an info-less line of
#     >= N backticks. A file that ends inside an open fence fails.
for f in "$skill" "$root"/skills/pathfinder/references/*.md; do
  state=$(awk '
    {
      n = 0
      while (substr($0, n + 1, 1) == "`") n++
      if (n < 3) next                         # not a fence line
      rest = substr($0, n + 1)
      sub(/[ \t]+$/, "", rest)                # strip trailing whitespace
      if (depth == 0) { depth = 1; openlen = n; next }   # open a fenced block
      if (rest == "" && n >= openlen) depth = 0          # close only on bare >= fence
      # any other fence line is literal content of the open block
    }
    END { print (depth == 0) ? "ok" : "open" }
  ' "$f")
  if [ "$state" = "ok" ]; then
    echo "ok: code fences nest and close ($(basename "$f"))"
  else
    err "mis-nested or unterminated code fence in $f (ends inside an open fence; check 3- vs 4-backtick nesting)"
  fi
done

# (TR-3 cont.) The open/close tracker above catches every asymmetric fence error and any
# file that ends inside an open block, but a SYMMETRIC 4->3 downgrade of the goal-pack
# wrapper (both fences) re-pairs into valid-but-wrong markdown it cannot see. The goal-pack
# example in SKILL.md nests 3-backtick blocks, so it MUST keep a 4-backtick wrapper. Assert
# those 4-backtick fences are present and balanced so downgrading them fails CI.
quad=$(grep -cE '^`{4}' "$skill" || true)
if [ "$quad" -ge 2 ] && [ $((quad % 2)) -eq 0 ]; then
  echo "ok: goal-pack 4-backtick wrapper present and balanced ($quad) in SKILL.md"
else
  err "goal-pack 4-backtick wrapper drift in SKILL.md: found $quad 4-backtick fence line(s) (need an even count >= 2; a 4->3 downgrade corrupts the nested goal-pack render)"
fi

if [ "$fail" -eq 0 ]; then
  echo "skill consistency: all invariants hold"
fi
exit "$fail"
