# Pathfinder compatibility and guarantees

Pathfinder can **create a bounded Goal in any readable folder**. The current release includes controller schemas, state machinery, adapters, and policy checks, but it does not expose a production host bridge that starts and drives a mission. Consequently every autonomous request currently degrades to a saved Goal. The execution outcomes below remain the fail-closed target contract for that future bridge.

## Compatibility matrix

| Surface | Goal creation | Autonomous v1 | Notes |
|---|---|---|---|
| Codex with native Goals enabled | Supported | Goal-only; mission bridge pending | A saved Goal may be activated manually; native Goal availability is not a programmatic Pathfinder mission backend. |
| Claude Code 2.1.139+ | Supported | Goal-only; mission bridge pending | Returns the exact `/goal` command; the controller does not drive its lifecycle yet. |
| Older/other agent host | Markdown fallback | Not persistent by default | Receives an `Implementation Goal`; the generic adapter never pretends it is a native Goal. |
| Linux | Supported | Controller checks pass in CI | Mission execution remains unavailable. |
| macOS | Supported | Controller checks pass locally and in CI | Mission execution remains unavailable. |
| Windows Git-Bash/MSYS | Supported | Controller checks pass in CI | Mission execution remains unavailable. |
| Non-Git folder | Supported | Goal-only | Discovery and Goal generation work; no branch/commit/PR mission. |
| Clean Git, no remote | Supported | Goal-only | Verified-local-branch execution is a future bridge outcome. |
| Git with a non-GitHub remote | Supported | Goal-only | Other forge adapters are deferred. |
| GitHub remote | Supported | Goal-only | Awaiting-review publication is a future bridge outcome; no merge method exists. |
| Monorepo | Supported | One explicit scope | Bind the scoped root and exact repository commit; cache keys include both. Separate per-package intent namespaces are deferred. |
| Unknown sandbox/network/credential controls | Supported | Blocked | Pathfinder saves the Goal and reports the missing enforcement. |

## Guarantee boundary

Pathfinder core components mechanically enforce schema validation, duplicate-key rejection, immutable authorization/base bindings, closed state transitions, atomic state/event writes, one active lease, structured command execution, working-directory containment, credential/path deny rules, hook-neutralized controller Git, conservative worktree cleanup, a one-Goal authorization shape, idempotent PR lookup, and no self-merge operation. Those components are not yet composed behind a callable production mission entry point.

Transition-level resume is tested. A process crash after an external side effect but before its next state checkpoint still depends on the callback reconciling real Git/forge state; command-boundary journaling is a documented remaining hardening item.

The host/runtime must prove filesystem and process isolation, network policy, credential isolation, native Goal lifecycle access, and publication credentials. Repository understanding, candidate value, code quality, and verifier judgment remain model behavior backed by evidence and replays—not formal proofs. `unknown` host enforcement blocks unattended execution.

Stable installs use immutable release tags. Repository `main` is the edge channel and may change between commits.
