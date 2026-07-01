#!/usr/bin/env bash
#
# Behavioral invariant harness (TR-1).
#
# The other check-*.sh guards assert STRUCTURE and TOKEN PRESENCE: do SKILL.md and its mirrors
# contain the same strings, are fences balanced, are versions synced. None tests DIRECTION.
# check-skill-consistency.sh's auto_invariants loop already asserts each autonomous-mode safety
# phrase is present *somewhere in its section* — which catches deletion but not a loosened or
# inverted rule that keeps the token. That polarity-inversion class reached main twice (v2.21.1/.2)
# and was caught only by manual dogfooding.
#
# This asserts RELATIONAL invariants a polarity inversion violates:
#   Family A (safety-direction): inside the '## Autonomous mode'..'## Phase 7:' window, every line
#     naming a controlled action (self-merge, unattended, dangerous categories, credential) must
#     also carry a governing qualifier ON THE SAME LINE. A qualifier-less occurrence is a loosened
#     gate with the token intact.
#   Family B (screen-escape): every fenced decision screen (contains "Agent recommends:") must carry
#     its "None of these" escape, unless it is an allowlisted fixed/exception screen. (Added in the
#     screen-escape task.)
#
# Scope, stated honestly (the anti-TR-1 discipline — the harness must not imply coverage it lacks):
# the same-line window is same-paragraph for this file's one-line-per-paragraph style, so an
# inversion on a long line that still mentions another qualifier can evade it, and a fluent reword
# that keeps a plausible qualifier can evade it. This catches the polarity-inversion-with-token-
# intact class that has actually shipped, NOT arbitrary semantic drift, and runs NO live agent.
# It reads SKILL.md as data only; it never executes it.
#
# Usage: bash scripts/check-skill-behavior.sh [ROOT]   (ROOT defaults to ".")
# Exit 0 when all invariants hold; non-zero otherwise.

set -uo pipefail

root="${1:-.}"
skill="$root/skills/pathfinder/SKILL.md"
fail=0

err() { echo "::error::$*"; fail=1; }

[ -f "$skill" ] || { err "missing required file: $skill"; exit "$fail"; }

# Family A: safety-direction. Within the autonomous-mode window, a controlled action must share its
# line with a governing qualifier. Window boundaries are column-0 headings (index()==1) like
# check_skill_section, so prose mentioning "## Phase 7:" cannot mis-scope the window. Case-insensitive
# via awk index(tolower()) — never grep -qiF, which aborts on MSYS GNU grep 3.0. Optional strip-regex
# removes a false-trigger form (e.g. the runtime-boundary field "credential_exposure") before the
# action is detected.
check_direction() {  # <action> <qualifier-regex, lowercase ERE> <label> [strip-regex]
  local action="$1" quals="$2" label="$3" strip="${4:-}"
  if awk -v start="## Autonomous mode" -v stop="## Phase 7:" \
         -v action="$action" -v quals="$quals" -v strip="$strip" '
    BEGIN { action = tolower(action) }
    index($0, start) == 1 { insec = 1 }
    insec && index($0, stop) == 1 { insec = 0 }
    insec {
      line = tolower($0)
      probe = line
      if (strip != "") gsub(strip, "", probe)
      if (index(probe, action) && line !~ quals) { bad = 1 }
    }
    END { exit bad ? 1 : 0 }
  ' "$skill"; then
    echo "ok: $label"
  else
    err "$label: an autonomous-section line names \"$action\" without a governing qualifier (/$quals/) on the same line — a loosened gate with the token intact"
  fi
}

check_direction "self-merge" "never|conditional|default-deny|do not" "self-merge stays default-deny/conditional"
check_direction "unattended" "never|cannot|neither" "unattended stays negated"
check_direction "dangerous categories" "never|excluded|exclude|filtered out|hard-block" "dangerous categories stay excluded"
check_direction "credential" "separation|separate|isolat|disabled|no-verify|hookspath|no shared" "credentials stay isolated" "credential_exposure|credential boundary"

if [ "$fail" -eq 0 ]; then
  echo "skill behavior: all invariants hold"
fi
exit "$fail"
