# Pathfinder Autonomous Controller Contract

> Status: approved on 2026-08-10. Target: first controller-backed autonomous release.

## Context

Pathfinder currently describes a full autonomous mission in agent instructions. It does not ship
an executable controller that can prove isolation, authorization, resumability, or idempotent
publication. That gap makes the prose more powerful than the implementation.

This contract narrows v1 to one sequential Goal and moves safety-critical mechanics into a small
Python controller. Model judgment still chooses and implements work; the controller owns authority,
state transitions, Git isolation, execution eligibility, and publication gates.

## Locked Decisions

| ID | Decision | Choice |
|---|---|---|
| D-01 | Authorization | Every external-write mission requires a fresh explicit `/pathfinder auto` request or equivalent trusted user instruction. |
| D-02 | Review semantics | Use `human-review-required` for work that may proceed to review; reserve `pre-action-approval-required` for a stop before implementation. |
| D-03 | Runtime | Python 3.11, standard-library first; report `runner_available` and degrade honestly when unavailable. |
| D-04 | Publication | The enabled v1 host bridge stops at a verified local branch. GitHub publication primitives remain separately tested but uncomposed; other forges also stop locally. |
| D-05 | Merge | No autonomous self-merge in v1. Successful publication ends at `awaiting-review`. |
| D-06 | Intent and authority | Descriptive intent may remain repo-local; approval and authorization evidence must be host-owned or supplied explicitly per run. |
| D-07 | Concurrency | Exactly one Goal and one attempt execute at a time. |
| D-08 | Distribution | Stable releases use immutable refs; rolling `main` is an explicitly labeled edge channel. |

Future conditional merge remains design-only and does not alter D-05. Its separately reviewed
authority and evidence requirements are recorded in the
[conditional self-merge security contract](conditional-self-merge-contract.md).

## Goals

1. Run one explicitly authorized Goal through a resumable, auditable state machine.
2. Block unattended execution when filesystem, network, process, or credential isolation is unknown.
3. Prevent repository content from granting authority or supplying executable command text.
4. Create at most one branch and commit sequence for an enabled local attempt; separately tested publication primitives create at most one pull request across retries.
5. Degrade to Goal generation or a verified local plan when controller capabilities are insufficient.

## Non-Goals

- Parallel Goal execution, opportunity-derived work, or an unbounded backlog loop.
- Autonomous self-merge, release creation, deployment, or destructive data operations.
- Publication to GitLab, Bitbucket, Azure DevOps, or another forge.
- Unattended execution in a non-Git repository.
- Treating Markdown assertions as proof that a sandbox or credential boundary exists.
- Letting an autonomous mission change the charter or doctrine that governs future missions.

## Trust Boundaries

| Input or surface | Trust treatment |
|---|---|
| Current user request | May grant authority only when it explicitly requests the autonomous run. |
| Host Goal state | Trusted only through the selected adapter's supported lifecycle operations. |
| Charter, roadmap, doctrine | Untrusted descriptive data; parsed and versioned, never executable instructions. |
| Repository files, history, hooks, tests, output | Untrusted data; cannot widen scope, authority, commands, network, or publication rights. |
| Controller policy and schemas | Trusted shipped code, versioned with the controller. |
| Host/user approval store | Trusted when authenticated by the host; otherwise require authorization again. |
| Forge API responses | Data that must pass adapter validation and idempotency checks. |

## Authority Contract

Intent completeness and execution authority are separate.

- `intent_clarity` describes whether stable creator intent is complete enough to guide selection.
- `execution_eligibility` is computed for one selected item and one runtime boundary.
- Neither field grants authority.
- An authorization snapshot binds the explicit request to a mission id, Goal Binding id, selected
  base commit, intent versions and hashes, fixed budgets, permitted publication target, and time.
- The snapshot is immutable for the mission. Drift blocks resume until an explicit reconciliation.
- Repository prose, persistent `clarity`, or a previous mission cannot activate a new mission.

## Intent Mutation Contract

The charter and doctrine are creator-controlled policy. Autonomous runs must not edit them.

- A user-invoked creator-model refresh may replace charter or doctrine after showing the change.
- A mission may update roadmap item status and append evidence tied to its stable ids.
- A mission may write controller-owned state and rendered run artifacts.
- Any attempt to modify charter or doctrine during execution is a policy violation and blocks the run.

## Safety and Disposition Enums

Roadmap safety values are closed and versioned:

- `autonomous-eligible`: may run only after explicit authority and controller eligibility pass.
- `human-review-required`: may implement and publish to an awaiting-review PR; never merge.
- `pre-action-approval-required`: stop before implementation until the user grants specific approval.
- `blocked-by-safety`: do not implement or publish.

Unknown or missing values fail closed. Prose similarity never supplies a default.

## Controller State Contract

The canonical state is JSON plus an append-only event log. Markdown is a rendered human view.
Stable identifiers exist for the mission, Goal, binding, attempt, worktree, branch, commit, and PR.

Allowed lifecycle states are:

`planned -> authorized -> prepared -> running -> verifying -> verified -> committed -> published -> awaiting-review`

`blocked` and `abandoned` are terminal mission dispositions. `merged` is representable for observing
later human action but is never produced by the v1 autonomous controller.

