## Phase 8: Final summary

Write `08-final-summary.md` with:

- What was explored.
- What the scouts found.
- Questions asked.
- User choices.
- Final goal path.
- Goal Binding summary and Binding Status for each saved goal.
- Runtime Boundary observed for any execution or handoff.
- Whether it was run.
- Files changed, if any.
- Checks run, if any.
- Remaining risks.
- Recommended next goal.

Exception: on the full-plugin prompt-to-goal fast path, do not write this file manually. The final `artifacts goal-saved` controller call validates and writes canonical JSON, renders this file and `06-goal-command.md` as deterministic views, then seals all four artifacts read-only so the call can remain the final filesystem write.

Also write `08-final-summary.json` using only `schemas/artifacts/final-summary.schema.json` fields. Keep its `mission_id` and `goal_id` identical to `06-goal-binding.json`; a saved but unexecuted Goal uses `final_state`/`disposition: goal-saved`, `binding_status`/`verification: not-run`, an empty `commit_ids` array, and `pr_url: null`. Validate the JSON before reporting success when the shipped schema and validator are available.

Final response to the user should include:

- The path to the work folder.
- The most important finding.
- The generated goal command path.
- Whether the goal was run.
- The next recommended step.
