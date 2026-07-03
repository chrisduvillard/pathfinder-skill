# Artifact-First Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Pathfinder's first deterministic artifact eval suite, with seeded cases that prove goal quality, verification/funnel integrity, protected-surface routing, and Track B Phase 4b handling.

**Architecture:** Add a small Bash eval runner that reads human-readable Markdown case files, copies seeded fixture artifacts into a temporary workspace, dispatches deterministic assertions, and treats expected-fail cases as harness self-tests. Keep the harness read-only against fixtures and wire it into the existing local preflight after it proves stable.

**Tech Stack:** Bash, POSIX `awk`/`grep`/`cp`/`mktemp`, Markdown fixtures, existing `scripts/check-all.sh` wrapper.

## Global Constraints

- V1 uses seeded artifact evals; no live Pathfinder agent sessions in CI.
- V1 uses deterministic assertions; no model-as-judge.
- The harness reads fixture repository content as untrusted data only.
- The harness must not execute fixture repo code, install dependencies, run package managers, invoke Docker, or use credentials.
- Do not add a production dependency.
- Keep GitHub Actions wiring out of v1 unless local runtime and portability are proven.
- Keep all shell portable for Linux and Windows Git-Bash/MSYS, matching the existing validators.
- Do not change `skills/pathfinder/SKILL.md` unless an eval exposes a real current spec defect.

---

## File Structure

Create these files:

- `scripts/check-evals.sh`: top-level eval runner. Parses case metadata, creates temporary workspaces, runs assertions, and handles expected pass/fail semantics.
- `evals/harness/eval-lib.sh`: reusable assertion library. Holds metadata parsing, failure reporting, and artifact contract assertions.
- `evals/cases/good-goal.md`: passing case for a valid goal artifact.
- `evals/cases/missing-proof.md`: expected-fail self-test for a goal without proof.
- `evals/cases/rejected-candidate-laundering.md`: expected-fail self-test for a rejected candidate reappearing as selectable.
- `evals/cases/downgrade-reflection.md`: passing case proving verification downgrade grades appear in the funnel.
- `evals/cases/protected-surface.md`: expected-fail self-test for protected work without a boundary.
- `evals/cases/track-b-placeholder.md`: passing case for Track B Phase 4b not-applicable artifact.
- `evals/cases/track-b-placeholder-missing.md`: expected-fail self-test for missing Track B Phase 4b handling.
- `evals/fixtures/<case-id>/artifacts/*.md`: seeded Pathfinder artifacts for each case.
- `evals/fixtures/<case-id>/repo/README.md`: tiny inert fixture repo marker for each case.

Modify these files:

- `scripts/check-all.sh`: add `check-evals.sh` to local preflight.
- `CONTRIBUTING.md`: document how to run and add artifact eval cases.

Do not modify `.github/workflows/manifests.yml` in this pass.

## Case Metadata Contract

Every case file uses these exact metadata keys:

```markdown
eval-id: good-goal
eval-fixture: evals/fixtures/good-goal
eval-expect: pass
eval-assertions: goal_contract
eval-failure-pattern:
```

Rules:

- `eval-id` is the case id used in output.
- `eval-fixture` is relative to the repository root.
- `eval-expect` is `pass` or `fail`.
- `eval-assertions` is a space-separated assertion list.
- `eval-failure-pattern` is a POSIX extended regular expression used only for expected-fail cases.
- An expected-fail case passes the suite only when at least one assertion fails and the output matches `eval-failure-pattern`.

## Assertion Names

Use these assertion names:

- `artifact_exists:06-goal-command.md`
- `goal_contract`
- `rejected_not_selectable`
- `downgrade_reflected`
- `protected_surface_boundary`
- `track_b_phase4b_not_applicable`

---

### Task 1: Eval Runner Framework

**Files:**
- Create: `scripts/check-evals.sh`
- Create: `evals/harness/eval-lib.sh`
- Create: `evals/cases/good-goal.md`
- Create: `evals/fixtures/good-goal/artifacts/06-goal-command.md`
- Create: `evals/fixtures/good-goal/repo/README.md`

