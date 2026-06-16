# Pathfinder Skill Version

Generated: 2026-06-16

Version: 2.7.0

Changes in v2.7.0:
- Restructured packaging to the conventional `skills/pathfinder/` layout (SKILL.md and references moved under it) so the skill is found by standard plugin skills auto-discovery; the plugin/marketplace manifests stay at the repo root.
- Fixed the Phase 5 question funnel so the examples match the universal rules: every work-selection question now demonstrates its escapes (`None of these`, plus `Go back` from L1 onward), and `Agent recommends:` is defined as a pointer line to one listed option rather than a duplicate numbered option. Applied in both `SKILL.md` and `references/question-funnel-template.md`.
- Corrected the documented Codex invocation from `@pathfinder` to `$pathfinder` (or `/skills`), per OpenAI Codex Agent Skills.
- Completed the README artifact list to the full nine-file contract.
- Moved the Claude marketplace `description` to the documented top-level field.

Changes in v2.6.0:
- Deepened Phase 2 scouts: every finding must now be located (file path plus symbol/route), evidence-backed, symptom-level, evidence-graded (confirmed/inferred/suspected), and carry a measurable candidate end state, verification command, and blast radius.
- Added a quality bar that rejects unlocated or ungrounded findings.
- Phase 1 blind discovery now produces a concrete seed inventory (stack, entry points, surface list, commands) for the scouts.
- Phase 4 synthesis now derives the Top 5 candidates and the L2/L3 surface index from scout finding ids, with dedup, evidence-grade-aware ranking, and a per-candidate goal-readiness signal.
- Rewrote the scout-brief template to the new per-finding structure.

Changes in v2.5.0:
- Reworked the Phase 5 question funnel into two user-selectable interview modes.
- Express mode preserves the original compact single-shot question.
- Deep dive mode adds a conditioned drill-down: intent (L0), domain (L1), surface (L2), exact target (L3), boundaries (L4), then execution mode, capped at five levels.
- Deep dive options are generated from the scout briefs, with a live narrowing trail, a goal-readiness confidence signal, adaptive stopping, an always-present agent recommendation, and escape/go-back options at every level.
- Phase 4 synthesis now emits a per-domain surface index and scout ownership to feed the drill-down.
- Artifacts record the chosen mode and the full narrowing path.

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
