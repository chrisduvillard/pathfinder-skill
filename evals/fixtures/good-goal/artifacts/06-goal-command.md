# Goal Command

Goal: Fix the dashboard empty state so an empty API result renders a useful empty message instead of a blank panel.

Proof: `npm test -- dashboard-empty-state` exits 0 and the agent reports the changed files.

Constraints: no schema change, no new dependency, no public API change, dashboard data-loading files only.

Stop: stop after 8 turns and report the blocker plus next input needed if the proof cannot run or still fails.
