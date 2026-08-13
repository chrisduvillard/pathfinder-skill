# Trusted Host Publication Contract

case-id: trusted-host-publication-contract
expected: pass
eval-fixture: evals/fixtures/trusted-host-publication-contract
assertion: trusted-host-publication-contract

Proves the source-only zero-merge composition validates one terminal publication journal before
requesting host input, binds that input to the exact request/dispatch/receipt before evidence reads,
replays a completed publication without another remote effect, and recovers a lost response only
through read-only reconciliation. The composition must remain unconstructed by packaged routes and
must expose no merge primitive.
