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

<p><b>Drop it on any unfamiliar repo — get back a bounded goal you can run,<br>with deterministic artifacts and honest capability checks.</b></p>

</div>

<br>

Pathfinder is an **agent skill plus a deterministic local controller** for **Claude Code** and **Codex**. It reads a codebase from the source up, ranks useful next moves, asks only the questions that affect the outcome, and forges a bounded, verifiable **Goal**. On a compatible attested host, it can also journal one typed action at a time through a verified local branch. If the host cannot prove its runtime boundary, expose a stable native Goal, or return truthful typed receipts, Pathfinder stops at the saved Goal/manual handoff.

No micro-managing exploration. No guessing where to start.

<br>

## ✅ What works today

| Capability | Current boundary |
|:--|:--|
| Explore an unfamiliar codebase and rank useful work | **Supported** in any readable folder |
| Turn a concrete request into a bounded `/goal` | **Supported** without the full exploration interview |
| Drive one Goal or an approved fixed pack | **Conditional** on host attestation; sequential, isolated, and local-only |
| Inspect local Pathfinder state | **Supported** through the skill's read-only status route |
| Inspect operator-supplied merge-readiness evidence | **Observation-only on POSIX** with `merge status` / `merge evaluate`; Windows fails closed; no network, credential, intent, or merge |
| Publish a PR from the enabled controller | **Not enabled** |
| Automatically merge, release, deploy, force-push, or handle secrets | **Not supported by the current release**; PR merging stays manual |

Pathfinder includes carefully tested, default-off publication and merge building blocks for future
trusted-host integrations. The publication and merge-execution paths have no installed caller,
credential loader, or execution command and do not expand the capabilities above.

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
# then run /skills, or type $pathfinder:pathfinder to invoke it
```

Codex namespaces plugin skills as `$plugin-name:skill-name`, so the plugin form
is `$pathfinder:pathfinder`. A manual Codex skill remains `$pathfinder`.
Codex's native `/goal` command controls a durable Goal after Pathfinder has
prepared one.

Marketplace installs use the immutable **stable** release tag. Repository `main`
is the explicitly labeled **edge** channel for manual/development installs.

> [!NOTE]
> Prefer no plugin system? Copy `skills/pathfinder/` into `~/.claude/skills/` (Claude Code) or `~/.agents/skills/` (Codex). Full notes in [`README-INSTALL.md`](README-INSTALL.md).

<br>

## ▶️ First run

1. Invoke the installed Pathfinder skill and choose **Explore**, **Prompt-to-goal**, or **Autonomous**.
2. Review the proposed scope, proof checks, safety boundary, and stop condition.
3. Start the bounded Goal, or let an attested host drive the local autonomous route.
4. Invoke the skill and choose **Status** whenever you want a read-only view of intent, artifacts, and mission state.
5. If separately authorized host tooling creates a pull request, review and merge it yourself; the
   enabled Pathfinder controller neither creates nor merges it.

The safest starting point is simply:

```text
Use the pathfinder skill on this repository.
```

<br>

## 🧭 Three ways to use it

Invoke **`/pathfinder:pathfinder`** in a Claude plugin install, **`$pathfinder:pathfinder`** in a Codex plugin install, or the shorter host-specific name for a manual skill install. The chooser shows every path before anything starts. All three build toward the same bounded, self-proving `/goal`.

| | Reach for it when | Kick it off with |
|:--|:--|:--|
| 🗺️ **Explore** | you're new to the repo and want the best next move | `Use the pathfinder skill on this repository.` |
| 🎯 **Prompt&#8209;to&#8209;goal** | you already know the task | `Pathfinder, turn this into a /goal: <the work>` |
| ⚡ **Autonomous**<br><sub>*(host-attested)*</sub> | you want one bounded Goal driven to a local review branch | `Run Pathfinder autonomously on this repository.` |

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

The controller derives the repository identity and scope fingerprint; the model does not invent
them. A dirty Git tree blocks saved artifacts by default. You may explicitly choose a
**committed-base Goal**, which binds execution to the current committed `HEAD`, preserves all local
edits, and prints a warning that those edits are excluded; the save command requires the separate
`--acknowledge-committed-base` gate. On POSIX, non-Git source folders save canonical artifacts only
in an explicit owner-only work directory outside the source folder. Other platforms keep the Goal
in native/manual handoff until equivalent ownership proof exists. Autonomous branch/commit
execution remains unavailable for non-Git folders.

**⚡ Autonomous** is the chooser's explicitly gated autonomous route. The enabled bridge is one sequential local Goal: **worktree → native Goal → implement → verify → commit → local awaiting review**. It binds authority to the current request and base commit and journals each intent/receipt/result before advancing. It never activates from saved intent, derives an unbounded backlog, edits charter/doctrine policy, publishes, or self-merges. Unknown enforcement, missing native Goal identity, or an ambiguous action response stops or requires reconciliation. A surrounding agent host may separately offer GitHub tools under its own user authorization, but those effects are outside Pathfinder's controller guarantee. → [Compatibility](docs/compatibility.md) · [Safety](#-safety)

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

Every work-producing run leaves a clean, resumable trail. Only phases the route actually uses are emitted; a short placeholder is reserved for an expected phase that started but was interrupted:

```text
.agent-work/pathfinder/<date>-<task>/
├─ 00-session.md              repo root, branch, tooling, objective
├─ 01-blind-discovery.md      what the repo actually is
├─ 02-scout-briefs/           compact findings for selected domains only
├─ 03-synthesis.md            ranked next moves + risks
├─ 03b-verification.md        adversarial check of the Top 5 (grades, rejects, re-rank)
├─ 04-question-funnel.md      the choices put to you
├─ 05-user-answers.md         what you picked
├─ 06-goal-command.md         a ready-to-copy /goal or grouped goal pack
├─ goals/NNNN/                per-item bindings and controller views for a run-all pack
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

