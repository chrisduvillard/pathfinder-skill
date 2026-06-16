# Candidate-first question funnel — design spec

Date: 2026-06-16
Status: approved (design); implementation pending
Scope: Phase 5 of the Pathfinder skill only
Target version: 2.8.0

## Problem

Phase 5 is the weakest part of the skill. The interview is supposed to pinpoint the
exact work, but the way it asks for that work fights against the user instead of helping:

1. **The first question is the least grounded.** `L0 Intent` is a fixed taxonomy of
   abstract verbs ("improve backend robustness", "harden security"). The universal rule
   says "ground every option in actual findings, not generic categories"
   (`skills/pathfinder/SKILL.md:341`), yet the opening question violates it. The user must
   commit to an abstraction before seeing one concrete finding, which can hide the best
   candidate (pick "fix a defect" and you never see the strong perf win).
2. **Mode and intent are chosen blind.** The user selects Express vs. Deep dive, then an
   intent, all before the ranked Top-5 candidate landscape is shown — even though Phase 4
   already computed it with confidence grades.
3. **Freedom is only an escape hatch.** `None of these` and `Go back` let the user *leave*
   the funnel; nothing lets them *roam inside it* (browse the whole map, widen a list,
   bail back to the ranked recommendation).
4. **Confidence is a bare word.** Options show "high/medium/low" but not the evidence that
   justifies the rank, so a choice is not actually informed.

## Principle

Resolve "spot-on vs. freedom" by splitting them into **two channels present on every
screen**:

- a **confident default** — the #1 ranked candidate, one keystroke away; and
- a **persistent lateral move** — browse the full map, narrow by area, or describe your own.

Spot-on stops competing with freedom because they occupy different parts of the same
screen. This is recognition-over-recall (react to a concrete candidate) plus progressive
disclosure (drill only when the user asks to).

## Key enabling fact

Candidate-first is a **pure presentation reorder of Phase 5**. Every field a candidate
card needs already exists in Phase 4 synthesis output (`skills/pathfinder/SKILL.md:316–327`):
measurable end state, exact location, observable symptom, evidence grade, confidence,
blast radius / protected areas, and goal-readiness. No scout or synthesis change is
required. Blast radius is limited to two files.

## Design

### 1. Mode selection — reframed and grounded

Keep the upfront mode question (preserves the v2.5 two-mode structure the user chose to
keep), but make the toggle itself informed by previewing the top candidate and the count,
fixing the "choose blind" problem:

```text
I mapped this repo and found 5 ranked candidates.
Top pick: duplicate-charge on retry — POST /orders (confirmed, HIGH).

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one   [recommended]
2. Explore from scratch drill down by intent → area → surface, ignoring my ranking

Agent recommends: 1 — one confirmed, high-confidence target stands out.
Reply 1 / 2, or "express"/"deep dive" (kept as aliases).
```

- **Mode 1 "Pick a move"** = candidate-first; the new default.
- **Mode 2 "Explore from scratch"** = today's L0→L4 drill-down, repositioned as the
  "I distrust the ranking / want to roam" path.
- `express` maps to Mode 1, `deep dive` maps to Mode 2; both kept as accepted typed
  aliases so existing docs and muscle memory keep working.
- If the user named a concrete target up front, still jump straight to Boundaries (L4),
  as today.

### 2. Mode 1 — Candidate-first flow

Show the ranked Top 5 as evidence-bearing cards. Card fields all come from Phase 4:

```text
Top moves (ranked by impact ÷ effort; confirmed outrank inferred outrank suspected):

 1. Duplicate-charge on retry            POST /orders handler  (orders.py:142)
    ✓ confirmed — failing test test_retry_double_charge   confidence: HIGH
    suggested scope: conservative · touches: orders.py, payments client (PROTECTED)
 2. Dashboard empty-state crash          DashboardView.loadData (dashboard.tsx:88)
    ~ inferred — null payload, no guard                    confidence: MED
 …

 Agent recommends: 1 — confirmed money bug, small blast radius.

 Pick 1–5 — or go sideways:
   • narrow by area/intent   → hands off to Mode 2 (Explore)
   • show the full map       → browse every surface, not just the Top 5
   • describe your own        (free text)
```

Card line format (per candidate):

- line 1: `<index>. <symptom one-liner>   <location: file:symbol/route>`
- line 2: `<grade glyph> <evidence_grade> — <one-line evidence>   confidence: <H/M/L>`
- line 3: `suggested scope: <scope>` · `touches: <blast radius; PROTECTED areas flagged>`

