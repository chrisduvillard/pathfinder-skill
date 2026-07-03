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
#     naming a controlled action (self-merge, unattended, irreversible/external hard stops, credential) must
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
check_direction "irreversible/external hard stops" "blocked|remain|never|absolute" "irreversible/external hard stops stay blocked"
check_direction "credential" "separation|separate|isolat|disabled|no-verify|hookspath|no shared|exclude|blocked|stop" "credentials stay isolated or blocked" "credential_exposure|credential boundary"

# (C1/TR-B6) Existence guard for the window boundaries check_direction keys on. Anchoring the Family-A
# window on headings is only safe if the headings exist: a rename leaves `insec` permanently unset, so
# every check_direction above passes VACUOUSLY (fail-open) with the token intact. This makes the file
# self-guarding rather than silently relying on check-skill-consistency.sh's separate heading list.
# Keep this list in sync with the start/stop args passed to check_direction above.
for heading in "## Autonomous mode" "## Phase 7:"; do
  if awk -v h="$heading" 'index($0, h) == 1 { f = 1 } END { exit f ? 0 : 1 }' "$skill"; then
    echo "ok: Family-A window boundary present: \"$heading\""
  else
    err "Family-A window boundary heading missing or renamed: \"$heading\" (check_direction keys on it; the window would fail open — update both together)"
  fi
done

# (C1/SEC-1) The Stop-conditions autonomous carve-out (## Stop conditions section) restates the
# autonomous authorization limits but sits OUTSIDE the '## Autonomous mode'..'## Phase 7:' window, so
# the Family-A guards above never see it. That line is qualifier-saturated (many negations), so the
# same-line check_direction discipline cannot catch a partial inversion of it. Guard its two
# load-bearing commitments directly: self-merge must stay CONDITIONAL, and the trust-boundary /
# irreversible/external carve-out must stay "never waived". For this one sentence those phrases ARE the
# direction — an inversion removes them. Fails CLOSED if '## Stop conditions' is renamed (insec never
# sets -> token reads absent). Scope, stated honestly: a fluent reword preserving meaning with
# different words is out of scope, the same limit the rest of this harness declares.
check_carveout() {  # <token> <label>
  local token="$1" label="$2"
  if awk -v start="## Stop conditions" -v stop="## Style" -v token="$token" '
    BEGIN { token = tolower(token); found = 0 }
    index($0, start) == 1 { insec = 1 }
    insec && index($0, stop) == 1 { exit }
    insec && index(tolower($0), token) { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$skill"; then
    echo "ok: carve-out keeps \"$token\""
  else
    err "Stop-conditions autonomous carve-out lost its safety direction: \"$token\" missing — the carve-out may have been inverted (self-merge no longer conditional, or the boundary no longer \"never waived\")"
  fi
}

check_carveout "conditional self-merge" "carve-out: self-merge stays conditional"
check_carveout "irreversible/external hard-stop carve-out" "carve-out: irreversible/external floor stays never-waived"

# (C2/TR-B1) The whole-line check_direction above passes a self-merge line as long as SOME qualifier
# (never|conditional|default-deny|do not) appears ANYWHERE on it. Self-merge is stated across MANY
# in-window lines with different qualifiers, so inverting one clause while an unrelated qualifier word
# survives on the same line can still ship green — the documented multi-qualifier evasion, and the
# exact polarity-inversion class that reached main in v2.21.1/.2. Close that gap for the flagship
# default-deny control with a forbidden-inversion guard: no autonomous-window line may grant self-merge
# UNCONDITIONALLY. It fires only on the concrete phrasings a polarity inversion produces (unconditional
# / always / auto-approve / for-all-items / self-merge without a gate), which legitimate conditional
# text never uses — so it adds real coverage the whole-line check misses, with no false-red on valid
# rewordings. (The other three check_direction actions invert by removing their guarded literal, which
# the check-skill-consistency.sh presence guards already catch; extending this discipline to them is a
# scoped follow-on, not claimed here.)
check_no_unconditional_selfmerge() {
  if awk -v start="## Autonomous mode" -v stop="## Phase 7:" '
    index($0, start) == 1 { insec = 1 }
    insec && index($0, stop) == 1 { insec = 0 }
    insec {
      line = tolower($0)
      if (index(line, "self-merge") && \
          line ~ /unconditional|always self-merg|auto-?merge|auto-?approv|self-merge(s|d)? (all|any|every)|for all items|any item|self-merge[^.]*without (a )?(gate|approval|review|branch)/) {
        bad = 1
      }
    }
    END { exit bad ? 1 : 0 }
  ' "$skill"; then
    echo "ok: no unconditional self-merge grant in the autonomous window"
  else
    err "self-merge default-deny inverted: an autonomous-section line grants self-merge unconditionally (unconditional/always/auto/for-all/without-a-gate) — the default-deny guarantee has been loosened even though the whole-line qualifier check still passes"
  fi
}
check_no_unconditional_selfmerge

check_autonomy_token() {  # <token> <label>
  local token="$1" label="$2"
  if awk -v start="## Autonomous mode" -v stop="## Phase 7:" -v token="$token" '
    BEGIN { token = tolower(token); found = 0 }
    index($0, start) == 1 { insec = 1 }
    insec && index($0, stop) == 1 { insec = 0 }
    insec && index(tolower($0), token) { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$skill"; then
    echo "ok: $label"
  else
    err "$label: autonomous-section token \"$token\" missing or inverted"
  fi
}

check_autonomy_token "protected code areas are eligible with doctrine proof" "protected code areas require doctrine proof, not blanket exclusion"
check_autonomy_token "force-pushes" "irreversible/external hard stops keep force-pushes blocked"
check_autonomy_token "create a mission worktree before edits" "autonomous mode creates a mission worktree before edits"
check_autonomy_token "absent branch protection produces awaiting-review" "absent branch protection stays awaiting-review"

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
