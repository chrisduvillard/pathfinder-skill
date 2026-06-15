# Question Funnel Template

Use after blind discovery, scout reports, synthesis, and the Top 5 candidate implementation goals.

Pathfinder runs one of two user-selectable modes. Ask which mode to use first, then follow that mode. Both modes obey the same universal rules.

## Universal rules

- Always suggest 3 to 6 numbered, repo-grounded answers. Never ask an open question with no options.
- Always include an `Agent recommends:` line that names the current best pick.
- Always include two escapes: `None of these, let me describe it` and `Go back`.
- Ground every option in actual findings, not generic categories.
- Record the chosen mode in `04-question-funnel.md`; for Deep dive, record the full narrowing path. Save answers to `05-user-answers.md`.
- Stop only when there is enough to write a measurable `/goal`.

## Mode selection (ask once)

```text
Two ways to proceed:
1. Express      one compact question, fastest, good when the target is fairly clear
2. Deep dive    a short guided drill-down from broad intent to the exact target

Agent recommends: <Express | Deep dive> because <one-line reason from findings>.
Reply 1, 2, or "express"/"deep dive".
```

Recommend Deep dive for large or ambiguous repos with several plausible targets; recommend Express when one high-confidence target stands out. If the user names a concrete target up front, jump straight to L4 (Boundaries) and confirm.

## Express mode

One compact question, then generate the goal.

```text
Recommended path: <top candidate from 03-synthesis.md>.
1. Accept recommendation, conservative scope, ask before running.
2. Accept recommendation, moderate scope, ask before running.
3. Pick another candidate: <numbers for the other Top 5 candidates>.
4. Audit only, no implementation.
None of these: describe the target in your own words.

Protected areas to avoid unless approved: <detected protected areas>.
Reply with a number or edits.
```

Accept compact answers like "recommendation + conservative + ask before running".

## Deep dive mode

One question per level. Hard cap of five levels (L0 to L4) before execution mode. Each level's options are conditioned on the previous answer and generated from the scout briefs.

Scout backbone: Architecture, Frontend/Product, Backend/Data, Testing/Reliability, Developer Experience/Security.

Before each question, show the narrowing trail and a confidence signal:

```text
Path so far: fix → backend/data → POST /orders handler → duplicate-charge on retry
Goal-readiness confidence: high
Next: how aggressive should the fix be?
```

### L0. Intent

```text
1. Fix a correctness/reliability defect
2. Improve a product/UX surface
3. Improve backend/API/data robustness
4. Improve tests and regression protection
5. Improve architecture/maintainability
6. Improve performance
7. Improve developer experience
8. Harden security/config/auth
9. Agent picks the highest-ROI outcome
```

### L1. Domain (real candidates from the owning scout)

```text
Given "<intent>", the strongest candidates from scouting:
1. <candidate #1 with symptom and confidence>
2. <candidate #2 ...>
3. <candidate #3 ...>
4. Agent recommends: <highest-confidence candidate>
None of these: describe the area.
```

### L2. Surface (concrete surfaces from the repo)

```text
Within <domain>, which surface?
1. <real route/module/service/test>
2. <real surface ...>
3. <real surface ...>
4. Agent recommends: <best surface> because <reason>
None of these: name the file/area.
```

### L3. Target (exact behavior/function/symptom)

If one clear target dominates, confirm rather than manufacture a menu:

```text
Best target: <exact behavior/function/symptom>.
1. Confirm this target
2. Adjust it: describe the precise behavior
Go back
```

Otherwise offer numbered targets plus `Agent recommends` and the escapes.

### L4. Boundaries (scoped to the target)

```text
For <target>, set the boundaries:
- Scope: 1) very conservative  2) moderate  3) ambitious  4) creative  (agent recommends: <n>)
- Protect (avoid without approval): <detected protected areas for this target>
- Done when: <2-3 concrete checks from the repo, flagged if they need to run repo code>
Reply with edits, or "accept agent recommendation".
```

### Adaptive stopping

- If goal-readiness confidence is already high before L3, skip to L4.
- If confidence is still low after L3, ask one extra sharpening question at the same altitude.
- If the user keeps choosing `Agent recommends`, commit to the highest-confidence path and stop asking.
- `Go back` re-presents the previous question without restarting the funnel.

## Execution mode (both modes)

1. Show the final goal and wait.
2. Save the goal, then ask before running.
3. Save and run automatically if aligned and no separate execution approval is required.
4. Audit only.

Default to option 2.
