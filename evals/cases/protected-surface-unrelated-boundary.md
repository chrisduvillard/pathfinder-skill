# Protected Surface Unrelated Boundary

eval-id: protected-surface-unrelated-boundary
eval-fixture: evals/fixtures/protected-surface-unrelated-boundary
eval-expect: fail
eval-assertions: protected_surface_boundary
eval-failure-pattern: missing manual/proof/safety boundary for auth surface

Proves a boundary in a different artifact does not satisfy the protected surface rule.
