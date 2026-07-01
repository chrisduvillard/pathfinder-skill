# Pathfinder Behavioral Invariant Harness (TR-1) - Design Spec

> Status: approved through brainstorming. Target release: assigned by the implementation plan.

## Context

Every CI check today is static structure or token verification. `check-manifests.sh`,
`check-skill-consistency.sh`, `check-portability.sh`, and `git diff --check` each read files
and assert strings, JSON, or fence structure. None of them tests what the skill *does*.

The regression class that has actually reached `main` — twice, caught only by manual
dogfooding (VERSION.md v2.21.1 and v2.21.2) — is a **safety gate that keeps its token but has
its rule loosened, inverted, or contradicted.** `check-skill-consistency.sh` already asserts a
list of safety phrases are *present within* the `## Autonomous mode` section (the `auto_invariants`
loop, via `check_skill_section`). That catches *deletion* of a phrase. It does **not** catch
*polarity inversion*: `self-merge` appearing in the section still passes even if its surrounding
sentence now permits what it used to forbid. The token survives; the direction flips.

This design adds a deterministic, agent-free harness that asserts **direction, not presence** — the
layer above every existing check. It is scoped to the two regression classes with the highest proven
or structural risk: autonomous-mode safety-direction, and decision-screen escape completeness.

## Locked Decisions

| Decision | Choice |
|---|---|
| Core strategy | Static invariant harness. No live agent runs. Deterministic and PR-gating. |
| Why not live agent | Nondeterministic, token-costly, flaky in CI, and strains the trust model (the harness would execute an untrusted-data-laden spec). Cannot be the required gate. |
| Initial scope | Two families: autonomous safety-direction invariants, and decision-screen escape invariants. |
| Assertion style | Section/block-anchored relational checks (co-occurrence, proximity, negative-space). Reuse the existing `check_skill_section` window and fence tracker. No new heavy parser. |
| Proof discipline | Every invariant is proven by an adversarial fixture in the existing `test-validators.sh` meta-suite before it counts as coverage. |
| Trust posture | Reads SKILL.md and its mirror as data only; never executes them. Same posture as the existing validators. |

## Goals

1. Catch the polarity-inversion-with-token-intact class in CI, deterministically, with no live agent run.
2. Assert safety **direction** in the autonomous section: a controlled action must sit next to its governing qualifier, not merely somewhere in the file.
3. Assert decision-screen **escape completeness**: every decision menu carries its `None of these` escape unless it is an allowlisted fixed menu.
4. Prove each invariant against the exact regression it claims to catch, so the harness is a test and not a feeling of coverage.
5. State the harness's bound honestly — what it does not catch — so it never implies full behavioral coverage.

## Non-Goals

This design does not run the skill against a live model, and makes no claim of full behavioral
coverage. It does not add a general scenario/transcript oracle, and it does not encode `/goal`
proof-obligation or phase-coherence invariants in this pass (the architecture extends to them; they
are deferred until a third regression class shows they are needed). It does not edit production spec
prose unless a fixture exposes a real current defect, which would be a finding, not part of the
planned change.

## Feature Shape

One new validator, `scripts/check-skill-behavior.sh`, parallel to the other `check-*.sh` scripts. It
reads only the repo's own `skills/pathfinder/SKILL.md` and `references/question-funnel-template.md`
as data. It runs two invariant families, both section- or block-anchored, reusing the
`check_skill_section` window mechanism and the fence open/close tracker that already live in
`check-skill-consistency.sh` — no new heavy parser is introduced.

### Family A - Safety-direction invariants

Scoped to the `## Autonomous mode` .. `## Phase 7:` window (the same boundaries the existing
`auto_invariants` loop uses, guarded for existence by the section-boundary heading check already in
`check-skill-consistency.sh`). A small table of `(controlled action, required-qualifier set,
proximity)`. For each line in the window containing a controlled action, assert a governing qualifier
occurs on that line or within +/-1 line. A qualifier-less occurrence of any controlled action in the
window exits non-zero.

Grounded in the current SKILL.md text (line numbers are anchors, not assertions — the check keys on
tokens, not line numbers):

