# Pathfinder Artifact Structure

```text
.agent-work/pathfinder/YYYYMMDD-HHMM-<short-task-slug>/
  00-session.md
  01-blind-discovery.md
  02-scout-briefs/                 # selected domains only
    architecture-scout.md          # only if selected
    frontend-product-scout.md      # only if selected
    backend-data-scout.md          # only if selected
    testing-reliability-scout.md   # only if selected
    dx-security-scout.md           # only if selected
  03-synthesis.md
  03b-verification.md
  04-question-funnel.md
  05-user-answers.md
  06-goal-command.md
  07-run-log.md
  07b-cross-model-review.md
  08-final-summary.md
  03-candidates.json
  03b-verification.json
  06-goal-binding.json
  07-run-log.json
  08-final-summary.json
```

Controller-owned JSON is the source of truth; Markdown is its human-readable run view. The existing structured sidecar filenames remain compatibility views of that state. Validate JSON before rendering Markdown. A Markdown artifact must never be parsed back into authoritative mission state.

This direction is mechanically guarded in production. The only allowed Markdown parsers are the explicit legacy intent migration and generated candidate/verification region replacement; the latter may preserve surrounding narrative only while replacing a controller-generated block from validated JSON. Tests, deterministic eval assertions, instruction validators, and golden comparisons may read Markdown because they verify output rather than own state. Add new machine facts to a versioned JSON schema, never to the production-reader allowlist.

When a full plugin is installed, load the matching files under `schemas/artifacts/` before writing sidecars and validate each sidecar against its schema before reporting success. Never invent route-specific top-level JSON fields. A manual skill-only install without schemas must preserve the canonical field names documented here and disclose that validation was unavailable.

For a full-plugin prompt Goal, never hand-author `06-goal-binding.json` or `08-final-summary.json`; also never hand-author `06-goal-command.md` or `08-final-summary.md`. Put the complete approved single-line objective and structured inputs in `.prompt-goal-request.json`. The bundled controller's `artifacts goal-saved` command validates and writes the canonical JSON, deterministically renders both Markdown views from it, seals all four artifacts, and must be the final filesystem write before the route reports success.

Structured sidecar purposes:

- `03-candidates.json`: stable candidate ids, source finding ids, evidence grade, expected value, risk/protected areas, proof availability, uncertainty, ranking basis, rejected/refill status, and search stop reason.
- `03b-verification.json`: verifier depth, lenses run or skipped, verdicts, downgrades, rejects, adjudication, proof gaps, and final candidate status.
- `06-goal-binding.json`: Goal Binding fields, selected capability profile, chosen goal surface (`/goal`, native Codex goal, or Implementation Goal fallback), character budget, proof requirements, and protected-area obligations.
- `07-run-log.json`: Runtime Boundary, commands/results, structured completion claim, Binding Status, verifier/reviewer disposition, and publication gates.
- `08-final-summary.json`: final shipped/blocked/excluded ledger, residual risks, next input needed, and replay pointers to the artifacts above.

Create only the applicable parts of the tree above, progressively. In full exploration, `01-blind-discovery.md` records the selected and skipped scout domains plus reasons; `02-scout-briefs/` contains compact briefs only for selected domains, and expanded narrative is optional. If an expected phase has started but not completed, its human artifact carries a short in-progress marker rather than implying completion. `03b-verification.md` is absent before Phase 4b, starts with `verification: in-progress`, and becomes `complete` only after the selected verification depth finishes. `07b-cross-model-review.md` is absent unless review is enabled and started, then records that it is in progress until a disposition exists. Never create a placeholder for a phase the selected route intentionally skips, an unselected scout domain, or a future lifecycle state.

`04-question-funnel.md` records the chosen interview mode (Pick a move or Explore from scratch) and, for Explore from scratch, the full narrowing path (L0 intent through L4 boundaries) with the options offered at each level. For Pick a move multi-select, it records the raw selection input and grouping review options shown.

`05-user-answers.md` records the user's selections, including any backtracking. For multi-select, it records selected moves, accepted grouping, splits, merges, drops, and execution choice.

`06-goal-command.md` contains either one ready-to-copy `/goal` plus Implementation Goal fallback or a numbered goal pack, where each grouped goal has its own command, fallback, character count, selected candidate ids, and grouping rationale. It also records a **Goal Binding** section for the single goal or for each numbered goal. Goal Binding is supporting metadata, not part of the `/goal` character budget, and uses stable field names: `binding_id`, `objective_source`, `selected_candidate_ids`, `charter_roadmap_refs`, `doctrine_refs`, `capability_profile`, `scope_fingerprint`, `proof_requirements`, `protected_areas`, `runtime_boundary_required`, and `model_depth_summary` when autonomous mode derived the goal.

