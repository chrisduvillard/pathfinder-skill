# Recorded controller replays

These deterministic replays are sanitized records of Pathfinder's synthetic route and controller scenarios. `replay.json` is validated against `schemas/replays/replay.schema.json`; scenario-specific schema conditions prove the expected safety outcome. They contain no live credentials, private paths, model transcripts, or network calls.

Run them with:

```bash
bash scripts/check-replay-evals.sh .
```