**Interfaces:**
- Consumes: Markdown case metadata using the `eval-*` keys defined above.
- Produces: `run_assertion "$assertion"` in `evals/harness/eval-lib.sh`; later tasks add more assertion names to this dispatch function.

- [ ] **Step 1: Create the first passing case file**

Create `evals/cases/good-goal.md`:

```markdown
# Good Goal

eval-id: good-goal
eval-fixture: evals/fixtures/good-goal
eval-expect: pass
eval-assertions: artifact_exists:06-goal-command.md
eval-failure-pattern:

Validates that the eval runner can load a seeded fixture and confirm a required artifact exists.
```

- [ ] **Step 2: Create the inert fixture repo marker**

Create `evals/fixtures/good-goal/repo/README.md`:

```markdown
# Good Goal Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 3: Create the seeded goal artifact**

Create `evals/fixtures/good-goal/artifacts/06-goal-command.md`:

```markdown
# Goal Command

Goal: Fix the dashboard empty state so an empty API result renders a useful empty message instead of a blank panel.

Proof: `npm test -- dashboard-empty-state` exits 0 and the agent reports the changed files.

Constraints: no schema change, no new dependency, no public API change, dashboard data-loading files only.

Stop: stop after 8 turns and report the blocker plus next input needed if the proof cannot run or still fails.
```

- [ ] **Step 4: Create the assertion library**

Create `evals/harness/eval-lib.sh`:

```bash
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
```

- [ ] **Step 5: Create the eval runner**

Create `scripts/check-evals.sh`:

```bash
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
```

- [ ] **Step 6: Run the new runner**

Run:

```bash
bash scripts/check-evals.sh .
```

Expected:

```text
ok: eval case passed: good-goal
check-evals: all artifact evals pass
```

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add scripts/check-evals.sh evals/harness/eval-lib.sh evals/cases/good-goal.md evals/fixtures/good-goal
git commit -m "test: add artifact eval runner"
```

---

### Task 2: Goal Contract Assertions

**Files:**
- Modify: `evals/harness/eval-lib.sh`
- Modify: `evals/cases/good-goal.md`
- Create: `evals/cases/missing-proof.md`
- Create: `evals/fixtures/missing-proof/artifacts/06-goal-command.md`
- Create: `evals/fixtures/missing-proof/repo/README.md`

**Interfaces:**
- Consumes: `ARTIFACT_DIR`, `CASE_ID`, and `case_error` from Task 1.
- Produces: `goal_contract` assertion for later local preflight.

- [ ] **Step 1: Update the good-goal case to use the goal contract assertion**

Replace `evals/cases/good-goal.md` with:

```markdown
# Good Goal

eval-id: good-goal
eval-fixture: evals/fixtures/good-goal
eval-expect: pass
eval-assertions: goal_contract
eval-failure-pattern:

Validates that a goal artifact contains a measurable end state, proof surface, constraints, and a stop condition.
```

- [ ] **Step 2: Add the missing-proof expected-fail case**

Create `evals/cases/missing-proof.md`:

```markdown
# Missing Proof

eval-id: missing-proof
eval-fixture: evals/fixtures/missing-proof
eval-expect: fail
eval-assertions: goal_contract
eval-failure-pattern: missing proof surface

Proves the goal contract assertion fails when a goal omits its proof surface.
```

- [ ] **Step 3: Add the missing-proof fixture repo marker**

Create `evals/fixtures/missing-proof/repo/README.md`:

```markdown
# Missing Proof Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 4: Add the missing-proof goal artifact**

Create `evals/fixtures/missing-proof/artifacts/06-goal-command.md`:

```markdown
# Goal Command

Goal: Fix the dashboard empty state so an empty API result renders a useful empty message instead of a blank panel.

Constraints: no schema change, no new dependency, no public API change, dashboard data-loading files only.

