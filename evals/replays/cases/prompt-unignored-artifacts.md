# Prompt unignored artifacts
case-id: replay-prompt-unignored-artifacts
expected: fail
eval-fixture: evals/replays/fixtures/prompt-unignored-artifacts
expected-failure: artifacts_ignored
assertion: replay-contract
