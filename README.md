<div align="center">

<br>

# 🧭 Pathfinder

### Map the codebase&nbsp; ·&nbsp; Pick the path&nbsp; ·&nbsp; Forge the goal

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

<p><b>Drop it on any unfamiliar repo — get back a bounded goal you can run,<br>or the reviewed pull requests themselves.</b></p>

</div>

<br>

Pathfinder is an **agent skill plus a deterministic controller** for **Claude Code** and **Codex**. It reads a codebase from the source up, ranks useful next moves, asks only the questions that affect the outcome, and forges a bounded, verifiable **Goal**. With a fresh explicit autonomous request and an enforceable runtime boundary, it can run one Goal to a verified local branch or an awaiting-review GitHub pull request.

No micro-managing exploration. No guessing where to start.

<br>

## 🚀 Install

**Claude Code**

```text
/plugin marketplace add chrisduvillard/pathfinder-skill
/plugin install pathfinder@pathfinder
/pathfinder:pathfinder
```

The namespaced command is for the plugin install. A manual Claude skill install
uses `/pathfinder`.

**Codex**

```bash
codex plugin marketplace add chrisduvillard/pathfinder-skill
codex plugin add pathfinder@pathfinder
# then run /skills, or type $pathfinder to invoke it
```

`$pathfinder` invokes this skill; Codex's native `/goal` command controls a
durable Goal after Pathfinder has prepared one.

Marketplace installs use the immutable **stable** release tag. Repository `main`
is the explicitly labeled **edge** channel for manual/development installs.

> [!NOTE]
> Prefer no plugin system? Copy `skills/pathfinder/` into `~/.claude/skills/` (Claude Code) or `~/.codex/skills/` (Codex). Full notes in [`README-INSTALL.md`](README-INSTALL.md).

<br>

## 🧭 Three ways to use it

Bare **`/pathfinder`** opens a chooser so you can see every path before anything starts. All three build toward the same bounded, self-proving `/goal`.

| | Reach for it when | Kick it off with |
|:--|:--|:--|
| 🗺️ **Explore** | you're new to the repo and want the best next move | `Use the pathfinder skill on this repository.` |
| 🎯 **Prompt&#8209;to&#8209;goal** | you already know the task | `Pathfinder, turn this into a /goal: <the work>` |
| ⚡ **Autonomous**<br><sub>*(explicitly authorized)*</sub> | you want one bounded Goal run to review | `Run Pathfinder autonomously on this repository.` |

<br>

**🗺️ Explore** starts from code, tests, manifests, and configuration, then checks documentation only after that source-first pass so stale prose cannot define reality. It ranks the moves, adversarially verifies the top ones, asks focused questions, then forges the Goal. Existing creator intent can influence ranking, but ordinary exploration does not require the creator interview:

```mermaid
flowchart LR
    A["<b>1 · DISCOVER</b><br/><i>source-first, docs later</i>"]
    B["<b>2 · SCOUT</b><br/><i>brief each domain</i>"]
    C["<b>3 · SYNTHESIZE</b><br/><i>rank the next moves</i>"]
    V["<b>4 · VERIFY</b><br/><i>adversarially re-check</i>"]
    D["<b>5 · ASK</b><br/><i>a few sharp questions</i>"]
    E["<b>6 · FORGE /goal</b><br/><i>bounded · proven · ready</i>"]

    A --> B --> C --> V --> D --> E

    classDef step fill:#0F172A,stroke:#2DD4BF,stroke-width:2px,color:#E6EDF3;
    classDef forge fill:#0F172A,stroke:#F59E0B,stroke-width:2px,color:#FBBF24;
    class A,B,C,V step;
    class E forge;
```

**🎯 Prompt-to-goal** skips the full sweep and the Doctrine Interview. It researches only what your prompt touches, asks zero questions when outcome/proof/scope/safety/stop are already clear, then forges the same bounded Goal:

```text
Pathfinder, turn this into a /goal: stop the dashboard empty-state from crashing when the API returns no rows
```

