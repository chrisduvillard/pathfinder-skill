# Worked Pathfinder outcomes

## GitHub repository

`/pathfinder auto` currently saves one bounded Goal and reports that the production mission bridge is unavailable. The controller already contains an idempotent GitHub publisher with no merge operation, but no production entry point composes it into an autonomous run yet.

## Git repository without a remote

Goal creation works normally. The target bridge contract would stop a successful mission at a verified local branch when publication is unavailable; the current release stops at the saved Goal before implementation.

## Git with a non-GitHub remote

Pathfinder detects Git and the remote type. The future bridge must not improvise a forge API; the current release saves the Goal and reports the unavailable mission runner.

## Non-Git folder

Prompt-to-goal and source-first exploration work. Pathfinder saves a native/manual Goal and artifacts. Autonomous branch/commit/PR execution is unavailable.

## Monorepo

The Goal Binding records the Git root, requested scoped root, exact base commit, dirty policy, and content fingerprint. Discovery/cache and changed-surface checks stay inside that scope unless the Goal explicitly names a cross-package dependency.

## Protected path

Auth, payments, permissions, CI/CD, schema/migration, public API, and network work needs doctrine alignment, narrow item proof, enforceable isolation, and a diff that remains inside the proven surfaces. Clean work may be implemented but still ends at human review; missing proof blocks before implementation or publication.

## Runtime enforcement unavailable

`doctor` reports the mission runner as unavailable, so autonomous eligibility is false before host enforcement is considered. Pathfinder saves the bounded Goal and names the missing capability; it does not imitate autonomy in the current checkout.
