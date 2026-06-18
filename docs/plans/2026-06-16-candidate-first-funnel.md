# Candidate-first Question Funnel Implementation Plan

> **Archive note (2026-06-18):** Completed and shipped in v2.8.0. See
> `VERSION.md` -> `Changes in v2.8.0` for the release record. This plan is
> retained as historical implementation detail; unchecked boxes below are not
> active work items.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder Phase 5 so it leads with the ranked, evidence-graded Top 5 candidates (a presentation change), keep a grounded two-mode toggle, and add persistent lateral moves for freedom — across `SKILL.md`, the funnel template, and supporting docs.

**Architecture:** Pathfinder is a markdown-only agent skill — there is no executable code and no test runner. "Tests" here are deterministic checks against the prose: `rg`/`grep` for required strings, `jq` for manifest validity, and read-throughs for spec drift. Every field a candidate card needs is already emitted by Phase 4 synthesis (`skills/pathfinder/SKILL.md:316–327`), so this is a Phase 5 presentation reorder with no scout/synthesis change.

**Tech Stack:** Markdown, JSON manifests (`jq`), git. Commands shown for Git Bash; PowerShell equivalents noted where they differ.

**Source spec:** `docs/specs/2026-06-16-candidate-first-funnel-design.md`

**Template-token note:** New blocks below contain angle-bracket tokens like `<symptom one-liner>` and `<location>`. These are the skill's own runtime placeholders — the agent fills them when it runs. **Do not replace them with concrete values while editing.** Copy them verbatim.

**Mode naming decision (locked):** Mode 1 = **"Pick a move"** (candidate-first, default; alias `express`). Mode 2 = **"Explore from scratch"** (the L0→L4 drill-down; alias `deep dive`).

---

## File Structure

Files modified (no files created except this plan and the already-committed spec):

- `skills/pathfinder/SKILL.md` — Phase 5 section, the universal rules, and the mode overview near the top. The canonical behavior spec.
- `skills/pathfinder/references/question-funnel-template.md` — the compact template the agent loads at funnel time. Must agree with SKILL.md on every screen.
- `.claude-plugin/plugin.json` / `.codex-plugin/plugin.json` — version bump only.
- `VERSION.md` — changelog entry.
- `README.md` — the mode blurb at "step 4" must match the new mode names.

---

## Task 1: SKILL.md — overview blurb, universal rules, mode-selection question

**Files:**
- Modify: `skills/pathfinder/SKILL.md` (mode overview ~15–20; universal rules ~335–343; mode selection ~345–360)

- [ ] **Step 1: Update the mode overview blurb**

Replace this block (currently ~lines 15–20):

```text
The interview that pinpoints the work comes in two user-selectable modes (see Phase 5):

- **Express**: one compact question. Fastest, best when the target is already fairly clear.
- **Deep dive**: a short guided drill-down from broad intent to the exact target, narrowing one level at a time. Best when the repo is large or several targets are plausible.

Both modes always suggest answers, always offer an agent recommendation, and always leave an escape to describe something else.
```

with:

```text
The interview that pinpoints the work comes in two user-selectable modes (see Phase 5). Both lead with what the scouts actually found, never an abstract category menu:

- **Pick a move** (default): show the ranked, evidence-graded Top 5 candidates and let the user pick one, then set boundaries. Fastest when a strong target stands out. Accepts the alias "express".
- **Explore from scratch**: a guided drill-down from broad intent to the exact target, narrowing one level at a time, for when the user wants to roam or distrusts the ranking. Accepts the alias "deep dive".

Both modes always suggest repo-grounded answers, always name the agent's recommendation, and always leave lateral moves to browse the full map or describe something else.
```

- [ ] **Step 2: Add three universal rules**

Find this exact bullet in the universal-rules list (~line 341):

```text
- Ground all options in actual findings from `01-blind-discovery.md`, the scout briefs, and the Top 5 candidate goals in `03-synthesis.md`. Do not invent generic menus when concrete findings exist.
```

