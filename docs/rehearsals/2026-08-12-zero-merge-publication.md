# Zero-merge publication and evidence rehearsal

Date: 2026-08-12

This record covers the bounded external-host prerequisite rehearsal for conditional-merge work. It
does not enable merge, add a packaged caller, or authorize K5.2. Credentials and full evidence stay
in operator-owned storage outside every repository; this document contains only non-secret facts and
hashes.

## Completed controls

- [x] Use the private disposable repository
  `Chris-Archive-Archive/pathfinder-merge-rehearsal`, not a production repository.
- [x] Keep repository merge configuration squash-only, with auto-merge and automatic branch deletion
  disabled.
- [x] Keep the repository Actions token read-only and unable to approve pull requests.
- [x] Create a private publication App with only Checks read, Contents write, Metadata read, and Pull
  requests write.
- [x] Create a separate private observation App with only Administration, Checks, Contents,
  Deployments, Members, Metadata, Pull requests, and Statuses read.
- [x] Install both Apps on only the disposable repository.
- [x] Create no merge App, install no merge credential, and issue no merge request.
- [x] Keep private keys outside repositories with owner-only file permissions.
- [x] Start from exactly one remote base branch and zero pull requests, deployments, and releases.
- [x] Bind the publication request to repository id/node, exact base/head refs and SHAs, all three diff
  hashes, one controller branch, one PR ceiling, and the pinned `rehearsal-check` / GitHub Actions App
  identity.
- [x] Run the real crash-safe publication controller through an external host adapter; it pushed the
  exact candidate, created PR 1, observed the exact successful check, and persisted an
  `awaiting-review` receipt.
- [x] Replay the same publication request without a second push, PR, or check-poll sequence.
- [x] Collect two independent complete live REST/GraphQL evidence snapshots through the read-only App.
- [x] Observe 16 disjoint request ids in each snapshot, no unknown or unsupported fields, and no drift
  across authority, repository, actor, PR, diff, policy/rules, reviews, checks, or completeness.
- [x] Match both live diff projections to the persisted publication receipt.
- [x] Prove the private Free-plan repository cannot enable classic protection or rulesets: the exact
  qualified endpoints returned GitHub's upgrade-required response, so the external host recorded an
  absence proof and the candidate remains policy-blocked.
- [x] Finish with one open, unmerged PR, two branches, zero deployments, and zero releases.

## Non-secret evidence anchors

- Publication receipt: `publication_receipt_rehearsal_20260812`
  (`7e089d7a1b5075bc4e8cea0c54db80b7ef273b04cbc433972e6e5d89d049507b`).
- Pull request: `https://github.com/Chris-Archive-Archive/pathfinder-merge-rehearsal/pull/1`.
- Base SHA: `11dbc49df3c6f5f44fc588c7ac315870c36a2064`.
- Head SHA: `5e9a7f0a5807ae2d9bc3d3701d9b7409d4d195c1`.
- Initial evidence: `merge_evidence_rehearsal_initial`
  (`98b9073d7818f4661d901d3fafa24c0bc992c77e3c10dc0df327b8ce1ac478e3`).
- Reread evidence: `merge_evidence_rehearsal_reread`
  (`2fcec6fd6ae9146a4aa2fddd0380dffbb3cf3e27009b7bff35cde3ea49a6f4ae`).

## Remaining gates and improvements

- [ ] Turn the one-off external publication adapter into a reviewed, installed trusted-host boundary;
  do not weaken the package guard or add it to ordinary `/goal`, `/pathfinder`, auto, pack, or resume
  routes.
- [x] Add a source-only orchestration boundary that shares one observer installation credential
  across the fixed identity, GraphQL, review, and check readers; eagerly closes the observation
  window before branch-ownership proof; composes canonical evidence/provenance; and persists the
  exact externally attested envelope without requiring any merge credential.
- [x] Add source-only exact candidate/diff/deployment and controller-branch ownership readers. They
  share the observer credential, fail closed on identity/ref/patch/visibility drift, and remain
  unconstructed outside the source collector boundary.
- [ ] Supply the remaining normalized classic-protection/ruleset/membership backend from a trusted
  installed host and construct the source readers there. The package still has no credential
  loader, authenticator/key implementation, command, or route.
- [ ] Define an operator-owned, schema-valid merge policy outside repository trust. The rehearsal used
  an explicit non-authorizing dry-run binding so it could not be mistaken for merge authority.
- [ ] Keep current-run merge authorization absent until an actual merge evaluation or execution is
  separately and explicitly requested.
- [x] Implement K5.1 as observation-only status/evaluation; it loads no writer credential, creates
  no merge intent, and remains awaiting-review even when eligible.
- [x] Obtain a separate independent K5.1 review; independent standards and adversarial
  security/spec reviews are clean after remediation, with direct counterexample probes retained as
  regressions.
- [ ] Keep K5.2 closed until its separate specialized-agent security quorum and explicit user
  authorization. Repeated implementation or rehearsal approval is not merge approval.
- [ ] If a later composed merge rehearsal is approved, use a newly bounded authorization and fresh
  evidence cycle; never reuse these expired snapshots.
- [ ] Decide whether to retain or manually remove the disposable PR, branch, Apps, and repository after
  the conditional-merge program finishes. No automatic cleanup is authorized.
