# Phase 4b verifier claim-framing refinement — Design

**Status:** approved
**Date:** 2026-06-23
**Target version:** 2.15.0
**Scope:** `skills/pathfinder/SKILL.md` Phase 4b only (plus version bump + this spec). Narrow refinement of the v2.14.0 adversarial-verification panel; see the original [`2026-06-23-adversarial-verification-design.md`](./2026-06-23-adversarial-verification-design.md) for the panel it refines.

## Problem

A dogfood run of Pathfinder on its own repository exposed a systematic false-reject in the Phase 4b verifier panel.

Candidate **C2** — a real, `confirmed`, high-value finding (`scripts/check-manifests.sh:45` and `.github/workflows/release.yml:46` use GNU-only `grep -oP '…\K…'`, which breaks the documented "green locally = green in CI" promise on macOS/BSD grep) — drew **two of three `reject` votes**. Two votes meet the destructive quarantine bar. The finding survived only because the hallucination-guard adjudication re-read the cited lines, found the GNU construct genuinely present, and overruled both rejects.

Both rejecting verifiers gave the same reasoning: they read `candidate_end_state` ("scripts exit 0 identically on macOS/BSD grep") as a **claim about the current code**, observed that the code does **not** behave that way, and concluded the claim was "fabricated."

## Root cause

The misframing is structural, not stylistic. In `SKILL.md` (line 423) the blind input each verifier receives is:

> the candidate's `location`, `evidence_grade`, `candidate_end_state`, and `verification` command

`symptom` is **not** in that list. But Lens 1 (line 425) is told to check:

> does the cited `location` exist and actually contain the claimed `symptom`/behavior?

Lens 1 references a field the verifier was never given. With no `symptom` to look for, the verifier substitutes the only behavioral description it has — `candidate_end_state` — as the thing to find in the code. Because `candidate_end_state` describes the **post-fix** state, the unfixed code never matches it, so a refute-leaning verifier reads the gap as disconfirmation and votes `reject`.

The two fields have **opposite** expected truth values against the current code:

- `symptom` — the current broken behavior; **should** be present (its presence confirms the finding).
- `candidate_end_state` — the desired post-fix state; should **not** be present yet (its absence is the normal pre-fix condition).

The spec never states this, and it withholds the one field (`symptom`) that carries the "should be present" expectation.

## Goal

Make verifiers judge the **symptom's presence** (does the finding describe something real in the current code?), never the **end-state's satisfaction** (is the fix already done?). A not-yet-implemented fix must never be grounds for `reject`.

## Non-goals

- No change to Lens 2/3's core questions beyond aligning them to the symptom/end-state distinction (broader lens review was explicitly scoped out).
- No change to scout briefs, the `candidate_end_state` definition, synthesis, the aggregation math (median-of-ceilings, ≥2-of-3 destructive bar), refill, or any Phase 5/6 screen.
- No new CI guard (Phase 4b internals are `SKILL.md`-only; the `check_pair` mirror guards cover Phase 5/6 screens, which are untouched).

## Design

All edits are within the `## Phase 4b: Adversarial verification of the Top 5` section of `skills/pathfinder/SKILL.md`.

### (a) Blind input → labeled two-part claim (replaces the flat list on line 423)

Each verifier receives only the claim to check — never the scout's reasoning, synthesis prose, or ranking. The claim has two parts with **opposite** expected truth values, and the verifier must treat them as such:

- `symptom` — the current observable behavior/risk the finding reports. The verifier **should** find this in the cited code; its presence confirms the finding is real.
- `candidate_end_state` — the state a fix would achieve. It is **not** expected to be present now; its absence is the normal pre-fix condition and is never disconfirming.

…plus `location`, `evidence_grade`, and the `verification` command. The verifier re-reads the cited code fresh and returns one verdict — `keep`, `downgrade-to-<grade>`, or `reject` — with a one-line reason.

`symptom` is an existing field on every finding and candidate; it is not a new artifact field. Adding it to the verifier input does not weaken independence: `symptom` is the claim **under test**, not the scout's reasoning, grade justification, or ranking — those remain excluded.

### (b) Lens wording aligned to the distinction

- **Lens 1 (Grounding)** — does the cited `location` exist and actually contain the claimed `symptom` (the current behavior)? Judge the symptom's presence, **not** whether the end-state holds.
- **Lens 2 (Grade justification)** — is the `evidence_grade` warranted by what is literally readable in the code **for the `symptom`**?
- **Lens 3 (Measurability)** — is `candidate_end_state` a single measurable end state, and would the named `verification` command prove it **once implemented**? Judge the end-state as a target; do not expect it to hold now. Judge read-only (see "Verifier safety").

### (c) Hallucination guard — new "pre-fix gap is not disconfirming" rule

Add to the reject criteria (the "Hallucination guard on rejects" subsection):

> The pre-fix gap is not disconfirming: a verifier must never cite "the code does not yet satisfy `candidate_end_state`" as its disconfirming observation or as grounds to `reject`. A `reject` must rest on the `symptom`/`location` being genuinely absent or mischaracterized (or on injection per the fail-safe). Adjudication overrules any `reject` whose only stated basis is the unmet end-state.

### (d) Sanitization includes the new field

The blind-input sanitization rule (line 482) changes from "(location, end state, command)" to "(location, **symptom**, end state, command)." `symptom` is repo-derived text, so it is redacted and stripped of instruction-like content before being sent to a verifier, exactly like the other blind-input fields.

### Degraded mode

The degraded single-pass mode reuses the same three lens definitions, so it inherits all of the above with no separate edit. The "Degraded verification" subsection needs no change.

## Why this prevents recurrence

The C2 failure required the verifier to (1) lack the `symptom` and (2) treat the unmet `candidate_end_state` as disconfirming. Edit (a) supplies the missing field; edits (a)/(c) make the opposite expected truth values explicit and forbid the exact disconfirming observation both C2 verifiers cited. Either edit alone helps; together they make the failure structurally hard to repeat.

## Verification (definition of done)

- `skills/pathfinder/SKILL.md` contains: the two-part labeled claim in the blind-input paragraph; `symptom` named in Lens 1; the "pre-fix gap is not disconfirming" rule in the hallucination-guard subsection; `symptom` in the sanitization list.
- `bash scripts/check-skill-consistency.sh` exits 0 (fence balance, artifact parity, mirror tokens — all unaffected).
- `bash scripts/check-manifests.sh` exits 0 (version parity: `VERSION.md`, both `plugin.json` at `2.15.0`; marketplaces carry no version).
- `VERSION.md` is `2.15.0` with a `Changes in v2.15.0:` block describing the refinement; both `plugin.json` files are `2.15.0`.
- `git diff --check` exits 0.

## Blast radius

- Modify: `skills/pathfinder/SKILL.md` (Phase 4b section only), `VERSION.md`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`.
- Create: this spec.
- Untouched: scout-brief template, synthesis rules, Phase 5/6 screens and their reference mirrors, both guard scripts' logic, all workflows.

## Protected areas / constraints

- Do not alter the aggregation math, the destructive-reject bar, refill, or the two-confidence-quantity model.
- Do not edit the Phase 5/6 mirrored screens or their `check_pair` tokens.
- `VERSION.md` format: exactly one anchored `Version:` line; editing it re-triggers `release.yml` on merge to main.
- Per-platform marketplace category casing stays as-is; marketplace files carry no version.
