# Pathfinder compatibility and guarantees

Pathfinder can **create a bounded Goal in any readable folder**. It also exposes a local host-driven start/next/record/resume protocol that journals each action before execution and each typed receipt before state advancement. This protocol is not blanket host support: without trustworthy runtime attestation, a stable native Goal identity, and truthful receipts, the active host must degrade to a saved Goal/manual handoff. Publication is not enabled.

## Compatibility matrix

| Surface | Goal creation | Autonomous v1 | Notes |
|---|---|---|---|
| Codex with native Goals enabled | Supported | Goal-only by default; local protocol conditional | The current dogfood proved typed manual handoff with zero side effects, not native Goal execution. Require an active stable Goal API and attested receipts before running. |
| Claude Code 2.1.139+ | Supported | Goal-only by default; local protocol unverified | Returns the exact `/goal` command. No Claude host was launched during bridge verification, so do not claim typed lifecycle support. |
| Older/other agent host | Markdown fallback | Not persistent by default | Receives an `Implementation Goal`; the generic adapter never pretends it is a native Goal. |
| Linux | Supported | Protocol checks pass in CI | Actual execution remains host-attestation dependent. |
| macOS | Supported | Protocol checks pass locally and in CI | Actual execution remains host-attestation dependent. |
| Windows Git-Bash/MSYS | Supported | Protocol checks pass in CI | Actual execution remains host-attestation dependent. |
| Non-Git folder | Supported | Goal-only | Discovery and Goal generation work; no branch/commit/PR mission. |
| Clean Git, no remote | Supported | Local protocol when host-attested | Ends at a committed local awaiting-review branch. |
| Git with a non-GitHub remote | Supported | Same local protocol | Other forge adapters are deferred. |
| GitHub remote | Supported | Same local protocol; no publication | Push, PR, CI polling, and merge are disabled in the bridge. |
| Monorepo | Supported | One explicit scope | Bind the scoped root and exact repository commit; cache keys include both. Separate per-package intent namespaces are deferred. |
| Unknown sandbox/network/credential controls | Supported | Blocked | Pathfinder saves the Goal and reports the missing enforcement. |

## Guarantee boundary

Pathfinder's local bridge mechanically enforces schema validation, duplicate-key rejection, immutable authorization/base/hash bindings, a versioned protected-surface registry with additive-only explicit policy, closed state transitions, atomic state/event/operation writes, one action at a time, receipt-before-result-before-transition ordering, reconcile-required ambiguity, one Goal, zero PRs, and no self-merge operation. Separate controller components provide structured command policy, working-directory containment, credential/path denies, hook-neutralized Git, conservative worktree cleanup, and idempotent PR lookup; the host-driven bridge does not claim it independently observes the host sandbox, commands, complete diff, or model reasoning.

Intent, host-receipt, terminal-result, and transition crash boundaries are tested for all five local action families. A lost side-effect response without a trustworthy receipt remains `reconcile-required`; it is never assumed retry-safe. Authorization limits cannot widen the Goal Binding; the persisted wall deadline survives restart and blocks new actions when exhausted. Token/cost accounting remains a host capability/non-guarantee because the typed protocol does not expose it. Publication primitives have persistent fixture coverage, but publication is not composed into the enabled bridge.

The host/runtime must prove filesystem and process isolation, network policy, credential isolation, and native Goal lifecycle access. The local bridge must have no publication credential. Repository understanding, candidate value, code quality, and verifier judgment remain model behavior backed by evidence and replays—not formal proofs. `unknown` host enforcement blocks unattended execution.

Stable installs use immutable release tags. Repository `main` is the edge channel and may change between commits.
