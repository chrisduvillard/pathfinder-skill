# Merge Status Contract

case-id: merge-status-contract
expected: pass
eval-fixture: evals/fixtures/merge-status-contract
assertion: merge-status-contract

Proves the installed K5.1 command consumes one exact awaiting-review publication receipt and two
exact evidence documents, emits a closed hash-bound report, and remains unable to load a writer,
create an intent, or execute a merge even when the pure evaluator returns eligible.
