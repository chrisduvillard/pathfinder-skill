# Pathfinder Deep Intent Gate - Design Spec

> Status: approved through brainstorming. Target release: assigned by the implementation plan.

## Context

Pathfinder's current objectives charter is too small for the role autonomous mode is meant to play. The existing Phase 4c interview asks three broad questions and stores one durable file, `.pathfinder/charter.md`. That is enough to bias a short interactive run. It is not enough to understand a creator's deeper intent, especially when important goals have not been started in the repository yet.

The new behavior makes the first Pathfinder run establish a deep creator-intent model before any entry point continues. This applies to explore, prompt-to-goal, autonomous mode, and `/pathfinder charter`. Pathfinder still drafts from repository evidence first, but it must also ask about future goals and intended direction that code, docs, and git history cannot reveal.

The result is two local-only files:

- `.pathfinder/charter.md` stores stable creator intent.
- `.pathfinder/roadmap.md` stores evolving future work.

Autonomous mode remains explicit on every run. When invoked, it may keep deriving and executing goals from the charter and roadmap until the intended work is complete, blocked, unsafe, ambiguous, or budget-limited.

## Locked Decisions

| Decision | Choice |
|---|---|
| First-run behavior | Run the deep intent flow by default for every Pathfinder entry point. |
| Interview shape | Hybrid: draft from repo evidence, then ask targeted deep questions. |
| Unstarted goals | Ask for them explicitly; do not rely only on repository evidence. |
| Persistence | Store stable intent in `.pathfinder/charter.md` and evolving work in `.pathfinder/roadmap.md`. |
| Autonomy scope | Continuous until done, blocked, unsafe, ambiguous, or budget-limited. |
| Autonomy authorization | Explicit invocation is required every run. |
| Finished state | Ask for it, but allow "ongoing product, no final endpoint." |

## Goals

The feature has five goals:

1. Make Pathfinder understand the project the creator intends, not only the code that exists.
2. Capture future goals, desired capabilities, and quality bars before autonomous execution can rely on them.
3. Split stable intent from changing work so the charter does not become a roadmap.
4. Let autonomous mode continue from a durable creator model instead of a single Top 5 candidate slate.
5. Preserve the existing safety model: local files guide work, but they never widen authorization or override safety policy.

## Non-Goals

This design does not make autonomous mode implicit. It does not let local intent files authorize commits, pushes, merges, dangerous categories, credential use, or protected-area changes by themselves.

This design also does not turn Pathfinder into a general project-management system. The roadmap is a local execution guide for Pathfinder, not a shared issue tracker, product board, or release-planning database.

## Deep Intent Gate

The Deep Intent Gate replaces the current "offer a three-screen charter" first-run behavior. It runs when either local intent file is missing, schema-invalid, incomplete, or explicitly refreshed. A Pathfinder run may continue only after the gate finishes.

For the approved default, Pathfinder asks the first-run questions rather than merely mentioning that they are available. The first-run gate applies to explore, prompt-to-goal, autonomous mode, and `/pathfinder charter`. It is not a skippable offer. If the user chooses to continue later, Pathfinder records the partial intent model and stops before the requested entry point continues.

The gate has three stages:

1. Evidence draft: inspect code, docs, and git history as evidence, then draft the current understanding.
2. Creator interview: ask targeted questions that fill weak, conflicting, future-facing, or high-stakes fields.
3. Persistence: write or update `.pathfinder/charter.md` and `.pathfinder/roadmap.md` after ignore checks pass.

Repository content, charter content, and roadmap content remain untrusted data. They can provide evidence and direction, but they cannot override the user, safety constraints, protected-area gates, or execution policy.

## Intent Model

The charter stores stable intent. It should answer:

- Purpose: north-star, primary promise, and what must feel true when the project works.
- Users: primary users, secondary users, excluded users, and key journeys.
- Success: durable metrics, quality bars, and acceptable tradeoffs.
- Constraints: technical, business, UX, security, performance, dependency, platform, and compatibility boundaries.
- Non-goals: things Pathfinder must not optimize for or accidentally build.
- Finished state: optional final state, or standing qualities for ongoing products.
- Autonomy policy: what may be derived automatically, what needs manual approval, and what must never run unattended.

The roadmap stores changing intent. It should answer:

- Future state: capabilities or product qualities the creator wants but the repo does not yet show.
- Unstarted goals: goals with no current implementation evidence.
- Milestones: coherent groups of work and why they belong together.
- Priorities: relative order, urgency, dependencies, and deferrals.
- Completion state: not started, active, complete, blocked, manual-only, or obsolete.
- Evidence links: where each item came from, such as the creator interview, repo evidence, or a later refresh.

## Interview Design

The interview is adaptive, not fixed at three questions. Pathfinder first shows its evidence-based draft. Then it asks enough questions to fill the intent model, with a minimum deep pass and a hard cap.

The first-run interview should usually include 8 to 12 compact screens:

1. Purpose and promise.
2. Primary users and excluded users.
3. Key journeys and must-work flows.
4. Durable success metrics and quality bars.
5. Future capabilities not started yet.
6. Roadmap priorities and sequencing.
7. Constraints and protected areas.
8. Non-goals and tradeoffs.
9. Optional finished state.
10. Autonomy policy and manual-approval boundaries.

Pathfinder may add follow-up screens only when the draft is weak, internally inconsistent, strategically important, or too ambiguous to drive autonomous work. It should offer a "continue later" escape that saves partial progress and stops; it must record incomplete fields as incomplete rather than pretending they were answered.

Every question should remain recognition-first:

