# Pathfinder Skill Version

Generated: 2026-06-15 21:46:31 CEST

Version: 2.4.0

Changes in v2.4.0:
- Added Codex plugin support with `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
- Added `codex plugin marketplace add chrisduvillard/pathfinder-skill` installation instructions.
- Aligned Claude and Codex plugin manifest versions.

Changes in v2.3.0:
- Added Claude Code plugin marketplace support with `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
- Added `/plugin marketplace add chrisduvillard/pathfinder-skill` installation instructions.
- Documented namespaced plugin invocation: `/pathfinder:pathfinder`.

Changes in v2.2.0:
- Renamed the skill from Repo Adjutant to Pathfinder.
- Renamed the command from `/repo-adjutant` to `/pathfinder`.
- Updated install paths, artifact paths, docs, and invocation examples.
- Added the tagline: "Map the codebase. Pick the path. Forge the goal."

Changes in v2.1.1:
- Added MIT license metadata and repository `LICENSE` file.

Changes in v2.1:
- Hardened prompt-injection and untrusted-repository handling.
- Added explicit secret redaction and artifact hygiene rules.
- Added Claude Code `/goal` version gate: v2.1.139 or newer.
- Added direct `/pathfinder` invocation guidance.
- Added exact "Start the full Pathfinder process" handling.
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
