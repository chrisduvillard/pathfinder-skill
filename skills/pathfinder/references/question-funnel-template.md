# Question Funnel Template

Use after blind discovery, scout reports, synthesis, and the Top 5 candidate implementation goals.

Pathfinder runs one of two user-selectable modes: Pick a move (candidate-first, default; alias "express") and Explore from scratch (drill-down; alias "deep dive"). Ask which mode to use first — leading with the strongest finding — then follow that mode. Pick a move can select one, select several, or select all Top moves before goal generation. Both obey the same universal rules.

This template is the interactive funnel. In autonomous mode (see "Autonomous mode" in `SKILL.md`) the Deep Intent Gate may ask first-run creator-model questions before hands-off execution continues; the work-selection screens below do not run. After the gate resolves clarity (`clarity: resolved`), autonomous mode selects goals from the sanitized charter plus roadmap — by explicit invocation or by auto-escalation — and runs continuous execution until a stop condition is reached.

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

## Phase 4c: Deep Intent Gate (runs before entry-point continuation)

When `.pathfinder/charter.md` or `.pathfinder/roadmap.md` is missing, schema-invalid, incomplete, marked `clarity: unresolved` with a still-open blocking unknown, explicitly refreshed, or contradicted by a light re-inference of current evidence (a charter non-goal now has implementing code, or a stable field the code now contradicts — a stale intent model, caught on every work-producing entry and re-opened as a blocking unknown), Phase 4c runs the Deep Intent Gate before the requested entry point continues. The first-run gate asks by default. It is not a skippable offer. If the user chooses `continue later`, save partial answers, mark unanswered fields incomplete, and stop before continuing. The gate keeps an ambiguity ledger and loops the interview until zero blocking unknowns remain; a blocking unknown the user cannot resolve is converted to a roadmap Open Question and its item marked `blocked` on creator input (the anti-deadlock rule), so the loop always terminates. Clarity becomes `clarity: resolved` only when both files are `completion: complete`, the ledger has no open blocking unknowns, and the model-depth proof gate passes.

The gate opens with an evidence draft, then asks a recognition-first interview that usually spans 8 to 12 compact screens. Every screen shows inferred answers with evidence and confidence, offers 3 to 6 concrete options where possible, includes `Agent recommends:`, includes free text, and asks directly about future capabilities not started yet.

```text
Deep Intent Gate - Evidence draft
I found this current project shape:
1. Purpose: <inferred purpose>   confidence: <confirmed|inferred|suspected>   basis: <file/git/doc basis>
2. Users: <inferred users>       confidence: <...>                            basis: <basis>
3. Constraints: <inferred constraints>   confidence: <...>                    basis: <basis>

The repo cannot tell me these future-facing parts:
- future capabilities not started yet
- roadmap priority and sequencing
- optional finished state
- autonomy policy

Agent recommends: continue the Deep Intent Gate now because every Pathfinder entry point needs the creator model.
Reply "continue" to answer now, or "continue later" to save a partial model and stop.
```

The normal screens are below. Keep them compact: each screen mirrors the best inferred answer first, names the evidence and confidence, offers 3 to 6 concrete choices where possible, includes `Agent recommends:`, and keeps both a free-text escape and `continue later`.

### Screen 1 - Purpose and promise

- Purpose: establish the north-star and the primary promise that must feel true when Pathfinder works.
- Mirror evidence: inferred purpose from `SKILL.md`, plugin manifests, README/product copy, and recurring verification gates.
- Options: 1) keep the inferred purpose, 2) tighten it around safety and bounded goals, 3) tighten it around autonomous PR delivery, 4) replace it with a creator-supplied promise.
- Agent recommends: the most code/scout-grounded option, usually the inferred purpose.
- Escape: `None of these - describe the purpose and promise yourself`, or `continue later`.

### Screen 2 - Primary users and excluded users

