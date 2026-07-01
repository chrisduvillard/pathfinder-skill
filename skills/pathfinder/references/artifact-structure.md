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

`06-goal-command.md` contains either one ready-to-copy `/goal` plus Implementation Goal fallback or a numbered goal pack, where each grouped goal has its own command, fallback, character count, selected candidate ids, and grouping rationale. It also records a **Goal Binding** section for the single goal or for each numbered goal. Goal Binding is supporting metadata, not part of the `/goal` character budget, and uses stable field names: `binding_id`, `objective_source`, `selected_candidate_ids`, `charter_roadmap_refs`, `scope_fingerprint`, `proof_requirements`, `protected_areas`, `runtime_boundary_required`, and `model_depth_summary` when autonomous mode derived the goal.

`00-session.md` and `07-run-log.md` record a **Runtime Boundary** section before execution or manual handoff. Use the fields `primary_runtime`, `tool_allowlist_enforced`, `sandbox_scope`, `network_access`, `credential_exposure`, `repo_code_execution`, and `pre_execution_consent`. The section discloses authority and exposure; it does not claim Pathfinder can enforce sandboxing that the underlying runtime cannot enforce.

`07-run-log.md`, `07b-cross-model-review.md`, and `08-final-summary.md` record **Binding Status** for each saved goal. Allowed statuses are `matched` when evidence matches the saved Goal Binding, `missing` when the binding or required proof evidence was not produced, `stale-objective` when execution followed a materially different objective, `mismatched` when changed files/checks/protected areas conflict with the binding, and `not-run` when the goal was saved but not executed.

In the prompt-to-goal track (see "Track B: Prompt-to-goal" in `SKILL.md`), the same numbered files are reused with track-appropriate content: `00-session.md` also records the verbatim user prompt and the routing decision; `01-blind-discovery.md` holds the targeted prompt-anchored research instead of a blind sweep; the `02-scout-briefs/` folder, `03-synthesis.md`, and `03b-verification.md` are short placeholders because the scouts, Top-5 ranking, and Phase 4b verification do not run; and `04-question-funnel.md` / `05-user-answers.md` record the gap-driven clarifying questions and answers. `06-goal-command.md`, `07-run-log.md`, `07b-cross-model-review.md`, and `08-final-summary.md` are produced exactly as in the full-exploration track; `07b-cross-model-review.md` remains a placeholder unless review is enabled and execution reaches a completed-claim or ordinary blocker.

`07b-cross-model-review.md` records Cross-Model Review only when review is enabled for the run and execution reaches a completed-claim or ordinary blocker. Its packet includes the saved Goal Binding, Runtime Boundary, Binding Status, protected-area status, and any `complexity_notes` surfaced by the primary executor. Its launch mode is `launched`, `manual-handoff`, `skipped`, or `failed-to-launch`. Its final disposition is `clean`, `fixed-clean`, `needs-primary-followup`, `needs-user-review`, `blocked`, or `skipped`.

In autonomous mode (see “Autonomous mode” in `SKILL.md`), the same numbered files are reused: `04-question-funnel.md` / `05-user-answers.md` record the selection from the sanitized creator model/roadmap, the ambiguity ledger and each loop pass, and any manual exclusions; `07-run-log.md` records the per-goal execution loop (branch, commands, exit results, verifier verdict, Runtime Boundary, Binding Status, push/PR/merge outcome) and roadmap updates; `07b-cross-model-review.md` records any optional Cross-Model Review packet, launch mode, verdicts, fixes, and disposition before publication; and `08-final-summary.md` adds the final shipped/blocked ledger (one row per goal: autonomous disposition, the item's roadmap class (`autonomous-eligible` or `manual-approval`/`manual-only`), the needs-review reason when applicable, Binding Status, PR URL, CI status, verification verdict, cross-model review disposition when run, and the next input for anything not merged). A goal's **autonomous disposition** is one of `merged` (an `autonomous-eligible` goal that passed the default-deny self-merge gate), `awaiting-review` (committed, pushed, and opened as a PR for human review — the terminus for every `manual-approval`/`manual-only` item and for any contested-but-not-vetoed verdict), `blocked` (a per-goal block before commit/push), or `excluded` (a hard-safety-floor item that was never worked, with its reason).

The Deep Intent Gate introduces no new numbered artifact: `04-question-funnel.md` / `05-user-answers.md` record the evidence draft, first-run interview, the ambiguity ledger and each loop pass, reconcile screens, refresh answers, and any `continue later` partial state. `00-session.md` records the charter and roadmap status (including the `completion` and `clarity` values for both intent files) plus the ignore decision. `.pathfinder/charter.md` and `.pathfinder/roadmap.md` are separate stable, local-only, never-committed files outside the run folder and are **not** part of the 00-08 artifact set.

Artifact folders should be ignored locally and should not be committed or pushed unless the user explicitly requests publication after review.
