# Pathfinder Roadmap JSON Template

`.pathfinder/roadmap.json` is Pathfinder's canonical, durable, **local-only** evolving desired work. `.pathfinder/roadmap.md` is a deterministic, replaceable human view rendered by the controller; never edit or parse the view as state.

The roadmap stores future capabilities, milestones, priorities, completion state, evidence, safety classification, and open questions. The charter holds stable creator intent, while doctrine holds the deep end-state model.

## Canonical shape

Start from this schema-shaped example, replace its values with confirmed creator intent, and validate it against `schemas/intent/roadmap.schema.json`. Preserve every key and use only the closed enums shown by the installed schema.

```json
{
  "schema_version": 1,
  "roadmap_id": "roadmap_example01",
  "completion": "complete",
  "intent_clarity": "resolved",
  "created_at": "2026-01-01T00:00:00Z",
  "refreshed_at": "2026-01-01T00:00:00Z",
  "source_basis": [
    "creator interview",
    "repository evidence"
  ],
  "future_state": [
    "Capability or quality the creator wants but the repository does not yet show"
  ],
  "items": [
    {
      "item_id": "R1",
      "status": "not-started",
      "priority": "high",
      "rationale": "Why this milestone matters to creator intent.",
      "depends_on": [],
      "evidence": [
        "creator interview"
      ],
      "safety": "human-review-required",
      "desired_outcome": "Measurable future capability or project quality.",
      "execution_eligibility": {
        "status": "unknown",
        "reasons": [
          "Not evaluated for a fresh base commit and runtime boundary"
        ],
        "evaluated_at": null,
        "base_commit": null
      }
    }
  ],
  "open_questions": []
}
```

Item status is one of `not-started`, `active`, `complete`, `blocked`, `manual-only`, or `obsolete`. Safety is one of `autonomous-eligible`, `human-review-required`, `pre-action-approval-required`, or `blocked-by-safety`. Missing or ambiguous safety fails closed. Protected code areas are eligible only with doctrine proof, scoped verification, and enforceable isolation.

Use `"completion": "incomplete"` when the creator chose `continue later`, left future state or priority unanswered, or left an Open Question that blocks safe goal derivation. Use `"intent_clarity": "unresolved"` while any canonical intent document is incomplete or a blocking ambiguity-ledger unknown remains open. Converted blocking unknowns become `open_questions` with affected items marked `blocked` on creator input.

Keep `execution_eligibility.status` as `unknown` until one selected item is evaluated against a fresh base commit and runtime boundary. Eligibility, safety classification, resolved intent, and the rendered view never authorize execution.
