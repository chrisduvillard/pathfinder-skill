# Question Funnel Template

Use after blind discovery, scout reports, synthesis, and the Top 5 candidate implementation goals.

## Candidate Goal Menu

List the Top 5 candidate implementation goals from `03-synthesis.md` first.

For each candidate include:

- measurable end state
- likely files/folders
- impact
- effort
- risk
- verification commands
- protected areas
- confidence

Ask the user to choose one candidate, combine candidates, reject all, or use the agent recommendation.

## Fast path

If the user wants the agent recommendation or does not want to answer many questions, ask one compact question:

```text
Recommended path: <candidate>. Choose:
1. Accept recommendation, conservative scope, ask before running.
2. Accept recommendation, moderate scope, ask before running.
3. Pick another candidate: <numbers>.
4. Audit only, no implementation.

Protected areas to avoid unless approved: <detected protected areas>. Reply with a number or edits.
```

Accept compact answers like “recommendation + conservative + ask before running.”

## A. Strategic direction

1. Fix the most important correctness/reliability issue.
2. Improve frontend/UI/UX.
3. Improve backend/API/data robustness.
4. Improve tests and regression protection.
5. Improve architecture and maintainability.
6. Improve performance.
7. Improve developer experience.
8. Improve security/config/auth hardening.
9. Work on a specific page, flow, feature, or bug.
10. Let the agent choose the highest ROI target.

## B. Product/business priority

1. More accurate results.
2. Better user experience.
3. More premium/polished interface.
4. Fewer bugs and edge cases.
5. Easier future development.
6. Faster app.
7. Safer deployment.
8. Better test coverage.
9. Better observability/debuggability.
10. Agent recommendation.

## C. Scope and aggressiveness

1. Very conservative.
2. Moderate.
3. Ambitious.
4. Creative.
5. Agent recommendation.

## D. Project-specific surface

Populate this with actual pages, components, APIs, pipelines, services, or tests discovered in the repo.

## E. Protected areas

Ask the user what must not be touched without approval.

## F. Success criteria

Offer concrete checks based on the actual repo, and flag whether each check requires executing repo code.

## G. Execution mode

1. Show final goal and wait.
2. Save goal, then ask before running.
3. Save and run automatically if aligned and no separate execution approval is required.
4. Audit only.
