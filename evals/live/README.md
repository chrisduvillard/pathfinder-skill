# Optional live-model smoke suite

The required suite is deterministic and offline. This advisory suite checks five conversational promises against a tiny synthetic repository: focused questions, intent preservation, route selection, native Goal activation, and honest blocking.

Set `PATHFINDER_LIVE_AGENT_BIN` to an absolute executable implementing this protocol:

```text
agent-bin <case-file> <synthetic-workspace> <transcript-output>
```

The executable must write a UTF-8 transcript to the requested output path and exit non-zero on transport/model failure. It must not publish, push, access arbitrary repositories, or write outside the synthetic workspace and transcript path. Each case has a 120-second limit. Then run:

```bash
PATHFINDER_LIVE_EVALS=1 PATHFINDER_LIVE_AGENT_BIN=/absolute/path/to/adapter bash scripts/check-live-evals.sh .
```
