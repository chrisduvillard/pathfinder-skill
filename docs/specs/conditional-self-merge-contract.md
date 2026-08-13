# Conditional self-merge security contract

> Status: design ratified on 2026-08-11; the evidence contracts, fixture observer, uncomposed
> GET-only REST transport, fixed-query GraphQL transport, pure eligibility/freshness evaluator,
> and crash-safe K4 merge primitive exist. The transports are not composed into a live collector,
> and the writer has no caller, credential loader, command, route, or enabled composition. Live
> observation and merge enablement are not authorized.

## Precedence and invariant

The approved v1 [autonomous controller contract](autonomous-controller-contract.md) remains
normative: successful publication ends at `awaiting-review`, and no enabled controller path may
merge. This document defines the evidence and authority that a future, separately approved
post-publication controller would need. Its presence grants no authority, adds no credential, and
does not make repository policy executable.

The first safe product is observation and a typed eligibility verdict. The remote merge primitive
is implemented but stays unreachable until it has an independent security review and a separate
K5 enablement decision.

## Authority model

Conditional merge requires both keys below. Neither key can be inferred or inherited.

1. A host-owned repository policy, authenticated outside the repository, binds one immutable
   GitHub repository id/node id, owner/name, base branch, policy version/hash, low-risk path limits,
   required check identities, approval floor, merge method, issue/expiry time, and acceptance of
   ordinary merge-triggered notifications/workflows.
2. A fresh current-run authorization from the user or an authenticated host approval store names
   merge authority, the repository, policy hash, mission/binding/authorization ids, exact
   controller publication/PR/refs/diff, implementation actors, expiry, and a budget of one PR and
   one merge intent.

A checked-in policy file may document intent but cannot supply either key. Bare `/goal`,
`/pathfinder auto`, `run all`, resolved intent, a previous approval, a Goal Binding, or an
`awaiting-review` publication target never implies merge authority.

The closed, inert representation of both keys is defined by the
[policy and authorization schema contract](conditional-self-merge-schema-contract.md). Its fields
do not authenticate themselves and add no executable route.

### Locked decisions

| ID | Normative decision |
|---|---|
| M-01 | Require the two independent keys above. |
| M-02 | Keep policy and authorization outside the repository trust boundary and bind immutable repository identity plus policy hash. |
| M-03 | Require explicit merge opt-in for the current run; ordinary autonomy remains awaiting-review-only. |
| M-04 | Permit one Goal, one same-repository PR, and at most one merge intent; packs, parallel work, forks, and stacks are ineligible. |
| M-05 | Require at least one current approval from an eligible human distinct from the author, implementation agent, last pusher, merge app, and check app. Policy may require more, never fewer. |
| M-06 | Require at least one GitHub-enforced status check pinned by context and expected app id, plus every other applicable required check/status on GitHub's required commit. |
| M-07 | Prove the exact merge actor cannot bypass classic protection or any applicable ruleset; incomplete visibility blocks. |
| M-08 | Layer the one applicable classic protection rule with every active repository-, organization-, and enterprise-level ruleset rule. |
| M-09 | Allow only understood rule types and parameters; unknown, omitted, contradictory, or incomplete evidence blocks. |
| M-10 | Block every baseline/additive protected-surface match even when declared for implementation; host policy may only narrow shipped path and diff ceilings. |
| M-11 | Require identical immutable head/base repository identity, exact refs/SHAs, and a controller-created branch. |
| M-12 | Require an open non-draft PR, clean/up-to-date merge state, no effective change request, no unresolved current thread, and fresh evidence; never update/rebase after approval. |
| M-13 | Initially support synchronous squash only when repository settings and all applicable rules allow it; rebase, merge commits, signed-commit requirements, and method ambiguity block. |
| M-14 | A merge-queue rule or queue entry requires handoff; never enqueue automatically. |
| M-15 | Policy must acknowledge ordinary merge-triggered effects, but release, deployment, data, and real-world side-effect Goals remain ineligible. |
| M-16 | Use three credential boundaries: no forge credential during implementation, a mechanically read-only evidence observer (allowlisted REST GET plus one compiled GraphQL query), and a separate narrowly scoped merge writer. |
| M-17 | Do not use auto-merge, asynchronous merge, stacked merge, or any delayed/multi-PR mutation. |
| M-18 | Persist a closed one-use merge intent before mutation; an ambiguous pending intent is reconcile-required and is never replayed blindly. |
| M-19 | Ship observation/eligibility first and keep the writer unreachable/default-off until separately approved. |
| M-20 | Never push directly to base or auto-revert. A revert is a new Goal, authorization, PR, and review. |