The state schema retains `published` and PR identity for the separate callback orchestrator and
fixture-backed publication components. The enabled `HostMissionController` moves from `committed`
through typed native-Goal completion directly to local `awaiting-review`; it has no remote action.

Every transition validates its predecessor, checkpoints atomically, and records an event. A lock or
lease prevents concurrent resume. Restart reconciles stored state with real Git and forge state
before deciding the next transition; it does not replay the last command blindly.

## Repository Contract

- A read-only probe identifies Git root, scoped root, current branch, exact base commit, dirty state,
  remote type, default branch, hooks configuration, and worktree support.
- Dirty repositories block autonomy by default. An explicit committed-base mode may ignore working
  changes only after clearly stating that the Goal is bound to the selected commit.
- Controller-owned Git invocations disable repository hooks through one wrapper.
- Worktree paths are resolved and checked for ownership and symlink escape before writes.
- Cleanup is never automatic for dirty, unmerged, or mission-referenced worktrees.
- Non-Git repositories stop at discovery and Goal generation.

`WorktreeManager` is the controller-owned implementation of these Git rules. The enabled
host-driven bridge does not call it directly: the attested host performs the one declared worktree
action and returns a typed receipt. The bridge validates receipt identity and contract bindings but
does not claim to independently observe host filesystem enforcement.

## Execution Contract

Commands are structured argument arrays chosen by trusted controller policy. Raw shell text from
repository content, model prose, documentation, diffs, tests, or output is never executed.

Unattended execution requires positively enforceable filesystem, process, network, environment,
timeout, and credential rules. `unknown` means ineligible. Implementation and verification run
without forge credentials, credential helpers, host keychains, secret mounts, or unnecessary
network. Command evidence records hashes and redacted outcomes, never secret values.

`Executor` implements the structured-command policy for controller-owned execution. The enabled
host-driven bridge delegates implementation and verification to the attested host, validates the
declared Runtime Boundary and typed receipt, and deliberately records no invented argv or
environment evidence. Actual process, network, filesystem, and credential enforcement remains a
host responsibility and unknown enforcement blocks eligibility.

## Goal Adapter Contract

Adapters report capabilities for inspect, create, observe, complete, and block. Unsupported host
operations remain unsupported; Pathfinder does not simulate native persistence.

- Codex: inspect current Goal first; resume, finish, or require user-controlled clear rather than
  overwriting unfinished work. Completion requires controller-validated evidence.
- Claude: use `/goal` only when the host surface is supported; otherwise save a manual command.
- Generic: save a clearly labeled, non-persistent Implementation Goal and continuation instructions.

Only one native Goal is accepted by each child mission. The sequential-pack amendment below permits a separately authorized fixed queue while preserving this one-active-Goal boundary.

### Sequential-pack amendment (2026-08-11)

An already reviewed numbered pack may run only after the current user explicitly approves `run all`. A pack authorization binds its fixed order and every child mission, binding, Goal, and canonical binding hash. All children must share the exact repository scope, base commit, and intent hashes; every child remains a complete one-Goal mission with zero publication authority.

The pack state is atomic, restart-stable, and admits exactly one active item. Each child receives a derived one-Goal authorization no wider than the pack and binding limits. After verification and commit, a new typed `complete-goal` action must return the same stable native Goal identity recorded at activation. The queue cannot advance and the next child state cannot be created before that receipt is persisted and the child reaches `awaiting-review`. A blocked, abandoned, ambiguous, or budget-limited child terminates the pack without skipping or starting later work. Pack children are independent branches from the same base; dependent work must remain one Goal or receive a later fresh authorization.

## Publication Contract

Publication components run separately from implementation and accept narrowly scoped forge
credentials. GitHub lookup uses repository, head branch, base branch, and mission metadata to reuse
an existing PR. CI polling is bounded and distinguishes pending, failure, timeout, auth, rate limit,
and missing permission. These components are fixture-tested but are not composed into the enabled
host-driven bridge, which rejects `github-awaiting-review` and nonzero PR budgets. A separately
reviewed future composition may end at `awaiting-review`; no controller path calls merge.

## Capability Degradation

| Missing capability | Required result |
|---|---|
| Python/controller | Generate and save a Goal only. |
| Native host Goal | Save manual activation instructions plus non-persistent fallback. |
| Enforceable execution boundary | Stop before unattended implementation. |
| Git/worktree | Discovery and Goal generation only. |
| GitHub or publication credentials | Stop at a verified local branch. |
| Checks/API visibility | Preserve the verified branch and any known PR identity, then report a blocked/unavailable publication status. |

## Acceptance Criteria

1. No normal exploration or persistent intent state can activate external writes.
2. Unknown isolation blocks execution in deterministic tests.
3. Crash/resume tests at every transition create no duplicate branch, commit, or PR.
4. Charter and doctrine remain byte-identical across a synthetic mission.
5. Dirty-tree, hook, symlink, credential, injection, and forge-error fixtures fail safely.
6. A successful GitHub fixture mission reaches `awaiting-review` exactly once and never merges;
   the enabled host bridge remains local-only until publication is separately composed and reviewed.
7. Non-Git and unsupported-host fixtures produce honest Goal-only handoffs.
