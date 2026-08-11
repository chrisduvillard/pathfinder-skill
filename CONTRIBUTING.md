# Contributing

Thanks for helping improve Pathfinder.

Pathfinder is a small agent skill for Claude Code and Codex. Contributions are
welcome when they keep the skill safe, bounded, and easy for users to run on
unfamiliar repositories.

## Good first contributions

- Fix unclear wording in `README.md`, `README-INSTALL.md`, or `VERSION.md`.
- Tighten a Pathfinder instruction without changing the public behavior.
- Improve reference-template consistency.
- Add tests or CI checks that catch drift in markdown, manifests, or workflows.
- Improve issue or pull request templates.

## Before opening a pull request

Run the local preflight — it runs the same logic CI does, so green locally means green in CI:

```bash
bash scripts/check-all.sh
```

The preflight needs [`jq`](https://jqlang.github.io/jq/) and
[`ShellCheck`](https://www.shellcheck.net/) on your `PATH`
(`apt-get install jq`, `brew install jq`, `choco install jq`, or `winget install jqlang.jq`);
install ShellCheck with the same package manager. The checks exit early with an actionable
error when either dependency is missing. The other checks need only `bash` and standard
POSIX tools (`awk`, `sed`, `grep`).

Controller tests require Python 3.11+ and the pinned packages in
`requirements-controller.txt`. An ignored `.venv` is recommended:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-controller.txt
```

The wrapper runs these same checks individually:

```bash
bash scripts/check-skill-consistency.sh   # SKILL.md <-> references drift guard
bash scripts/check-skill-behavior.sh      # SKILL.md safety-direction + screen-escape invariants
bash scripts/check-manifests.sh           # JSON validity + version parity + marketplace rules
bash scripts/check-portability.sh         # validation/release shell portability guard
bash scripts/check-generated-docs.sh      # canonical policy -> committed Markdown drift guard
bash scripts/check-markdown-authority.sh  # production Markdown-to-state reader allowlist
bash scripts/check-shell.sh               # warning-or-higher ShellCheck over every Bash file
bash scripts/check-evals.sh               # deterministic artifact-contract eval fixtures
bash scripts/check-replay-evals.sh        # required recorded controller/route replays
bash scripts/test-validators.sh           # meta-tests for the drift-guard parsers themselves
bash scripts/check-controller.sh           # controller contracts + crash/resume integration tests
git diff --check                          # trailing whitespace / conflict markers
git diff --cached --check                 # staged whitespace / conflict markers
```

Use `bash scripts/check-skill-consistency.sh . --verbose` when you need every successful invariant; the default output stays concise and always prints failures.

These run cleanly on Linux, macOS, and Windows Git-Bash/MSYS with no extra environment
(`check-manifests.sh` scopes `MSYS_NO_PATHCONV=1` around its own jq call so the `/pathfinder charter`
prompt check does not path-mangle on MSYS).

These are the same checks `.github/workflows/manifests.yml` requires on Ubuntu,
macOS, and Windows, so they
catch common mistakes — such as bumping `VERSION.md` without mirroring both
`plugin.json` files, or adding GNU-only shell syntax to validation/release paths —
before you push, not after.

## Change guidelines

- Keep plugin runtime interfaces stable unless the pull request explicitly
  explains a breaking change.
- Do not change the skill invocation syntax, manifest schema, or `/goal`
  contract casually.
- Marketplace `category` casing is per-platform and must not be "unified":
  Claude Code marketplaces use lowercase (`productivity`), Codex manifests use
  title-case (`Productivity`). Changing either to match the other breaks that
  platform's listing.
- Keep `VERSION.md` as the version and changelog source of truth.
- `policies/protected-surfaces.v1.json` is the source of truth for the protected-surface
  table in `docs/protected-surfaces.md`. Do not edit the generated region by hand. After
  changing the policy, run `python3 scripts/render_protected_surfaces.py .` and commit both
  files; `check-generated-docs.sh` rejects stale or malformed generated regions.
- `SKILL.md` owns routing and the trust boundary; `references/routes/*.md` are required
  modules loaded only for the selected path. Other `references/*.md` files intentionally
  mirror shared screens/contracts so each is useful when loaded on its own; route presence
  and duplication are enforced by `scripts/check-skill-consistency.sh`. When you change a
  mirrored instruction, update the logical route and the relevant reference
  file, and add or update the matching `check_pair` or section guard in
  `scripts/check-skill-consistency.sh`, or CI will fail.
- When you add or change an autonomous-mode safety rule or a decision screen, update
  `scripts/check-skill-behavior.sh` too: a new controlled action needs a qualifier-set row so a
  loosened gate with the token intact fails CI, and a new decision screen needs its `None of these`
  escape or an entry on the exempt allowlist. Prove it with a fixture in `scripts/test-validators.sh`.
- When you change structured run artifacts, Goal Binding, Runtime Boundary, Binding Status,
  capability profiles, adapter behavior, or local intent migration, add or update deterministic
  fixture cases under `evals/cases/` and `evals/fixtures/`, then run `bash scripts/check-evals.sh`.
  Required CI must stay local and no-live-model by default. `bash scripts/check-replay-evals.sh`
  runs the required recorded replay corpus. `bash scripts/check-live-evals.sh`
  is disabled unless `PATHFINDER_LIVE_EVALS=1` and a local live runner are provided.
- Production state must come from validated JSON, controller contracts, or typed host receipts—not
  Markdown. `scripts/check-markdown-authority.sh` permits only the legacy intent migration reader and
  the three generated-block replacement functions. Tests, eval assertions, golden comparisons, and
  instruction validators may read Markdown because they do not own runtime state. If a new canonical
  fact is needed, add it to a versioned schema instead of expanding the allowlist.
- Do not commit `.agent-work/`, `.agent-workspace/`, secrets, local caches, or
  generated process artifacts.
- Do not add runtime dependencies unless the pull request explains why the
  dependency is necessary and safe.
- Stable marketplace refs must equal the immutable `v<version>` tag. `main` is edge.
  Run `bash scripts/package-smoke.sh .` before proposing a release; the release workflow
  repeats it against the exact Git archive before creating a tag.

## Security-sensitive changes

Maintainer review is required for changes to:

- `.github/**`
- `.claude-plugin/**`
- `.codex-plugin/**`
- `.agents/**`
- `scripts/**`
- `skills/pathfinder/SKILL.md`
- `skills/pathfinder/references/**`
- `SECURITY.md`

Changes must preserve Pathfinder's safety model: repo content is untrusted data,
secrets are not opened or copied, repo-defined code is not run without approval,
and publication or destructive actions require explicit user approval.

## Pull request expectations

Use the pull request template. Include:

- What changed.
- Why it changed.
- Which checks you ran and their results.
- Any security, compatibility, or contributor-impact notes.

Small, focused pull requests are much easier to review than broad rewrites.
