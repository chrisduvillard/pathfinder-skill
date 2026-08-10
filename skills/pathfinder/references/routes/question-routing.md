## Phase 5: Question funnel, big picture to detail

The goal of this phase is to pinpoint the exact work to do, then convert it into a measurable `/goal`. Pathfinder offers two interview modes. The user always chooses which one runs.

In autonomous mode this interview does not run: Pathfinder does not show the interactive work-selection screens. After the Deep Intent Gate, it selects goals from the sanitized charter plus roadmap and current repo evidence as described in “Autonomous mode” before Phase 7. The rest of Phase 5 below describes the interactive funnel only.

Universal rules that apply to both modes:

- Ask by value-of-information: each question must be capable of changing goal choice, scope, proof, safety classification, authorization, stop conditions, or creator-model clarity. When a stronger model can take an adaptive short path, record why skipped questions were low value and still satisfy the artifact contracts.
- Every question must offer suggested answers. Use 3 to 6 numbered, repo-grounded options. Never ask an open question without options. The one exception is the Full surface map browse screen (below): it is an index of every discovered surface, not a 3-to-6 option menu, but it still carries an `Agent recommends:` line and the escapes.
- Every question must include an explicit `Agent recommends:` line that names which of the listed options is the agent's current best pick, and why, so choosing it is informed rather than blind. `Agent recommends:` is a pointer to one of the existing options, never an extra numbered option in the list.
- Every option-bearing work-selection question (L0 intent through L4 boundaries, Pick a move's candidate screen, and the selected-moves grouping review) must include a `None of these, let me describe it` free-text escape. Every drill-down question after the first (L1 onward) must also include a `Go back` option. The one-time mode-selection question and the terminal post-save execution choice use fixed menus and are exempt from both escapes.
- The user may answer with a number, a short combination, a Pick a move multi-select, or free text.
- Ground all options in actual findings from `01-blind-discovery.md`, the scout briefs, and the Top 5 candidate goals in `03-synthesis.md`. Do not invent generic menus when concrete findings exist. (The prompt-to-goal track runs no scouts or Top-5 ranking, so its gap-driven questions ground in the targeted prompt-anchored research in `01-blind-discovery.md` instead — see "Track B: Prompt-to-goal".)
- Recognition-first ordering: the first screen in either mode must show the most grounded artifact available (the ranked Top 5 candidates, or the full surface map), never an abstract category menu presented before any concrete finding.
- Two-channel freedom: every work-selection screen must carry a lateral move to widen (`show the full map`) and to leave (`describe your own`), in addition to `Go back`. In Explore mode, every level also offers `back to candidates` to return to the ranked list.
- Evidence with options: wherever an option carries a confidence word, it also shows its evidence grade (confirmed, inferred, or suspected) and a one-line basis, so the choice is informed rather than blind.
- Post-verification grades: when `03b-verification.md` is `complete`, every work-selection screen shows the post-verification grade and a one-line `Verified:` field; when it is `not-run` or `in-progress`, show the Phase 4 grades and no `Verified:` field. Surface any candidates the panel rejected in a `Rejected by verification` line.
- Objective awareness (only when a charter is loaded): the mode-selection preamble states `Objectives: <north-star> (from your charter) — <k> of 5 top moves align.`; every Pick a move card and Explore option carries an `Aligns:` line/token showing only **north-star** alignment (`✓` aligned, `~` partial, omitted when neutral, words `counter to north-star` for the rare counter case — no new glyphs); a candidate the tiebreak moved appends `(moved <from>-><to> on north-star alignment)`; and an `ignore objectives` escape at any level strips the annotations and reverts to pure evidence order. The `users`/`constraints` charter dimensions are not shown per-card (they live in the charter). Log each pre/post rank change and reason to `05-user-answers.md`.
- Save every question asked to `04-question-funnel.md` and every answer to `05-user-answers.md`. Record the chosen mode and, for Explore from scratch, the full narrowing path. For Pick a move multi-select, `04-question-funnel.md` records the raw selection input and the grouping review options shown; `05-user-answers.md` records selected moves, accepted grouping, splits, merges, drops, and execution choice.
- Stop only when there is enough to write a measurable, verifiable `/goal`.

### Mode selection (ask once)

Before any other question, preview the single strongest finding so the choice is informed, then ask which interview mode to use:

```text
I mapped this repo and found <N> candidates.   (when 03b-verification.md is complete: "<N> verified candidates (<M> rejected by verification)"; when not-run/in-progress: "<N> candidates (verification not run — pre-verification grades)")
Top pick: <top candidate symptom> — <location> (<evidence_grade>, <confidence>).
Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ | n/a (not run)>.
Objectives: <north-star> (from your charter) — <k> of 5 top moves align.   (only when a charter is loaded)

How do you want to choose the work?
1. Pick a move          show the ranked candidates, pick one or more   (default)
2. Explore from scratch drill down by intent → area → surface, ignoring my ranking

Agent recommends: <1 | 2> because <one-line reason from findings, e.g. one confirmed
high-confidence target stands out, or the repo is large with several plausible targets>.
Reply 1, 2, or "express"/"deep dive".
```

"express" selects Pick a move; "deep dive" selects Explore from scratch. If the user already named a mode up front, skip this question. If the user named a concrete target up front in either mode, jump straight to the Boundaries step (L4) and confirm.

### Zero or low survivors after verification

If Phase 4b left zero verified candidates, do not enter the normal funnel. Show this fixed menu (exempt from the candidate-grounded-option rule because there are no candidates):

```text
Verification rejected all candidates. Reasons (from 03b-verification.md): <summary>.
1. Re-run the scouts with these rejection reasons as hints   [recommended]
2. Switch to prompt-to-goal: you name the work, I research it
3. Review the "Rejected by verification" block and decide manually
Agent recommends: 1 because re-scouting with the disconfirming evidence usually surfaces real, locatable work.
```

If one to four verified candidates remain, proceed with them; the mode-selection preamble already states the true count.
