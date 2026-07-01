# TR-1 Behavioral Invariant Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, agent-free CI validator that asserts the *direction* of Pathfinder's autonomous-mode safety rules and the *escape-completeness* of its decision screens, catching the polarity-inversion-with-token-intact class that has reached `main` twice and was caught only by manual dogfooding.

**Architecture:** One new script, `scripts/check-skill-behavior.sh`, reads `skills/pathfinder/SKILL.md` as data only. Family A scopes to the `## Autonomous mode`..`## Phase 7:` window and asserts each line naming a controlled action (self-merge, unattended, dangerous categories, credential) also carries a governing qualifier on the same line. Family B walks fenced blocks and asserts each decision screen (contains `Agent recommends:`) carries its `None of these` escape unless allowlisted. Every invariant is proven by an adversarial fixture added to the existing `scripts/test-validators.sh` meta-suite. Wired into `check-all.sh` and `manifests.yml`, shipped as patch release v2.21.9.

**Tech Stack:** POSIX `bash` + `awk` (no `jq`, no `grep -P`, no `grep -i`+`-F` combo — matches the repo's portability guard). Meta-tests reuse the `newroot()` / `assert_*` fixture harness in `test-validators.sh`.

## Global Constraints

- Commit author is `Chris <duvillard.c@gmail.com>` on every commit (use `git -c user.name="Chris" -c user.email="duvillard.c@gmail.com" commit`).
- Work on branch `feat/tr1-behavioral-invariant-harness` (already checked out; the design spec is already committed there).
- New/edited shell must stay portable: no `grep -P` / `--perl-regexp`, no `grep -i`+`-F` in one flag group. Use `awk index(tolower())` for case-insensitive literals. `check-skill-behavior.sh` uses awk only (no `grep`).
- The harness reads SKILL.md as untrusted data; it never executes it and never runs repo-defined commands.
- Do NOT edit production spec files (`skills/pathfinder/SKILL.md` or `references/*.md`). If a golden run fails, that is either a qualifier-set gap (widen the set) or a real current defect (stop and report it as a finding) — not a reason to edit the spec inside this plan.
- Run the full local suite on Windows with `MSYS_NO_PATHCONV=1` (required by `check-manifests.sh`'s jq path handling; harmless elsewhere): `MSYS_NO_PATHCONV=1 bash scripts/check-all.sh .`
- Version consistency is CI-enforced: `VERSION.md` `Version:` line, `.claude-plugin/plugin.json`, and `.codex-plugin/plugin.json` must all read the same version, and `VERSION.md` must contain a `Changes in v<version>:` entry for it.
- `scripts/**` and `.github/**` are maintainer-review protected; this ships as a normal branch → PR → review → CI → squash-merge → auto-release.

---

### Task 1: Family A — safety-direction invariants (new script + fixtures)

**Files:**
- Create: `scripts/check-skill-behavior.sh`
- Modify: `scripts/test-validators.sh` (add `csb` runner, `assert_pass_b`/`assert_catch_b`, and Family A fixtures before the final summary block)

**Interfaces:**
- Produces: `scripts/check-skill-behavior.sh` — invoked as `bash scripts/check-skill-behavior.sh [ROOT]` (ROOT default `.`); exit 0 when all invariants hold, non-zero otherwise; emits `::error::` lines on failure and `skill behavior: all invariants hold` on success.
- Produces (in `test-validators.sh`): `csb <root>` runs the harness capturing stdout+stderr; `assert_pass_b <root> <label>`; `assert_catch_b <root> <regex> <label>` — mirrors of the existing `csc`/`assert_pass`/`assert_catch`, targeting the behavior harness instead of check-skill-consistency.

- [ ] **Step 1: Add the behavior-harness meta-test helpers and Family A fixtures to `test-validators.sh`**

Open `scripts/test-validators.sh`. Immediately BEFORE the final summary block (the lines `if [ "$fail" -eq 0 ]; then` / `echo "test-validators: all parser meta-tests pass"`), insert:

```bash
# ---- Behavioral invariant harness (check-skill-behavior.sh) ----
skillbeh="$here/scripts/check-skill-behavior.sh"
csb() { MSYS_NO_PATHCONV=1 bash "$skillbeh" "$1" 2>&1; }
assert_pass_b() {  # <root> <label>
  local out ec
  out="$(csb "$1")"; ec=$?
  if [ "$ec" -eq 0 ]; then ok "$2"; else bad "$2 (exit=$ec, expected 0)"; printf '%s\n' "$out" | tail -4; fi
}
assert_catch_b() {  # <root> <regex> <label>
  local out ec
  out="$(csb "$1")"; ec=$?
  if [ "$ec" -ne 0 ] && printf '%s' "$out" | grep -Eq "$2"; then
    ok "$3"
  else
    bad "$3 (exit=$ec; expected non-zero output matching /$2/)"
  fi
}

echo "== behavior baseline: a clean copy passes check-skill-behavior =="
assert_pass_b "$(newroot)" "baseline: clean tree passes check-skill-behavior"

echo "== behavior 1: self-merge must carry a gating qualifier (the loosened-gate class) =="
# Drop the qualifier from the core authorization grant while keeping the token. This is TR-1's
# literal acceptance test: a safety-token-preserving-but-logic-inverting change must be caught.
R="$(newroot)"
sed -i 's/and a conditional self-merge/and a self-merge/' "$R/skills/pathfinder/SKILL.md"
assert_catch_b "$R" "self-merge|governing qualifier|loosened gate" "self-merge polarity: dropping the qualifier (token intact) is caught"

echo "== behavior 2: 'unattended' must carry a negation =="
# Remove the sole negation attached to an 'unattended' mention; the line then permits what it forbade.
R="$(newroot)"
sed -i 's/a charter Never unattended category/a charter always-unattended category/' "$R/skills/pathfinder/SKILL.md"
assert_catch_b "$R" "unattended|governing qualifier" "unattended inversion: removing the negation is caught"
```

- [ ] **Step 2: Run the meta-suite and watch Family A fail (script does not exist yet)**

Run: `MSYS_NO_PATHCONV=1 bash scripts/test-validators.sh .`
Expected: FAIL. The three new assertions error because `scripts/check-skill-behavior.sh` does not exist (`csb` runs `bash` on a missing file → non-zero, and the baseline `assert_pass_b` expects exit 0). Output includes `::error::baseline: clean tree passes check-skill-behavior ...`.

- [ ] **Step 3: Create `scripts/check-skill-behavior.sh` with Family A**

Create `scripts/check-skill-behavior.sh` with exactly this content:

```bash
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
check_direction "credential" "separation|separate|isolat|disabled|no-verify|hookspath|no shared" "credentials stay isolated" "credential_exposure"

if [ "$fail" -eq 0 ]; then
  echo "skill behavior: all invariants hold"
fi
exit "$fail"
```

- [ ] **Step 4: Run the meta-suite and watch Family A pass**

Run: `MSYS_NO_PATHCONV=1 bash scripts/test-validators.sh .`
Expected: PASS. `ok: baseline: clean tree passes check-skill-behavior`, `ok: self-merge polarity: ...`, `ok: unattended inversion: ...`, and finally `test-validators: all parser meta-tests pass`.

- [ ] **Step 5: Run the harness against the real tree (the golden must pass)**

Run: `bash scripts/check-skill-behavior.sh .`
Expected: four `ok:` lines then `skill behavior: all invariants hold`, exit 0.
If instead a `check_direction` fails on the real tree, do NOT edit SKILL.md: confirm whether the flagged line is (a) a qualifier the set is missing — add the synonym to that check's regex and re-run — or (b) a genuinely qualifier-less safety statement, which is a real finding to report and stop on.

- [ ] **Step 6: Commit**

```bash
git add scripts/check-skill-behavior.sh scripts/test-validators.sh
git -c user.name="Chris" -c user.email="duvillard.c@gmail.com" commit -m "feat: add safety-direction invariant harness (TR-1 Family A)"
```

---

### Task 2: Family B — screen-escape invariants

**Files:**
- Modify: `scripts/check-skill-behavior.sh` (add `check_screens` + its call before the summary block)
- Modify: `scripts/test-validators.sh` (add the screen-escape fixture)

**Interfaces:**
- Consumes: `scripts/check-skill-behavior.sh` from Task 1 (adds a function; keeps the same CLI and exit contract).
- Produces: `check_screens` — asserts every fenced block containing `Agent recommends:` also contains `None of these`, unless the block contains one of the allowlist signatures.

- [ ] **Step 1: Add the screen-escape fixture to `test-validators.sh`**

In `scripts/test-validators.sh`, immediately AFTER the `behavior 2` block added in Task 1 (after its `assert_catch_b` line) and still before the final summary block, insert:

```bash
echo "== behavior 3: a decision screen must carry its 'None of these' escape =="
# Delete the first "None of these" line, orphaning one non-exempt decision screen from its escape.
R="$(newroot)"
awk 'BEGIN{d=0} /None of these/ && d==0 {d=1; next} {print}' \
  "$R/skills/pathfinder/SKILL.md" > "$R/skills/pathfinder/SKILL.md.new" \
  && mv "$R/skills/pathfinder/SKILL.md.new" "$R/skills/pathfinder/SKILL.md"
assert_catch_b "$R" "screen-escape|None of these|allowlist" "screen-escape: dropping a screen's escape is caught"
```

- [ ] **Step 2: Run the meta-suite and watch Family B fail (no screen check yet)**

Run: `MSYS_NO_PATHCONV=1 bash scripts/test-validators.sh .`
Expected: FAIL on `behavior 3` only. The harness has no screen check yet, so removing an escape still exits 0; `assert_catch_b` reports `::error::screen-escape: dropping a screen's escape is caught (exit=0; expected non-zero ...)`.

- [ ] **Step 3: Add `check_screens` to `scripts/check-skill-behavior.sh`**

In `scripts/check-skill-behavior.sh`, insert the following BETWEEN the last `check_direction ... "credential_exposure"` line and the `if [ "$fail" -eq 0 ]; then` summary block:

```bash
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
```

- [ ] **Step 4: Run the meta-suite and watch everything pass**

Run: `MSYS_NO_PATHCONV=1 bash scripts/test-validators.sh .`
Expected: PASS, including `ok: screen-escape: dropping a screen's escape is caught` and the unchanged `ok: baseline: clean tree passes check-skill-behavior`, ending `test-validators: all parser meta-tests pass`.

- [ ] **Step 5: Run the harness against the real tree (golden still passes with Family B)**

Run: `bash scripts/check-skill-behavior.sh .`
Expected: the four Family A `ok:` lines, then `ok: every non-exempt decision screen carries its "None of these" escape`, then `skill behavior: all invariants hold`, exit 0.
If a real screen is flagged: confirm it is genuinely a decision menu missing its escape (a real finding — stop and report) versus a deliberately exempt screen the allowlist is missing (add its distinctive signature to the `allow` split and re-run).

- [ ] **Step 6: Commit**

```bash
git add scripts/check-skill-behavior.sh scripts/test-validators.sh
git -c user.name="Chris" -c user.email="duvillard.c@gmail.com" commit -m "feat: add screen-escape invariant (TR-1 Family B)"
```

---

### Task 3: Wire into check-all, CI, and CONTRIBUTING

**Files:**
- Modify: `scripts/check-all.sh` (after the skill-consistency `run_check`)
- Modify: `.github/workflows/manifests.yml` (after the skill-consistency step)
- Modify: `CONTRIBUTING.md` (add to the local-checks block and the maintainer guidance)

**Interfaces:**
- Consumes: `scripts/check-skill-behavior.sh` from Tasks 1-2.

- [ ] **Step 1: Wire into `scripts/check-all.sh`**

Replace:

```bash
run_check "skill consistency" bash "$root/scripts/check-skill-consistency.sh" "$root"
run_check "manifest consistency" bash "$root/scripts/check-manifests.sh" "$root"
```

with:

```bash
run_check "skill consistency" bash "$root/scripts/check-skill-consistency.sh" "$root"
run_check "skill behavior invariants" bash "$root/scripts/check-skill-behavior.sh" "$root"
run_check "manifest consistency" bash "$root/scripts/check-manifests.sh" "$root"
```

- [ ] **Step 2: Wire into `.github/workflows/manifests.yml`**

Replace:

```yaml
      - name: Check SKILL.md <-> reference-template consistency
        run: bash scripts/check-skill-consistency.sh

      - name: Check validation/release portability
        run: bash scripts/check-portability.sh
```

with:

```yaml
      - name: Check SKILL.md <-> reference-template consistency
        run: bash scripts/check-skill-consistency.sh

      - name: Check SKILL.md behavioral invariants
        run: bash scripts/check-skill-behavior.sh

      - name: Check validation/release portability
        run: bash scripts/check-portability.sh
```

- [ ] **Step 3: Add the script to the CONTRIBUTING local-checks block**

In `CONTRIBUTING.md`, replace:

```bash
bash scripts/check-skill-consistency.sh   # SKILL.md <-> references drift guard
bash scripts/check-manifests.sh           # JSON validity + version parity + marketplace rules
```

with:

```bash
bash scripts/check-skill-consistency.sh   # SKILL.md <-> references drift guard
bash scripts/check-skill-behavior.sh      # SKILL.md safety-direction + screen-escape invariants
bash scripts/check-manifests.sh           # JSON validity + version parity + marketplace rules
```

- [ ] **Step 4: Add the maintainer guidance note**

In `CONTRIBUTING.md`, replace:

```markdown
  file, and add or update the matching `check_pair` or section guard in
  `scripts/check-skill-consistency.sh`, or CI will fail.
- Do not commit `.agent-work/`, `.agent-workspace/`, secrets, local caches, or
```

with:

```markdown
  file, and add or update the matching `check_pair` or section guard in
  `scripts/check-skill-consistency.sh`, or CI will fail.
- When you add or change an autonomous-mode safety rule or a decision screen, update
  `scripts/check-skill-behavior.sh` too: a new controlled action needs a qualifier-set row so a
  loosened gate with the token intact fails CI, and a new decision screen needs its `None of these`
  escape or an entry on the exempt allowlist. Prove it with a fixture in `scripts/test-validators.sh`.
- Do not commit `.agent-work/`, `.agent-workspace/`, secrets, local caches, or
```

- [ ] **Step 5: Run the full local suite**

Run: `MSYS_NO_PATHCONV=1 bash scripts/check-all.sh .`
Expected: every `==>` check reports `ok:`, including `ok: skill behavior invariants`, ending `check-all: all checks pass`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/check-all.sh .github/workflows/manifests.yml CONTRIBUTING.md
git -c user.name="Chris" -c user.email="duvillard.c@gmail.com" commit -m "ci: run skill-behavior harness in check-all and manifests workflow"
```

---

### Task 4: Release prep — v2.21.9

**Files:**
- Modify: `VERSION.md` (bump `Version:` + add changelog entry)
- Modify: `.claude-plugin/plugin.json` (`version`)
- Modify: `.codex-plugin/plugin.json` (`version`)

**Interfaces:**
- Consumes: the completed harness + wiring from Tasks 1-3.

- [ ] **Step 1: Bump the version in `VERSION.md`**

Replace `Version: 2.21.8` with `Version: 2.21.9`.

- [ ] **Step 2: Add the changelog entry in `VERSION.md`**

Directly above the line `Changes in v2.21.8:`, insert:

```markdown
Changes in v2.21.9:
- Added a behavioral invariant harness `scripts/check-skill-behavior.sh` (TR-1), wired into `check-all.sh` and CI, that asserts DIRECTION rather than token presence — closing the class where an autonomous-mode safety gate keeps its token but has its rule loosened or inverted (the class that reached `main` in v2.21.1/.2 and was caught only by manual dogfooding). Family A: inside the `## Autonomous mode` window, every line naming a controlled action (self-merge, unattended, dangerous categories, credential) must carry a governing qualifier on the same line. Family B: every fenced decision screen (contains `Agent recommends:`) must carry its `None of these` escape unless it is an allowlisted fixed/exception screen. Each invariant is proven by an adversarial fixture in `scripts/test-validators.sh` (a qualifier-dropping self-merge reword and a dropped screen escape are both caught; a clean tree passes). Design and plan in `docs/superpowers/`.

```

- [ ] **Step 3: Bump both plugin manifests**

In `.claude-plugin/plugin.json`, change `"version": "2.21.8"` to `"version": "2.21.9"`.
In `.codex-plugin/plugin.json`, change `"version": "2.21.8"` to `"version": "2.21.9"`.

- [ ] **Step 4: Run the full local suite at the new version**

Run: `MSYS_NO_PATHCONV=1 bash scripts/check-all.sh .`
Expected: `check-all: all checks pass`, exit 0. In particular `manifest consistency` confirms `VERSION.md` (2.21.9), both `plugin.json` (2.21.9), and the `Changes in v2.21.9:` entry all agree.

- [ ] **Step 5: Commit**

```bash
git add VERSION.md .claude-plugin/plugin.json .codex-plugin/plugin.json
git -c user.name="Chris" -c user.email="duvillard.c@gmail.com" commit -m "release: v2.21.9 — behavioral invariant harness (TR-1)"
```

- [ ] **Step 6: Push and open the PR**

```bash
git push -u origin feat/tr1-behavioral-invariant-harness
gh pr create --fill --base main
```

Then run an independent code review (`feature-dev:code-reviewer`) on the diff, address any high-confidence findings, wait for CI green, and hand the merge to the user per the repo's merge flow (self-merge to the default branch is not done autonomously; the user merges, which auto-cuts the v2.21.9 release).

---

## Notes for the implementer

- **Why same-line, not ±1 line:** every governing qualifier in the current autonomous section sits on the same logical line as its controlled action (SKILL.md is one-line-per-paragraph). Same-line is both sufficient for the golden and stricter — a qualifier on an adjacent unrelated line cannot mask a local inversion. This is the deliberate tightening of the spec's "±1 proximity" wording; it honors the spec's stated goal that "an unrelated distant qualifier can't satisfy a gate."
- **Qualifier sets are validated against the current SKILL.md.** They are generous by design (synonyms) to avoid tripping legitimate rewordings, but tight enough to omit weak words: `awaiting-review` was deliberately left OUT of the self-merge set (it appears on lines that also mention self-merge, so it would immunize them), and bare `not` was left out of the unattended set for the same reason.
- **Allowlist is exact, not guessed.** The four exempt screens were confirmed by extracting every fenced block containing `Agent recommends:` and checking which lack `None of these`. The Track-B "How should I help?" menu and the `/pathfinder` entry chooser are NOT in the allowlist because they use `Recommendation: 🟢`, not `Agent recommends:`, so they never trigger the check.
