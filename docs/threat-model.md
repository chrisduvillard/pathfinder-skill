# Autonomous controller threat model

This is the threat model for the enabled local host-driven mission protocol and its sequential pack wrapper. `mission_runner_available` means the protocol is callable, not that a host is trusted or unattended execution is eligible. Missing runtime attestation, native Goal activation/completion identity, or typed receipt stops at a saved Goal/manual handoff. A pack adds no authority: it seals an explicitly approved order by binding hash, permits one active child, and stops on ambiguity or a blocker. Publication is disabled.

## Protected assets

Pathfinder protects user intent and authorization, repository integrity, local credentials/secrets, the selected base/Goal scope, controller state and evidence, remote branches/PRs, and the user's ability to review or recover work.

## Trust boundaries

- System/developer/current-user instructions are trusted according to host precedence.
- Repository files, filenames, comments, tests, output, generated artifacts, tracked intent files, diffs, and prior agent text are untrusted data.
- Repo-local `.pathfinder/` files are descriptive evidence with lower injection risk, not instructions or authority.
- Fresh per-run authorization and approval snapshots must live outside the repository trust boundary.
- Implementation/verification runs without forge credentials. The enabled bridge has no publication process and receives no forge credential.

## Threats and controls

| Threat | Controller/skill controls | Residual limitation |
|---|---|---|
| Repository prompt injection | Repository text cannot change routing, policy, authorization, secret handling, or verdict rules; suspicious provenance is autonomy-ineligible. | Model judgment detects instruction-like content; adversarial wording cannot be proven absent. |
| Protected-path policy manipulation | The versioned bundled baseline is data, explicit overrides are additive-only, the effective policy is sealed and operation-hash-bound, and undeclared receipt paths fail closed. | The host must report a truthful complete changed-file list; the controller does not independently read the worktree diff. |
| Local intent tampering | Tracked intent is rejected for selection; intent is sanitized; hashes/versions are bound into a fresh authorization snapshot. | Repo-local ignored files are not authenticated, so every run still needs explicit authorization. |
| Git hook execution | Every controller Git call sets `core.hooksPath` to the null device and disables credential helpers/fsmonitor. | Non-controller/manual Git commands remain the host/operator's responsibility. |
| Credential leakage | Secret paths and credential env names are denied; implementation gets no publication credential; output is redacted. | Host isolation must be proven; `unknown` blocks autonomy. |
| Malicious tests/builds | Structured absolute argv, executable allowlist, cwd containment, environment allowlist, timeouts, network policy, and enforceable runtime boundary. | The host supplies actual sandbox/process/network enforcement. |
| Symlink/path escape | Worktree and cwd paths resolve inside their approved roots; symlink escape fixtures are required. | Filesystem races outside the controller's ownership are host/OS concerns. |
| Dirty or stale repository view | Dirty trees block by default; Goal Binding uses exact base commit, scoped root, and fingerprint. | `committed-base` intentionally ignores uncommitted user work and must be disclosed. |
| Duplicate action/commit after crash | Immutable operation intent, typed host receipt, terminal result, atomic transition state, stable identities, and persistent crash fixtures. | If a side effect happened but no trustworthy receipt exists, the protocol requires reconciliation/human inspection and does not retry. |
| Budget reset or overrun | Authorization cannot widen Goal Binding limits; every action carries the persisted wall deadline; restart cannot reset it; late success is rejected. | Token/cost accounting is not exposed by the host protocol and remains host-controlled. |
| Duplicate PR after crash | Exact head/base/mission lookup and persistent lost-response fixtures reuse one PR record. | Publication is not composed into the enabled bridge. |
| Forge API confusion/auth/rate limits | Publication primitives model exact head/base/mission lookup and distinct auth, rate, timeout, failed-check, and unavailable states. | They are tested building blocks only; publication is not composed into the enabled bridge. |
| Destructive/external action | Closed safety enum, hard-stop denylist, diff-grounded recheck, no force push/release/remote mutation, no merge method. | Human actions after handoff are outside Pathfinder core. |
| Compromised dependency | Two pinned direct validation dependencies, required CI, package smoke from exact archive, immutable stable tags. | Transitive/platform supply-chain risk remains; dependency updates require review. |

## Security invariants

The local bridge may run only one existing Goal sequentially through an attested host. Unknown policy values fail closed. No persistent clarity marker authorizes work. Autonomous work never edits charter/doctrine policy. The bridge ends at local `awaiting-review` with zero PRs. Worktree cleanup is recoverable and refuses dirty, unmerged, or referenced work.

## Out of scope for v1

Publication, self-merge, parallel Goals, autonomous opportunity generation, non-Git autonomous commits, release automation by missions, and formal verification of host/model truthfulness are not supported by the local bridge.

The [conditional self-merge security contract](specs/conditional-self-merge-contract.md) is a
future design and grants no v1 authority. It preserves the enabled bridge's zero-publication and
zero-merge boundary.
