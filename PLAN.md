# Pathfinder audit and autonomous-goal roadmap

Date: 2026-08-10
Repository baseline: `main` at `89c7d0d` (`v2.23.0`)
Plan size: **Large** — the recommended work adds an executable control plane, host adapters, state schemas, safety enforcement, and end-to-end evaluation.

## Executive verdict at the audited v2.23.0 baseline

1. Pathfinder is currently a cross-platform **instruction plugin**, not an autonomous runner: nearly all product behavior is specified in the 1,558-line `skills/pathfinder/SKILL.md`; the executable files under `scripts/` validate prose and fixtures but do not run missions.
2. Its product idea is strong: inspect an unfamiliar repository, identify valuable bounded work, turn it into a verifiable Goal, and optionally carry that work through reviewable pull requests.
3. Its best-developed area is the written safety model: untrusted repository content, local-only intent files, bounded goals, protected surfaces, diff review, and default-deny self-merge are all addressed explicitly.
4. Its weakest area is enforcement: worktree isolation, credential separation, command isolation, goal lifecycle, resume behavior, and publication idempotency are instructions to a model rather than mechanically checked transitions.
5. The current local preflight is **red on macOS**, despite `CONTRIBUTING.md` claiming macOS support: `scripts/test-validators.sh` uses GNU-style `sed -i`, causing 15 seeded mutation tests to fail before they actually mutate their fixtures.
6. `scripts/check-all.sh` runs `scripts/check-evals.sh` twice, adding avoidable work and noise.
7. The artifact eval layer does not validate real JSON or full schemas; it accepts any brace-shaped text and most fixtures contain only a small subset of the documented fields.
8. The project recognizes “Codex-native goal support” in prose but does not define or test the native `get/create/update` lifecycle; it mainly writes a Markdown fallback. Current [official OpenAI documentation](https://learn.chatgpt.com/codex/use-cases/follow-goals) also documents the `features.goals` enablement path, which the repository copy omits.
9. Several policy concepts need correction before autonomy is safe: persistent clarity should not itself authorize a new external-write run, `manual-approval-required` should not mean “implement and push without approval,” and autonomous work must not rewrite the doctrine that authorizes later autonomy.
10. The right next product is a **thin conversational skill over a deterministic, resumable controller**. The model should choose and implement work; code should own schemas, state transitions, sandbox gates, worktrees, budgets, and publication idempotency.

## Goal restated

Pathfinder is done when a user can install it in an arbitrary repository, quickly produce a precise Goal, explicitly start an autonomous run, safely resume after interruption, and receive an evidence-backed local result or reviewable PR without relying on a model to remember or correctly reinterpret safety-critical workflow state.

Observable success means:

- A prompt-to-goal path produces or activates one native host Goal in under two user interactions when intent is already clear.
- An autonomous run has a persisted finite-state mission record, an immutable authorization snapshot, explicit budgets, and idempotent resume behavior.
- Production commands run only when the runtime can enforce the declared sandbox/network/credential boundary; otherwise the mission stops before execution.
- The controller can prove which commit, worktree, goal binding, commands, diff, checks, and publication outcome belong to each attempt.
- Linux, macOS, and Windows CI exercise the same required local preflight.
- Golden end-to-end scenarios generate artifacts from a real Pathfinder run; seeded prose fixtures are no longer the only behavioral evidence.

## Blast radius and reversibility

- The current repository contains no application database, authentication system, payment flow, or live user data. The immediate P0 fixes affect only local/CI validation and documentation and are easily reversible.
- The later controller touches security-sensitive surfaces: local filesystem state, Git worktrees and branches, repository-defined command execution, host Goal lifecycle, credentials, GitHub publication, and possibly merge policy.
- Schema and intent changes affect ignored local user state. They require versioned migration, backup, and downgrade handling even though the files are not committed.
- Publication behavior is externally visible and not fully reversible after a PR, comment, or merge. This is why the plan makes publication idempotent, keeps v1 at awaiting-review, and removes self-merge from the first controller release.

## Assumptions

- The primary product remains a plugin/skill for Codex and Claude Code rather than a standalone hosted service.
- A safe goal-generation-only experience is preferable to a best-effort autonomous run when required capabilities are missing.
- GitHub is the first remote forge worth supporting; broader forge support can follow an adapter contract.
- Python 3.11 is acceptable for the first controller prototype. If host packaging cannot guarantee it, that premise must be revisited before Phase 2 rather than hidden behind installation prose.
- Existing public invocation forms should remain recognizable even if their internal implementation changes.
- The user wants reviewable autonomous progress, not silent external side effects or autonomy at any cost.

## Ambiguities to resolve

- Whether “manual approval required” means approval before implementation, before publication, or only human review before merge.
- Whether persistent creator intent may recommend autonomy or actually authorize a later run. This plan recommends recommendation-only.
- Whether stable users should receive rolling `main` or immutable releases.
- Whether Python can be guaranteed by both plugin hosts; otherwise a packaged binary or host-native tool server is needed.
- Whether future self-merge is a product requirement. This plan treats it as optional and out of v1.
- Which host APIs permit programmatic Goal creation and status updates from a plugin versus requiring a user slash command.

## Missing pieces identified at the audited baseline

- A threat model tied to executable controls rather than prose tokens.
- A canonical schema, migration system, and durable mission state machine.
- Runtime capability detection and a hard eligibility gate for sandbox/network/credential isolation.
- Native host Goal lifecycle adapters.
- Dirty-worktree, worktree cleanup, crash recovery, locking, idempotency, and budget semantics.
- Forge adapters and a bounded CI/publication protocol.
- Generated-run, replay, injection, platform, and crash-point evaluations.
- A compatibility/support matrix and operator recovery guide.

## Scope split

This is several projects and should not ship as one rewrite:

1. **First project:** restore portable, trustworthy validation (Phase 0).
2. **Second project:** ratify authority semantics and schemas (Phase 1).
3. **Third project:** implement one sequential local mission and one awaiting-review GitHub path (Phase 2).
4. **Fourth project:** integrate/streamline the skill and add behavioral evidence (Phases 3-4).
5. **Deferred product expansion:** parallel goals, additional forges, autonomous opportunity generation, and any self-merge capability.

## What the audited baseline did

The public flow is:

`chooser -> repository discovery -> candidate scouts -> candidate verification -> creator-intent interview -> Goal generation -> optional implementation -> optional PR/merge`

The main persisted surfaces are:

- `.pathfinder/charter.md`: stable creator intent.
- `.pathfinder/roadmap.md`: changing desired work and status.
- `.pathfinder/doctrine.md`: long-lived product doctrine and autonomy policy.
- `.agent-work/pathfinder/<run>/`: Markdown run artifacts plus five JSON sidecars.

The distribution surfaces are:

- Claude Code plugin metadata under `.claude-plugin/`.
- Codex plugin metadata under `.codex-plugin/` and `.agents/plugins/`.
- The shared skill under `skills/pathfinder/`.
- Bash validators and seeded artifact evals under `scripts/` and `evals/`.

## Evidence-backed findings

| ID | Severity | Finding | Evidence |
|---|---:|---|---|
| F-01 | P0 | Required preflight fails on macOS. | `scripts/test-validators.sh:101-318` uses GNU `sed -i`; the local `bash scripts/check-all.sh` run failed in validator meta-tests with BSD `sed` errors. |
| F-02 | P0 | Artifact evals run twice. | `scripts/check-all.sh:28` and `scripts/check-all.sh:30`. |
| F-03 | P0 | Claude plugin invocation docs disagree. | `README.md:43` says `/pathfinder`; `README-INSTALL.md:15` says namespaced `/pathfinder:pathfinder`. |
| F-04 | P0 | Native Codex Goal activation is unspecified. | `skills/pathfinder/SKILL.md:1093-1115` chooses a conceptual adapter but defines no native lifecycle or tool calls; `capability-model.md:22-26` is descriptive only. |
| F-05 | P0 | The Codex Goal guide misses current enablement guidance. | `docs/goal_command_codex.md:39-88` discusses install/version but not `features.goals`; official OpenAI docs describe both config and CLI enablement. |
| F-06 | P1 | Autonomous execution has no executable controller. | No runtime package or mission runner exists; `scripts/` contains only checks, while the entire loop is prose at `SKILL.md:1313-1414`. |
| F-07 | P1 | Autonomous authority can arise from persistent state rather than a fresh explicit run request. | Auto-escalation is granted by `clarity: resolved` at `SKILL.md:73`, `1315`, `1321`, and `1333`. |
| F-08 | P1 | “Manual approval required” work is implemented and pushed without that approval. | `SKILL.md:1346` and `roadmap-template.md:51-54`. |
| F-09 | P1 | The autonomy-authorizing doctrine can be mutated by autonomous work. | `SKILL.md:1372` and `artifact-structure.md:54` require doctrine updates after goals, conflicting with doctrine’s creator/end-state role in `doctrine-template.md:3-6`. |
| F-10 | P1 | `clarity` mixes project intent completeness with per-item execution eligibility. | `SKILL.md:130-140`, `675-691`, and all three intent templates make one stored field depend on a proof evaluated later for each item. |
| F-11 | P1 | Isolation and credential separation are asserted, not enforced. | `SKILL.md:1388-1401` asks the model to remove credentials, isolate tests, disable hooks, publish, and poll CI; no controller verifies these properties. |
| F-12 | P1 | Git hooks can still execute outside the two credentialed commands. | Hooks are neutralized for commit/push at `SKILL.md:1398-1399`, but worktree creation, checkout, pull, merge/rebase, and other Git transitions are not governed by one hook-free wrapper. |
| F-13 | P1 | Resume is a prose ledger, not an idempotent state machine. | `SKILL.md:1406-1410` records recovery in Markdown but defines no transition schema, lock, attempt identity, or duplicate-PR prevention. |
| F-14 | P1 | Derived work can extend a run without a fixed initial ceiling. | The Opportunity Scout may keep adding work at `SKILL.md:1349`; the default whole-run budget at `1408` is based on eligible goal caps and has no fixed derived-goal limit. |
| F-15 | P1 | “Any codebase” currently means Git + usually GitHub. | The mission loop assumes worktrees, branches, `gh`, branch protection, PRs, and a default branch at `SKILL.md:1337` and `1388-1402`; non-Git/non-GitHub degradation is not a first-class adapter. |
| F-16 | P1 | Dirty-worktree semantics are undefined. | Phase 0 records status, but selection can observe uncommitted code while the mission worktree is created from a commit, producing a stale or mismatched Goal Binding. |
| F-17 | P1 | Sidecars are not validated as JSON or against schemas. | `evals/harness/eval-lib.sh:76-93` checks only whether whitespace-stripped text starts/ends with braces/brackets. |
| F-18 | P1 | Goal evals can be satisfied by unrelated supporting prose. | `assert_goal_contract` in `eval-lib.sh:47-74` scans the whole Markdown file for proof, constraints, stop language, and claim fields rather than parsing the actual goal condition. |
| F-19 | P1 | No generated-run or transcript test proves behavior. | `check-evals.sh` copies seeded artifacts; `check-replay-evals.sh` has no `evals/replays/`; `check-live-evals.sh` has no checked-in live cases/runner and skips by default. The deferral is explicit in `artifact-first-evals-design.md:211-224`. |
| F-20 | P2 | The skill is too large and duplicated for efficient, reliable interpretation. | `SKILL.md` is 1,558 lines; `question-funnel-template.md` repeats 419 lines; `check-skill-consistency.sh` spends 546 lines guarding hand-maintained mirrors. |
| F-21 | P2 | New repositories pay a heavy intent-interview cost even for a one-off Goal. | All work-producing entry points trigger the Deep Intent Gate at `SKILL.md:71` and `608-697`; the normal interview is up to 8-12 screens. |
| F-22 | P2 | Parallel autonomous execution is specified before the sequential path is mechanically proven. | `SKILL.md:1370-1384` defines parallel eligibility, but no sequential controller or concurrency tests exist. |
| F-23 | P2 | Persistent intent is kept inside the repository trust boundary. | `.pathfinder/` is local-only but repo-local; repository code can still modify ignored files. Sanitization does not authenticate creator approval. |
| F-24 | P2 | CI does not test the advertised platform matrix. | `.github/workflows/manifests.yml` runs only `ubuntu-latest`; no macOS or Windows job catches F-01. |
| F-25 | P2 | Passing checks are unusually noisy. | `check-skill-consistency.sh` prints hundreds of `ok:` lines, making the important failure signal hard to find. |
| F-26 | P3 | The marketplace is a rolling `main` release. | `.agents/plugins/marketplace.json` pins `source.ref: main`, and `check-manifests.sh` enforces it, reducing reproducibility and rollback safety. |

## Recommended target architecture

Keep the model responsible for judgment and implementation, but move safety-critical mechanics into a small controller:

1. **Thin skill/router** — detects the requested path, asks only necessary questions, invokes the appropriate host Goal adapter, and explains results.
2. **Pathfinder core** — a standard-library-first Python 3.11 package is the recommended first implementation because this workload is I/O-bound and the repository already prioritizes minimal production dependencies. It validates schemas, resolves repository capabilities, manages worktrees, owns mission state, and emits permitted next actions. Prefer one mature, pinned schema-validation dependency over a hand-written partial JSON Schema engine if standards-compliant validation cannot remain in the standard library. If a supported host lacks Python, Pathfinder degrades to goal-generation-only instead of pretending to enforce autonomy.
3. **Host Goal adapters** — Codex native Goal lifecycle, Claude `/goal`, and a generic Markdown fallback, each with explicit capabilities and tests.
4. **Execution adapter** — runs only controller-approved commands inside a runtime boundary that is actually available and verified. `unknown` isolation is a blocker for unattended code execution, not merely a disclosed field.
5. **Publication adapters** — local Git first; GitHub PR second; other forges and non-Git repositories degrade explicitly. Self-merge stays off by default until separately opted in and tested.
6. **Schemas and event log** — canonical JSON state with Markdown rendered from it. The controller, not free-form prose, owns state transitions and resumability.

The first autonomous release should be deliberately narrower than the current prose promise: sequential goals, Git repositories, GitHub PR publication, no automatic self-merge, no autonomous doctrine edits, and no automatic escalation from a normal exploration run.

## Decisions to ratify before implementation

- [x] **D-01 — Authorization:** adopt explicit `/pathfinder auto` (or equivalent trusted user request) for every external-write run. Recommendation: **yes**; resolved intent may shorten the interview and recommend autonomy, but must not activate it.
- [x] **D-02 — Manual work semantics:** either require approval before implementation, or rename the class to `human-review-required`. Recommendation: rename it and reserve `manual-approval-required` for a real pre-action stop.
- [x] **D-03 — Controller runtime:** use Python 3.11 standard library for v1 and expose `runner_available` in capabilities. Recommendation: **yes**, with goal-only degradation when unavailable.
- [x] **D-04 — Publication scope:** support local Git plus GitHub PRs in v1; all other forges stop at a verified local branch. Recommendation: **yes**.
- [x] **D-05 — Self-merge:** remove it from v1 autonomous behavior and make it a later, explicit repository policy. Recommendation: **yes**.
- [x] **D-06 — Intent storage:** keep descriptive intent repo-local but keep authorization snapshots and creator approvals in host/user state outside the repository. Recommendation: **yes**.
- [x] **D-07 — Parallelism:** disable autonomous parallel execution until sequential crash/resume and publication tests are stable. Recommendation: **yes**.
- [x] **D-08 — Release channels:** add immutable stable tags and retain `main` only as an explicitly labeled edge channel. Recommendation: **yes**.

## Master improvement checklist

### P0 — Repair the baseline before expanding behavior

- [x] Replace every GNU-only `sed -i` fixture mutation in `scripts/test-validators.sh` with a portable temp-file-and-move helper or a small Python mutation helper.
- [x] Extend `scripts/check-portability.sh` to reject unportable in-place `sed` usage.
- [x] Add a seeded meta-test proving the portability guard catches `sed -i`.
- [x] Remove the duplicate artifact-eval invocation from `scripts/check-all.sh`.
- [x] Add macOS and Windows jobs to the required preflight workflow; keep Ubuntu.
- [x] Add a lightweight ShellCheck job or locally reproducible ShellCheck command for all Bash files.
- [x] Make validator success output concise by default and add `--verbose` for the full per-invariant list.
- [x] Correct Claude plugin installation examples so namespaced and manual invocations are clearly distinguished.
- [x] Update `docs/goal_command_codex.md` with the current `features.goals` enablement check and Goal lifecycle controls.
- [x] Add a `pathfinder doctor`/status capability row showing native Goal availability, controller availability, Git/forge capabilities, sandbox enforcement, network policy, and publication readiness.

### P1 — Correct the authority and intent model

- [x] Remove clarity-gated automatic escalation from ordinary exploration; require explicit per-run autonomy authorization.
- [x] Split stored `intent_clarity` from per-item `execution_eligibility`; never make a durable project field depend on a later item proof.
- [x] Make the authorization snapshot immutable for the duration of a mission and bind it to intent versions plus the selected base commit.
- [x] Prohibit autonomous edits to `.pathfinder/charter.md` and `.pathfinder/doctrine.md`; update only the roadmap and run evidence automatically.
- [x] Require an explicit creator refresh to change charter/doctrine policy.
- [x] Replace `manual-approval-required` with two unambiguous states: `human-review-required` and `pre-action-approval-required`.
- [x] Define a deterministic status/safety enum and reject unknown values instead of inferring their meaning from prose.
- [x] Store creator approvals outside the repository trust boundary, or require explicit per-run authorization when secure host storage is unavailable.
- [x] Version and migrate every intent schema; never treat presence of a marker string as schema validity.
- [x] Add a protected-surface registry that is data-driven, versioned, and overridable only through explicit additive policy—not repository prose. Seal and hash-bind the effective policy per mission, and reject undeclared protected paths before state advances.

### P1 — Add canonical schemas and state

- [x] Add real JSON Schemas for candidates, verification, Goal Binding, runtime boundary, mission state, run log, final summary, charter, roadmap, and doctrine.
- [x] Validate JSON with a real parser before schema checks; reject duplicate keys, unknown enum values, missing required fields, and malformed timestamps.
- [x] Make JSON the source of truth and render Markdown views from it, eliminating drift between human and machine artifacts.
- [x] Give each mission, goal, attempt, worktree, branch, commit, and PR a stable identifier.
- [x] Define an append-only event log and a compact current-state snapshot.
- [x] Define allowed state transitions, including `planned`, `authorized`, `prepared`, `running`, `verifying`, `verified`, `committed`, `published`, `awaiting-review`, `merged`, `blocked`, and `abandoned`.
- [x] Write state atomically and use a lock/lease so two Pathfinder processes cannot resume the same mission concurrently.
- [x] Record the base commit and dirty-tree policy in the Goal Binding.
- [x] Refuse resume when the base, binding, intent snapshot, or worktree has drifted without an explicit reconciliation transition.
- [x] Add schema migrations with golden old-version fixtures.

### P1 — Implement native Goal adapters

- [x] Add a Codex adapter that detects native Goal support and uses the host Goal lifecycle rather than only printing Markdown.
- [x] Before creating a Codex Goal, inspect existing Goal state and route to resume, finish, or user-controlled clear; never overwrite an unfinished Goal.
- [x] Bind Codex Goal completion to controller-validated evidence and mark complete only after the objective actually holds.
- [x] Respect host-specific blocked semantics and budget limits; do not equate a single failed loop with host-level `blocked`.
- [x] Add a Claude adapter for `/goal`, including version/hook availability checks and clear manual handoff when the command cannot be activated programmatically.
- [x] Keep the Implementation Goal fallback, but label it as non-persistent and require explicit continuation behavior.
- [x] Add a capability negotiation record to every Goal Binding and test all three adapter paths.
- [x] For goal packs, activate only one native Goal at a time and persist the queue in mission state. *(An explicit `run all` authorization now seals ordered binding hashes; atomic pack state delegates to isolated one-Goal child missions, requires a matching typed `complete-goal` receipt before advancing, and stops without starting later work on block, ambiguity, abandonment, or deadline expiry.)*

### P1 — Build the sequential autonomous controller

- [x] Implement a read-only repository capability probe before any mission writes.
- [x] Detect Git root, subproject scope, current branch, base commit, remote type, default branch, dirty state, hooks configuration, and worktree support.
- [x] Define a dirty-tree policy: default to blocking autonomy; optionally allow an explicit committed-base run that ignores uncommitted changes and says so before Goal generation.
- [x] Create mission worktrees through one controller function; verify the resolved path, ownership, base commit, and absence of symlink escapes. *(The enabled host bridge delegates this action to an attested host and validates the typed receipt; `WorktreeManager` is not a production caller in that bridge.)*
- [x] Neutralize repository hooks for every controller-owned Git command that can trigger them, not just commit and push.
- [x] Avoid `git pull` as an opaque step; fetch, resolve the exact remote base, verify fast-forward ancestry, then create/rebase deterministically.
- [x] Run exactly one goal at a time in v1.
- [x] Add a real `mission start/next/record/resume` host bridge and one typed offline end-to-end mission; unsupported native Goal hosts stop at a manual handoff instead of inventing lifecycle support.
- [x] Journal an immutable intent before every host action, then persist its typed receipt and terminal result before advancing state.
- [x] On restart, recover from persisted receipts/results and require explicit host reconciliation when actual Git/Goal state is ambiguous; never replay the last action by assumption.
- [x] Detect and reuse an existing branch/PR for the same attempt; never create duplicate PRs after a timeout. *(This remains a separately fixture-tested publication primitive, not an enabled host-bridge action.)*
- [x] Preserve recoverable blocked work without carrying its diff into the next goal.
- [x] Add safe worktree cleanup/status commands; never delete a dirty or unmerged worktree automatically.
- [x] Disable the Opportunity Scout by default in v1; when enabled later, cap derived goals at the run’s initial immutable limit.
- [x] Enforce fixed maxima in the enabled bridge: one active Goal and stable attempt, an explicitly approved pack's fixed Goal count/order, authorization limits no wider than each Goal Binding, restart-stable mission/pack wall deadlines, and zero open/total PRs. Token/cost accounting remains an explicit non-guarantee until a host exposes it.

### P1 — Enforce execution and publication safety

- [x] Convert Runtime Boundary fields from disclosure-only metadata into an eligibility gate: unattended execution requires known, enforceable filesystem, network, secret, and process isolation.
- [x] If sandboxing cannot be enforced, stop at a generated Goal or verified local plan; do not simulate isolation in prose.
- [x] Build commands from structured controller decisions; never execute raw command text copied from repository content, docs, test output, or model prose.
- [x] Add deterministic deny rules for secret files, key material, credential stores, destructive Git/database operations, release commands, and external side effects.
- [x] Run implementation and verification in an environment without GitHub/forge credentials, credential-helper access, unnecessary network, or host secret mounts.
- [x] Introduce publication credentials only in a separate publication process with a narrow command allowlist.
- [x] Treat local credential helpers and keychains as credential exposure even when no environment variable is set.
- [x] Record hashes of executed command argv, environment policy, working directory, timeout, exit status, and relevant output artifact—not raw secrets.
- [x] Make GitHub publication idempotent using head branch + base + mission metadata.
- [x] Poll required checks with a bounded timeout and distinguish failure, pending, missing permission, and unavailable API.
- [x] Default publication to `awaiting-review`; keep self-merge out of v1.
- [ ] When self-merge is reconsidered, support both branch protection and repository rulesets and require an explicit repo policy plus positive API evidence.
- [x] For non-GitHub remotes, stop at a verified local branch until an adapter exists.
- [x] For non-Git repositories, provide discovery and Goal generation only.

Completion qualifier: structured command, worktree, and GitHub publication components are tested
controller primitives, but the enabled `mission start/next/record/resume` bridge delegates local
side effects to an attested host. It validates Runtime Boundary claims, immutable intents, typed
receipts, and zero-publication budgets; it does not independently observe the host sandbox or
compose the publisher. Those limits are explicit non-guarantees, not implied production wiring.

### P2 — Make Pathfinder substantially faster and easier to use

- [x] Reduce `SKILL.md` to a thin router, trust boundary, and required route-loading rules.
- [x] Move explore, prompt-to-goal, intent-refresh, autonomous, status, and reviewer workflows into separate route references loaded only when needed.
- [x] Replace hand-copied rule mirrors with canonical schema/config fragments and generated documentation where practical. *(The highest-value data mirror—the protected-surface category/path table—is now deterministically generated from the versioned baseline and checked locally, in packaged archives, and on all hosted platforms; behavioral prose remains explicitly guarded rather than mechanically generated.)*
- [x] Make prompt-to-goal independent of the full Doctrine Interview; ask only unresolved Goal-contract questions.
- [x] Require the deep creator interview only before explicit autonomous execution or an explicit creator-model refresh.
- [x] Add a fast path for a well-formed prompt: targeted search, proof discovery, one recognition screen, then native Goal activation.
- [x] Start exploration with one repository map and expand scouts only where uncertainty or risk justifies the cost.
- [x] Replace the default five-scout/three-verifier fan-out with an adaptive evidence budget and hard maximum.
- [x] Cache read-only discovery by base commit and scoped path fingerprint; invalidate only affected surfaces.
- [x] Add monorepo namespaces so charter/roadmap/doctrine can be scoped to a subproject without conflating unrelated products. *(Root intent keeps the existing `.pathfinder/` layout; an explicit normalized subproject path maps to `.pathfinder/scopes/<scoped-root>/intent/`, with isolated locks/documents, no root-or-sibling fallback, path/symlink rejection, creator-confirmed CLI activation, and crash rollback.)*
- [x] Render a compact status summary from controller state instead of rereading every Markdown artifact.
- [x] Add `--json`/structured status for automation and concise human status for interactive use.
- [x] Keep artifacts useful but stop creating placeholders for every unused phase; represent lifecycle explicitly in the state snapshot and render placeholders only when a human view needs them. *(Prompt and full-exploration routes now omit intentionally skipped phases and unselected scout domains; autonomous mission views derive active/terminal lifecycle from controller state.)*
- [x] Limit default run artifacts to evidence required for resume, audit, and evaluation; make verbose scout prose optional. *(Full exploration records its evidence budget once, writes compact briefs only for selected domains, and makes expanded narrative opt-in or evidence-justified.)*
- [x] Add progress updates at meaningful checkpoints rather than per invariant or per file. *(The always-loaded route contract now reports route/evidence/Goal/execution transitions in a compact changed-evidence-next shape, while controller persistence remains independent from chat narration.)*

### P2 — Build evaluation that measures real behavior

- [x] Replace “JSON-shaped” assertions with parser + schema validation.
- [x] Parse the exact Goal payload and validate outcome, proof, constraints, scope, stop condition, and final evidence contract inside that payload.
- [x] Add negative fixtures where proof/constraints exist only in supporting notes and confirm they fail.
- [x] Add cross-artifact referential checks: candidate IDs, binding IDs, grades, attempts, commands, and final dispositions must agree.
- [x] Add controller unit tests for every allowed and forbidden state transition.
- [x] Add crash-point tests after worktree creation, command start, verification, commit, push, PR creation, and CI polling. *(Every controller action is exercised across intent, side-effect, receipt, result, and transition boundaries with an explicit action-set guard; persistent publication fixtures cover ambiguous push, exact PR reuse after a lost response, and bounded/reconcile-required check polling.)*
- [x] Add idempotency tests showing resume does not duplicate commits, branches, or PRs.
- [x] Add dirty-tree, symlink, malicious filename, hook, credential-helper, and command-injection fixtures.
- [x] Add prompt-injection fixtures covering source files, README/docs, tests, diffs, tool output, intent files, and prior artifacts.
- [x] Add GitHub API fixtures for branch protection, rulesets, auth failure, rate limit, pending checks, failed checks, merge conflict, and existing PR. *(Protected, unprotected, active-ruleset, and conflicted observations remain awaiting-review with zero merge attempts; typed auth/rate failures, bounded pending/failed checks, and exact existing-PR reuse are covered separately.)*
- [x] Add Linux/macOS/Windows controller tests.
- [x] Add recorded replay cases produced by actual Pathfinder runs. *(Sanitized local Claude Code dogfood now guards placeholder churn, ignored-path failure, and pre-approval repository execution; no credentials, private paths, or transcript text are retained.)*
- [x] Add a small optional live-model suite for the highest-value behaviors: question choice, intent preservation, safe routing, native Goal activation, and honest blocking.
- [x] Add a nightly dogfood run against tiny synthetic repositories; never point CI autonomy at arbitrary external repositories.
- [x] Add plugin install/load smoke tests for Claude Code and Codex when their non-interactive test surfaces are available. *(A credential-free isolated harness now installs the exact local snapshot on both hosts, proves Codex plugin and `.agents/skills` discovery through model-visible prompt JSON, and proves Claude strict validation plus parsed skill inventory. It deliberately does not invoke a model or claim native Goal/autonomy behavior.)*
- [x] Maintain a coverage matrix mapping every README autonomy promise to a deterministic test, a live/replay eval, or an explicitly documented non-guarantee.

### P3 — Harden distribution, operations, and documentation

- [x] Introduce `stable` and `edge` marketplace channels; stable resolves to an immutable release tag or commit.
- [x] Generate release notes from structured change metadata or validate the current `VERSION.md` extraction with cross-platform tests.
- [x] Smoke-install the exact release artifact before publishing a tag.
- [x] Publish a compatibility matrix for host versions, Goal support, Python/controller availability, Git/GitHub requirements, and supported operating systems.
- [x] Add an upgrade/migration command for intent and mission schemas.
- [x] Add an operator guide for pause, resume, abandon, inspect, clean up, and recover a mission.
- [x] Add a threat model covering repository injection, local intent tampering, hook execution, credential leakage, malicious tests, forge API confusion, duplicate publication, and compromised dependencies.
- [x] Clarify in the README which guarantees come from Pathfinder core and which still depend on host/model behavior.
- [x] Replace “reads code, never README” with the more accurate “defers docs until after a source-first pass.”
- [x] Add worked examples for GitHub, Git without a remote, non-GitHub Git, non-Git folders, monorepos, protected paths, and blocked sandbox capability.
- [x] Document retention and cleanup for ignored intent, run logs, worktrees, branches, and review packets.

### Implementation status note

The master checklist above is the completion record. The risk-ordered sub-prompts below are preserved as the original execution specification; their boxes are not a second status tracker. Completed behavior is also recorded in `PROGRESS.md` and must have a deterministic check, replay, or explicit non-guarantee. Two compositions remain deliberately deferred rather than implied complete: GitHub publication from the enabled host bridge and conditional self-merge. The publisher stays a separately tested primitive, and the separately reviewed self-merge plan at the end of this document enables no merge authority. Token/cost accounting also remains an explicit host-owned non-guarantee until the typed protocol exposes trustworthy usage.

## Next execution batch — close the real mission-runtime gap

### Investigation findings (2026-08-10)

1. `pathfinder_core/__main__.py` exposes `doctor`, mission `status`/`abandon`, migrations, and prompt artifacts; it has no mission `start`, `next`, `record`, `run`, or `resume` entry point.
2. `pathfinder_core/mission.py` accepts a `MissionCallbacks` protocol, but the only implementation is `FakeCallbacks` in `tests/integration/test_one_goal_mission.py`.
3. Codex, Claude, worktree, execution, and GitHub components exist independently, but no production composition root connects them into one mission.
4. `doctor.runner_available` currently means Python plus schema dependencies are importable; it does not mean an autonomous mission runner is callable.
5. `unattended_execution_eligible` cannot become true through the current CLI because host enforcement evidence has no input/attestation path and all four enforcement capabilities are hard-coded `unknown`.
6. Resume tests crash only after state transitions. They do not cover a crash after a callback performs a side effect but before the following checkpoint.
7. The transition event schema reserves `command-started` and `command-finished`, but `MissionStore` writes only transition events and couples event sequence to state revision, so those event types are not currently usable.
8. Worktree creation and exact PR lookup have local idempotency primitives; native Goal activation, arbitrary implementation commands, commit, push, PR creation, and CI polling lack one shared durable operation protocol.
9. The threat model correctly discloses command-boundary journaling as absent, while README and compatibility prose still describe autonomous execution as supported when capabilities are present. The executable path needed to make that condition true does not yet exist.
10. Official OpenAI Goal guidance documents an interactive host lifecycle (`/goal`, inspect/control, pause/resume/clear), not a Python API the plugin controller can assume. A host bridge must therefore request native Goal actions from the active host and record their results rather than pretending the Python process owns that API.

**Size:** large. This crosses capability reporting, mission/operation schemas, durable storage, CLI protocol, host adapters, integration tests, and public guarantees. A test-only patch would preserve the underlying non-runnable design.

**Goal restated:** from a clean Git fixture and an explicit authorization snapshot, a host can start and resume one controller-owned Goal mission through a documented CLI protocol, with every side-effecting action durably identified and ambiguous crashes stopping for reconciliation instead of being replayed.

**Blast radius:** mission-local ignored state, a dedicated worktree/branch, optional local commits, native Goal state, and eventually one awaiting-review PR. No auth/payment/user database is in scope. Local work is recoverable; commit, push, PR creation, and host Goal mutation are external side effects and require exact reconciliation identities. No live credentials or network calls belong in required tests.

**Assumptions and decisions:**

- Use a stepwise host bridge, not a Python subprocess that launches Codex or Claude. Recommendation: the controller returns one typed action; the active host executes only that action and returns a typed receipt.
- A missing completion receipt after an action starts is `reconcile-required`, never implicit permission to retry. Retry is allowed only when a concrete adapter proves the prior side effect did not occur.
- Keep transition revision/events unchanged in the first slice. Add a separate append-only operation receipt contract keyed by stable operation id; do not overload the currently revision-coupled transition sequence.
- Make a verified local branch the first runnable milestone. Keep credentialed GitHub publication behind the existing separate boundary until local start/resume/crash behavior is green.
- Keep native Goal creation host-mediated. The controller validates the requested objective and receipt identity but never claims a programmatic host API it cannot access.
- Preserve `runner_available` for compatibility only if its meaning is made explicit. Add a distinct `mission_runner_available`/host-bridge capability and fail closed until the bridge is actually callable.

**Missing pieces this batch must supply:** a host-attested runtime-boundary input, mission initialization request, typed next-action/result schemas, durable operation intent/result receipts, pending-operation inspection, exact reconciliation outcomes, CLI start/next/record/resume commands, a non-fake local mission integration, and honest capability/docs output.

### Phase A — make availability claims honest

**Goal:** separate “controller library importable” from “autonomous mission bridge runnable” before adding more behavior, so unsupported hosts fail closed for the correct reason.

**Preconditions:** clean worktree; current 83-test baseline and hosted checks green.

#### Sub-prompt R1 — capability truthfulness

- [ ] `[writes code]` Change only `pathfinder_core/capabilities.py`, `tests/core/test_capabilities.py`, public capability/autonomy documentation, the autonomous skill route, and its consistency guard; stop before touching mission execution. The caller scan expanded the original file boundary because leaving the route and install/example docs unchanged would preserve a contradictory execution claim.
- [ ] First present a short plan. Imitate the existing capability rows and concise compatibility-table language.
- [ ] Distinguish controller/schema availability from a callable mission host bridge. Existing `runner_available` consumers must either retain a precisely documented compatibility meaning or receive an additive migration; do not silently redefine it.
- [ ] Required tests must pass unmodified in meaning. Add a negative assertion proving importable Python/schema dependencies alone cannot report mission execution available.
- [ ] Before deleting or renaming any field, show `rg -n 'runner_available|unattended_execution_eligible'` evidence for every caller and stop if compatibility cannot be preserved additively.
- [ ] Expected diff: 60–120 lines. Stop and split documentation from code if it exceeds 150 lines.
- [ ] Verify with `.venv/bin/python -m unittest tests.core.test_capabilities`, `bash scripts/check-manifests.sh .`, and `bash scripts/check-all.sh .`; the doctor JSON must distinguish controller availability from mission-runner availability.
- [ ] Append one line to `PROGRESS.md` recording the corrected claim, verification, and any contradiction.
- [ ] Stop condition: if a callable production mission entry point already exists outside `pathfinder_core/__main__.py`, record its exact path in `PROGRESS.md` and revise this batch instead of adding a second entry point.

**Rollback:** revert the additive capability/docs commit; no mission state is written.

### Phase B — define and persist a crash-safe operation contract

**Goal:** give every side-effecting host/controller action a stable, append-only intent and terminal receipt before wiring the runtime.

**Preconditions:** Phase A passes; no public surface claims the mission runner is available.

#### Sub-prompt R2 — operation schema

- [ ] `[writes code]` Add only `schemas/mission/operation-intent.schema.json`, `schemas/mission/operation-result.schema.json`, focused fixtures, and `tests/contracts/test_mission_schemas.py`; stop before production storage code.
- [ ] First present a schema plan. Imitate `schemas/mission/event.schema.json` IDs/timestamps and `schemas/artifacts/run-log.schema.json` command evidence.
- [ ] Cover stable operation id, mission/attempt id, stage, action kind, request hash, authority/runtime snapshot hashes, start time, terminal outcome (`succeeded`, `failed`, `not-observed`, `reconcile-required`), redacted result evidence, and completion time. Unknown fields/enums and duplicate keys must fail.
- [ ] Do not place secrets, raw environment values, full command output, or forge credentials in receipts.
- [ ] Existing tests must pass unmodified. No deletion is expected; show zero-caller evidence before replacing the dormant command event types.
- [ ] Expected diff: 100–150 lines; split intent and result fixtures if larger.
- [ ] Verify with `.venv/bin/python -m unittest tests.contracts.test_mission_schemas` and JSON parsing over every new fixture.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop condition: if one receipt cannot represent both host-native Goal actions and controller-owned Git/command actions without weakening validation, record the mismatch and split the schemas by authority owner.

#### Sub-prompt R3 — operation journal storage

- [ ] `[writes code]` Add only `pathfinder_core/operations.py` and `tests/core/test_operations.py`; touch `pathfinder_core/storage.py` only if a reusable atomic-read/write primitive is strictly required.
- [ ] First present a plan. Imitate `MissionStore` atomic writes, duplicate-key rejection, and idempotent equality checks.
- [ ] Persist immutable `<operation-id>.intent.json` and one terminal `<operation-id>.result.json`; identical retries are no-ops, different retries fail, result-before-intent fails, and started-without-result loads as pending/reconcile-required.
- [ ] Existing tests must pass unmodified. Show callers before changing any storage primitive.
- [ ] Expected diff: 100–150 lines per production/test file; split before exceeding the bound.
- [ ] Verify with `.venv/bin/python -m unittest tests.core.test_operations tests.core.test_state`, including crashes before intent write, after intent write, after result write, and during atomic replacement.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop condition: if the journal needs to mutate or renumber existing transition events, stop and write a migration plan before changing `MissionStore`.

**Rollback:** remove the new operation files/code while preserving any created mission folder for inspection; never auto-delete user worktrees.

### Phase C — expose a host-driven local mission protocol

**Goal:** make one no-publication mission actually startable and resumable without embedding a model subprocess or fake callback implementation.

**Preconditions:** operation contract/storage green; runtime remains unavailable in `doctor` until the final integration test passes.

#### Sub-prompt R4 — typed host action protocol

- [ ] `[writes code]` Add only `pathfinder_core/host_protocol.py`, its schemas under `schemas/mission/`, and `tests/core/test_host_protocol.py`.
- [ ] First present a plan. Imitate adapter result enums and the mission authorization/runtime schemas.
- [ ] Define one-action-at-a-time requests for `prepare-worktree`, `activate-goal`, `implement`, `verify`, `commit`, and `publish`, plus typed receipts and the `reconcile-required` response. Repository text may populate evidence fields but never action kind, authority, policy, or credentials.
- [ ] Existing tests must pass unmodified. No public adapter deletion or rename is allowed.
- [ ] Expected diff: 100–150 lines per protocol/schema slice.
- [ ] Verify with `.venv/bin/python -m unittest tests.core.test_host_protocol tests.adapters` and negative forged-operation/authority/runtime fixtures.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop condition: if the active host cannot return a stable native Goal identity, define a manual/non-persistent blocked handoff; do not fabricate an id.

#### Sub-prompt R5 — mission start/next/record/resume CLI

- [ ] `[writes code]` Change only `pathfinder_core/mission.py`, `pathfinder_core/__main__.py`, one new composition module if necessary, `scripts/pathfinder-controller.sh`, and `tests/integration/test_one_goal_mission.py`.
- [ ] First present a plan and CLI transcript. Imitate existing JSON error output and `MissionStore` transitions.
- [ ] Add validated `mission start`, `mission next`, `mission record`, and `mission resume/status` behavior for a local, no-publication mission. Each side effect must have an operation intent before the host acts and a validated result before state advances.
- [ ] A pending operation returns `reconcile-required`; it never calls the action again automatically. Terminal missions remain idempotent. Keep GitHub credentials and live publication out of this slice.
- [ ] Existing tests must pass unmodified in meaning. Show all `MissionOrchestrator` callers before changing its protocol; retain a compatibility wrapper or migrate every caller explicitly.
- [ ] Expected diff: 100–150 lines per command/protocol slice; split initialization, next-action, and receipt handling into separate commits.
- [ ] Verify with `.venv/bin/python -m unittest tests.integration.test_one_goal_mission`, a fixture CLI transcript from start through verified local branch, and `bash scripts/check-all.sh .`.
- [ ] Append one `PROGRESS.md` line per slice.
- [ ] Stop condition: if the CLI would need to shell-launch Codex/Claude, access host credentials, or accept raw repository command text, stop and keep mission-runner availability false.

**Rollback:** disable the additive mission commands/capability first, then revert protocol commits. Preserve mission state and worktrees for manual recovery.

### Phase D — prove crash reconciliation before publication

**Goal:** seed every ambiguous boundary and prove at-most-once transition records plus fail-closed external side-effect handling.

**Preconditions:** a real fixture host bridge completes a no-publication mission; no live network or credential dependency.

#### Sub-prompt R6 — crash matrix

- [ ] `[writes code]` Add only focused fixtures and tests under `tests/integration/`, `tests/core/`, and `tests/adapters/`; production changes are forbidden in this sub-prompt.
- [ ] First present a matrix for crashes before intent, after intent/before action, after side effect/before result, after result/before transition, and after transition for worktree, Goal activation, implementation command, verification, commit, push, PR creation, and CI polling.
- [ ] Imitate `test_resume_after_every_checkpoint_does_not_duplicate_side_effects`, but use persistent fake backends that retain real-world state across orchestrator instances.
- [ ] Assert: at most one branch/commit/PR record; no blind replay after ambiguous Goal/command/push state; exact existing PR reuse; bounded check polling; and explicit `reconcile-required` or blocked state when proof is unavailable.
- [ ] Existing tests must pass unmodified. A failing new fixture is reported against the responsible lower-level phase; do not weaken the expected outcome or patch production here.
- [ ] No deletion is expected. Expected diff: under 150 lines per side-effect family.
- [ ] Verify with `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` and `bash scripts/check-all.sh .` on Ubuntu, macOS, and Windows.
- [ ] Append one result line per side-effect family to `PROGRESS.md`.
- [ ] Stop condition: when a backend cannot distinguish “did not happen” from “happened but response was lost,” require reconciliation/user inspection; never classify it retry-safe by assumption.

#### Sub-prompt R7 — enable and document the verified bridge

- [x] `[writes code]` Change capability reporting, the autonomous router/route, public capability/autonomy documentation and metadata, and matching focused tests/guards. The caller scan expanded the original boundary because install, example, operating-kernel, and plugin descriptions otherwise retain false “bridge unavailable” claims.
- [x] First present a guarantee-delta plan. Imitate the current fail-closed capability and guarantee-boundary language.
- [x] Report `mission_runner_available` only when the host bridge is callable; report unattended eligibility separately and keep it false until runtime attestation validates. Document the exact start/next/record/resume flow and retain the explicit Goal-only fallback.
- [x] Existing tests pass unmodified in meaning. All old “bridge unavailable” and overbroad autonomous-support claims were scanned before replacement.
- [x] Keep capability enablement and public prose in separate commits so each remains reviewable.
- [x] Verify with `bash scripts/check-all.sh .`, exact-archive package smoke, one offline synthetic host-bridge replay, and bounded Codex/Claude dogfood that creates no commit, push, PR, or publication.
- [x] Append the required result line to `PROGRESS.md`.
- [x] Codex currently proves only typed manual handoff and Claude was not launched; both remain Goal-only unless the active host can return stable native Goal identities and typed receipts.

**Rollback:** set mission-runner capability unavailable and restore Goal-only routing before reverting implementation. Do not delete saved mission evidence.

### Risks, confidence, and exclusions

**What could go wrong:** (1) a model-generated receipt could be mistaken for controller evidence, so operation authority and hashes must be controller-derived; (2) a host Goal side effect may be impossible to reconcile after a lost response, which must block rather than retry; (3) adding a second journal could drift from mission state unless stable IDs and cross-validation are mandatory.

**Least confidence:** the exact typed-action surface Codex and Claude can both honor from a plugin skill without a dedicated native plugin API. Validate the smallest offline transcript first, then perform bounded host dogfood before changing support claims.

**Do not do:** do not launch agent CLIs as subprocesses, add self-merge, enable live publication, redesign goal packs, renumber existing transition events, migrate intent namespaces, or expand forge support in this batch. Those are separate projects.

## Risk-ordered implementation phases

### Phase 0 — Restore a trustworthy baseline

**Goal:** make the current repository checks honest, portable, concise, and green before using them to guard larger changes.

**Preconditions:** the plan is committed or otherwise preserved; the worktree is clean; `jq`, Bash, Git, and Python 3 are available.

#### Sub-prompt P0.1 — portable validator mutations

- [ ] `[writes code]` Fix only the macOS portability defect in `scripts/test-validators.sh` and the matching detection in `scripts/check-portability.sh`; stop and report before touching any other file.
- [ ] First present a short implementation plan, then edit.
- [ ] Imitate the existing temp-file-and-`mv` mutation pattern at `scripts/test-validators.sh:84-86`.
- [ ] Replace GNU-only `sed -i` calls without weakening or deleting any seeded behavioral assertion; add one negative portability fixture that proves GNU-only in-place syntax is rejected.
- [ ] Existing unrelated tests must pass unmodified; report a failing test rather than editing it to hide the failure.
- [ ] For any deletion or helper replacement, show `rg` evidence that no remaining caller depends on the old form.
- [ ] Expected diff: 40-90 lines. Split and stop if it would exceed 150 lines.
- [ ] Verify with `bash scripts/test-validators.sh .`, `bash scripts/check-portability.sh .`, and `bash scripts/check-all.sh .`; all must exit 0 on macOS.
- [ ] End by appending one line to `PROGRESS.md` recording work, verification, and contradictions found.
- [ ] Stop condition: if the failure is not caused by BSD/GNU `sed` incompatibility, record the evidence in `PROGRESS.md` and stop without improvising another fix.

#### Sub-prompt P0.2 — remove duplicate eval execution

- [ ] `[writes code]` Change only `scripts/check-all.sh`; stop before touching any other file.
- [ ] First present a short implementation plan, then edit.
- [ ] Imitate the surrounding `run_check` calls.
- [ ] Remove the duplicate artifact-eval invocation and keep the intended ordering exactly once.
- [ ] Existing tests must pass unmodified; report failures, never edit them.
- [ ] Show `rg -n 'artifact evals' scripts/check-all.sh` before and after as zero-caller/de-duplication evidence.
- [ ] Expected diff: under 10 lines.
- [ ] Verify with `bash scripts/check-all.sh .`; expected final line: `check-all: all checks pass` and only one artifact-eval section.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if two invocations serve distinct documented purposes; record that contradiction and stop.

#### Sub-prompt P0.3 — required platform matrix

- [ ] `[writes code]` Add the required Ubuntu/macOS/Windows preflight matrix in `.github/workflows/manifests.yml` and update only `CONTRIBUTING.md`; stop before touching other files.
- [ ] First present a short implementation plan, then edit.
- [ ] Imitate the existing `jobs.check` workflow and the portability wording in `CONTRIBUTING.md:24-49`.
- [ ] Keep actions SHA-pinned and install only the already documented `jq` prerequisite.
- [ ] Existing tests and checks must pass unmodified; report failures rather than weakening jobs.
- [ ] Show search evidence before deleting or replacing the old single-runner job.
- [ ] Expected diff: 40-100 lines.
- [ ] Verify with `bash scripts/check-portability.sh .`, `bash scripts/check-manifests.sh .`, and a successful three-OS GitHub Actions run.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if the project does not intend to support one of the three advertised platforms; record the mismatch and request a support-matrix decision.

#### Sub-prompt P0.4 — invocation and Codex Goal documentation

- [ ] `[writes code]` Correct only `README.md`, `README-INSTALL.md`, and `docs/goal_command_codex.md`; stop before changing skill behavior or manifests.
- [ ] First present a short implementation plan, then edit.
- [ ] Imitate the concise installation sections already present in both README files and the lifecycle style in `docs/goal_command_codex.md:39-88`.
- [ ] Distinguish Claude plugin `/pathfinder:pathfinder`, manual Claude `/pathfinder`, Codex `$pathfinder`, and Codex native `/goal`; add official `features.goals` enablement guidance with an authoritative link.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] For any deletion or removed invocation example, show search evidence for every remaining caller/reference first.
- [ ] Expected diff: 30-80 lines.
- [ ] Verify with `bash scripts/check-manifests.sh .`, `bash scripts/check-skill-consistency.sh .`, and `rg -n '/pathfinder(:pathfinder)?|features.goals|features enable goals' README.md README-INSTALL.md docs/goal_command_codex.md`.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if current host behavior cannot be confirmed; record the unresolved product fact instead of guessing.

