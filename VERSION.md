# Pathfinder Skill Version

Generated: 2026-06-18

Version: 2.10.0

## Versioning & distribution

The version above is the single source of truth. It is mirrored into
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, and CI enforces
that all three match. The two `marketplace.json` files intentionally carry **no**
version: Claude Code resolves a plugin's version from `plugin.json` first, so
declaring it in a marketplace entry as well would let a stale manifest silently
mask it (per the official plugin-marketplaces docs). CI fails if either
marketplace file adds a version. The Codex marketplace pins `source.ref: main`
deliberately — a rolling release in which each commit on `main` is the new
version.

Changes in v2.10.0:
- Made Pick a move bulk selection first-class: `all`, `a`, `1-5`, and `1,2,3,4,5` now select all Top moves, while partial multi-select such as `1,3,5` opens a selected-moves grouping review.
- Expanded Top move cards to show plain outcome, exact location, evidence grade and basis, likely fix shape, proof/checks, protected-area risk, and grouping hints without requiring users to inspect hidden synthesis artifacts.
- Added Phase 4 derived grouping notes for the Top 5 using only existing candidate data: shared files/surfaces, scout domain, verification commands, blast radius, protected areas, and goal-readiness.
- Extended Phase 6 so multiple selected/grouped moves save a numbered goal pack in `06-goal-command.md`, with each group carrying its own `/goal`, Implementation Goal fallback, character count, selected candidate ids, and grouping rationale.
- Updated execution wording so goal packs are saved first by default and run one goal at a time unless the user explicitly asks to run all goals in the pack.
- Extended markdown drift checks for `goal pack`, `grouping review`, and `select all` terminology across `SKILL.md` and `references/question-funnel-template.md`.

Changes in v2.9.4:
- Documented and CI-enforced the versioning/distribution model (BD-3): the two `marketplace.json` files must not declare a version (`plugin.json` is the single source Claude Code resolves first; a duplicate would silently mask it), and the Codex marketplace's `ref: main` is a deliberate rolling-release pin. A new `manifests.yml` step fails if either marketplace file adds a version.
- Extended `scripts/check-skill-consistency.sh` with a markdown fence-balance check (TR-6): every skill markdown file (`SKILL.md` + `references/*.md`) must close every code fence (triple-backtick block) it opens, so an unterminated funnel/goal screen fails CI instead of shipping a broken render. (Reference-path existence was already guarded since v2.9.2.)

Changes in v2.9.3:
- Closed the Phase 4 candidate data-contract provenance gaps: every candidate field now either copies a named scout finding field or is explicitly derived, with the three synthesis-only fields (`impact`, `risk`, `confidence`) given documented derivation rules. Added an intent tally as the named source for the L0 screen's candidate/confirmed counts, named the L0 intent buckets as the consumer of the finding `type`, and disambiguated candidate `confidence` (from `evidence_grade`) from `goal-readiness` so the two are never collapsed.
- Added release-hygiene CI guards to `.github/workflows/manifests.yml`: the build now fails when VERSION.md has more than one `Version:` line or lacks a `Changes in v<declared>:` changelog heading for the version it declares.
- Extended `scripts/check-skill-consistency.sh` to assert the artifact-file contract (the `NN-*.md` and `*-scout.md` set) matches between `SKILL.md` and `references/artifact-structure.md`, folding the triplicated artifact list into the existing drift-guard.
- Spec-hygiene nits: Phase 2 now maps each scout to its brief filename (documenting the `dx-` abbreviation); Phase 3 no longer instructs writing `03-synthesis.md` before Phase 4 creates it; the work-folder ignore guidance checks "already ignored" before adding a redundant local exclude; the Phase 6 confirmation screen now requires sanitizing every mirrored repo-derived line.
- Added `.gitattributes` enforcing LF for `*.sh`/`*.yml` (with `* text=auto`) so the Linux-CI guard scripts are guaranteed LF regardless of the committer's platform, instead of relying on autocrlf behavior.

