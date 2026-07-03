# Pathfinder Artifact-First Evals - Design Spec

> Status: approved through brainstorming. Target release: assigned by the implementation plan.

## Context

Pathfinder already has strong static guards. `scripts/check-skill-consistency.sh` checks
cross-file drift, `scripts/check-skill-behavior.sh` checks known safety-direction and
screen-escape invariants, and `scripts/test-validators.sh` proves those parsers catch seeded
defects. These checks protect the specification from known drift classes.

They do not answer the next question: given a known scenario, did Pathfinder leave behind the
right map and goal? A contributor can preserve every guarded token while still weakening the
run trail, laundering a rejected candidate back into the funnel, or producing a goal without a
real proof surface.

This feature adds the first scenario-level eval layer. It starts with deterministic artifact
evals, not live agent transcript evals, so the suite can run cheaply in local preflight and CI.

## Locked Decisions

| Decision | Choice |
|---|---|
| First eval type | Artifact-first evals. |
| Initial execution model | Seeded artifact evals; no live Pathfinder agent sessions in v1. |
| Judge type | Deterministic assertions; no model-as-judge in v1. |
| Fixture style | Tiny synthetic cases under `evals/`, with human-readable case definitions. |
| CI posture | Add a local `scripts/check-evals.sh`; wire into `scripts/check-all.sh`. GitHub Actions wiring may follow after runtime and portability are proven. |
| Harness tests | Include golden and seeded failing fixtures so the eval harness proves its own claims. |
| Future direction | Add a small transcript eval layer later for the highest-value conversational behaviors. |

## Goals

1. Catch scenario-level failures that static token and structure guards cannot catch.
2. Verify that key Pathfinder artifacts preserve the intended behavioral contract.
3. Keep the first suite deterministic, cheap, and easy to run locally.
4. Make eval cases easy for contributors to add without learning a heavy framework.
5. Create a path toward live transcript evals without depending on them in v1.

## Non-Goals

This design does not run real Pathfinder agent sessions in CI. It does not grade open-ended
conversation quality, use a model as judge, or claim full behavioral coverage.

It also does not replace the existing drift guards. The eval suite complements them: drift
guards protect load-bearing prose and mirrors; artifact evals protect the behavior implied by
complete run artifacts.

## Feature Shape

Add an `evals/` tree and a CI-friendly wrapper:

```text
evals/
├─ cases/
│  ├─ good-goal.md
│  ├─ missing-proof.md
│  ├─ rejected-candidate-laundering.md
│  ├─ protected-surface.md
│  └─ track-b-placeholder.md
├─ fixtures/
│  └─ <case-name>/
│     ├─ repo/
│     └─ artifacts/
└─ harness/
   └─ <parser-and-assertion helpers>

scripts/check-evals.sh
```

Each case describes:

- the case id and purpose;
- the fixture path;
- the artifacts to inspect;
- the assertions to run;
- the expected result, either `pass` or `fail`;
- the failure message pattern for negative cases.

An expected `fail` case is a harness self-test. The suite treats it as passing only when the
target assertion fails and the failure message matches the case definition. If the bad fixture
passes cleanly, or fails for the wrong reason, the suite fails.

The v1 harness may use Bash plus small POSIX helpers, matching the current validator style. If
Bash becomes too awkward, the implementation plan may choose a small Python script, but it
should not add a production dependency.

## Data Flow

The first version uses seeded artifact evals:

```text
case definition + fixture artifacts
  -> temporary eval workspace
  -> artifact parser/assertions
  -> pass/fail report
```

The fixture repo exists to make each case concrete and future-proof. In v1, however, the harness
does not need to invoke a live agent to generate artifacts from that repo. It can copy seeded
artifacts into a temporary workspace and assert their contracts.

This gives the project useful eval infrastructure before it solves live replay.

## Artifact Contracts

The first assertion set should focus on Pathfinder's strongest promises:

- Required artifact exists.
- Artifact lifecycle or status field is valid where the artifact defines one.
- `06-goal-command.md` contains one measurable end state.
- The goal contains a proof surface, such as a test, check, command, benchmark, or explicit
  artifact inspection.
- The goal states relevant constraints, such as no schema change, no new dependency, no public
  API change, or scoped files.
- The goal contains a bounded stop condition.
- A candidate rejected in `03b-verification.md` does not appear as a selectable normal goal in
  `04-question-funnel.md`.
- A verification downgrade in `03b-verification.md` is reflected in the funnel instead of using
  stale Phase 4 confidence.
- Protected work, such as auth, payment, schema, migration, CI/CD, public API, or network-related
  work, carries the required manual, proof, or safety boundary.