**Phase verification:** `bash scripts/check-all.sh .` exits 0 on Linux, macOS, and Windows; the output contains one artifact-eval run.

**Rollback:** revert the four isolated commits individually; no schema or user state is migrated in this phase.

**Decision:** whether ShellCheck is required immediately or added in Phase 4. Recommendation: add it now if its version can be pinned and reproduced locally.

### Phase 1 — Freeze and formalize the contracts

**Goal:** remove ambiguous authority semantics and define machine-checkable state before building an executor.

**Preconditions:** Phase 0 is green on all required platforms; clean worktree.

#### Sub-prompt P1.1 — autonomy decision record

- [ ] `[writes code]` Create only `docs/specs/autonomous-controller-contract.md`; do not edit shipped behavior yet.
- [ ] First present a short plan, then write the decision record.
- [ ] Imitate `docs/superpowers/specs/2026-07-03-artifact-first-evals-design.md` for sections and decision tables.
- [ ] Ratify D-01 through D-07, define explicit per-run authority, v1 scope, non-goals, threat boundaries, and degradation behavior.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] No deletion is expected; if replacing another spec is proposed, show zero-caller evidence and stop for review.
- [ ] Expected diff: 100-150 lines.
- [ ] Verify with a manual review against every P1 finding F-06 through F-16 and `git diff --check`.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if any decision remains unresolved; record the options and blocker rather than silently choosing.