Insert these three bullets immediately AFTER it:

```text
- Recognition-first ordering: the first screen in either mode must show the most grounded artifact available (the ranked Top 5 candidates, or the full surface map), never an abstract category menu presented before any concrete finding.
- Two-channel freedom: every work-selection screen must carry a lateral move to widen (`show the full map`) and to leave (`describe your own`), in addition to `Go back`. In Explore mode, every level also offers `back to candidates` to return to the ranked list.
- Evidence with options: wherever an option carries a confidence word, it also shows its evidence grade (confirmed, inferred, or suspected) and a one-line basis, so the choice is informed rather than blind.
```

- [ ] **Step 3: Reframe the mode-selection question**

Replace the whole `### Mode selection (ask once)` block (from the heading through the line ending "...jump straight to the Boundaries step (L4) and confirm.", ~lines 345–360) with:

````text
### Mode selection (ask once)

Before any other question, preview the single strongest finding so the choice is informed, then ask which interview mode to use:

```text
I mapped this repo and found <N> ranked candidates.
Top pick: <top candidate symptom> — <location> (<evidence_grade>, <confidence>).

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one   [recommended]
2. Explore from scratch drill down by intent → area → surface, ignoring my ranking

Agent recommends: <1 | 2> because <one-line reason from findings, e.g. one confirmed
high-confidence target stands out, or the repo is large with several plausible targets>.
Reply 1 / 2, or "express"/"deep dive".
```

"express" selects Pick a move; "deep dive" selects Explore from scratch. If the user already named a mode up front, skip this question. If the user named a concrete target up front in either mode, jump straight to the Boundaries step (L4) and confirm.
````

- [ ] **Step 4: Verify the edits landed and the old mode names are gone from these regions**

Run:

```bash
rg -n "Pick a move|Explore from scratch|Recognition-first|Two-channel freedom|Evidence with options" skills/pathfinder/SKILL.md
```

Expected: at least 5 matches (overview blurb + 3 rules + mode-selection heading text).

Run:

```bash
rg -n "two user-selectable modes" skills/pathfinder/SKILL.md
```

Expected: one match, and the surrounding text now says "Both lead with what the scouts actually found".

- [ ] **Step 5: Commit**

```bash
git add skills/pathfinder/SKILL.md
git commit -m "feat: ground Phase 5 mode selection and add recognition-first rules"
```

---

## Task 2: SKILL.md — replace Express section with Mode 1 (candidate-first)

**Files:**
- Modify: `skills/pathfinder/SKILL.md` (the `### Express mode (compact, single-shot)` section, ~362–379)

- [ ] **Step 1: Replace the Express section**

Replace the entire `### Express mode (compact, single-shot)` section (from the heading through the line "Accept compact answers such as ... Then go to Phase 6.", ~lines 362–379) with:

````text
### Mode 1: Pick a move (candidate-first, default)

Show the ranked Top 5 candidates from `03-synthesis.md` as evidence-bearing cards. Every field below already exists in synthesis output (`Phase 4`); do not re-derive the repo.

```text
Top moves (ranked by impact ÷ effort; confirmed outrank inferred outrank suspected):

 1. <symptom one-liner>            <location: file:symbol/route>
    <glyph> <evidence_grade> — <one-line evidence>   confidence: <HIGH|MED|LOW>
    suggested scope: <scope> · touches: <blast radius; PROTECTED areas flagged>
 2. <symptom one-liner>            <location>
    <glyph> <evidence_grade> — <one-line evidence>   confidence: <HIGH|MED|LOW>
 ... up to 5 candidates ...

Agent recommends: <option n> because <one-line reason from findings>.

Pick 1–5 — or go sideways:
  • narrow by area/intent   → switches to Explore from scratch (L0)
  • show the full map       → browse every surface, not just the Top 5
  • describe your own        (free text)
```

