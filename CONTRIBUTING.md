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

Run the local checks:

```bash
bash scripts/check-skill-consistency.sh
git diff --check
```

Validate the JSON manifests:

```powershell
$files = @(
  ".claude-plugin/plugin.json",
  ".codex-plugin/plugin.json",
  ".claude-plugin/marketplace.json",
  ".agents/plugins/marketplace.json"
)
foreach ($f in $files) {
  Get-Content -Raw $f | ConvertFrom-Json | Out-Null
  Write-Output "ok: $f"
}
```

## Change guidelines

- Keep plugin runtime interfaces stable unless the pull request explicitly
  explains a breaking change.
- Do not change the skill invocation syntax, manifest schema, or `/goal`
  contract casually.
- Keep `VERSION.md` as the version and changelog source of truth.
- Update both `SKILL.md` and the relevant `references/*.md` file when changing
  mirrored instructions.
- Do not commit `.agent-work/`, `.agent-workspace/`, secrets, local caches, or
  generated process artifacts.
- Do not add runtime dependencies unless the pull request explains why the
  dependency is necessary and safe.

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
