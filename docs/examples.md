# Worked Pathfinder outcomes

## GitHub repository

`/pathfinder auto` may use the local bridge only when the active host provides real runtime attestation, stable native Goal activation and completion identities, and typed receipts. It stops at a committed local awaiting-review branch. GitHub publication and merge are disabled; otherwise it saves the Goal/manual handoff.

If the user explicitly approves `run all` for an already reviewed numbered pack, Pathfinder may use `mission pack-start` with the ordered schema-valid Goal Bindings and a hash-bound pack authorization. Each item runs as an independent one-Goal mission from the same base. The controller requires native Goal completion before creating the next child mission, and any block leaves the remaining queue untouched and unstarted.

## Git repository without a remote

Goal creation works normally. An attested host-driven mission can stop at a verified local awaiting-review branch; unsupported hosts stop at the saved Goal.

## Git with a non-GitHub remote

Pathfinder detects Git and the remote type. The local bridge does not improvise a forge API: it stops at the local branch regardless of remote type.

## Non-Git folder

Prompt-to-goal and source-first exploration work. Pathfinder can hand off a native/manual Goal. A
full controller install on POSIX saves canonical artifacts only under an explicit
current-user-owned `0700` host work root outside the source folder, using `pathfinder/<run>` beneath
that root. Other platforms fail closed pending equivalent ownership proof. It records a `non-git`
scope with no invented commit. Autonomous branch/commit/PR execution is unavailable.

## Dirty Git repository

Goal saving blocks by default. If the user explicitly chooses committed-base mode, Pathfinder uses
the controller-derived scope for the current `HEAD`, passes the separate
`--acknowledge-committed-base` save gate, preserves all modified and untracked files, and prints
that those files are excluded from execution. This choice does not authorize autonomy;
the host still has to prove every runtime and receipt boundary.

## Monorepo

The Goal Binding records the repository kind and opaque identity, requested scoped root, exact base commit, dirty policy, and controller-derived scope fingerprint. Root intent remains in `.pathfinder/`; selecting `apps/api` reads and writes only `.pathfinder/scopes/apps/api/intent/`, while `apps/web` gets a separate namespace. A missing scoped model stays unresolved instead of borrowing the repository or sibling product model. Discovery/cache and changed-surface checks stay inside the selected scope unless the Goal explicitly names a cross-package dependency.

## Protected path

Auth, payments, permissions, CI/CD, schema/migration, public API, and network work needs doctrine alignment, narrow item proof, enforceable isolation, and a diff that remains inside the proven surfaces. Clean work may be implemented but still ends at human review; missing proof blocks before implementation or publication.

## Runtime enforcement unavailable

`doctor` reports the local mission protocol as callable but host enforcement as unknown, so unattended eligibility remains false by default. Without separate trustworthy attestation, Pathfinder saves the bounded Goal and names the missing capability; it does not imitate autonomy in the current checkout.