#### Sub-prompt P1.2 — intent and eligibility schemas

- [ ] `[writes code]` Add only `schemas/intent/*.json` and `tests/contracts/test_intent_schemas.py`; stop before editing Markdown behavior.
- [ ] First present a short plan, then implement.
- [ ] Imitate the field names in `charter-template.md`, `roadmap-template.md`, and `doctrine-template.md`, but separate `intent_clarity` from item `execution_eligibility`.
- [ ] Use Python standard-library JSON parsing plus a mature pinned validator for the declared schema dialect; do not build an incomplete ad hoc JSON Schema interpreter.
- [ ] Existing tests must pass unmodified; add new tests rather than weakening current assertions.
- [ ] For any deletion, removal, or enum rename, show zero-reference/caller evidence first.
- [ ] Expected diff: 100-150 lines; split charter/doctrine and roadmap eligibility if larger.
- [ ] Verify with `python3 -m unittest tests.contracts.test_intent_schemas` and negative fixtures for missing fields, bad enums, duplicate keys, and stale versions.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if JSON cannot faithfully represent the ratified contract; record the schema gap and revise the decision record first.

#### Sub-prompt P1.3 — mission and artifact schemas

- [ ] `[writes code]` Add only `schemas/artifacts/*.json`, `schemas/mission/*.json`, and `tests/contracts/test_mission_schemas.py`.
- [ ] First present a short plan, then implement.
- [ ] Imitate `artifact-structure.md:28-54` and `evals/fixtures/good-goal/artifacts/*.json` for names, not for their currently incomplete field coverage.
- [ ] Define stable IDs, allowed transitions, runtime boundary, Goal Binding, authorization snapshot, attempts, budgets, commands, Git state, and publication state.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before dropping an existing sidecar field.
- [ ] Expected diff: 100-150 lines per schema group; split rather than exceed the bound.
- [ ] Verify with `python3 -m unittest tests.contracts.test_mission_schemas` and `python3 -m json.tool` over every fixture/schema JSON file.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if a transition cannot be made idempotent; record the ambiguous transition and return to P1.1.

#### Sub-prompt P1.4 — align shipped policy prose

- [ ] `[writes code]` Update only `skills/pathfinder/SKILL.md`, the three intent templates, `artifact-structure.md`, `operating-kernel.md`, and `README.md` to match the ratified contract.
- [ ] First present a short plan, then edit one semantic concern per commit.
- [ ] Imitate the explicit safety language in `operating-kernel.md`.
- [ ] Remove auto-escalation authority, prevent autonomous charter/doctrine mutation, and replace the misleading manual-approval disposition.
- [ ] Existing tests must pass unmodified in meaning; update only drift guards whose expected canonical wording legitimately changes, never to conceal a regression.
- [ ] For every deleted rule, show `rg` evidence of all mirrors/callers before removal.
- [ ] Expected diff: under 150 lines per concern; split into at least three commits if necessary.
- [ ] Verify with `bash scripts/check-all.sh .` plus schema contract tests.
- [ ] Append one `PROGRESS.md` line per concern/commit.
- [ ] Stop if shipped prose would diverge from P1.1; revise the decision record explicitly first.

**Phase verification:** all intent/mission fixtures parse and validate; forbidden transitions and stale authorization snapshots fail; `bash scripts/check-all.sh .` exits 0.

**Rollback:** revert policy and schema commits together to avoid prose/schema mismatch. Do not migrate real `.pathfinder/` state until Phase 5.

**Decisions:** D-01 through D-07 must be resolved before P1.4. Recommendation: accept all seven defaults above.

### Phase 2 — Build a safe sequential controller

**Goal:** make one explicitly authorized Goal run resumably in an isolated Git worktree without publication duplication or unverifiable safety claims.

**Preconditions:** Phase 1 schemas and authority contract are stable; clean worktree; Python 3.11 selected for v1.

#### Sub-prompt P2.1 — controller skeleton and doctor

- [ ] `[writes code]` Add only `pathfinder_core/__main__.py`, `pathfinder_core/capabilities.py`, `pathfinder_core/errors.py`, and `tests/core/test_capabilities.py`.
- [ ] First present a short plan, then implement.
- [ ] Imitate CLI failure reporting from `scripts/check-evals.sh`, using concise machine-readable errors.
- [ ] Implement read-only `doctor --json` capability detection; no mission writes or repo commands beyond version/capability inspection.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] No deletion expected; show zero-caller evidence before replacing any script entrypoint.
- [ ] Expected diff: 100-150 lines; split if larger.
- [ ] Verify with `python3 -m unittest tests.core.test_capabilities` and `python3 -m pathfinder_core doctor --json`.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if a capability cannot be detected safely; return `unknown` and record it rather than probing by executing repository code.

#### Sub-prompt P2.2 — atomic mission state machine

- [ ] `[writes code]` Add only `pathfinder_core/state.py`, `pathfinder_core/storage.py`, and `tests/core/test_state.py`.
- [ ] First present a short plan, then implement.
- [ ] Imitate the schemas from Phase 1 exactly.
- [ ] Implement allowed transitions, atomic writes, append-only events, lock/lease handling, and recovery after an interrupted write.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before removing a transition or field.
- [ ] Expected diff: 100-150 lines per file group; split storage from transitions if larger.
- [ ] Verify with `python3 -m unittest tests.core.test_state`, including concurrent-resume and crash-write cases.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if filesystem locking cannot be portable; record the unsupported platform and choose an explicit degraded mode.

#### Sub-prompt P2.3 — repository and worktree adapter

- [ ] `[writes code]` Add only `pathfinder_core/repository.py`, `pathfinder_core/worktrees.py`, and their tests.
- [ ] First present a short plan, then implement.
- [ ] Imitate the path validation and ignored-artifact safety rules at `SKILL.md:158-234`.
- [ ] Implement Git/non-Git detection, dirty-tree block, exact base commit, safe worktree path resolution, hook-neutralized Git invocation, and recoverable cleanup status.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] For deletion/cleanup behavior, prove zero unmerged commits, zero dirty files, and zero active mission references before permitting removal.
- [ ] Expected diff: 100-150 lines per concern; split probing, creation, and cleanup.
- [ ] Verify with `python3 -m unittest tests.core.test_repository tests.core.test_worktrees` using temp repositories with malicious symlinks, hooks, dirty files, and unusual names.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if hook execution cannot be neutralized for a Git transition; mark that transition unsupported rather than running it.

#### Sub-prompt P2.4 — execution boundary

- [ ] `[writes code]` Add only `pathfinder_core/execution.py`, `pathfinder_core/policy.py`, and their tests.
- [ ] First present a short plan, then implement.
- [ ] Imitate the hard-stop categories in `operating-kernel.md:14-23` and the ratified threat model.
- [ ] Execute structured argv only; enforce cwd, timeout, environment allowlist, network/sandbox capability, secret path denylist, and output redaction.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show caller evidence before deleting an allow/deny rule.
- [ ] Expected diff: 100-150 lines per concern; split policy from process execution.
- [ ] Verify with `python3 -m unittest tests.core.test_execution`, including shell metacharacter, credential-helper, secret file, network-unknown, timeout, and malicious output cases.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if the host cannot enforce the declared boundary; return a blocking capability result and do not add a best-effort unattended path.

#### Sub-prompt P2.5 — native Goal adapters

- [ ] `[writes code]` Add only adapter protocol/types, Codex adapter instructions, Claude adapter instructions, generic fallback, and adapter contract tests under `pathfinder_core/adapters/` and `tests/adapters/`.
- [ ] First present a short plan, then implement.
- [ ] Imitate `capability-model.md` field names and official host lifecycle semantics.
- [ ] Support inspect/create/observe/complete/block capabilities without assuming every host permits every transition.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before changing any public adapter name.
- [ ] Expected diff: under 150 lines per adapter.
- [ ] Verify with `python3 -m unittest discover -s tests/adapters -p 'test_*.py'`; all capability matrices must pass.
- [ ] Append one result line per adapter to `PROGRESS.md`.
- [ ] Stop when a host API is unavailable; preserve a manual activation fallback rather than simulating native persistence.

#### Sub-prompt P2.6 — GitHub publication adapter

- [ ] `[writes code]` Add only `pathfinder_core/adapters/github.py` and fixture-driven tests; no live publication.
- [ ] First present a short plan, then implement.
- [ ] Imitate the default-deny publication contract in `SKILL.md:1393-1402`, tightened to awaiting-review only for v1.
- [ ] Implement credential-separated push, existing-PR lookup, idempotent PR creation, bounded CI polling, and explicit auth/rate-limit/error states.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before removing a publication state.
- [ ] Expected diff: 100-150 lines; split push, PR, and CI polling if larger.
- [ ] Verify with `python3 -m unittest tests.adapters.test_github`; fixtures must cover duplicate resume, auth error, timeout, failed checks, and success.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if implementation would self-merge or require live credentials in tests.

#### Sub-prompt P2.7 — one-goal mission orchestration

- [ ] `[writes code]` Add only `pathfinder_core/mission.py`, its CLI wiring, and `tests/integration/test_one_goal_mission.py`.
- [ ] First present a short plan, then implement.
- [ ] Imitate the Phase 1 state transitions and call only the controller components built in P2.1-P2.6.
- [ ] Orchestrate prepare -> activate Goal -> implement handoff -> verify -> bind -> commit -> optional PR -> awaiting-review, with checkpoint/resume after every step.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before replacing any transition.
- [ ] Expected diff: 100-150 lines; split transition groups rather than build a large function.
- [ ] Verify with `python3 -m unittest tests.integration.test_one_goal_mission` and crash injection at every transition.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if any step is not idempotent; record the transition and fix the lower-level adapter first.

**Phase verification:** `python3 -m unittest discover -s tests -p 'test_*.py'` and `bash scripts/check-all.sh .` exit 0; a synthetic mission survives every seeded crash and creates at most one branch and one PR record.

**Rollback:** disable the controller capability in the manifest/skill first, then revert controller commits. Preserve user mission state for inspection; do not delete worktrees automatically.

**Decisions:** publication remains awaiting-review only; non-GitHub and non-Git modes stop before publication.

### Phase 3 — Integrate the skill and optimize the user journey

**Goal:** make the shipped skill use the controller and native Goals while reducing prompt size and unnecessary interviewing.

**Preconditions:** one-goal controller integration is green; clean worktree; controller has a safe goal-only degradation path.

#### Sub-prompt P3.1 — thin route modules

- [ ] `[writes code]` Refactor only `skills/pathfinder/SKILL.md` and new route files under `skills/pathfinder/references/routes/`.
- [ ] First present a short plan and route inventory, then edit one route at a time.
- [ ] Imitate the existing supplemental-reference loading convention at `SKILL.md:77-90`.
- [ ] Keep the trust boundary and routing in the main skill; move route-specific workflows out and mark each route reference as required when selected.
- [ ] Existing behavioral tests must pass unmodified in meaning; update path/mirror guards only after route parity tests exist.
- [ ] Before deleting a main-skill section, show `rg` evidence of its new canonical location and all callers.
- [ ] Expected diff: under 150 lines per route; do not perform one giant rewrite.
- [ ] Verify each slice with `bash scripts/check-all.sh .` and a route-presence test.
- [ ] Append one result line per route to `PROGRESS.md`.
- [ ] Stop if the host cannot reliably load a required route reference; retain that route in the main skill.

#### Sub-prompt P3.2 — prompt-to-goal fast path

- [ ] `[writes code]` Change only the prompt-to-goal route, matching reference, and focused replay fixtures.
- [ ] First present a short plan, then edit.
- [ ] Imitate the current targeted research at `SKILL.md:259-325`, but remove the full Doctrine Interview prerequisite for non-autonomous Goal creation.
- [ ] Ask only unresolved outcome/proof/scope/safety/stop questions and activate the host-native Goal only after explicit user selection to run.
- [ ] Existing tests must pass unmodified; add fixtures rather than weakening them.
- [ ] Show zero-caller evidence before deleting old gate language.
- [ ] Expected diff: 80-150 lines.
- [ ] Verify with a recorded well-formed prompt requiring zero clarification and an ambiguous prompt requiring one focused screen.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if removing the interview would permit autonomous publication; keep goal creation and autonomous authority strictly separate.

#### Sub-prompt P3.3 — controller-backed autonomous route

- [ ] `[writes code]` Change only the autonomous route, controller invocation glue, and one integration replay.
- [ ] First present a short plan, then edit.
- [ ] Imitate the ratified Phase 1 authorization contract and the controller CLI—not the old prose loop.
- [ ] Require explicit per-run authorization, controller eligibility, immutable intent snapshot, one goal, fixed budget, and awaiting-review publication.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before removing auto-escalation, parallelism, self-merge, or doctrine-update text.
- [ ] Expected diff: 100-150 lines; split deletions and integration if larger.
- [ ] Verify with a replay that blocks without explicit authorization and a synthetic authorized run that reaches awaiting-review exactly once.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if controller capability is missing or unknown; fall back to saved Goal, never inline autonomous imitation.

#### Sub-prompt P3.4 — commit-fingerprint discovery cache

- [ ] `[writes code]` Add only discovery cache code, cache schema, and tests; do not change ranking policy.
- [ ] First present a short plan, then implement.
- [ ] Imitate the mission storage atomicity rules.
- [ ] Key cache entries by repo identity, base commit, scoped root, route, and relevant config fingerprint; invalidate conservatively.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before removing any existing fresh-read path.
- [ ] Expected diff: 100-150 lines.
- [ ] Verify with cache-hit, changed-file invalidation, branch change, monorepo scope, and stale-schema tests.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if cache use could cross repository identities or leak private paths; disable cache for that case.

**Phase verification:** route-level replays prove fast prompt-to-goal, explicit autonomy, safe degradation, and controller-backed resume; main `SKILL.md` is materially smaller; all checks pass.

**Rollback:** restore the old route entry while leaving the controller disabled. Preserve schemas and tests; they are backward-compatible evidence.

**Decision:** keep full exploration available, but make prompt-to-goal the recommended path when the user already has a concrete task.

### Phase 4 — Replace confidence-by-prose with behavioral evidence

**Goal:** prove that Pathfinder generates and runs correct Goals across failure, injection, platform, and resume scenarios.

**Preconditions:** controller-backed routes are complete; clean worktree; no live credentials in test environments.

#### Sub-prompt P4.1 — real JSON and Goal parsing

- [ ] `[writes code]` Change only `evals/harness/`, `scripts/check-evals.sh`, and focused fixtures/cases.
- [ ] First present a short plan, then implement parser/schema validation before semantic assertions.
- [ ] Imitate existing case definitions in `evals/cases/` and the new Phase 1 schemas.
- [ ] Validate the actual Goal payload, not unrelated Markdown notes; add supporting-note laundering negatives.
- [ ] Existing tests must pass unmodified in intent; bad fixtures must still fail for their named reason.
- [ ] Show zero-caller evidence before removing an assertion alias.
- [ ] Expected diff: 100-150 lines per assertion family.
- [ ] Verify with `bash scripts/check-evals.sh .` and `python3 -m unittest tests.contracts`.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if a legacy fixture lacks required fields; migrate it explicitly instead of weakening the schema.

