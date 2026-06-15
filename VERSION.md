# Repo Adjutant Skill Version

Generated: 2026-06-15 15:24:25

Version: 2.1.1

Changes in v2.1.1:
- Added MIT license metadata and repository `LICENSE` file.

Changes in v2.1:
- Hardened prompt-injection and untrusted-repository handling.
- Added explicit secret redaction and artifact hygiene rules.
- Added Claude Code `/goal` version gate: v2.1.139 or newer.
- Added direct `/repo-adjutant` invocation guidance.
- Added exact "Start the full Repo Adjutant process" handling.
- Added repo-root detection, safe work-folder handling, and local ignore guidance.
- Added ranked candidate-goal menu before the question funnel.
- Added fast-path question funnel for agent-recommendation mode.
- Added Implementation Goal fallback alongside `/goal` output.
- Added character-count requirement for generated goal conditions.
- Added guardrails for repo-defined command execution and GitHub/publication side effects.

Changes in v2:
- Added Claude Code `/goal` best-practice rules.
- Added evaluator-aware goal generation.
- Added measurable-end-state requirement.
- Added stated proof/check requirement.
- Added explicit 3900-character budget.
- Added turn/stop-bound requirement.
- Added `goal-best-practices.md` reference.
