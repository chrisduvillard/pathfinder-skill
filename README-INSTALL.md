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

Then invoke it in Codex with `$pathfinder`, or run `/skills` to pick it.

`$pathfinder` invokes the installed skill. Codex's native `/goal` command is a
separate lifecycle control for the durable Goal that Pathfinder prepares.

Codex reads the marketplace entry from `.agents/plugins/marketplace.json` and the plugin manifest from `.codex-plugin/plugin.json` at the repository root.

The marketplace entry is the stable channel and resolves to an immutable `v<version>` tag. Repository `main` is the edge channel for manual/development installs; use it only when you intentionally want unreleased changes.

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

If your Codex setup supports Agent Skills, copy this repo's `skills/pathfinder/` directory (its `SKILL.md` and `references/`) to your Codex skills folder, commonly:

```text
~/.codex/skills/pathfinder/
```

Invoke it in Codex with `$pathfinder` or by running `/skills`. If your Codex runtime does not auto-discover skills, include `SKILL.md` as context and invoke it the same way.

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

On Windows use `.venv/Scripts/python.exe`. `runner_available` is the compatibility name for those controller dependencies; it does not mean a mission can run. Check `mission_runner_available` separately. The current release reports it as false because the production host start/next/record/resume bridge is not implemented, so `/pathfinder auto` degrades to saved-Goal-only behavior. A future autonomous run will also require a clean Git repository and host-proven filesystem/process/network/credential isolation.

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
