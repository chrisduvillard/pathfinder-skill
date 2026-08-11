# Worked Pathfinder outcomes

## GitHub repository

`/pathfinder auto` may use the local bridge only when the active host provides real runtime attestation, stable native Goal identity, and typed receipts. It stops at a committed local awaiting-review branch. GitHub publication and merge are disabled; otherwise it saves the Goal/manual handoff.

## Git repository without a remote

Goal creation works normally. An attested host-driven mission can stop at a verified local awaiting-review branch; unsupported hosts stop at the saved Goal.

## Git with a non-GitHub remote

Pathfinder detects Git and the remote type. The local bridge does not improvise a forge API: it stops at the local branch regardless of remote type.

## Non-Git folder

Prompt-to-goal and source-first exploration work. Pathfinder saves a native/manual Goal and artifacts. Autonomous branch/commit/PR execution is unavailable.

## Monorepo

The Goal Binding records the Git root, requested scoped root, exact base commit, dirty policy, and content fingerprint. Root intent remains in `.pathfinder/`; selecting `apps/api` reads and writes only `.pathfinder/scopes/apps/api/intent/`, while `apps/web` gets a separate namespace. A missing scoped model stays unresolved instead of borrowing the repository or sibling product model. Discovery/cache and changed-surface checks stay inside the selected scope unless the Goal explicitly names a cross-package dependency.

## Protected path

Auth, payments, permissions, CI/CD, schema/migration, public API, and network work needs doctrine alignment, narrow item proof, enforceable isolation, and a diff that remains inside the proven surfaces. Clean work may be implemented but still ends at human review; missing proof blocks before implementation or publication.

## Runtime enforcement unavailable

`doctor` reports the local mission protocol as callable but host enforcement as unknown, so unattended eligibility remains false by default. Without separate trustworthy attestation, Pathfinder saves the bounded Goal and names the missing capability; it does not imitate autonomy in the current checkout.
