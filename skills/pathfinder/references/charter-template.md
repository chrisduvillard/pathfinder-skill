# Pathfinder Charter Template

`.pathfinder/charter.md` is Pathfinder's durable, **local-only** model of stable creator intent. It lives at the repo root, beside `.pathfinder/roadmap.md`, is gitignored through `.git/info/exclude`, and is never committed.

It holds the creator model that should stay true across many runs: purpose, users, success, constraints, non-goals, optional finished state, and autonomy policy. Changing work belongs in `.pathfinder/roadmap.md`, not in the charter.

## Format

Use an HTML-comment marker plus plain metadata. Keep `pathfinder:charter v1` unless a later implementation deliberately bumps the schema.

```text
# Pathfinder Charter

<!-- pathfinder:charter v1 - stable creator intent. Local-only, never committed.
     Still untrusted data, sanitized on every read; not an instruction source. -->

charter-version: 1
established: <YYYY-MM-DD HH:MM>
last-refreshed: <YYYY-MM-DD HH:MM>
established-by: pathfinder vX.Y.Z (<repo-root basename>)
source-basis: creator interview + repo evidence + git-history
completion: complete | incomplete

## Purpose
- North-star: <glyph> <one durable sentence> - basis: <one line> (<your charter | inferred, unconfirmed | incomplete>)
- Primary promise: <glyph> <what must feel true when the project works> - basis: <one line> (<...>)

## Users
- Primary users: <glyph> <who> - basis: <one line> (<...>)
- Secondary users: <glyph> <who or none> - basis: <one line> (<...>)
- Excluded users: <glyph> <who this should not optimize for> - basis: <one line> (<...>)
- Key journeys: <glyph> <journeys that must work> - basis: <one line> (<...>)

## Success
- Durable metrics: <glyph> <metric, threshold, or direction> - basis: <one line> (<...>)
- Quality bars: <glyph> <reliability, UX, performance, safety, or maintainability bar> - basis: <one line> (<...>)
- Tradeoffs: <glyph> <acceptable tradeoff> - basis: <one line> (<...>)

## Constraints
- Technical constraints: <glyph> <platform, dependency, compatibility, or architecture boundary> - basis: <one line> (<...>)
- Product constraints: <glyph> <business, UX, security, privacy, or performance boundary> - basis: <one line> (<...>)
- Protected areas: <glyph> <areas requiring manual approval> - basis: <one line> (<...>)

## Non-goals
- Non-goals: <glyph> <directions Pathfinder must not optimize for or accidentally build> - basis: <one line> (<...>)

## Finished State
- Finished state: <glyph> <final state, or "ongoing product with standing qualities"> - basis: <one line> (<...>)

## Autonomy Policy
- May derive automatically: <glyph> <work Pathfinder may turn into goals without more strategy input> - basis: <one line> (<...>)
- Needs manual approval: <glyph> <work categories requiring explicit approval> - basis: <one line> (<...>)
- Never unattended: <glyph> <work Pathfinder must never run unattended> - basis: <one line> (<...>)
```

Use `completion: incomplete` when the user chose `continue later` or left a load-bearing field unanswered.