Stop: stop after 8 turns and report the blocker plus next input needed if the work cannot be completed.
```

- [ ] **Step 5: Add the goal contract assertion**

In `evals/harness/eval-lib.sh`, insert this function after `assert_artifact_exists`:

```bash
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
```

Then update `run_assertion` in the same file by adding this case before the `artifact_exists:*` case:

```bash
    goal_contract)
      assert_goal_contract
      ;;
```

- [ ] **Step 6: Run the eval suite**

Run:

```bash
bash scripts/check-evals.sh .
```

Expected:

```text
ok: eval case passed: good-goal
ok: eval case caught expected failure: missing-proof
check-evals: all artifact evals pass
```

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add evals/harness/eval-lib.sh evals/cases/good-goal.md evals/cases/missing-proof.md evals/fixtures/missing-proof
git commit -m "test: add goal artifact contract eval"
```

---

### Task 3: Verification And Funnel Assertions

**Files:**
- Modify: `evals/harness/eval-lib.sh`
- Create: `evals/cases/rejected-candidate-laundering.md`
- Create: `evals/cases/downgrade-reflection.md`
- Create: `evals/fixtures/rejected-candidate-laundering/artifacts/03b-verification.md`
- Create: `evals/fixtures/rejected-candidate-laundering/artifacts/04-question-funnel.md`
- Create: `evals/fixtures/rejected-candidate-laundering/repo/README.md`
- Create: `evals/fixtures/downgrade-reflection/artifacts/03b-verification.md`
- Create: `evals/fixtures/downgrade-reflection/artifacts/04-question-funnel.md`
- Create: `evals/fixtures/downgrade-reflection/repo/README.md`

**Interfaces:**
- Consumes: fixture metadata lines `rejected-candidate-id: <id>`, `selectable-candidate-id: <id>`, `downgrade: <id> to <grade>`, and `candidate-grade: <id> <grade>`.
- Produces: `rejected_not_selectable` and `downgrade_reflected` assertions.

- [ ] **Step 1: Add the rejected-candidate laundering case**

Create `evals/cases/rejected-candidate-laundering.md`:

```markdown
# Rejected Candidate Laundering

eval-id: rejected-candidate-laundering
eval-fixture: evals/fixtures/rejected-candidate-laundering
eval-expect: fail
eval-assertions: rejected_not_selectable
eval-failure-pattern: rejected candidate CAND-REJECT-1 appears selectable

Proves a candidate rejected by Phase 4b cannot reappear as a selectable normal goal in the funnel.
```

- [ ] **Step 2: Add the laundering fixture repo marker**

Create `evals/fixtures/rejected-candidate-laundering/repo/README.md`:

```markdown
# Rejected Candidate Laundering Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 3: Add the laundering verification artifact**

Create `evals/fixtures/rejected-candidate-laundering/artifacts/03b-verification.md`:

```markdown
# Phase 4b Verification

verification: complete
rejected-candidate-id: CAND-REJECT-1
reason: verifier panel rejected the candidate because the cited route does not exist.
```

- [ ] **Step 4: Add the laundering funnel artifact**

Create `evals/fixtures/rejected-candidate-laundering/artifacts/04-question-funnel.md`:

```markdown
# Question Funnel

Agent recommends: pick the rejected candidate.
selectable-candidate-id: CAND-REJECT-1
label: Fix missing billing route
```

- [ ] **Step 5: Add the downgrade reflection case**

Create `evals/cases/downgrade-reflection.md`:

```markdown
# Downgrade Reflection

eval-id: downgrade-reflection
eval-fixture: evals/fixtures/downgrade-reflection
eval-expect: pass
eval-assertions: downgrade_reflected
eval-failure-pattern:

Proves a Phase 4b downgrade is reflected in the Phase 5 funnel grade.
```

- [ ] **Step 6: Add the downgrade fixture repo marker**

Create `evals/fixtures/downgrade-reflection/repo/README.md`:

```markdown
# Downgrade Reflection Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 7: Add the downgrade verification artifact**