`00-session.md` and `07-run-log.md` record a **Runtime Boundary** section before execution or manual handoff. Use the fields `primary_runtime`, `mission_worktree` when autonomous mode runs, `tool_allowlist_enforced`, `sandbox_scope`, `network_access`, `credential_exposure`, `repo_code_execution`, and `pre_execution_consent`. The section discloses authority and exposure; it does not claim Pathfinder can enforce sandboxing that the underlying runtime cannot enforce.

`07-run-log.md`, `07b-cross-model-review.md`, and `08-final-summary.md` record **Binding Status** for each saved goal. Allowed statuses are `matched` when evidence matches the saved Goal Binding, `missing` when the binding or required proof evidence was not produced, `stale-objective` when execution followed a materially different objective, `mismatched` when changed files/checks/protected areas conflict with the binding, and `not-run` when the goal was saved but not executed.

In the prompt-to-goal track (see "Track B: Prompt-to-goal" in `SKILL.md`), a zero-clarification, no-execution run writes only `00-session.md`, `01-blind-discovery.md`, `06-goal-command.md`, `06-goal-binding.json`, `08-final-summary.md`, and `08-final-summary.json`. The first file records the verbatim prompt and routing decision; the second holds targeted prompt-anchored research. Omit `02-scout-briefs/`, `03-synthesis.md`, `03-candidates.json`, `03b-verification.md`, and `03b-verification.json` because their absence means not applicable on this route. Add `04-question-funnel.md` and `05-user-answers.md` only when clarification occurs. Add `07-run-log.md`, `07-run-log.json`, or `07b-cross-model-review.md` only after execution or a manual execution handoff.

`07b-cross-model-review.md` records Cross-Model Review only when review is enabled for the run and execution reaches a completed-claim or ordinary blocker. Its packet includes the saved Goal Binding, Runtime Boundary, Binding Status, protected-area status, and any `complexity_notes` surfaced by the primary executor. Its launch mode is `launched`, `manual-handoff`, `skipped`, or `failed-to-launch`. Its final disposition is `clean`, `fixed-clean`, `needs-primary-followup`, `needs-user-review`, `blocked`, or `skipped`.

In autonomous mode, `00-session.md` records the immutable authorization snapshot, exact base commit, and mission worktree. The selected existing roadmap item carries a closed safety disposition and a separate base-bound execution-eligibility record; the v1 controller never derives extra work. `07-run-log.md` renders the one-Goal state machine, command evidence, Runtime Boundary, Binding Status, verification, and the local zero-publication outcome. The mission records roadmap outcomes in controller-owned run artifacts and never changes creator intent; a later creator-confirmed refresh may update the canonical roadmap. `08-final-summary.md` records `awaiting-review`, `blocked`, or `abandoned`, plus stable mission, Goal, attempt, worktree, branch, and commit identifiers; the PR identifier remains null in the enabled bridge. `merged` may be observed later after human action but is never produced by the v1 controller.

For a full-plugin autonomous mission, never hand-author `07-run-log.json`, `07-run-log.md`, `08-final-summary.json`, or `08-final-summary.md`. Run `artifacts mission-view` after each surfaced controller checkpoint. It validates the persisted mission bundle, writes replaceable run-log views for active states, and writes then seals all four views only for terminal states. The v1 operation journal stores typed host actions rather than command argv/environment data, so `commands` is honestly empty and the Markdown renders a redacted host-action ledger separately. An interrupted refresh never changes mission state and must be retried without replaying the host action.

The Deep Intent Gate and Doctrine Interview introduce no new numbered artifact: `04-question-funnel.md` / `05-user-answers.md` record the evidence draft, first-run interview, Project Doctrine screens, the ambiguity ledger and each loop pass, reconcile screens, refresh answers, explicit creator confirmation, and any `continue later` partial state. `00-session.md` records the selected scoped root and intent namespace, schema validation plus the `completion` and `intent_clarity` values and hashes for all three canonical intent JSON documents, the ignore decision, activation result, and backup location. Root intent lives directly in `.pathfinder/`; an explicit monorepo scope such as `apps/api` lives in `.pathfinder/scopes/apps/api/intent/`. Each namespace is a separate stable, local-only, never-committed three-document set outside the run folder; matching `.md` files are replaceable controller-rendered human views. Namespaces never inherit or fall back to one another. None are part of the 00-08 artifact set, and no numbered artifact or Markdown view may be parsed into canonical intent.

Artifact folders should be ignored locally and should not be committed or pushed unless the user explicitly requests publication after review.

Never create the run directory or any repository-local artifact until the concrete artifact path is confirmed ignored. If an ignore update is denied or fails, use a safe outside work folder or keep the proposed artifact in the conversation; never fall through to an untracked repository folder.