Glyphs: `✓` confirmed, `~` inferred, `?` suspected. `suggested scope` is derived from each candidate's `blast_radius`, `risk`, and protected-area fields (a fix touching a protected area leans conservative); it previews the L4 scope recommendation and is not a new synthesis field.

When the user picks a number, go straight to the Boundaries step (L4) for that candidate, then the execution-mode question. Do not ask intent, domain, or surface questions on this path.

`show the full map` presents the per-domain surface index from `03-synthesis.md` so the user can point at any surface, not only the Top 5. `narrow by area/intent` hands off to Explore from scratch starting at L0.

Confidence-adaptive collapse: when exactly one candidate is goal-readiness `high` and clearly dominates the rest, present a single confirm card instead of the full menu:

```text
One target clearly dominates:
<symptom> — <location> (<evidence_grade>, HIGH).
1. Confirm it and set boundaries
2. See the other <N> candidates
Agent recommends: 1.
None of these: describe your own.   show the full map
```
````

- [ ] **Step 2: Verify the candidate card and collapse exist**

Run:

```bash
rg -n "Mode 1: Pick a move|Top moves \(ranked|Confidence-adaptive collapse|narrow by area/intent" skills/pathfinder/SKILL.md
```

Expected: 4 matches.

Run:

```bash
rg -n "Express mode \(compact" skills/pathfinder/SKILL.md
```

Expected: no matches (the section header is gone).

- [ ] **Step 3: Commit**

```bash
git add skills/pathfinder/SKILL.md
git commit -m "feat: replace Express with candidate-first Pick a move flow"
```

---

## Task 3: SKILL.md — Mode 2 Explore (rename, grounded L0, lateral moves, adaptive, reservoir)

**Files:**
- Modify: `skills/pathfinder/SKILL.md` (`### Deep dive mode`, L0–L4, Adaptive stopping, Option reservoir intro; ~381–502)

- [ ] **Step 1: Rename the Deep dive section header and intro**

Replace this exact line (~line 381):

```text
### Deep dive mode (conditioned drill-down)
```

with:

```text
### Mode 2: Explore from scratch (conditioned drill-down)
```

- [ ] **Step 2: Ground L0 and add lateral moves**

Replace the `#### L0. Intent` block's fenced example and the line above it. Find this block (~lines 407–422):

````text
Ask what kind of outcome the user wants. Draw options from reservoir A/B. Always include `Agent recommends` and the escapes.

```text
1. Fix a correctness/reliability defect
2. Improve a product/UX surface
3. Improve backend/API/data robustness
4. Improve tests and regression protection
5. Improve architecture/maintainability
6. Improve performance
7. Improve developer experience
8. Harden security/config/auth
9. Agent picks the highest-ROI outcome

Agent recommends: <option n> because <one-line reason from findings>.
None of these: describe the outcome you want.
```
````

Replace it with:

````text
Ask what kind of outcome the user wants. List only intents that have at least one real candidate, annotate each with its candidate count, and draw wording from reservoir A/B. Always include `Agent recommends` and the lateral moves.

```text
1. Fix a correctness/reliability defect      → <n> candidates (<m> confirmed)
2. Improve a product/UX surface              → <n> candidates
3. Improve backend/API/data robustness       → <n> candidates
... only intents that have candidates, annotated with counts ...
9. Agent picks the highest-ROI outcome

Agent recommends: <option n> because <one-line reason from findings>.
None of these: describe the outcome you want.
back to candidates: return to the ranked Top 5.   show the full map
```
````

- [ ] **Step 3: Add lateral moves to L1**

Find the L1 footer (~lines 434–436):

```text
Agent recommends: <option n, the highest-confidence candidate> because <reason>.
None of these: describe the area you care about.
Go back: return to the previous question.
```

Replace with:

