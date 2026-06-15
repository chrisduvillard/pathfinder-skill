<div align="center">

# Pathfinder

**Map a repo. Pick the next move. Write the goal.**

<img alt="Skill: Pathfinder" src="https://img.shields.io/badge/skill-pathfinder-2DD4BF?style=for-the-badge&labelColor=0F172A">
<img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude_Code-plugin-F59E0B?style=for-the-badge&labelColor=0F172A">
<img alt="Codex plugin" src="https://img.shields.io/badge/Codex-plugin-38BDF8?style=for-the-badge&labelColor=0F172A">

`/pathfinder:pathfinder`

</div>

Pathfinder is a small agent skill for Claude Code and Codex.

It reads an unfamiliar repository, finds useful work, asks a few focused questions, then writes a clear implementation goal you can run or hand to another agent.

## Install with Claude Code `/plugin`

```text
/plugin marketplace add chrisduvillard/pathfinder-skill
/plugin install pathfinder@pathfinder
```

Then run the namespaced plugin skill:

```text
/pathfinder:pathfinder
```

## Install with Codex `plugin`

```bash
codex plugin marketplace add chrisduvillard/pathfinder-skill
codex plugin add pathfinder@pathfinder
```

Then start Codex and invoke the skill (`@pathfinder` or the slash equivalent in interactive sessions).

## Manual install

Copy the skill folder:

```text
~/.claude/skills/pathfinder/
# or
~/.codex/skills/pathfinder/
```

Then run:

```text
/pathfinder
```

Or say:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

## What it gives you

```text
.agent-work/pathfinder/<date>-<task>/
  01-blind-discovery.md
  02-scout-briefs/
  03-synthesis.md
  04-question-funnel.md
  06-goal-command.md
```

In plain terms:

- what the repo does
- the highest value next moves
- the risks and protected areas
- a few choices for scope
- a ready to copy `/goal` command

## Example

You say:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

Pathfinder replies with a short route:

```text
Best next move: fix the dashboard empty-state crash.
Scope: dashboard data loading and tests only.
Proof: regression test passes, typecheck passes, changed files listed.
Goal: /goal Fix the dashboard empty-state crash so users see a useful empty state instead of a blank page...
```

## Safety

Pathfinder treats repo files as untrusted data. It does not run repo scripts, install packages, open secrets, or push changes unless you approve.

## License

MIT. See `LICENSE`.
