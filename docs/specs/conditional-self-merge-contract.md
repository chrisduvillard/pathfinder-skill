# Conditional self-merge security contract

> Status: design ratified on 2026-08-11; implementation and enablement are not authorized.

## Precedence and invariant

The approved v1 [autonomous controller contract](autonomous-controller-contract.md) remains
normative: successful publication ends at `awaiting-review`, and no enabled controller path may
merge. This document defines the evidence and authority that a future, separately approved
post-publication controller would need. Its presence grants no authority, adds no credential, and
does not make repository policy executable.

The first safe product is observation and a typed eligibility verdict. A remote merge writer stays
unreachable until it has an independent security review and a separate enablement decision.

## Authority model

Conditional merge requires both keys below. Neither key can be inferred or inherited.

1. A host-owned repository policy, authenticated outside the repository, binds one immutable
   GitHub repository id/node id, owner/name, base branch, policy version/hash, low-risk path limits,
   required check identities, approval floor, merge method, issue/expiry time, and acceptance of
   ordinary merge-triggered notifications/workflows.
2. A fresh current-run authorization from the user or an authenticated host approval store names
   merge authority, the repository, policy hash, mission/binding/authorization ids, expiry, and a
   budget of one PR and one merge intent.

A checked-in policy file may document intent but cannot supply either key. Bare `/goal`,
`/pathfinder auto`, `run all`, resolved intent, a previous approval, a Goal Binding, or an
`awaiting-review` publication target never implies merge authority.

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
| M-16 | Use three credential boundaries: no forge credential during implementation, an enforced GET-only evidence observer, and a separate narrowly scoped merge writer. |
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
| Evidence credential | Separate elevated reader whose runtime must mechanically allow only the required GET/GraphQL reads. |
| Merge credential | A repository-scoped GitHub App installation identity; user/PAT merge actors are unsupported initially. It cannot be an admin or bypass actor. |
| Implementation/verification environment | Receives neither evidence nor merge credentials. |

## Hard eligibility floors

Every condition is required; policy can only make it stricter.

- Repository, policy, run, mission, PR, branch, diff, actor, and method identities/hashes match.
- The repository is not archived/disabled and the target is the policy-bound default/base branch.
- The PR is same-repository, open, non-draft, current, conflict-free, clean, and up to date.
- The complete API changed-file set matches controller evidence, stays inside the allowlist and
  strict file/line/size ceilings, and touches zero protected categories, symlinks, submodules,
  binaries, workflows, CODEOWNERS, or policy surfaces.
- GitHub itself enforces at least one independent human approval and one required check with an
  expected app id. The greater approval/check requirements from shipped policy, host policy,
  classic protection, and all active rulesets apply.
- Latest effective reviews are evaluated per reviewer. Author/agent/bot/app/last-pusher,
  dismissed, stale, pending, and unknown-association reviews do not count. Any effective change
  request, required code-owner gap, or unresolved current thread blocks.
- Every required check/status is complete and successful on the exact head or test merge commit
  selected by GitHub. A same-name check run and commit status must both satisfy the requirement;
  context/app/SHA ambiguity blocks.
- Classic PR bypass allowances and every applicable ruleset bypass actor are visible. The exact
  merge App/installation matches none and has no administration permission.
- Only supported classic settings and ruleset rules are active. Merge queue, required deployment,
  required signature, code scanning/quality/coverage, file/metadata restriction, or an unknown
  rule is an initial typed blocker.