```text
Agent recommends: <option n, the highest-confidence candidate> because <reason>.
None of these: describe the area you care about.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

- [ ] **Step 4: Add lateral moves to L2**

Find the L2 footer (~lines 449–451):

```text
Agent recommends: <option n, the best surface> because <reason>.
None of these: name the file/area.
Go back: return to the previous question.
```

Replace with:

```text
Agent recommends: <option n, the best surface> because <reason>.
None of these: name the file/area.
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

- [ ] **Step 5: Add lateral moves to L3**

Find the L3 confirm footer (~lines 463–465):

```text
1. Confirm this target
2. Adjust it: describe the precise behavior in your own words (free-text escape)
Go back: return to the previous question.
```

Replace with:

```text
1. Confirm this target
2. Adjust it: describe the precise behavior in your own words (free-text escape)
Go back: return to the previous question.
back to candidates: return to the ranked Top 5.   show the full map
```

- [ ] **Step 6: Add lateral move to L4**

Find the L4 final line (~line 479):

```text
Reply with edits, "accept agent recommendation", or "go back" to revise the target.
```

Replace with:

```text
Reply with edits, "accept agent recommendation", "go back" to revise the target, or "back to candidates" to return to the ranked Top 5.
```

- [ ] **Step 7: Extend Adaptive stopping**

Find this bullet in `#### Adaptive stopping` (~line 487):

```text
- Support `Go back` at any level by re-presenting the previous question with the prior answer noted, without restarting the whole funnel.
```

Replace with:

```text
- Support `Go back` at any level by re-presenting the previous question with the prior answer noted, without restarting the whole funnel.
- `back to candidates` and `show the full map` are available at every level: the first re-presents Mode 1's ranked Top 5, the second shows the per-domain surface index. Neither restarts the funnel.
```

- [ ] **Step 8: Fix the Option reservoir intro**

Find this line (~line 502):

```text
Both modes draw suggested answers from this reservoir. Adapt and reorder based on actual findings; drop options that do not apply to the repo.
```

Replace with:

```text
Explore from scratch and the shared Boundaries question draw suggested answers from this reservoir; the Pick a move candidate cards come from `03-synthesis.md`, not this reservoir. Adapt and reorder based on actual findings; drop options that do not apply to the repo.
```

- [ ] **Step 9: Verify Mode 2 edits**

Run:

```bash
rg -n "Mode 2: Explore from scratch|back to candidates|→ <n> candidates" skills/pathfinder/SKILL.md
```

Expected: the rename (1) + `back to candidates` on L0, L1, L2, L3, L4, and adaptive stopping (6) + the annotated L0 example (≥1).

Run:

```bash
rg -n "Deep dive mode \(conditioned" skills/pathfinder/SKILL.md
```

Expected: no matches.

- [ ] **Step 10: Commit**

```bash
git add skills/pathfinder/SKILL.md
git commit -m "feat: reposition drill-down as Explore from scratch with lateral moves"
```

---

## Task 4: Mirror every change into the funnel template

**Files:**
- Modify: `skills/pathfinder/references/question-funnel-template.md` (whole file is the compact mirror of Phase 5)

The template must agree with SKILL.md on every screen. Apply the same changes in the template's compact style.

- [ ] **Step 1: Update the intro + universal rules**

Find this line (~line 5):

```text
Pathfinder runs one of two user-selectable modes. Ask which mode to use first, then follow that mode. Both modes obey the same universal rules.
```

Replace with:

```text
Pathfinder runs one of two user-selectable modes: Pick a move (candidate-first, default; alias "express") and Explore from scratch (drill-down; alias "deep dive"). Ask which mode to use first — leading with the strongest finding — then follow that mode. Both obey the same universal rules.
```

Then find the universal-rules bullet (~line 12):

```text
- Ground every option in actual findings, not generic categories.
```

Insert these bullets immediately AFTER it:

