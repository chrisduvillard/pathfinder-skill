# Pathfinder Artifact Structure

```text
.agent-work/pathfinder/YYYYMMDD-HHMM-<short-task-slug>/
  00-session.md
  01-blind-discovery.md
  02-scout-briefs/
    architecture-scout.md
    frontend-product-scout.md
    backend-data-scout.md
    testing-reliability-scout.md
    dx-security-scout.md
  03-synthesis.md
  04-question-funnel.md
  05-user-answers.md
  06-goal-command.md
  07-run-log.md
  08-final-summary.md
```

If a phase has not been reached yet, create a short placeholder rather than implying completion.

`04-question-funnel.md` records the chosen interview mode (Pick a move or Explore from scratch) and, for Explore from scratch, the full narrowing path (L0 intent through L4 boundaries) with the options offered at each level. `05-user-answers.md` records the user's selections, including any backtracking.

Artifact folders should be ignored locally and should not be committed or pushed unless the user explicitly requests publication after review.
