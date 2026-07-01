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

# Family B: screen-escape. Walk fenced blocks honoring fence length (3- vs 4-backtick nesting), the
# same tracker check-skill-consistency.sh uses. A block that presents a decision menu ("Agent
# recommends:") must contain its "None of these" escape, unless it is one of the deliberately exempt
# fixed/exception screens: the Phase 5 mode-selection preamble, the all-candidates-rejected screen,
# the Explore full-surface map, and the Phase 6 recognition-first goal contract. Keep this allowlist
# in sync with the funnel's fixed-menu rules.
check_screens() {
  if awk '
    BEGIN {
      na = split("I mapped this repo and found|Verification rejected all candidates|Full surface map|Here is the /goal I assembled from your answers", allow, "|")
    }
    {
      n = 0; while (substr($0, n + 1, 1) == "`") n++
      if (n >= 3) {
        rest = substr($0, n + 1); sub(/[ \t]+$/, "", rest)
        if (depth == 0) { depth = 1; openlen = n; block = ""; bstart = NR; next }
        if (rest == "" && n >= openlen) {
          if (index(block, "Agent recommends:") && !index(block, "None of these")) {
            exempt = 0
            for (i = 1; i <= na; i++) if (index(block, allow[i])) exempt = 1
            if (!exempt) { bad = 1; printf "  decision screen opened at line %d has no \"None of these\" escape and is not allowlisted\n", bstart }
          }
          depth = 0; next
        }
        block = block $0 "\n"; next
      }
      if (depth) block = block $0 "\n"
    }
    END { exit bad ? 1 : 0 }
  ' "$skill"; then
    echo "ok: every non-exempt decision screen carries its \"None of these\" escape"
  else
    err "screen-escape drift: a fenced decision screen (contains \"Agent recommends:\") is missing its \"None of these\" escape and is not on the exempt allowlist"
  fi
}

check_screens

if [ "$fail" -eq 0 ]; then
  echo "skill behavior: all invariants hold"
fi
exit "$fail"