Changes in v2.9.2:
- Made the untrusted-data clause mandatory in the generated `/goal`: it is now a required-content item and a slot in the `/goal` shape (was conditional "when relevant" and absent from the required-content list), and it appears in every Good example. Mirrored across `SKILL.md` Phase 6 and `references/goal-best-practices.md` (template, checklist, examples), now aligned on one mandatory-clause set.
- Added the missing `/goal` shape slots the required-content list mandates: the user's chosen direction, non-goals, and a success-path final-report line.
- Fixed the Phase 5 funnel self-conformance: the L4 Boundaries screen now carries the mandated `None of these` free-text escape (it was the only L0–L4 screen missing it), and the escape grammar is unified across all work-selection screens (L3 single-confirm and the Pick a move card no longer use ad-hoc wording). Synced the mode-selection reply line and wired reservoir D into L2. Mirrored in `references/question-funnel-template.md`.
- Added a CI drift-guard (`scripts/check-skill-consistency.sh`, run from `.github/workflows/manifests.yml`) that fails when `SKILL.md` and its reference templates diverge on shared invariants (execution-mode default, five-level cap, escape grammar, lateral moves, glyph legend, 3900-char budget, the v2.1.139 gate, the untrusted-data clause) or when a `references/*.md` path `SKILL.md` cites is missing — closing the unguarded drift class the entries below recur on.

Changes in v2.9.1:
- Fixed the Phase 5 L3 Target single-confirm screen to obey the skill's own universal rules: it now carries the mandatory `Agent recommends:` line and a one-line evidence basis, matching the multi-option variant (both were missing on the common high-confidence path). Mirrored in `references/question-funnel-template.md`.
- Closed a Phase 5 Mode 2 spec/example gap: added an explicit note that the narrowing-trail + `Goal-readiness confidence` header is rendered before every level (L0–L4); the per-level example screens omit it only for brevity. Adaptive stopping depends on that signal. Mirrored in the template.
- Carried the finding `type` (defect/risk/opportunity/smell) into the Phase 4 candidate field list so the Phase 5 funnel's intent annotations have an explicit upstream source (data-contract fix). Scoped to the schema field only; no L1 filtering rule added.

Changes in v2.9.0:
- Gave `show the full map` its own concrete browse screen: a Full surface map that lists every discovered surface grouped by scout domain, with evidence glyphs and finding counts, built from the per-domain surface index already in `03-synthesis.md` (no scout/synthesis change). Picking a surface jumps to the Target step (L3), or auto-confirms to Boundaries (L4) for a single-finding surface.
- Made the Phase 6 `/goal` confirmation recognition-first: the assembled goal is mirrored back as a labeled, glyph-tagged, line-by-line contract with provenance, replacing the opaque block plus blind yes/no.
- Tightened the generated `/goal` to match the official Claude Code and Codex `/goal` docs: added an explicit iteration policy ("between loops, record what changed and choose the next best action") and a sharper blocked-stop that names the next input needed to proceed.
- Noted the Full surface map as the one index-screen exemption to the 3-to-6 option rule; applied all changes across `SKILL.md`, `references/question-funnel-template.md`, and `references/goal-best-practices.md`.

Changes in v2.8.0:
- Reordered the Phase 5 question funnel to lead with the ranked, evidence-graded Top 5 candidates (a presentation reorder of existing Phase 4 output; no scout/synthesis change).
- Renamed the two interview modes to "Pick a move" (candidate-first, default; alias "express") and "Explore from scratch" (the drill-down; alias "deep dive"), and grounded the mode-selection question with a top-candidate teaser.
- Added two-channel freedom: persistent `show the full map` and `describe your own` lateral moves on every work-selection screen, plus `back to candidates` at every level of Explore from scratch.
- Added confidence-adaptive collapse: when one high-confidence candidate dominates, the funnel confirms it instead of showing a full menu.
- Grounded Explore's L0 to list only intents that have candidates, annotated with candidate counts, with evidence carried alongside every option.
- Applied the changes in both `SKILL.md` and `references/question-funnel-template.md`, and synced the README mode blurb.

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
