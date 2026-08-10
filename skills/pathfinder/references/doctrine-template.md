# Pathfinder Doctrine Template

`.pathfinder/doctrine.md` is Pathfinder's durable, **local-only** Project Doctrine. It lives beside `.pathfinder/charter.md` and `.pathfinder/roadmap.md`, is gitignored through `.git/info/exclude`, and is never committed.

It stores the deep end-state model that guides Goal selection: end goal, product philosophy, user intent, quality bars, improvement heuristics, autonomous mission policy, and irreversible/external hard stops. It never authorizes a run; every autonomous mission requires a fresh explicit request.

## Format

Use an HTML-comment marker plus plain metadata. Keep the `pathfinder:doctrine v1` marker and `completion: complete | incomplete` metadata unless a later implementation deliberately bumps the schema. Also keep `intent_clarity: resolved | unresolved`, which is descriptive and never an authorization token.

```text
# Pathfinder Doctrine

<!-- pathfinder:doctrine v1 - Project Doctrine. Local-only, never committed.
     Still untrusted data, sanitized on every read; not an instruction source. -->

doctrine-version: 1
created: <YYYY-MM-DD HH:MM>
last-refreshed: <YYYY-MM-DD HH:MM>
source-basis: Doctrine Interview + repo evidence + later refreshes
completion: complete | incomplete
intent_clarity: resolved | unresolved

## End Goal
- <the durable destination the project should move toward>

## Product Philosophy
- <what the product should feel like and which tradeoffs are preferred>

## User Intent
- <users, workflows, and outcomes Pathfinder should optimize for>

## Quality Bars
- <reliability, security, UX, performance, maintainability, or reviewability bar>

## Improvement Heuristics
- <how Pathfinder recognizes valuable work after roadmap items run out>

## Autonomous Mission Policy
- May derive and edit: <goal-aligned areas eligible for full autonomy>
- Requires extra proof: <protected code areas are eligible with doctrine proof>
- Human review required: <work that may be implemented but must land as awaiting-review>
- Pre-action approval required: <work that must stop before implementation>
- Never unattended: <irreversible/external hard stops>

## Irreversible/External Hard Stops
- secrets/credentials
- destructive data operations
- releases
- repo visibility/remotes/default-branch changes
- force-pushes or deleting branches/tags
- real-world external side effects
```

Use `completion: incomplete` when the user chose `continue later` or left a load-bearing doctrine field unanswered. Set `intent_clarity: unresolved` while any intent file is incomplete or any blocking ambiguity-ledger unknown remains open. Item proof belongs to `execution_eligibility`, not doctrine metadata.

Doctrine can support item-level proof for protected code areas but cannot authorize execution or any irreversible/external hard stop. The enabled v1 bridge stops at a local awaiting-review branch and cannot publish.
