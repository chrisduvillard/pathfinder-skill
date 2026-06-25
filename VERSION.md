# Pathfinder Skill Version

Generated: 2026-06-25

Version: 2.17.1

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

Changes in v2.17.1:
- Fixed a charter-persistence bug surfaced by a live dogfood on Windows/MSYS git: the local-only ignore ladder's "already ignored?" rung tested the bare `.pathfinder/` directory, but `git check-ignore` on a not-yet-created directory false-positives on some git builds (reproducible with any nonexistent `<dir>/`). That mis-selected rung 1, skipped writing the `.git/info/exclude` rule, and let the file-level verify-after-write force an in-memory fallback — so the charter silently never persisted across runs on those platforms (safe, but the durability premise no-opped). Both ignore ladders (charter and work-folder) now test a concrete file path under the directory, matching the path the verify step already uses.
- Clarified the reconcile stale-basis check: a field's cited artifact is resolved by basename against the tracked-file set (a basis may name `SKILL.md`, not its full path) and flagged unratified only when no tracked file matches, so a moved-but-present file does not false-flag.

Changes in v2.17.0:
- Added a durable, local-only objectives charter (`.pathfinder/charter.md`, gitignored via `.git/info/exclude`, never committed): a new Phase 4c between Phase 4b and the funnel that researches the project (code + docs + git history + scout findings) and, on the first run, offers a skippable three-screen BLEND interview — each screen leading with evidence-graded inferred suggestions (`✓/~/?` + basis), backed by a scaffolded generic row and a describe-your-own escape — to capture exactly three durable dimensions: north-star & success metrics, target users & key journeys, and constraints & non-goals. Roadmap/near-term priorities are deliberately excluded.
- Made the charter reusable: later runs load it and reconcile only the fields where fresh inference disagrees (default keep-and-proceed; empty delta collapses to one line), and an explicit `/pathfinder charter` invocation (or a reconcile-screen option) re-opens the full interview to deepen it when objectives change.
- Added transparent objective re-bias: a charter-driven alignment tiebreak that breaks only same-band near-ties on impact ÷ effort toward north-star-aligned candidates (never across an evidence band, only on interview-ratified fields), a visible `Aligns:` signal on every funnel card, an `ignore objectives` escape that reverts to pure evidence order, and a charter-framed `in service of <north-star>` line in the generated `/goal` and its recognition-first contract. The charter north-star is sanitized and capped to a single short clause before it ships, since it is untrusted data.
- Hardened the trust posture: the charter is lower injection risk but still untrusted and sanitized on every read (a tracked charter is treated as fully untrusted); reading docs/git to infer objectives is evidence, never an instruction; and autonomous mode never runs the interview and never lets the charter reorder execution or widen authorization. Reused the existing `04`/`05` artifacts (no new artifact filenames) and extended `scripts/check-skill-consistency.sh` with `check_pair` and SKILL-only presence guards for every new invariant.

