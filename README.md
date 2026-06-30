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

Then start with the options menu or jump directly:

- **Show the options** — *"Show the Pathfinder options."* or bare `/pathfinder`
- **Explore a repo** — *"Use the pathfinder skill on this repository."*
- **Turn a task into a goal** — *"Pathfinder, turn this into a /goal: &lt;the work you want done&gt;."*
- **Run it autonomously** *(opt-in)* — *"Run Pathfinder autonomously on this repository."*
- **Refresh creator model** — *"/pathfinder charter"*
- **Check local state** — *"Show Pathfinder status."* or `/pathfinder status`

<br>

## 🔭 How it works

Bare `/pathfinder` first shows a compact chooser, so you can see the available paths before anything starts. The main work paths — explore a repo, hand it a prompt, or let it run autonomously — all build toward the same bounded, verifiable `/goal`.

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

**⚡ Autonomous** *(opt-in)* — autonomous mode is explicit opt-in. Pathfinder first ensures the Deep Intent Gate has captured the creator model, then requires a model-depth proof gate before deriving unattended work from `.pathfinder/charter.md`, `.pathfinder/roadmap.md`, and current repo evidence. It implements, runs deep verification/testing, commits, pushes, opens a PR, and self-merges where allowed; updates the roadmap; and continues until the work is complete, blocked, unsafe, ambiguous, or budget-limited:

```text
Run Pathfinder autonomously on this repository.
```

Later runs reuse `.pathfinder/charter.md` and `.pathfinder/roadmap.md`, and you can refresh them with `/pathfinder charter`. Pathfinder may isolate a recoverable per-goal failure and continue to another independent eligible goal; parallel execution is allowed only after an independence check proves separate branches/worktrees, disjoint surfaces, and separate verification. It **never** auto-touches the dangerous categories (auth, payments, migrations, secrets, CI, public APIs). It's an explicit escalation — Pathfinder never enters this mode on an ordinary invocation. See [Safety](#-safety).

Two details matter when you expect questions: on first use, Pathfinder asks the Deep Intent Gate questions by default for every entry point, including autonomous mode. Later runs reuse `.pathfinder/charter.md` and `.pathfinder/roadmap.md`; run `/pathfinder charter` to refresh or deepen either file.

**Status/help** — want the lay of the land without starting work? Run `/pathfinder status` to inspect safe local state: current repo/branch, whether the charter and roadmap exist and are complete, the latest visible Pathfinder run, and the same entry paths shown by the chooser. It is read-only and then returns to the chooser.

<br>

## 🧰 What Pathfinder can do

A map of the full capability set:

**🧭 Show the chooser first** — bare `/pathfinder` opens a compact menu of Pathfinder paths: explore the repo, turn a prompt into a goal, run autonomously, refresh the creator model, or show status/help.

**🔍 Understand any codebase** — reads the repo from the **source up** (code, tests, configs, routes, schemas — not the README, so a stale or missing doc never misleads it). Five domain **scouts** (architecture, frontend/product, backend/data, testing/reliability, DX/security) produce located, evidence-graded findings, synthesized into a ranked **Top 5** of the highest-value next moves (impact ÷ effort; confirmed > inferred > suspected).

**✅ Trust the findings** — an adversarial, blind **three-verifier panel** re-checks every Top-5 candidate, downgrades or rejects the weak ones, and surfaces a `Verified:` grade — so you act on confirmed work, not a hunch.

**🎛️ Pick the work, your way** — choose the move through whichever lens fits:
- **Pick a move** — select from ranked, evidence-bearing candidate cards.
- **Explore from scratch** — drill down intent → domain → surface → target → boundaries.
- **Goal packs** — select several moves and Pathfinder groups them into numbered, separately-bounded goals.

**🎯 Forge a runnable goal** — produces a bounded, measurable, self-proving Claude Code **`/goal`** (or an `Implementation Goal` fallback for Codex and older clients): one end state, exact proof checks, constraints, protected areas, and stop bounds — kept under 3900 characters.

**Add a second-model review** *(opt-in)* — after a goal run finishes or hits an ordinary blocker, Pathfinder can hand the original goal, diff summary, checks, and run log to the opposite local subscription tool (Claude Code after Codex/ChatGPT, or Codex after Claude). The reviewer can make simple goal-bounded fixes and related polish, then Pathfinder records the result in `07b-cross-model-review.md`. If no local launcher is available, the artifact becomes a manual handoff packet.

