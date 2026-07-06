# Pathfinder Capability Model

The capability model decouples Pathfinder from hardcoded provider assumptions. A runtime, model, or
local tool is described by a capability profile, then strategies choose the safest route supported by
that profile.

## Capability profile fields

- `provider_name`: human-readable provider or local tool name.
- `native_goal_support`: whether the runtime supports `/goal`, Codex Goals, or no native loop.
- `max_goal_chars`: maximum safe condition length when a native goal command exists.
- `context_window`: available context size when knowable.
- `tool_execution`: whether the runtime can run shell/file/tool actions.
- `subagents`: whether independent worker/reviewer agents are available.
- `browser`: whether browser automation is available.
- `structured_output`: whether JSON sidecars can be requested or validated directly.
- `review_launcher`: local command or manual-handoff route for Cross-Model Review.
- `cost_latency_hint`: cheap/normal/expensive/unknown, used only for strategy choice.

## Defaults

- Claude Code with `/goal` uses `native_goal_support: claude-goal` and `max_goal_chars: 3900`.
- Codex uses `native_goal_support: codex-goal` when available; otherwise it receives the
  Implementation Goal fallback.
- Unknown runtimes use conservative defaults: no native goal assumption, no hidden credentials, no
  publication authority, and manual-handoff review.

## Adapter rules

- A generated goal records the capability profile used to choose `/goal` versus fallback text.
- Cross-Model Review selects a reviewer from compatible capability profiles; if no safe launcher
  exists, it writes a manual-handoff packet.
- Structured sidecars are preferred when `structured_output` is available. If not, Pathfinder still
  writes deterministic sidecars from its own artifacts before reporting completion.
