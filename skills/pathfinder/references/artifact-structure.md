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
  03b-verification.md
  04-question-funnel.md
  05-user-answers.md
  06-goal-command.md
  07-run-log.md
  07b-cross-model-review.md
  08-final-summary.md
```

If a phase has not been reached yet, create a short placeholder rather than implying completion. `03b-verification.md` follows the same rule (placeholder text: "verification not run yet"). `07b-cross-model-review.md` also follows the placeholder rule (placeholder text: "cross-model review not run").

`04-question-funnel.md` records the chosen interview mode (Pick a move or Explore from scratch) and, for Explore from scratch, the full narrowing path (L0 intent through L4 boundaries) with the options offered at each level. For Pick a move multi-select, it records the raw selection input and grouping review options shown.

`05-user-answers.md` records the user's selections, including any backtracking. For multi-select, it records selected moves, accepted grouping, splits, merges, drops, and execution choice.

`06-goal-command.md` contains either one ready-to-copy `/goal` plus Implementation Goal fallback or a numbered goal pack, where each grouped goal has its own command, fallback, character count, selected candidate ids, and grouping rationale.

In the prompt-to-goal track (see "Track B: Prompt-to-goal" in `SKILL.md`), the same numbered files are reused with track-appropriate content: `00-session.md` also records the verbatim user prompt and the routing decision; `01-blind-discovery.md` holds the targeted prompt-anchored research instead of a blind sweep; the `02-scout-briefs/` folder, `03-synthesis.md`, and `03b-verification.md` are short placeholders because the scouts, Top-5 ranking, and Phase 4b verification do not run; and `04-question-funnel.md` / `05-user-answers.md` record the gap-driven clarifying questions and answers. `06-goal-command.md`, `07-run-log.md`, and `08-final-summary.md` are produced exactly as in the full-exploration track.

In autonomous mode (see “Autonomous mode (opt-in)” in `SKILL.md`), the same numbered files are reused: `04-question-funnel.md` / `05-user-answers.md` record the selection from the sanitized creator model/roadmap and any manual exclusions; `07-run-log.md` records the per-goal execution loop (branch, commands, exit results, verifier verdict, push/PR/merge outcome) and roadmap updates; `07b-cross-model-review.md` records any optional Cross-Model Review packet, launch mode, verdicts, fixes, and disposition before publication; and `08-final-summary.md` adds the final shipped/blocked ledger (one row per goal: disposition, PR URL, CI status, verification verdict, cross-model review disposition when run, and the next input for anything not merged). No new artifact filenames are introduced.

The Deep Intent Gate introduces no new numbered artifact: `04-question-funnel.md` / `05-user-answers.md` record the evidence draft, first-run interview, reconcile screens, refresh answers, and any `continue later` partial state. `00-session.md` records the charter and roadmap status plus the ignore decision. `.pathfinder/charter.md` and `.pathfinder/roadmap.md` are separate stable, local-only, never-committed files outside the run folder and are **not** part of the 00-08 artifact set.

Artifact folders should be ignored locally and should not be committed or pushed unless the user explicitly requests publication after review.
