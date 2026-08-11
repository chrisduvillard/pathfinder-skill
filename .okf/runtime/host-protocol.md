---
type: API Contract
title: Host action protocol
description: The protocol binds one action request to one typed receipt using stable mission identities and contract hashes.
resource: ../../pathfinder_core/host_protocol.py
tags: [pathfinder, host, protocol, receipts]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: host-protocol
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/host_protocol.py
    title: Host protocol source
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: operator-guide
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/docs/operator-guide.md
    title: Pathfinder operator guide
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Actions

The protocol defines `prepare-worktree`, `activate-goal`, `implement`, `verify`, `commit`, `complete-goal`, and `publish`. The enabled [mission controller](/runtime/mission-controller.md) uses the first six and has no publication step.[^host-protocol]

# Request Binding

Each request is schema-validated and must match trusted values supplied by the controller:

| Field family | Bound values |
|---|---|
| Identity | `action_id`, `operation_id`, `mission_id`, `attempt_id` |
| Operation | `action_kind`, request context, requested time |
| Integrity | `request_sha256`, `authorization_snapshot_sha256`, `runtime_boundary_sha256` |

The completion action must carry the stable native Goal id established by activation.[^host-protocol]

# Receipt Contract

A receipt repeats the bound request fields, adds an outcome, structured evidence, and completion time, and must match the exact action. Outcomes are `succeeded`, `failed`, `manual-handoff`, `not-observed`, and `reconcile-required`. Ambiguous reconciliation and manual handoff require matching evidence codes; successful Goal activation and completion require a non-empty stable id.[^host-protocol]

# Trust Meaning

The protocol proves consistency between the controller's sealed contracts and the host's typed report. It does not independently observe the host sandbox, command execution, filesystem, model reasoning, or complete diff; those remain part of the [runtime trust boundary](/safety/trust-boundary.md).[^operator-guide]

[^host-protocol]: Host protocol source.
[^operator-guide]: Pathfinder operator guide.
