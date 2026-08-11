# Pathfinder operator guide

This guide covers local controller state. The enabled mission bridge creates no remote side effects and has no publication action.

## Inspect capabilities

```bash
bash scripts/pathfinder-controller.sh doctor --json
```

`controller_available` means the supported Python runtime and schema validators are available. `runner_available` is a compatibility alias with the same limited meaning. `mission_runner_available` reports whether the local host-driven start/next/record/resume protocol is callable. `unattended_execution_eligible` remains false in the read-only doctor because it does not fabricate or probe host filesystem, process, network, or credential enforcement. A real host attestation is validated again by `mission start`.

For a prompt-only Goal, a full plugin writes canonical saved-Goal outputs through `artifacts goal-saved`. The command consumes only a validated `.prompt-goal-request.json` inside an already ignored Pathfinder run directory, verifies the bound Git base and safe path, validates `06-goal-command.md`, emits schema-valid `06-goal-binding.json` and `08-final-summary.json`, renders `08-final-summary.md` with the stable IDs, seals all four final artifacts read-only, and is idempotent for the same request.

## Run the local host-driven protocol

Keep the state directory and authorization outside repository trust. Publication targets and PR budgets must be zero. Then use:

```bash
bash scripts/pathfinder-controller.sh mission start --state-dir <path> --goal-binding <binding.json> --authorization <authorization.json> --runtime-boundary <boundary.json> --json
bash scripts/pathfinder-controller.sh mission next --state-dir <path> --json
bash scripts/pathfinder-controller.sh mission record --state-dir <path> --receipt-file <receipt.json> --json
bash scripts/pathfinder-controller.sh mission resume --state-dir <path> --json
```

`start` rejects an authorization whose Goal, attempt, wall-time, or PR limit widens the immutable Goal Binding. `next` journals one closed action before returning it, including the fixed mission deadline in the trusted action context. Perform only that action, then return a receipt conforming to `schemas/mission/host-action-receipt.schema.json`. `record` persists the typed receipt and operation result before advancing state. `resume` recovers persisted receipt/result boundaries, but an intent with no trustworthy receipt returns `reconcile-required` and must not be replayed. The local sequence is prepare-worktree, activate-goal, implement, verify, commit, then local `awaiting-review`. A manual/non-persistent Goal blocks; push, PR, CI, merge, and publication credentials are disabled.

The bundled protected-surface registry is always active. To add repository-specific categories, pass `--protected-policy <additive-policy.json>` to `mission start`; this explicit input can only add rules. The effective policy is sealed with the mission and bound into each operation. Every successful receipt's `changed_files` is classified, and an undeclared protected category stops before the receipt is persisted. See [protected surface policy](protected-surfaces.md).

The wall deadline is derived from the original persisted mission creation time and the narrower of the authorization and Goal Binding limits. Restarting cannot extend it. At or after the deadline the controller issues no new action and persists `terminal_reason: budget-limited`; a successful receipt completed after the deadline is rejected and remains reconciliation-required. Goal count is fixed at one, this bridge creates only one stable attempt, and both open/total PR limits are zero. Token/cost accounting is not exposed by the host protocol and is therefore not claimed as a controller guarantee.

## Inspect persisted mission state

```bash
bash scripts/pathfinder-controller.sh mission status --state-dir <mission-state-dir> --json
```

This command inspects state without advancing it. Do not infer unattended eligibility from a valid state file or manually edit state. Terminal missions are idempotent. Local receipt/result/transition crashes recover from persisted evidence; ambiguous side effects without receipts require host reconciliation.

If the lease exists, first confirm no Pathfinder process is using the mission. A stale lease may be reclaimed only through the controller's explicit stale-lease path; never delete a live lease by guesswork.

## Abandon

```bash
bash scripts/pathfinder-controller.sh mission abandon --state-dir <mission-state-dir> --json
```

Abandon is terminal. It preserves the state, event log, branch, and worktree for inspection. It does not delete files, branches, commits, or PRs.

## Migrate local state

Choose a new backup directory outside the repository, then run:

```bash
bash scripts/pathfinder-controller.sh migrate intent --root <repo-root> --backup-dir <new-backup-dir> --json
bash scripts/pathfinder-controller.sh migrate mission --state-dir <mission-state-dir> --backup-dir <new-backup-dir> --json
```

V1 intent migration changes legacy `clarity:` metadata to `intent_clarity: unresolved`; it never grants clarity or authorization. Current v1 mission state is validated and backed up. An unknown version, missing file, symlinked intent file, existing backup destination, or failed write stops the migration; failed intent writes are restored from the in-memory originals and the backup remains available.

## Recover common outcomes

| Outcome | Action |
|---|---|
| `goal-saved` / manual handoff | Activate the printed Goal manually, or start a new local mission only when the active host can satisfy every attestation/receipt gate. |
| `blocked` before commands | Read the Runtime Boundary/authorization error; supply only the named capability or user decision. Do not edit state JSON. |
| `blocked` after verification | Inspect the diff, run log, Binding Status, and verifier evidence. Continue in a new explicitly scoped mission. |
| `blocked` with `terminal_reason: budget-limited` | Review the preserved branch/state. A larger budget requires a fresh explicit mission; restart does not extend the old deadline. |
| `awaiting-review` | Review the local branch. The enabled bridge has no PR or merge operation. |
| external publication auth/rate/timeout failure | This is outside the enabled bridge. Preserve the local branch and use a separately reviewed publication process. |
| corrupt or divergent event/state | Preserve the entire state directory and backup; do not hand-edit. Report the first controller error and stop. |

## Cleanup and retention

- `.pathfinder/*.md`: retain while the creator model is useful; migrate with a backup before format changes. Never commit it.
- `.agent-work/pathfinder/...`: retain until the Goal/PR is reviewed; it is the human/replay evidence packet. Never publish it by default.
- Mission state and authorization: retain at least through review/abandon and any audit window. Authorization belongs outside the repository trust boundary.
- Mission worktrees: remove only after the controller proves no dirty files, unmerged commits, or active mission references. Never force-remove a worktree Pathfinder refuses to clean.
- Branches: delete manually only after review/merge/explicit abandonment and normal repository policy. Pathfinder never force-pushes or deletes branches/tags.
- Migration backups: retain until the migrated state has been opened, validated, and—where applicable—resumed successfully.
