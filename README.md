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

<p><b>Drop it on any unfamiliar repo, hand it a prompt, or let it run hands-off — get back a bounded goal you can run, or the merged PRs themselves.</b></p>

</div>

<br>

Pathfinder is a small agent skill for **Claude Code** and **Codex**. It reads a codebase from the source up, proposes useful work, asks a few sharp questions, then writes a bounded, verifiable goal you can execute or hand to another agent — or, opt-in, runs the work itself all the way to a merged pull request.

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

Then use it three ways:

- **Explore a repo** — *"Use the pathfinder skill on this repository."*
- **Turn a task into a goal** — *"Pathfinder, turn this into a /goal: &lt;the work you want done&gt;."*
- **Run it autonomously** *(opt-in)* — *"Run Pathfinder autonomously on this repository."*

<br>

## 🔭 How it works

Three ways in — explore a repo, hand it a prompt, or let it run autonomously — all built on the same bounded, verifiable `/goal`.

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

**⚡ Autonomous** *(opt-in)* — want it hands-off? Invoke it explicitly and Pathfinder runs the normal exploration, asks the one-time objectives interview if no local charter exists yet, then implements, verifies, commits, pushes, opens a PR, and self-merges every verified move — one goal at a time, end to end:

```text
Run Pathfinder autonomously on this repository.
```

It is hands-off after charter preflight: later runs reuse `.pathfinder/charter.md`, and you can refresh it with `/pathfinder charter`. Pathfinder only ever self-merges where the repo's own branch protection allows it (otherwise it leaves a green PR for you to merge), isolates a failing goal and keeps going, and **never** auto-touches the dangerous categories (auth, payments, migrations, secrets, CI, public APIs). It's an explicit escalation — Pathfinder never enters this mode on an ordinary invocation. See [Safety](#-safety).

Two details matter when you expect questions: Pathfinder asks the charter interview only when `.pathfinder/charter.md` is missing; if that file already exists, it reuses it and tells you to run `/pathfinder charter` to refresh. Update or reinstall the plugin to v2.17.3 or newer before testing this behavior, because older installed caches skip the autonomous charter preflight.

<br>

## 🧰 What Pathfinder can do

A map of the full capability set:

**🔍 Understand any codebase** — reads the repo from the **source up** (code, tests, configs, routes, schemas — not the README, so a stale or missing doc never misleads it). Five domain **scouts** (architecture, frontend/product, backend/data, testing/reliability, DX/security) produce located, evidence-graded findings, synthesized into a ranked **Top 5** of the highest-value next moves (impact ÷ effort; confirmed > inferred > suspected).

**✅ Trust the findings** — an adversarial, blind **three-verifier panel** re-checks every Top-5 candidate, downgrades or rejects the weak ones, and surfaces a `Verified:` grade — so you act on confirmed work, not a hunch.

**🎛️ Pick the work, your way** — choose the move through whichever lens fits:
- **Pick a move** — select from ranked, evidence-bearing candidate cards.
- **Explore from scratch** — drill down intent → domain → surface → target → boundaries.
- **Goal packs** — select several moves and Pathfinder groups them into numbered, separately-bounded goals.

**🎯 Forge a runnable goal** — produces a bounded, measurable, self-proving Claude Code **`/goal`** (or an `Implementation Goal` fallback for Codex and older clients): one end state, exact proof checks, constraints, protected areas, and stop bounds — kept under 3900 characters.

**⌨️ Skip the sweep when you already know the task** — **Prompt-to-goal**: hand it a task description and it researches only what that prompt touches, then forges the same bounded goal.

**⚡ Run it hands-off** *(opt-in)* — **autonomous mode** executes the verified moves end to end — branch → implement → verify → commit → push → open a PR → self-merge where the repo's rules allow — one goal at a time, isolating a failing goal and continuing. See [Safety](#-safety).

**🗂️ Leave a clean trail** — every run writes a resumable `00–08` artifact set under `.agent-work/` (see [What you get](#-what-you-get)).

**🧠 Remember what the project is for** — a short, one-time interview (it suggests the answers from your code) saves the project's **north-star, users, and constraints** to a private, local-only `.pathfinder/charter.md`. The first autonomous run may ask this before going hands-off; later runs reuse it to steer interactive rankings and frame goals — always visibly, so you can override or refresh it.

**🧩 Run anywhere** — works as a plugin or a manual install, in both **Claude Code** and **Codex**.

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

Separately, `.pathfinder/charter.md` holds your durable project objectives. Unlike the per-run `.agent-work/` trail above, it **persists across runs** — and stays private: gitignored via `.git/info/exclude`, never committed. If it already exists, Pathfinder does not re-ask the one-time interview unless you run `/pathfinder charter`.

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

**Autonomous mode** is the one path that runs and merges without a per-step prompt — and only when you invoke it explicitly. Even then the trust boundary holds: repo content can't redirect the work, dangerous-category changes (auth, payments, migrations, secrets, CI, public APIs) are excluded from automated execution and hard-blocked on the real diff, the push credential is kept out of the environment while repo code runs, and a self-merge happens only on a positive branch-protection signal — never just because nothing blocked it.

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
