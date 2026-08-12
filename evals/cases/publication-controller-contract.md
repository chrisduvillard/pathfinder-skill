# Publication Controller Contract

case-id: publication-controller-contract
expected: pass
eval-fixture: evals/fixtures/publication-controller-contract
assertion: publication-controller-contract

Proves the default-off controller persists one authenticated exact-PR receipt, replays it without
network activity, and remains unreachable from production CLI, mission, publisher, and Goal routes.
