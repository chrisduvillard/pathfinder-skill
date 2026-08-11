---
type: Operational Contract
title: Bounded Goal contract
description: A Pathfinder Goal is a measurable completion condition with explicit scope, proof, safety constraints, reporting fields, and a stop bound.
tags: [pathfinder, goal, verification, contract]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: goal-contract
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/references/routes/goal-contract.md
    title: Goal contract reference
    author: human:chris-duvillard
    last_modified: "2026-08-10"
  - id: pathfinder-skill
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/SKILL.md
    title: Pathfinder skill instructions
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: artifacts
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/references/artifact-structure.md
    title: Artifact structure reference
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Contract Shape

A generated Goal describes one measurable end state and includes the scope, concrete proof commands or proof-discovery rule, constraints and non-goals, protected areas, runtime assumptions, iterative checkpoint behavior, and a bounded stop condition.[^goal-contract]

The Claude `/goal` form must stay below 3,900 characters, excluding the `/goal ` prefix. Other hosts use their capability profile or receive an equivalent non-persistent Implementation Goal.[^pathfinder-skill]

# Required Transcript Proof

The implementation agent must surface these fields so completion can be evaluated without an independent filesystem pass:[^goal-contract]

| Field | Purpose |
|---|---|
| `changed_files` | Exact implementation scope. |
| `checks_run_with_exit_results` | Commands and outcomes used as proof. |
| `criteria_satisfied` | Mapping from work to acceptance criteria. |
| `scope_deviations` | Any departure from the saved binding. |
| `protected_area_status` | Whether protected surfaces were touched and covered. |
| `runtime_boundary_observed` | Actual execution boundary. |
| `complexity_notes` | Justification for necessary complexity. |
| `remaining_risks` | Known residual uncertainty. |
| `next_input_needed_if_blocked` | Smallest input needed to resume. |

# Binding

The saved Goal is accompanied by a machine-readable Goal Binding. Later run logs and summaries compare evidence to that binding and record `matched`, `missing`, `stale-objective`, `mismatched`, or `not-run`.[^artifacts]

See [artifact contracts](/runtime/artifact-contracts.md) for the durable files and [mission controller](/runtime/mission-controller.md) for execution.

[^goal-contract]: Goal contract reference.
[^pathfinder-skill]: Pathfinder skill instructions.
[^artifacts]: Artifact structure reference.
