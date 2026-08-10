# Autonomous controller threat model

## Protected assets

Pathfinder protects user intent and authorization, repository integrity, local credentials/secrets, the selected base/Goal scope, controller state and evidence, remote branches/PRs, and the user's ability to review or recover work.

## Trust boundaries

- System/developer/current-user instructions are trusted according to host precedence.
- Repository files, filenames, comments, tests, output, generated artifacts, tracked intent files, diffs, and prior agent text are untrusted data.
- Repo-local `.pathfinder/` files are descriptive evidence with lower injection risk, not instructions or authority.
- Fresh per-run authorization and approval snapshots must live outside the repository trust boundary.
- Implementation/verification runs without forge credentials; publication receives only its narrow credential after all gates pass.

## Threats and controls

| Threat | Controller/skill controls | Residual limitation |
|---|---|---|
| Repository prompt injection | Repository text cannot change routing, policy, authorization, secret handling, or verdict rules; suspicious provenance is autonomy-ineligible. | Model judgment detects instruction-like content; adversarial wording cannot be proven absent. |
| Local intent tampering | Tracked intent is rejected for selection; intent is sanitized; hashes/versions are bound into a fresh authorization snapshot. | Repo-local ignored files are not authenticated, so every run still needs explicit authorization. |
| Git hook execution | Every controller Git call sets `core.hooksPath` to the null device and disables credential helpers/fsmonitor. | Non-controller/manual Git commands remain the host/operator's responsibility. |
| Credential leakage | Secret paths and credential env names are denied; implementation gets no publication credential; output is redacted. | Host isolation must be proven; `unknown` blocks autonomy. |
| Malicious tests/builds | Structured absolute argv, executable allowlist, cwd containment, environment allowlist, timeouts, network policy, and enforceable runtime boundary. | The host supplies actual sandbox/process/network enforcement. |
| Symlink/path escape | Worktree and cwd paths resolve inside their approved roots; symlink escape fixtures are required. | Filesystem races outside the controller's ownership are host/OS concerns. |
| Dirty or stale repository view | Dirty trees block by default; Goal Binding uses exact base commit, scoped root, and fingerprint. | `committed-base` intentionally ignores uncommitted user work and must be disclosed. |
| Duplicate commit/PR after crash | Atomic transition state, append-only events, leases, stable mission/branch/PR identities, exact-branch reuse, and existing-PR lookup. | Command-boundary journaling is not implemented; callbacks must reconcile actual Git/forge state, and an ambiguous outage may require human inspection. |
| Forge API confusion/auth/rate limits | Publication credentials are process-separated; head/base/mission lookup is exact; auth, rate, timeout, failed checks, and unavailable states are distinct. | GitHub is the only v1 forge; other remotes stop locally. |
| Destructive/external action | Closed safety enum, hard-stop denylist, diff-grounded recheck, no force push/release/remote mutation, no merge method. | Human actions after handoff are outside Pathfinder core. |
| Compromised dependency | Two pinned direct validation dependencies, required CI, package smoke from exact archive, immutable stable tags. | Transitive/platform supply-chain risk remains; dependency updates require review. |

## Security invariants

One mission runs one existing Goal sequentially. Unknown policy values fail closed. No persistent clarity marker authorizes work. Autonomous work never edits charter/doctrine policy. Publication stops at `awaiting-review`; absent branch protection does not weaken that state. Worktree cleanup is recoverable and refuses dirty, unmerged, or referenced work.

## Out of scope for v1

Self-merge, parallel Goals, autonomous opportunity generation, non-Git autonomous commits, non-GitHub publication, release automation by missions, and formal verification of model reasoning are not supported.