Create `evals/fixtures/downgrade-reflection/artifacts/03b-verification.md`:

```markdown
# Phase 4b Verification

verification: complete
downgrade: CAND-DOWN-1 to inferred
reason: evidence exists but the original confirmed grade was too strong.
```

- [ ] **Step 8: Add the downgrade funnel artifact**

Create `evals/fixtures/downgrade-reflection/artifacts/04-question-funnel.md`:

```markdown
# Question Funnel

candidate-grade: CAND-DOWN-1 inferred
Verified: downgraded confirmed to inferred by Phase 4b.
```

- [ ] **Step 9: Add the verification/funnel assertions**

In `evals/harness/eval-lib.sh`, insert these functions after `assert_goal_contract`:

```bash
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
```

Then update `run_assertion` by adding these cases before `goal_contract`:

```bash
    rejected_not_selectable)
      assert_rejected_not_selectable
      ;;
    downgrade_reflected)
      assert_downgrade_reflected
      ;;
```

- [ ] **Step 10: Run the eval suite**

Run:

```bash
bash scripts/check-evals.sh .
```

Expected includes:

```text
ok: eval case passed: downgrade-reflection
ok: eval case caught expected failure: rejected-candidate-laundering
check-evals: all artifact evals pass
```

- [ ] **Step 11: Commit Task 3**

Run:

```bash
git add evals/harness/eval-lib.sh evals/cases/rejected-candidate-laundering.md evals/cases/downgrade-reflection.md evals/fixtures/rejected-candidate-laundering evals/fixtures/downgrade-reflection
git commit -m "test: add verification funnel artifact evals"
```

---

### Task 4: Protected Surface And Track B Assertions

**Files:**
- Modify: `evals/harness/eval-lib.sh`
- Create: `evals/cases/protected-surface.md`
- Create: `evals/cases/track-b-placeholder.md`
- Create: `evals/cases/track-b-placeholder-missing.md`
- Create: `evals/fixtures/protected-surface/artifacts/06-goal-command.md`
- Create: `evals/fixtures/protected-surface/repo/README.md`
- Create: `evals/fixtures/track-b-placeholder/artifacts/03b-verification.md`
- Create: `evals/fixtures/track-b-placeholder/repo/README.md`
- Create: `evals/fixtures/track-b-placeholder-missing/artifacts/03b-verification.md`
- Create: `evals/fixtures/track-b-placeholder-missing/repo/README.md`

**Interfaces:**
- Consumes: fixture metadata lines `protected-surface: <surface>`, `manual-review-boundary: yes`, `doctrine-proof-boundary: yes`, `safety-boundary: yes`, and Phase 4b text `not applicable: Track B`.
- Produces: `protected_surface_boundary` and `track_b_phase4b_not_applicable` assertions.

- [ ] **Step 1: Add the protected-surface expected-fail case**

Create `evals/cases/protected-surface.md`:

```markdown
# Protected Surface

eval-id: protected-surface
eval-fixture: evals/fixtures/protected-surface
eval-expect: fail
eval-assertions: protected_surface_boundary
eval-failure-pattern: missing manual/proof/safety boundary for auth surface

Proves protected work cannot appear without a manual, proof, or safety boundary.
```

- [ ] **Step 2: Add the protected-surface fixture repo marker**

Create `evals/fixtures/protected-surface/repo/README.md`:

```markdown
# Protected Surface Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 3: Add the protected-surface goal artifact**

Create `evals/fixtures/protected-surface/artifacts/06-goal-command.md`:

```markdown
# Goal Command

Goal: Change login session handling for expired tokens.

protected-surface: auth

Proof: `npm test -- auth-session` exits 0.

Constraints: auth files only.

Stop: stop after 8 turns and report the blocker plus next input needed if the proof cannot run.
```

- [ ] **Step 4: Add the Track B passing case**

Create `evals/cases/track-b-placeholder.md`:

```markdown
# Track B Placeholder

