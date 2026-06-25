# Question Funnel Template

Use after blind discovery, scout reports, synthesis, and the Top 5 candidate implementation goals.

Pathfinder runs one of two user-selectable modes: Pick a move (candidate-first, default; alias "express") and Explore from scratch (drill-down; alias "deep dive"). Ask which mode to use first — leading with the strongest finding — then follow that mode. Pick a move can select one, select several, or select all Top moves before goal generation. Both obey the same universal rules.

This template is the interactive funnel. In autonomous mode (see “Autonomous mode (opt-in)” in `SKILL.md`) none of these screens run: auto-selection takes every verified survivor and the Phase 7-A loop executes them without an interview.

## Universal rules

- Always suggest 3 to 6 numbered, repo-grounded answers. Never ask an open question with no options. Exception: the Full surface map browse screen lists every surface as an index, not a 3-to-6 menu; it still carries `Agent recommends:` and the escapes.
- Always include an `Agent recommends:` line that names which listed option is the current best pick. It is a pointer to one of the options, never an extra numbered option.
- Every option-bearing work-selection question (L0-L4, Pick a move's candidate screen, and the selected-moves grouping review) includes a `None of these, let me describe it` escape; every drill-down question after the first (L1 onward) also includes `Go back`. The one-time mode-selection and terminal post-save execution choice are exempt from both.
- Ground every option in actual findings, not generic categories.
- Recognition-first: the first screen shows the ranked Top 5 or the full map, never an abstract category menu.
- Two-channel freedom: every work-selection screen offers `show the full map` and `describe your own`; Explore mode also offers `back to candidates` at every level.
- Evidence with options: each option shows its evidence grade (confirmed/inferred/suspected) and a one-line basis next to any confidence word.
- Post-verification grades: when `03b-verification.md` is `complete`, every work-selection screen shows the post-verification grade and a one-line `Verified:` field; when it is `not-run` or `in-progress`, show the Phase 4 grades and no `Verified:` field. Surface any candidates the panel rejected in a `Rejected by verification` line.
- Objective awareness (only when a charter is loaded): the mode-selection preamble states `Objectives: <north-star> (from your charter) — <k> of 5 top moves align.`; every Pick a move card and Explore option carries an `Aligns:` line/token showing only **north-star** alignment (`✓` aligned, `~` partial, omitted when neutral, words `counter to north-star` for the rare counter case — no new glyphs); a candidate the tiebreak moved appends `(moved <from>-><to> on north-star alignment)`; and an `ignore objectives` escape at any level strips the annotations and reverts to pure evidence order. The `users`/`constraints` charter dimensions are not shown per-card (they live in the charter). Log each pre/post rank change and reason to `05-user-answers.md`.
- Record the chosen mode in `04-question-funnel.md`; for Explore from scratch, record the full narrowing path. For Pick a move multi-select, record the raw selection input and grouping review options shown. Save answers to `05-user-answers.md`, including selected moves, accepted grouping, splits, merges, drops, and execution choice.
- Stop only when there is enough to write a measurable `/goal`.

## Phase 4c: Objectives charter interview (runs before mode selection)

When `.pathfinder/charter.md` is absent, Phase 4c (see `SKILL.md`) offers a skippable three-screen interview that establishes the durable objectives charter; when it is present, Phase 4c reconciles it instead of re-asking. Each screen leads with evidence-graded inferred suggestions, backs them with a scaffolded generic row, and carries the `None of these - describe your own` escape and an `Agent recommends:` pointer.

```text
Objective 1 of 3 - North-star & success metrics
What is this project ultimately for, and how do we know it's winning?

Inferred from research:
1. ~ North-star: "<inferred north-star>"   basis: <code/structure basis> (inferred)
2. ? Success metric: "<inferred metric>"   basis: <basis> (suspected)

Or pick a generic frame:
3. Adoption / usage growth   4. Reliability / quality bar   5. Time-to-value for a new user

Agent recommends: 1 because <reason from a code/scout-grounded candidate>.
None of these - describe your own north-star and metric in your own words.
```

Screens 2 (Target users & key journeys, generic row from reservoir B) and 3 (Constraints & non-goals, generic row from reservoirs E + F) follow the same grammar. Roadmap is never a screen. Record the screens in `04-question-funnel.md`, the ratified objectives in `05-user-answers.md`, and the durable answers in `.pathfinder/charter.md`.

On a later run with a charter present, Phase 4c reconciles instead of re-asking: it shows only fields where fresh inference disagrees as keep/update/edit option screens (default keep-and-proceed; empty delta collapses to one line), and offers `refresh objectives (go deeper)` to re-open all three screens. The standalone `/pathfinder charter` invocation runs the same refresh directly.

## Mode selection (ask once)

```text
I mapped this repo and found <N> verified candidates (<M> rejected by verification).
Top pick: <top candidate symptom> — <location> (<evidence_grade>, <confidence>).
Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ | n/a (not run)>.
Objectives: <north-star> (from your charter) — <k> of 5 top moves align.   (only when a charter is loaded)

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one or more   [recommended]
2. Explore from scratch drill down by intent → area → surface, ignoring my ranking

Agent recommends: <1 | 2> because <one-line reason from findings>.
Reply 1, 2, or "express"/"deep dive".
```

Recommend Pick a move when one high-confidence target stands out; recommend Explore for large or ambiguous repos. "express" → Pick a move, "deep dive" → Explore from scratch. If the user names a concrete target up front, jump straight to L4 (Boundaries) and confirm.

If verification leaves zero candidates, show the fixed zero-survivor menu from SKILL.md (re-run scouts / switch to prompt-to-goal / review rejected block) instead of the funnel.

## Mode 1: Pick a move (candidate-first, default)

Show the ranked Top 5 from `03-synthesis.md` as evidence cards. The card must be understandable without reading hidden synthesis files: show the plain outcome/symptom, exact location, evidence grade and basis, likely fix shape, proof/checks, risk/protected areas, and grouping hint.

```text
Top moves (impact ÷ effort; confirmed > inferred > suspected):
 1. Outcome: <plain-language symptom or result>
    Location: <exact file:symbol/route/component>
    Evidence: <glyph> <evidence_grade> — <one-line basis>   confidence: <HIGH|MED|LOW>
    Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ (median of 3) | 1/3 flagged; median holds>
    Aligns:   ✓ north-star   - <one-line why>   (omit when neutral)
    Likely fix shape: <validation/refactor/test/etc.>
    Proof/checks: <narrow verification commands; flag repo-code execution>
    Risk/protected areas: <blast radius; PROTECTED flagged>
    Grouping hint: <can group with ids because... / keep separate because...>
 2. Outcome: <plain-language symptom or result>
    Location: <exact location>
    Evidence: <glyph> <evidence_grade> — <basis>   confidence: <...>
    Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ (median of 3) | 1/3 flagged; median holds>
    Aligns:   ✓ north-star   - <one-line why>   (omit when neutral)
    Likely fix shape: <fix shape>
    Proof/checks: <checks>
    Risk/protected areas: <risk>
    Grouping hint: <hint>
 ... up to 5 ...

Rejected by verification (<N>): <symptoms> — see 03b-verification.md

Agent recommends: <option n> because <reason>.

Pick a move:
  • one: 1
  • several: 1,3,5
  • select all: all, a, 1-5, or 1,2,3,4,5

narrow by area/intent: switch to Explore from scratch (L0)
None of these: describe your own (free text)   show the full map
```

Glyphs: `✓` confirmed, `~` inferred, `?` suspected. Picking one number jumps straight to L4 (Boundaries).

Pick a move input grammar:

- Single select: `1` through `5`.
- Partial multi-select: comma-separated candidate numbers such as `1,3,5`.
- All aliases: `all`, `a`, `1-5`, and `1,2,3,4,5`. These all mean select all five Top moves.

Any multi-select, including all aliases or manually selecting all five moves, opens the Selected moves grouping review before boundaries or goal generation. Recommend grouped goals by default when one measurable goal can cover the selected moves cleanly. Keep unrelated, risky, protected-area-heavy, low-confidence, or incompatible-verification moves separate.

```text
Selected moves: <ids and short outcomes>

Recommended grouping review:
  Goal 1: candidates <ids> — <shared surface/check/end state>
    Rationale: <why one measurable goal can cover them>
    Proof: <shared or compatible checks>
  Goal 2: candidate <id> — kept separate
    Rationale: <unrelated surface, protected area, risk, or incompatible proof>

1. Accept recommended grouping and save a goal pack   [recommended when groups are coherent]
2. Split into one goal per selected move
3. Adjust selection: reply with numbers or all aliases
4. Go back to Top moves

Agent recommends: <1 | 2> because <one-line grouping rationale>.
None of these, let me describe it: describe the grouping you want in free text.
```

Accepted grouping produces a numbered goal pack in `06-goal-command.md`; split produces one goal per selected move. Adjusting selection re-runs the grouping review. If the final selection has one move, return to the single-goal flow.

Confidence-adaptive collapse — when one goal-readiness `high` candidate dominates, confirm instead of menu:

```text
One target clearly dominates (selected on post-verification goal-readiness `high`):
<symptom> — <location> (<evidence_grade>, confidence: HIGH).
Verified: <panel verdict>.
1. Confirm it and set boundaries
2. See the other <N> candidates (back to the ranked Top 5)
Agent recommends: 1 because this is the single goal-ready, high-confidence target.
None of these: describe your own.   show the full map
```

Compute collapse eligibility only after re-rank and refill settle, on post-verification `goal-readiness`. Never carry the pre-verification dominator forward. Do not collapse on a single-pass `keep` or on any candidate where a verifier flagged suspicious content.

## Full surface map (shared browse screen)

The destination for every `show the full map`. Built from the per-domain surface index in `03-synthesis.md` (or the re-emitted post-verification index in `03b-verification.md` when Phase 4b is `complete`); lists every surface as an index, not a 3-to-6 menu.

```text
Full surface map — grouped by domain (✓ confirmed  ~ inferred  ? suspected · count = findings)

Backend/Data
  b1. api/orders.py:POST /orders   ✓ duplicate-charge on retry   (3)   Verified: 3/3 confirm
Frontend/Product
  f1. views/DashboardView.tsx      ✓ empty-state crash           (2)

Rejected by verification
  (surfaces backing rejected candidates appear here with their rejection reason; picking one re-enters at L3 with the reason shown)

Pick a surface to set it as your target.
Agent recommends: b1 — most confirmed findings.
back to candidates: ranked Top 5  ·  describe your own  ·  go back
```

Group by scout domain; order by finding count then evidence grade. Picking a surface jumps to L3 (Target) for it; a single-finding surface auto-confirms and goes to L4. Carries `Agent recommends:` and the escapes; does not re-offer `show the full map`.

## Mode 2: Explore from scratch

One question per level. Hard cap of five levels (L0 to L4) before Phase 6 goal confirmation and the post-save execution choice. Each level's options are conditioned on the previous answer and generated from the scout briefs.

Scout backbone: Architecture, Frontend/Product, Backend/Data, Testing/Reliability, Developer Experience/Security.

Before each question, show the narrowing trail and a confidence signal:

```text
Path so far: fix → backend/data → POST /orders handler → duplicate-charge on retry
Goal-readiness confidence: high (Verified: <verdict>)
Next: how aggressive should the fix be?
```

Render this header before every level (L0–L4); the per-level screens below omit it only for brevity, never because it is skipped. Only trigger adaptive early-stopping when goal-readiness is high AND verified.

### L0. Intent (only intents with candidates, annotated)

```text
1. Fix a correctness/reliability defect → <n> candidates (<m> confirmed)
2. Improve a product/UX surface         → <n> candidates
3. Improve backend/API/data robustness  → <n> candidates
... only intents that have candidates ...
9. Agent picks the highest-ROI outcome

Agent recommends: <option n> because <one-line reason from findings>.
None of these: describe the outcome you want.
back to candidates: return to the ranked Top 5.   show the full map
```

### L1. Domain (real candidates from the owning scout)

```text
Given "<intent>", the strongest candidates (glyph = evidence grade: ✓ confirmed, ~ inferred, ? suspected):
1. <glyph> <candidate #1 symptom> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>
2. <glyph> <candidate #2 symptom> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>
3. <glyph> <candidate #3 symptom> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>

Agent recommends: <option n, highest-confidence candidate> because <reason>.
None of these: describe the area.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

### L2. Surface (concrete surfaces from the repo)

```text
Within <domain>, which surface?
1. <real route/module/service/test> — <glyph> <strongest finding symptom here>   Verified: <verdict>
2. <real surface> — <glyph> <strongest finding symptom>   Verified: <verdict>
3. <real surface> — <glyph> <strongest finding symptom>   Verified: <verdict>

Agent recommends: <option n, best surface> because <reason>.
None of these: name the file/area.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

### L3. Target (exact behavior/function/symptom)

If one clear target dominates, confirm rather than manufacture a menu:

```text
Best target: <glyph> <exact behavior/function/symptom> — <one-line basis> (<evidence_grade>, <confidence>).
Verified: <verdict>.
1. Confirm this target
2. None of these: describe the precise behavior in your own words
Agent recommends: 1 because <one-line reason>.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

Otherwise offer numbered targets plus `Agent recommends` and the escapes, appending `   Verified: <verdict>` to each option line.

### L4. Boundaries (scoped to the target)

```text
For <target>, set the boundaries:
- Scope: 1) very conservative  2) moderate  3) ambitious  4) creative
- Protect (avoid without approval): <detected protected areas for this target>
- Done when: <2-3 concrete checks from the repo, flagged if they need to run repo code>
Agent recommends: Scope 2 (moderate) because <reason>.
None of these: describe the scope, protected areas, or success criteria in your own words.
Reply with edits, "accept agent recommendation", "go back", "back to candidates", or "show the full map".
```

### Adaptive stopping

- If goal-readiness confidence is already high before L3, skip to L4.
- If confidence is still low after L3, ask one extra sharpening question at the same altitude.
- If the user keeps choosing `Agent recommends`, commit to the highest-confidence path and stop asking.
- `Go back` re-presents the previous question without restarting the funnel.
- `back to candidates` returns to the ranked Top 5 and `show the full map` opens the Full surface map browse screen, at any level, without restarting.
- `ignore objectives` strips the charter alignment annotations and reverts to pure evidence order, at any level.

## Prompt-to-goal track (gap-driven clarifying funnel)

This is the funnel for the prompt-to-goal track (see "Track B: Prompt-to-goal" in `SKILL.md`), used when the user supplies a prompt instead of asking Pathfinder to explore. It replaces the L0–L4 drill-down and does not run the five scouts or Top-5 ranking.

The `/goal` best-practices checklist (`goal-best-practices.md`) is the rubric. Targeted, prompt-anchored research fills every item it can; then ask only about the checklist items still missing or ambiguous: measurable end state, scope, proof/checks, constraints, non-goals, protected areas, stop bound. These are gap-driven questions — ask nothing the research already settled, and if the prompt is already well-formed, skip straight to the Phase 6 recognition-first contract.

Each gap question obeys the universal rules: 3 to 6 repo-grounded options, an `Agent recommends:` pointer line, and a `None of these, let me describe it` escape.

```text
The prompt is clear on the target, but the goal still needs a stop bound. How should the loop stop?
1. After 10 turns or 3 failed implementation loops, then report the blocker and the next input needed   [recommended]
2. After 15 turns or 3 failed loops, then report the blocker
3. When the named tests pass, or after 8 turns
Agent recommends: 1 because the change is small and localized to <surface>.
None of these, let me describe it.
```

Record the gap questions in `04-question-funnel.md` and answers in `05-user-answers.md`, then continue to Phase 6 (recognition-first contract), Phase 7, and Phase 8 exactly as the exploration modes do.

## Post-save execution choice (both modes)

Show this only after the recognition-first contract is accepted and `06-goal-command.md` has been written.

1. Show the saved goal or goal pack and wait.
2. Keep it saved; do not run until I explicitly approve. [default]
3. Run the saved goal now after showing the exact command. For a goal pack, ask which numbered goal to run first.
4. Audit only.

Default to option 2. Do not recommend option 3 merely because the user confirmed the goal, selected a narrow scope, or the goal looks safe; confirmation to save is not confirmation to run.

For a goal pack, default remains save first and ask before running. If the user approves execution, run one numbered goal at a time unless the user explicitly asks to run all goals in the pack.
