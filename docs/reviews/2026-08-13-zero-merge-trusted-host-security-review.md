# Independent security review: zero-merge trusted-host composition

Status: pending independent human review

Pull request: [#73](https://github.com/chrisduvillard/pathfinder-skill/pull/73)

Comparison base: `7174eac5d1f813d1148ede76818b7ed38a4ea698`

Prepared: 2026-08-13

This is a review handoff, not an approval. It covers only the source-only composition from exact
awaiting-review publication through authenticated, read-only evidence collection. It does not
approve an installed host, live credentials, merge execution, or K5.2.

## Pin the review

- [ ] Record the exact PR head from `git rev-parse HEAD`: `________________`.
- [ ] Confirm that the recorded head is still PR #73's head and compare it with the fixed base above.
- [ ] Record reviewer name or handle and review date: `________________` / `________________`.
- [ ] Confirm the reviewer is a human who did not implement the reviewed change.
- [ ] Confirm every required hosted check is green for that exact head, not an earlier commit.

Any head change invalidates the decision below until the new diff is reviewed and the checklist is
re-run.

## Required safety invariants

- [ ] The composition exposes no merge call, merge token, writer, intent, request, dispatch, or retry route.
- [ ] No CLI, ordinary `/goal`, `/pathfinder`, mission, pack, resume, publisher, or installed route constructs the composition.
- [ ] The terminal publication journal is schema-validated before the trusted input provider or evidence collector is called.
- [ ] Only `awaiting-review` with one exact terminal receipt can reach collection.
- [ ] The trusted input is authenticated at the collector-owned clock instant, not a caller-selected time.
- [ ] The authenticated request, dispatch, and receipt are byte-identical to the selected terminal journal before any GitHub evidence read.
- [ ] Invalid policy credentials, malformed or nonterminal journals, unavailable input, expired authority, split identity, and journal drift all stop before an evidence read.
- [ ] A repeated completed request performs at most one push and one pull-request creation while allowing a fresh read-only collection.
- [ ] A lost publication response can recover only through exact read-only reconciliation and never through a second push or create.
- [ ] No source loads an authenticator key, secret, environment token, publication credential, or merge credential.
- [ ] The change does not weaken the existing authenticated artifact, exact candidate, repository, PR, ref/SHA, diff, policy, or evidence bindings.
- [ ] The change does not mark either installed-host readiness item or K5.2 complete.

## Reproduce the prepared evidence

- [ ] Run `bash scripts/check-all.sh .` and record the result: `________________`.
- [ ] Run `PATHFINDER_HOST_SMOKE=1 bash scripts/package-smoke.sh . 3.2.0 worktree` and record the result: `________________`.
- [ ] Run `.venv/bin/python -m unittest tests.core.test_trusted_host_publication tests.adapters.test_github_evidence_collector tests.core.test_publication_controller tests.core.test_publication_journal` and record the result: `________________`.
- [ ] Search packaged sources for callers of `TrustedHostPublicationEvidenceController`; confirm only its definition, tests, and documentation are present.
- [ ] Search packaged sources for a live publication backend, authenticator/key loader, credential loader, merge writer, or merge-execution caller; confirm none was added by this diff.

## Adversarial probes

- [ ] Re-hash a changed request, dispatch, or receipt and confirm collection stops before any evidence read.
- [ ] Supply a validly authenticated but expired or cross-identity input and confirm collection stops before any evidence read.
- [ ] Supply a nonterminal journal with a fabricated receipt and confirm collection is never attempted.
- [ ] Inject a failure after publication dispatch and before its response; confirm restart uses read-only reconciliation and the remote effect count remains one.
- [ ] Replay the completed request; confirm the publication effect count remains one and collection may be refreshed.
- [ ] Substitute repository, PR, branch, head/base SHA, or diff identity; confirm the boundary fails closed.
- [ ] Make the trusted input provider or policy reader fail; confirm no GitHub evidence read follows.

## Decision

- [ ] **Approve this exact zero-merge source composition only.**
- [ ] **Approve with conditions** recorded below.
- [ ] **Reject** with findings recorded below.

Conditions or findings:

```text

```

Reviewer attestation:

- [ ] I reviewed the exact recorded head and the complete diff from the fixed comparison base.
- [ ] My decision does not approve an installed trusted host or K5.2 merge composition.
- [ ] K5.2 must receive a later, separate human security approval over its own exact diff and live-host evidence.

## Still-open operational gates

- [ ] A concrete operator-owned installed host supplies authenticated envelopes, credentials, policy, and exact persisted PR identity.
- [ ] That host supplies complete live REST/GraphQL evidence through the reviewed read-only boundary.
- [ ] The installed-host integration passes a disposable zero-merge rehearsal without adding merge authority.
- [ ] A separate K5.2 design and diff receive explicit human security approval before any merge-execution composition is implemented or enabled.
