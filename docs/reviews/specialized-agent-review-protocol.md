# Specialized-agent security review protocol

This protocol replaces independent-human **development review** for Pathfinder's security-sensitive
implementation gates. It does not replace the runtime requirement that GitHub itself record an
independent human approval on a candidate pull request before conditional self-merge. If no human
approves that future pull request, the evaluator must remain ineligible and the PR remains open.

## Required quorum

For a security-sensitive source, contract, installed-host, or merge-execution change:

- [ ] Pin one immutable comparison base, target commit, commit list, and diff command.
- [ ] Run an isolated standards reviewer against repository contribution and coding rules.
- [ ] Run an isolated specification reviewer against the governing plan, contracts, schemas, and callers.
- [ ] Run an isolated adversarial security reviewer that derives and executes a bounded attack ledger.
- [ ] Keep reviewer prompts independent; do not prime one reviewer with another reviewer's verdict.
- [ ] Have the coordinating agent reproduce and adjudicate every concrete finding.
- [ ] Remediate every confirmed finding before approval; record rejected hypotheses and judgment calls separately.
- [ ] Run focused, full, exact-package, and hosted checks appropriate to the changed surface.
- [ ] Re-run every affected review role after a material remediation or other source/contract change.
- [ ] Record the exact final target, reviewer roles, findings, remediation commits, verification, residual bounds, and decision in `docs/reviews/`.

The quorum is not satisfied by repeated implementation instructions, a single coordinating-agent
self-review, green tests alone, or reports that do not pin the reviewed target. An unavailable,
blocked, or materially inconclusive security review keeps the gate closed unless the residual is
explicitly outside the governing contract and source reachability.

## Decision rules

- [ ] **Approve** only when standards and specification reviews have no unresolved hard finding, the adversarial reviewer has no unresolved confirmed finding, and the coordinator reproduces the claimed evidence.
- [ ] **Approve with bounded residuals** only when every residual is named, outside the enabled path or explicitly fail-closed, and does not weaken a mandatory security invariant.
- [ ] **Reject** when any confirmed finding remains, a required reviewer is missing, the reviewed target is ambiguous, or a material post-review change has not been re-reviewed.

For K5.2, quorum approval is still only a prerequisite to implementation. The user must separately
authorize the exact K5.2 implementation scope. Default-off settings, operator-owned credentials,
one-use intent, complete evidence, the runtime independent-human PR approval floor, and the bounded
live rehearsal remain separate controls.
