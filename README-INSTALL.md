# Pathfinder Skill Installation

This file is kept for users who open the original install note directly. The main repository README has the same information plus the safety model.

## Install with Claude Code `/plugin`

```text
/plugin marketplace add chrisduvillard/pathfinder-skill
/plugin install pathfinder@pathfinder
```

Then invoke the namespaced plugin skill:

```text
/pathfinder:pathfinder
```

Claude Code namespaces plugin skills as `/plugin-name:skill-name` to avoid collisions.

## Install with Codex `plugin`

```bash
codex plugin marketplace add chrisduvillard/pathfinder-skill
codex plugin add pathfinder@pathfinder
```

Then invoke it in Codex with `$pathfinder:pathfinder`, or run `/skills` to pick it.

Codex namespaces plugin skills as `$plugin-name:skill-name`. The shorter
`$pathfinder` form below is for a manual skill install. Codex's native `/goal`
command is a separate lifecycle control used only after Pathfinder prepares a
Goal and the user chooses to activate it. A printed manual command is not an
active Goal.

Codex reads the marketplace entry from `.agents/plugins/marketplace.json` and the plugin manifest from `.codex-plugin/plugin.json` at the repository root.

The marketplace entry is the stable channel and resolves to the versioned `v<version>` release tag. Published release tags are never rewritten by project policy. Repository `main` is the edge channel for manual/development installs; use it only when you intentionally want unreleased changes.

## Manual Claude Code install

Copy this repo's `skills/pathfinder/` directory, including its `SKILL.md` and `references/`, to one of:

```text
<repo>/.claude/skills/pathfinder/
~/.claude/skills/pathfinder/
```

Invoke directly in Claude Code:

```text
/pathfinder
```

or:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

No separate slash-command wrapper is required.

## Manual Codex install

Copy this repo's `skills/pathfinder/` directory (its `SKILL.md` and `references/`) to either the repository or user Codex skill location:

```text
<repo>/.agents/skills/pathfinder/
~/.agents/skills/pathfinder/
```

Codex scans `.agents/skills` from the current working directory through the
repository root and also reads the user location. Invoke this manual install
with `$pathfinder` or by running `/skills`. See OpenAI's official
[Build skills](https://learn.chatgpt.com/docs/build-skills) guide for the current
discovery locations and invocation behavior.

## Claude Code `/goal` compatibility

`/goal` requires Claude Code v2.1.139 or newer.

Pathfinder saves both a ready-to-copy `/goal <condition>` command and an equivalent `Implementation Goal` Markdown fallback for Codex, older Claude Code versions, or environments where slash commands cannot be executed directly.

The generated `/goal` condition is bounded, measurable, under the character budget, and requires the implementation agent to surface proof in the transcript because the `/goal` evaluator does not independently run tools or read files.

## Autonomous controller requirements

Goal generation does not require the controller. Python 3.11+ and the pinned validator packages enable controller validation and inspection:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-controller.txt
.venv/bin/python -m pathfinder_core doctor --json
```

On Windows use `.venv/Scripts/python.exe`. `runner_available` is the compatibility name for those controller dependencies. `mission_runner_available` separately reports the callable local start/next/record/resume protocol. It does not grant unattended eligibility: an actual run still requires a clean Git repository or an explicitly acknowledged committed base, a trusted authorization snapshot, host-proven filesystem/process/network/credential isolation, a stable native Goal identity, and typed receipts. The host must verify the actual repository and `HEAD`; `mission start` validates the supplied closed documents and does not independently discover repository state. Missing evidence degrades to saved-Goal/manual-handoff behavior; publication is disabled.

Full plugin installs include `scripts/pathfinder-controller.sh`, which resolves the plugin root even while Pathfinder operates on another repository. A manual copy of only `skills/pathfinder/` is Goal-generation-only unless the controller is separately installed.

See [`docs/compatibility.md`](docs/compatibility.md) and [`docs/operator-guide.md`](docs/operator-guide.md).

## Codex `/goal` compatibility

If `/goal` is absent from Codex's slash-command list, enable it in `config.toml`:

```toml
[features]
goals = true
```

Or run `codex features enable goals`. See OpenAI's official
[Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals) guide for the
current setup and lifecycle controls.
