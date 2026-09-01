# Pathfinder compatibility and guarantees

Pathfinder can **create a bounded Goal in any readable folder**. It also exposes a local host-driven start/next/record/resume protocol and a persisted sequential pack wrapper. Each child journals its action before execution and typed receipt before state advancement; a pack hashes the fixed ordered bindings and permits exactly one active native Goal. This is not blanket host support: without trustworthy runtime attestation, stable native Goal activation and completion identities, and truthful receipts, the active host must degrade to a saved Goal/manual handoff. Publication is not enabled.

## Compatibility matrix

| Surface | Goal creation | Autonomous v1 | Notes |
|---|---|---|---|
| Codex with native Goals enabled | Supported | Goal-only by default; local protocol conditional | The current dogfood proved typed manual handoff with zero side effects, not native Goal execution. Require an active stable Goal API and attested receipts before running. |
| Claude Code 2.1.139+ | Supported | Goal-only by default; local protocol unverified | Returns the exact `/goal` command. No Claude host was launched during bridge verification, so do not claim typed lifecycle support. |
| Older/other agent host | Markdown fallback | Not persistent by default | Receives an `Implementation Goal`; the generic adapter never pretends it is a native Goal. |
| Linux | Supported | Protocol checks pass in CI | Actual execution remains host-attestation dependent. |
| macOS | Supported | Protocol checks pass locally and in CI | Actual execution remains host-attestation dependent. |
| Windows Git-Bash/MSYS | Supported | Protocol checks pass in CI | Actual execution remains host-attestation dependent. |
| Non-Git folder | Supported | Goal-only | Discovery and Goal generation work. On POSIX, canonical artifacts require an explicit owner-only work root outside the source folder; other platforms fail that write closed. No branch/commit/PR mission. |
| Clean Git, no remote | Supported | Local protocol when host-attested | Ends at a committed local awaiting-review branch. |
| Git with a non-GitHub remote | Supported | Same local protocol | Other forge adapters are deferred. |
| GitHub remote | Supported | Same local protocol; no publication | Push, PR, CI polling, and merge are disabled in the bridge. |
| Monorepo | Supported | One explicit scope | Bind the scoped root and exact repository commit; cache keys include both. Root and subproject creator models use isolated intent namespaces with no fallback or inheritance. |
| Unknown sandbox/network/credential controls | Supported | Blocked | Pathfinder saves the Goal and reports the missing enforcement. |

## Guarantee boundary

Pathfinder's local bridge mechanically enforces schema validation, duplicate-key rejection, immutable authorization/base/hash bindings, a versioned protected-surface registry with additive-only explicit policy, closed child transitions, atomic queue/state/event/operation writes, one action and one native Goal at a time, receipt-before-result-before-transition ordering, reconcile-required ambiguity, zero PRs, and no self-merge operation. Pack authorization fixes membership and order by canonical binding hash; any child blocker stops later activation. Separate controller components provide structured command policy, working-directory containment, credential/path denies, hook-neutralized Git, conservative worktree cleanup, and idempotent PR lookup; the host-driven bridge does not claim it independently observes the host sandbox, commands, complete diff, or model reasoning.

Intent, host-receipt, terminal-result, and transition crash boundaries are tested for all six local action families, including native Goal completion. Mission status is observation-only; interrupted transition repair is explicit and locked, and transition events are payload-, state-, identity-, sequence-, and chain-validated before recovery. Queue checkpoint crashes are retried without starting the next child. A lost side-effect response without a trustworthy receipt remains `reconcile-required`; it is never assumed retry-safe. Authorization limits cannot widen a Goal Binding; persisted mission and pack deadlines survive restart and block new actions when exhausted. Token/cost accounting remains a host capability/non-guarantee because the typed protocol does not expose it. Publication primitives have persistent fixture coverage, but publication is not composed into the enabled bridge.

The host/runtime must prove filesystem and process isolation, network policy, credential isolation, and native Goal lifecycle access. The local bridge must have no publication credential. Repository understanding, candidate value, code quality, and verifier judgment remain model behavior backed by evidence and replays—not formal proofs. `unknown` host enforcement blocks unattended execution.

Stable installs use versioned release tags that project policy forbids rewriting. Repository `main` is the edge channel and may change between commits.

Before writing a saved Goal, use `repository inspect` to obtain the controller-derived repository
identity and scope fingerprint. Dirty Git defaults to `block`; `--committed-base` is an explicit
choice that binds the Goal to `HEAD`, requires the separate save acknowledgement, and excludes while preserving uncommitted files. Non-Git scope
uses no fabricated commit and cannot be passed to `mission start` or a Goal pack.

## Credential-free host installation smoke

`scripts/check-host-installs.sh` builds an isolated local marketplace from the
exact supplied tree and never invokes a model or reads host authentication.
Codex must install and enable the plugin, expose the namespaced
`pathfinder:pathfinder` skill and its installed `SKILL.md` in model-visible
prompt JSON, and discover a separate repository-scoped manual skill from
`.agents/skills`. Claude Code must strictly validate the local marketplace,
install and enable the plugin, and parse exactly one Pathfinder skill in its
component inventory. CI installs pinned host CLI versions before running this
probe. These checks prove packaging and discovery, not model behavior, native
Goal execution, runtime attestation, or autonomy.
