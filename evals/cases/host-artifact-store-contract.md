# Host Artifact Store Contract

case-id: host-artifact-store-contract
expected: pass
eval-fixture: evals/fixtures/host-artifact-store-contract
assertion: host-artifact-store-contract

Proves the source-only host store authenticates one closed collection-input envelope before use and
atomically persists one externally authenticated output envelope that
contains the exact publication journal, publication/observer credential receipts, operator policy,
current-run authorization, protected-surface policy, controller-branch ownership proof, evidence,
and provenance. Re-hashed input and output tampering must still fail external authentication, repeat
persistence must not re-attest, and the only packaged consumers must remain the unconstructed
collector and two-snapshot read-only adapter; no credential loader, GitHub client, publication
controller, or merge executor is allowed.