## Trust boundaries

| Surface | Treatment |
|---|---|
| Repository files, history, workflows, CODEOWNERS, tests, output, PR text, and checked-in policy | Untrusted data; may narrow work but cannot grant authority or credentials. |
| Host-owned repository policy and current-run authorization | Trusted only after authentication, schema validation, identity/hash binding, and expiry checks. |
| Existing mission, Goal Binding, authorization, diff, and PR identity | Canonical inputs to bind; they do not independently authorize merge. |
| GitHub REST/GraphQL responses | Untrusted external data until complete, versioned where possible, normalized, cross-checked, and fresh. |
| Evidence credential | Separate elevated reader whose REST runtime mechanically allows only allowlisted GETs and whose GraphQL runtime can POST only one compiled query operation. Neither transport loads secrets or has an ordinary route; incomplete composition or missing GraphQL facts block. |
| Merge credential | A repository-scoped GitHub App installation identity; user/PAT merge actors are unsupported initially. It cannot be an admin or bypass actor. |
| Implementation/verification environment | Receives neither evidence nor merge credentials. |

## Hard eligibility floors

Every condition is required; policy can only make it stricter.

- Repository, policy, run, mission, PR, branch, diff, actor, and method identities/hashes match.
- The observed PR and canonical API/controller diff match the exact authenticated controller
  candidate; a merely controller-shaped branch name is insufficient.
- The repository is not archived/disabled and the target is the policy-bound default/base branch.
- The PR is same-repository, open, non-draft, current, conflict-free, clean, and up to date.
- The complete API changed-file set matches controller evidence, stays inside the allowlist and
  strict file/line/size ceilings, and touches zero protected categories, symlinks, submodules,
  binaries, workflows, CODEOWNERS, or policy surfaces.
- GitHub itself enforces at least one independent human approval and one required check with an
  expected app id. The greater approval/check requirements from shipped policy, host policy,
  classic protection, and all active rulesets apply.
- Latest effective reviews are evaluated per reviewer. Only host-attested human actor ids can
  count. Author/agent/bot/app/last-pusher and every check creator,
  dismissed, stale, pending, and unknown-association reviews do not count. Any effective change
  request, required code-owner gap, or unresolved current thread blocks.
- Every required check/status is complete and successful on the exact head or test merge commit
  selected by GitHub. A same-name check run and commit status must both satisfy the requirement;
  context/app/SHA ambiguity blocks.
- Classic PR bypass allowances and every applicable ruleset bypass actor are visible. Every
  team, repository-role, or organization-admin actor has exactly one typed resolution bound to
  the same policy source, ruleset/mode where applicable, organization/repository, and exact merge
  bot id/login. Missing, duplicate, extra, pending, or identity-drifted resolutions are unknown.
  The exact merge App/installation matches none and has no administration permission.
- Only supported classic settings and ruleset rules are active. Merge queue, required deployment,
  required signature, code scanning/quality/coverage, file/metadata restriction, or an unknown
  rule is an initial typed blocker.
- A complete snapshot is no older than the shortest of host expiry, host-policy lifetime, and 60
  seconds. It includes a host-policy-store read receipt. A repository, actor, PR head/base,
  ruleset, review, check, diff, or policy change requires a complete new snapshot.

## GitHub API evidence map

All REST requests must send `Accept: application/vnd.github+json` and
`X-GitHub-Api-Version: 2026-03-10`. GitHub lists that REST version as supported in
[API Versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions?apiVersion=2026-03-10).
Persist request/response timestamps, request ids, pagination completion, and ETags where available.
For GraphQL, persist the exact query hash; absent fields and unknown enum values block.

