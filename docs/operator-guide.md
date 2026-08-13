# Pathfinder operator guide

This guide covers local controller state. The enabled mission bridge creates no remote side effects and has no publication action.

The package contains an internal K4 merge primitive for deterministic security and crash-recovery
testing. It has no command, route, configured host-envelope reader, credential loader, or normal
caller. Do not instantiate it manually or place a merge token in repository files or environment
variables. Conditional merge remains unavailable until the separately reviewed K5 composition and
operator-owned enablement gate exist.

Its source contract requires two host-owned, fresh authenticated readers: one that collects and
attests the complete two-snapshot evidence envelope at the execution instant, and one that returns a
GitHub App token with a closed scope/identity/issuance receipt. The journal atomically spends the
authorization/readiness proof once, persists that receipt, and records dispatch at the final
pre-transport boundary before the sole possible request. An intent without dispatch cannot be
credited as merged; after restart, a dispatched intent without a terminal result also remains
reconciliation-required because a local marker cannot prove the remote request began. These interfaces have no
live implementation in this package; fixture success is not operator enablement.

The package now also contains a source-only GraphQL evidence primitive. It can send exactly one
compiled pull-request query to GitHub's fixed GraphQL endpoint and has no arbitrary query, mutation,
URL, secret loader, command, or caller. It binds the exact query hash and completely paginates the
latest effective reviews, code-owner review requests, and review threads while rechecking stable PR
identity on every page. This does not make live observation available: a later pure composer binds
the REST and GraphQL outputs, but no installed trusted-host credential reader calls either. A separate
source-only verifier now accepts a hash-bound, fresh, one-repository observer issuance receipt and
cross-checks the observer App/installation/bot/repository plus the future merge
App/installation/bot through exact live reads. The source collector requires both verified
identities at the same trusted instant and uses only the merge bot for policy-membership and
evidence-actor decisions; its authenticated artifact stores the non-secret receipt, never the merge
token. A dedicated feature read treats the private-plan
upgrade response as absence only when GitHub also identifies the exact required read permission;
ordinary 403 remains a permission error. A pure source-only composer now requires distinct verified
observer and merge receipts and all seven identity audits, authenticated publication receipt, fixed-query GraphQL
projection, reconciled REST reviews, policy-derived required checks, exact check/status pages, and
the remaining normalized REST families and a canonical controller-branch ownership proof. It
emits one schema-valid evidence document plus a
separately hashed provenance receipt bound to the evidence, observer/merge/publication receipts,
reviews, checks, request identities, and collection window. The ownership proof requires restricted
create/update/delete rules, the authenticated publication App as the sole always-bypass actor, the
complete effective-rule view for the exact head branch, and a final exact ref/SHA reread after
evidence collection. It still does not install a collector, load a credential from the host, or add
a caller. Before any GitHub read, the source collector now accepts only one closed input envelope
whose exact canonical bytes, store/repository/evidence identity, and trusted-clock start are verified
by the injected external host authenticator; it no longer accepts loose policy, authorization,
receipt, or object-evidence arguments. Unsigned, altered, stale, malformed, or wrong-store input
stops without a network read. A correctly signed but internally split or expired bundle also stops
before network: the store rechecks nested hashes and the exact publication, authority, repository,
mission, candidate, protected-policy, credential, actor, and time bindings. After collection, the same source-only store can place the
validated publication journal, exact operator policy/current-run authorization/protected policy,
all three non-secret credential receipts, ownership proof, evidence, and provenance into one immutable
externally authenticated v3 envelope. It ships no authenticator/key implementation. Its packaged
consumers are the unconstructed collector and an unconstructed read-only adapter that requires two explicit evidence ids,
identical publication/authority documents, and the same authenticator/key identity. On POSIX the
store pins an owner-only non-symlink directory
outside repository trust and uses one size-bounded, fsynced, write-once file; Windows fails closed
until equivalent ACL ownership proof exists. This is a storage contract for a future trusted host,
not an installed collector or runnable publication route. The existing `merge status` CLI remains
the separately reviewed owner-only file reader; it does not silently instantiate this stronger
adapter without a real host authenticator. A
source-only membership reader now qualifies exact team and
organization absence and exact repository-role permissions, while the check reader walks suites
before runs so GitHub's 1,000-suite shortcut cannot hide evidence. A source-only review reader
fully paginates the REST review audit and reads one exact repository permission for every unique
review actor, requiring positive `Metadata=read` evidence and cross-checking the returned actor.
The check reader also reads the combined status envelope, fully paginates the creator-bearing status
history, derives the latest item per context, cross-checks count/state for the exact repository/SHA,
classifies checks only against a closed supplied context/App union, and requires every required run
to name the supplied candidate's exact PR/head/base identity. Suites, runs, and both status reads
share one request budget. These readers retain distinct request audits and fail on identity,
permission, pagination, request budget, PR binding, or SHA drift; none is an installed collector,
and only the uncalled pure composer binds the supplied union/candidate to their outputs. An
uncalled pure projector can now form that union from the host floor, qualified classic protection,
and all completely paginated active rules; it rejects any unpinned or contradictory check identity.
An uncalled pure review reconciler also requires the GraphQL latest-opinionated record for every
actor to match the exact record selected from the complete chronological, permission-qualified REST
history. A second pure reconciler validates the canonical publication request and receipt, requires
a later fixed-query GraphQL view of the identical repository, PR, refs, and commits, and projects the
authenticated controller bot id carried through publication preflight and the exact push receipt.
It does not authenticate storage or prove that an installed host prevented a different actor from
pushing the same commit later. A pure GraphQL projector then requires that same pusher-bound
snapshot, the exact schema-pinned compiled query hash, complete review/reviewer/thread connections,
and one-to-one request/rate-limit audit coverage before emitting mergeability, queue, requested-
reviewer, thread, pagination, and `graphql-pull-request` audit inputs. These source pieces and their
pure composer still are not an installed collector or an
installed runtime route.

