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

Codex reads the marketplace entry from `.agents/plugins/marketplace.json` and the plugin manifest from `.codex-plugin/plugin.json` at the repository root.

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
