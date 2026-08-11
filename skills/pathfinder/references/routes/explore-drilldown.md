### Mode 2: Explore from scratch (conditioned drill-down)

Run a guided drill-down. Ask exactly one question per level. Hard cap of five levels (L0 through L4) before Phase 6 goal confirmation and the post-save execution choice. Each level's options are conditioned on the previous answer and generated from the scout briefs, not from a fixed list.

The selected scout domains form the branching backbone. Choose them from the five-domain reservoir:

- Architecture Scout
- Frontend/Product Scout
- Backend/Data Scout
- Testing/Reliability Scout
- Developer Experience/Security Scout

Show only selected domains with real candidates. Intent supplies the lens; the scout that owns the chosen domain supplies the menu content for the next level.

Before each question, show a compact narrowing trail and a confidence signal:

```text
Path so far: fix → backend/data → POST /orders handler → duplicate-charge on retry
Goal-readiness confidence: high (Verified: <verdict>)
Next: how aggressive should the fix be?
```

`Goal-readiness confidence` is the agent's estimate of whether it can already write a measurable `/goal`. Use it for adaptive stopping (see below); only trigger adaptive early-stopping when goal-readiness is high AND verified.

Render this trail-and-confidence header before every level below (L0 through L4). The per-level example screens omit it only for brevity; it is shown each time, never skipped. When a charter is loaded, each candidate-bearing Explore option also carries the same `Aligns:` north-star token as the Pick a move card (omit when neutral), so charter alignment is not mode-dependent.

#### L0. Intent

Ask what kind of outcome the user wants. List only intents that have at least one real candidate, annotate each with its candidate count and confirmed-only count from the post-verification intent tally in `03b-verification.md` when Phase 4b is `complete`, else the Phase 4 intent tally in `03-synthesis.md`, and draw wording from reservoir A/B. Always include `Agent recommends` and the lateral moves.

```text
1. Fix a correctness/reliability defect      → <n> candidates (<m> confirmed)
2. Improve a product/UX surface              → <n> candidates
3. Improve backend/API/data robustness       → <n> candidates
... only intents that have candidates, annotated with counts ...
9. Agent picks the highest-ROI outcome

Agent recommends: <option n> because <one-line reason from findings>.
None of these: describe the outcome you want.
back to candidates: return to the ranked Top 5.   show the full map   ignore objectives (when a charter is loaded)
```

#### L1. Domain

Given the intent, present the candidates owned by the relevant scout(s), ranked by impact ÷ effort using the synthesis values (the same order as the Mode 1 Top moves); each option line shows its evidence grade and confidence. These options are real findings, not categories.

```text
Given "fix a defect", the strongest candidates from scouting (glyph = evidence grade: ✓ confirmed, ~ inferred, ? suspected):
1. <glyph> <candidate #1 symptom> — <one-line evidence basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>
2. <glyph> <candidate #2 symptom> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>
3. <glyph> <candidate #3 symptom> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>

Agent recommends: <option n, the highest-confidence candidate> because <reason>.
None of these: describe your own — the area you care about.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map   ignore objectives (when a charter is loaded)
```

#### L2. Surface

Within the chosen domain, present concrete surfaces discovered in the repo: specific routes, modules, services, components, pipelines, or test files. Draw the surface categories from reservoir D (Surface candidates), populated from the scout briefs.

```text
Within <chosen domain>, which surface?
1. <real route/module/service/test from the briefs> — <glyph> <strongest finding symptom here>   Verified: <verdict>
2. <real surface> — <glyph> <strongest finding symptom>   Verified: <verdict>
3. <real surface> — <glyph> <strongest finding symptom>   Verified: <verdict>

Agent recommends: <option n, the best surface> because <reason>.
None of these: describe your own — name the file/area.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map   ignore objectives (when a charter is loaded)
```

#### L3. Target

Within the chosen surface, pin the exact behavior, function, or symptom. This is where precision is won.

- If scouting converges on one clear target with high confidence, do not manufacture a multi-option menu. Instead present a single confirm:

```text
Best target: <glyph> <exact behavior/function/symptom, e.g. empty-state crash in
DashboardView.loadData when the payload is empty> — <one-line evidence basis> (<evidence_grade>, <confidence>).
Verified: <verdict>.
1. Confirm this target
2. None of these: describe your own — the precise behavior
Agent recommends: 1 because <one-line reason the target is the right call from the findings>.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map   ignore objectives (when a charter is loaded)
```

- If several plausible targets remain, offer them as numbered options plus an `Agent recommends:` line and the escapes:

```text
Within <surface>, which exact target?
1. <glyph> <behavior/function/symptom #1> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>
2. <glyph> <behavior/function/symptom #2> — <basis>   confidence: <HIGH|MED|LOW>   Verified: <verdict>

Agent recommends: <option n> because <reason>.
None of these: describe your own — the precise behavior.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map   ignore objectives (when a charter is loaded)
```

#### L4. Boundaries

Now that the target is concrete, ask one combined question for scope aggressiveness, protected areas, and success criteria, scoped tightly to that target. Draw from reservoirs C, E, and F.

```text
For <target>, set the boundaries:
- Scope: 1) very conservative  2) moderate  3) ambitious  4) creative
- Protect (avoid without approval): <detected protected areas relevant to this target>
- Done when: <2-3 concrete checks discovered from the repo, flagged if they need to run repo code>
Agent recommends: Scope 2 (moderate) because <one-line reason from findings>.
None of these: describe your own — the scope, protected areas, or success criteria.
Reply with edits, "accept agent recommendation", "go back" to revise the target, "back to candidates" to return to the ranked Top 5, "show the full map", or "ignore objectives" (when a charter is loaded).
```

#### Adaptive stopping

- If goal-readiness confidence is already high before reaching L3 (the target is unambiguous), skip ahead to L4.
- If confidence is still low after L3, ask one extra sharpening question at the same altitude rather than proceeding with a vague target. Never exceed the five-level cap by more than this single clarifier.
- If the user repeatedly chooses `Agent recommends`, commit to the highest-confidence path and stop asking. Never loop.
- Support `Go back` at any level by re-presenting the previous question with the prior answer noted, without restarting the whole funnel.
- `back to candidates` and `show the full map` are available at every level: the first re-presents Mode 1's ranked Top 5, the second opens the Full surface map browse screen. Neither restarts the funnel.