eval-id: track-b-placeholder
eval-fixture: evals/fixtures/track-b-placeholder
eval-expect: pass
eval-assertions: track_b_phase4b_not_applicable
eval-failure-pattern:

Proves prompt-to-goal artifacts explicitly mark Phase 4b as not applicable.
```

- [ ] **Step 5: Add the Track B passing fixture repo marker**

Create `evals/fixtures/track-b-placeholder/repo/README.md`:

```markdown
# Track B Placeholder Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 6: Add the Track B passing verification artifact**

Create `evals/fixtures/track-b-placeholder/artifacts/03b-verification.md`:

```markdown
# Phase 4b Verification

verification: not-run
not applicable: Track B does not run scouts, synthesis, or Phase 4b verification.
```

- [ ] **Step 7: Add the Track B missing expected-fail case**

Create `evals/cases/track-b-placeholder-missing.md`:

```markdown
# Track B Placeholder Missing

eval-id: track-b-placeholder-missing
eval-fixture: evals/fixtures/track-b-placeholder-missing
eval-expect: fail
eval-assertions: track_b_phase4b_not_applicable
eval-failure-pattern: missing Track B not-applicable marker

Proves a silent Phase 4b artifact fails the Track B assertion.
```

- [ ] **Step 8: Add the Track B missing fixture repo marker**

Create `evals/fixtures/track-b-placeholder-missing/repo/README.md`:

```markdown
# Track B Placeholder Missing Fixture

This fixture repo is inert. The eval harness reads it as data only.
```

- [ ] **Step 9: Add the Track B missing verification artifact**

Create `evals/fixtures/track-b-placeholder-missing/artifacts/03b-verification.md`:

```markdown
# Phase 4b Verification

verification: not-run
```

- [ ] **Step 10: Add protected-surface and Track B assertions**

In `evals/harness/eval-lib.sh`, insert these functions after `assert_downgrade_reflected`:

```bash
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
```

Then update `run_assertion` by adding these cases before `rejected_not_selectable`:

```bash
    protected_surface_boundary)
      assert_protected_surface_boundary
      ;;
    track_b_phase4b_not_applicable)
      assert_track_b_phase4b_not_applicable
      ;;
```

In `scripts/check-evals.sh`, set `EVAL_TMP` before running assertions by adding this line after `ARTIFACT_DIR="$workspace/artifacts"`:

```bash
  EVAL_TMP="$tmp"
```

- [ ] **Step 11: Run the eval suite**

Run:

```bash
bash scripts/check-evals.sh .
```

Expected includes:

```text
ok: eval case caught expected failure: protected-surface
ok: eval case passed: track-b-placeholder
ok: eval case caught expected failure: track-b-placeholder-missing
check-evals: all artifact evals pass
```

- [ ] **Step 12: Run the portability guard**

Run:

```bash
bash scripts/check-portability.sh .
```

Expected:

```text
portability: no GNU-only grep usage found and workflow + composite-action actions are SHA-pinned
```

- [ ] **Step 13: Commit Task 4**

Run:

```bash
git add scripts/check-evals.sh evals/harness/eval-lib.sh evals/cases/protected-surface.md evals/cases/track-b-placeholder.md evals/cases/track-b-placeholder-missing.md evals/fixtures/protected-surface evals/fixtures/track-b-placeholder evals/fixtures/track-b-placeholder-missing
git commit -m "test: add protected and track-b artifact evals"
```

---

### Task 5: Preflight Wiring And Contributor Docs

**Files:**
- Modify: `scripts/check-all.sh`
- Modify: `CONTRIBUTING.md`

**Interfaces:**
- Consumes: `scripts/check-evals.sh .` from Tasks 1-4.
- Produces: local preflight coverage through `scripts/check-all.sh`.

- [ ] **Step 1: Wire evals into local preflight**

In `scripts/check-all.sh`, insert this line after the `validator meta-tests` check:

```bash
run_check "artifact evals" bash "$root/scripts/check-evals.sh" "$root"
```

The relevant block should become:

```bash
run_check "skill consistency" bash "$root/scripts/check-skill-consistency.sh" "$root"
run_check "skill behavior invariants" bash "$root/scripts/check-skill-behavior.sh" "$root"
run_check "manifest consistency" bash "$root/scripts/check-manifests.sh" "$root"
run_check "portability" bash "$root/scripts/check-portability.sh" "$root"
run_check "validator meta-tests" bash "$root/scripts/test-validators.sh" "$root"
run_check "artifact evals" bash "$root/scripts/check-evals.sh" "$root"
run_check "unstaged diff whitespace/conflict markers" git -C "$root" diff --check
run_check "staged diff whitespace/conflict markers" git -C "$root" diff --cached --check
```

- [ ] **Step 2: Document the eval command in CONTRIBUTING**

In `CONTRIBUTING.md`, add this command to the preflight command list after `bash scripts/test-validators.sh`:

```bash
bash scripts/check-evals.sh              # seeded artifact evals for Pathfinder run-trail contracts
```

- [ ] **Step 3: Add contributor guidance for new eval cases**

In `CONTRIBUTING.md`, add this bullet under "Change guidelines" after the existing behavior-harness bullet:

```markdown
- When you add or change a Pathfinder run artifact contract, add or update an artifact eval under
  `evals/cases/` and `evals/fixtures/`. Expected-fail cases are harness self-tests: they should pass
  the suite only when the seeded bad artifact fails for the intended reason.
```

- [ ] **Step 4: Run the eval suite directly**

Run:

```bash
bash scripts/check-evals.sh .
```

Expected:

```text
check-evals: all artifact evals pass
```

The output should also include these case lines:

```text
ok: eval case passed: good-goal
ok: eval case caught expected failure: missing-proof
ok: eval case caught expected failure: protected-surface
ok: eval case caught expected failure: rejected-candidate-laundering
ok: eval case passed: downgrade-reflection
ok: eval case passed: track-b-placeholder
ok: eval case caught expected failure: track-b-placeholder-missing
```

- [ ] **Step 5: Run full local preflight**

Run:

```bash
bash scripts/check-all.sh .
```

Expected:

```text
check-all: all checks pass
```

- [ ] **Step 6: Check the final diff**

Run:

```bash
git diff --check
git status --short
```

Expected:

```text
```

`git diff --check` should print no output. `git status --short` should show only the files touched by this plan.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add scripts/check-all.sh CONTRIBUTING.md
git commit -m "docs: document artifact eval workflow"
```

---

## Final Verification

After all tasks are complete, run:

```bash
bash scripts/check-evals.sh .
bash scripts/check-all.sh .
git status --short
```

Expected:

```text
check-evals: all artifact evals pass
check-all: all checks pass
```

`git status --short` should show a clean worktree after the final commit.

## Self-Review Notes

Spec coverage:

- Seeded artifact evals are covered by Tasks 1-4.
- Deterministic assertions are covered by `evals/harness/eval-lib.sh`.
- Expected-fail harness self-tests are covered by the missing-proof, laundering, protected-surface, and Track B missing cases.
- Goal proof, boundedness, constraints, and stop conditions are covered by `goal_contract`.
- Rejected-candidate laundering and downgrade reflection are covered by Task 3.
- Protected-surface routing and Track B Phase 4b handling are covered by Task 4.
- Local preflight and contributor docs are covered by Task 5.
- GitHub Actions wiring is intentionally excluded from v1, matching the spec.

Placeholder scan:

- No unfinished-marker steps are allowed in this plan.
- The word "placeholder" appears only in the approved Track B Phase 4b artifact contract.

Type and interface consistency:

- `scripts/check-evals.sh` sources `evals/harness/eval-lib.sh`.
- `run_assertion` is the only assertion dispatch interface.
- Assertion functions use `CASE_ID`, `CASE_FAIL`, `ARTIFACT_DIR`, and, after Task 4, `EVAL_TMP`.
- Case metadata keys are consistent across all case files.