- Purpose: name who the skill optimizes for and who it should not optimize for.
- Mirror evidence: installation surfaces, invocation examples, plugin interface copy, support templates, and docs that identify Claude Code/Codex users.
- Options: 1) developers exploring unfamiliar repos, 2) agent operators converting tasks into goals, 3) maintainers running safe autonomous work, 4) add secondary users, 5) name excluded users.
- Agent recommends: the option best supported by installed/invocation surfaces.
- Escape: `None of these - describe users and excluded users yourself`, or `continue later`.

### Screen 3 - Key journeys and must-work flows

- Purpose: capture the journeys that must stay reliable across releases.
- Mirror evidence: supported invocation paths, artifact pipeline, prompt-to-goal routing, autonomous mode loop, and plugin default prompts.
- Options: 1) explore repo -> ranked candidates -> goal, 2) prompt -> targeted research -> goal, 3) autonomous -> roadmap goal -> PR ledger, 4) refresh creator model, 5) name another must-work flow.
- Agent recommends: the journey with the strongest source and docs evidence.
- Escape: `None of these - describe key journeys yourself`, or `continue later`.

### Screen 4 - Durable success metrics and quality bars

- Purpose: define stable measures of success and non-negotiable quality bars.
- Mirror evidence: `/goal` budget, proof/check requirements, verification panel, safety filters, and CI validation scripts.
- Options: 1) every run ends in a bounded goal or clear ledger, 2) generated goals stay under 3900 chars and include proof, 3) verified candidates are evidence-backed, 4) autonomous work never bypasses safety gates, 5) name another quality bar.
- Agent recommends: the option that best matches the repo's current guardrails.
- Escape: `None of these - describe metrics and quality bars yourself`, or `continue later`.

### Screen 5 - Future capabilities not started yet

- Purpose: ask for desired capabilities the repository cannot reveal.
- Mirror evidence: gaps from scout findings, roadmap template empty slots, issue themes, and docs/spec plans; mark repo-only guesses as suspected.
- Options: 1) more accurate candidate ranking, 2) better Deep Intent Gate UX, 3) stronger autonomous safety verification, 4) better Codex/Claude install experience, 5) no future capability right now, 6) creator-supplied capability.
- Agent recommends: do not recommend a docs-only guess; recommend the strongest code/scout-grounded gap or ask the creator to supply one.
- Escape: `None of these - describe future capabilities yourself`, or `continue later`.

### Screen 6 - Roadmap priorities and sequencing

- Purpose: turn desired work into ordered roadmap items with dependencies.
- Mirror evidence: verified candidates, existing roadmap items, open blockers, recent changelog themes, and creator-stated urgency.
- Options: 1) highest safety/quality risk first, 2) highest user-visible value first, 3) smallest safe autonomous item first, 4) blocked/manual items first for clarification, 5) creator-supplied ordering.
- Agent recommends: the highest-value option that is not blocked by safety or ambiguity.
- Escape: `None of these - describe priority and sequencing yourself`, or `continue later`.

### Screen 7 - Constraints and protected areas

- Purpose: record boundaries that require approval or must not change.
- Mirror evidence: stop conditions, CODEOWNERS, security docs, workflows, manifests, scripts, schemas, auth/payment/secret surfaces, and user-stated constraints.
- Options: 1) preserve public invocation and `/goal` contract, 2) protect CI/release/scripts/manifests, 3) avoid new dependencies, 4) avoid auth/payments/migrations/secrets/public APIs, 5) add project-specific protected files.
- Agent recommends: the strictest code-backed safety boundary.
- Escape: `None of these - describe constraints and protected areas yourself`, or `continue later`.

### Screen 8 - Non-goals and tradeoffs

- Purpose: state what Pathfinder should not optimize for and what tradeoffs are acceptable.
- Mirror evidence: safety model, README positioning, stop conditions, roadmap template, and previous non-goal statements.
- Options: 1) not a general unattended coding bot, 2) not a shared roadmap/product-board replacement, 3) favor reviewability over broad refactors, 4) favor safety over speed, 5) creator-supplied non-goal.
- Agent recommends: the non-goal that most directly protects the current safety model.
- Escape: `None of these - describe non-goals and tradeoffs yourself`, or `continue later`.