| Controlled action | Must co-occur with one of | Anchor lines |
|---|---|---|
| `self-merge` | `never` / `default-deny` / `conditional` / `do not` / `only after` ... `clean` or `fixed-clean` / `awaiting-review` | 1282, 1301-1302, 1360, 1470 |
| `unattended` | `never` / `not` / `cannot` | 613, 1305, 1329 |
| `dangerous categories` | `never` / `excluded` / `filtered out` / `hard-block` | 1287 |
| `credential`(s) near exec steps | `separation` / `separate` / `isolat` / `disabled` | 1341, 1362-1363 |

This is the anchoring `check_pair` lacked: the qualifier must be near its action, not merely somewhere
in the file. Matching is case-insensitive via the portable `awk index(tolower())` idiom already used
in `check-skill-consistency.sh` (never `grep -qiF`, which aborts on MSYS GNU grep 3.0).

### Family B - Screen-escape invariants

Every fenced screen block that contains an `Agent recommends:` line (a decision menu) must also
contain its `None of these` escape, unless the block is on a small fixed-menu allowlist. The block is
scoped by its enclosing fence, reusing the fence tracker's open/close logic. The allowlist covers the
menus the spec deliberately exempts from the escape grammar: the Phase 5 mode-selection menu, the
Track-B "How should I help?" entry menu, and the bare `/pathfinder` entry chooser. A non-allowlisted
decision menu missing its escape exits non-zero.

This catches the class where a new or edited screen silently drops its escape — invisible to CI today.

### Proof - adversarial fixtures

Every invariant is proven by an adversarial fixture in `scripts/test-validators.sh`, extending its
existing `newroot()` / `assert_pass` / `assert_catch` machinery:

- **Golden:** an unmodified copy of the tree makes `check-skill-behavior.sh` exit 0.
- **Polarity fixture:** rewrite a `self-merge` line in the autonomous section to drop its qualifier
  while keeping the token; the harness exits non-zero. This is TR-1's literal acceptance test — a
  safety-token-preserving-but-logic-inverting change is caught.
- **Unattended fixture:** flip a "never run unattended" statement to permit it; non-zero.
- **Escape fixture:** delete `None of these` from one non-allowlisted screen; non-zero.

The golden-plus-seeded-defect pattern is identical to the whole-script meta-tests already in
`test-validators.sh`, so the proof layer reuses the established harness rather than adding a new one.

### Wiring

- `scripts/check-all.sh` - one `run_check "skill behavior invariants" bash "$root/scripts/check-skill-behavior.sh" "$root"` line.
- `.github/workflows/manifests.yml` - one step, alongside the existing validator and meta-test steps.
- `CONTRIBUTING.md` - one line telling maintainers that a new decision menu needs an escape or an
  allowlist entry, and a new autonomous safety action needs a qualifier-set row.

### Error handling and the false-positive tension

The real risk is a legitimate reword tripping CI. Mitigations: qualifier sets are generous
(synonyms, case-insensitive); proximity is +/-1 line, not same-line; the allowlist is explicit and
greppable. Every `::error::` names the file, the controlled action or screen, and the expected
qualifier or escape, so a maintainer fixes or allowlists in one step.

### Honest scope - what it does not catch

A determined, fluent reword that keeps a plausible qualifier while still inverting intent can evade
it. This harness catches the polarity-inversion-with-token-intact class that has actually shipped, not
arbitrary semantic drift. Because there is no live agent, it makes no claim of full behavioral
coverage. This bound is stated in the script header; stating it is itself the anti-TR-1 discipline —
the harness must not become the "feeling of coverage without coverage" that TR-1 warns about.

## Files Touched

- New: `scripts/check-skill-behavior.sh`.
- Modified: `scripts/test-validators.sh` (adversarial fixtures + golden), `scripts/check-all.sh`
  (wire in), `.github/workflows/manifests.yml` (CI step), `CONTRIBUTING.md` (maintainer note).
- No production spec (`SKILL.md` / references) edits unless a fixture exposes a real current defect,
  which would be reported as a finding.

`scripts/**` and `.github/**` are maintainer-review protected per CONTRIBUTING; this change ships as a
patch release through the normal branch -> PR -> review -> CI -> squash-merge -> auto-release flow,
like the surrounding v2.21.x hardening releases.
