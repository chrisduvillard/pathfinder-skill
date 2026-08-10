# Pathfinder operator guide

This guide covers local controller state. Commands do not create external side effects unless a separately authorized mission reaches its publication adapter.

## Inspect capabilities

```bash
bash scripts/pathfinder-controller.sh doctor --json
```

`runner_available` means the controller and schema validator can run. `unattended_execution_eligible` remains false until the host supplies enforceable filesystem, process, network, and credential evidence; the read-only doctor does not probe by running repository code.

For a prompt-only Goal, a full plugin writes canonical saved-Goal outputs through `artifacts goal-saved`. The command consumes only a validated `.prompt-goal-request.json` inside an already ignored Pathfinder run directory, verifies the bound Git base and safe path, validates `06-goal-command.md`, emits schema-valid `06-goal-binding.json` and `08-final-summary.json`, renders `08-final-summary.md` with the stable IDs, seals all four final artifacts read-only, and is idempotent for the same request.

## Inspect and resume a mission

```bash
bash scripts/pathfinder-controller.sh mission status --state-dir <mission-state-dir> --json
```

To pause, stop the host after its current controller checkpoint. There is no unsafe mid-command pause. Resume with the same mission id, state directory, Goal Binding, authorization snapshot, base commit, worktree, and branch; never start a second mission over the same worktree. The controller reconciles an event written immediately before a crash and returns terminal missions unchanged.

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
| `goal-saved` / manual handoff | Activate the printed native Goal or Implementation Goal, then start a fresh explicitly authorized mission if autonomy is wanted. |
| `blocked` before commands | Read the Runtime Boundary/authorization error; supply only the named capability or user decision. Do not edit state JSON. |
| `blocked` after verification | Inspect the diff, run log, Binding Status, and verifier evidence. Continue in a new explicitly scoped mission. |
| `awaiting-review` | Review the PR or local branch. Humans own merge. |
| publication auth/rate/timeout failure | Preserve the branch and rerun the same publication identity after the external condition clears; the adapter reuses an existing PR. |
| corrupt or divergent event/state | Preserve the entire state directory and backup; do not hand-edit. Report the first controller error and stop. |

## Cleanup and retention

- `.pathfinder/*.md`: retain while the creator model is useful; migrate with a backup before format changes. Never commit it.
- `.agent-work/pathfinder/...`: retain until the Goal/PR is reviewed; it is the human/replay evidence packet. Never publish it by default.
- Mission state and authorization: retain at least through review/abandon and any audit window. Authorization belongs outside the repository trust boundary.
- Mission worktrees: remove only after the controller proves no dirty files, unmerged commits, or active mission references. Never force-remove a worktree Pathfinder refuses to clean.
- Branches: delete manually only after review/merge/explicit abandonment and normal repository policy. Pathfinder never force-pushes or deletes branches/tags.
- Migration backups: retain until the migrated state has been opened, validated, and—where applicable—resumed successfully.