| Evidence | Required endpoint/query and fields |
|---|---|
| API support | `GET /versions`; the pinned REST version must still be supported. |
| Repository identity/settings | `GET /repos/{owner}/{repo}`: `id`, `node_id`, `full_name`, owner id, `visibility`, `archived`, `disabled`, `default_branch`, merge-method flags, and permissions. [Repository endpoint](https://docs.github.com/en/rest/repos/repos#get-a-repository) |
| Merge App identity | With a separately protected App JWT, `GET /app` and `GET /app/installations/{installation_id}` (or exact repository installation): App id/node id/slug, installation id/account, repository selection, permissions, and suspension. Separately bind issued/expiry times from the host's access-token issuance receipt. User/PAT writers are unsupported. [GitHub App endpoints](https://docs.github.com/en/rest/apps/apps) |
| Exact PR | `GET /repos/{owner}/{repo}/pulls/{number}`: id/node id/number, state, draft/merged, author, head/base repo ids/refs/SHAs, mergeability, test/real `merge_commit_sha`, `merged_at`, `merged_by`, and changed-file totals. [Pull request endpoints](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request) |
| API diff | Fully paginate `GET /repos/{owner}/{repo}/pulls/{number}/files`: filename, previous filename, status, SHA, additions/deletions/changes. Cross-check the complete path set against an authenticated controller Git-diff receipt carrying regular/symlink/submodule and binary evidence; the observer derives special-file labels and the authorization binds its canonical hash. Missing or mismatched object evidence blocks. The endpoint's 3,000-file ceiling is above the hard policy ceiling; reaching any ceiling blocks. [PR files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files) |
| Classic protection | `GET /repos/{owner}/{repo}/branches/{base}/protection`: required checks and strict/app ids, `enforce_admins`, required review count, stale/code-owner/last-push rules, dismissal and bypass allowances, restrictions, linear history, signatures, and conversation resolution. [Protected branches](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection) |
| Applicable rules | Fully paginate `GET /repos/{owner}/{repo}/rules/branches/{base}`: every active rule's type, parameters, ruleset id/source/source type, allowed merge methods, review count, and pinned check identities. Disabled/evaluate-only rules do not satisfy a floor. Hash the normalized type/parameter set and require every fetched source ruleset to produce the same semantic hash. [Rules for a branch](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch) |
| Ruleset sources/bypass | Fully paginate `GET /repos/{owner}/{repo}/rulesets?includes_parents=true`, then each referenced ruleset: id/node id, source/source type, target, enforcement, conditions, rules, timestamps, and complete `bypass_actors` including actor id/type/mode. Omitted bypass actors are unknown, not empty. Cross-check GraphQL `RepositoryRuleset.bypassActors`, `conditions`, `rules`, `source`, and `updatedAt` when needed. [REST rulesets](https://docs.github.com/en/rest/repos/rules) · [GraphQL rulesets](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/repos#repositoryruleset) |
| Bypass membership | For each membership-based bypass actor, bind the exact merge bot id/login and policy source. The bypass-actor source projection must carry the exact team slug or repository-role name beside its id/mode; the resolution cannot supply that metadata independently. Resolve teams with `GET /orgs/{org}/teams/{team_slug}/memberships/{username}` and require `state: active`; resolve organization-admin actors with `GET /orgs/{org}/memberships/{username}` and require `state: active` plus `role: admin`; resolve repository-role actors by comparing GraphQL `repositoryRoleDatabaseId`/`repositoryRoleName` with the exact `role_name` from `GET /repos/{owner}/{repo}/collaborators/{username}/permission`. Every resolution binds one unique request id whose audit records the exact allowlisted target, `200`/qualified `404` status, and positive permission qualification; one audit cannot cover multiple resolutions. A permission of `none` is an authoritative no-match only when paired with no role name; a different non-null effective role remains unknown because it need not disprove every underlying role grant. Team/org `404` may become `absent` only inside a permission-qualified exact-endpoint backend; `403`, pending, missing role name, or ambiguous absence remains unknown. Organization-admin and deploy-key ruleset actors use GitHub's idless/null actor semantics rather than a fabricated numeric id. [Team membership](https://docs.github.com/en/rest/teams/members#get-team-membership-for-a-user) · [Organization membership](https://docs.github.com/en/rest/orgs/members#get-organization-membership-for-a-user) · [Repository permission](https://docs.github.com/en/rest/collaborators/collaborators#get-repository-permissions-for-a-user) · [GraphQL rulesets](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/repos#repositoryruleset) |
| Review decision/threads/queue | One paginated GraphQL PR query: `id`, `state`, `isDraft`, head/base OIDs and repositories, `mergeable`, `mergeStateStatus`, `reviewDecision`, `mergeQueueEntry`, latest opinionated reviews, review requests including `asCodeOwner`, and every review thread's `isResolved`/`isOutdated`. [GraphQL pull requests](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/pulls#pullrequest) |
| Review audit | Fully paginate `GET /repos/{owner}/{repo}/pulls/{number}/reviews` and `/requested_reviewers`: review id, actor id/login/type, state, `commit_id`, submission time, author association, requested users/teams. For every candidate human approval, read `GET /repos/{owner}/{repo}/collaborators/{username}/permission`, cross-check the returned user id, and require legacy `write` or `admin`; association alone is not permission evidence. [Reviews](https://docs.github.com/en/rest/pulls/reviews#list-reviews-for-a-pull-request) · [Review requests](https://docs.github.com/en/rest/pulls/review-requests#get-all-requested-reviewers-for-a-pull-request) · [Repository permission](https://docs.github.com/en/rest/collaborators/collaborators#get-repository-permissions-for-a-user) |
| Check runs | Fully paginate check suites/runs for GitHub's required SHA: run id/name, `head_sha`, status, conclusion, started/completed times, App id/slug, suite id, and PR head/base identities. Do not rely on the endpoint's 1,000-suite shortcut. [Check runs](https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference) |
| Commit statuses | Fully paginate `GET /repos/{owner}/{repo}/commits/{sha}/status`: combined state plus each id/context/state/creator/time and exact SHA. A combined green value alone is insufficient. [Commit statuses](https://docs.github.com/en/rest/commits/statuses#get-the-combined-status-for-a-specific-reference) |
| Deployments | If an active rule requires deployments, identify matching deployments by repository/environment/SHA and read their latest statuses through `GET /repos/{owner}/{repo}/deployments/{id}/statuses`; initial implementation still returns `unsupported-required-deployments`. [Deployment statuses](https://docs.github.com/en/rest/deployments/statuses#list-deployment-statuses) |
| Result/reconciliation | Future writer only: `PUT /repos/{owner}/{repo}/pulls/{number}/merge` with explicit `sha` and `merge_method: squash`. Reconcile with `GET .../pulls/{number}`, `GET .../pulls/{number}/merge`, and base ref/commit observations; require exact `merged`, `merge_commit_sha`, `merged_at`, and `merged_by`. [Merge endpoint](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request) |

All list/connection evidence must prove pagination completion. `401`, `403`, ambiguous `404`,
rate limit, timeout, `410`, malformed data, response truncation, or a missing permission/field returns
a typed blocker; none is evidence of absence.

### Implemented REST and fixed-query GraphQL source boundaries

The uncomposed evidence transport has one fixed network destination: TLS port 443 on
`api.github.com`. It exposes only `GET`, rejects `/graphql` and non-evidence endpoint paths, and
follows at most two redirects only when they remain HTTPS on that exact host. Every request fixes
the media type, REST version, and Pathfinder user agent. Responses are limited to 8 MiB each and
30 pages; duplicate JSON keys, unsafe pagination links, missing request ids, total-count drift,
and byte/page ceilings fail closed. One retry is allowed only for timeout or transient server
failure. Rate limits are never retried inside the freshness window.

The dedicated host process must inject a credential directly into the GET-only boundary; there is
no repository config, environment loader, CLI flag, logging hook, or general-purpose URL method.
An installation credential must declare `read` for repository `administration`, `checks`,
`contents`, `deployments`, `metadata`, `pull_requests`, and `statuses`, plus organization
`members`; any declared write permission is rejected. The allowlist includes only the exact
organization/team membership and repository-permission GET paths needed for typed bypass
resolution. A separately injected App JWT may read only App/installation identity and declares no
repository permissions. Credential and response-body representations are redacted.

The source now also has a closed canonical observer-token receipt for exact one-repository
selection, read permissions, App/installation/account/bot identity, suspension, and one-hour
issuance/expiry/verification. An uncalled verifier requires a fresh receipt and independently reads
the exact observer App, repository installation, bot, and repository. It separately validates the
future merge credential receipt and reads the merge App, exact repository installation, and bot;
the observer token never substitutes for the merge actor. The source collector now consumes both
verified identities at one trusted observation instant: observer audits prove the read boundary,
while the verified merge actor alone drives bypass-membership reads and the evidence actor. The
externally authenticated v3 artifact stores both non-secret receipts and binds evidence/provenance
to the merge receipt. It contains no merge token and installs no credential reader.

For private-plan feature absence, the GET boundary accepts `403` only through a dedicated closed
method for classic protection, active branch rules, or source rulesets. It requires the exact
allowlisted endpoint, the endpoint-specific read permission in GitHub's
`X-Accepted-GitHub-Permissions` response header, the exact upgrade-required message, a closed error
shape/status, and a GitHub REST documentation URL. Every other `403` remains
`permission-missing`; an ordinary GET cannot opt into this exception.

GitHub's ordinary GraphQL queries use HTTP
`POST`, so the REST boundary remains strictly GET-only. A separate source-only transport can POST
only the compiled `PathfinderPullRequestEvidence` query to `/graphql`; callers supply only the
owner, repository, PR number, and bounded cursors. Its canonical query hash is fixed in source. It
collects exact PR/ref/mergeability/review-decision/queue identity plus independently paginated
latest reviews, code-owner review requests, and review threads, and rejects partial data, GraphQL
errors, unknown fields/enums, identity or total-count drift, repeated request ids/items/cursors,
missing request ids, and byte/page ceilings. It accepts only the exact read-only installation
credential declaration and exposes no arbitrary query, mutation, URL, environment loader, or
enabled caller. The merge-evidence schema pins this exact compiled query hash and requires a real
`graphql-pull-request` audit; separate synthetic review-request/thread audits cannot substitute for
the single query that supplied all three connections.

The source now also has uncalled bypass-membership, review, and check-evidence readers. Team and
organization `404` become absence only on the exact endpoint with GitHub's `Members=read`
qualification; repository-role reads require `Metadata=read`, exact bot identity, and preserve all
six GitHub permission levels so `maintain`/`triage` cannot be silently collapsed into `write`.
Every resolution has a unique request audit. REST reviews are fully paginated, each unique actor's
current repository permission is read once with positive `Metadata=read` evidence, and the returned
id/login must match the review actor. Check collection lists every suite for the exact SHA, then
paginates runs per suite instead of using GitHub's 1,000-suite shortcut. It reads the combined
`/status` envelope, fully paginates the creator-bearing `/statuses` history, derives the latest item
per context, and cross-checks the derived count/state against the exact repository id/name and SHA
in the combined response. Required evidence is marked only from a closed context/App union supplied
by the future policy composer, and each required run must include the exact supplied candidate PR
database id/number plus head/base repository ids, refs, and SHAs. One global request ceiling covers
suites, runs, and both status reads; duplicate suite/run/status/request ids and
repository/PR/SHA/suite/state drift fail closed.

The source-only policy projector forms the check union from the non-empty host-policy floor, one
permission-qualified classic-protection response, and every rule in a complete active-rules page
set. It rejects unpinned/null/any-App requirements, classic context/check disagreement, duplicate
rule identities, malformed source attribution, unknown check fields, and incomplete or
request-id-ambiguous pagination. The projector has no caller and is not authority to read a policy
or install the collector.

The source-only review reconciler selects the last `APPROVED`, `CHANGES_REQUESTED`, or `DISMISSED`
record per actor from the complete chronological permission-qualified REST audit and requires the
complete GraphQL `latestOpinionatedReviews` actor set to match it exactly by review database/node id,
actor database/node/login/type, state, commit SHA, submission instant, and association. Later
`COMMENTED` records do not replace an earlier opinion. Missing/extra actors, malformed permission
bindings, identity drift, nonchronological history, incomplete pagination, duplicate identities, or
cross-protocol request-id reuse block. This pure check has no caller and does not compose review
requests, threads, or a complete snapshot.

The source-only publication reconciler validates the canonical authenticated publication request
and terminal receipt together, including the request's publication bot database/node/login identity
and the receipt's exact repository/ref/SHA push attestation. It then requires a fixed-query GraphQL
observation at or after publication whose repository, PR database/node/number, head/base repository,
refs, and SHAs are identical, and projects the controller bot database id for `last_pusher_id`.
Malformed documents, hash drift, request/receipt actor drift, stale observations, query drift,
duplicate request ids, or object/ref/SHA drift block. This pure check has no caller and does not
authenticate host storage or prove exclusive branch ownership against a later same-SHA push.

A separate pure source-only ownership prover closes that missing proof shape. It accepts only a
canonical one-repository publication credential receipt whose bot identity matches the reconciled
pusher; one active repository branch ruleset dedicated to restricting creation, update, and
deletion; exactly that publication App as the sole `always` bypass actor; the complete effective
rules returned for the exact controller branch; and a final qualified ref read at the published
SHA. Ruleset, effective-rule, and ref requests must be unique, ordered, permission-qualified, and
at or after the evidence completion instant. Missing rules, another bypass actor, fetch-and-merge,
stale or incomplete reads, endpoint drift, request reuse, or identity/SHA drift block. The proof
has no client, credential loader, storage, command, or installed caller.

The source-only GraphQL projector requires the exact publication-pusher proof and the identical
repository, PR database/node/number, head/base repositories, refs, and SHAs. It accepts only the
schema-pinned query hash, complete latest-review/review-request/review-thread connections, unique
closed reviewer and thread identities, and one request audit plus rate-limit record per actual
GraphQL response. It emits the normalized review-request/thread, mergeability/queue, pagination,
and shared `graphql-pull-request` audit inputs. Incomplete connections, synthetic per-surface audit
coverage, query drift, identity drift, duplicate reviewers/threads/request ids, or audit-count/time
drift block. This projector is pure, uncalled, and not a complete snapshot composer.

One pure source-only composer now binds these primitives together. It requires the verified
one-repository observer receipt and all four App/installation/bot/repository audits, the separately
verified merge receipt and three App/installation/bot audits, the canonical
publication request/receipt pair, the fixed-query GraphQL snapshot, the complete permission-
qualified REST review history, host/classic/ruleset required-check union, exact check/status pages,
every remaining normalized REST family, and the canonical controller-branch ownership proof. It
emits one schema-valid evidence document plus a
separately hashed provenance receipt bound to the evidence hash, observer/merge/publication receipt
hashes, ownership proof, query hash, reconciled review ids, required checks, request-id hash, and
collection window. Cross-surface request reuse or any split identity/policy/review/check/ownership
input blocks. The composer owns no client, credential, storage, command, or caller, so it is not an
installed production collector. A separate source-only store now defines the durable boundary: one
closed externally authenticated input envelope first binds the exact journal, all three non-secret
credential receipts, operator authority, protected policy, policy-read receipt, full Git-object
evidence, repository, evidence id, store id, and trusted collection-start time. The collector
verifies that canonical envelope through the injected authenticator before parsing nested documents
or making any GitHub read; loose, stale, re-hashed, wrong-store, or unauthenticated inputs block.
After collection, one
immutable externally authenticated v3 envelope contains the exact publication journal, operator
policy/current-run authorization/protected policy, publication, observer, and non-secret merge
credential receipts,
ownership proof, evidence, and provenance. It independently rechecks their canonical/effective
hashes and complete cross-document identities, uses a pinned owner-only POSIX host
directory outside repository trust, and rejects partial, replaced, renamed, re-hashed, wrong-store,
or unauthenticated records. One unconstructed read-only adapter accepts two explicit evidence ids,
re-verifies both envelopes, and rejects publication, authority, or authenticator/key drift. The
package ships no authenticator implementation/key loader or route that constructs the adapter;
Windows fails closed pending equivalent ACL proof. An installed trusted
host must still inject the authenticator and live collector and persist these facts rather than UI
text. Conditional merge therefore remains unsupported for live use.

## Typed block and result contract

At minimum the observer/evaluator must distinguish:

- `policy-missing`, `policy-expired`, `authorization-missing`, `authorization-expired`,
  `identity-drift`, `diff-drift`, `protected-surface`, and `diff-limit-exceeded`;
- `classic-protection-unknown`, `ruleset-evidence-incomplete`, `ruleset-drift`,
  `bypass-visibility-unknown`, `merge-actor-can-bypass`, and `unsupported-active-rule`;
- `independent-review-not-enforced`, `independent-review-missing`, `changes-requested`,
  `code-owner-review-missing`, `unresolved-thread`, and `review-drift`;
- `required-check-unproven`, `required-check-pending`, `required-check-failed`,
  `unexpected-check-app`, `check-sha-drift`, and `check-evidence-incomplete`;
- `draft`, `fork`, `base-behind`, `merge-conflict`, `merge-state-unknown`,
  `merge-queue-required`, `unsupported-required-deployments`, and `unsupported-merge-method`;
- `auth-error`, `rate-limited`, `permission-missing`, `api-unavailable`, `policy-blocked`,
  `reconcile-required`, `not-merged`, and `merged`.

`eligible` on one snapshot is a dry-run verdict, not authority and not a merge result. Only a
schema-valid `intent-ready` proof from two complete, ordered, disjoint snapshots can be bound by a
future intent.

### Implemented pure eligibility evaluator

The unused evaluator accepts only a closed host policy, current-run authorization, the exact
effective protected-surface policy document, a normalized evidence snapshot, and an offset-aware
evaluation time. It validates the closed schemas and
canonical hashes, authority/repository/mission bindings, validity windows, request audits,
pagination counts, snapshot completeness, exact authenticated controller candidate, controller
Git-object receipt, diff hashes and totals, repository and PR state, independently recomputed
path/protected/special-surface ceilings, the one classic layer plus all active
rulesets, source-rule semantic hashes, allowed squash methods, bypass visibility, exact-coverage
typed team/repository-role/organization-admin membership resolution, review decision,
latest effective permission-qualified and host-attested independent-human reviews, current
threads/requests, check-creator exclusion, and exact check context/App/SHA/status proof. Inputs are
never mutated.

The classic layer exposes its safety-relevant settings as closed normalized fields rather than
trusting only an opaque settings hash: stale-review dismissal, code-owner review, linear history,
required signatures, push restrictions, and review-dismissal restrictions. Unknown values block.
Required signatures are typed unsupported; active classic code-owner or restriction semantics are
also unsupported until evidence can attribute and evaluate them without guessing. Squash satisfies
an explicit linear-history requirement, while commit-SHA-pinned review evidence makes either known
stale-review setting evaluable.

The protected-surface baseline is loaded from the shipped registry. The evaluator accepts only that
exact baseline or a schema-valid additive override tied to its policy id; a weaker caller-provided
replacement baseline is invalid even if the caller recomputes every downstream hash.

Restrictions form one AND-only lattice: shipped floors, host policy, classic protection, and every
active ruleset can add requirements but cannot cancel an earlier requirement. Required checks are
unioned and the approval floor is the maximum. Typed outcome precedence is `unknown`, then
`unsupported`, then `policy-blocked`, then `eligible`; all discovered blocks remain in the verdict
even when a higher-precedence outcome wins. Blocks and proof summaries are deterministically
ordered.

The evaluator has no credential, network, filesystem mutation, or merge method. Its only production
consumers are the uncomposed K4 journal/executor boundary. The complete fixture can produce
`eligible`; the source now has both REST GET-only and GraphQL fixed-query primitives, but no trusted
host composes them into the required complete live snapshot. Live conditional merge therefore
remains unsupported, and no ordinary `/goal`, mission, publication, or resume path evaluates or
acts on a verdict.

Snapshot validity ends at the earliest of the authenticated host's `expires_at`, the policy's
maximum age, and exactly 60 seconds after `observed_at`; `completed_at`, the policy read, and every
request audit must stay inside that window. Thus a host can shorten the lifetime but cannot extend
the shipped ceiling. The pure reread path
independently evaluates an initial and final complete snapshot. The final collection must begin
strictly after the first completes and have a new evidence id/hash, policy-read receipt, and
disjoint request ids for the full required surface. It compares whole normalized authority/policy
binding, repository, actor, PR
head/base and merge state, diff, classic/ruleset/bypass-membership, review/decision, check, and completeness domains.
Any mismatch is typed unknown and invalidates the attempt; consumers must start a new complete
two-snapshot cycle and may not patch or retain an earlier green domain. Success returns a distinct,
immutable, closed, canonical readiness proof binding both snapshots; failure returns no proof.
The K4 journal retains both complete evidence documents and reproduces the same proof by running
this evaluator at the intent time. Summary-only snapshot metadata is insufficient. A proof
that has crossed a process boundary is still untrusted until its host-owned storage or attestation
envelope is authenticated.

## Implemented unreachable mutation and crash reconciliation

The prerequisite publication boundary is also source-only and uncomposed. A fresh authenticated
host request embeds and canonically binds the full explicit GitHub-awaiting-review authorization,
its one-PR ceiling, one committed mission, repository, controller branch, exact head/base SHAs,
canonical diff/file/object hashes, required check context/App identities, and the authenticated
publication credential's bot database/node/login identity. It is journaled before
the injected publication-only backend may act. That backend must first perform a read-only preflight
and return the identical repository/ref/commit/diff/check target; mismatch blocks before push or PR
creation. Neither publication nor reconciliation accepts a caller-selected timestamp; freshness
and observation time come only from the injected authenticated-host clock. Successful
awaiting-review publication writes a closed authenticated receipt containing
repository identity plus PR database id, node id, number, URL, exact refs/SHAs, mission-state and
authorization hashes, diff, the publication bot identity bound to the exact repository/ref/SHA
push, and each successful check's exact context, App id, and head SHA. The
write-once dispatch marker is persisted under lock, then the lock is released before the remote
callback so actual process death cannot strand reconciliation. A pending request cannot be
published again; explicit recovery can only find the same exact PR and observe checks. No installed
or ordinary route constructs this controller, and no live backend currently implements the trusted
preflight.

Independent source review of this boundary is complete. That closes a code-review prerequisite,
not an operational one: there is still no installed authenticated envelope reader, exact live
backend, complete live evidence collector, operator policy/credential store, or zero-merge
publication/evidence rehearsal in a disposable repository. The later composed merge rehearsal is a
separate K6 gate. K5 therefore remains closed and the default CLI exposes no merge surface.

Before the unreachable primitive can issue its one remote call, an atomic one-use claim persists a
write-once intent and binds the two-snapshot readiness-proof hash,
both evidence ids/hashes, policy and authorization hashes; repository and PR ids; exact head/base
SHAs; all three controller diff hashes; merge App/installation; squash method; endpoint class; start
time; authenticated credential-receipt id/hash; and one-use operation id. The journal rejects the
same authorization or readiness proof under another operation id. A single advisory verdict is
never accepted. Only the process that creates the intent claim receives the process-local
capability required to enter one combined dispatch-and-send boundary. That boundary holds the
journal lock while the backend prepares the fixed request, then lets that backend persist
`dispatch-started` only at its final pre-transport boundary before the one synchronous, SHA-bound
request. There is no separately callable dispatch marker. A preparation crash therefore remains
known-zero-send, while any failure after the marker is conservatively ambiguous. Concurrent,
second-instance, or restarted execution never sends another request.

The executor accepts the dedicated GitHub App installation token only from an injected fresh,
authenticated host credential reader. Its closed receipt positively records selected-one-repository
scope; exactly `contents: write`, `pull_requests: read`, and implicit `metadata: read`; App,
installation/account, and bot identities; suspension state; issuance/expiry; and verification time.
The receipt is persisted and bound into the intent. User/PAT credentials, administration access,
extra repositories or permissions, stale/self-declared receipts, environment loading, arbitrary
URLs, redirects, and generic HTTP methods are rejected. Its actor/App/installation identity must
exactly match the final K3 evidence and intent. No live reader or token loader is installed.

The current-run authorization additionally carries an authenticated controller Goal-risk binding.
Only `low-risk-code-change` with release, deployment, data mutation, and real-world-side-effect
flags all false can validate. This makes the existing hard-stop class representable before merge
eligibility is evaluated; repo content cannot mint the binding.

`merged` requires a successful response plus exact follow-up observation, or exact follow-up proof
within the same live execution after a typed lost response. After a process restart, a dispatch
record with no terminal result is permanently `reconcile-required`: observation may aid a human,
but it can never attribute or credit the merge because the crash may have occurred after the local
marker and before the remote request. The proof binds the repository and PR ids, head SHA, base ref, pre-merge base
as the squash commit's single parent, post-merge base as the merge commit, merge endpoint status,
merge actor, request ids, and ordered timestamps. `409`, `405`, malformed success, connection loss,
or PR closure never implies success. A pending intent without exact merged proof becomes
`reconcile-required` and sends no second `PUT`. An intent with no `dispatch-started` record is
terminally classified `dispatch-not-started` without observing or crediting a merge. A completed
merge is forward-only; the primitive
never deletes the branch, comments, deploys, releases, pushes directly to base, or automatically
reverts.

Crash fixtures cover failure before intent, after intent/before dispatch, during request
preparation, after dispatch/remote effect before response, after response/before result, and after
terminal persistence. An explicit reconciliation entry point performs observation only, never
credits a restarted pending operation as merged, and has no mutation method. Repository search proves no CLI,
mission, Goal pack, publisher, host bridge, or installed route constructs `MergeExecutor`.

## Residual race

GitHub's synchronous merge request atomically binds the PR head through `sha`; it does not bind the
base SHA, protection response, ruleset versions, reviews, checks, or policy snapshot. Pathfinder
must minimize this time-of-check/time-of-use window with an immediate complete reread and a
non-bypass merge actor. A trusted repository administrator changing control-plane policy after the
final reread remains an explicit residual risk, not a solved guarantee. The pure reread comparison
detects change between two observations; it does not claim that GitHub freezes those observations
between the last response and a future merge request.

## Explicit non-goals

- Autonomous/self approval or counting any bot/app as the independent human.
- Repo-local authority, Goal packs, parallel/derived work, forks, stacks, or arbitrary PR discovery.
- Protected-surface merges, releases, deployments, migrations, destructive data changes, or
  real-world side effects.
- Merge queues, auto-merge, asynchronous/stacked merge, rebase, merge commits, signed-commit
  support, branch deletion, direct base pushes, or automatic revert in the first release.
- Another forge, a GitHub UI scraper, or UI text used as machine evidence.
- A claim that client-side evidence is atomically bound to all GitHub control-plane state.

## Ratification evidence

`GitHubPublisher` still exposes only `push`, exact PR lookup/creation, and check polling; its backend
protocol and production callers contain no merge method. The K4 backend is separate, and only the
uncomposed executor can call it. The enabled mission host and Goal-pack transition maps emit no push,
PR, remote-publication, or merge action; the generic host protocol's unused `publish` enum grants no
caller or transition. Existing awaiting-review behavior remains unchanged.
