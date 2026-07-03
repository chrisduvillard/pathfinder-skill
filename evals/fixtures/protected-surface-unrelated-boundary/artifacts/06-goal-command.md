# Goal Command

Goal: Change login session handling for expired tokens.

protected-surface: auth

Proof: `npm test -- auth-session` exits 0.

Constraints: auth files only.

Stop: stop after 8 turns and report the blocker plus next input needed if the proof cannot run.
