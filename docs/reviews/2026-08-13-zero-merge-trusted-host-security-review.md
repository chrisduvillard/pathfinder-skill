# Specialized-agent security review: zero-merge trusted-host composition

Status: approved within the recorded zero-merge source and evaluator scope

Pull request: [#73](https://github.com/chrisduvillard/pathfinder-skill/pull/73)

Comparison base: `7174eac5d1f813d1148ede76818b7ed38a4ea698`

Reviewed implementation/evaluator target: `d483e19c5fadab717ca5533df0401e12e0b62f7e`

Reviewed: 2026-08-13

This record follows the
[`specialized-agent-review-protocol.md`](specialized-agent-review-protocol.md). It approves only the
source-only composition from exact awaiting-review publication through authenticated, read-only
evidence collection. It does not approve an installed host, live credentials, merge execution, or
K5.2.

## Fixed review identity

- [x] Compared `7174eac5d1f813d1148ede76818b7ed38a4ea698...d483e19c5fadab717ca5533df0401e12e0b62f7e`.
- [x] Reviewed `1dc38c9` and `559e2e9` as the zero-merge composition, `cbdcced` as the review/eval remediation, and `d483e19` as the alias-isolation remediation.
- [x] Isolated standards role: `/root/standards_review`.
- [x] Isolated specification role: `/root/spec_fidelity_review`.
- [x] Isolated adversarial security role: `/root/security_adversarial_review`.
- [x] Coordinating agent independently inspected the diff, reproduced focused and package evidence, and adjudicated the reports.
- [x] All eight hosted checks were green for source target `559e2e9`; full and exact-package checks passed again on final reviewed target `d483e19`.

This approval is pinned to `d483e19`. The immediate successor that closes this record changes only
the review record and progress log; it adds no product, evaluator, contract, gate, or capability
behavior. Any later material product, evaluator, contract, or governance change invalidates the
affected decision until the required quorum roles run again.

## Required safety invariants

- [x] The composition exposes no merge call, merge token, writer, intent, request, dispatch, or retry route.
- [x] No CLI, ordinary `/goal`, `/pathfinder`, mission, pack, resume, publisher, or installed route constructs the composition.
- [x] The terminal publication journal is schema-validated before the trusted input provider or any downstream evidence read.
- [x] Only `awaiting-review` with one exact terminal receipt can reach collection.
- [x] The trusted input is authenticated at the collector-owned clock instant, not a caller-selected time.
- [x] The authenticated request, dispatch, and receipt equal the selected validated canonical journal documents before any GitHub evidence read.
- [x] Invalid policy credentials, malformed or nonterminal journals, unavailable input, expired authority, split identity, and journal drift all stop before an evidence read.
- [x] A repeated completed request performs at most one push and one pull-request creation while allowing a fresh read-only collection.
- [x] A lost publication response can recover only through exact read-only reconciliation and never through a second push or create.
- [x] No source loads an authenticator key, secret, environment token, publication credential, or merge credential.
- [x] The change does not weaken the existing authenticated artifact, exact candidate, repository, PR, ref/SHA, diff, policy, or evidence bindings.
- [x] The change does not mark either installed-host readiness item or K5.2 complete.

## Reproduced evidence

- [x] `bash scripts/check-all.sh .` on `d483e19`: 514 tests plus all validators and artifact replays passed.
- [x] `PATHFINDER_HOST_SMOKE=1 bash scripts/package-smoke.sh . 3.2.0 worktree` on `d483e19`: exact package and credential-free Codex/Claude install/load passed.
- [x] Focused publication/collector/controller/journal suite: 48 tests passed in both coordinator and adversarial-review snapshots.
- [x] Source scan found zero packaged constructor callers of `TrustedHostPublicationEvidenceController`.
- [x] Source scan found no live publication backend, authenticator/key loader, credential loader, merge writer, or merge-execution caller added by this diff.
- [x] Standards review found one process defect: changed adapter behavior lacked the deterministic eval required by `CONTRIBUTING.md`.
- [x] The process defect was remediated with `trusted-host-publication-contract`, covering terminal validation, exact binding, replay, recovery, zero callers, and zero merge primitives.
- [x] The first follow-up adversarial review found two weak-oracle families: disconnected binding order and lexical constructor/sink scans; `cbdcced` moved the eval onto the real collector path and added AST/route checks.
- [x] The second follow-up found re-export/assignment and bound-member alias bypasses; `d483e19` replaced symbol matching with non-owner capability-module isolation and member-reference checks.
- [x] Disposable mutants for binding removal/reordering, direct/dotted/re-export/assignment/subclass aliases, bound methods, dynamic module lookup, `getattr`, and subscripted capability access all made the eval fail for the intended reason.

## Adversarial result

- [x] Ledger closed `COMPLETE_WITHIN_MODEL`: 15 `SURVIVED`, one zero-merge `CONTRACT_EXCLUDED`, and zero counterexample, inconclusive, blocked, or deferred rows.
- [x] Re-hashed and validly authenticated split request/dispatch/receipt and authority inputs stopped before evidence reads.
- [x] Expired, stale, unavailable, malformed, and nonterminal inputs stopped before evidence reads.
- [x] Completed replay, post-publication collection failure, and lost-response recovery retained one push and one PR creation.
- [x] One controlled two-thread dispatch interleaving retained one push and one PR creation.
- [x] Empty, missing, and non-string evidence identities failed closed.
- [x] Caller/source-to-sink tracing found no secret loader, ordinary route, or merge sink.
- [x] Final remediation ledger on `d483e19` closed `COMPLETE_WITHIN_MODEL`: 14 `SURVIVED` and zero counterexample, inconclusive, blocked, or deferred rows.

Residual bounds: one deterministic high-value two-thread schedule rather than every schedule; no live
GitHub, concrete installed host, host authenticator, credential injector, or Windows ACL execution;
injected host components remain trusted. These surfaces are absent or fail-closed in the reviewed
source target and remain operational gates below. The static reachability oracle covers direct,
aliased, re-exported, subclassed, bound-member, exact dynamic-module, `getattr`, and subscript forms;
deliberately obfuscated computed-string interpreter tricks remain outside the bounded model.

## Quorum decision

- [x] **Approve exact target `d483e19c5fadab717ca5533df0401e12e0b62f7e` within the zero-merge source/evaluator scope and recorded bounds.**
- [ ] **Approve with unresolved conditions.**
- [ ] **Reject.**

Judgment calls retained without a hard finding:

```text
The terminal journal remains a closed Mapping across the protocol boundary rather than a new domain
wrapper, and the orchestrator reloads through PublicationController.journal. Adding another source
type or controller method would enlarge this deliberately narrow composition without changing its
validated trust boundary; revisit only if another production consumer is approved.
```

Quorum attestation:

- [x] Every role reviewed the fixed target independently and reported to the coordinating agent.
- [x] Standards follow-up found no hard finding and confirmed the repository-required deterministic eval and final wording.
- [x] Specification follow-up found no mismatch or scope creep and confirmed runtime-human, installed-host, and K5.2 boundaries.
- [x] Adversarial follow-up found no confirmed defect on `d483e19`; closure was `COMPLETE_WITHIN_MODEL` and the decision was approve.
- [x] The coordinating agent reproduced the findings, mutant failures, full checks, and exact-package checks on the immutable target.
- [x] This decision does not approve an installed trusted host or K5.2 merge composition.
- [x] K5.2 requires a later specialized-agent quorum over its exact design/diff plus explicit user authorization.
- [x] Any future runtime self-merge still requires a GitHub-recorded independent human PR approval; agent review is not counted as that approval.

## Still-open operational gates

- [ ] A concrete operator-owned installed host supplies authenticated envelopes, credentials, policy, and exact persisted PR identity.
- [ ] That host supplies complete live REST/GraphQL evidence through the reviewed read-only boundary.
- [ ] The installed-host integration passes a disposable zero-merge rehearsal without adding merge authority.
- [ ] A separate K5.2 design and diff receive the specialized-agent security quorum and explicit user authorization before merge-execution composition is implemented or enabled.
