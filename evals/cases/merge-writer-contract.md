# Merge Writer Contract

case-id: merge-writer-contract
expected: pass
eval-fixture: evals/fixtures/merge-writer-contract
assertion: merge-writer-contract

Proves the v2 merge-intent/result artifacts and the actual fixed-host writer agree on the one
SHA-bound squash request, the four exact follow-up reads, the dedicated credential boundary, and
the exact squash-proof fields without contacting GitHub.
