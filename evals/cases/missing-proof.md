# Missing Proof

eval-id: missing-proof
eval-fixture: evals/fixtures/missing-proof
eval-expect: fail
eval-assertions: goal_contract
eval-failure-pattern: missing proof surface

Proves the goal contract assertion fails when a goal omits its proof surface.
