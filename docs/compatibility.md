# Pathfinder compatibility and guarantees

Pathfinder can **create a bounded Goal in any readable folder**. Autonomous implementation is deliberately narrower: v1 needs Python 3.11+, a clean Git repository, an enforceable host runtime boundary, and a native/manual Goal handoff. GitHub is optional; without it, a successful mission stops at a verified local branch.

## Compatibility matrix

| Surface | Goal creation | Autonomous v1 | Notes |
|---|---|---|---|
| Codex with native Goals enabled | Supported | Supported when the host supplies enforceable runtime evidence and the Goal backend | Enable `[features] goals = true` or `codex features enable goals`. A missing programmatic backend becomes a manual Goal handoff. |
| Claude Code 2.1.139+ | Supported | Supported when the controller boundary and safe launcher are available | Uses `/goal`; otherwise returns the exact manual command. |
| Older/other agent host | Markdown fallback | Not persistent by default | Receives an `Implementation Goal`; the generic adapter never pretends it is a native Goal. |
| Linux | Supported | CI configured | The required workflow runs all deterministic checks; the first hosted v3 run is pending publication. |
| macOS | Supported | Locally tested + CI configured | Local BSD-tool and package checks pass; the required hosted job is pending publication. |
| Windows Git-Bash/MSYS | Supported | CI configured | The required workflow uses Bash and the Windows Python environment; the first hosted v3 run is pending publication. |
| Non-Git folder | Supported | Goal-only | Discovery and Goal generation work; no branch/commit/PR mission. |
| Clean Git, no remote | Supported | Verified local branch | Publication is unavailable. |
| Git with a non-GitHub remote | Supported | Verified local branch | Other forge adapters are deferred. |
| GitHub remote | Supported | Awaiting-review PR when `gh`, publication-only credentials, and policy are available | Exactly one PR record; no merge method exists in v1. |
| Monorepo | Supported | One explicit scope | Bind the scoped root and exact repository commit; cache keys include both. Separate per-package intent namespaces are deferred. |
| Unknown sandbox/network/credential controls | Supported | Blocked | Pathfinder saves the Goal and reports the missing enforcement. |

## Guarantee boundary

Pathfinder core mechanically enforces schema validation, duplicate-key rejection, immutable authorization/base bindings, closed state transitions, atomic state/event writes, one active lease, structured command execution, working-directory containment, credential/path deny rules, hook-neutralized controller Git, conservative worktree cleanup, a one-Goal authorization shape, idempotent PR lookup, and no self-merge operation.

Transition-level resume is tested. A process crash after an external side effect but before its next state checkpoint still depends on the callback reconciling real Git/forge state; command-boundary journaling is a documented remaining hardening item.

The host/runtime must prove filesystem and process isolation, network policy, credential isolation, native Goal lifecycle access, and publication credentials. Repository understanding, candidate value, code quality, and verifier judgment remain model behavior backed by evidence and replays—not formal proofs. `unknown` host enforcement blocks unattended execution.

Stable installs use immutable release tags. Repository `main` is the edge channel and may change between commits.
