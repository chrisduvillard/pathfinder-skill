<div align="center">

<br>

# 🧭 Pathfinder

### Map the codebase. Pick the path. Forge the goal.

<br>

<p>
<img alt="Skill: Pathfinder" src="https://img.shields.io/badge/agent_skill-pathfinder-2DD4BF?style=for-the-badge&labelColor=0F172A">
<img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude_Code-plugin-F59E0B?style=for-the-badge&labelColor=0F172A">
<img alt="Codex plugin" src="https://img.shields.io/badge/Codex-plugin-38BDF8?style=for-the-badge&labelColor=0F172A">
<img alt="License MIT" src="https://img.shields.io/badge/license-MIT-A78BFA?style=for-the-badge&labelColor=0F172A">
</p>

<p><b>Drop it on any unfamiliar repo. Get back the highest-value next move and a goal you can run.</b></p>

</div>

<br>

Pathfinder is a small agent skill for **Claude Code** and **Codex**. It reads a codebase from the source up, proposes useful work, asks a few sharp questions, then writes a bounded, verifiable goal you can execute or hand to another agent.

No micro-managing exploration. No guessing where to start.

<br>

## ⚡ Quick start

### <img alt="" src="https://img.shields.io/badge/-Claude_Code-F59E0B?style=flat-square&labelColor=0F172A"> &nbsp;Claude Code

```text
/plugin marketplace add chrisduvillard/pathfinder-skill
/plugin install pathfinder@pathfinder
/pathfinder:pathfinder
```

### <img alt="" src="https://img.shields.io/badge/-Codex-38BDF8?style=flat-square&labelColor=0F172A"> &nbsp;Codex

```bash
codex plugin marketplace add chrisduvillard/pathfinder-skill
codex plugin add pathfinder@pathfinder
# then run /skills, or type $pathfinder to invoke it
```

> Or just say it in plain language:
> **"Use the pathfinder skill on this repository. Start the full Pathfinder process."**

<br>

## 🔭 How it works

```mermaid
flowchart LR
    A["<b>1 · DISCOVER</b><br/><i>read code, not docs</i>"]
    B["<b>2 · SCOUT</b><br/><i>brief each domain</i>"]
    C["<b>3 · SYNTHESIZE</b><br/><i>rank the next moves</i>"]
    D["<b>4 · ASK</b><br/><i>a few sharp questions</i>"]
    E["<b>5 · FORGE /goal</b><br/><i>bounded · proven · ready to run</i>"]

    A --> B --> C --> D --> E

    classDef step fill:#0F172A,stroke:#2DD4BF,stroke-width:2px,color:#E6EDF3;
    classDef forge fill:#0F172A,stroke:#F59E0B,stroke-width:2px,color:#FBBF24;
    class A,B,C,D step;
    class E forge;
```

Pathfinder builds understanding from **actual code, tests, configs, routes, and schemas** before it ever opens a README. Then it converts your decisions into one precise execution goal.

At step 4 you pick how it interviews you:

- **Pick a move** (default): Pathfinder shows the ranked, evidence-graded Top 5 candidates and you pick one, then set boundaries. Fastest when a strong target stands out. (Alias: "express".)
- **Explore from scratch**: a guided drill-down from broad intent down to the exact file and behavior, one sharp question at a time. (Alias: "deep dive".) Every question suggests answers, names the agent's recommendation, and lets you go back, return to the ranked candidates, browse the full map, or describe your own.

<br>

## 📦 What you get

Every run drops a clean, resumable trail inside the repo:

```text
.agent-work/pathfinder/<date>-<task>/
├── 00-session.md              repo root, branch, tooling, objective
├── 01-blind-discovery.md      what the repo actually is
├── 02-scout-briefs/           located, evidence-graded findings per domain
├── 03-synthesis.md            ranked next moves + risks
├── 04-question-funnel.md      the choices put to you
├── 05-user-answers.md         what you picked
├── 06-goal-command.md         a ready-to-copy /goal
├── 07-run-log.md              progress if the goal is run
└── 08-final-summary.md        what was explored, found, and decided
```

In plain terms: **what the repo does, the best next moves with file-level evidence, the risks, your scope choices, and a goal command** you can paste straight into Claude Code or Codex.

<br>

## ✨ Example

You say:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

Pathfinder maps the repo, then hands back a route:

```text
Best next move : fix the dashboard empty-state crash
Scope          : dashboard data loading and tests only
Proof          : regression test passes, typecheck passes, changed files listed
Goal           : /goal Fix the dashboard empty-state crash so users see a useful
                 empty state instead of a blank page; npm test exits 0; tsc clean;
                 no schema change; between loops note what changed and pick the next
                 fix; stop after 12 turns, then report the blocker and the next input needed
```

That `/goal` is bounded, measurable, and self-proving, so Claude Code keeps working toward it across turns until the condition holds.

<br>

## 🛠 Manual install

If you would rather not use the plugin system, copy this repo's `skills/pathfinder/` folder (it holds `SKILL.md` and `references/`) directly to:

```text
~/.claude/skills/pathfinder/      # Claude Code
~/.codex/skills/pathfinder/       # Codex
```

Then run `/pathfinder` in Claude Code, or `$pathfinder` (or `/skills`) in Codex. See [`README-INSTALL.md`](README-INSTALL.md) for `/goal` compatibility notes.

<br>

## 🔒 Safety

Pathfinder treats every repo file as **untrusted data**. It does not run repo scripts, install packages, open secrets, or push changes unless you approve. Tokens, credentials, and private paths are redacted from its artifacts.

<br>

<div align="center">

**Map the codebase. Pick the path. Forge the goal.**

MIT licensed · built for Claude Code and Codex

</div>