```text
- Recognition-first: the first screen shows the ranked Top 5 or the full map, never an abstract category menu.
- Two-channel freedom: every work-selection screen offers `show the full map` and `describe your own`; Explore mode also offers `back to candidates` at every level.
- Evidence with options: each option shows its evidence grade (confirmed/inferred/suspected) and a one-line basis next to any confidence word.
```

- [ ] **Step 2: Replace the Mode selection block**

Replace the `## Mode selection (ask once)` fenced block and the sentence after it (~lines 16–27) with:

````text
## Mode selection (ask once)

```text
I mapped this repo and found <N> ranked candidates.
Top pick: <top candidate symptom> — <location> (<evidence_grade>, <confidence>).

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one   [recommended]
2. Explore from scratch drill down by intent → area → surface

Agent recommends: <1 | 2> because <one-line reason from findings>.
Reply 1, 2, or "express"/"deep dive".
```

Recommend Pick a move when one high-confidence target stands out; recommend Explore for large or ambiguous repos. "express" → Pick a move, "deep dive" → Explore from scratch. If the user names a concrete target up front, jump straight to L4 (Boundaries) and confirm.
````

- [ ] **Step 3: Replace the Express section with Mode 1**

Replace the `## Express mode` section (heading through "Accept compact answers like ...", ~lines 29–45) with:

````text
## Mode 1: Pick a move (candidate-first, default)

Show the ranked Top 5 from `03-synthesis.md` as evidence cards, then generate the goal.

```text
Top moves (impact ÷ effort; confirmed > inferred > suspected):
 1. <symptom>   <location>
    <glyph> <evidence_grade> — <one-line evidence>   confidence: <HIGH|MED|LOW>
    suggested scope: <scope> · touches: <blast radius; PROTECTED flagged>
 2. <symptom>   <location>
    <glyph> <evidence_grade> — <evidence>   confidence: <...>
 ... up to 5 ...

Agent recommends: <option n> because <reason>.

Pick 1–5 — or go sideways:
  • narrow by area/intent → Explore from scratch (L0)
  • show the full map     → browse every surface
  • describe your own      (free text)
```

Glyphs: `✓` confirmed, `~` inferred, `?` suspected. `suggested scope` is derived from `blast_radius`/`risk`/protected areas, not a new field. Picking a number jumps straight to L4 (Boundaries).

Confidence-adaptive collapse — when one `high` candidate dominates, confirm instead of menu:

```text
One target dominates: <symptom> — <location> (<evidence_grade>, HIGH).
1. Confirm it and set boundaries
2. See the other <N> candidates
Agent recommends: 1.
None of these: describe your own.   show the full map
```
````

- [ ] **Step 4: Rename Deep dive and ground L0**

Find (~line 47):

```text
## Deep dive mode
```

Replace with:

```text
## Mode 2: Explore from scratch
```

Then replace the `### L0. Intent` fenced block (~lines 61–76) with:

````text
### L0. Intent (only intents with candidates, annotated)

```text
1. Fix a correctness/reliability defect → <n> candidates (<m> confirmed)
2. Improve a product/UX surface         → <n> candidates
3. Improve backend/API/data robustness  → <n> candidates
... only intents that have candidates ...
9. Agent picks the highest-ROI outcome

Agent recommends: <option n> because <one-line reason from findings>.
None of these: describe the outcome you want.
back to candidates: return to the ranked Top 5.   show the full map
```
````

- [ ] **Step 5: Add `back to candidates` + `show the full map` to L1, L2, L3 in the template**

In the L1 block, find:

```text
None of these: describe the area.
Go back: return to the previous question.
```

Replace with:

```text
None of these: describe the area.
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

In the L2 block, find:

```text
None of these: name the file/area.
Go back: return to the previous question.
```

Replace with:

```text
None of these: name the file/area.
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

In the L3 block, find:

```text
2. Adjust it: describe the precise behavior in your own words (free-text escape)
Go back: return to the previous question.
```

Replace with:

```text
2. Adjust it: describe the precise behavior in your own words (free-text escape)
Go back: return to the previous question.
back to candidates: ranked Top 5.   show the full map
```

- [ ] **Step 6: Add lateral move to L4 and Adaptive stopping in the template**

In the L4 block, find:

```text
Reply with edits, "accept agent recommendation", or "go back" to revise the target.
```

Replace with:

```text
Reply with edits, "accept agent recommendation", "go back", or "back to candidates".
```

In `### Adaptive stopping`, find:

```text
- `Go back` re-presents the previous question without restarting the funnel.
```

Replace with:

```text
- `Go back` re-presents the previous question without restarting the funnel.
- `back to candidates` returns to the ranked Top 5 and `show the full map` shows the surface index, at any level, without restarting.
```

- [ ] **Step 7: Update the Deep dive prose line in the template**

Find (~line 49):

```text
One question per level. Hard cap of five levels (L0 to L4) before execution mode. Each level's options are conditioned on the previous answer and generated from the scout briefs.
```

Confirm it still reads correctly under the new heading (no change needed if it does). If it names "Deep dive" anywhere in prose, change that word to "Explore from scratch".

- [ ] **Step 8: Verify the template mirrors SKILL.md**

Run:

```bash
rg -n "Pick a move|Explore from scratch|back to candidates|Confidence-adaptive collapse|Recognition-first" skills/pathfinder/references/question-funnel-template.md
```

Expected: mode names present; `back to candidates` appears on L0, L1, L2, L3, L4, adaptive (6); collapse + recognition-first present.

Run:

```bash
rg -n "## Express mode|## Deep dive mode" skills/pathfinder/references/question-funnel-template.md
```

Expected: no matches.

- [ ] **Step 9: Commit**

```bash
git add skills/pathfinder/references/question-funnel-template.md
git commit -m "feat: mirror candidate-first funnel into the template"
```

---

## Task 5: Version bump + VERSION.md changelog

**Files:**
- Modify: `.claude-plugin/plugin.json:3`, `.codex-plugin/plugin.json:3`, `VERSION.md`

- [ ] **Step 1: Bump both manifest versions**

In `.claude-plugin/plugin.json` change:

```json
  "version": "2.7.0",
```

to:

```json
  "version": "2.8.0",
```

Make the identical change in `.codex-plugin/plugin.json`.

- [ ] **Step 2: Update VERSION.md header and add the changelog entry**

In `VERSION.md`, change `Version: 2.7.0` to `Version: 2.8.0` (leave `Generated: 2026-06-16` as-is — same day).

Insert this block immediately after the `Version: 2.8.0` line and its blank line, before `Changes in v2.7.0:`:

```text
Changes in v2.8.0:
- Reordered the Phase 5 question funnel to lead with the ranked, evidence-graded Top 5 candidates (a presentation reorder of existing Phase 4 output; no scout/synthesis change).
- Renamed the two interview modes to "Pick a move" (candidate-first, default; alias "express") and "Explore from scratch" (the drill-down; alias "deep dive"), and grounded the mode-selection question with a top-candidate teaser.
- Added two-channel freedom: persistent `show the full map` and `describe your own` lateral moves on every work-selection screen, plus `back to candidates` at every level of Explore from scratch.
- Added confidence-adaptive collapse: when one high-confidence candidate dominates, the funnel confirms it instead of showing a full menu.
- Grounded Explore's L0 to list only intents that have candidates, annotated with candidate counts, with evidence carried alongside every option.
- Applied the changes in both `SKILL.md` and `references/question-funnel-template.md`, and synced the README mode blurb.
```

- [ ] **Step 3: Verify versions and JSON validity**

Run:

```bash
jq -r .version .claude-plugin/plugin.json .codex-plugin/plugin.json
```

Expected: prints `2.8.0` twice.

Run:

```bash
jq . .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json > /dev/null && echo "all manifests parse"
```

Expected: `all manifests parse`.

