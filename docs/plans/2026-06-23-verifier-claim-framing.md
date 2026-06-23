# Phase 4b Verifier Claim-Framing Refinement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the Phase 4b verifier panel from false-rejecting a real finding because its fix is not yet implemented, by giving each verifier the `symptom` it is told to check and framing `symptom` vs `candidate_end_state` as having opposite expected truth values.

**Architecture:** Pure documentation refinement of one section (`## Phase 4b`) of `skills/pathfinder/SKILL.md`, plus a version bump. No code, no new artifact, no CI-guard change. The "test harness" is the two repo guard scripts, which must exit 0 after each task.

**Tech Stack:** Markdown (the skill spec), POSIX bash guard scripts (`scripts/check-skill-consistency.sh`, `scripts/check-manifests.sh`), JSON plugin manifests.

## Global Constraints

- All prose edits are confined to the `## Phase 4b: Adversarial verification of the Top 5` section of `skills/pathfinder/SKILL.md`. Do not touch scout briefs, synthesis rules, the aggregation math (median-of-ceilings, ≥2-of-3 destructive bar), refill, or any Phase 5/6 screen or its reference mirror.
- `symptom` is an existing finding/candidate field — do **not** introduce a new artifact field, and do **not** edit `references/scout-brief-template.md`.
- No new CI guard: Phase 4b internals live only in `SKILL.md`; the `check_pair` mirror tokens cover Phase 5/6 screens, which stay untouched. Do not remove any existing guarded token (`Verified:`, `Rejected by verification`, `proof unverified by Lens 3`, etc.).
- Target version `2.15.0`, mirrored identically across `VERSION.md`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`. The two `marketplace.json` files carry **no** version.
- `VERSION.md` keeps exactly one anchored `Version:` line and must include a `Changes in v2.15.0:` heading. Editing `VERSION.md` re-triggers `release.yml` on merge to main.
- Commit identity must be `Chris <duvillard.c@gmail.com>`.
- `bash scripts/check-skill-consistency.sh` and `bash scripts/check-manifests.sh` must each exit 0 after every task (run under Git Bash; both are POSIX sh).

## File Structure

| File | Responsibility | Task |
|------|----------------|------|
| `skills/pathfinder/SKILL.md` | The four Phase 4b wording edits (a)–(d) | Task 1 |
| `VERSION.md` | Version → 2.15.0 + `Changes in v2.15.0:` block | Task 2 |
| `.claude-plugin/plugin.json` | `version` → `2.15.0` | Task 2 |
| `.codex-plugin/plugin.json` | `version` → `2.15.0` | Task 2 |

---

### Task 1: Phase 4b verifier claim-framing edits

**Files:**
- Modify: `skills/pathfinder/SKILL.md` (the `## Phase 4b` section only — currently around lines 419–482)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the refined Phase 4b wording. Task 2 depends on nothing from this task except that the file is committed first.

Apply four exact edits with the Edit tool (match by content, not line number).

- [ ] **Step 1: Edit (a) — restructure the blind-input paragraph**

Replace this exact paragraph:

```
Each verifier receives only the claim to check — the candidate's `location`, `evidence_grade`, `candidate_end_state`, and `verification` command — never the scout's reasoning, the synthesis prose, or the ranking. Each verifier re-reads the cited code fresh and returns one verdict on the candidate: `keep`, `downgrade-to-<grade>`, or `reject`, with a one-line reason. Prime each verifier with one of three lens emphases so their blind spots decorrelate:
```

with:

```
Each verifier receives only the claim to check — never the scout's reasoning, the synthesis prose, or the ranking. The claim has two behavioral parts with **opposite** expected truth values against the current code, and the verifier must treat them as such:

- `symptom` — the current observable behavior/risk the finding reports. The verifier **should** find this in the cited code; its presence confirms the finding is real.
- `candidate_end_state` — the state a fix would achieve. It is **not** expected to be present now; its absence is the normal pre-fix condition and is never disconfirming.

…plus the candidate's `location`, `evidence_grade`, and `verification` command. (`symptom` is an existing finding/candidate field, not a new one; including it does not weaken independence, because it is the claim under test rather than the scout's reasoning, grade, or ranking.) Each verifier re-reads the cited code fresh and returns one verdict on the candidate: `keep`, `downgrade-to-<grade>`, or `reject`, with a one-line reason. Prime each verifier with one of three lens emphases so their blind spots decorrelate:
```

- [ ] **Step 2: Edit (b) — align the three lens descriptions**

Replace this exact block:

```
1. Grounding — does the cited `location` exist and actually contain the claimed `symptom`/behavior?
2. Grade justification — is the `evidence_grade` warranted by what is literally readable in the code?
3. Measurability — is `candidate_end_state` a single measurable end state, and would the named `verification` command actually prove it? Judge read-only (see "Verifier safety").
```

with:

```
1. Grounding — does the cited `location` exist and actually contain the claimed `symptom` (the current behavior)? Judge the symptom's presence, not whether the end-state already holds.
2. Grade justification — is the `evidence_grade` warranted by what is literally readable in the code for the `symptom`?
3. Measurability — is `candidate_end_state` a single measurable end state, and would the named `verification` command prove it once implemented? Judge the end-state as a target; do not expect it to hold now. Judge read-only (see "Verifier safety").
```

- [ ] **Step 3: Edit (c) — add the "pre-fix gap is not disconfirming" rule to the hallucination guard**

In the `### Hallucination guard on rejects` subsection, replace this exact bullet:

```
- Require each `reject` to cite a concrete disconfirming observation: the exact path and symbol read and what was found there instead.
```

with these two bullets (original bullet kept, new bullet added after it):