Glyphs: `✓` confirmed, `~` inferred, `?` suspected.

`suggested scope` is derived at presentation time from the candidate's existing
`blast_radius`, `risk`, and protected-area fields (e.g. a fix touching a protected area →
conservative). It is a preview of the L4 scope recommendation, not a new Phase 4 field.

Behavior:

- **Pick a number → go straight to Boundaries (L4)**, then execution mode. The common path
  is short: pick the recommended candidate, confirm boundaries, choose execution mode — no
  intent/domain/surface drilling.
- **Confidence-adaptive collapse**: when exactly one candidate is goal-ready `high` and
  clearly dominates the rest, render a single **confirm** card with a "see the other N"
  option instead of the full menu. On by default.
- Lateral moves (`narrow by area/intent`, `show the full map`, `describe your own`) are
  always present.

After a candidate is chosen, run the existing **L4 Boundaries** question (scope, protected
areas, done-when), scoped to that candidate. If the candidate already carries a clear
recommended scope and done-when, L4 may collapse to a one-line confirm.

### 3. Mode 2 — Explore from scratch (freedom path, grounding fixes)

The existing L0→L4 drill-down is kept, with these fixes so it never feels ungrounded:

- **L0 intents annotated with real candidate counts**, e.g.
  `1. Fix a defect → 3 candidates (1 confirmed)`. Drop intents with zero candidates.
- **Two persistent lateral moves added at every level**: `back to candidates` (bail out to
  the Mode 1 ranked list at any depth) and `show the full map`, alongside the existing
  `None of these` and `Go back`.
- **Evidence travels with every option** (grade glyph + one-line basis), not just a bare
  confidence word.

All other Mode 2 mechanics (one question per level, five-level cap, narrowing trail,
goal-readiness confidence signal, adaptive stopping) are unchanged.

### 4. Universal-rules edits (`skills/pathfinder/SKILL.md:335–343`)

- **Recognition-first ordering**: the first thing shown in either mode must be the most
  grounded artifact available (ranked candidates or the full map), never an abstract
  category menu shown before any finding.
- **Two-channel freedom**: every work-selection screen must carry a lateral move to
  *widen* (`show the full map`) and to *leave* (`describe your own`), not only `Go back`.
- **Evidence with options**: wherever a confidence word appears, the option also shows its
  evidence grade and a one-line basis.

The existing `Agent recommends:` rule (a pointer line to one listed option, never an extra
numbered option) and the escape rules are retained and extended to the new screens.

### 5. Artifacts

- `04-question-funnel.md` records the chosen mode **and** which channel produced the
  decision: a candidate pick, a Mode 2 drill path, or a full-map browse.
- `05-user-answers.md` is unchanged in spirit (records the answers and final target).

## Blast radius

- Files changed: `skills/pathfinder/SKILL.md` (Phase 5 section and the universal rules),
  and `skills/pathfinder/references/question-funnel-template.md`.
- Phase 4 synthesis, the scout briefs, and all other phases are untouched.
- Version bump `2.7.0 → 2.8.0` in `.claude-plugin/plugin.json` and
  `.codex-plugin/plugin.json`; add a `Changes in v2.8.0` entry to `VERSION.md`.

## Acceptance checks

1. Mode-selection question previews the top candidate and the candidate count.
2. Mode 1 shows ranked Top-5 cards with location, evidence grade + one-line basis,
   confidence, suggested scope, and blast radius; picking a number routes straight to L4.
3. Confidence-adaptive collapse triggers when one `high` candidate dominates.
4. Mode 1 and Mode 2 both expose `show the full map` and `describe your own`; Mode 2 also
   exposes `back to candidates` at every level.
5. Mode 2 L0 lists only intents that have candidates, each annotated with a candidate
   count; evidence accompanies options at every level.
6. `express`/`deep dive` still select Mode 1/Mode 2 respectively.
7. SKILL.md and the template agree on every screen (no spec drift between them).
8. Both JSON manifests parse and report version 2.8.0; VERSION.md has the v2.8.0 entry.

## Out of scope

- No change to scouts, synthesis, the `/goal` generation rules, or the artifact contract
  beyond the `04-question-funnel.md` channel note.
- No new upstream fields; the redesign consumes existing Phase 4 output.