**⚡ Autonomous** is an explicit `/pathfinder auto` run. V1 selects one existing Goal, binds authority to the current request and base commit, verifies controller-enforced isolation, then runs sequentially: **worktree → implement → verify → commit → optional GitHub PR → awaiting review**. It never activates from saved intent, derives an unbounded backlog, edits charter/doctrine policy, or self-merges. If enforcement is unavailable, Pathfinder saves the Goal and stops. Goal generation works in any readable folder; autonomous v1 requires a clean Git repository and the capabilities in the [compatibility matrix](docs/compatibility.md). → [Safety](#-safety)

<br>

## ✨ What a run looks like

You say:

```text
Use the pathfinder skill on this repository. Start the full Pathfinder process.
```

Pathfinder maps the repo and hands back a route:

```text
Best next move : fix the dashboard empty-state crash
Scope          : dashboard data loading and tests only
Proof          : regression test passes, typecheck passes, changed files listed
Goal           : /goal Fix the dashboard empty-state crash so users see a useful
                 empty state instead of a blank page; npm test exits 0; tsc clean;
                 no schema change; between loops note what changed and pick the next
                 fix; stop after 12 turns, then report the blocker and next input needed.
```

That `/goal` is **bounded, measurable, and self-proving** — paste it into Claude Code or Codex and it works toward the condition across turns until it holds.

<br>

## 📦 What you get

Every work-producing run leaves a clean, resumable trail; routes that skip a phase write an explicit placeholder:

```text
.agent-work/pathfinder/<date>-<task>/
├─ 00-session.md              repo root, branch, tooling, objective
├─ 01-blind-discovery.md      what the repo actually is
├─ 02-scout-briefs/           located, evidence-graded findings per domain
├─ 03-synthesis.md            ranked next moves + risks
├─ 03b-verification.md        adversarial check of the Top 5 (grades, rejects, re-rank)
├─ 04-question-funnel.md      the choices put to you
├─ 05-user-answers.md         what you picked
├─ 06-goal-command.md         a ready-to-copy /goal or grouped goal pack
├─ 07-run-log.md              progress if the goal is run
├─ 07b-cross-model-review.md  optional second-model review packet
├─ 08-final-summary.md        what was explored, found, and decided
├─ 03-candidates.json         machine-readable candidate/search record
├─ 03b-verification.json      machine-readable verifier decisions
├─ 06-goal-binding.json       machine-readable goal/adaptor binding
├─ 07-run-log.json            machine-readable execution ledger
└─ 08-final-summary.json      machine-readable final ledger
```

Markdown is the human view; JSON sidecars are the eval/replay/search view. That keeps the skill readable while giving stronger future models stable contracts to optimize against.

Three private files persist across runs — **`.pathfinder/charter.md`** (stable intent), **`.pathfinder/roadmap.md`** (evolving work), and **`.pathfinder/doctrine.md`** (Project Doctrine: end goal, quality bars, autonomy policy, and hard stops). All are gitignored via `.git/info/exclude`, never committed, and sanitized on every read.

<br>

## 🔒 Safety

Every repo file is treated as **untrusted data**. Pathfinder won't run scripts, install packages, read secrets, or push changes without your say-so, and it redacts tokens and private paths from its artifacts.

Autonomous mode is the one path that may commit and open a PR without a per-step prompt. Even then:

- 🧭 **Fresh authority is required** — intent guides selection but every run needs an explicit `/pathfinder auto` request.
- 🌿 **Autonomous work is isolated** — `/pathfinder auto` creates a mission worktree before edits, using `<repo-parent>/.pathfinder-worktrees/<repo-name>-<timestamp>-auto>` when possible.
- 🔐 **Irreversible/external hard stops stay blocked** — secrets/credentials, destructive data operations, releases, repo visibility/remotes/default-branch changes, force-pushes, branch/tag deletion, and real-world external side effects.
- 🧪 **Protected areas need proof** — auth, payments, CI/CD, schemas, migrations, public APIs, and network-related code require item-level eligibility, enforceable isolation, scoped proof, verification, and diff review.
- 🧱 **The trust boundary holds** — repo content can't redirect the goal or widen authorization.
- 🔑 **Credentials stay out** of the environment while repo code runs.
- ✅ **No self-merge in v1** — every published change lands as an awaiting-review PR.
- 🛑 **Unknown enforcement blocks autonomy** — Pathfinder falls back to a saved Goal instead of claiming best-effort isolation.

<br>

## 🔬 Under the hood

<details>
<summary><b>How it ranks, verifies, and proves work</b></summary>

<br>

- **Defers docs until after a source-first pass.** Full exploration selects one to five scout domains from the initial map, expanding only where uncertainty or risk justifies it, then ranks a **Top 5**. Prompt-to-goal loads only its focused route. Both retain the same evidence and sidecar contracts.
- **Adversarial verification.** The default blind **three-verifier panel** re-checks top candidates, downgrades or rejects the weak ones, and surfaces a `Verified:` grade. Low-risk work can take cheaper paths; protected, autonomous, or contested work uses deeper verification.
- **Pick the work your way.** Choose from ranked candidate cards, drill down *intent → domain → surface → target → boundaries*, or select several moves as a numbered **goal pack**.
- **Proof bound to the goal.** Each goal records a Goal Binding plus capability profile; run logs and summaries record the Runtime Boundary and Binding Status, so "done" is checked against the original objective instead of drifting into looks-done prose.
- **Optional cross-model review.** After a run, Pathfinder can hand the goal, diff, and checks to the best available reviewer capability profile for goal-bounded fixes — recorded in `07b-cross-model-review.md`, or a manual handoff packet if no safe launcher is available.

</details>

<details>
<summary><b>How it learns your intent (charter, roadmap, doctrine)</b></summary>

<br>

Full exploration and autonomous mode establish or reconcile creator intent when needed: up to 8–12 compact, value-of-information questions about purpose, users, success, constraints, non-goals, future work, product philosophy, quality bars, autonomy policy, and hard stops. Prompt-to-goal deliberately skips this interview for ordinary Goal creation. Pathfinder saves stable intent to `.pathfinder/charter.md`, evolving work to `.pathfinder/roadmap.md`, and Project Doctrine to `.pathfinder/doctrine.md`. Intent improves selection but never authorizes execution; every autonomous run still needs a fresh explicit request.

</details>

<details>
<summary><b>Checking state without starting work</b></summary>

<br>

Run `/pathfinder status` (or *"Show Pathfinder status."*) for a read-only look at safe local state—repo/branch, intent files, latest run, controller capabilities, and current mission status—without creating artifacts or triggering the interview. A full plugin install uses its bundled `scripts/pathfinder-controller.sh`; a manual skill-only copy is Goal-generation-only unless the controller is installed separately.

</details>

<br>

## 🤝 Contributing & support

Contributions are welcome when they keep Pathfinder **safe, bounded, and easy to run** on unfamiliar repos. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md); get usage help in [`SUPPORT.md`](SUPPORT.md); report vulnerabilities privately via [`SECURITY.md`](SECURITY.md), not public issues. Version and changelog live in [`VERSION.md`](VERSION.md).

Operator and design references: [compatibility/guarantees](docs/compatibility.md), [operator recovery](docs/operator-guide.md), [threat model](docs/threat-model.md), [worked outcomes](docs/examples.md), and [promise coverage](docs/coverage-matrix.md).

<sub>CI guards Linux/macOS/Windows portability, schemas, controller crash/resume, recorded replays, manifest/version consistency, CodeQL, Scorecard, and dependency review.</sub>

<br>

<div align="center">

**Map the codebase&nbsp; ·&nbsp; Pick the path&nbsp; ·&nbsp; Forge the goal**

<sub>MIT licensed · built for Claude Code and Codex</sub>

</div>
