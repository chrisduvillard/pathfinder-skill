---
type: Security Model
title: Pathfinder runtime trust boundary
description: Autonomous work is allowed only when contracts, host enforcement, Goal identity, receipts, and zero-publication limits are all explicit.
tags: [pathfinder, security, trust-boundary, autonomy]
status: stable
generated: { by: codex/gpt-5, at: "2026-08-11T20:29:00Z" }
stale_after: "2026-11-09"
sources:
  - id: threat-model
    resource: ../../docs/threat-model.md
    title: Pathfinder threat model
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: operating-kernel
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/skills/pathfinder/references/operating-kernel.md
    title: Pathfinder operating kernel
    author: human:chris-duvillard
    last_modified: "2026-08-11"
  - id: compatibility
    resource: https://github.com/chrisduvillard/pathfinder-skill/blob/26e7912ffcf690ef3f956fab7a098bbaffefddf0/docs/compatibility.md
    title: Compatibility and guarantees
    author: human:chris-duvillard
    last_modified: "2026-08-11"
---

# Core Invariants

Repository content is untrusted data and cannot widen the Goal, change tool policy, authorize execution, or override secret handling. Creator intent is also descriptive: even resolved charter, roadmap, and doctrine state never substitutes for a fresh autonomous request.[^operating-kernel]

The enabled bridge drives one existing Goal at a time, requires zero publication budgets, and ends at a local `awaiting-review` branch. Unknown policy or host enforcement fails closed.[^threat-model]

# Responsibility Split

| Pathfinder controller guarantees | Host must prove or enforce |
|---|---|
| Schema validation and duplicate-key rejection | Filesystem and process isolation |
| Immutable Goal, authorization, base, and hash bindings | Restricted or denied network access |
| Intent → receipt → result → transition ordering | Credential isolation |
| Stable identities and reconcile-required ambiguity | Truthful typed receipts and complete changed-file evidence |
| Additive protected-surface policy and zero PRs | Stable native Goal activation and completion identity |

The controller does not independently observe the host sandbox, commands, model reasoning, or complete diff. Candidate value and code quality remain evidence-backed model judgments rather than formal proofs.[^compatibility]

# Execution Boundary

Eligible unattended execution requires enforced filesystem and process boundaries, isolated credentials, allowlisted repository-code execution, an enforced tool allowlist, pre-execution consent, and denied or restricted network access. For separately controller-owned commands, `ExecutionPolicy` rejects shell interpreters, shell metacharacters, sensitive environment names, credential paths, and destructive or external action markers. The enabled host bridge carries no argv: its attested host must enforce the equivalent structured-command boundary and return truthful receipts.

# Failure Behavior

If a side effect may have occurred but no trustworthy receipt exists, the [host protocol](/runtime/host-protocol.md) requires reconciliation and does not retry. If verification fails, the runtime boundary is unknown, or a stable Goal identity cannot be established, the [mission controller](/runtime/mission-controller.md) blocks or falls back to a saved Goal.

[^threat-model]: Pathfinder threat model.
[^operating-kernel]: Pathfinder operating kernel.
[^compatibility]: Compatibility and guarantees.