Three canonical private JSON documents persist across runs—`charter.json` (stable intent), `roadmap.json` (evolving work), and `doctrine.json` (Project Doctrine: end goal, quality bars, autonomy policy, and hard stops)—with generated Markdown views for humans. Repository intent lives in `.pathfinder/`; an explicit monorepo scope such as `apps/api` gets the isolated namespace `.pathfinder/scopes/apps/api/intent/`. Namespaces never inherit from root or siblings. All are gitignored via `.git/info/exclude`, never committed, schema-validated, and sanitized on every read.

<br>

## 🔒 Safety

Every repo file is treated as **untrusted data**. Pathfinder won't run scripts, install packages, read secrets, or push changes without your say-so, and it redacts tokens and private paths from its artifacts.

The local autonomous bridge is the only path designed to commit without a per-step prompt. It cannot publish or open a PR. It is enabled only for an attested host, and all of these rules apply:

- 🧭 **Fresh authority is required** — intent guides selection but every run needs an explicit `/pathfinder auto` request.
- 🌿 **Autonomous work is isolated** — the attested host creates a mission worktree before edits, using `<repo-parent>/.pathfinder-worktrees/<repo-name>-<timestamp>-auto>` when possible.
- 🔐 **Irreversible/external hard stops stay blocked** — secrets/credentials, destructive data operations, releases, repo visibility/remotes/default-branch changes, force-pushes, branch/tag deletion, and real-world external side effects.
- 🏷️ **Repository releases are deliberate** — merging or editing `VERSION.md` cannot publish a release. A maintainer must separately dispatch the release workflow from `main` and confirm the exact declared version.
- 🧪 **Protected areas need proof** — a versioned data registry classifies auth, payments, permissions, deployment, CI/CD, schemas, migrations, public APIs, and network egress; autonomous work requires declared scope, item-level eligibility, enforceable isolation, verification, and diff review. Explicit policy may add protection but cannot weaken the baseline.
- 🧱 **The trust boundary holds** — repo content can't redirect the goal or widen authorization.
- 🔑 **Credentials stay out** of the environment while repo code runs.
- ✅ **No publication or self-merge** — the enabled bridge stops at a local awaiting-review branch with no PR.
- 🛑 **Unknown enforcement blocks autonomy** — Pathfinder falls back to a saved Goal instead of claiming best-effort isolation.

Security-sensitive Pathfinder development uses a fixed-target quorum of independent standards,
specification-fidelity, and adversarial-security agents. That quorum is development evidence only:
it cannot create runtime authority, load credentials, or approve a merge. In the current release,
pull-request merging remains a deliberate manual action.

<br>

## 🔬 Under the hood

<details>
<summary><b>How it ranks, verifies, and proves work</b></summary>

<br>