- Track B prompt-to-goal writes Phase 4b as not applicable, rather than silently omitting it.

The harness should report one precise violation per failed assertion when possible.

## Initial Cases

### Good Goal

A seeded `06-goal-command.md` contains a measurable end state, proof command, constraints, and
stop condition. The case should pass.

### Missing Proof

A seeded goal omits the proof surface. The case should fail with a message naming
`06-goal-command.md` and the missing proof contract.

### Rejected Candidate Laundering

`03b-verification.md` rejects a candidate. `04-question-funnel.md` presents the same candidate as
a selectable normal goal. The case should fail and name the rejected candidate id.

### Protected Surface

A goal or funnel item touches a protected surface, such as auth or schema, without the required
manual-review, proof, or safety boundary. The case should fail and name the protected surface.

### Track B Placeholder

A prompt-to-goal run includes a Phase 4b artifact that says the phase is not applicable for Track
B. The case should pass. A missing or silent Phase 4b artifact should fail.

## Failure Reporting

Failures should be short and actionable:

```text
::error::case protected-surface: 06-goal-command.md missing manual-review boundary for auth surface
```

Each failure should include:

- the case id;
- the artifact path;
- the violated contract;
- the relevant candidate id, surface, or field when available.

The wrapper should continue through all cases and exit non-zero if any case fails, like the
existing `check-all.sh` wrapper.

## Harness Self-Tests

The eval harness must prove itself before it counts as coverage.

Add self-tests that mirror `scripts/test-validators.sh`:

- a golden passing case proves the harness can pass a valid artifact set;
- a missing-proof fixture proves the goal proof assertion fails;
- a laundering fixture proves rejected candidates cannot re-enter the funnel;
- a protected-surface fixture proves the safety-boundary assertion fails;
- a Track B negative fixture proves a missing or silent Phase 4b placeholder fails.

Run these self-tests through `scripts/check-evals.sh` in v1. A separate `scripts/test-evals.sh`
can be added later only if the eval runner becomes too large to read.

## Integration Points

The implementation should update these surfaces:

- `evals/cases/`: add human-readable case definitions.
- `evals/fixtures/`: add tiny fixture repos and seeded artifacts.
- `evals/harness/`: add parser and assertion helpers.
- `scripts/check-evals.sh`: run all eval cases and print precise failures.
- `scripts/check-all.sh`: call `check-evals.sh` after the current validator suite.
- `CONTRIBUTING.md`: explain how to run and add eval cases.
- `.github/workflows/manifests.yml`: optional in v1; add only after local runtime and portability are proven.

The implementation should avoid changing `skills/pathfinder/SKILL.md` unless the eval cases expose
a real current spec defect.

## Safety And Trust

Fixture repository content remains untrusted data. The v1 eval harness reads files as data only.
It must not execute fixture repo code, install dependencies, run package managers, invoke Docker,
or use credentials.

The harness should use temporary workspaces and clean them up. It must not write inside fixture
directories except through deliberate fixture updates by contributors.

## Transcript Evals Later

Transcript evals should come after artifact evals are stable.

The later layer should cover the few behaviors artifacts cannot fully judge:

- whether Pathfinder asks the right clarifying question;
- whether it explains safety boundaries clearly;
- whether it routes a user away from unsafe autonomy;
- whether it keeps options recognition-first and not overwhelming;
- whether it preserves the user's stated intent across turns.

Those transcript evals may use model grading or recorded conversations, but they should remain a
small, separate suite. They should not make the deterministic artifact suite flaky.

## Validation Plan

The implementation plan should verify:

1. `bash scripts/check-evals.sh .`
2. `bash scripts/check-all.sh .`
3. A golden case passes.
4. Each seeded negative case is treated as a passing harness self-test only when it fails for the
   intended reason.
5. The eval wrapper reports all failing cases before exiting non-zero.
6. The harness does not execute fixture repo code.
7. The suite runs on Linux and Windows Git-Bash/MSYS with the same assumptions as the existing
   validators.

## Acceptance Criteria

The change is done when:

- `scripts/check-evals.sh` runs the artifact eval suite locally.
- At least the five approved initial cases exist.
- The harness checks goal proof, boundedness, protected-surface routing, rejected-candidate
  laundering, verification downgrade reflection, and Track B Phase 4b placeholder behavior.
- The harness has seeded positive and negative coverage for its own assertions.
- `scripts/check-all.sh` runs the eval suite.
- Contributors can understand how to add a case from `CONTRIBUTING.md`.
- The suite uses no live agent sessions, no model-as-judge, no fixture code execution, and no new
  production dependency in v1.
