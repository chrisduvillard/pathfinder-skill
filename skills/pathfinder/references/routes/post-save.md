### Post-save execution choice (both modes)

Do not show this screen until the recognition-first contract is accepted and `06-goal-command.md` has been written. Then ask what to do with the saved goal or goal pack:

```text
1. Show the saved `/goal` command or goal pack and wait.
2. Keep it saved; do not run until I explicitly approve. [default]
3. Run the saved goal now after showing the exact command. For a goal pack, ask which numbered goal to run first.
4. Audit only, no implementation.
5. Run the saved goal now with Cross-Model Review enabled after showing the exact command and review packet plan.
```

Default to option 2 unless the user explicitly selects another mode. Do not recommend option 3 or option 5 merely because the user confirmed the goal, selected a narrow scope, or the goal looks safe; confirmation to save is not confirmation to run. For a goal pack, saving first and asking before running remains the default. If the user approves execution of a pack, proceed one goal at a time and ask before the next goal unless the user explicitly says to run all goals in the pack.

Option 5 enables Cross-Model Review for this run only. It runs the saved goal under the normal Phase 7 approval rules, then runs optional Phase 7b after a completed-claim or ordinary blocker. Option 5 does not authorize commits, pushes, PRs, merges, or protected-area changes.

### Option reservoir

Explore from scratch and the shared Boundaries question draw suggested answers from this reservoir; the Pick a move candidate cards come from `03-synthesis.md`, not this reservoir. Adapt and reorder based on actual findings; drop options that do not apply to the repo.

Strategic direction (reservoir A):

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

Product/business priority (reservoir B):

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

Scope and aggressiveness (reservoir C):

1. Very conservative: minimal safe fixes only.
2. Moderate: improve quality without changing architecture.
3. Ambitious: meaningful refactors allowed.
4. Creative: propose a better product/technical direction.
5. Agent recommendation.

Surface candidates (reservoir D), populate from the briefs:

- specific pages/routes
- specific components
- specific APIs
- specific services
- specific data pipelines
- specific tests
- specific flows

Protected areas (reservoir E):

- auth
- payments
- schema/migrations
- deployment
- public APIs
- data contracts
- styling system
- specific files
- specific user flows
- production configuration

Success criteria (reservoir F):

1. Tests pass.
2. Typecheck/lint/build pass.
3. Specific bug is fixed.
4. Specific page/flow is visibly better.
5. Specific edge cases are covered.
6. No public API/schema change.
7. No new dependencies.
8. Final diff is small and reviewable.
9. Playwright or integration checks pass where relevant.
10. Agent recommendation.