### Screen 9 - Optional finished state

- Purpose: decide whether the project has a final desired state or ongoing standing qualities.
- Mirror evidence: README positioning, release notes, roadmap items, and recurring quality bars.
- Options: 1) ongoing product with standing safety/quality bars, 2) finished when core entry paths are stable, 3) finished when autonomous roadmap execution is reliable, 4) no fixed finished state, 5) creator-supplied final state.
- Agent recommends: the option best supported by project shape and roadmap evidence.
- Escape: `None of these - describe the finished state yourself`, or `continue later`.

### Screen 10 - Autonomy policy and manual-approval boundaries

- Purpose: define what may run unattended, what needs approval, and what must never run unattended.
- Mirror evidence: autonomous-mode safety rules, roadmap safety classifications, CODEOWNERS, protected files, credential separation, and branch-protection/self-merge rules.
- Options: 1) autonomous only for explicitly marked `autonomous-eligible` roadmap items, 2) manual approval for scripts/workflows/manifests/public interfaces, 3) never unattended for dangerous categories, 4) stop on ambiguity or missing provenance, 5) creator-supplied autonomy policy.
- Agent recommends: the strictest option that still permits safe low-risk work.
- Escape: `None of these - describe autonomy policy yourself`, or `continue later`.

### Ambiguity loop screen (repeats until no blocking unknowns)

After the normal screens, run the ambiguity-resolution loop. Maintain an **ambiguity ledger** of unknowns, each tagged `blocking` or `non-blocking`, and regenerate targeted screens aimed only at the still-open blocking unknowns until none remain.

```text
Deep Intent Gate - Clarity check
Open blocking unknowns (must clear before autonomy):
1. <unknown> - affects <charter/roadmap field or item> - basis: <evidence>
2. <unknown> - affects <...> - basis: <...>

For each, pick the answer that removes the doubt:
- <3 to 6 concrete options grounded in repo evidence>
Agent recommends: <the option that best removes the blocking doubt>.
Escape: None of these - describe it yourself; continue later; or
"I can't answer this" to convert it to a roadmap Open Question (the item becomes
`blocked` on creator input and is excluded from unattended work until answered, and
clarity resolves for the rest).
```

Clarity resolves (`clarity: resolved`) only when every blocking unknown is resolved or converted.

Record the screens in `04-question-funnel.md`, the ratified answers in `05-user-answers.md`, stable creator intent in `.pathfinder/charter.md`, and evolving desired work in `.pathfinder/roadmap.md`. Also record the ambiguity ledger, each loop pass, the final `clarity` value on both files, and any blocking-unknown conversions to roadmap Open Questions.

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
None of these: describe the area you care about.
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

Before saving, the Phase 6 recognition-first contract must show proof, protected areas, and runtime authority as separate lines with confirmed/inferred/missing provenance. Do not ask extra questions for Runtime Boundary fields the environment already supplies; derive them from the current runtime, sandbox, repo-code execution plan, and consent state, and mark unknown fields as unknown instead of blocking goal saving.

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

Ask only after `06-goal-command.md` is saved:

```text
1. Show the saved goal or goal pack and wait.
2. Keep it saved; do not run until I explicitly approve. [default]
3. Run the saved goal now after showing the exact command. For a goal pack, ask which numbered goal to run first.
4. Audit only, no implementation.
5. Run the saved goal now with Cross-Model Review enabled after showing the exact command and review packet plan.
```

Default to option 2. Do not recommend option 3 or option 5 merely because the user confirmed the goal, selected a narrow scope, or the goal looks safe; confirmation to save is not confirmation to run.

For a goal pack, default remains save first and ask before running. If the user approves execution, run one numbered goal at a time unless the user explicitly asks to run all goals in the pack.

Option 5 enables Cross-Model Review for this run only. It writes `07b-cross-model-review.md`, then runs or hands off the optional Phase 7b review after a completed-claim or ordinary blocker. It does not authorize commits, pushes, PRs, merges, or protected-area changes.
