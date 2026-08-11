# Pathfinder Doctrine JSON Template

`doctrine.json` in the selected intent namespace is Pathfinder's canonical, durable, **local-only** Project Doctrine. Root scope uses `.pathfinder/`; an explicit monorepo scope such as `apps/api` uses `.pathfinder/scopes/apps/api/intent/`. `doctrine.md` beside it is a deterministic, replaceable human view rendered by the controller; never edit or parse the view as state or fall back to another namespace.

Doctrine stores the deep end-state model that guides Goal selection: end goal, product philosophy, user intent, quality bars, improvement heuristics, autonomous mission policy, and irreversible/external hard stops. It never authorizes a run; every autonomous mission requires a fresh explicit request.

## Canonical shape

Start from this schema-shaped example, replace its values with confirmed creator intent, and validate it against `schemas/intent/doctrine.schema.json`. Preserve every key. The seven `hard_stops` values are a closed, required safety floor.

```json
{
  "schema_version": 1,
  "doctrine_id": "doctrine_example01",
  "completion": "complete",
  "intent_clarity": "resolved",
  "created_at": "2026-01-01T00:00:00Z",
  "refreshed_at": "2026-01-01T00:00:00Z",
  "source_basis": [
    "Doctrine Interview",
    "repository evidence"
  ],
  "end_goal": "The durable destination the project should move toward.",
  "product_philosophy": [
    "How the product should feel and which tradeoffs are preferred"
  ],
  "user_intent": [
    "Users, workflows, and outcomes Pathfinder should optimize for"
  ],
  "quality_bars": [
    "Reliability, security, UX, performance, maintainability, or reviewability bar"
  ],
  "improvement_heuristics": [
    "How Pathfinder recognizes valuable work"
  ],
  "autonomous_mission_policy": {
    "may_derive_and_edit": [],
    "requires_extra_proof": [
      "protected code areas are eligible with doctrine proof"
    ],
    "human_review_required": [],
    "never_unattended": [
      "Irreversible or external work"
    ]
  },
  "hard_stops": [
    "secrets-or-credentials",
    "destructive-data-operations",
    "releases",
    "repository-administration",
    "force-push",
    "branch-or-tag-deletion",
    "external-side-effects"
  ]
}
```

Use `"completion": "incomplete"` when the creator chose `continue later` or left a load-bearing doctrine field unanswered. Use `"intent_clarity": "unresolved"` while any canonical intent document is incomplete or any blocking ambiguity-ledger unknown remains open. Item proof belongs to `execution_eligibility`, not doctrine.

Doctrine can support item-level proof for protected code areas but cannot authorize execution or override an irreversible/external hard stop. The enabled v1 bridge stops at a local awaiting-review branch and cannot publish. Activate doctrine only with the charter and roadmap through the creator-confirmed controller; never fall back to authoritative Markdown.
