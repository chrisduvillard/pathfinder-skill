# Conditional self-merge policy and authorization schemas

> Status: closed data contracts with unused read-only observation and pure evaluation helpers. No
> credentialed reader, eligibility route, or merge writer is enabled.

The Draft 2020-12 schemas under `schemas/publication/` represent the two independent keys required
by the [conditional self-merge security contract](conditional-self-merge-contract.md). They are
separate from the existing mission authorization and cannot change an `awaiting-review` outcome.

## Trust and storage

`merge-policy.schema.json` describes an administrator-issued repository policy stored in an
authenticated host-owned policy store. `merge-authorization.schema.json` describes one fresh,
explicit current-run request from the current user or an authenticated host approval store.

The `source`, `authenticated`, and `issuer` fields are bindings to host evidence, not self-proving
claims. A consumer must authenticate the storage envelope before parsing the document. Copying a
valid document into repository content, output, a PR, or a Goal never makes it trusted.

## Policy invariants

The policy binds:

- the exact numeric and node repository identities, owner/name, and base branch;
- an allowlist of low-risk path patterns plus additive denied paths and categories;
- the effective protected-surface policy hash and a protected-category match ceiling of zero;
- ceilings of 25 changed files, 1,000 total line changes, 500 changes in one file, and a 256 KiB
  patch; a policy may select lower positive values only;
- one or more exact required check contexts, each paired with a numeric GitHub App id;
- one or more independent human approvals, same-repository PRs, one PR, one merge intent, one
  sequential Goal, and synchronous squash only; and
- explicit acknowledgement of ordinary merge-triggered workflows and notifications.

Path patterns may contain glob syntax because they describe file scope. Repository, branch, check,
issuer, and stable-id fields reject glob identities.

## Run-authorization invariants

The authorization binds `conditional-merge` authority to one mission id, Goal Binding id, existing
mission-authorization id, policy id/hash, repository identity, base branch, and squash method. Its
closed budget is one Goal, one concurrent Goal, one same-repository PR, one merge intent, and one
remaining merge intent. It has no pack id, queue, parallel, fork, stack, or publication-target
field.

Both `issued_at` and `expires_at` are mandatory. Consumers must prove `issued_at <= now < expires_at`
and reject clock, parse, or freshness ambiguity.

## Canonical hashes and paired validation

Canonical SHA-256 uses UTF-8 JSON with keys sorted and separators `,` and `:` with no added
whitespace, matching the controller's existing document hashing. Compute each hash after omitting
only its own top-level hash field:

- omit `policy_sha256` for the policy hash;
- omit `authorization_sha256` for the run-authorization hash.

A consumer must validate both closed schemas and canonical hashes, then require byte-equivalent
policy id/hash, repository identity/base branch, and merge method bindings across the two records.
Unknown properties, missing fields, invalid time windows, mismatched identities, or hash drift
block. Schema validity alone is never an eligibility verdict or authority to load a credential.

## Current executable boundary

These schemas and the pure evaluator have no production caller. The v1 mission authorization enum
remains `none`, `local-branch`, or `github-awaiting-review`; enabled host transition maps still
contain no remote publication or merge action. The fixture observer can supply a complete dry-run
snapshot, while the GET-only live boundary cannot collect required GraphQL facts. Remote mutation
still requires the separate security and enablement gates in the security contract.