- A complete snapshot is no more than 60 seconds old. A repository, actor, PR head/base, ruleset,
  review, check, diff, or policy change requires a complete new snapshot.

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
| API diff | Fully paginate `GET /repos/{owner}/{repo}/pulls/{number}/files`: filename, previous filename, status, SHA, additions/deletions/changes. The endpoint's 3,000-file ceiling is above the hard policy ceiling; reaching any ceiling blocks. [PR files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files) |
| Classic protection | `GET /repos/{owner}/{repo}/branches/{base}/protection`: required checks and strict/app ids, `enforce_admins`, required review count, stale/code-owner/last-push rules, dismissal and bypass allowances, restrictions, linear history, signatures, and conversation resolution. [Protected branches](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection) |
| Applicable rules | Fully paginate `GET /repos/{owner}/{repo}/rules/branches/{base}`: every active rule's type, parameters, ruleset id/source/source type. Disabled/evaluate-only rules do not satisfy a floor. [Rules for a branch](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch) |
| Ruleset sources/bypass | Fully paginate `GET /repos/{owner}/{repo}/rulesets?includes_parents=true`, then each referenced ruleset: id/node id, source/source type, target, enforcement, conditions, rules, timestamps, and complete `bypass_actors` including actor id/type/mode. Omitted bypass actors are unknown, not empty. Cross-check GraphQL `RepositoryRuleset.bypassActors`, `conditions`, `rules`, `source`, and `updatedAt` when needed. [REST rulesets](https://docs.github.com/en/rest/repos/rules) · [GraphQL rulesets](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/repos#repositoryruleset) |
| Review decision/threads/queue | One paginated GraphQL PR query: `id`, `state`, `isDraft`, head/base OIDs and repositories, `mergeable`, `mergeStateStatus`, `reviewDecision`, `mergeQueueEntry`, latest opinionated reviews, review requests including `asCodeOwner`, and every review thread's `isResolved`/`isOutdated`. [GraphQL pull requests](https://docs.github.com/en/enterprise-cloud@latest/graphql/reference/pulls#pullrequest) |
| Review audit | Fully paginate `GET /repos/{owner}/{repo}/pulls/{number}/reviews` and `/requested_reviewers`: review id, actor id/login/type, state, `commit_id`, submission time, author association, requested users/teams. [Reviews](https://docs.github.com/en/rest/pulls/reviews#list-reviews-for-a-pull-request) · [Review requests](https://docs.github.com/en/rest/pulls/review-requests#get-all-requested-reviewers-for-a-pull-request) |
| Check runs | Fully paginate check suites/runs for GitHub's required SHA: run id/name, `head_sha`, status, conclusion, started/completed times, App id/slug, suite id, and PR head/base identities. Do not rely on the endpoint's 1,000-suite shortcut. [Check runs](https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference) |
| Commit statuses | Fully paginate `GET /repos/{owner}/{repo}/commits/{sha}/status`: combined state plus each id/context/state/creator/time and exact SHA. A combined green value alone is insufficient. [Commit statuses](https://docs.github.com/en/rest/commits/statuses#get-the-combined-status-for-a-specific-reference) |
| Deployments | If an active rule requires deployments, identify matching deployments by repository/environment/SHA and read their latest statuses through `GET /repos/{owner}/{repo}/deployments/{id}/statuses`; initial implementation still returns `unsupported-required-deployments`. [Deployment statuses](https://docs.github.com/en/rest/deployments/statuses#list-deployment-statuses) |
| Result/reconciliation | Future writer only: `PUT /repos/{owner}/{repo}/pulls/{number}/merge` with explicit `sha` and `merge_method: squash`. Reconcile with `GET .../pulls/{number}`, `GET .../pulls/{number}/merge`, and base ref/commit observations; require exact `merged`, `merge_commit_sha`, `merged_at`, and `merged_by`. [Merge endpoint](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request) |

All list/connection evidence must prove pagination completion. `401`, `403`, ambiguous `404`,
rate limit, timeout, `410`, malformed data, response truncation, or a missing permission/field returns
a typed blocker; none is evidence of absence.

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

`eligible` is a dry-run verdict, not authority and not a merge result.

## Future mutation and crash reconciliation

Before any future remote call, a write-once intent must bind policy, authorization and evidence
hashes; repository and PR ids; exact head/base SHAs; diff; merge App/installation; squash method;
endpoint class; start time; and one-use operation id. The executor may send one synchronous,
SHA-bound request only.

`merged` requires a successful response plus exact follow-up observation, or exact follow-up proof
after a lost response. `409`, `405`, malformed success, connection loss, or PR closure never implies
success. A pending intent without exact merged proof becomes `reconcile-required` and sends no
second `PUT`. A completed merge is forward-only; the controller never deletes the branch,
comments, deploys, releases, pushes to base, or automatically reverts.

## Residual race

GitHub's synchronous merge request atomically binds the PR head through `sha`; it does not bind the
base SHA, protection response, ruleset versions, reviews, checks, or policy snapshot. Pathfinder
must minimize this time-of-check/time-of-use window with an immediate complete reread and a
non-bypass merge actor. A trusted repository administrator changing control-plane policy after the
final reread remains an explicit residual risk, not a solved guarantee.

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

At ratification, `GitHubPublisher` exposes only `push`, exact PR lookup/creation, and check polling;
its backend protocol and production callers contain no merge method. The only fixture `merge`
method raises if called, and tests assert zero attempts. The enabled mission host and Goal-pack
transition maps emit no push, PR, remote-publication, or merge action; the generic host protocol's
unused `publish` enum grants no caller or transition. Existing no-self-merge behavior guards and
awaiting-review contracts remain unchanged.
