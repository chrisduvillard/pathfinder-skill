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

<p>
<a href="https://github.com/chrisduvillard/pathfinder-skill/actions/workflows/manifests.yml"><img alt="Manifests workflow" src="https://github.com/chrisduvillard/pathfinder-skill/actions/workflows/manifests.yml/badge.svg"></a>
<a href="https://github.com/chrisduvillard/pathfinder-skill/actions/workflows/codeql.yml"><img alt="CodeQL workflow" src="https://github.com/chrisduvillard/pathfinder-skill/actions/workflows/codeql.yml/badge.svg"></a>
<a href="https://scorecard.dev/viewer/?uri=github.com/chrisduvillard/pathfinder-skill"><img alt="OpenSSF Scorecard" src="https://api.scorecard.dev/projects/github.com/chrisduvillard/pathfinder-skill/badge"></a>
</p>

<p><b>Drop it on any unfamiliar repo — or hand it a prompt. Either way, get back a bounded goal you can run.</b></p>

</div>

<br>

Pathfinder is a small agent skill for **Claude Code** and **Codex**. It reads a codebase from the source up, proposes useful work, asks a few sharp questions, then writes a bounded, verifiable goal you can execute or hand to another agent.

> [!TIP]
> **Already know what you want?** Hand it a prompt instead — it researches just what that prompt touches and forges the same goal, faster. Ideal if you just want a prompt → loop (`/goal`) tool.

No micro-managing exploration. No guessing where to start.

<br>

## 🚀 Get started

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

Then use it two ways:

- **Explore a repo** — *"Use the pathfinder skill on this repository."*
- **Turn a task into a goal** — *"Pathfinder, turn this into a /goal: &lt;the work you want done&gt;."*

<br>

## 🔭 How it works

Two ways in, one result — a bounded, verifiable `/goal` you can run or hand to another agent.

**🗺️ Explore** — point it at a repo. Pathfinder reads the code (not the docs), ranks the highest-value next moves, asks a few sharp questions, then forges the goal:

```mermaid
flowchart LR
    A["<b>1 · DISCOVER</b><br/><i>read code, not docs</i>"]
    B["<b>2 · SCOUT</b><br/><i>brief each domain</i>"]
    C["<b>3 · SYNTHESIZE</b><br/><i>rank the next moves</i>"]
    V["<b>4 · VERIFY</b><br/><i>adversarially check the top moves</i>"]
    D["<b>5 · ASK</b><br/><i>a few sharp questions</i>"]
    E["<b>6 · FORGE /goal</b><br/><i>bounded · proven · ready to run</i>"]

    A --> B --> C --> V --> D --> E

    classDef step fill:#0F172A,stroke:#2DD4BF,stroke-width:2px,color:#E6EDF3;
    classDef forge fill:#0F172A,stroke:#F59E0B,stroke-width:2px,color:#FBBF24;
    class A,B,C,V,D step;
    class E forge;
```

**🎯 Prompt-to-goal** — already know the task? Hand Pathfinder a prompt and it researches only what that prompt touches, then forges the same goal — skipping the full sweep:

```text
Pathfinder, turn this into a /goal: make the dashboard empty-state stop crashing when the API returns no rows
```

<br>

## 📦 What you get

Every run drops a clean, resumable trail inside the repo:

```text
.agent-work/pathfinder/<date>-<task>/
├── 00-session.md              repo root, branch, tooling, objective
├── 01-blind-discovery.md      what the repo actually is
├── 02-scout-briefs/           located, evidence-graded findings per domain
├── 03-synthesis.md            ranked next moves + risks
├── 03b-verification.md        adversarial check of the Top 5 (grades, rejects, re-rank)
├── 04-question-funnel.md      the choices put to you
├── 05-user-answers.md         what you picked
├── 06-goal-command.md         a ready-to-copy /goal or grouped goal pack
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

## 🤝 Contributing and support

Contributions are welcome when they keep Pathfinder safe, bounded, and easy to run on unfamiliar repositories. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md), use the issue templates, and keep pull requests focused.

For usage help, see [`SUPPORT.md`](SUPPORT.md). Please report vulnerabilities privately through [`SECURITY.md`](SECURITY.md), not in public issues.

## 🧪 Project health

This repository uses GitHub Actions for manifest/version consistency, CodeQL workflow scanning, OpenSSF Scorecard security-health checks, and dependency review. `VERSION.md` remains the version and changelog source of truth.

<br>

<div align="center">

**Map the codebase. Pick the path. Forge the goal.**

MIT licensed · built for Claude Code and Codex

</div>
