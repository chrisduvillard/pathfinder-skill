# Repo Adjutant Artifact Structure

```text
.agent-work/repo-adjutant/YYYYMMDD-HHMM-<short-task-slug>/
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

Artifact folders should be ignored locally and should not be committed or pushed unless the user explicitly requests publication after review.
