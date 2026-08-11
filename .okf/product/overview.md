---
type: Product Overview
title: Pathfinder overview
description: Pathfinder maps unfamiliar repositories and turns selected work into bounded, evidence-bearing Goals.
tags: [pathfinder, product, goals]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: readme
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/README.md
    title: Pathfinder README
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: codex-manifest
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/.codex-plugin/plugin.json
    title: Codex plugin manifest
    author: human:chris-duvillard
    last_modified: "2026-08-10"
  - id: pathfinder-skill
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/SKILL.md
    title: Pathfinder skill instructions
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Purpose

Pathfinder combines an agent skill with a deterministic controller. It maps an unfamiliar repository, ranks useful next moves, asks only questions that affect the outcome, and forges a bounded Goal with explicit proof and stop conditions.[^readme]

The Codex plugin manifest identifies the packaged product as `pathfinder` version `3.0.0`, with repository discovery, Goal generation, and guarded autonomous preparation as its public surface.[^codex-manifest]

# Product Boundary

Pathfinder is primarily a Goal-authoring and local-control system. Its enabled autonomous bridge is conditional on host attestation, a stable native Goal identity, and truthful typed receipts; otherwise it stops at a saved Goal or manual handoff. The bridge ends on a local branch in `awaiting-review` and does not publish or self-merge.[^readme]

# Major Components

| Component | Responsibility |
|---|---|
| Agent skill | Chooses a [user route](/product/user-routes.md), explores source, and assembles a [bounded Goal](/product/goal-contract.md). |
| Controller | Drives the [local mission state machine](/runtime/mission-controller.md). |
| Host protocol | Exchanges one typed [action and receipt](/runtime/host-protocol.md) at a time. |
| Goal adapters | Select native or manual [host Goal integration](/runtime/goal-adapters.md). |
| Artifact layer | Writes schema-validated [run evidence](/runtime/artifact-contracts.md). |
| Safety layer | Enforces the [trust boundary](/safety/trust-boundary.md) and [protected surfaces](/safety/protected-surfaces.md). |

[^readme]: Pathfinder README.
[^codex-manifest]: Codex plugin manifest.
[^pathfinder-skill]: Pathfinder skill instructions.