**⌨️ Skip the sweep when you already know the task** — **Prompt-to-goal**: hand it a task description and it researches only what that prompt touches, then forges the same bounded goal.

**⚡ Run it hands-off** *(opt-in)* — **autonomous mode** is explicit opt-in. Pathfinder first captures the creator model through the Deep Intent Gate, passes a model-depth proof gate for each derived goal, then runs full code implementation plus deep verification/testing and optional Cross-Model Review - branch -> implement -> verify -> review when enabled -> commit -> push -> open a PR -> conditional self-merge where the repo's rules allow - updating the roadmap and continuing until the work is complete, blocked, unsafe, ambiguous, or budget-limited. Parallel goal work is default-deny unless independence is proven first. See [Safety](#-safety).

**🗂️ Leave a clean trail** — every run writes a resumable `00–08` artifact set under `.agent-work/` (see [What you get](#-what-you-get)).

**🧠 Understands creator intent deeply** — on first use, Pathfinder asks 8 to 12 compact questions about purpose, users, success, constraints, non-goals, finished state, autonomy policy, and future capabilities not started yet. It saves stable intent to `.pathfinder/charter.md` and evolving desired work to `.pathfinder/roadmap.md`; later runs reuse both, show their influence, and let you refresh or override them.

**🧾 Show status without starting work** — `/pathfinder status` reports safe local Pathfinder state and available paths without creating run artifacts or triggering the Deep Intent Gate.

**🧩 Run anywhere** — works as a plugin or a manual install, in both **Claude Code** and **Codex**.

<br>

## 📦 What you get

Every run drops a clean, resumable trail inside the repo:

```text
.agent-work/pathfinder/<date>-<task>/
|-- 00-session.md              repo root, branch, tooling, objective
|-- 01-blind-discovery.md      what the repo actually is
|-- 02-scout-briefs/           located, evidence-graded findings per domain
|-- 03-synthesis.md            ranked next moves + risks
|-- 03b-verification.md        adversarial check of the Top 5 (grades, rejects, re-rank)
|-- 04-question-funnel.md      the choices put to you
|-- 05-user-answers.md         what you picked
|-- 06-goal-command.md         a ready-to-copy /goal or grouped goal pack
|-- 07-run-log.md              progress if the goal is run
|-- 07b-cross-model-review.md  optional second-model review packet, verdicts, and fixes
\-- 08-final-summary.md        what was explored, found, and decided
```

Separately, `.pathfinder/charter.md` holds stable creator intent and `.pathfinder/roadmap.md` holds evolving desired work. Both persist across runs, stay private, are gitignored via `.git/info/exclude`, are never committed, and are sanitized on every read.

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

Then run `/pathfinder` in Claude Code to see the chooser, or `$pathfinder` (or `/skills`) in Codex. See [`README-INSTALL.md`](README-INSTALL.md) for `/goal` compatibility notes.

<br>

## 🔒 Safety

Pathfinder treats every repo file as **untrusted data**. It does not run repo scripts, install packages, open secrets, or push changes unless you approve. Tokens, credentials, and private paths are redacted from its artifacts.

**Autonomous mode** is the one path that runs and merges without a per-step prompt — and only when you invoke it explicitly. Even then the trust boundary holds: goals come from sanitized intent files plus current repo evidence after a model-depth proof gate, repo content can't redirect the work, dangerous-category changes (auth, payments, migrations, secrets, CI, public APIs) are excluded from automated execution and hard-blocked on the real diff, safety/manual/ambiguity/budget boundaries stop the run, parallel work requires a proven independence check, the push credential is kept out of the environment while repo code runs, and a self-merge happens only on a positive branch-protection signal — never just because nothing blocked it.

Cross-Model Review is opt-in and does not widen authorization. It uses local subscription tools when available, never APIs, OpenRouter, browser automation, or hidden credentials in v1, and falls back to a manual handoff packet when a reviewer cannot be launched. Reviewer fixes stay inside the original goal boundary; safety/manual/protected stops go back to the user.

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
