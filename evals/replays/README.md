# Recorded controller replays

These deterministic replays are sanitized records of Pathfinder's synthetic route and controller scenarios. `replay.json` is validated against `schemas/replays/replay.schema.json`; scenario-specific schema conditions prove the expected safety outcome. They contain no live credentials, private paths, model transcripts, or network calls.

The prompt fast-path replay also fixes the exact six-file artifact set for a clear, unexecuted Goal and requires those repository-local artifacts to be ignored. Negative replays reject skipped-phase placeholder churn, a denied ignore update that falls through to an untracked folder, and pre-approval repository execution. The last case is a sanitized behavioral record from local Claude Code plugin dogfood: the host ran two proof probes and created Python cache files while it was supposed to generate artifacts only.

Run them with:

```bash
bash scripts/check-replay-evals.sh .
```
