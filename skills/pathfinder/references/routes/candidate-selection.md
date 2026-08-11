### Mode 1: Pick a move (candidate-first, default)

Show the ranked Top 5 candidates from `03-synthesis.md` as evidence-bearing cards. Use the Phase 4 candidate fields directly; render likely fix shape from the candidate end state, blast radius, and effort, and render grouping hints from the derived grouping notes. Do not re-discover the repo.

```text
Top moves (ranked by impact ÷ effort; confirmed outrank inferred outrank suspected):

 1. Outcome: <plain-language symptom or user-visible result>
    Location: <exact file:symbol/route/component>
    Evidence: <glyph> <evidence_grade> — <one-line basis>   confidence: <HIGH|MED|LOW>
    Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ (median of 3) | 1/3 flagged; median holds>
    Aligns:   ✓ north-star   - <one-line why this serves the north-star>   (omit this line when neutral)
    Likely fix shape: <small/medium/large shape, e.g. validation + regression test>
    Proof/checks: <narrow verification commands; flag commands that run repo code>
    Risk/protected areas: <blast radius; PROTECTED areas flagged>
    Grouping hint: <can group with ids because... / keep separate because...>
 2. Outcome: <plain-language symptom or user-visible result>
    Location: <exact location>
    Evidence: <glyph> <evidence_grade> — <one-line basis>   confidence: <...>
    Verified: <panel verdict, e.g. 3/3 confirm | downgraded ✓→~ (median of 3) | 1/3 flagged; median holds>
    Aligns:   ✓ north-star   - <one-line why this serves the north-star>   (omit this line when neutral)
    Likely fix shape: <fix shape>
    Proof/checks: <checks>
    Risk/protected areas: <risk>
    Grouping hint: <hint>
 ... up to 5 candidates ...

Rejected by verification (<N>): <symptoms> — see 03b-verification.md

Agent recommends: <option n> because <one-line reason from findings>.

Pick a move:
  • one: 1
  • several: 1,3,5
  • select all: all, a, 1-5, or 1,2,3,4,5

narrow by area/intent: switch to Explore from scratch (L0)
None of these: describe your own (free text)   show the full map   ignore objectives (when a charter is loaded)
```

Glyphs: `✓` confirmed, `~` inferred, `?` suspected. The card text should be understandable without opening `03-synthesis.md`: plain outcome, exact location, evidence basis, likely fix shape, proof/checks, risk/protected areas, and grouping hint are all visible.

Pick a move input grammar:

- Single select: `1` through `5`.
- Partial multi-select: comma-separated candidate numbers such as `1,3,5`.
- All aliases: `all`, `a`, `1-5`, and `1,2,3,4,5`. These all mean select all five Top moves.

When the user picks one number, go straight to the Boundaries step (L4) for that candidate, then Phase 6 goal confirmation and the post-save execution choice. Do not ask intent, domain, or surface questions on this path.

When the user picks multiple candidates, including any select all alias or manually selecting all five moves, show the Selected moves grouping review before boundaries or goal generation. The grouping review recommends logical goal groups by default, but keeps unrelated, unsafe, protected-area-heavy, low-confidence, or incompatible-verification moves separate.

```text
Selected moves: <ids and short outcomes>

Recommended grouping review:
  Goal 1: candidates <ids> — <shared surface/check/end state>
    Rationale: <why one measurable goal can cover them>
    Proof: <shared or compatible checks>
  Goal 2: candidate <id> — kept separate
    Rationale: <unrelated surface, protected area, risk, or incompatible proof>

1. Accept recommended grouping and save a goal pack   [recommended when groups are coherent]
2. Split into one goal per selected move
3. Adjust selection: reply with numbers or all aliases
4. Go back to Top moves

Agent recommends: <1 | 2> because <one-line grouping rationale>.
None of these, let me describe it: describe the grouping you want in free text.
```

If the user accepts grouping, continue to Phase 6 with those groups. If the user chooses split, create one group per selected move. If the user adjusts the selection, re-run the grouping review for the new selection. If edits or drops leave exactly one selected move, return to the single-goal flow. Record the raw multi-select input, grouping review options, accepted grouping, splits, merges, drops, and execution choice in the artifacts named above.

`show the full map` opens the Full surface map browse screen (below) so the user can point at any surface, not only the Top 5. `narrow by area/intent` hands off to Explore from scratch starting at L0.

Confidence-adaptive collapse: when exactly one candidate is goal-readiness `high` and clearly dominates the rest, present a single confirm card instead of the full menu:

```text
One target clearly dominates (selected on post-verification goal-readiness `high`):
<symptom> — <location> (<evidence_grade>, confidence: HIGH).
Verified: <panel verdict>.
1. Confirm it and set boundaries
2. See the other <N> candidates (back to the ranked Top 5)
Agent recommends: 1 because this is the single goal-ready, high-confidence target.
None of these: describe your own.   show the full map
```

Compute collapse eligibility only after re-rank and refill settle, on post-verification `goal-readiness`. Never carry the pre-verification dominator forward. Do not collapse on a single-pass `keep` or on any candidate where a verifier flagged suspicious content.

### Full surface map (the shared browse screen)

`show the full map` opens this screen — the single destination for every `show the full map` offer in either mode and at every level. It is built from the per-domain surface index already in `03-synthesis.md` (Phase 4) and adds no new synthesis field. When `03b-verification.md` is `complete`, read the re-emitted post-verification surface index from `03b` instead (post-verification grades, surviving-finding counts, and the rejected-surface section). Because it is a browse/index rather than a 3-to-6 option question, it may list as many surfaces as the scouts found.

```text
Full surface map — every surface the scouts found, grouped by domain
(✓ confirmed  ~ inferred  ? suspected · count = findings on that surface)

Backend/Data
  b1. api/orders.py:POST /orders     ✓ duplicate-charge on retry      (3)   Verified: 3/3 confirm
  b2. api/auth.py:refresh_token      ~ token TTL never validated      (1)
Frontend/Product
  f1. views/DashboardView.tsx        ✓ empty-state crash in loadData  (2)
Testing/Reliability
  t1. tests/orders/                  ~ retry path uncovered           (1)

Rejected by verification
  (surfaces backing rejected candidates appear here with their rejection reason; picking one re-enters at L3 with the reason shown)

Pick a surface (b1, f1, …) to set it as your target.
Agent recommends: b1 — most confirmed findings.
back to candidates: ranked Top 5  ·  describe your own  ·  go back
```

- Group surfaces by scout domain; within a domain, order by finding count, then evidence grade (confirmed before inferred before suspected). Each row shows its path, evidence glyph, the strongest finding's symptom, and the finding count.
- Picking a surface jumps to the Target step (L3) scoped to that surface. If the surface has exactly one finding, confirm it as the target automatically and go straight to Boundaries (L4).
- The screen carries an `Agent recommends:` line (the surface with the most confirmed findings, unless another clearly dominates) and the escapes `back to candidates`, `describe your own`, and `go back` (returns to the screen the user came from). It does not re-offer `show the full map` — the user is already there.