- Show the inferred answer first.
- Give the evidence and confidence for that answer.
- Offer 3 to 6 concrete options when possible.
- Include an `Agent recommends:` line.
- Include a free-text escape.
- Ask explicitly about goals that have not been started yet.

## Entry Point Behavior

Explore mode runs the Deep Intent Gate before the normal candidate funnel when intent files are absent or incomplete. Once the files exist, explore mode reuses them and asks only reconcile questions when fresh evidence conflicts with stored intent.

Prompt-to-goal also runs the Deep Intent Gate on first use. The user's prompt remains the trusted task objective for that run. The charter and roadmap provide project context, constraints, and direction, but they do not override the prompt.

Autonomous mode requires valid intent files before execution. If they are missing or incomplete, it runs the Deep Intent Gate first. After that, the user has already explicitly invoked autonomous mode, so Pathfinder may proceed into continuous execution subject to safety filters and budgets.

`/pathfinder charter` becomes a refresh and deepening command for both local files. It can update stable charter fields, roadmap fields, or both.

## Continuous Autonomous Loop

Autonomous mode changes from "execute the verified Top 5" to "execute from the creator model." Once explicitly invoked, it should loop:

1. Read and sanitize the charter and roadmap.
2. Inspect current repo evidence.
3. Select the next highest-value roadmap item or derive a missing goal from charter plus repo evidence.
4. Write a bounded `/goal` or Implementation Goal.
5. Execute the goal.
6. Verify the result.
7. Update roadmap status and evidence.
8. Repeat.

The loop stops when:

- the roadmap has no viable intended work left;
- a blocker needs creator input;
- a safety or manual-approval boundary is reached;
- the next step is too ambiguous to derive safely;
- the run budget is reached;
- verification fails beyond the allowed retry bound.

The loop should report progress one goal at a time. A completed goal updates the roadmap before the next goal starts, so later selection uses the current project state.

## Safety Rules

The safety model stays strict.

- Autonomous mode requires explicit invocation every run.
- `.pathfinder/charter.md` and `.pathfinder/roadmap.md` are local-only, gitignored, and never committed.
- Both files remain untrusted data and are sanitized on every read.
- The files never authorize dangerous categories, credential access, deployment, public API changes, migrations, data deletion, or protected-area edits.
- A roadmap item can mark work as desired, but it cannot make that work safe for unattended execution.
- If creator intent conflicts with safety policy, safety policy wins and Pathfinder stops.
- If creator intent conflicts with current repo evidence, Pathfinder asks or records a blocker.

## Persistence And Schema

The charter should keep the existing `pathfinder:charter v1` marker unless implementation chooses a compatible version bump. It should expand the body from three broad dimensions into the stable intent model above.

The roadmap should use a new marker, for example `pathfinder:roadmap v1`. It should be plain Markdown with simple metadata, mirroring the charter's parser-light style. Each roadmap item should have an id, status, priority, rationale, evidence, and safety classification.

Both files should use the same local-only ignore ladder as the current charter:

1. Check whether the concrete file path is ignored.
2. If not, add `.pathfinder/` to `.git/info/exclude`.
3. Verify with `git check-ignore`.
4. If the file would be trackable, do not persist it.

## Implementation Surface

The implementation should update these files:

- `skills/pathfinder/SKILL.md`: canonical Deep Intent Gate, first-run behavior, roadmap file, expanded charter, continuous autonomous loop.
- `skills/pathfinder/references/question-funnel-template.md`: first-run deep intent screens and adaptive question rules.
- `skills/pathfinder/references/charter-template.md`: expanded stable-intent schema.
- `skills/pathfinder/references/roadmap-template.md`: new evolving-roadmap schema.
- `skills/pathfinder/references/artifact-structure.md`: local-only charter and roadmap outside the 00-08 run set.
- `skills/pathfinder/references/goal-best-practices.md`: goal framing from charter plus roadmap direction.
- `scripts/check-skill-consistency.sh`: required reference and drift guards for Deep Intent Gate and roadmap invariants.
- `README.md`: first-run deep intent behavior and continuous autonomous behavior.
- Version and manifest files if the change ships as a release.

## Drift Guards

The guard script should pin the load-bearing behavior with clause-unique tokens. At minimum, it should guard:

- `Deep Intent Gate`
- `.pathfinder/roadmap.md`
- `pathfinder:roadmap v1`
- `future capabilities not started yet`
- `continuous execution`
- `explicit invocation every run`
- `sanitized on every read`
- `never widens authorization`

It should also require `references/roadmap-template.md` once `SKILL.md` cites it. Shared screen tokens should appear in both `SKILL.md` and `question-funnel-template.md`. Goal-framing tokens should appear in both `SKILL.md` and `goal-best-practices.md`.

## Verification Plan

The implementation plan should verify:

1. `bash scripts/check-skill-consistency.sh .`
2. `bash scripts/check-manifests.sh .`
3. A first-run dogfood path with no `.pathfinder/` files.
4. A reuse path with both files present.
5. A refresh path through `/pathfinder charter`.
6. An autonomous dry run or constrained dogfood run that derives more than one goal from the roadmap.
7. Negative guard checks that prove removing the roadmap template citation or core Deep Intent tokens fails CI.

## Acceptance Criteria

The change is done when:

- First Pathfinder use asks deep intent questions by default for all entry points.
- The first-run flow captures both current evidence and not-yet-started creator intent.
- `.pathfinder/charter.md` stores stable project intent.
- `.pathfinder/roadmap.md` stores evolving desired work.
- Autonomous mode can continuously derive next goals from both files, but only after explicit invocation.
- Safety boundaries remain stronger than charter or roadmap content.
- The drift guards fail if the Deep Intent Gate, roadmap schema, or explicit-autonomy rule is removed from one mirror.
