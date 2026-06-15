# Pathfinder Skill Installation

This file is kept for users who open the original install note directly. The main repository README has the same information plus the safety model.

## Install for Claude Code

Copy the entire `pathfinder/` directory, including `SKILL.md` and `references/`, to one of:

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

## Install for Codex

If your Codex setup supports Agent Skills, copy the entire skill directory to your Codex skills folder, commonly:

```text
~/.codex/skills/pathfinder/
```

If your Codex runtime does not auto-discover skills, include `pathfinder/SKILL.md` as context and use the same invocation.

## Claude Code `/goal` compatibility

`/goal` requires Claude Code v2.1.139 or newer.

Pathfinder saves both a ready-to-copy `/goal <condition>` command and an equivalent `Implementation Goal` Markdown fallback for Codex, older Claude Code versions, or environments where slash commands cannot be executed directly.

The generated `/goal` condition is bounded, measurable, under the character budget, and requires the implementation agent to surface proof in the transcript because the `/goal` evaluator does not independently run tools or read files.
