# Merge Evidence Contract

case-id: merge-evidence-contract
expected: pass
eval-fixture: evals/fixtures/merge-evidence-contract
assertion: merge-evidence-contract

Proves permission-qualified review identity, closed review decision, squash support,
source/active rule semantic hashes, a mode-qualified nonmatching bypass actor, typed positive
team/repository-role/organization-admin membership resolution, candidate identity, policy receipt,
and check-creator identity remain present in normalized merge evidence. The actual evaluator must
derive `merge-actor-can-bypass` for every positive membership case.
