# Specialized-agent security review: zero-merge trusted-host composition

Status: provisional pending an immutable remediation commit and follow-up role review

Pull request: [#73](https://github.com/chrisduvillard/pathfinder-skill/pull/73)

Comparison base: `7174eac5d1f813d1148ede76818b7ed38a4ea698`

Reviewed target: `559e2e9953587bc868a36cdab8a94e5629db4bf4`

Reviewed: 2026-08-13

This record follows the
[`specialized-agent-review-protocol.md`](specialized-agent-review-protocol.md). It approves only the
source-only composition from exact awaiting-review publication through authenticated, read-only
evidence collection. It does not approve an installed host, live credentials, merge execution, or
K5.2.

## Fixed review identity

- [x] Compared `7174eac5d1f813d1148ede76818b7ed38a4ea698...559e2e9953587bc868a36cdab8a94e5629db4bf4`.
- [x] Reviewed commits `1dc38c9` and `559e2e9` as the complete zero-merge composition slice.
- [x] Isolated standards role: `/root/standards_review`.
- [x] Isolated specification role: `/root/spec_fidelity_review`.
- [x] Isolated adversarial security role: `/root/security_adversarial_review`.
- [x] Coordinating agent independently inspected the diff, reproduced focused and package evidence, and adjudicated the reports.
- [x] All eight hosted checks were green for exact target `559e2e9`.

The source approval above remains pinned to `559e2e9`. Subsequent review-governance and deterministic
eval changes require their own focused re-review; any later product or contract change invalidates
this decision until the affected quorum roles run again.

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

- [x] `bash scripts/check-all.sh .`: 514 tests plus all validators and artifact replays passed.
- [x] `PATHFINDER_HOST_SMOKE=1 bash scripts/package-smoke.sh . 3.2.0 worktree`: exact package and credential-free Codex/Claude install/load passed.
- [x] Focused publication/collector/controller/journal suite: 48 tests passed in both coordinator and adversarial-review snapshots.
- [x] Source scan found zero packaged constructor callers of `TrustedHostPublicationEvidenceController`.
- [x] Source scan found no live publication backend, authenticator/key loader, credential loader, merge writer, or merge-execution caller added by this diff.
- [x] Standards review found one process defect: changed adapter behavior lacked the deterministic eval required by `CONTRIBUTING.md`.
- [x] The process defect was remediated with `trusted-host-publication-contract`, covering terminal validation, exact binding, replay, recovery, zero callers, and zero merge primitives.

## Adversarial result

- [x] Ledger closed `COMPLETE_WITHIN_MODEL`: 15 `SURVIVED`, one zero-merge `CONTRACT_EXCLUDED`, and zero counterexample, inconclusive, blocked, or deferred rows.
- [x] Re-hashed and validly authenticated split request/dispatch/receipt and authority inputs stopped before evidence reads.
- [x] Expired, stale, unavailable, malformed, and nonterminal inputs stopped before evidence reads.
- [x] Completed replay, post-publication collection failure, and lost-response recovery retained one push and one PR creation.
- [x] One controlled two-thread dispatch interleaving retained one push and one PR creation.
- [x] Empty, missing, and non-string evidence identities failed closed.
- [x] Caller/source-to-sink tracing found no secret loader, ordinary route, or merge sink.

Residual bounds: one deterministic high-value two-thread schedule rather than every schedule; no live
GitHub, concrete installed host, host authenticator, credential injector, or Windows ACL execution;
injected host components remain trusted. These surfaces are absent or fail-closed in the reviewed
source target and remain operational gates below.

## Provisional quorum decision

- [ ] **Approve the remediation target within the zero-merge scope and recorded bounds.** Pending immutable target and follow-up results.
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
- [ ] The coordinating agent reproduced the evidence and committed the only hard process remediation at an immutable target.
- [x] This decision does not approve an installed trusted host or K5.2 merge composition.
- [x] K5.2 requires a later specialized-agent quorum over its exact design/diff plus explicit user authorization.
- [x] Any future runtime self-merge still requires a GitHub-recorded independent human PR approval; agent review is not counted as that approval.

## Still-open operational gates

- [ ] A concrete operator-owned installed host supplies authenticated envelopes, credentials, policy, and exact persisted PR identity.
- [ ] That host supplies complete live REST/GraphQL evidence through the reviewed read-only boundary.
- [ ] The installed-host integration passes a disposable zero-merge rehearsal without adding merge authority.
- [ ] A separate K5.2 design and diff receive the specialized-agent security quorum and explicit user authorization before merge-execution composition is implemented or enabled.
