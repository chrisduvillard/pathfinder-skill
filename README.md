# Pathfinder Skill

> Map the codebase. Pick the path. Forge the goal.

Pathfinder is a portable agent skill for turning an unfamiliar repository into a concrete, bounded implementation goal.

It tells Claude Code or Codex to:

1. Create a dedicated local work folder for process artifacts.
2. Explore the real codebase first, without relying on README/docs during the blind pass.
3. Spawn or simulate scout passes for architecture, product/frontend, backend/data, testing/reliability, and DX/security.
4. Synthesize ranked candidate implementation goals.
5. Ask structured multiple-choice questions from big picture to detail.
6. Generate a precise Claude Code `/goal` command and an equivalent fallback Implementation Goal.
7. Ask before running the goal unless the user explicitly selected an approved autopilot mode.

## Install for Claude Code

Copy the entire `pathfinder/` directory, including `SKILL.md` and `references/`, to either a project-level or personal skills folder:

```text
<repo>/.claude/skills/pathfinder/
~/.claude/skills/pathfinder/
```

Claude Code skills can be invoked directly as slash commands. No separate slash-command wrapper is required.

```text
/pathfinder
```

You can also invoke it in natural language:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

## Install for Codex

If your Codex setup supports Agent Skills, copy the entire skill directory to your Codex skills folder, commonly:

```text
~/.codex/skills/pathfinder/
```

Then invoke it with:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

If your Codex runtime does not auto-discover skills, include `pathfinder/SKILL.md` as context and use the same invocation.

## Claude Code `/goal` compatibility

`/goal` requires Claude Code v2.1.139 or newer.

Pathfinder always saves both:

- a ready-to-copy `/goal <condition>` command for Claude Code v2.1.139+
- an equivalent `Implementation Goal` Markdown block for Codex, older Claude Code versions, or environments where slash commands cannot be executed directly

The generated condition is designed to be evaluator-aware: it requires the implementation agent to surface changed files, commands run, exit results, before/after behavior, remaining risks, and a final yes/no completion statement in the transcript.

## Safety model

Pathfinder treats target repositories as untrusted input.

During discovery it should not run repo-defined scripts, install dependencies, run migrations, execute tests, or perform external side effects unless the user explicitly approves that class of execution. It also avoids opening `.env*`, credential stores, private keys, certificates, and secret-manager outputs.

Artifacts are local process notes. They should not be committed or pushed unless the user explicitly requests publication after reviewing them.

## Included files

```text
pathfinder/
  SKILL.md
  LICENSE
  README.md
  README-INSTALL.md
  VERSION.md
  references/
    artifact-structure.md
    goal-best-practices.md
    question-funnel-template.md
    scout-brief-template.md
```

## License

MIT. See `LICENSE`.