Run:

```bash
rg -n "Changes in v2.8.0:" VERSION.md
```

Expected: one match.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json .codex-plugin/plugin.json VERSION.md
git commit -m "chore: bump to 2.8.0 and document the candidate-first funnel"
```

---

## Task 6: Sync README mode blurb

**Files:**
- Modify: `README.md` (the "step 4" mode list, ~73–76)

- [ ] **Step 1: Replace the mode blurb**

Find this block (~lines 73–76):

```text
At step 4 you pick how it interviews you:

- **Express**: one compact question. Fastest, when the target is already clear.
- **Deep dive**: a guided drill-down from broad intent down to the exact file and behavior, one sharp question at a time. Every question suggests answers, names the agent's recommendation, and lets you go back or describe your own.
```

Replace with:

```text
At step 4 you pick how it interviews you:

- **Pick a move** (default): Pathfinder shows the ranked, evidence-graded Top 5 candidates and you pick one, then set boundaries. Fastest when a strong target stands out. (Alias: "express".)
- **Explore from scratch**: a guided drill-down from broad intent down to the exact file and behavior, one sharp question at a time. (Alias: "deep dive".) Every question suggests answers, names the agent's recommendation, and lets you go back, return to the ranked candidates, browse the full map, or describe your own.
```

- [ ] **Step 2: Verify**

Run:

```bash
rg -n "Pick a move|Explore from scratch" README.md
```

Expected: 2 matches.

Run:

```bash
rg -n "\*\*Express\*\*|\*\*Deep dive\*\*" README.md
```

Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: sync README mode blurb with candidate-first funnel"
```

---

## Task 7: Final cross-file verification

**Files:** none modified — verification only.

- [ ] **Step 1: No stale mode names remain anywhere in shipped docs**

Run:

```bash
rg -n "Express mode|Deep dive mode" skills/ README.md README-INSTALL.md
```

Expected: no matches. (Bare alias words "express"/"deep dive" inside the new blocks are fine; this pattern only catches the old section/mode-name phrasing.)

- [ ] **Step 2: SKILL.md and template agree on the core vocabulary**

Run:

```bash
for term in "Pick a move" "Explore from scratch" "back to candidates" "show the full map" "Confidence-adaptive collapse"; do
  echo "== $term =="
  rg -c "$term" skills/pathfinder/SKILL.md skills/pathfinder/references/question-funnel-template.md
done
```

Expected: every term appears in BOTH files (collapse may read "Confidence-adaptive collapse" in SKILL.md and the template — confirm each shows a count ≥ 1 in both).

- [ ] **Step 3: Acceptance-check read-through**

Open `docs/specs/2026-06-16-candidate-first-funnel-design.md`, read the "Acceptance checks" list (8 items), and confirm each is satisfied by reading the relevant region of `SKILL.md` / the template. Note any miss; if found, fix it in the owning file and re-commit.

- [ ] **Step 4: Confirm clean tree and correct commit identity**

Run:

```bash
git status --porcelain && git log -5 --format='%h %an <%ae> %s'
```

Expected: empty porcelain output (clean tree); the recent commits all show `Chris <duvillard.c@gmail.com>`.

---

## Self-Review (completed by plan author)

**Spec coverage:** Each spec section maps to a task — mode reframe → Task 1; Mode 1 cards + collapse → Task 2; Mode 2 grounding + lateral moves → Task 3; template mirror → Task 4; artifacts/version → Task 5; README sync (drift prevention) → Task 6; acceptance checks → Task 7.

**Placeholder scan:** No plan-level placeholders. Angle-bracket tokens are intentional skill runtime template content (flagged in the header).

**Type/vocabulary consistency:** Mode names ("Pick a move" / "Explore from scratch"), lateral-move labels ("back to candidates", "show the full map", "describe your own"), and glyphs (`✓`/`~`/`?`) are used identically across SKILL.md, the template, and README tasks.
