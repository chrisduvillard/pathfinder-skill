---
type: Runtime Component
title: Local mission controller
description: The host-driven controller advances one authorized Goal through worktree preparation, activation, implementation, verification, commit, completion, and local review.
resource: ../../pathfinder_core/mission_host.py
tags: [pathfinder, controller, state-machine, local]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: mission-host
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/mission_host.py
    title: Host mission controller source
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: mission-state
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/state.py
    title: Mission state transition source
    author: human:chris-duvillard
    last_modified: "2026-08-10"
  - id: operator-guide
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/docs/operator-guide.md
    title: Pathfinder operator guide
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Lifecycle

Mission start validates and seals the Goal Binding, authorization snapshot, runtime boundary, and effective protected-surface policy. It fixes mission identity to the Goal, base commit, and a deterministic attempt id, then moves `planned` to `authorized`.[^mission-host]

| Current state | Required host action | Success state |
|---|---|---|
| `authorized` | `prepare-worktree` | `prepared` |
| `prepared` | `activate-goal` | `running` |
| `running` | `implement` | `verifying` |
| `verifying` | `verify` | `verified` |
| `verified` | `commit` | `committed` |
| `committed` | `complete-goal` | `awaiting-review` |

Failed or non-observed actions terminate the mission as `blocked`. `abandoned` is also terminal. The enabled bridge does not issue a publication action and ends on a local awaiting-review branch.[^operator-guide]

# Checkpoint Ordering

For each step, `next` journals an immutable operation intent before returning the [typed host action](/runtime/host-protocol.md). `record` validates and persists the receipt, records the operation result, and only then advances mission state. If an intent exists without a trustworthy receipt, the controller returns `reconcile-required` instead of replaying the side effect.[^mission-host]

# Budgets and Protected Changes

The wall deadline is derived from the original persisted creation time and the narrower of the Goal Binding and authorization limits, so restart cannot extend it. Successful receipts are rejected after the deadline. Receipt `changed_files` are classified against the [protected-surface registry](/safety/protected-surfaces.md); an undeclared protected category blocks advancement.[^mission-host]

# Operator Interface

The command surface provides `mission start`, `next`, `record`, `resume`, `status`, and `abandon`, plus a sequential pack wrapper. Packs activate one child Goal at a time and stop the entire queue on a blocker.[^operator-guide]

[^mission-host]: Host mission controller source.
[^mission-state]: Mission state transition source.
[^operator-guide]: Pathfinder operator guide.