The package also contains an uncomposed awaiting-review publication prerequisite. Its explicit
controller accepts one fresh authenticated host request containing the canonically bound full
explicit GitHub-awaiting-review authorization, one-PR ceiling, and publication bot database/node/
login identity. Before mutation, its injected
publication-only backend must read-only preflight the exact repository, refs, commits, diff hashes,
required check context/App pairs, and bot identity. Publication and reconciliation accept no caller-selected
timestamp; only the injected trusted host clock can establish freshness and receipt time. The
controller writes a closed receipt only after the backend returns
the exact repository and pull-request database/node/number identities, controller head/base refs
and SHAs, mission-state/authorization binding, diff hashes, GitHub URL, and successful check
context/App/head-SHA observations. The same receipt attests the exact bot id/node/login against the
repository, controller ref, and head SHA. Dispatch is persisted before the remote callback without holding
the journal lock across that callback, so process death leaves a recoverable pending record instead
of a stale lock. A pending request is never published again; explicit reconciliation performs only
exact PR lookup and check observation. The source includes no command, live backend, credential
loader, ordinary mission caller, or installed route. Do not instantiate it manually or interpret
its fixture receipt as a real published PR.

Independent publication source review is complete, but that is not execution readiness. A bounded external-host
rehearsal has now exercised the source publication controller and two complete live evidence
snapshots with zero merge capability; its sanitized record is in
[`docs/rehearsals/2026-08-12-zero-merge-publication.md`](rehearsals/2026-08-12-zero-merge-publication.md).
That one-off host adapter is not a packaged or installed route, and its deliberately non-authorizing
dry-run binding is not an operator merge policy or current-run merge authorization. A trusted
installed host, supported live backend, and operator-owned schema-valid policy boundary therefore
remain absent. This is separate from the later composed merge rehearsal. The shipped CLI therefore intentionally has no
publication or merge-execution command. It now has only the K5.1 `merge status` and `merge evaluate`
inspection commands described below. Packaged routes construct neither the publication controller nor
the merge executor. They also cannot bypass the controller by constructing the lower-level GitHub publisher;
the package guard rejects that caller and any concrete generic or exact GitHub backend. The
canonical checked/unchecked gate is in
[`PLAN.md`](../PLAN.md#phase-k5--compose-an-explicit-default-off-conditional-merge-path).

## Inspect conditional merge readiness

K5.1 is an observation-only installed-host boundary. It reads one exact, persisted
`awaiting-review` publication receipt and optional operator-supplied policy and evidence documents.
It never contacts GitHub, discovers a pull request, loads a merge credential, persists or exposes a
readiness proof, creates a merge intent, or calls the K4 writer. Even an `eligible` report remains
`state: awaiting-review` with `intent_ready`, `execution_available`,
`writer_credential_loaded`, and `merge_intent_created` all fixed to `false`.

On POSIX, the host directory must be an existing current-user-owned, owner-only, non-symlink
directory outside the repository. The reader pins that directory descriptor once and opens every
journal/input descendant relative to the pinned descriptor with symlink following disabled, so a
path swap after validation cannot redirect reads into repository trust. K5.1 fails closed on
Windows until an equivalent current-user and owner-only ACL proof is implemented; the rest of the
Pathfinder controller remains supported there. The fixed host layout is:

```text
<host-dir>/
  journal/publication-operations/<publication-request-id>.{request,dispatch,receipt}.json
  merge-policy.json                 # optional; missing is typed
  merge-authorization.json          # optional; missing is typed
  merge-evidence-initial.json       # optional; missing is typed
  merge-evidence-reread.json        # optional; missing is typed
  protected-policy.json             # optional additive policy; shipped baseline otherwise
```

Run either view explicitly:

```bash
bash scripts/pathfinder-controller.sh merge status --repo-root <repository> --host-dir <host-dir> --publication-request-id <id> --json
bash scripts/pathfinder-controller.sh merge evaluate --repo-root <repository> --host-dir <host-dir> --publication-request-id <id>
```

`--json` emits the closed canonical report. The default Markdown is only a rendering of that report.
Each input entry binds its state, canonical document hash, declared identity, and declared hash
where applicable, so the report hash identifies the exact policy, authorization, and both evidence
documents that were evaluated. Block codes are closed to the evaluator's typed deny-code domain.
The two commands use the same pure two-snapshot evaluator; `operation` records which view the
operator requested. Missing, expired, malformed, unsupported, drifted, or incomplete inputs produce
typed blocks without widening authority. A missing exact publication receipt is a hard error.
Supplying these files does not authorize execution, and no repository file, environment variable,
or ordinary `/goal`, mission, Goal-pack, publication, or resume route can escalate into it.

## Inspect capabilities

```bash
bash scripts/pathfinder-controller.sh doctor --json
```

`controller_available` means the supported Python runtime and schema validators are available. `runner_available` is a compatibility alias with the same limited meaning. `mission_runner_available` reports whether the local host-driven start/next/record/resume protocol is callable. `unattended_execution_eligible` remains false in the read-only doctor because it does not fabricate or probe host filesystem, process, network, or credential enforcement. A real host attestation is validated again by `mission start`.

For a prompt-only Goal, a full plugin writes canonical saved-Goal outputs through `artifacts goal-saved`. The command consumes only a validated `.prompt-goal-request.json` inside an already ignored Pathfinder run directory, verifies the bound Git base and safe path, emits schema-valid `06-goal-binding.json` and `08-final-summary.json`, deterministically renders both Markdown views, seals all four final artifacts read-only, and is idempotent for the same request.

## Run the local host-driven protocol

Keep the state directory and authorization outside repository trust. Publication targets and PR budgets must be zero. Then use:

```bash
bash scripts/pathfinder-controller.sh mission start --state-dir <path> --goal-binding <binding.json> --authorization <authorization.json> --runtime-boundary <boundary.json> --json
bash scripts/pathfinder-controller.sh mission next --state-dir <path> --json
bash scripts/pathfinder-controller.sh mission record --state-dir <path> --receipt-file <receipt.json> --json
bash scripts/pathfinder-controller.sh mission resume --state-dir <path> --json
bash scripts/pathfinder-controller.sh artifacts mission-view --repo-root <repo-root> --state-dir <path> --output-dir <ignored-run-dir> --json
```

`start` rejects an authorization whose Goal, attempt, wall-time, or PR limit widens the immutable Goal Binding. `next` journals one closed action before returning it, including the fixed mission deadline in the trusted action context. Perform only that action, then return a receipt conforming to `schemas/mission/host-action-receipt.schema.json`. `record` persists the typed receipt and operation result before advancing state. `resume` recovers persisted receipt/result boundaries, but an intent with no trustworthy receipt returns `reconcile-required` and must not be replayed. The local sequence is prepare-worktree, activate-goal, implement, verify, commit, complete-goal, then local `awaiting-review`. The completion receipt must carry the same stable native Goal identity returned by activation. A manual/non-persistent Goal blocks; push, PR, CI, merge, and publication credentials are disabled.

## Sequential Goal packs

A pack is available only after the user explicitly approves the complete numbered set. It is not a backlog selector. Every item needs its own schema-valid Goal Binding with a unique mission/binding/Goal identity, the exact same repository scope and base commit, complete matching intent hashes, zero publication budgets, and an independently reviewable outcome. The pack authorization validates against `schemas/mission/goal-pack-authorization.schema.json` and records every binding hash in the approved order.

```text
bash scripts/pathfinder-controller.sh mission pack-start --state-dir <pack-path> --goal-binding <goal-1.json> --goal-binding <goal-2.json> --authorization <pack-authorization.json> --runtime-boundary <boundary.json> --json
bash scripts/pathfinder-controller.sh mission pack-next --state-dir <pack-path> --json
bash scripts/pathfinder-controller.sh mission pack-record --state-dir <pack-path> --receipt-file <receipt.json> --json
bash scripts/pathfinder-controller.sh mission pack-resume --state-dir <pack-path> --json
bash scripts/pathfinder-controller.sh mission pack-status --state-dir <pack-path> --json
bash scripts/pathfinder-controller.sh mission pack-abandon --state-dir <pack-path> --json
```

The top-level `state.json` is the canonical queue. It records exactly one active item, fixed ordered identities and hashes, a restart-stable pack deadline, per-item child paths, and terminal outcomes. Each child under `goals/NNNN/` is an ordinary one-Goal mission with its own immutable contracts, operation journal, typed receipts, events, branch, and commit. `goal-advanced` means the queue checkpoint was persisted; it is not permission to perform a host action. Call `pack-next` again. The next child state is not created until the prior child reaches `awaiting-review` through a matching `complete-goal` receipt. Any block, abandonment, ambiguity, or budget expiry stops the whole pack without starting later items.

Pack items are independent branches from the same authorized base. If goal 2 depends on goal 1's commit, express them as one bounded Goal or obtain a new authorization after the dependency lands; the pack never silently rebases or widens later bindings.

Run `artifacts mission-view` after `mission start` and after every surfaced `next`, `record`, or `resume` result. Active missions refresh only replaceable `07-run-log.json` and `07-run-log.md`; terminal missions also write `08-final-summary.json` and `08-final-summary.md` and seal all four. For a pack, project the active child state from `<pack-path>/goals/NNNN` into an ignored `<run-dir>/goals/NNNN/` directory and use `pack-status` for the queue. This command reads validated controller state and writes only the confirmed ignored run directory. It executes no repository code, uses no credentials, performs no state transition, and is safe to retry after an interrupted view write. Never replay a host action to repair a view.

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

## Activate or migrate local intent

Canonical creator intent is one closed three-document namespace. Repository scope `.` uses `.pathfinder/{charter,roadmap,doctrine}.json`; an explicit monorepo scope such as `apps/api` uses `.pathfinder/scopes/apps/api/intent/{charter,roadmap,doctrine}.json`. Matching Markdown files are generated, replaceable views and are never read back into selection or authority. A scoped namespace never inherits or falls back to root or a sibling. Confirm all six concrete paths in the selected namespace are locally ignored and keep activation inputs plus backups in an ignored run folder or outside the repository.

After the creator explicitly confirms the complete three-document proposal, activate it with:

```bash
bash scripts/pathfinder-controller.sh migrate intent-activate --root <repo-root> --scoped-root <scoped-root> --backup-dir <new-backup-dir> --charter-json <draft-charter.json> --roadmap-json <draft-roadmap.json> --doctrine-json <draft-doctrine.json> --creator-confirmed --json
```

Use `--scoped-root .` for repository intent or one normalized existing repository-relative directory for subproject intent. The command rejects absolute/traversal/alias paths, missing directories, symlinks, and `.pathfinder` itself. It validates all three documents before creating the backup, preserves exact bytes for every existing JSON/view target, writes canonical JSON before deterministic views, and restores the original file set plus newly created namespace directories after a write failure. Its result reports the normalized `scoped_root` and exact `intent_dir`, plus `authorization_granted: false` and `autonomy_authorized: false`. Do not pass `--creator-confirmed` on the creator's behalf or use a prior autonomous request as confirmation.

The older command below is compatibility-only: it reads legacy v1 Markdown metadata, backs up exact bytes, and forces migrated clarity to unresolved. Runtime selection does not read that legacy Markdown.

Choose a new backup directory outside the repository, then run:

```bash
bash scripts/pathfinder-controller.sh migrate intent --root <repo-root> --backup-dir <new-backup-dir> --json
bash scripts/pathfinder-controller.sh migrate mission --state-dir <mission-state-dir> --backup-dir <new-backup-dir> --json
```

V1 intent migration changes legacy `clarity:` metadata to `intent_clarity: unresolved`; it never grants clarity or authorization. Current v1 mission state is validated and backed up. An unknown version, missing file, symlinked intent file, existing backup destination, or failed write stops the migration; failed intent writes are restored from the in-memory originals and the backup remains available.

Production Markdown reads are intentionally limited to that legacy migration and generated-region replacement used to repair candidate/verification views. Tests and evals may inspect rendered Markdown, but no operator should treat a view, marker, or prose assertion as controller state.

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

- `.pathfinder/{charter,roadmap,doctrine}.json` and `.pathfinder/scopes/<scoped-root>/intent/{charter,roadmap,doctrine}.json`: retain each selected namespace as a separate canonical creator model. Keep matching `.md` views only for humans; every namespace is local-only and must never be committed.
- `.agent-work/pathfinder/...`: retain until the Goal/PR is reviewed; it is the human/replay evidence packet. Never publish it by default.
- Mission state and authorization: retain at least through review/abandon and any audit window. Authorization belongs outside the repository trust boundary.
- Mission worktrees: remove only after the controller proves no dirty files, unmerged commits, or active mission references. Never force-remove a worktree Pathfinder refuses to clean.
- Branches: delete manually only after review/merge/explicit abandonment and normal repository policy. Pathfinder never force-pushes or deletes branches/tags.
- Migration backups: retain until the migrated state has been opened, validated, and—where applicable—resumed successfully.
