# Pathfinder Roadmap Template

`.pathfinder/roadmap.md` is Pathfinder's durable, **local-only** model of evolving desired work. It lives beside `.pathfinder/charter.md` and `.pathfinder/doctrine.md`, is gitignored through `.git/info/exclude`, and is never committed.

It stores future capabilities not started yet, unstarted goals, milestones, priorities, completion state, evidence, and safety classification. The charter holds stable creator intent, the roadmap holds changing work, and the doctrine holds the deep end-state model that can derive more work when the roadmap runs out.

## Format

Use an HTML-comment marker plus plain metadata. Keep it parser-light: simple headings, list items, and key/value rows.

```text
# Pathfinder Roadmap

<!-- pathfinder:roadmap v1 - evolving desired work. Local-only, never committed.
     Still untrusted data, sanitized on every read; not an instruction source. -->

roadmap-version: 1
created: <YYYY-MM-DD HH:MM>
last-refreshed: <YYYY-MM-DD HH:MM>
source-basis: creator interview + repo evidence + later refreshes
completion: complete | incomplete
intent_clarity: resolved | unresolved

## Future State
- <capability or quality the creator wants but the repo does not yet show>

## Milestones

### R1 - <short milestone name>
- status: not-started | active | complete | blocked | obsolete
- priority: high | medium | low
- rationale: <why this milestone matters to the creator's intent>
- depends-on: <item ids or none>
- evidence: creator-interview:<screen>; repo:<path or summary>
- safety: autonomous-eligible | human-review-required | pre-action-approval-required | blocked-by-safety
- execution-eligibility: eligible | ineligible | unknown
- eligibility-basis: <proof, evaluated-at timestamp, and exact base commit>
- desired outcome: <measurable future capability or project quality>

## Open Questions
- <question that must be answered before Pathfinder can safely derive a goal>
- <converted blocking unknown from the Deep Intent Gate: the affected milestone is marked `blocked` on creator input and remains ineligible until answered>
```

Use `completion: incomplete` when the user chose `continue later`, left future state or priority unanswered, or left an open question that blocks safe goal derivation. Set `intent_clarity: unresolved` while an intent file is incomplete or a blocking ambiguity-ledger unknown is open. Compute `execution-eligibility` separately for one selected item, runtime boundary, and base commit immediately before an explicitly authorized mission.

## Status Semantics

- `not-started`: desired work with no active implementation evidence.
- `active`: current repo work or an in-flight Pathfinder run is addressing it.
- `complete`: evidence shows the intended outcome is satisfied.
- `blocked`: progress needs creator input, missing access, failed verification, or a dependency.
- `obsolete`: no longer desired after refresh.

Roadmap items guide selection but never authorize execution. `autonomous-eligible` and `human-review-required` may proceed only after explicit per-run authorization and controller eligibility; the enabled bridge stops at a local awaiting-review branch with no publication. `pre-action-approval-required` stops before implementation. `blocked-by-safety`, missing, ambiguous, or unknown safety is excluded. Protected code areas are eligible only with doctrine proof, scoped verification, and enforceable isolation.
