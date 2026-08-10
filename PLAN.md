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
- [ ] Add a lightweight ShellCheck job or locally reproducible ShellCheck command for all Bash files.
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
- [ ] Add a protected-surface registry that is data-driven, versioned, and overridable only through explicit policy—not repository prose.

### P1 — Add canonical schemas and state

- [x] Add real JSON Schemas for candidates, verification, Goal Binding, runtime boundary, mission state, run log, final summary, charter, roadmap, and doctrine.
- [x] Validate JSON with a real parser before schema checks; reject duplicate keys, unknown enum values, missing required fields, and malformed timestamps.
- [ ] Make JSON the source of truth and render Markdown views from it, eliminating drift between human and machine artifacts.
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
- [ ] For goal packs, activate only one native Goal at a time and persist the queue in mission state.

### P1 — Build the sequential autonomous controller

- [x] Implement a read-only repository capability probe before any mission writes.
- [x] Detect Git root, subproject scope, current branch, base commit, remote type, default branch, dirty state, hooks configuration, and worktree support.
- [x] Define a dirty-tree policy: default to blocking autonomy; optionally allow an explicit committed-base run that ignores uncommitted changes and says so before Goal generation.
- [x] Create mission worktrees through one controller function; verify the resolved path, ownership, base commit, and absence of symlink escapes.
- [x] Neutralize repository hooks for every controller-owned Git command that can trigger them, not just commit and push.
- [x] Avoid `git pull` as an opaque step; fetch, resolve the exact remote base, verify fast-forward ancestry, then create/rebase deterministically.
- [x] Run exactly one goal at a time in v1.
- [ ] Add a real `mission start/next/record/resume` host bridge and at least one non-fake end-to-end mission; the current `MissionOrchestrator` is a library protocol used only by fixture callbacks, not a runnable autonomous entry point.
- [ ] Checkpoint before and after every external command and state transition.
- [ ] On restart, inspect actual Git/Goal/PR state and make the next transition idempotently rather than replaying the last command. *(Lower-level worktree and PR reuse exists, but no production mission bridge invokes reconciliation after an ambiguous callback crash.)*
- [x] Detect and reuse an existing branch/PR for the same attempt; never create duplicate PRs after a timeout.
- [x] Preserve recoverable blocked work without carrying its diff into the next goal.
- [x] Add safe worktree cleanup/status commands; never delete a dirty or unmerged worktree automatically.
- [x] Disable the Opportunity Scout by default in v1; when enabled later, cap derived goals at the run’s initial immutable limit.
- [ ] Enforce fixed maxima for goals, attempts per goal, wall time, tokens/cost when exposed, open PRs, and total PRs—not only open awaiting-review PRs.

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

### P2 — Make Pathfinder substantially faster and easier to use

- [x] Reduce `SKILL.md` to a thin router, trust boundary, and required route-loading rules.
- [x] Move explore, prompt-to-goal, intent-refresh, autonomous, status, and reviewer workflows into separate route references loaded only when needed.
- [ ] Replace hand-copied rule mirrors with canonical schema/config fragments and generated documentation where practical.
- [x] Make prompt-to-goal independent of the full Doctrine Interview; ask only unresolved Goal-contract questions.
- [x] Require the deep creator interview only before explicit autonomous execution or an explicit creator-model refresh.
- [x] Add a fast path for a well-formed prompt: targeted search, proof discovery, one recognition screen, then native Goal activation.
- [x] Start exploration with one repository map and expand scouts only where uncertainty or risk justifies the cost.
- [x] Replace the default five-scout/three-verifier fan-out with an adaptive evidence budget and hard maximum.
- [x] Cache read-only discovery by base commit and scoped path fingerprint; invalidate only affected surfaces.
- [ ] Add monorepo namespaces so charter/roadmap/doctrine can be scoped to a subproject without conflating unrelated products.
- [x] Render a compact status summary from controller state instead of rereading every Markdown artifact.
- [x] Add `--json`/structured status for automation and concise human status for interactive use.
- [ ] Keep artifacts useful but stop creating placeholders for every unused phase; represent lifecycle explicitly in the state snapshot and render placeholders only when a human view needs them. *(The zero-clarification prompt route now omits never-run phases; broader lifecycle rendering remains open.)*
- [ ] Limit default run artifacts to evidence required for resume, audit, and evaluation; make verbose scout prose optional. *(The zero-clarification prompt route is now fixed at six evidence artifacts; optional full-exploration scout prose remains open.)*
- [ ] Add progress updates at meaningful checkpoints rather than per invariant or per file.