Changes in v2.16.0:
- Added autonomous mode (opt-in): an explicitly-invoked entrypoint ("run Pathfinder autonomously" / "/pathfinder auto") that runs the normal exploration through Phase 4b, then auto-selects every verified survivor (grouped by the existing rules, no interview) and executes the goal pack sequentially end to end — branch, implement, run the goal's proof checks, verify, commit, push, open a PR, and self-merge where the repository's own rules allow it — isolating-and-continuing on any failure. Sequential completion off a freshly updated base avoids merge-order staleness and parallel-branch collisions; parallel execution is deferred.
- Made it a distinct authorization tier, not a new default: added "Execution authorization tiers" (read-only / autopilot / autonomous) to Execution safety. Autonomous is reached only by explicit invocation and is never an option in the post-save execution menu, so the save-don't-run default (option 2) keeps its meaning. The trust boundary and the dangerous-category carve-out (auth/payments/migrations/secrets/CI/public-API/data-deletion) are never waived: candidates touching them are excluded from autonomous execution.
- Hardened the unattended-merge path with diff-grounded safety gates the pre-execution estimate cannot be: a post-execution protected-path gate and an absolute-danger scan run on the real `git diff` before any push; an automated verification agent (the Phase 4b panel applied to the completed diff with fidelity and absolute-danger lenses, contested → no merge) replaces the removed human checkpoint; an injection-disqualifies-autonomy filter drops candidates whose provenance flagged suspicious repo content; credential separation keeps the push token out of the environment during repo-code execution and disables repo-defined git hooks on the credentialed commit/push/PR steps (so an activated `core.hooksPath` cannot run repo code with the token live); and self-merge is default-deny, requiring a positive branch-protection signal rather than the mere absence of a blocker.
- Reused the existing artifact contract (auto-selection logged to `04`/`05`, per-goal run log in `07`, shipped/blocked ledger in `08`) so no new artifact filenames were introduced, and extended `scripts/check-skill-consistency.sh` with a SKILL-only presence guard for the five load-bearing autonomous-mode safety invariants so silently deleting any one fails CI.

Changes in v2.15.0:
- Refined the Phase 4b verifier panel so it can no longer false-reject a real finding for not being fixed yet. Each blind verifier now receives the candidate's `symptom` — the current behavior, which should be present in the code (the field Lens 1 always referenced but was never supplied) — alongside `candidate_end_state`, the post-fix target, which is not expected to be present and whose absence is never disconfirming. Lens 1 judges the symptom's presence, Lens 3 judges the end-state as a target, and the hallucination guard now forbids citing the unmet end-state as grounds to reject. `symptom` is added to the blind-input sanitization list.
- Surfaced by a dogfood run of Pathfinder on its own repository: two of three verifiers misread a confirmed finding's post-fix end-state as a false claim about current code and voted reject (meeting the 2-of-3 destructive bar); only the adjudication re-read kept the finding from being quarantined.

Changes in v2.14.0:
- Added Phase 4b: an independent, adversarial verification pass over the Top 5 between synthesis and the funnel. A blind three-verifier panel (grounding / grade-justification / measurability lenses) re-reads each candidate's cited code; grades aggregate by median-of-ceilings and a destructive reject needs a 2-of-3 majority with an adjudication re-read, so one hallucinating verifier cannot quarantine a real candidate. Verdicts downgrade grades, re-rank, and quarantine fabrications into a visible "Rejected by verification" block, refilling from re-verified runner-ups; the intent tally and surface index are re-emitted so L0 and the full map never read stale counts. Results surface as a `Verified:` field across the Phase 5 screens and as display-only provenance in the Phase 6 contract (never inside the generated `/goal`).
- Recorded the new `03b-verification.md` artifact (placeholder in Track B), its lifecycle header and resumable verdict log, and read-only verifier safety (untrusted-data restatement, injection fail-safe to reject, secret/protected-file redaction, no command execution). Extended `scripts/check-skill-consistency.sh` to guard the new artifact filename and the `Verified:` / `Rejected by verification` / Lens-3 mirror invariants across `SKILL.md`, `question-funnel-template.md`, and `goal-best-practices.md`.

Changes in v2.13.0:
- Pinned `*.json` to LF in `.gitattributes` so the JSON manifests parsed by jq/awk on the Linux CI runners get the same explicit LF guarantee as every other CI-consumed type instead of relying on `text=auto` alone (DX-4), and added explicit CODEOWNERS rules for `VERSION.md` (auto-publishes releases) and `.gitattributes` (guards CI line endings) (DX-5).
- Extracted the manifest JSON-validity, version-parity, marketplace-version-absence, and VERSION.md-hygiene checks into `scripts/check-manifests.sh`, now run by both `.github/workflows/manifests.yml` and `CONTRIBUTING.md`, so contributors reproduce every version-drift failure locally before pushing instead of after (DX-2).
- Reconciled the Phase 3 wording that called `03-synthesis.md` a file Phase 4 "creates" with the placeholder-first model — it now "fills" the placeholder created at session setup (ARCH-6) — and labeled the confidence-adaptive collapse's second option as the path back to the ranked Top 5 (FP-2).
- Documented two intentional designs in `CONTRIBUTING.md` so they are not "fixed" into breakage: marketplace `category` casing is per-platform (Claude lowercase, Codex title-case) and must not be unified (BD-3); the `references/*.md` files deliberately mirror the `SKILL.md` Phase 5/6 screens for on-demand loading and the mirror is enforced by `scripts/check-skill-consistency.sh` (ARCH-5).

