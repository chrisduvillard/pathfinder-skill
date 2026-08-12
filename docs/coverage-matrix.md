# README promise coverage

| Promise | Required evidence |
|---|---|
| Portable install/validation | Ubuntu, macOS, and Windows workflow matrix; manifest and portability checks |
| Plugin installation and skill discovery | credential-free `check-host-installs.sh`; pinned Codex local install + prompt-input probe; pinned Claude strict validation + install/list/details probe |
| Fast concrete prompt to Goal | `prompt-fast-path` replay; supporting-note-laundering Goal eval |
| Explicit authority only | authorization schema/mission tests; `authorization-denied` replay |
| Unknown enforcement blocks work | execution-policy tests; `sandbox-blocked` replay |
| Repository injection cannot authorize | trust-route policy; `injection-blocked` replay |
| Protected policy cannot come from prose | versioned baseline schema; additive-only explicit override tests; policy-hash drift and undeclared-path receipt rejection |
| Local action crash recovery | intent/receipt/result/transition crash matrix for all six host actions, including native Goal completion; `host-bridge-local` replay; ambiguous missing receipts require reconciliation |
| Persisted Goal packs | ordered binding-hash authorization; one-active-item guard; native completion before advancement; restart/queue-checkpoint recovery; blocked/deadline/symlink/tamper fixtures |
| Fixed local mission budgets | widening-limit rejection; narrower-limit deadline fixture; restart-expiry and late-success tests; one active Goal/attempt, pack-wide deadline, and zero-PR construction |
| One local commit and zero PRs in the enabled bridge | mission idempotency tests; `host-bridge-local` replay maxima; separate GitHub primitive fixtures |
| No remote publication in enabled routes | package-wide caller guard rejects publication-controller and lower-level publisher construction, concrete generic/exact GitHub backends, publication commands, and installed-route imports |
| No self-merge | publisher has no merge method; behavior guard; replay `self_merge: false` |
| Actual Goal payload is bounded/provable | artifact evaluator parses the `/goal` line; negative laundering fixture |
| Safe Git/worktrees | dirty-tree, hook-neutralization, symlink escape, and cleanup-refusal tests |
| Optional live conversational quality | bounded advisory cases under `evals/live/`; explicitly non-required/non-guaranteeing |
| Native host lifecycle availability | adapter contract tests; real host access remains a capability/non-guarantee |