#### Sub-prompt P4.2 — crash, idempotency, and security matrix

- [ ] `[writes code]` Add only test fixtures and tests for crash points, duplicate publication, dirty trees, hooks, symlinks, credentials, injection, and forge errors.
- [ ] First present a test matrix and expected outcomes, then implement one concern per slice.
- [ ] Imitate the controller integration test harness from P2.7.
- [ ] Do not call live networks, real credential stores, or external repositories.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] No production deletion is expected; show zero-caller evidence if proposing one.
- [ ] Expected diff: under 150 lines per concern.
- [ ] Verify with `python3 -m unittest discover -s tests -p 'test_*.py'` on all three OS jobs.
- [ ] Append one result line per concern to `PROGRESS.md`.
- [ ] Stop if a safety property cannot be tested deterministically; document it as a non-guarantee and add a bounded replay/live eval.

#### Sub-prompt P4.3 — recorded replay layer

- [ ] `[writes code]` Add only `evals/replays/`, replay runner improvements, and replay documentation.
- [ ] First present a short plan, then add the smallest high-value corpus.
- [ ] Imitate `evals/cases/` metadata and `scripts/check-replay-evals.sh` behavior.
- [ ] Cover prompt-to-goal, explicit auto authorization, blocked sandbox, injection, crash-resume, and awaiting-review.
- [ ] Existing deterministic tests must pass unmodified; report failures.
- [ ] Show zero-caller evidence before replacing replay formats.
- [ ] Expected diff: under 150 lines per replay.
- [ ] Verify with `bash scripts/check-replay-evals.sh .`; expected result is actual replay execution, not “no replay cases found; skipped.”
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if a replay contains secrets or private paths; sanitize or discard it.

#### Sub-prompt P4.4 — optional live-model smoke suite

- [ ] `[writes code]` Add only tiny live cases, a runner interface, and docs under `evals/live/` plus `scripts/check-live-evals.sh`.
- [ ] First present a short plan and cost/safety bound, then implement.
- [ ] Imitate the opt-in environment gating already in `check-live-evals.sh`.
- [ ] Test only high-value conversational properties and never publish or use arbitrary repositories.
- [ ] Existing tests must pass unmodified; live tests remain non-required unless a stable runner is configured.
- [ ] Show zero-caller evidence before changing environment flags.
- [ ] Expected diff: under 150 lines per case/runner slice.
- [ ] Verify with a local `PATHFINDER_LIVE_EVALS=1` run against synthetic repositories and confirm normal CI remains offline/deterministic.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if the runner cannot guarantee cost and external-side-effect bounds.

**Phase verification:** deterministic tests are green on three OSes; replay tests actually run; live smoke is bounded and optional; the README-promise coverage matrix has no unexplained gaps.

**Rollback:** remove optional live/replay integration first while retaining deterministic schemas and controller tests. Never delete recorded failure evidence without replacement coverage.

**Decision:** live-model evals remain advisory until repeated runs show an acceptable flake rate and cost.

### Phase 5 — Migrate, package, and release safely

**Goal:** ship the controller-backed behavior with explicit compatibility, migrations, and an immutable stable release.

**Preconditions:** Phases 0-4 green; threat-model review complete; clean worktree; release candidate tested from its packaged artifact.

#### Sub-prompt P5.1 — intent/mission migration command

- [ ] `[writes code]` Add only migration code, migration fixtures, and user-facing migration documentation.
- [ ] First present a migration/rollback plan, then implement.
- [ ] Imitate Phase 1 schema versions and atomic storage from P2.2.
- [ ] Back up old local state, migrate deterministically, validate the result, and never silently resolve clarity or grant authorization.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show zero-caller and fixture evidence before dropping an old schema reader.
- [ ] Expected diff: 100-150 lines per schema generation.
- [ ] Verify with golden migrations from every shipped schema version and a failed-migration rollback test.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop on an unknown schema; preserve files and report manual recovery steps.

#### Sub-prompt P5.2 — stable/edge packaging

- [ ] `[writes code]` Change only plugin/marketplace manifests, release workflow, version docs, and packaging tests.
- [ ] First present a release-channel plan, then edit.
- [ ] Imitate existing manifest identity/version checks.
- [ ] Make stable resolve immutably and label `main` as edge; smoke-install the packaged artifact before tag/release creation.
- [ ] Existing tests must pass unmodified; update expected manifest policy only after new negative fixtures exist.
- [ ] Show all callers before removing the enforced `source.ref: main` rule.
- [ ] Expected diff: 80-150 lines; split packaging test from channel change.
- [ ] Verify with `bash scripts/check-all.sh .`, package smoke tests, and a dry-run release that creates no tag or external release.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if either host cannot consume immutable refs; retain edge-only distribution and document the limitation.

#### Sub-prompt P5.3 — operator and compatibility documentation

- [ ] `[writes code]` Change only README/install/support docs and add one operator guide.
- [ ] First present an information architecture plan, then edit.
- [ ] Imitate the current concise README and keep deep recovery detail in the operator guide.
- [ ] Document capability degradation, supported hosts/OS/forges, authorization, budgets, pause/resume/abandon, cleanup, and guarantee boundaries.
- [ ] Existing tests must pass unmodified; report failures.
- [ ] Show search evidence before deleting legacy instructions.
- [ ] Expected diff: under 150 lines per document.
- [ ] Verify links, manifest prompt consistency, `git diff --check`, and one clean install walkthrough per host.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop if documented behavior lacks a deterministic test, replay, or explicit non-guarantee label.

**Phase verification:** an install from the release candidate can generate a Goal in a synthetic non-Git folder, run one local Git mission to a verified branch, and run one GitHub fixture mission to exactly one awaiting-review PR record; migrations preserve existing intent without granting authority.

**Rollback:** publish a new patch release pointing stable back to the prior immutable artifact; do not rewrite tags. Preserve migration backups and provide a downgrade reader where feasible.

**Decision:** only promote stable after at least one release-candidate dogfood cycle on each supported host.

## What could go wrong

1. **The controller becomes a second, overbuilt product.** Keep v1 to one sequential Goal, local Git, optional GitHub PR, no self-merge, and strict degradation. Defer parallelism, additional forges, and autonomous opportunity generation.
2. **Host lifecycle capabilities differ from assumptions.** The adapter contract must support `unsupported` and manual activation; never fake native Goal state or completion.
3. **Safety metadata creates false confidence.** Unknown sandbox/credential/network enforcement must block unattended execution. A field saying `isolated` is not proof unless the controller created and verified the boundary.

## Where confidence is lowest

- The exact non-interactive plugin test surface available for each current Claude Code and Codex release needs verification during implementation.
- The best secure storage surface for creator approvals varies by host; explicit per-run authorization is the safe fallback.
- GitHub rulesets and enterprise branch policies need fixture-backed API research before any self-merge design is reconsidered.

## What not to do

- [ ] Do not add more prose-only autonomous powers before a controller and state machine exist.
- [ ] Do not retain automatic external-write escalation merely because the intent model is “clear.”
- [ ] Do not let autonomous runs update the policy that authorizes future runs.
- [ ] Do not start with parallel goals, multiple forges, or self-merge.
- [ ] Do not treat generated Markdown, model claims, or brace-shaped text as validated state.
- [ ] Do not run repository-defined commands when isolation is unknown or best-effort.
- [ ] Do not rewrite the entire skill in one diff; move one route at a time with replay coverage.
- [ ] Do not make live-model evals a flaky required gate; keep deterministic contracts required and live evals bounded/advisory.
- [ ] Do not migrate user intent in place without a validated backup and rollback path.

## Recommended first implementation slice

Start with **P0.1 and P0.2 only**. They are confirmed, small, reversible defects that restore trust in the project’s own preflight. Then ratify P1.1 before changing any autonomy semantics or building runtime code.

## Next execution batch — make JSON authority real

Date: 2026-08-11
Repository baseline: `codex/v3-controller` at `08818fe`
Plan size: **Large** — this crosses prompt artifacts, autonomous mission projections, durable creator intent, schemas, migrations, route instructions, and deterministic evals.

### Investigation findings

1. `skills/pathfinder/references/artifact-structure.md` already states the intended rule: controller-owned JSON is authoritative, Markdown is a human-readable view, and Markdown must never be parsed back into mission state.
2. The prompt fast path only partially implements that rule. `pathfinder_core/artifacts.py` builds `06-goal-binding.json` and `08-final-summary.json`, but it first parses the hand-authored `06-goal-command.md` and renders `08-final-summary.md` from request fields rather than from the validated summary document.
3. `tests/core/test_artifacts.py` checks that stable IDs appear in Markdown, but it has no byte-for-byte golden renderer, tampered-view repair test, or proof that changing Markdown cannot change JSON.
4. The host mission controller already has strong canonical JSON inputs: `state.json`, append-only events, sealed contracts, operation intents/results, and typed receipts under the mission state directory.
5. The host mission controller never projects that bundle into `07-run-log.json`, `07-run-log.md`, `08-final-summary.json`, or `08-final-summary.md`, despite the autonomous route promising those views.
6. The existing v1 run-log and final-summary schemas can express the required compatibility summaries. Rich Markdown can be derived from the validated bundle without making one sidecar duplicate every sealed contract or receipt field.
7. Candidate and verification JSON are schema-valid canonical records, while their structured Markdown representations remain model-authored inside `03-synthesis.md` and `03b-verification.md`.
8. The three intent schemas exist, but production intent is still stored only as `.pathfinder/charter.md`, `roadmap.md`, and `doctrine.md`; `pathfinder_core/migrations.py` parses and mutates those Markdown files directly.
9. Existing legacy intent Markdown is intentionally flexible prose. Automatically converting it into security-relevant autonomy JSON would be lossy and could silently invent policy; migration must require creator-confirmed structured input.
10. `evals/harness/eval-lib.sh` parses Markdown for UX and safety assertions. That is acceptable only when testing rendered output; it must not use Markdown to establish canonical state when a JSON document exists.

### Goal restated

Pathfinder is done with this batch when every state-bearing Markdown artifact is deterministically reproducible from validated JSON, no runtime path parses a generated Markdown view back into authority, a crash or manual Markdown edit cannot change canonical state, and existing users receive an explicit safe migration path for local intent.

Observable completion criteria:

- `artifacts goal-saved` accepts structured input and creates `06-goal-command.md` plus `08-final-summary.md`; it does not require or parse a pre-authored Goal Markdown file.
- Rendering the same validated JSON bundle twice produces identical bytes.
- Editing or deleting a generated Markdown view and rerendering restores it without changing any JSON hash.
- A terminal host-driven mission can produce schema-valid `07-run-log.json` and `08-final-summary.json` plus matching Markdown from its persisted mission bundle.
- Structured candidate and verification sections are generated from `03-candidates.json` and `03b-verification.json`, not separately authored facts.
- `.pathfinder/charter.json`, `roadmap.json`, and `doctrine.json` become canonical; their `.md` counterparts are replaceable views.
- Unknown or legacy-only intent never becomes autonomy-eligible through an automatic prose parser.
- A repository search finds no production reader that derives state from `06-goal-command.md`, `07-run-log.md`, `08-final-summary.md`, or `.pathfinder/*.md`.

### Blast radius and reversibility

- Prompt and mission artifacts live in ignored local work areas and contain no live application data. Renderer changes are reversible by reverting the controller commit and regenerating views from preserved JSON.
- Mission state is security-sensitive but already JSON. This batch must not change transition authority, authorization, host action selection, receipt validation, budgets, or publication scope.
- Durable intent affects autonomous goal eligibility. Its cutover is the highest-risk phase because a bad conversion could widen autonomy. Preserve the original Markdown in an explicit backup and default ambiguous conversions to unresolved and goal-only.
- Generated Markdown is expendable. Canonical JSON, event logs, receipts, and migration backups are not; rollback must preserve them.

### Ambiguities and recommended decisions

- **What counts as a view?** Recommendation: `06-goal-command.md`, structured candidate/verification sections, `07-run-log.md`, `08-final-summary.md`, and `.pathfinder/*.md` are generated views. Discovery prose (`00`, `01`, scout briefs, question/answer narrative, and cross-model review narrative) remains evidence, not controller state, until it receives a schema.
- **Does one Markdown file need one JSON twin?** Recommendation: no. A view may render from a validated bundle such as mission state + binding + runtime boundary + receipts. Do not inflate `run-log.schema.json` merely to duplicate already-sealed JSON.
- **Should a view mismatch block state progress?** Recommendation: no. Canonical transitions commit first; a failed view refresh is reported as stale and is safely repairable. It must never roll back or reinterpret mission state.
- **How should prompt Goal compatibility work?** Recommendation: because v3 is still an unreleased draft, remove the input role of `--goal-file`. The controller owns the fixed `06-goal-command.md` path and renders it from the validated binding/request.
- **How should legacy intent migrate?** Recommendation: never infer full policy from prose. Back up legacy Markdown, require creator-confirmed schema-valid JSON produced by the intent interview, then render the new Markdown view. Legacy-only intent remains readable evidence but cannot authorize autonomy.
- **When are views sealed?** Recommendation: seal prompt Goal views immediately; keep active mission views atomically replaceable; seal final mission views only at a terminal state. Canonical JSON contracts retain their existing sealing rules.

### Missing pieces that must be added

- Pure renderers with no filesystem, clock, Git, or host access.
- Golden Markdown fixtures and bundle-level identity validation before rendering.
- An atomic view writer that can replace stale views without treating them as input.
- A mission projection builder from existing state/contracts/journals/receipts.
- A controller command for explicit mission-view refresh and repair.
- Structured generated-block markers for the candidate and verification portions of narrative artifacts.
- Canonical intent JSON storage, safe backup/activation, and Markdown renderers.
- A guard documenting and testing the remaining allowed Markdown reads.
- Crash fixtures for JSON-written/view-missing and view-tampered recovery.

### Scope split

1. **First project:** pure renderers and prompt-to-Goal authority reversal. This is the smallest place where the current implementation contradicts its documented rule.
2. **Second project:** host mission projections and crash-safe view refresh from already-canonical controller state.
3. **Third project:** generated candidate/verification sections and eval assertions that compare views with JSON.
4. **Fourth project:** creator-confirmed canonical intent JSON plus legacy backup and goal-only degradation.
5. **Deferred:** schemas for free-form discovery, question transcripts, and cross-model review narrative; rich UI renderers; HTML output; template customization.

### Phase J0 — lock down the authority boundary

**Goal:** add breakage detection before reversing any writer, so a later refactor cannot silently restore Markdown authority.

**Preconditions:** clean worktree; commit `08818fe`; all 146 tests and `bash scripts/check-all.sh .` green.

#### Sub-prompt J0.1 — authority inventory and characterization tests

- [x] `[read-only]` Inspect only `pathfinder_core/artifacts.py`, `pathfinder_core/migrations.py`, `pathfinder_core/mission_host.py`, `evals/harness/`, `tests/core/test_artifacts.py`, and the three intent templates. Run Codex in a read-only sandbox.
- [x] Confirm every production `read_text`/Markdown parser and classify it as generated-view input, legacy migration input, narrative evidence, or instruction validation.
- [x] Imitate the concise evidence table in `PLAN.md`; do not change code or tests.
- [x] Existing tests must pass unmodified; report a pre-existing failure and stop rather than edit it.
- [x] No deletion is allowed. If a later removal is proposed, record `rg` callers now.
- [x] Expected diff: zero code lines; only append the required finding to `PROGRESS.md`.
- [x] Verify with `rg -n "read_text|06-goal-command.md|07-run-log.md|08-final-summary.md|charter.md|roadmap.md|doctrine.md" pathfinder_core evals tests` and record the exact production readers.
- [x] Append a line to `PROGRESS.md` recording the inventory, verification, and any premise that contradicts this plan.
- [x] Stop if another runtime package or host writes these artifacts outside `pathfinder_core`; revise the ownership map before implementation.

#### Sub-prompt J0.2 — golden authority tests

- [x] `[writes code]` Change only `tests/core/test_artifacts.py` and new fixtures under `tests/core/fixtures/rendering/`; first present a short test plan.
- [x] Characterize the current valid prompt bundle, then add failing expectations for deterministic rerender, view tamper repair, and JSON hashes remaining unchanged after Markdown edits.
- [x] Imitate `tests/core/test_artifacts.py` setup and stable clock/hash fixtures.
- [x] Existing tests must pass unmodified; new tests may fail only for the missing renderer behavior.
- [x] No production deletion is allowed.
- [x] Expected diff: 80-120 test/fixture lines; split prompt and mission goldens if larger.
- [x] Verify with `python3 -m unittest tests.core.test_artifacts`; record which new tests fail before implementation.
- [x] Append a line to `PROGRESS.md` recording the characterization, expected failures, and contradictions.
- [x] Stop if the existing JSON documents cannot fully determine the promised prompt Markdown; identify the smallest missing schema field instead of embedding request-only state in the renderer.

**Phase verification:** the authority inventory is complete and focused tests distinguish JSON mutation from Markdown mutation.

### Phase J1 — reverse prompt-to-Goal authority

**Goal:** make the validated prompt request/binding/summary bundle produce both Markdown views without parsing either view.

**Preconditions:** J0 complete; clean worktree; prompt golden failures captured.

#### Sub-prompt J1.1 — pure prompt renderers

- [x] `[writes code]` Add only `pathfinder_core/rendering.py` and focused renderer tests/fixtures; first present a short function/input/output plan.
- [x] Implement pure deterministic renderers for `06-goal-command.md` from validated Goal Binding and `08-final-summary.md` from validated Goal Binding + Final Summary.
- [x] Imitate `_render_final_summary` formatting in `pathfinder_core/artifacts.py` and schema fixtures under `evals/fixtures/good-goal/`; do not introduce a template engine.
- [x] Escape or normalize untrusted text so values cannot create fake generated headings or generated-block markers; preserve the exact `/goal` objective as one line.
- [x] Existing tests must pass unmodified; report failures.
- [x] Show `rg` evidence of all `_render_final_summary` callers before removing it in a later sub-prompt.
- [x] Expected diff: 100-150 production/test lines; split Goal and summary renderers if larger.
- [x] Verify with `python3 -m unittest tests.core.test_rendering`; expected output is byte-identical golden Markdown on two runs.
- [x] Append a line to `PROGRESS.md` recording renderer coverage and verification.
- [x] Stop if the current schemas cannot determine required output; propose one explicit schema addition and do not read the request or Markdown inside the renderer.

#### Sub-prompt J1.2 — controller-owned prompt writes

- [x] `[writes code]` Change only `pathfinder_core/artifacts.py`, `pathfinder_core/__main__.py`, `tests/core/test_artifacts.py`, and focused CLI tests; first present the compatibility change.
- [x] Construct and schema-validate binding/summary JSON first, render both Markdown files from those documents, and atomically write the complete bundle. Remove the input role of `--goal-file`; the fixed output remains `06-goal-command.md`.
- [x] Imitate `_write_idempotent`, path/symlink guards, and sealing behavior already in `pathfinder_core/artifacts.py`.
- [x] A different Markdown view must be repaired from JSON, not accepted as authority and not used to alter JSON.
- [x] Existing tests must pass unmodified except tests explicitly characterizing the unreleased `--goal-file` input; replace those only after showing all CLI/route callers with `rg`.
- [x] Expected diff: 100-150 lines; split atomic bundle writing into a follow-up if larger.
- [x] Verify with `python3 -m unittest tests.core.test_artifacts tests.core.test_rendering` and a CLI run where a tampered view is restored.
- [x] Append a line to `PROGRESS.md` recording the authority reversal and verification.
- [x] Stop if canonical JSON would be written while another canonical document is invalid; validate the complete in-memory bundle before the first filesystem write.

#### Sub-prompt J1.3 — prompt route and replay cutover

- [x] `[writes code]` Change only `skills/pathfinder/SKILL.md`, `skills/pathfinder/references/artifact-structure.md`, `skills/pathfinder/references/routes/prompt-to-goal.md`, `evals/replays/cases/prompt-fast-path.md`, its replay fixture, and matching consistency guards; first present a route-diff plan.
- [x] Instruct hosts to create only the structured request, then let the controller generate and seal `06-goal-command.md`, both JSON sidecars, and `08-final-summary.md`.
- [x] Imitate the existing absolute-plugin-root and final-filesystem-write gate; keep static-inspection-only behavior and exact ignore checks unchanged.
- [x] Existing tests must pass unmodified in safety meaning; update replay expectations rather than weakening them.
- [x] Show zero-caller evidence for the old pre-authored `--goal-file` form before deleting it.
- [x] Expected diff: 80-140 lines across route/docs/replay; split mirror updates if larger.
- [x] Verify with `bash scripts/check-skill-consistency.sh .`, `bash scripts/check-replay-evals.sh .`, and `python3 -m unittest tests.core.test_artifacts`.
- [x] Append a line to `PROGRESS.md` recording the route cutover and verification.
- [x] Stop if any supported host requires the Goal file before the controller can run; retain a conversation-only preview, never a filesystem input presented as canonical.

Implementation note: the prompt replay's six output paths and safety semantics were already correct, so its fixture required no mutation. The final-summary route mirror was updated with the same generated-view rule, and a consistency guard now fails if the removed Goal-file input returns.

**Phase verification:** `rg` finds no production read of `06-goal-command.md`; prompt JSON hashes remain stable after view tampering; full preflight passes.

**Rollback:** revert the route and writer together. Preserve request/binding/summary JSON and regenerate the prior view; never restore Markdown-to-state parsing as a partial rollback.

### Phase J2 — render host mission views from the persisted bundle

**Goal:** produce honest run-log and final-summary projections without changing mission transitions or side-effect authority.

**Preconditions:** J1 green; host mission crash matrix green; a clean state bundle reaches `awaiting-review`, `blocked`, and `abandoned` in fixtures.