- **Defers docs until after a source-first pass.** Full exploration selects one to five scout domains from the initial map, expanding only where uncertainty or risk justifies it, then ranks a **Top 5**. Prompt-to-goal loads only its focused route. Both retain the same evidence and sidecar contracts.
- **Adversarial verification.** The default blind **three-verifier panel** re-checks top candidates, downgrades or rejects the weak ones, and surfaces a `Verified:` grade. Low-risk work can take cheaper paths; protected, autonomous, or contested work uses deeper verification.
- **Pick the work your way.** Choose from ranked candidate cards, drill down *intent → domain → surface → target → boundaries*, or select several moves as a numbered **goal pack**.
- **Resume an approved pack safely.** An explicit `run all` approval can be sealed as an ordered binding-hash queue. Pathfinder activates one native Goal at a time, requires typed completion before advancing, and stops the pack on any blocker instead of skipping ahead.
- **Proof bound to the goal.** Each goal records a Goal Binding plus capability profile; run logs and summaries record the Runtime Boundary and Binding Status, so "done" is checked against the original objective instead of drifting into looks-done prose.
- **Optional cross-model review.** After a run, Pathfinder can hand the goal, diff, and checks to the best available reviewer capability profile for goal-bounded fixes — recorded in `07b-cross-model-review.md`, or a manual handoff packet if no safe launcher is available.
- **Meaningful progress, not play-by-play.** Updates appear when the route, evidence, Goal, execution disposition, or required input changes; each says what changed, the strongest evidence, and the next gate instead of listing every file or internal check.

</details>

<details>
<summary><b>How it learns your intent (charter, roadmap, doctrine)</b></summary>

<br>

Full exploration and autonomous-request preparation establish or reconcile creator intent when needed: up to 8–12 compact, value-of-information questions about purpose, users, success, constraints, non-goals, future work, product philosophy, quality bars, autonomy policy, and hard stops. Prompt-to-goal deliberately skips this interview for ordinary Goal creation. After explicit creator confirmation, the controller activates all three canonical JSON documents together in the selected repository or subproject namespace and renders replaceable Markdown views. Intent improves selection but never authorizes execution; every local autonomous run still needs a fresh explicit request.

</details>

<details>
<summary><b>Checking state without starting work</b></summary>

<br>

Invoke Pathfinder and choose **Status** (or say *"Show Pathfinder status."*) for a read-only look at safe local state—repo/branch, intent files, latest run, controller capabilities, and current mission status—without creating artifacts or triggering the interview. In Claude this is `/pathfinder:pathfinder` for the plugin or `/pathfinder` for a manual skill. In Codex it is `$pathfinder:pathfinder` for the plugin or `$pathfinder` for a manual skill. A full plugin install uses its bundled `scripts/pathfinder-controller.sh`; a manual skill-only copy is Goal-generation-only unless the controller is installed separately.

</details>

<details>
<summary><b>Advanced: inspecting merge readiness without merging</b></summary>

<br>

Operators with an owner-only, externally supplied awaiting-review publication journal can ask the
bundled controller to validate the exact persisted PR, policy, authorization, and two evidence
snapshots:

```bash
bash scripts/pathfinder-controller.sh merge status --repo-root <repository> --host-dir <host-dir> --publication-request-id <id> --json
bash scripts/pathfinder-controller.sh merge evaluate --repo-root <repository> --host-dir <host-dir> --publication-request-id <id>
```

These commands are deliberately observation-only. They do not contact GitHub, discover a PR, expose
a readiness proof, load a writer credential, create an intent, or merge. Missing, malformed, expired,
unsupported, or drifted input fails closed. The CLI proves local current-user ownership, permissions,
out-of-repository placement, and symlink-safe reads; it does not instantiate the separate uninstalled
external-authenticator adapter. This inspection path is POSIX-only and fails closed on Windows. See the
[operator guide](docs/operator-guide.md#inspect-conditional-merge-readiness) for the protected host
directory layout and platform boundary.

</details>

<br>

## 🤝 Contributing & support

Contributions are welcome when they keep Pathfinder **safe, bounded, and easy to run** on unfamiliar repos. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md); get usage help in [`SUPPORT.md`](SUPPORT.md); report vulnerabilities privately via [`SECURITY.md`](SECURITY.md), not public issues. Version and changelog live in [`VERSION.md`](VERSION.md).

Operator and design references: [compatibility/guarantees](docs/compatibility.md), [operator recovery](docs/operator-guide.md), [protected surfaces](docs/protected-surfaces.md), [threat model](docs/threat-model.md), [worked outcomes](docs/examples.md), and [promise coverage](docs/coverage-matrix.md).

<sub>CI guards Linux/macOS/Windows portability, schemas, controller crash/resume, recorded replays, manifest/version consistency, CodeQL, Scorecard, and dependency review.</sub>

<br>

<div align="center">

**Map the codebase&nbsp; ·&nbsp; Pick the path&nbsp; ·&nbsp; Forge the goal**

<sub>MIT licensed · built for Claude Code and Codex</sub>

</div>
