from __future__ import annotations

from .errors import StateError


def _inline(value) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")


def _joined(values: list) -> str:
    return ", ".join(_inline(value) for value in values) if values else "none"


def render_goal_command(binding: dict) -> str:
    objective = binding["objective"]
    if "\n" in objective or "\r" in objective:
        raise StateError("Goal objective must be a single line")
    lines = [
        "# Goal",
        "",
        f"/goal {objective}",
        "",
        "# Implementation Goal",
        "",
        objective,
        "",
        "# Goal Binding",
        "",
        f"- binding_id: {_inline(binding['binding_id'])}",
        f"- mission_id: {_inline(binding['mission_id'])}",
        f"- goal_id: {_inline(binding['goal_id'])}",
        f"- objective_source: {_inline(binding['objective_source'])}",
        f"- selected_candidate_ids: {_joined(binding['selected_candidate_ids'])}",
        "- intent_snapshot:",
    ]
    for kind in ("charter", "roadmap", "doctrine"):
        snapshot = binding["intent_snapshot"][kind]
        rendered = (
            "none" if snapshot is None
            else f"version {snapshot['version']}, sha256 {_inline(snapshot['sha256'])}"
        )
        lines.append(f"  - {kind}: {rendered}")
    lines.append("- capability_profile:")
    for name in sorted(binding["capabilities"]):
        lines.append(f"  - {_inline(name)}: {_inline(binding['capabilities'][name])}")
    lines.append("- scope:")
    for name in (
        "repository_id", "scoped_root", "base_commit", "dirty_policy", "fingerprint"
    ):
        lines.append(f"  - {name}: {_inline(binding['scope'][name])}")
    lines.append("- proof_requirements:")
    lines.extend(f"  - {_inline(value)}" for value in binding["proof_requirements"])
    lines.extend([
        f"- protected_surfaces: {_joined(binding['protected_surfaces'])}",
        f"- runtime_boundary_required: {_inline(binding['runtime_boundary_required'])}",
        "- budgets:",
    ])
    for name in (
        "max_goals", "max_attempts_per_goal", "max_wall_seconds",
        "max_open_prs", "max_total_prs",
    ):
        lines.append(f"  - {name}: {_inline(binding['budgets'][name])}")
    lines.append(f"- created_at: {_inline(binding['created_at'])}")
    return "\n".join(lines) + "\n"


def render_final_summary(binding: dict, summary: dict) -> str:
    if summary.get("mission_id") != binding.get("mission_id"):
        raise StateError("final summary mission_id does not match Goal Binding")
    goals = summary.get("goals")
    if not isinstance(goals, list) or len(goals) != 1:
        raise StateError("final summary must contain exactly one Goal")
    goal = goals[0]
    if goal.get("goal_id") != binding.get("goal_id"):
        raise StateError("final summary goal_id does not match Goal Binding")
    if summary.get("final_state") != goal.get("disposition"):
        raise StateError("final summary state does not match Goal disposition")
    route = (
        "prompt-to-goal fast path"
        if binding["objective_source"] == "user-prompt"
        else binding["objective_source"]
    )
    lines = [
        "# Final summary",
        "",
        f"- Route: {_inline(route)}",
        f"- mission_id: {_inline(binding['mission_id'])}",
        f"- goal_id: {_inline(binding['goal_id'])}",
        f"- binding_id: {_inline(binding['binding_id'])}",
        f"- final_state: {_inline(summary['final_state'])}",
        f"- disposition: {_inline(goal['disposition'])}",
        f"- attempt_id: {_inline(goal['attempt_id'])}",
        f"- binding_status: {_inline(goal['binding_status'])}",
        f"- verification: {_inline(goal['verification'])}",
        f"- commit_ids: {_joined(goal['commit_ids'])}",
        f"- pr_url: {_inline(goal['pr_url'])}",
    ]
    if summary["final_state"] == "goal-saved":
        lines.append(
            "- Goal was not run; verification, commits, publication, and native "
            "activation are not-run."
        )
    lines.append(f"- Next input needed: {_inline(summary['next_input_needed'])}")
    risks = summary["residual_risks"]
    if risks:
        lines.append("- Residual risks:")
        lines.extend(f"  - {_inline(risk)}" for risk in risks)
    else:
        lines.append("- Residual risks: none")
    replay = summary["replay_artifacts"]
    if replay:
        lines.append("- Replay artifacts:")
        lines.extend(f"  - {_inline(path)}" for path in replay)
    else:
        lines.append("- Replay artifacts: none")
    lines.append(f"- completed_at: {_inline(summary['completed_at'])}")
    return "\n".join(lines) + "\n"
