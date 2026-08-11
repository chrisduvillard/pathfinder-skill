# Pathfinder Charter JSON Template

`.pathfinder/charter.json` is Pathfinder's canonical, durable, **local-only** stable creator intent. `.pathfinder/charter.md` is a deterministic, replaceable human view rendered by the controller; never edit or parse the view as state.

The charter holds purpose, users, success, constraints, non-goals, optional finished state, and autonomy policy. Changing work belongs in `.pathfinder/roadmap.json`; the deeper Project Doctrine belongs in `.pathfinder/doctrine.json`.

## Canonical shape

Start from this schema-shaped example, replace its values with confirmed creator intent, and validate it against `schemas/intent/charter.schema.json`. Preserve every key and do not add free-form top-level fields.

```json
{
  "schema_version": 1,
  "charter_id": "charter_example01",
  "completion": "complete",
  "intent_clarity": "resolved",
  "established_at": "2026-01-01T00:00:00Z",
  "refreshed_at": "2026-01-01T00:00:00Z",
  "source_basis": [
    "creator interview",
    "repository evidence"
  ],
  "purpose": {
    "north_star": "State the durable destination.",
    "primary_promise": "State what must feel true when the project works."
  },
  "users": {
    "primary": [
      "Primary user"
    ],
    "secondary": [],
    "excluded": [],
    "key_journeys": [
      "Journey that must work"
    ]
  },
  "success": {
    "durable_metrics": [],
    "quality_bars": [
      "Durable reliability, UX, performance, safety, or maintainability bar"
    ],
    "tradeoffs": []
  },
  "constraints": {
    "technical": [],
    "product": [],
    "protected_surfaces": []
  },
  "non_goals": [],
  "finished_state": "Final state, or ongoing product with standing qualities.",
  "autonomy_policy": {
    "may_derive": [],
    "human_review_required": [],
    "never_unattended": [
      "Irreversible or external work"
    ]
  }
}
```

Use `"completion": "incomplete"` when the creator chose `continue later` or left a load-bearing field unanswered. Use `"intent_clarity": "unresolved"` whenever any canonical intent document is incomplete or a blocking ambiguity-ledger unknown remains open. Set it to `resolved` only when those descriptive conditions clear and the creator confirms the complete three-document model.

Activate charter, roadmap, and doctrine together with `migrate intent-activate --creator-confirmed`. The controller validates JSON before any backup or write, preserves prior exact bytes, writes canonical JSON, and renders Markdown. Charter state and its generated view grant no execution authority.