### P2 — Build evaluation that measures real behavior

- [x] Replace “JSON-shaped” assertions with parser + schema validation.
- [x] Parse the exact Goal payload and validate outcome, proof, constraints, scope, stop condition, and final evidence contract inside that payload.
- [x] Add negative fixtures where proof/constraints exist only in supporting notes and confirm they fail.
- [x] Add cross-artifact referential checks: candidate IDs, binding IDs, grades, attempts, commands, and final dispositions must agree.
- [x] Add controller unit tests for every allowed and forbidden state transition.
- [ ] Add crash-point tests after worktree creation, command start, verification, commit, push, PR creation, and CI polling.
- [x] Add idempotency tests showing resume does not duplicate commits, branches, or PRs.
- [ ] Add dirty-tree, symlink, malicious filename, hook, credential-helper, and command-injection fixtures. *(All listed concerns except a dedicated malicious-filename fixture are covered.)*
- [ ] Add prompt-injection fixtures covering source files, README/docs, tests, diffs, tool output, intent files, and prior artifacts.
- [ ] Add GitHub API fixtures for branch protection, rulesets, auth failure, rate limit, pending checks, failed checks, merge conflict, and existing PR.
- [x] Add Linux/macOS/Windows controller tests.
- [x] Add recorded replay cases produced by actual Pathfinder runs. *(Sanitized local Claude Code dogfood now guards placeholder churn, ignored-path failure, and pre-approval repository execution; no credentials, private paths, or transcript text are retained.)*
- [x] Add a small optional live-model suite for the highest-value behaviors: question choice, intent preservation, safe routing, native Goal activation, and honest blocking.
- [x] Add a nightly dogfood run against tiny synthetic repositories; never point CI autonomy at arbitrary external repositories.
- [ ] Add plugin install/load smoke tests for Claude Code and Codex when their non-interactive test surfaces are available. *(Manual dogfood now covers an isolated Codex edge install and Claude load/status/prompt-controller runs; a repeatable credential-free Codex model invocation is still unavailable.)*
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

The master checklist above is the completion record. The risk-ordered sub-prompts below are preserved as the original execution specification; their boxes are not a second status tracker. Completed behavior is also recorded in `PROGRESS.md` and must have a deterministic check, replay, or explicit non-guarantee. Open master items are deliberately deferred rather than implied complete. In particular, a real host-to-controller mission bridge, command-level crash journaling, fixed cost/token caps, monorepo intent namespaces, exhaustive provenance-injection and GitHub-ruleset fixtures, a clean post-hardening host replay, and repeatable non-interactive host install tests remain future work.

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

- [ ] `[writes code]` Change only `pathfinder_core/capabilities.py`, `tests/core/test_capabilities.py`, `README.md`, `docs/compatibility.md`, and `docs/operator-guide.md`; stop before touching mission execution.
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

- [ ] `[writes code]` Change only `pathfinder_core/capabilities.py`, `skills/pathfinder/references/routes/autonomous.md`, `README.md`, `docs/compatibility.md`, `docs/operator-guide.md`, `docs/threat-model.md`, and matching focused tests/guards.
- [ ] First present a guarantee-delta plan. Imitate the current fail-closed capability and guarantee-boundary language.
- [ ] Report mission-runner availability only when the host bridge exists and the runtime attestation validates. Document the exact start/next/record/resume flow and retain the explicit Goal-only fallback.
- [ ] Existing tests must pass unmodified in meaning. Show all old “autonomous supported” claims before replacing them.
- [ ] Expected diff: 80–150 lines; split capability enablement from prose if larger.
- [ ] Verify with `bash scripts/check-all.sh .`, exact-archive package smoke, one offline synthetic host-bridge replay, and bounded Codex/Claude dogfood that creates no commit, push, PR, or publication.
- [ ] Append the required result line to `PROGRESS.md`.
- [ ] Stop condition: if either host cannot reliably load the bridge protocol or return typed receipts, keep that host degraded to Goal-only and document the precise limitation.

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