#### Sub-prompt J2.1 — mission projection builder

- [x] `[writes code]` Add only `pathfinder_core/projections.py` and `tests/core/test_projections.py`; first present a field-mapping table from canonical source to projection field.
- [x] Read and validate existing `state.json`, binding, runtime boundary, operation intents/results, and typed receipts; construct schema-v1 run-log/final-summary documents without reading Markdown.
- [x] Imitate `OperationJournal.load`, `MissionStore.load`, and `evals/harness/validate-bundle.py` identity checks.
- [x] Use only redacted receipt fields; do not expose argv, output, environment, credentials, or raw repository content.
- [x] Existing tests must pass unmodified; report failures.
- [x] No deletion is expected; show callers before replacing any bundle loader.
- [x] Expected diff: 100-150 lines per projection; split run-log and final-summary builders if larger.
- [x] Verify with `python3 -m unittest tests.core.test_projections` for authorized, verifying, awaiting-review, blocked, abandoned, and reconcile-required bundles.
- [x] Append a line to `PROGRESS.md` recording mappings, verification, and any schema insufficiency.
- [x] Stop if schema v1 cannot represent an honest required status; add a versioned schema/migration plan rather than overloading an enum or prose field.

#### Sub-prompt J2.2 — atomic mission view writer and CLI

- [x] `[writes code]` Change only `pathfinder_core/rendering.py`, one new view-writer module if needed, `pathfinder_core/__main__.py`, and focused tests; first present the write/crash model.
- [x] Add `artifacts mission-view --repo-root --state-dir --output-dir --json` that validates the ignored output path, loads canonical mission state, writes JSON projections atomically, then writes Markdown views derived from those in-memory documents.
- [x] Imitate `_validated_output_dir`, `write_atomic`, and the prompt renderer; do not couple canonical state transitions to view writes.
- [x] Active views remain replaceable; terminal views may be sealed after every document is present and validated.
- [x] Existing tests must pass unmodified; report failures.
- [x] Show zero-caller evidence before sharing or moving `_validated_output_dir`.
- [x] Expected diff: 100-150 lines; split CLI wiring from crash tests if larger.
- [x] Verify with focused tests for missing view, tampered view, crash after JSON projection, repeated refresh, symlink path, and unignored output.
- [x] Append a line to `PROGRESS.md` recording view repair and verification.
- [x] Stop if a view failure mutates or rolls back mission state; views must remain downstream projections only.

#### Sub-prompt J2.3 — autonomous route and crash replay

- [x] `[writes code]` Change only the autonomous/final-summary route modules, artifact contract, one recorded replay, and matching eval assertions; first present the exact controller call points.
- [x] Require a mission-view refresh after each surfaced checkpoint and before final reporting, while stating that JSON state remains authoritative if rendering is interrupted.
- [x] Imitate the current `mission next/record/resume` sequence and fail-closed reconciliation language.
- [x] Existing safety tests must pass unmodified; report failures.
- [x] Show callers before replacing any direct `07-run-log.md` or `08-final-summary.md` writing instruction.
- [x] Expected diff: 80-140 lines; split route mirrors if larger.
- [x] Verify with `bash scripts/check-replay-evals.sh .`, the host bridge crash matrix, and a replay where canonical state exists but Markdown is missing and is repaired once.
- [x] Append a line to `PROGRESS.md` recording route enforcement and verification.
- [x] Stop if refresh requires credentials, repository code execution, or a state transition; it must be a local read/projection operation only.

Implementation note: the v1 final-summary schema has no active or reconcile-required disposition, so active checkpoints intentionally project only replaceable run-log views. Terminal states project and seal all four views. The operation journal stores typed host actions but no argv/environment evidence; `commands` therefore remains empty, while Markdown renders only schema-validated redacted receipt fields.

**Phase verification:** a complete host mission produces schema-valid JSON views and matching Markdown; all crash boundaries retain one canonical transition history and repairable views.

**Rollback:** disable the mission-view route call and retain canonical state. Generated views may be deleted and regenerated; never delete the mission directory or event log.

### Phase J3 — generate structured exploration views

**Goal:** eliminate independently authored candidate and verification facts while preserving narrative discovery prose.

**Preconditions:** J2 green; candidate and verification schemas remain v1; golden rich fixtures selected.

#### Sub-prompt J3.1 — generated candidate/verification blocks

- [x] `[writes code]` Change only `pathfinder_core/rendering.py`, focused rendering tests, and golden fixtures; first present generated-block markers and escaping rules.
- [x] Render the candidate section of `03-synthesis.md` from `03-candidates.json` and the structured result section of `03b-verification.md` from `03b-verification.json` between versioned generated markers.
- [x] Imitate candidate cards in `skills/pathfinder/references/routes/candidate-selection.md` and current verification fixture vocabulary.
- [x] Preserve narrative text outside generated markers byte-for-byte; reject malformed, nested, or duplicate marker regions.
- [x] Existing tests must pass unmodified; report failures.
- [x] Show all candidate/verification Markdown consumers before replacing their authored fields.
- [x] Expected diff: 100-150 lines per renderer; split candidates and verification if larger.
- [x] Verify with golden rendering, special-character escaping, duplicate-marker rejection, and rerender idempotency tests.
- [x] Append a line to `PROGRESS.md` recording generated sections and verification.
- [x] Stop if a displayed field is not present in schema JSON; either label it explicitly narrative/noncanonical or propose a versioned schema field.

#### Sub-prompt J3.2 — eval authority cleanup

- [x] `[writes code]` Change only `evals/harness/eval-lib.sh`, `evals/harness/validate-bundle.py`, relevant eval fixtures/cases, and contract tests; first map each assertion to its canonical JSON input and rendered-output check.
- [x] Use JSON for candidate identity, grades, binding status, verification, and final state. Parse Markdown only to test renderer/UX output, never to establish those facts.
- [x] Imitate the duplicate-safe JSON validator and existing cross-artifact bundle checks.
- [x] Existing bad fixtures must still fail for their named reason; report any reason drift rather than weakening a case.
- [x] Show zero-caller evidence before removing assertion aliases.
- [x] Expected diff: under 150 lines per assertion family.
- [x] Verify with `bash scripts/check-evals.sh .` and `python3 -m unittest tests.contracts.test_artifact_validator`.
- [x] Append a line to `PROGRESS.md` recording which Markdown authority reads were removed.
- [x] Stop if a case has no canonical JSON evidence; add a schema-backed fixture or keep the case explicitly UX-only.

**Phase verification:** changing candidate/verification JSON changes generated Markdown; editing the generated block is repaired; narrative content remains unchanged.

### Phase J4 — cut durable intent over to canonical JSON

**Goal:** make creator intent schema-valid and machine-readable without silently converting prose into autonomy policy.

**Preconditions:** J1-J3 green; creator-model route has a safe goal-only degradation; migration backups are tested.

#### Sub-prompt J4.1 — intent JSON store and pure renderers

- [x] `[writes code]` Add only an intent storage module, intent renderers, and focused tests; first present a file/lock/atomicity plan.
- [x] Validate `charter.json`, `roadmap.json`, and `doctrine.json` against existing schemas before writing; render corresponding `.md` views deterministically.
- [x] Imitate `MissionStore` duplicate-safe JSON loading and atomic writes, plus current charter/roadmap/doctrine template headings.
- [x] Never derive authorization, clarity, safety, or hard stops from the Markdown view.
- [x] Existing tests must pass unmodified; report failures.
- [x] No deletion is allowed in this slice.
- [x] Expected diff: 100-150 lines per intent kind; split common storage from renderers if larger.
- [x] Verify with round-trip-independent tests: JSON -> Markdown, tamper Markdown, rerender, unchanged JSON hash.
- [x] Append a line to `PROGRESS.md` recording intent authority behavior and verification.
- [x] Stop if the three schemas need semantic changes; version and migrate one schema at a time rather than accepting extra properties.

#### Sub-prompt J4.2 — creator-confirmed activation and legacy backup

- [x] `[writes code]` Change only `pathfinder_core/migrations.py`, `pathfinder_core/__main__.py`, `tests/core/test_migrations.py`, and golden migration fixtures; first present rollback and partial-failure behavior.
- [x] Add a command that backs up legacy `.md`, accepts creator-confirmed schema-valid JSON from the intent interview, writes canonical JSON atomically, renders views, and reports that no authorization was granted.
- [x] Imitate the current backup-before-write and rollback-on-exception behavior.
- [x] Unknown, incomplete, or legacy-only intent remains `intent_clarity: unresolved` for autonomy and is never automatically parsed into policy.
- [x] Existing migration tests must pass unmodified; report failures.
- [x] Show all `_migrate_intent_text` callers before deprecating it; do not delete the legacy reader until one full release can consume backups.
- [x] Expected diff: 100-150 lines; split activation from deprecation if larger.
- [x] Verify with legacy backup, creator-confirmed activation, invalid JSON, unknown schema, crash rollback, CRLF, symlink, and view-repair tests.
- [x] Append a line to `PROGRESS.md` recording migration safety and verification.
- [x] Stop if the input lacks explicit creator confirmation or all three policy-bearing documents required for autonomy; preserve legacy files and remain goal-only.

#### Sub-prompt J4.3 — skill, templates, and intent eval cutover

- [x] `[writes code]` Change only the intent-refresh/autonomous route modules, `SKILL.md`, the three intent templates, artifact structure, relevant eval fixtures, and consistency guards; first present the mirror/caller list.
- [x] Make route behavior write canonical JSON through the controller and treat `.md` only as a human view. Require JSON schema validation and creator confirmation before intent becomes resolved.
- [x] Imitate existing ignore-ladder, tracked-file distrust, doctrine proof, and explicit authorization boundaries exactly.
- [x] Existing behavior tests must pass unmodified in meaning; add JSON fixtures instead of relaxing migration assertions.
- [x] Show zero-caller evidence before removing Markdown marker reads from runtime instructions.
- [x] Expected diff: under 150 lines per intent kind/route; split charter, roadmap, doctrine, and autonomous references if larger.
- [x] Verify with `bash scripts/check-skill-consistency.sh .`, `bash scripts/check-skill-behavior.sh .`, `bash scripts/check-evals.sh .`, and focused migration tests.
- [x] Append a line to `PROGRESS.md` recording the route cutover and verification.
- [x] Stop if a supported manual skill-only install cannot invoke the controller; degrade that install to conversation-only draft intent rather than writing authoritative Markdown.

**Phase verification:** only `.pathfinder/*.json` influences machine intent, rendered Markdown is replaceable, legacy-only state cannot authorize autonomy, and migration backups restore the exact original bytes.

**Rollback:** restore the backed-up legacy Markdown and disable intent-based autonomy. Preserve new JSON for manual recovery; do not synthesize a downgrade from generated Markdown.

### Phase J5 — enforce, document, package, and dogfood

**Goal:** make the authority rule mechanically visible and prove it from the exact shipped archive.

**Preconditions:** J1-J4 green; no canonical schema or route drift; clean worktree.

#### Sub-prompt J5.1 — authority guard and operator docs

- [x] `[writes code]` Change only one new validation script, `scripts/check-all.sh`, `CONTRIBUTING.md`, operator/artifact docs, and focused validator meta-tests; first present the allowlist of legitimate Markdown readers.
- [x] Fail when production code introduces a new state-bearing Markdown parser outside explicitly documented legacy migration/renderer tests.
- [x] Imitate `scripts/check-portability.sh` plus its adversarial parser fixtures; keep the guard structural and narrow, not a broad ban on `read_text`.
- [x] Existing tests must pass unmodified; report failures.
- [x] No deletion is expected.
- [x] Expected diff: 80-140 lines.
- [x] Verify with a seeded forbidden-reader fixture, a renderer read allowed only for view replacement, ShellCheck, and full preflight.
- [x] Append a line to `PROGRESS.md` recording enforcement and verification.
- [x] Stop if the guard false-flags instruction validation or golden output tests; narrow by production module/path and exact artifact classes.

#### Sub-prompt J5.2 — exact archive and host dogfood

- [x] `[writes code]` Change only replay fixtures and documentation if dogfood exposes a real contradiction; first run without editing.
- [x] Exercise prompt Goal generation, view tamper repair, mission-view refresh after a seeded crash, and legacy intent goal-only degradation from an isolated packaged install.
- [x] Imitate `scripts/package-smoke.sh` and existing sanitized replay format; never use a live repository, credentials, publication, or merge.
- [x] Existing tests must pass unmodified; report failures.
- [x] Show zero-caller evidence before removing any compatibility route exposed by dogfood.
- [x] Expected diff: zero unless a focused replay/doc correction is required; any correction stays under 150 lines.
- [x] Verify with `bash scripts/check-all.sh .`, `bash scripts/package-smoke.sh . "" git`, hosted Linux/macOS/Windows preflight, CodeQL, and Dependency Review.
- [x] Append a line to `PROGRESS.md` recording exact commit, package result, host results, and non-guarantees.
- [x] Stop if dogfood changes canonical JSON after Markdown tampering or requires parsing a view; return to the owning phase.

**Phase verification:** full local and hosted checks pass, the exact archive repairs views from JSON, and the checklist item “Make JSON the source of truth and render Markdown views from it” can be checked without qualification.

### What could go wrong

1. **The renderer becomes a second state model.** Prevent this by accepting only validated JSON documents, keeping renderers pure, and refusing request-only or Markdown-derived fallback fields.
2. **A view-writing crash is mistaken for mission failure.** Canonical state must commit independently; rerender repairs the view and never replays a host action or transition.
3. **Legacy intent conversion silently widens autonomy.** Never parse flexible prose into policy. Require creator-confirmed JSON, preserve exact backups, and default unresolved/legacy-only state to goal-only.

### Where confidence is lowest

- The current intent schemas may not capture every nuance users have placed in flexible Markdown; creator-confirmed regeneration is safer than claiming lossless automatic migration.
- Candidate data may not contain every field required by the current rich candidate cards. Missing display-only fields should remain labeled narrative until a deliberately versioned schema addition.
- Manual skill-only installations without the controller cannot honestly maintain canonical JSON + rendered views. The safest degradation is conversation-only output, but host UX needs dogfood.

### What not to do

- [ ] Do not add a general template engine or user-editable rendering templates.
- [ ] Do not make Markdown mismatch block or rewrite canonical mission state.
- [ ] Do not expand mission transitions, publication, budgets, or host authority in this batch.
- [ ] Do not duplicate every receipt and contract field into `run-log.schema.json` merely for rendering convenience.
- [ ] Do not auto-parse legacy intent prose into autonomy policy.
- [ ] Do not schema-encode all free-form discovery narrative in the same migration.
- [ ] Do not check the master checklist item after prompt rendering alone; mission and intent authority must also be real.

### Recommended first implementation slice

Execute **J0.2, J1.1, and J1.2 only** after this plan. They close the existing prompt-path authority inversion with no mission-state schema migration and create the renderer primitive the later phases reuse.

## Next execution batch — design conditional self-merge without enabling it

Date: 2026-08-11

Repository baseline: `codex/v3-controller` at `66f1893`

Plan size: **Large** — a merge is an irreversible remote write whose safety depends on trusted authorization, GitHub identity and permission evidence, layered branch rules, review state, check provenance, race handling, and crash reconciliation.

> Design status only. Nothing in this section authorizes implementation, publication, or merge. The shipped publisher must continue to expose no merge operation until the separately reviewed phases below reach their explicit enablement gate.

### Investigation findings

