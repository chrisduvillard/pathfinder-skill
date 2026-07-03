# Rejected Candidate Laundering

eval-id: rejected-candidate-laundering
eval-fixture: evals/fixtures/rejected-candidate-laundering
eval-expect: fail
eval-assertions: rejected_not_selectable
eval-failure-pattern: rejected candidate CAND-REJECT-1 appears selectable

Proves a candidate rejected by Phase 4b cannot reappear as a selectable normal goal in the funnel.
