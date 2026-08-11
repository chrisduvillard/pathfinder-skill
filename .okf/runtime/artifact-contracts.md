---
type: Data Contract
title: Pathfinder artifact contracts
description: Human-readable Markdown views are paired with schema-validated JSON sidecars for replay, evaluation, and safe resumption.
resource: ../../pathfinder_core/artifacts.py
tags: [pathfinder, artifacts, schemas, replay]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:01:42Z" }
stale_after: "2026-11-09"
sources:
  - id: artifact-reference
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/references/artifact-structure.md
    title: Artifact structure reference
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: artifact-source
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/pathfinder_core/artifacts.py
    title: Artifact writer source
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: readme
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/README.md
    title: Pathfinder README
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Artifact Families

Work-producing routes create only artifacts for phases that actually ran. Markdown is the human view; JSON sidecars carry stable contracts for evaluation, replay, and search.[^artifact-reference]

| Phase | Human artifact | Structured artifact |
|---|---|---|
| Discovery | `01-blind-discovery.md` | — |
| Candidate synthesis | `03-synthesis.md` | `03-candidates.json` |
| Verification | `03b-verification.md` | `03b-verification.json` |
| Goal | `06-goal-command.md` | `06-goal-binding.json` |
| Execution | `07-run-log.md` | `07-run-log.json` |
| Final ledger | `08-final-summary.md` | `08-final-summary.json` |

Optional scout briefs, question/answer artifacts, and cross-model review are added only when those phases occur.[^readme]

# Saved Prompt Goal

The prompt-goal writer accepts a schema-valid request inside a confirmed ignored Pathfinder run directory, verifies the exact Git base and scope, derives stable mission/Goal/binding ids from the request, and writes four final artifacts: the Goal Markdown, Goal Binding JSON, final-summary Markdown, and final-summary JSON. Existing different artifacts are never overwritten; completed artifacts are sealed read-only.[^artifact-source]

# Mission Views

For autonomous missions, controller-owned state and operation receipts are authoritative. `artifacts mission-view` deterministically renders the run log and final summary; operators must not hand-author those views or treat Markdown as mission state.[^artifact-reference]

The [bounded Goal contract](/product/goal-contract.md) defines the proof fields, and the [mission controller](/runtime/mission-controller.md) defines when execution artifacts advance.

[^artifact-reference]: Artifact structure reference.
[^artifact-source]: Artifact writer source.
[^readme]: Pathfinder README.
