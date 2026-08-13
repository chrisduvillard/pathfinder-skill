# Host Artifact Store Contract

case-id: host-artifact-store-contract
expected: pass
eval-fixture: evals/fixtures/host-artifact-store-contract
assertion: host-artifact-store-contract

Proves the source-only host store atomically persists one externally authenticated envelope that
contains the exact publication journal, publication/observer credential receipts, controller-
branch ownership proof, evidence, and provenance. Re-hashed tampering must still fail external
authentication, repeat persistence must not re-attest, and the packaged store must have no caller,
credential loader, GitHub client, publication controller, or merge executor.
