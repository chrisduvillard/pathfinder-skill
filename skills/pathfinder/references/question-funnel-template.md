# Question Funnel Template

Use after blind discovery, scout reports, synthesis, and the Top 5 candidate implementation goals.

Pathfinder runs one of two user-selectable modes: Pick a move (candidate-first, default; alias "express") and Explore from scratch (drill-down; alias "deep dive"). Ask which mode to use first — leading with the strongest finding — then follow that mode. Pick a move can select one, select several, or select all Top moves before goal generation. Both obey the same universal rules.

## Universal rules

- Always suggest 3 to 6 numbered, repo-grounded answers. Never ask an open question with no options. Exception: the Full surface map browse screen lists every surface as an index, not a 3-to-6 menu; it still carries `Agent recommends:` and the escapes.
- Always include an `Agent recommends:` line that names which listed option is the current best pick. It is a pointer to one of the options, never an extra numbered option.
- Every option-bearing work-selection question (L0-L4 and Pick a move's candidate screen) includes a `None of these, let me describe it` escape; every drill-down question after the first (L1 onward) also includes `Go back`. The one-time mode-selection and terminal post-save execution choice are exempt from both.
- Ground every option in actual findings, not generic categories.
- Recognition-first: the first screen shows the ranked Top 5 or the full map, never an abstract category menu.
- Two-channel freedom: every work-selection screen offers `show the full map` and `describe your own`; Explore mode also offers `back to candidates` at every level.
- Evidence with options: each option shows its evidence grade (confirmed/inferred/suspected) and a one-line basis next to any confidence word.
- Record the chosen mode in `04-question-funnel.md`; for Explore from scratch, record the full narrowing path. For Pick a move multi-select, record the raw selection input and grouping review options shown. Save answers to `05-user-answers.md`, including selected moves, accepted grouping, splits, merges, drops, and execution choice.
- Stop only when there is enough to write a measurable `/goal`.

## Mode selection (ask once)

```text
I mapped this repo and found <N> ranked candidates.
Top pick: <top candidate symptom> — <location> (<evidence_grade>, <confidence>).

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one or more   [recommended]
2. Explore from scratch drill down by intent → area → surface, ignoring my ranking

Agent recommends: <1 | 2> because <one-line reason from findings>.
Reply 1, 2, or "express"/"deep dive".
```

Recommend Pick a move when one high-confidence target stands out; recommend Explore for large or ambiguous repos. "express" → Pick a move, "deep dive" → Explore from scratch. If the user names a concrete target up front, jump straight to L4 (Boundaries) and confirm.

## Mode 1: Pick a move (candidate-first, default)

Show the ranked Top 5 from `03-synthesis.md` as evidence cards. The card must be understandable without reading hidden synthesis files: show the plain outcome/symptom, exact location, evidence grade and basis, likely fix shape, proof/checks, risk/protected areas, and grouping hint.

```text
Top moves (impact ÷ effort; confirmed > inferred > suspected):
 1. Outcome: <plain-language symptom or result>
    Location: <exact file:symbol/route/component>
    Evidence: <glyph> <evidence_grade> — <one-line basis>   confidence: <HIGH|MED|LOW>
    Likely fix shape: <validation/refactor/test/etc.>
    Proof/checks: <narrow verification commands; flag repo-code execution>
    Risk/protected areas: <blast radius; PROTECTED flagged>
    Grouping hint: <can group with ids because... / keep separate because...>
 2. Outcome: <plain-language symptom or result>
    Location: <exact location>
    Evidence: <glyph> <evidence_grade> — <basis>   confidence: <...>
    Likely fix shape: <fix shape>
    Proof/checks: <checks>
    Risk/protected areas: <risk>
    Grouping hint: <hint>
 ... up to 5 ...

Agent recommends: <option n> because <reason>.

Pick a move:
  • one: 1
  • several: 1,3,5
  • select all: all, a, 1-5, or 1,2,3,4,5

Or go sideways:
  • narrow by area/intent → Explore from scratch (L0)
  • show the full map     → Full surface map (below)
  • None of these: describe your own   (free text)
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
```

Accepted grouping produces a numbered goal pack in `06-goal-command.md`; split produces one goal per selected move. Adjusting selection re-runs the grouping review. If the final selection has one move, return to the single-goal flow.

Confidence-adaptive collapse — when one `high` candidate dominates, confirm instead of menu:

```text
One target dominates: <symptom> — <location> (<evidence_grade>, HIGH).
1. Confirm it and set boundaries
2. See the other <N> candidates
Agent recommends: 1.
None of these: describe your own.   show the full map
```

## Full surface map (shared browse screen)

The destination for every `show the full map`. Built from the per-domain surface index in `03-synthesis.md`; lists every surface as an index, not a 3-to-6 menu.

```text
Full surface map — grouped by domain (✓ confirmed  ~ inferred  ? suspected · count = findings)

Backend/Data
  b1. api/orders.py:POST /orders   ✓ duplicate-charge on retry   (3)
Frontend/Product
  f1. views/DashboardView.tsx      ✓ empty-state crash           (2)

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
Goal-readiness confidence: high
Next: how aggressive should the fix be?
```

Render this header before every level (L0–L4); the per-level screens below omit it only for brevity, never because it is skipped.

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
1. <glyph> <candidate #1 symptom> — <basis>   confidence: <HIGH|MED|LOW>
2. <glyph> <candidate #2 symptom> — <basis>   confidence: <HIGH|MED|LOW>
3. <glyph> <candidate #3 symptom> — <basis>   confidence: <HIGH|MED|LOW>

Agent recommends: <option n, highest-confidence candidate> because <reason>.
None of these: describe the area.
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

### L2. Surface (concrete surfaces from the repo)

```text
Within <domain>, which surface?
1. <real route/module/service/test> — <glyph> <strongest finding symptom here>
2. <real surface> — <glyph> <strongest finding symptom>
3. <real surface> — <glyph> <strongest finding symptom>

Agent recommends: <option n, best surface> because <reason>.
None of these: name the file/area.
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

### L3. Target (exact behavior/function/symptom)

If one clear target dominates, confirm rather than manufacture a menu:

```text
Best target: <glyph> <exact behavior/function/symptom> — <one-line basis> (<evidence_grade>, <confidence>).
1. Confirm this target
2. None of these: describe the precise behavior in your own words
Agent recommends: 1 because <one-line reason>.
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

Otherwise offer numbered targets plus `Agent recommends` and the escapes.

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

## Post-save execution choice (both modes)

Show this only after the recognition-first contract is accepted and `06-goal-command.md` has been written.

1. Show the saved goal or goal pack and wait.
2. Keep it saved; do not run until I explicitly approve. [default]
3. Run the saved goal now after showing the exact command. For a goal pack, ask which numbered goal to run first.
4. Audit only.

Default to option 2. Do not recommend option 3 merely because the user confirmed the goal, selected a narrow scope, or the goal looks safe; confirmation to save is not confirmation to run.

For a goal pack, default remains save first and ask before running. If the user approves execution, run one numbered goal at a time unless the user explicitly asks to run all goals in the pack.
