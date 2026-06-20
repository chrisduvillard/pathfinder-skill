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
fail=0

err() { echo "::error::$*"; fail=1; }

for f in "$skill" "$funnel" "$goal" "$arts"; do
  [ -f "$f" ] || err "missing required file: $f"
done
if [ "$fail" -ne 0 ]; then exit "$fail"; fi

# (1) Reference-path existence: every references/<name>.md cited in SKILL.md
#     must exist on disk (catches a renamed reference whose citation was missed).
while IFS= read -r ref; do
  if [ -f "$root/skills/pathfinder/$ref" ]; then
    echo "ok: cited reference exists: $ref"
  else
    err "SKILL.md cites a missing reference path: $ref"
  fi
done < <(grep -oE 'references/[a-z0-9-]+\.md' "$skill" | sort -u)

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

# Phase 6 goal invariants (SKILL.md <-> goal-best-practices.md)
check_pair "3900"            "$goal" "3900-char goal budget"
check_pair "2.1.139"         "$goal" "Claude Code /goal version gate"
check_pair "untrusted data"  "$goal" "untrusted-data clause"

# (2b) Single-file presence: the Track B "How should I help?" entry-menu screen is
#      prompt-to-goal routing that lives only in SKILL.md (it is deliberately not
#      mirrored into the funnel template), so it cannot use check_pair. Assert it is
#      present so silently dropping the routing screen fails CI like any other drift.
if grep -qF -- "How should I help?" "$skill"; then
  echo "ok: Track B entry-menu screen present in SKILL.md"
else
  err "SKILL.md is missing the Track B \"How should I help?\" entry-menu screen"
fi

# (3) Artifact-contract parity: the set of pathfinder artifact filenames
#     (NN-*.md numbered files + *-scout.md briefs) must match between the
#     canonical SKILL.md list and artifact-structure.md. A file renamed or added
#     in one but not the other is the same drift class as the invariants above.
art_re='[0-9]{2}-[a-z-]+\.md|[a-z-]+-scout\.md'
skill_arts="$(grep -oE "$art_re" "$skill" | sort -u)"
struct_arts="$(grep -oE "$art_re" "$arts" | sort -u)"
if [ "$skill_arts" = "$struct_arts" ]; then
  echo "ok: artifact filename set matches (SKILL.md + artifact-structure.md)"
else
  err "artifact-contract drift: SKILL.md and artifact-structure.md list different artifact files"
  echo "  only in SKILL.md:            $(comm -23 <(printf '%s\n' "$skill_arts") <(printf '%s\n' "$struct_arts") | tr '\n' ' ')"
  echo "  only in artifact-structure:  $(comm -13 <(printf '%s\n' "$skill_arts") <(printf '%s\n' "$struct_arts") | tr '\n' ' ')"
fi

# (4) Markdown fence balance: the skill's value is dozens of hand-aligned
#     fenced screens; an odd count of ^``` lines means an unterminated block,
#     which corrupts rendering of the funnel/goal screens. Assert each skill
#     markdown file closes every fence it opens.
for f in "$skill" "$root"/skills/pathfinder/references/*.md; do
  n=$(grep -cE '^```' "$f" || true)
  if [ $((n % 2)) -eq 0 ]; then
    echo "ok: balanced code fences ($n) in $(basename "$f")"
  else
    err "unbalanced code fence in $f: $n \`\`\` lines (odd = an unterminated block)"
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "skill consistency: all invariants hold"
fi
exit "$fail"
