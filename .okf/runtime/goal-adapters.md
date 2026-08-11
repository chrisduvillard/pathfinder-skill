---
type: Integration Map
title: Goal adapters
description: Goal adapters expose native lifecycle operations when the host can support them and explicit manual fallbacks when it cannot.
tags: [pathfinder, codex, claude, integration]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: compatibility
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/docs/compatibility.md
    title: Compatibility and guarantees
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: codex-adapter
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/adapters/codex.py
    title: Codex Goal adapter source
    author: human:chris-duvillard
    last_modified: "2026-08-10"
  - id: claude-adapter
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/adapters/claude.py
    title: Claude Goal adapter source
    author: human:chris-duvillard
    last_modified: "2026-08-10"
  - id: generic-adapter
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/adapters/generic.py
    title: Generic Goal adapter source
    author: human:chris-duvillard
    last_modified: "2026-08-10"
---

# Adapter Behavior

| Host | Native behavior | Fallback |
|---|---|---|
| Codex | With a native backend, inspect, create, observe, complete, and block a stable Goal. Reuse an identical active Goal and reject a conflicting unfinished Goal. | Emit `/goal <objective>` and require manual lifecycle controls. |
| Claude | Launch `/goal <objective>` only when a launcher is supplied. | Return the exact `/goal` command and manual inspection guidance. |
| Generic | No native lifecycle is claimed. | Return a non-persistent Implementation Goal that explicitly continues across checkpoints. |

Codex completion requires controller-validated evidence, and marking a Codex Goal blocked requires three consecutive blocked turns.[^codex-adapter] Claude's adapter deliberately advertises manual inspect, observe, complete, and block capabilities even when it can launch goal creation.[^claude-adapter]

# Compatibility Boundary

Goal creation works in readable folders, but autonomous execution depends on a host that can prove runtime enforcement, expose a stable native Goal lifecycle, and return truthful typed receipts. Without those capabilities Pathfinder saves the [bounded Goal](/product/goal-contract.md) and hands control back to the user.[^compatibility]

See the [host action protocol](/runtime/host-protocol.md) for the receipt contract.

[^compatibility]: Compatibility and guarantees.
[^codex-adapter]: Codex Goal adapter source.
[^claude-adapter]: Claude Goal adapter source.
[^generic-adapter]: Generic Goal adapter source.
