---
type: User Workflow
title: Pathfinder user routes
description: The entry routes separate repository exploration, prompt-based Goal creation, guarded autonomy, creator-model refresh, and status inspection.
tags: [pathfinder, workflow, authority]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: pathfinder-skill
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/SKILL.md
    title: Pathfinder skill instructions
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: readme
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/README.md
    title: Pathfinder README
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Entry Routes

Bare invocation presents a chooser. The selected route determines what may be inspected, written, or executed; persistent intent can improve recommendations but never authorizes work.[^pathfinder-skill]

| Route | Intended use | Authority and output |
|---|---|---|
| Explore | The repository is unfamiliar and the next move is unknown. | Source-first discovery, ranked candidates, focused questions, then a saved Goal. |
| Prompt-to-goal | The user already has a concrete task. | Targeted research and the same bounded Goal contract; clarification only when required. |
| Autonomous | The user explicitly asks to drive work. | A fresh, guarded request for one Goal or an explicitly approved sequential pack; degrades to Goal-only when host gates fail. |
| Refresh creator model | Charter, roadmap, or doctrine is missing, stale, or contradicted. | Creator-confirmed local intent documents; intent remains descriptive rather than executable authority. |
| Status/help | The user wants current local state and available paths. | Read-only inspection; no run artifacts, creator interview, or repository code execution. |

# Exploration Route

Full exploration proceeds through discovery, domain scouting, synthesis, adversarial verification, a question funnel, and Goal forging. The first discovery pass intentionally reads code, tests, manifests, schemas, and runtime entry points before documentation.[^readme]

# Autonomous Route

Autonomy is an explicit opt-in on every run. It requires the [runtime controller](/runtime/mission-controller.md), an enforceable [trust boundary](/safety/trust-boundary.md), and a stable Goal lifecycle through a [host adapter](/runtime/goal-adapters.md). Unknown or missing enforcement stops rather than silently weakening the route.

[^pathfinder-skill]: Pathfinder skill instructions.
[^readme]: Pathfinder README.