Changes in v2.12.0:
- Hardened `scripts/check-skill-consistency.sh` so the drift it exists to catch fails CI instead of shipping green: the artifact-filename parity check now covers the `02-scout-briefs/` directory slot (TR-1); the mandatory untrusted-data `/goal` clause is asserted by a clause-unique phrase instead of a bare substring that survived in unrelated trust-boundary prose (TR-2); code-fence validation tracks open/close state and asserts the goal-pack's 4-backtick wrapper instead of counting parity, which was blind to a 4→3 downgrade (TR-3); and previously un-mirrored shared `SKILL.md`↔`question-funnel-template.md` invariants (the select-all alias grammar, `deep dive`, `Goal-readiness confidence`, `Audit only`) are now guarded (TR-6).
- Closed Phase 4/5/6 self-conformance and provenance gaps in `SKILL.md`, mirrored in the references: the recognition-first goal contract gains a Non-goals row and honest provenance tags for End state and Constraints (ARCH-1/2/3); the confidence-adaptive collapse names its goal-readiness trigger, labels the card confidence, and restores the `Agent recommends … because` rationale (ARCH-4, FP-1); the selected-moves grouping review gains the universal `None of these, let me describe it` escape and the escape rule enumerates it (FP-3); the Pick a move escapes are flattened to match the L0–L4 style (FP-4); the `back to candidates` wording is unified across `SKILL.md` and the funnel template (FP-5); and Phase 4 copies `severity` so `impact`'s input is named, ranks L1 by impact ÷ effort like Mode 1, and makes the type×domain→L0-intent mapping deterministic (BD-1/BD-2/BD-4).
- Made the release/CI workflows fail loudly and closed their guard gaps: a failed `gh release create` now fails the `release.yml` step instead of being masked by the trailing success echo under `set -uo pipefail` (DX-1); version parsing is unified on one anchored regex across the `manifests.yml` count/parse and the `release.yml` parse so they cannot resolve different versions (TR-4); the marketplace version-absence `jq` check also rejects a version nested under `.plugins[].source` (TR-5); and `manifests.yml` scopes its `push` trigger to `main` and adds a `concurrency` group with cancel-in-progress (DX-3).

Changes in v2.11.0:
- Added a prompt-to-goal track (Track B): when the user supplies a prompt to convert, Pathfinder does targeted, prompt-anchored research instead of the full blind discovery + five scouts + Top-5 ranking, asks only the `/goal`-checklist gaps research could not settle, and forges the same bounded `/goal` by reusing Phases 6–8. It is routed automatically on a prompt-bearing invocation, or via a one-time entry choice. The user's prompt is treated as a trusted instruction while repository content stays untrusted; protected-area gating and Phase 7 approval still apply.
- Reused the existing numbered artifact contract for Track B (`00-session.md` records the verbatim prompt and routing decision; `01-blind-discovery.md` holds the prompt-anchored research; `02-scout-briefs/` and `03-synthesis.md` are placeholders; `04-question-funnel.md` / `05-user-answers.md` hold the gap-driven questions and answers), so no new artifact filenames were introduced and the artifact-contract drift check is unchanged.
- Extended the markdown drift checks (`scripts/check-skill-consistency.sh`) for `prompt-to-goal` and `gap-driven` across `SKILL.md` and `references/question-funnel-template.md`.

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