```
- Require each `reject` to cite a concrete disconfirming observation: the exact path and symbol read and what was found there instead.
- The pre-fix gap is not disconfirming: a verifier must never cite "the code does not yet satisfy `candidate_end_state`" as its disconfirming observation or as grounds to `reject`. A `reject` must rest on the `symptom`/`location` being genuinely absent or mischaracterized (or on injection per the fail-safe). Adjudication overrules any `reject` whose only stated basis is the unmet end-state.
```

- [ ] **Step 4: Edit (d) — add `symptom` to the blind-input sanitization list**

Replace this exact text (in the "Verifier safety" / fail-safe paragraph):

```
Sanitize the blind input (location, end state, command) before sending it to a verifier, the same way Phase 6 sanitizes mirrored lines.
```

with:

```
Sanitize the blind input (location, symptom, end state, command) before sending it to a verifier, the same way Phase 6 sanitizes mirrored lines.
```

- [ ] **Step 5: Verify the new wording is present and nothing was lost**

Run (Git Bash), expecting each to print a match:

```bash
grep -c 'two behavioral parts with' skills/pathfinder/SKILL.md      # expect 1
grep -c 'pre-fix gap is not disconfirming' skills/pathfinder/SKILL.md # expect 1
grep -c 'location, symptom, end state, command' skills/pathfinder/SKILL.md # expect 1
grep -c 'claimed `symptom` (the current behavior)' skills/pathfinder/SKILL.md # expect 1
```

And confirm no guarded token was removed (each must still be > 0):

```bash
grep -c 'Verified:' skills/pathfinder/SKILL.md
grep -c 'Rejected by verification' skills/pathfinder/SKILL.md
grep -c 'proof unverified by Lens 3' skills/pathfinder/SKILL.md
```

- [ ] **Step 6: Run the consistency guard**

Run: `bash scripts/check-skill-consistency.sh`
Expected: exits 0 (prints its success summary; no fence-balance, artifact-parity, or mirror-token failure). Also run `bash scripts/check-manifests.sh` and expect exit 0 (version parity still holds at the unchanged 2.14.0).

- [ ] **Step 7: Commit**

```bash
git add skills/pathfinder/SKILL.md
git commit -m "feat: frame Phase 4b verifier claim as symptom (present) vs end-state (post-fix)"
```

---

### Task 2: Version bump to 2.15.0

**Files:**
- Modify: `VERSION.md` (lines 5 and the changelog region after line 18)
- Modify: `.claude-plugin/plugin.json:3`
- Modify: `.codex-plugin/plugin.json:3`

**Interfaces:**
- Consumes: a committed Task 1 (so the changelog describes shipped wording).
- Produces: the release-ready version metadata; `release.yml` cuts `v2.15.0` on merge to main.

- [ ] **Step 1: Bump the VERSION.md version line**

Replace `Version: 2.14.0` with `Version: 2.15.0`. Leave `Generated: 2026-06-23` unchanged (already today).

- [ ] **Step 2: Add the v2.15.0 changelog block**

Insert this block immediately before the existing `Changes in v2.14.0:` line (keep one blank line separating blocks):

```
Changes in v2.15.0:
- Refined the Phase 4b verifier panel so it can no longer false-reject a real finding for not being fixed yet. Each blind verifier now receives the candidate's `symptom` — the current behavior, which should be present in the code (the field Lens 1 always referenced but was never supplied) — alongside `candidate_end_state`, the post-fix target, which is not expected to be present and whose absence is never disconfirming. Lens 1 judges the symptom's presence, Lens 3 judges the end-state as a target, and the hallucination guard now forbids citing the unmet end-state as grounds to reject. `symptom` is added to the blind-input sanitization list.
- Surfaced by a dogfood run of Pathfinder on its own repository: two of three verifiers misread a confirmed finding's post-fix end-state as a false claim about current code and voted reject (meeting the 2-of-3 destructive bar); only the adjudication re-read kept the finding from being quarantined.

```

- [ ] **Step 3: Bump both plugin manifests**

In `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, change `"version": "2.14.0"` to `"version": "2.15.0"` (line 3 in each).

- [ ] **Step 4: Run the manifests guard**

Run: `bash scripts/check-manifests.sh`
Expected: exits 0 — version parity holds at 2.15.0 across `VERSION.md` + both `plugin.json`; both `marketplace.json` carry no version; exactly one `Version:` line; a `Changes in v2.15.0:` heading exists. Also run `bash scripts/check-skill-consistency.sh` and expect exit 0.

- [ ] **Step 5: Commit**

```bash
git add VERSION.md .claude-plugin/plugin.json .codex-plugin/plugin.json
git commit -m "chore: release v2.15.0 — Phase 4b verifier claim-framing"
```

---

## Self-Review

**1. Spec coverage:** Spec edits (a)/(b)/(c)/(d) → Task 1 Steps 1/2/3/4. Versioning (2.15.0 + changelog) → Task 2. "No CI-guard change" → honored (Global Constraints + no script edits). Definition-of-done items (wording present, both guards exit 0, version parity, `git diff --check`) → Task 1 Steps 5–6 + Task 2 Step 4 (`git diff --check` runs in the final review). Degraded mode "inherits, no edit" → honored (no edit to that subsection). All spec sections covered.

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to". Every edit step carries the exact old and new text; every verification step carries the exact command and expected result.

**3. Type/text consistency:** The new strings checked in Task 1 Step 5 (`two behavioral parts with`, `pre-fix gap is not disconfirming`, `location, symptom, end state, command`, `claimed \`symptom\` (the current behavior)`) are exactly the strings introduced in Steps 1–4. The version string `2.15.0` and heading `Changes in v2.15.0:` are identical across Task 2 and the guard expectations.
