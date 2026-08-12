# Conditional self-merge policy and authorization schemas

> Status: closed data contracts with unused read-only observation, pure evaluation helpers, an
> inert two-snapshot readiness-proof contract, and an unreachable K4 journal/writer primitive. No
> credentialed observer, eligibility route, merge command, or writer composition is enabled.

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
- a host-selected snapshot lifetime from 1 to the shipped 60-second ceiling;
- one or more exact required check contexts, each paired with a numeric GitHub App id;
- one or more host-attested human reviewer actor ids and independent approvals, same-repository
  PRs, one PR, one merge intent, one sequential Goal, and synchronous squash only; and
- explicit acknowledgement of ordinary merge-triggered workflows and notifications.

Path patterns may contain glob syntax because they describe file scope. Repository, branch, check,
issuer, and stable-id fields reject glob identities.

## Run-authorization invariants

The authorization binds `conditional-merge` authority to one mission id, Goal Binding id, existing
mission-authorization id, policy id/hash, repository identity, base branch, and squash method. It
also binds the authenticated controller publication receipt and mission-state hash; the exact PR
id/node/number, head/base refs and SHAs; canonical diff, file-list, and Git-object evidence hashes;
and every implementation actor id. A closed controller Goal-risk binding must classify the work as
a low-risk code change and explicitly attest `false` for release, deployment, data mutation, and
real-world side effects. Its closed budget is one Goal, one concurrent Goal, one
same-repository PR, one merge intent, and one remaining merge intent. It has no pack id, queue,
parallel, fork, stack, or publication-target field.

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

These schemas and the pure evaluator are consumed only by the uncomposed K4 journal/executor. A
single-snapshot verdict is advisory and always has `intent_ready = false`. The evaluator applies the
earlier of host expiry, host policy age, and the 60-second shipped ceiling. Only its pure reread path can produce the closed,
canonical `merge-readiness-proof` binding two disjoint evidence hashes, request-audit hashes,
policy-read receipts, and observation windows. The v2 merge-intent/result schemas require that proof
hash instead of accepting a lone evidence hash. The K4 journal persists both complete evidence
documents—not only their summary fields—and replays the pure two-snapshot evaluator at the intent
timestamp. The intent also directly binds the controller diff, changed-file, and Git-object evidence
hashes plus the authenticated merge-credential receipt id/hash. The closed receipt records exact
repository selection, permissions, App/installation/account/bot identity, suspension, and issuance,
expiry, and host verification times. Each document hash, generated readiness proof, and intent binding must match exactly;
fabricated initial metadata or a proof outside either effective freshness window blocks. The
uncomposed K1 preview used schema version 1; K4 replaces those preview shapes with version 2 before
any production caller or durable production record exists. Consumers reject v1 merge intents and
results rather than guessing a migration.

The protected-policy input is either the byte-equivalent shipped baseline or a schema-valid
additive override anchored to that shipped baseline. A caller-supplied replacement baseline is
invalid even when its hash is internally consistent. The policy and evidence bind the resulting
effective registry hash.

The readiness document remains content-addressed data, not a self-authenticating cross-process
attestation. The K4 executor accepts it only through an injected authenticated host-envelope reader
whose contract requires a newly collected, host-authenticated envelope for the exact execution
instant; the executor rejects an older authentication timestamp and replays both snapshots. No
repository, CLI, or live reader implements that trust boundary. The v1 mission authorization enum
remains `none`, `local-branch`, or
`github-awaiting-review`; enabled host transition maps still contain no remote publication or merge
action. Terminal results carry a closed reason and exact squash proof: repository/PR/head/base,
single pre-merge base parent, post-merge base/commit, actor, merged and observed times, merge-status
observation, and unique request ids. The separate dispatch record distinguishes a durable intent
that never reached dispatch from an
ambiguous dispatched operation; only the atomic intent creator may write it, and reconciliation
never sends a second mutation. Because a durable local marker cannot be atomic with the remote
request, restarted reconciliation never credits a pending dispatched operation as merged even when
observation finds matching merged state. The fixture observer can supply a complete dry-run snapshot, while
the source REST and fixed-query GraphQL transports are not composed into a live collector. K5
composition still requires the separate security and enablement gates in the security contract.

The source-only publication prerequisite now produces the candidate input shape rather than relying
on a URL or branch discovery heuristic. Its closed request is authenticated outside repository
trust and embeds the full explicit GitHub-awaiting-review authorization. Its canonical hash binds
that authorization, one-PR ceiling, committed mission, repository, controller branch, exact
head/base SHAs, diff hashes, required check context/App identities, and authenticated publication
bot database/node/login identity. The backend must return the
identical target from read-only preflight before mutation, and the controller exposes no
caller-selected time override for authorization or envelope freshness. After successful required-check
observation, the write-once receipt adds the exact PR database id, node id, number, GitHub URL, and
one context/App/head-SHA tuple for every required check, plus a repository/ref/head-SHA push
attestation carrying the same bot identity. A pure uncalled reconciler validates the canonical
request/receipt pair and projects that actor only after a later fixed-query GraphQL snapshot matches
the exact repository, PR, head/base repositories, refs, and SHAs. The evidence schema pins the
compiled query hash and requires one actual `graphql-pull-request` request audit rather than
invented per-connection provenance. A pure uncalled projector requires complete latest-review,
review-request, and review-thread connections plus exact request/rate-limit audit coverage before
emitting normalized review/thread, mergeability, queue, and pagination inputs. The merge authorization candidate is a
direct projection of that receipt. Pending recovery is read-only and process death cannot leave the
journal lock around a remote callback; no CLI, enabled mission, or live backend currently produces
the receipt.