1. `pathfinder_core/adapters/github.py` is deliberately an awaiting-review publisher. Its protocol has push, exact PR lookup/creation, and bounded check polling, but no merge method.
2. `tests/adapters/test_github.py` records branch-protection, unprotected-branch, active-ruleset, and merge-conflict observations while asserting zero merge attempts. This is a useful negative baseline, not an eligibility implementation.
3. The enabled host bridge is local-only. `pathfinder_core/mission_host.py`, the operator guide, autonomous route, compatibility matrix, and threat model all stop at a verified local `awaiting-review` branch with no push, PR, or merge action. Conditional merge therefore depends on a separately approved runnable publication boundary; it cannot be slipped into the local action sequence.
4. The mission and final-summary schemas can represent `merged` for observation after a human action. That enum does not grant a transition path or merge authority.
5. The authorization snapshot allows only `none`, `local-branch`, or `github-awaiting-review`. Ordinary autonomy, a Goal Binding, repository prose, or the existing publication target cannot authorize merge.
6. The protected-surface registry is additive and fail-closed for undeclared changed files, but declared protected work can still execute. Initial conditional merge needs a stricter rule: any protected category blocks automatic merge even when it was declared for implementation.
7. GitHub states that rulesets layer with classic branch protection and with one another; all matching rules aggregate and the most restrictive version wins. By contrast, only one classic branch-protection rule applies to a branch. See [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) and [Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).
8. GitHub's `GET /repos/{owner}/{repo}/rules/branches/{branch}` endpoint returns every active repository- and organization-level ruleset rule that applies to an exact branch, excluding disabled and evaluate-only rules. This aggregate endpoint should be authoritative for applicability; complete source rulesets are still needed for bypass visibility. See [REST API endpoints for rules](https://docs.github.com/en/rest/repos/rules).
9. Classic branch protection exposes required checks, administrator enforcement, review counts, stale-review dismissal, code-owner review, last-push approval, PR bypass allowances, linear history, and conversation resolution. Reading it requires repository Administration read permission. See [REST API endpoints for protected branches](https://docs.github.com/en/rest/branches/branch-protection).
10. Rulesets may name users, teams, repository roles, organization administrators, deploy keys, or integrations as `always`, `pull_request`, or `exempt` bypass actors. GitHub may omit `bypass_actors` unless the caller has write access to the ruleset. Missing bypass visibility is therefore `unknown`, never proof that the merge credential cannot bypass. Team membership requires the exact team-membership endpoint; organization-admin membership requires active organization membership with the admin role; repository-role membership requires the ruleset role id/name and the exact repository-permission `role_name`. Organization-admin and deploy-key actors are idless/null in GitHub's contract and must not be normalized to fabricated numeric ids.
11. Required check evidence is more subtle than one combined green status. Checks and commit statuses with the same required name must both pass; required checks apply to the latest head or GitHub's test merge commit, and a requirement may pin the expected GitHub App. See [Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
12. GitHub exposes PR mergeability, review decision, merge-state status, merge queue, latest reviews, and review-thread resolution through GraphQL. A complete observer must paginate reviews and threads rather than trust a truncated first page. See [GraphQL pull request objects](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/pulls).
13. A ruleset can require a merge queue. That is a different asynchronous protocol whose checks run against merge groups; a direct merge implementation must stop and hand off when any applicable rule requires the queue.
14. The synchronous merge endpoint accepts `sha`, which makes a changed PR head fail with `409`. It does not bind the base SHA, applicable ruleset versions, review set, or check snapshot atomically. See [Merge a pull request](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request).
15. GitHub now also exposes asynchronous and stacked-PR merge endpoints. They add delayed execution and may merge multiple PRs. They are explicitly outside the first conditional-merge design.
16. A lost merge response cannot be retried blindly. The executor must first reconcile the exact PR's merged state, merge commit, head/base identity, and merging actor; rollback is a new revert change with separate authority, not an automatic undo.

### Goal restated

Pathfinder may eventually perform the final merge action only after an independent human has approved a low-risk controller-created PR and a separate trusted policy plus fresh GitHub evidence proves that every hard floor and every applicable repository rule is satisfied.

Observable completion means:

- A normal `/pathfinder auto` or `/goal` run still ends at `awaiting-review` and has no merge credential.
- Conditional merge requires both a host-owned repository policy and a fresh explicit run authorization that names merge authority; neither is sufficient alone.
- A merge intent is bound to immutable repository, policy, mission, PR, base, head, actor, and method identities before the remote call.
- The observer positively reads classic branch protection, all active layered rules, source rulesets, bypass actors, reviews, threads, checks, deployments, and PR state; missing, truncated, stale, unsupported, or contradictory evidence blocks.
- The merge credential is proven unable to bypass review or ruleset requirements.
- At least one independent human approval and one required, provenance-pinned successful check are GitHub-enforced hard floors that repository policy cannot weaken.
- Any protected surface, fork PR, draft, stale branch, unresolved thread, requested change, unknown rule type, merge queue, hidden bypass actor, or ambiguous identity remains `awaiting-review` or becomes `blocked`.
- The only first-release remote mutation is one synchronous merge request for one exact PR head SHA. There is no auto-merge, asynchronous merge, stacked merge, queue enrollment, branch deletion, comment, release, deployment, or automatic revert.
- A response-loss replay either proves that the exact intended merge already occurred or returns `reconcile-required`; it never sends a second blind merge request.

### Non-goals

- Fully autonomous approval: the implementation agent, PR author, last pusher, merge app, and check app cannot satisfy the independent-human-review floor.
- Turning repository-controlled files into authority. A checked-in policy file may document intent but cannot enable merge.
- Self-merge for Goal packs, parallel missions, fork PRs, stacked PRs, protected-surface changes, releases, deployments, migrations, or destructive data operations.
- Implementing GitHub merge queues, auto-merge, asynchronous merge, or another forge in the first release.
- Claiming that a client-side snapshot is atomically bound to GitHub's control plane. Concurrent repository-admin policy mutation remains an explicit residual risk.
- Automatically reverting a completed merge. Recovery is a separately authorized forward change.

### Recommended locked decisions

- [x] **M-01 — Two keys:** require a host-owned repository policy and a fresh current-run merge authorization. Persistent policy alone never activates a run; ordinary autonomy authority never implies merge.
- [x] **M-02 — Trusted storage:** store policy and authorization outside the repository trust boundary. Bind both to immutable GitHub repository id/node id, owner/name, base branch, and policy hash.
- [x] **M-03 — Explicit invocation:** require the user or trusted approval store to opt into merge for this run. Bare `/pathfinder auto`, `/goal`, `run all`, resolved intent, or a previous approval remains awaiting-review-only.
- [x] **M-04 — One PR:** first release allows one Goal, one PR, and at most one merge intent. Goal packs and dependent/stacked PRs are ineligible.
- [x] **M-05 — Human floor:** require at least one current effective approval from an eligible human who is not the PR author, implementation agent, last pusher, merge credential actor, or check credential actor. Repository policy may require more, never fewer.
- [x] **M-06 — Check floor:** require at least one GitHub-enforced status check pinned by context and expected app id, plus success for every other applicable required check/status on the exact GitHub-required commit. Policy may add checks, never remove them.
- [x] **M-07 — No bypass:** require complete classic PR-bypass and ruleset-bypass evidence and prove the exact merge actor matches none of it. Membership-based actors require exact-coverage typed team/repository-role/organization-admin facts bound to source-projected actor metadata, the merge bot, one qualified exact-endpoint request audit, and the policy source; missing, shared, duplicate, pending, extra, or identity-drifted facts block.
- [x] **M-08 — Layer all controls:** combine the one applicable classic protection response with the aggregate active ruleset response. Fetch every source ruleset, including organization parents, to validate enforcement, version, conditions, and bypass actors.
- [x] **M-09 — Supported-rule allowlist:** recognize only explicitly implemented rule types and parameters. An unknown type, new enum, omitted field, incomplete page, evaluate/disabled contradiction, or unsupported requirement blocks rather than being ignored.
- [x] **M-10 — Low-risk changes only:** any baseline or additive protected-surface match blocks conditional merge even if declared. Policy must also define allowed path patterns and strict file/line/size ceilings; it may only narrow the shipped baseline.
- [x] **M-11 — Same repository:** require the PR head and base repositories to share the exact immutable repository identity. Forks, deleted refs, retargeted bases, and maintainer-edit ambiguity block.
- [x] **M-12 — Fresh and current:** require an open non-draft PR, exact expected head and base SHAs, a clean/up-to-date merge state, no unresolved review thread, no active change request, and a short-lived evidence snapshot. Do not auto-update or rebase after human approval.
- [x] **M-13 — Merge method:** support synchronous `squash` first, only when repository settings and every applicable rule allow it. Block rebase, direct merge commits, signed-commit requirements, and method ambiguity until each has dedicated reconciliation fixtures.
- [x] **M-14 — Queue handoff:** any merge-queue rule or existing queue entry blocks the direct executor and reports a human/queue handoff. Do not enqueue automatically.
- [x] **M-15 — External effects:** the trusted policy must explicitly acknowledge that merging triggers notifications and may trigger repository workflows. A Goal that itself performs release/deploy/data side effects remains ineligible regardless of that acknowledgement.
- [x] **M-16 — Three credential boundaries:** implementation has no forge credential; a GET-only evidence process holds the minimum elevated visibility needed to inspect policy/bypass data; a separate merge process holds only the identity and write permissions needed for the exact merge endpoint. No token is reused across implementation and merge.
- [x] **M-17 — Immediate execution only:** do not use GitHub auto-merge, async merge, or stacked merge. Their delayed/multi-PR behavior breaks the last-moment evidence binding and the one-PR budget.
- [x] **M-18 — Journal before mutation:** persist a closed merge intent before the request. On ambiguity, reconcile via read-only endpoints; never infer success from an exception, timeout, or PR closure alone.
- [x] **M-19 — Default off:** ship observation and eligibility before mutation. The merge executor remains unreachable by normal route and CLI paths until a separate security review and explicit enablement commit.
- [x] **M-20 — No automatic rollback:** a successful merge is terminal. A revert requires a new Goal, new authority, new PR, and normal review; the controller must never push directly to the base branch.

### Authority and evidence contract

| Layer | Trusted input or positive evidence | Failure behavior |
|---|---|---|
| Repository identity | GitHub numeric id/node id, owner/name, visibility, default branch, archived/disabled state | Any mismatch, rename ambiguity, archive, or disabled repository blocks |
| Repository policy | Host-owned, admin-authored, versioned, hash-bound, unexpired, explicitly enabled for one repository/base | Missing, repo-local-only, expired, widened, or hash drift blocks |
| Run authorization | Fresh trusted user/host approval naming merge authority, one mission, one policy hash, one merge budget | Bare autonomy, inherited approval, pack authority, or expired authority blocks |
| Goal and diff | Exact mission/binding/authorization ids, controller-created same-repo branch, changed-file list, diff hash, zero protected matches | Undeclared file, protected category, symlink/submodule/binary ambiguity, or limit excess blocks |
| PR identity | Exact PR node id/number, open state, non-draft, author, head/base repo ids, refs, SHAs, merge method | Retarget, force-push, fork, deleted ref, draft, closed, or identity drift blocks |
| Classic protection | Full protection response or explicit absence, including review/check/bypass/admin/conversation/linear settings | Missing permission, partial response, or unsupported setting blocks |
| Rulesets | Fully paginated aggregate active rules plus every source ruleset including parents, enforcement and bypass visibility | Hidden actor, page truncation, source mismatch, unknown rule, queue, or unsupported rule blocks |
| Reviews | GitHub review decision plus fully paginated effective reviews and threads bound to the current diff/head | No independent human approval, changes requested, stale approval, unresolved thread, or unknown eligibility blocks |
| Checks | Required contexts and app ids from classic/rulesets plus check-runs and commit statuses on the required SHA/test merge commit | Missing, pending, duplicate-source ambiguity, unexpected app, stale SHA, or non-success blocks |
| Merge actor | Exact user/app/installation identity and scoped permission inventory, compared with all bypass actors plus exact-coverage typed team/repository-role/organization-admin resolutions | Actor identity drift, incomplete/duplicate/pending membership, admin/role ambiguity, or any positive bypass match blocks |
| Freshness | API version, observed timestamps, response/request ids, ETags where available, base/head reread immediately before intent | Snapshot expiry, control-plane drift, or inconsistent reread blocks |
| Merge result | Synchronous response or later exact observation of merged PR, method-compatible merge commit, actor, head/base, and timestamp | Lost or contradictory evidence returns `reconcile-required`; no retry or fabricated `merged` state |

### Fail-closed acceptance matrix

K3 closes all 17 observer/evaluator and inert-composition cases below with direct executable
evidence. K4 closes the two writer cases with the unreachable executor and deterministic crash
fixtures; no normal route can call it.

- [x] Protected branch with classic checks/reviews, an active additive ruleset, complete non-bypass actor evidence, independent approval, and exact green checks can produce `eligible`; the observer still performs zero merge calls. (`test_complete_layered_fixture_is_deterministically_eligible`, `test_backend_protocol_exposes_read_methods_only`)
- [x] Classic protection absent and no active rulesets returns `policy-unenforced`, even when the host-owned policy says enabled. (`test_policy_layers_take_the_most_restrictive_review_floor`)
- [x] Classic protection present but required review count is zero returns `independent-review-not-enforced`. (`test_policy_layers_take_the_most_restrictive_review_floor`)
- [x] Active rulesets present but a source ruleset cannot be positively attributed returns `ruleset-evidence-incomplete`; source/parent permission, transport, or timeout failure retains its more specific typed outcome and yields no partial evidence. (`test_unattributed_ruleset_and_ambiguous_actor_stop_without_evidence`, `test_source_ruleset_read_failures_never_yield_partial_evidence`)
- [x] The aggregate branch-rules endpoint and fetched source ruleset disagree on ids, enforcement, or rule parameters returns `ruleset-drift`. (`test_ruleset_source_parameters_and_bypass_evidence_fail_closed`)
- [x] Missing ruleset/classic bypass visibility, an unknown bypass mode, or unresolved actor-role membership returns `bypass-visibility-unknown`; an omitted required bypass mode returns `malformed-response`, and an unprovable actor identity returns `actor-identity-unknown`. (`test_missing_bypass_visibility_is_a_typed_unknown`, `test_rule_parameter_cross_checks_fail_closed`, `test_actor_bypass_matrix_distinguishes_exact_matches_from_ambiguity`, `test_unattributed_ruleset_and_ambiguous_actor_stop_without_evidence`)
- [x] An exact named user/App/integration bypass match in any recorded mode or any administration permission returns `merge-actor-can-bypass`. (`test_actor_bypass_matrix_distinguishes_exact_matches_from_ambiguity`, `test_fixture_driven_candidate_matrix_returns_exact_codes`, `merge-evidence-contract` eval)
- [x] Positively resolved team, repository-role, or organization-admin membership returns `merge-actor-can-bypass`; exact no-match evidence remains eligible, while missing source metadata, missing/shared/unqualified endpoint audits, duplicate, pending, extra, identity-drifted, reread-drifted, or fabricated summary assertions return `bypass-visibility-unknown` or a stronger typed identity failure. (`test_typed_bypass_memberships_resolve_each_supported_actor_class`, `test_membership_resolution_coverage_and_state_fail_closed`, `test_each_membership_requires_its_own_qualified_request_audit`, `test_typed_membership_matches_block_each_supported_bypass_class`, `test_membership_no_match_and_fabricated_assessment_are_recomputed`, `merge-evidence-contract` eval)
- [x] A new/unknown active GitHub rule type or enum returns `unsupported-active-rule` or a stronger `field-unknown` when the payload itself is outside the closed projection. (`test_bypass_actor_match_and_unsupported_rule_are_explicit`, `test_malformed_and_future_fields_never_look_complete`, `test_unsupported_rule_types_are_typed_and_never_generic_success`)
- [x] A `merge_queue` rule or queue entry returns `merge-queue-required`; no enqueue or merge call occurs. (`test_unsupported_rule_types_are_typed_and_never_generic_success`, `test_fixture_driven_candidate_matrix_returns_exact_codes`, `test_evaluator_has_zero_network_mutation_credentials_or_production_callers`)
- [x] Required deployments, signed commits, code-scanning/quality gates, or another initially unsupported rule returns its typed unsupported reason rather than a generic success. (`test_unsupported_rule_types_are_typed_and_never_generic_success`, `test_classic_protection_semantics_are_explicit_and_fail_closed`)
- [x] A required check with the correct name but wrong App id, stale SHA, pending/duplicate/conflicting sources, failed conclusion, missing enforcement, or incomplete timestamps returns its exact typed check denial rather than generic success. (`test_required_check_matrix_proves_app_sha_status_and_conclusion`)
- [x] Review approval from the author, implementation agent, last pusher, merge actor, bot, dismissed reviewer, stale commit, check creator, or ineligible association does not count. (`test_latest_effective_independent_human_review_only`)
- [x] A current `CHANGES_REQUESTED`, `REVIEW_REQUIRED`, requested code-owner review, or unresolved non-outdated thread blocks. (`test_review_changes_code_owner_and_threads_are_independent_blocks`, `test_fixture_driven_candidate_matrix_returns_exact_codes`)
- [x] Any protected path, workflow, CODEOWNERS/policy surface, schema/migration, dependency-policy exception surface, submodule, symlink, binary, or diff-limit excess blocks. (`test_protected_and_special_surface_matrix_is_independently_derived`, `test_diff_hash_paths_protected_surfaces_and_effective_limits`, `test_authenticated_git_object_evidence_drives_special_file_blocking`)
- [x] Base advancement, head force-push, PR retarget, changed diff hash, policy expiry, ruleset update, review dismissal, or evidence timeout between observation and intent blocks. (`test_reread_drift_matrix_forces_a_new_complete_snapshot_cycle`, `test_authority_and_evidence_windows_are_independently_current`, `test_complete_disjoint_reread_is_required_and_stays_pure`)
- [x] A `409` head mismatch, `405` unmergeable/already-merged response, auth/rate/permission failure, timeout, malformed response, or response loss never becomes success without the exact allowed proof. (`test_definitive_http_failures_are_typed_and_never_retried`, `test_405_uses_exact_state_to_distinguish_already_merged`, `test_malformed_or_server_response_never_becomes_success`)
- [x] A lost response followed by exact merged-state proof records one merged result; any other state is `reconcile-required` and sends no second PUT. (`test_response_loss_can_merge_only_with_exact_reconciliation_proof`, `test_pending_intent_is_not_replayed_and_explicit_reconcile_sends_no_put`, crash-boundary regressions in `test_merge_executor.py`)
- [x] Ordinary publication, local bridge, Goal pack, install smoke, and replay paths retain zero merge calls and require no merge credential. (`test_forge_policy_and_mergeability_fixtures_never_trigger_merge`, `test_k4_writer_is_isolated_and_has_no_enabled_caller`, `test_evaluator_stays_pure_with_only_the_isolated_k4_consumers`, full `scripts/check-all.sh`)

### Phase K0 — ratify a standalone security contract

**Goal:** turn this plan into a concise normative contract that can be reviewed without changing executable authority.

**Preconditions:** current publisher and host bridge still have no merge operation; draft PR remains awaiting-review-only; no live credentials.

#### Sub-prompt K0.1 — contract and API evidence map

- [x] `[writes docs only]` Change only a new `docs/specs/conditional-self-merge-contract.md`, `PLAN.md`, and links from existing controller/threat documentation if essential; present a file plan before editing.
- [x] Copy the locked M-01 through M-20 decisions, trust boundaries, evidence table, residual race, typed block reasons, and explicit non-goals into the normative contract without weakening v1's existing no-self-merge language.
- [x] Cite only current official GitHub REST/GraphQL documentation for API semantics. Record the chosen API version and every endpoint/field required to distinguish rulesets, classic protection, reviews, threads, checks, bypass actors, actor identity, mergeability, and result reconciliation.
- [x] State that repository content may document policy but cannot grant authority; host-owned policy and fresh run authorization are mandatory.
- [x] Existing tests must pass unmodified; no behavior or schema change is allowed.
- [x] No deletion is expected. Show zero-caller evidence before removing or renaming any existing no-merge assertion.
- [x] Expected diff: 140-220 documentation lines. Split endpoint details into an appendix if the contract exceeds 300 lines.
- [x] Verify every current `no self-merge`, `never merges`, and `awaiting-review` statement remains true and the publisher protocol still has zero merge methods.
- [x] Append a `PROGRESS.md` line recording design ratification only; do not claim support or enablement.
- [x] Stop if any required bypass, review, check-provenance, or merge-result fact cannot be obtained positively from supported GitHub APIs; record it as a blocker rather than substituting GitHub UI text or inference.

**Implementation note (2026-08-11):** the 183-line normative contract pins REST API version `2026-03-10`, the complete REST/GraphQL evidence map, all M-01-M-20 decisions, typed blockers, crash reconciliation, and the residual control-plane race. The approved v1 controller and threat contracts link to it as future design only. Repository search proves the publisher protocol still has zero merge methods, its only fixture merge method raises on use, and the enabled local transition map emits no remote publication or merge action. No schema, controller behavior, credential, publication, or merge authority changed; full preflight passes with 223 tests.

**Phase verification:** review can answer who grants merge authority, what exact evidence is required, which races remain, what blocks, and which code paths must stay incapable of merge.

**Rollback:** remove the new contract link and retain the current v1 no-self-merge contract. No state or remote side effect exists.

### Phase K1 — define closed, host-owned merge contracts

**Goal:** make authority, evidence, intent, and result machine-validatable before any network writer exists.

**Preconditions:** K0 approved; schema versioning and canonical JSON rules remain unchanged; repository-local policy is untrusted.

#### Sub-prompt K1.1 — policy and authorization schemas

- [x] `[writes code]` Add only `schemas/publication/merge-policy.schema.json`, `schemas/publication/merge-authorization.schema.json`, focused fixtures/tests, and schema documentation; present the proposed fields and invariants before editing.
- [x] The policy must bind immutable repository id/node id, owner/name, base branch, allowed low-risk paths, additive deny paths/categories, strict diff ceilings, required check context+app identities, approval floor, one supported merge method, workflow-side-effect acknowledgement, issuer, issued/expiry times, and canonical hash.
- [x] The authorization must bind a fresh explicit trusted request, one mission/binding/authorization id set, one policy hash, one repository/base, one merge budget, issue/expiry times, and a source limited to current user or authenticated host approval storage.
- [x] Enforce non-configurable floors: one independent human approval, one pinned required check, one same-repository PR, zero protected categories, one merge, and no pack/parallel authority.
- [x] Do not add a merge publication target to the existing mission authorization or make the local controller accept publication.
- [x] Imitate existing Draft 2020-12 closed schemas, canonical hashes, stable id patterns, fixture validators, and additional-property rejection.
- [x] Existing schema tests must pass unmodified. Add negative fixtures for repo-local provenance, widened floor, wildcard identity, missing app id, missing expiry, pack authority, and hash drift.
- [x] No deletion is expected. Show all callers before changing an existing authorization enum or schema.
- [x] Expected diff: 220-320 lines. Split policy and authorization if either review exceeds 180 lines.
- [x] Append a `PROGRESS.md` line recording contracts only and the continued absence of a merge caller.
- [x] Stop if policy storage cannot be authenticated outside the repository or if the host cannot distinguish a current explicit merge request from ordinary autonomy.

**Implementation note (2026-08-11):** added separate 99-line policy and 71-line current-run authorization schemas, a paired fixture with eight fail-closed mutations, seven focused cross-document/hash/freshness tests, and a 66-line trust/canonicalization contract. The complete schema/fixture/test/documentation slice is 425 lines before plan/progress bookkeeping—above the estimate because authentication caveats and cross-key invariants remain explicit, while each schema stays below the 180-line split threshold. Existing mission schemas and enums are byte-identical, repository search finds no production consumer or merge method, and full preflight passes with 230 tests.

#### Sub-prompt K1.2 — evidence, intent, and result schemas

- [x] `[writes code]` Add only closed merge-evidence, merge-intent, and merge-result schemas plus focused fixtures/tests; present the identity-binding and replay invariants before editing.
- [x] Evidence must carry completeness/pagination markers, API version, observation window, repository/actor/PR identities, exact head/base SHAs, diff and policy hashes, classic protection, aggregate active rules, source rulesets, bypass visibility, effective reviews/threads, required checks/statuses, mergeability, and typed unsupported/unknown fields.
- [x] Intent must bind an intent-ready two-snapshot proof, both evidence ids/hashes, policy and authorization hashes, exact PR/head/base, selected method, actor, endpoint class, start time, and one-use operation id before a mutation.
- [x] Result must distinguish `merged`, `not-merged`, `reconcile-required`, `policy-blocked`, `auth-error`, `rate-limited`, `permission-missing`, and `api-unavailable`; `merged` requires exact result evidence rather than a message string.
- [x] Imitate `OperationJournal` write-once binding, but do not widen its existing action enums yet. A dedicated merge journal keeps an unreachable future writer separate from the local host action machine.
- [x] Existing contract tests must pass unmodified. Add result-without-intent, changed-head, changed-policy, changed-actor, expired-evidence, missing-page, unknown-enum, and fabricated-merged negatives.
- [x] No deletion is expected. Show zero-caller evidence before replacing any existing publication or operation schema.
- [x] Expected diff: 280-420 lines, split across evidence and journal commits if reviewability suffers.
- [x] Append a `PROGRESS.md` line recording schema ids/versions and zero remote writers.
- [x] Stop if a result cannot prove the exact intended PR/head/base and actor after response loss; retain `reconcile-required` as terminal human handoff.

**Implementation note (2026-08-11):** added closed v1 evidence, one-use intent, and terminal result schemas; a complete paired fixture with eight adversarial mutations; and seven focused shape/hash/freshness/replay tests. The 547-line schema/fixture/test slice exceeds the estimate because all ten paged surfaces, layered protection/rules/reviews/checks, exact actor/PR bindings, and structured merged proof remain explicit; it is split into evidence and journal commits for reviewability. Existing operation/publication schemas and action enums are byte-identical, production contains no caller or merge method, pending intent is terminal `reconcile-required`, and full preflight passes with 237 tests.

**Phase verification:** invalid or incomplete authority/evidence cannot be represented as eligible, while all current local/publication schemas and callers are unchanged.

**Rollback:** remove the unused publication schemas/fixtures. Existing mission state needs no migration because no enum or transition changed.

### Phase K2 — build a read-only, complete GitHub observer

**Goal:** collect normalized, fixture-backed evidence with zero mutation methods and explicit permission/completeness failures.

**Preconditions:** K1 schemas green; endpoint/API version map ratified; no merge writer or live production credential.

#### Sub-prompt K2.1 — fixture-driven observer and normalization

- [x] `[writes code]` Add a separate `pathfinder_core/adapters/github_merge_observer.py`, focused tests/fixtures, and no changes to `GitHubPublisher`; present the backend protocol and endpoint-to-evidence map before editing.
- [x] Expose read methods only for repository and credential actor identity, exact PR, base/head refs, changed files, classic protection, aggregate active branch rules, full source rulesets with parents/bypass actors, reviews, requested reviewers, review threads, checks, commit statuses, deployments, repository merge settings, and merged-state reconciliation.
- [x] Normalize response shapes into the closed evidence schema. Preserve ids, source levels, app identities, rule parameters, pagination totals/cursors, timestamps, and unknown fields needed to fail closed.
- [x] Treat 401, 403, 404, rate limit, timeout, malformed data, pagination ceiling, and missing bypass visibility as distinct typed evidence outcomes. A 404 is not synonymous with "unprotected" unless endpoint, repository identity, permission, and companion rule evidence prove that interpretation.
- [x] Imitate the current adapter's typed auth/rate/permission states and deterministic fixture backends; do not perform live calls in required tests.
- [x] Existing publisher tests must pass unmodified and continue asserting zero merge attempts.
- [x] No deletion is expected. Show all adapter callers before moving any existing method or state enum.
- [x] Expected diff: 300-450 lines per observer/fixture slice; split identity, policy, and PR/check normalization if larger.
- [x] Append a `PROGRESS.md` line listing supported evidence families and remaining unsupported rules.
- [x] Stop when an endpoint is not fully pageable, actor identity is ambiguous, a parent ruleset cannot be attributed, or the API omits a field required by the contract; return typed unknown evidence.

**Implementation note (2026-08-11):** added one unused, fixture-only read protocol and normalizer covering 16 endpoint families; exact request ids/ETags/timestamps, repository/actor/PR/ref/file identities, merge settings and reconciliation, layered classic/ruleset/bypass evidence, review state, checks/statuses, and complete pagination now produce schema-valid canonical snapshots. Ten focused tests distinguish auth, permission, 404, rate, availability, timeout, malformed, pagination, bypass, actor, attribution, ref-drift, future-field, unsupported-rule, and reconciliation paths; a bare classic-protection 404 cannot become `absent` without exact repository, permission, endpoint, and companion-page proof. The cohesive 708-line production module exceeds the estimate because the protocol, closed projections, audit hashes, and typed stop paths share one intentionally isolated seam; review remains separated into the production observer, a 91-line raw fixture, and focused tests. `GitHubPublisher` and its tests are byte-unchanged, the observer has no HTTP implementation or mutating method, merge intent/result still have zero production consumers, and full preflight passes with 247 tests. Merge queue, required deployments/signatures, code scanning/quality, file/metadata restrictions, and unknown future rules remain explicitly unsupported.

#### Sub-prompt K2.2 — GET-only API client boundary

- [x] `[writes code]` Add only the minimal versioned GitHub HTTP client/backend, credential-boundary policy, redaction tests, and operator configuration needed by K2.1; present the exact hostname, methods, endpoints, headers, and permission scopes before editing.
- [x] Enforce `api.github.com`, TLS, GET-only requests, fixed API version/Accept headers, bounded response sizes, bounded pagination, timeouts, retry limits for safe reads only, and redaction of authorization headers and response bodies from logs.
- [x] Keep the elevated evidence token in a process that cannot issue POST/PATCH/PUT/DELETE. Never pass it to implementation, tests, repository commands, publisher callbacks, or the later merge writer.
- [x] Positively record token/actor identity and whether bypass lists were visible. Elevated permission is not positive evidence by itself.
- [x] Imitate existing structured command/network boundary reporting and capability degradation; do not add a general-purpose GitHub client or shell out to repository-provided code.
- [x] Existing tests must pass unmodified. Use a local fake HTTP server or transport fixture; required CI must not contact GitHub.
- [x] No deletion is expected. Show zero callers before replacing a backend seam.
- [x] Expected diff: 220-340 lines. Split transport from credential policy if larger.
- [x] Append a `PROGRESS.md` line recording zero mutating HTTP methods and credential non-guarantees.
- [x] Stop if bypass visibility requires granting the observer mutation capability that the runtime cannot mechanically constrain to GET; keep merge unsupported for that host.

**Implementation note (2026-08-11):** implemented an uncomposed standard-library REST boundary split into a 48-line read-only credential policy, 42-line fixed-host TLS transport, 80-line endpoint/query policy, and 311-line client. It fixes `api.github.com:443`, `GET`, media type, REST `2026-03-10`, user agent, 8 MiB responses, 30 pages, 10-second timeouts, one safe transient retry, two same-host redirects, duplicate-safe JSON, request-id/ETag audits, and typed auth/permission/404/rate/timeout/availability/malformed outcomes. Eleven fake-transport tests prove endpoint/query/redirect/size/page/retry bounds, response and credential redaction, exact version probing, zero mutating transport methods, no secret loader, and zero enabled production caller; full preflight passes with 258 tests. The operator contract requires direct secret injection into this dedicated process, an App JWT with no repository permissions, and an installation token declaring only the seven required read permissions; declarations do not prove actual token scope or identity. Official GitHub documentation confirms ordinary GraphQL queries require `POST`, so the GET-only runtime rejects `/graphql` and returns typed `api-unavailable` for review-thread/queue/cross-check evidence. At this original REST slice, positive token/actor identity and complete bypass visibility remained unchecked; later receipt/identity readers and the pure composed provenance boundary close that source-contract item without installing a live collector. Live eligibility/merge stays unsupported.

**Fixed-query GraphQL follow-up (2026-08-12):** added a separate uncomposed TLS transport that
can POST only one compiled `PathfinderPullRequestEvidence` query to `api.github.com/graphql`.
Callers cannot supply operation text or a URL; variables are closed to exact owner/repository/PR
identity, three independent cursors, and include flags. The canonical query hash binds exact
PR/repository/ref/mergeability/review-decision/queue facts and independently paginated latest
opinionated reviews, code-owner review requests, and review threads. Twelve fake-transport tests
cover fixed operation/body/host/method, connection completion, independent pagination, retry and
byte/page ceilings, response/request-id/identity/count/cursor drift, partial GraphQL errors,
unknown actors/enums/fields, credential redaction, no secret loader, and zero enabled callers. The
REST process remains mechanically GET-only. This source primitive is not a production collector,
and a later source-only identity slice still does not compose it. That slice adds a closed,
canonical host issuance receipt for the one-repository observer token; independently cross-checks
the observer App/installation/bot/repository and future merge App/installation/bot against exact
live responses; and accepts a plan-level protection/rules 403 only when the exact endpoint,
GitHub's `X-Accepted-GitHub-Permissions` header, and the closed upgrade-required response all
qualify absence. Ordinary 403 remains `permission-missing`. The identity verifier has no caller,
does not load either token, and does not yet record its receipt/audits in a complete normalized
snapshot. Later source-only readers now resolve exact permission-qualified membership absence,
walk every check suite/run under a global ceiling without using GitHub's 1,000-suite shortcut,
and fully paginate REST reviews before reading one exact `Metadata=read`-qualified repository
permission per unique reviewer identity. Reviewer permission responses are cross-checked against
the requested actor and retain distinct target-bound audits. Check evidence now also projects the
complete suite/run set and the latest creator-bearing `/statuses` item per context into the observer
contract, cross-checking the result against the combined `/status` envelope, deriving `required`
only from a closed context/App union, requiring every required run to name the exact candidate PR
database/number/head/base identity, and sharing one global request budget. A new pure, uncalled
projector unions host-policy, qualified classic-protection, and every completely paginated active
ruleset check, rejecting unpinned App ids, duplicate/contradictory identities, or incomplete rule
pages. These readers still have no caller and do not read/compose those policy inputs or the
candidate from live sources or compose the review/check/PR projections into a snapshot. A pure
uncalled review reconciler now proves that GraphQL's complete latest-opinionated
review per actor is the exact node/database/actor/state/commit/time/association record selected from
the complete chronological permission-qualified REST audit; split actor sets, identity drift,
nonchronological history, incomplete pagination, or reused request ids block. Review requests,
threads, mergeability, and queue state now pass through a second pure projector that requires the
exact compiled query hash, one real GraphQL audit family, complete independent connections, exact
repository/PR/ref/SHA identity, rate-limit/audit coverage, and the reconciled publication-pusher
proof. A pure, uncalled composer now requires those projections plus the verified observer receipt,
all four App/installation/bot/repository identity audits, complete REST review history, the policy-
derived required-check union, exact check pages, and every remaining normalized REST family. It
emits schema-valid evidence plus a separate canonical provenance receipt bound to the evidence,
credential/publication receipts, query, reviews, checks, request ids, and collection window. The
publication request now also binds the
authenticated publication credential's bot database/node/login identity through exact preflight and
the durable repository/ref/SHA push receipt. An uncalled pure reconciler validates both canonical
publication documents, requires a later fixed-query GraphQL observation of the identical
repository/PR/head/base identity, and projects that bot database id as the controller pusher. This
does not prove that an installed host prevented a later same-SHA push by a different actor; that
branch-ownership fact remains mandatory. The positive-identity/bypass checkbox is now closed by
the composed provenance receipt, while both K5 installed-host readiness items remain unchecked:
the composer owns no client, credential, durable host store, or installed caller.

**Branch-ownership follow-up (2026-08-12):** a pure, uncalled proof now requires one active,
repository-scoped ruleset whose only rules restrict controller-branch creation, update, and
deletion and whose sole always-bypass actor is the authenticated publication App. It then requires
the complete effective-rule view for the exact controller branch and a final qualified ref read at
the published SHA, all ordered after the evidence instant with unique request ids. The complete
evidence composer binds the resulting canonical proof and rejects request-id or identity reuse.
This closes the source proof shape, not the installed-host gate: no packaged route collects,
authenticates, or durably persists these inputs, and K5.2 remains closed.

**Composer follow-up (2026-08-12):** the 462-line production adapter exceeds the per-slice estimate
because it owns the closed backend projection for every observer method, global request/time checks,
and the separately schema-validated provenance receipt in one auditable boundary. Five focused
tests cover deterministic composition, malformed and drifted identities, review/policy/check drift,
cross-surface request reuse, collection-window violations, input immutability, and zero source
callers. It adds no network client or installed route.

**Phase verification:** deterministic fixtures prove complete normalized evidence and every incomplete/permission path, while a structural test proves the observer has zero remote mutation method.

**Rollback:** remove the unused observer/client. Existing awaiting-review publication remains unchanged and credentials were never exposed to implementation.

### Phase K3 — implement a pure eligibility decision

**Goal:** produce an auditable typed verdict from trusted contracts and evidence without network or mutation access.

**Preconditions:** K2 normalization complete; all M decisions represented in schemas; protected registry and canonical diff evidence available.

#### Sub-prompt K3.1 — policy lattice and hard floors

- [x] `[writes code]` Add an unused `pathfinder_core/merge_policy.py`, focused unit/property-style fixtures, and typed verdict documentation; split typed results and check/review proofs when the decision module crosses the review threshold; present precedence and every deny code before editing.
- [x] Evaluate shipped hard floors, then host policy, then the most restrictive classic/ruleset combination. Repository settings may narrow but can never cancel a shipped floor or host-policy restriction.
- [x] Require exact identity/hash/time bindings, fully complete evidence, same-repository PR, open/non-draft/current branch, zero protected matches, diff ceilings, supported squash method, independent current human review, clean review decision/threads, required pinned checks, non-bypass actor, clean/up-to-date merge state, and an unexpired observation window.
- [x] Count the latest effective review per human only. Exclude author, implementation agent/other bots, last pusher, merge/check actors, dismissed/stale reviews, and unknown associations. Require the greater of shipped, host-policy, classic, and ruleset approval counts.
- [x] Union required check identities across classic protection, all rulesets, and host policy. Require both a status and check run when GitHub reports both under a required name; validate expected app id and the exact GitHub-required SHA.
- [x] Block all unknown or initially unsupported active rule types, including merge queue, required deployments, required signatures, code scanning/quality/coverage, file restrictions, and metadata rules until dedicated semantics and fixtures are added.
- [x] Imitate `ExecutionPolicy` and `ProtectedSurfaceRegistry`: closed inputs, explicit errors, additive restrictions, no prose inference, and deterministic results.
- [x] Existing behavioral tests pass. Add an adversarial matrix covering every evaluator-relevant fail-closed acceptance item above and pairwise classic/ruleset conflicts; change the K2 evidence schema/fixture/observer only where semantic proof was missing.
- [x] No deletion is expected. Show zero-caller evidence before consolidating existing publication states.
- [x] Expected diff: 300-450 lines, with data fixtures separate from decision logic. Split checks/reviews from rule layering if larger.
- [x] Append a `PROGRESS.md` line recording supported rules, all typed blockers, and zero merge capability.
- [x] Stop if eligibility needs a UI-only GitHub fact, repository prose, model judgment, or a permission/bypass inference; return an explicit unsupported/unknown verdict.

**Implementation note (2026-08-11):** added an unused pure evaluator split into policy/rule layering, review/check proofs, and immutable typed verdicts after the production decision exceeded the review threshold. The AND-only lattice validates closed schemas, canonical hashes, authority and repository bindings, validity windows, request audits and pagination, diff hashes/classifications/ceilings, same-repository controller PR state, classic plus all active rules, bypass actors, latest permission-qualified independent reviews, review decision/threads, and exact required check App/SHA/status evidence. Outcome precedence is `unknown > unsupported > policy-blocked > eligible`; the approval maximum and check union are deterministic and no input is mutated. A minimal K2 evidence correction now carries allowed merge methods, a source/aggregate rule-parameter semantic hash, the closed GitHub review decision, and exact reviewer write/admin permission instead of asking K3 to infer them from association. Thirty-five focused contract/observer/evaluator tests and all 277 repository tests pass. Repository search proves the evaluator has zero production callers, credentials, network primitives, mutation methods, or merge capability; GraphQL-only live facts remained unavailable in that slice. The later fixed-query GraphQL primitive is still uncomposed, so live eligibility and merge stay unsupported.

#### Sub-prompt K3.2 — freshness and drift re-evaluation

- [x] `[writes code]` Change only the pure evaluator, evidence snapshot helpers, and focused tests; present the time/reread algorithm before editing.
- [x] Bind the snapshot to observed start/end times and a hard maximum age of 60 seconds; allow host policy to shorten but not lengthen it.
- [x] Require immediate rereads of repository, actor, PR head/base, policy/ruleset version identifiers, review decision, and check rollup before a future intent can be issued. Any mismatch requires a complete new snapshot, not selective patching.
- [x] Record that GitHub offers no atomic policy-snapshot precondition on the merge call. Treat a concurrent trusted-admin control-plane mutation after the final reread as a documented residual risk, not as something the client has solved.
- [x] Existing tests must pass unmodified. Use a fake clock and fixtures for expiry at the boundary, base advance, force-push, ruleset update, review dismissal, check rerun, actor rotation, and policy hash drift.
- [x] No deletion is expected. Expected diff: 100-180 lines.
- [x] Append a `PROGRESS.md` line recording the residual TOCTOU non-guarantee.
- [x] Stop if implementation attempts to cache or selectively reuse earlier green evidence after any identity/control-plane drift.

**Implementation note (2026-08-11):** the pure evaluator now applies the earlier of the
host-provided expiry and `observed_at + 60 seconds`, with the exact boundary expired. Its separate
`evaluate_reread` path independently evaluates two complete snapshots, requires the reread to start
after the first collection, and rejects reused evidence identities, hashes, or request ids. Whole
normalized authority, repository, actor, PR/merge-state, diff, protection/ruleset, review/decision,
check, and completeness domains must remain equal; a mismatch returns typed unknown and requires a
brand-new complete snapshot cycle. The fake-clock/drift matrix and all 280 repository tests pass.
The evaluator remains unused and unable to read, cache, issue an intent, access a credential, call a
network, or merge. GitHub still offers no atomic precondition over the base, policy, protection,
rules, reviews, and checks after that final reread, so trusted-admin control-plane mutation remains a
documented residual race.

#### Sub-prompt K3.3 — independent-review remediation and intent-ready proof

- [x] `[writes code]` Bind authorization to the exact authenticated controller publication,
  mission-state hash, PR id/node/number, head/base refs and SHAs, and canonical diff/file/object
  evidence hashes; a controller-shaped branch alone cannot pass.
- [x] Anchor protected surfaces to the shipped baseline: accept only that exact baseline or a
  schema-valid additive override naming it, then independently recompute every current/previous
  path classification. Derive special-file labels from an authenticated controller Git-diff
  receipt; forge-supplied labels cannot erase a protected, symlink, submodule, binary, workflow,
  CODEOWNERS, or policy match.
- [x] Allow host policy to shorten the 60-second ceiling, require a fresh host-policy-store receipt
  in each snapshot, use strict non-touching reread ordering, and reject receipt reuse or policy hash
  drift.
- [x] Count only host-attested human reviewer ids and exclude PR author, last pusher, merge actor,
  all implementation actors, and every observed check creator. Normalize commit-status creator
  identity explicitly.
- [x] Keep a single-snapshot verdict advisory with `intent_ready = false`; emit a distinct immutable
  readiness proof only after two complete ordered/disjoint green snapshots. Bind inert intent and
  result contracts to that proof and both evidence hashes.
- [x] Persist both complete evidence documents in the inert journal, validate their canonical
  hashes, and replay the actual two-snapshot evaluator at intent time; summary-only or stale proof
  metadata cannot satisfy the readiness contract.
- [x] Make the low-risk Goal boundary and classic protection semantics machine-readable. Reject
  release, deployment, data mutation, and real-world-side-effect Goal bindings; normalize and
  cross-check stale-review, code-owner, linear-history, signature, and restriction settings, with
  unsupported semantics typed fail-closed.
- [x] Add adversarial regressions for rehashed different PRs, erased protected/special labels,
  changed registry hashes, unallowlisted service users, implementation/check actors, policy receipt
  reuse, and freshness shortening. Add the required deterministic merge-evidence eval fixture.
- [x] Preserve zero production callers, credentials, network/mutation primitives, routes, and merge
  methods. K4 remains closed until a fresh independent security review is clean and exact PR
  identity is durably persisted by runnable awaiting-review publication.

**Implementation note (2026-08-12):** the K3 review-remediation slice now authenticates the exact
controller candidate, anchors protected policy to the shipped baseline, recomputes protected and
special surfaces, normalizes controller Git-object/policy-read/check-creator receipts, narrows
reviewer identity to a host human allowlist, and separates advisory verdicts from closed
two-snapshot readiness proofs. The K1 journal persists both full evidence documents and accepts a
proof only when the actual evaluator reproduces it at intent time. Closed Goal-risk fields exclude
release/deployment/data/real-world work, while explicit classic-protection semantics reject opaque
or unsupported settings, including ruleset code-owner requirements. Malformed protected-policy
objects return typed denials, and journals replay the exact baseline or additive policy document.
Focused contract, observer, evaluator, adversarial journal, and actual-code eval suites cover each
reproduced bypass, and all 287 repository tests pass. The implementation
remains inert: repository search finds no production caller, credential, remote mutation, merge
method, or enabled route. A proof crossing a process boundary will still require a trusted
host-owned envelope in any future K4 composition.

**Phase verification:** a pure process can explain exactly why a PR is eligible or blocked, and exhaustive negative fixtures prove it cannot merge or perform network access.

**Rollback:** remove the unused evaluator. No schema migration or external state exists.

### Phase K4 — add a crash-safe merge primitive, unreachable by default

**Goal:** implement one exact synchronous merge operation behind a dedicated boundary without routing any normal user flow to it.

**Preconditions:** K0-K3 independently security-reviewed; runnable awaiting-review publication exists separately; exact PR identity is persisted; no merge queue or unsupported active rule. The isolated primitive may be built and tested before publication is composed, but it must retain zero callers until every precondition is satisfied.

#### Sub-prompt K4.1 — dedicated merge credential and journal

- [x] `[writes code]` Add only a separate merge executor module/process, dedicated journal implementation using K1 schemas, focused fixtures, and credential policy; present the state machine and credential scopes before editing.
- [x] The executor accepts only schema-valid policy, authorization, exact protected policy, an
  intent-ready two-snapshot proof, both bound evidence records, and merge intent inputs. It rejects
  a single advisory verdict. It cannot discover work, update a Goal, push, open/edit/comment on a
  PR, change protection/rulesets, delete a branch, release, deploy, or invoke repository code.
- [x] Restrict the merge token to the one repository and permissions needed for reading the exact PR and writing contents through the merge endpoint. Bind and compare its exact actor/app/installation identity with observer evidence and every bypass list.
- [x] Persist the write-once intent before network mutation. An intent with no terminal result is `reconcile-required`; it is never automatically replayed.
- [x] Atomically claim the authorization/readiness proof once across operation ids, persist a closed authenticated credential receipt, and allow only the intent creator to record dispatch and send.
- [x] Imitate `OperationJournal` atomic write-once behavior and binding checks, but keep its namespace/action enums separate from the local mission journal until composition is explicitly approved.
- [x] Existing operation/publication behavior remains green and retains zero merge calls. The two deliberate K3 absence guards now assert exact K4 isolation instead of asserting that no writer source exists.
- [x] No deletion is expected. Show zero callers for the new executor before and after this phase.
- [x] Split credential policy, journaling, execution, and the fixed-host backend. The implementation exceeds the estimate because the closed result reasons, exact squash proof, host-envelope boundary, and full crash matrix are explicit rather than implicit.
- [x] Append a `PROGRESS.md` line recording that the primitive is unreachable/default-off.
- [x] Stop if the merge token is also available to implementation, observer, repository commands, or ordinary publication, or if its actor may bypass a rule.

#### Sub-prompt K4.2 — exact synchronous request and reconciliation

- [x] `[writes code]` Change only the unreachable executor/backend protocol and fixture tests; present the request, response, crash points, and reconciliation table before editing.
- [x] Permit one `PUT /repos/{owner}/{repo}/pulls/{number}/merge` with exact `sha` and `merge_method: squash` only. Reject missing SHA, default method, rebase, merge commit, async, stacked, auto-merge, or queue endpoints.
- [x] Re-read and re-evaluate fresh evidence immediately before issuing the intent; after intent persistence, send at most one request.
- [x] Record success only when the response says merged and exact follow-up observation confirms repository/PR/head/base, method-compatible merge commit, merging actor, and time. Do not trust the response message string.
- [x] On timeout/connection loss, read the exact PR/merged endpoint once through the read-only boundary. Exact proof records the result; non-merged, closed-without-merge, changed identity, or unavailable evidence returns `reconcile-required` and sends no second PUT.
- [x] Map 401/403/404/405/409/422, rate limits, malformed success, and already-merged responses to typed results without retrying mutation.
- [x] Existing functional tests remain green. Add crashes before intent, after intent, before send, after remote side effect/before response, after response/before result, and after result; assert one or zero merge calls as appropriate.
- [x] Distinguish a pre-dispatch crash from an ambiguous dispatched operation so reconciliation cannot credit known-zero-send state; prove concurrent callers and repackaged operation ids cannot create a second send.
- [x] Version the strengthened intent/result shapes as v2, explicitly reject the uncomposed K1 preview v1, and cover the actual writer plus artifacts with a deterministic offline eval.
- [x] No deletion is expected. The explicit transport, proof normalization, and crash fixtures exceed the estimate without adding an enabled caller.
- [x] Append a `PROGRESS.md` line recording fixture call counts and the absence of a normal caller.
- [x] Stop if response-loss reconciliation cannot attribute the exact merge or if any path retries a pending intent.

**Phase verification:** the primitive is internally crash-safe and adversarially tested, but repository search proves no CLI, route, publisher, mission, or host bridge can call it.

**Rollback:** remove the unreachable primitive and journal records from test fixtures. If a future live test merged a disposable PR, preserve the audit record; never rewrite base history.

### Phase K5 — compose an explicit, default-off conditional merge path

**Goal:** expose the primitive only through a separately approved post-publication controller whose default remains observation-only.

**Preconditions:** K4 green and independently reviewed; awaiting-review GitHub publication is
itself runnable, idempotent, and isolated; the operator has installed trusted policy and credential
boundaries; and a disposable-repository rehearsal has exercised publication plus complete
read-only evidence collection with zero merge calls. This is distinct from the later, separately
approved composed merge rehearsal in K6.2.

**Current readiness gate (2026-08-12):**

- [x] K4 source primitive is green and independently reviewed.
- [x] The source-only publication prerequisite is crash-tested and independently reviewed.
- [x] A source-only immutable host-artifact envelope binds and externally authenticates the exact publication journal, operator policy/authorization/protected policy, both credential receipts, branch-ownership proof, evidence, and provenance; its only packaged consumers are an unconstructed single-snapshot collector and the unconstructed two-snapshot read-only adapter.
- [x] Exact archive, credential-free host-install, CodeQL, dependency, and three-OS checks are green.
- [ ] Awaiting-review publication is runnable through a trusted installed host with authenticated envelopes and exact persisted PR identity.
- [ ] A trusted host supplies complete live GraphQL/REST evidence plus operator-owned policy and credential boundaries.
- [x] The publication and complete read-only evidence boundaries have passed a bounded disposable-repository rehearsal with zero merge calls.
- [x] K5.1 read-only composition is implemented and independently reviewed.
- [ ] K5.2 has separate human security approval. Repeated implementation approval does not satisfy this gate.

Until the remaining operational prerequisites and separate K5.2 approval are checked, the safe
next work is trusted-host/read-only-collector closure, contract clarification, and default-off
regression coverage only. Fixture success cannot be relabeled as runnable publication,
trusted-host installation, live evidence, or merge authority.

**Bounded operational rehearsal (2026-08-12):** an external operator-hosted adapter used two
repository-scoped GitHub Apps against the private disposable
`Chris-Archive-Archive/pathfinder-merge-rehearsal` repository. The real source controller persisted
one exact awaiting-review receipt for PR 1 and replayed without another remote effect. A separate
read-only App collected two complete 16-request REST/GraphQL snapshots with disjoint request ids,
matching receipt diff hashes, no unknown/unsupported fields, and no security-domain drift. The PR
remained open and unmerged; deployments and releases stayed at zero; no merge App, credential,
intent, or request existed. GitHub's qualified upgrade-required response proved classic protection
and rulesets unavailable on this private Free-plan target, so it cannot be eligible. See
[`docs/rehearsals/2026-08-12-zero-merge-publication.md`](docs/rehearsals/2026-08-12-zero-merge-publication.md).
This closes only the bounded rehearsal checkbox: the adapter is not an installed package route, the
package still has no live backend/credential loader, and the host binding deliberately was not a
schema-valid merge policy or authorization. The first two readiness items remain unchecked. K5.1's
explicitly approved observation-only source implementation and independent review are now complete;
that does not close either installed-host prerequisite or authorize K5.2.

**Authenticated host-artifact implementation note (2026-08-13):** added one source-only,
uncalled immutable collection store for the completed publication/evidence boundary. It accepts an
injected external host authenticator but ships no authenticator implementation or key loader. One
closed envelope atomically contains the validated publication request/dispatch/receipt, publication
and observer credential receipts, controller-branch ownership proof, complete evidence, and
provenance. The store independently rechecks every canonical hash plus repository, mission, PR,
ref/SHA, diff, App/installation/bot, review/check, request, and observation-time binding. POSIX
storage is current-user-owned, owner-only, non-symlink, outside repository trust, descriptor-pinned,
size-bounded, and write-once via a durable hard-link publication; Windows fails closed pending
equivalent ACL proof. Reads never create state, exact repeats do not re-attest, concurrent writers
converge on one envelope, and renamed, re-hashed, wrong-store, split-identity, or externally
unauthenticated records block. The composer now also rejects a publication/evidence diff or mission
binding mismatch that this integration exposed. A deterministic actual-code eval and 460 controller
tests are green. A follow-up v2 envelope now also carries the exact operator policy, current-run
authorization, and shipped-baseline or additive protected policy. It independently binds their
canonical/effective hashes, repository, mission, publication candidate, evidence policy-read, and
validity windows. One source-only read adapter accepts only two explicit, distinct evidence ids,
re-verifies both external attestations, and requires identical publication and authority documents
plus one authenticator/key identity across the pair before passing them to K5.1. Additive policies
are hashed only after recomposition with the shipped baseline. No package route constructs this
adapter or supplies its authenticator. This closes a stronger source storage/composition contract
only: no trusted authenticator/key, installed collector, live credential injector, publication
route, or merge path was added, so both installed-host readiness items and K5.2 remain unchecked.

**Source collector implementation note (2026-08-13):** added one unconstructed orchestration
boundary around the already fixed observer identity, GraphQL, permission-qualified REST review, and
exact check/status readers. Every reader must share the same injected observer installation
credential; the observer verifier no longer requires or constructs a merge App credential. The
collector derives the exact candidate and required-check union, eagerly materializes every supplied
normalized base surface, closes the trusted evidence window using only its injected clock, then
obtains the post-window controller-branch proof, composes canonical evidence/provenance, and sends
the exact documents to the immutable external-authentication store. Stale receipt time, mixed
credentials, backwards/expired completion, post-window lazy reads, and persistence drift fail
closed; a real-store integration attests and reloads the exact snapshot. A follow-up source slice
now supplies the exact candidate/diff/deployment reader and the concrete post-window ownership
reader. The collector consumes candidate reads only after authenticated REST/GraphQL publication
reconciliation, and it requires both readers plus the policy backend to share the exact
observer installation credential. Changed-file patches are byte-counted directly; an omitted patch
is accepted only for controller-attested binary content. Ownership reads are fixed to the configured
repository ruleset, complete effective rules, and final branch ref; every response must carry the
documented Metadata- or Contents-read qualification, and omitted bypass actors remain a hard
unknown rather than an empty list. The collector still requires an injected policy backend,
external authenticator, store, and already-created credentials. Nothing constructs it from a command,
mission, pack, publication controller, environment, or installed host route. It therefore narrows
but does not close the two installed-host readiness items, and it adds no merge credential, writer,
intent, request, or K5.2 authority.

**Normalized policy REST implementation note (2026-08-13):** added one source-only concrete
reader for the remaining classic-protection, aggregate active-rule, source-ruleset, bypass-actor,
and exact membership surfaces. One immutable snapshot owns both normalized evidence and the
classic/ruleset required-check views, so a caller cannot mix policy reads with different request
audits. Active rules and the `includes_parents=true` source index are permission-qualified and fully
paginated; every referenced ruleset is fetched once, source/index/detail identities and semantic
parameters are cross-checked, and all physical request ids are globally unique. Bypass actors are a
zero-request derived projection of those details rather than a duplicate synthetic read. Qualified
private-plan absence remains explicit, while an ordinary 403, omitted ruleset `bypass_actors`,
unknown field/parameter, source drift, request/page ceiling, or unsupported source blocks. Classic
team and ruleset organization-admin memberships use the existing exact qualified endpoints;
ruleset Team/RepositoryRole ids remain unresolved and ineligible because REST does not provide the
source-owned slug/role name required to prove them safely. The reader accepts only an injected exact
merge-actor subject and is still unconstructed; binding that subject to a separately verified merge
App receipt, supplying the observer credential and external authenticator/key, and installing a
trusted host route remain open. No credential loader, command, publication mutation, merge
credential, intent, request, or K5.2 path was added.

**Prerequisite implementation note (2026-08-12):** added a source-only, uncomposed publication
controller and separate write-once journal. A fresh authenticated host envelope embeds and
canonically binds the full explicit GitHub-awaiting-review authorization, its one-PR ceiling, the
committed mission, repository, controller branch, exact head/base SHAs, all three diff hashes,
bounded title/body, pinned check context/App identities, and publication-only credential boundary.
Before push or create, the injected backend must read-only preflight and return that exact target.
The entry points take no caller-selected time; the injected host clock alone proves envelope and
authorization freshness.
Success persists a closed authenticated receipt containing repository id/node, PR database
id/node/number, GitHub URL, exact refs/SHAs, mission-state and authorization hashes, diff, and each
successful check's exact context, App id, and head SHA. The dispatch record is durable before the
remote callback, but the journal lock is released before that callback so process death cannot
strand recovery; a pending operation can only use read-only exact lookup/check observation and
never pushes or creates again. Deterministic tests, a process-death probe, and an actual-code eval
prove terminal replay, exact merge-authorization projection, one-use claims, pre-effect target
rejection, check-identity rejection, and zero production callers. The package guard rejects both
controller and lower-level publisher construction plus concrete generic or exact GitHub backends
outside the source-only protocol owner. No CLI, mission host, Goal pack, installed route, live
backend, credential loader, or merge path constructs the controller, so this prerequisite grants no
publication or K5 execution authority. Its independent source review is now complete. The later
K5.1 observation-only implementation does not make publication runnable, install a live evidence
collector, or supply operator authorization, policy, or credentials.

#### Sub-prompt K5.1 — read-only status and dry-run composition

- [x] `[writes code]` Add only a `merge status`/`merge evaluate` surface, composition state, operator docs, and focused tests; present the call graph before editing.
- [x] Default output is a typed eligibility/block report. It may collect evidence but cannot create an intent or load the merge token.
- [x] Keep normal `/goal`, `/pathfinder`, `/pathfinder auto`, mission host, Goal packs, publisher, and resume behavior unchanged. No automatic route escalation may call merge evaluation or execution.
- [x] Require exact persisted mission/PR metadata from the separately authorized publisher; never discover an arbitrary open PR by title, branch prefix alone, or latest timestamp.
- [x] Imitate concise controller status and structured `--json` output; rendered Markdown remains a view of canonical JSON.
- [x] Existing behavior tests pass unchanged; three exact source-consumer allowlists were minimally updated for the sole read-only evaluator caller. Call-graph/behavior guards prove default routes and package installs load no merge credential and issue zero merge requests.
- [x] No deletion occurred. Constructor scans showed zero publication, publisher, or merge-executor callers before and after; the new caller reaches only the pure evaluator.
- [x] Scope remained K5.1-only. The additive diff exceeded the estimate because the closed report schema, exact receipt/evidence rebinding, installed-host ownership/symlink checks, and deterministic negative suite are explicit rather than implicit.
- [x] Append a `PROGRESS.md` line recording dry-run-only composition.
- [x] Stop if awaiting-review publication lacks persisted exact PR identity or if reading merge status would implicitly authorize execution.

**K5.1 implementation note (2026-08-12):** the explicitly selected command lazily loads one
observation-only reader rooted in an owner-only, current-user-owned non-symlink host directory
outside repository trust. On POSIX it pins that directory descriptor and reads only fixed
journal/policy/authorization/two-snapshot evidence descendants relative to the descriptor with
symlink following disabled; Windows fails closed until equivalent ACL ownership proof exists. It
requires one exact validated publication request/dispatch/receipt, falls back only to the shipped
protected-surface baseline, and rebinds both snapshots and authorization to the receipt's
repository, mission, PR, refs, SHAs, and diff. Its closed hashed report binds each evaluated input's
canonical identity/hash and uses only the closed evaluator deny-code domain. It always remains
`awaiting-review` with execution, writer credential, intent readiness, and intent creation fixed to
false; even an eligible evaluation discards the generated readiness proof. Missing or malformed
inputs are typed, while a missing exact publication receipt stops. A deterministic actual-code
artifact eval owns this structured runtime contract. The package scan forbids every writer,
credential, environment-token, subprocess, and network primitive from the caller. Independent
standards and adversarial security/spec reviews are clean after direct remediation probes for host
path swaps, Windows ownership, journal identity, malformed JSON, exact input correlation, and
closed report domains. The 382-test preflight and exact archive smoke are green. K5.2 remains
closed and requires separate human security approval.

#### Sub-prompt K5.2 — separately approved execution gate

- [ ] `[writes code; separately approved enablement]` Change only the explicit merge execution command/controller, authorization loader, package/docs mirrors, and focused tests; present the final call graph and human approval evidence before editing.
- [ ] Require an authenticated host-owned policy, fresh merge-enabled run authorization, exact mission/PR binding, one remaining merge budget, fresh eligible evidence, and explicit execution command. Absence of any key returns awaiting-review without loading the writer credential.
- [ ] Make the feature disabled in shipped defaults. Enabling it requires an operator-owned setting outside the repository plus the current run authorization; repository code and the PR diff cannot toggle it.
- [ ] Advance canonical state to `merged` only after K4 result proof. Preserve `awaiting-review`, `blocked`, or `reconcile-required` otherwise; never report merged from a closed PR alone.
- [ ] Do not delete the head branch, comment, release, deploy, auto-revert, or activate another Goal after merge.
- [ ] Existing tests must pass unmodified. Add missing-key, expired-key, wrong-repo, wrong-policy, second-call, pending-intent, response-loss, ordinary-auto, pack, and protected-diff negatives.
- [ ] No deletion is expected. Show the exact new caller list; it must contain only the explicit controller path.
- [ ] Expected diff: 220-340 lines. Split state projection/docs from execution if larger.
- [ ] Append a `PROGRESS.md` line recording the enablement decision, call graph, and review reference.
- [ ] Stop without implementation unless a human security review explicitly approves this sub-prompt after K0-K5.1 evidence. Approval to implement earlier phases does not authorize this gate.

**Phase verification:** default installs remain awaiting-review-only; an explicitly configured test host can execute exactly one eligible disposable PR merge; all ordinary and missing-evidence paths issue zero calls.

**Rollback:** disable the host-owned feature flag and revoke the merge credential. Preserve journals and merged observations. Do not attempt history rewrite or automatic revert.

### Phase K6 — adversarial verification, packaging, and operational recovery

**Goal:** prove the exact shipped artifact keeps merge authority narrow and fails safely across platforms, hosts, retries, and GitHub policy variants.

**Preconditions:** K5 explicitly approved; all deterministic suites green; dedicated disposable GitHub repository available for optional live rehearsal only.

#### Sub-prompt K6.1 — deterministic attack and regression suite

- [ ] `[writes code]` Change only fixtures/evals, validation scripts, coverage/threat/operator documentation, and CI wiring; present the scenario matrix before editing.
- [ ] Cover classic-only, ruleset-only, layered/more-restrictive, organization-parent, hidden-bypass, admin/role/app bypass, rule drift, review drift, check-source collision, required merge commit, fork, protected diff, queue, signed commits, deployment, unknown rule, API-version change, and every crash boundary.
- [ ] Seed polarity tests that fail if `default off`, independent human review, pinned checks, same-repository, zero protected surfaces, no bypass, synchronous SHA binding, no retry, or no normal-route caller is weakened.
- [ ] Imitate the existing behavioral invariant, replay, package smoke, and coverage-matrix conventions. Never put live credentials in CI fixtures or logs.
- [ ] Existing tests must pass unmodified. No deletion is expected; show zero-caller evidence before removing any no-merge fixture.
- [ ] Expected diff: 300-450 lines split by contracts, adapter, evaluator, executor, and behavior guards.
- [ ] Verify focused tests, full `scripts/check-all.sh`, exact-archive package smoke, credential-free Codex/Claude install/load smoke, ShellCheck, CodeQL, Dependency Review, and hosted Ubuntu/macOS/Windows jobs.
- [ ] Append a `PROGRESS.md` line with exact commit/archive ids and zero-credential hosted results.
- [ ] Stop if a fixture can reach the merge backend without first producing valid policy, authorization, evidence, intent, and one-use budget records.

#### Sub-prompt K6.2 — optional disposable live rehearsal and recovery guide

This is the later rehearsal of the composed writer path. It does not satisfy or replace K5's
earlier zero-merge publication/evidence rehearsal.

- [ ] `[external mutation; separately approved]` Use only a dedicated disposable GitHub repository with no deployment/release hooks, test credentials, and a test PR created for this rehearsal; present exact targets and cleanup before acting.
- [ ] Exercise one blocked PR for each visible GitHub rule family and at most one eligible squash merge. Capture sanitized endpoint/status evidence, never tokens or private response bodies.
- [ ] Simulate a lost client response only through a controllable proxy/transport; verify read-only reconciliation and zero second merge call.
- [ ] Do not point the rehearsal at Pathfinder, a production repository, an organization-wide ruleset, a fork network, or a branch with real release/deployment effects.
- [ ] Existing deterministic tests remain the required gate; live rehearsal is bounded/manual and must not become flaky required CI.
- [ ] Document operator actions for awaiting-review, policy blocked, permission missing, rate limited, reconcile required, token revocation, feature disablement, and separately authorized revert PR creation.
- [ ] Expected repository diff: documentation/sanitized fixtures only, under 200 lines. No automatic deletion; explicitly retire test credentials after evidence capture.
- [ ] Append a `PROGRESS.md` line naming only the disposable repository class, outcome, and sanitization—not secrets or private ids.
- [ ] Stop if the target cannot be proven disposable or if any workflow can deploy, release, mutate data, notify real users, or affect another repository.

**Phase verification:** exact packages preserve default-off behavior, deterministic attack cases stay green on all hosts, and a bounded disposable rehearsal confirms GitHub enforcement/reconciliation assumptions without production impact.

**Rollback:** revoke/rotate test and merge credentials, disable the host-owned gate, archive the disposable repository if desired, and preserve audit records. Existing merges remain forward-only history.

### What could go wrong

1. **The bot relies on GitHub to block it while holding bypass power.** Prevent this with exact actor identity, complete bypass evidence, a credential that is not an admin/bypass actor, and a hard block when visibility is incomplete.
2. **The evaluator mistakes one ruleset for the effective policy.** Use the aggregate exact-branch endpoint, fetch every repository/organization source, layer classic protection, and block on pagination or source drift.
3. **A green check is forged or belongs to the wrong commit/app.** Union required contexts, pin expected app identities, inspect both check-runs and commit statuses, and bind them to GitHub's required latest head/test merge commit.
4. **Approval becomes stale after a push or base change.** Require current effective reviews, last-push independence, a clean/up-to-date base, immediate reread, and no automatic update/rebase after review.
5. **Repository content grants itself merge power.** Keep enablement, policy, approval, and credentials outside the repository; categorically block changes to protected/policy/CI/CODEOWNERS surfaces.
6. **A timeout causes a duplicate or misattributed merge.** Journal intent first, send one SHA-bound request, and require exact read-only reconciliation before recording `merged`.
7. **The feature quietly spreads into normal autonomy.** Keep a separate module, credential, journal, command, authorization type, package guard, and explicit zero-caller tests for ordinary routes.
8. **A merge triggers deployment or another irreversible workflow.** Require explicit admin acknowledgement for ordinary merge-triggered workflows while continuing to block any Goal or repository whose merge path has release, deploy, data, or real-world side effects.
9. **A repository admin weakens rules during the final race window.** GitHub does not bind the full policy snapshot to the merge request. Minimize the window, reread immediately, require a non-bypass actor, audit ids/times, and state this trusted-control-plane residual risk honestly.

### Where confidence is lowest

- GitHub's bypass-actor visibility can require elevated ruleset access. Some hosts may be unable to provide that visibility through a mechanically GET-only process; those hosts must remain awaiting-review-only.
- GitHub policy and review/check state cannot all be atomically preconditioned on the synchronous merge call. Only the head SHA is server-bound by the request; the remaining race assumes trusted repository administrators do not mutate controls concurrently.
- Required-check selection can target a test merge commit rather than the head and can combine check-runs with commit statuses. Fixture research must match current GitHub behavior before the evaluator recognizes this as supported.
- CODEOWNERS and eligible-reviewer semantics are best treated as GitHub-enforced facts plus full review evidence, not reimplemented from a possibly changed repository file. The exact positive API proof needs disposable live rehearsal.
- Signed commits, required deployments, code scanning/quality/coverage, merge queues, and rebase reconciliation each deserve separate designs. Blocking them initially is safer than partially supporting them.

### What not to do

- [ ] Do not check the remaining master item merely because this design exists; support requires K0-K6 evidence and the separately approved execution gate.
- [ ] Do not add `merge()` to `GitHubPublisher` or a merge action to the local mission host as the first implementation step.
- [ ] Do not let a checked-in YAML/JSON/Markdown file, prior approval, resolved intent, or ordinary Goal grant merge authority.
- [ ] Do not treat branch `protected: true`, a green combined status, `mergeable: true`, or GitHub's merge button state as sufficient evidence.
- [ ] Do not interpret 404/empty arrays/omitted bypass actors as absence of protection or bypass.
- [ ] Do not count bot/self/stale/dismissed/author/last-pusher approval toward the human floor.
- [ ] Do not allow protected surfaces, packs, forks, stacks, queues, releases, deployments, migrations, destructive changes, or unknown active rules in the first release.
- [ ] Do not use auto-merge, asynchronous merge, stacked merge, direct pushes to the base, branch deletion, or automatic revert.
- [ ] Do not retry a pending merge intent or fabricate `merged` from PR closure, an exception message, or a missing PR.
- [ ] Do not expose observer/merge credentials to implementation, repository commands, test subprocesses, logs, or one another.
- [ ] Do not claim the client has eliminated GitHub control-plane TOCTOU; document the residual administrator race.
- [ ] Do not run live merge tests against this repository or any non-disposable codebase.

### Recommended first implementation slice

**K0.1 through K4.2 are implemented locally.** The K4 primitive and source-only publication
prerequisite have passed independent source review, but both remain unreachable and default-off:
repository search proves no CLI, route, publisher, mission, Goal pack, or host bridge constructs the
executor. K5 remains closed until runnable awaiting-review publication durably persists exact PR
identity through an installed trusted host, live evidence collects every required fact, operator-owned
policy and credential boundaries exist, the disposable rehearsal passes, and a separate
execution-enable decision authorizes K5.2. Do not infer K5 authority from source presence, source
review, or green fixture tests.
