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


def render_run_log(projection: dict) -> str:
    state = projection["state"]
    binding = projection["binding"]
    boundary = projection["runtime_boundary"]
    run_log = projection["run_log"]
    if len({state["mission_id"], binding["mission_id"], run_log["mission_id"]}) != 1:
        raise StateError("run-log projection mission identity drift")
    if state["binding_id"] != binding["binding_id"] or run_log["binding_id"] != binding["binding_id"]:
        raise StateError("run-log projection binding identity drift")
    if run_log["runtime_boundary_id"] != boundary["boundary_id"]:
        raise StateError("run-log projection Runtime Boundary identity drift")
    lines = [
        "# Run log",
        "",
        "## Mission",
        "",
        f"- mission_id: {_inline(state['mission_id'])}",
        f"- goal_id: {_inline(state['goal_id'])}",
        f"- attempt_id: {_inline(state['attempt_id'])}",
        f"- state: {_inline(state['state'])}",
        f"- revision: {_inline(state['revision'])}",
        f"- base_commit: {_inline(state['base_commit'])}",
        f"- worktree_id: {_inline(state['worktree_id'])}",
        f"- worktree_path: {_inline(state['worktree_path'])}",
        f"- branch_id: {_inline(state['branch_id'])}",
        f"- branch_name: {_inline(state['branch_name'])}",
        f"- commit_ids: {_joined(state['commit_ids'])}",
        "",
        "## Goal Binding",
        "",
        f"- binding_id: {_inline(binding['binding_id'])}",
        f"- objective_source: {_inline(binding['objective_source'])}",
        f"- objective: {_inline(binding['objective'])}",
        f"- binding_status: {_inline(run_log['binding_status'])}",
        f"- protected_surfaces: {_joined(binding['protected_surfaces'])}",
        "- proof_requirements:",
    ]
    lines.extend(f"  - {_inline(item)}" for item in binding["proof_requirements"])
    lines.extend([
        "",
        "## Runtime Boundary",
        "",
        f"- boundary_id: {_inline(boundary['boundary_id'])}",
        f"- primary_runtime: {_inline(boundary['primary_runtime'])}",
        f"- filesystem: {_inline(boundary['filesystem'])}",
        f"- process: {_inline(boundary['process'])}",
        f"- network: {_inline(boundary['network'])}",
        f"- credentials: {_inline(boundary['credentials'])}",
        f"- repo_code_execution: {_inline(boundary['repo_code_execution'])}",
        f"- tool_allowlist_enforced: {_inline(boundary['tool_allowlist_enforced'])}",
        f"- pre_execution_consent: {_inline(boundary['pre_execution_consent'])}",
        f"- execution_eligible: {_inline(boundary['execution_eligible'])}",
        f"- blocking_reasons: {_joined(boundary['blocking_reasons'])}",
        "",
        "## Host action ledger",
        "",
    ])
    operations = projection["operations"]
    if not operations:
        lines.append("- No host actions have been journaled.")
    for operation in operations:
        lines.extend([
            f"### {_inline(operation['stage'])}: {_inline(operation['action_kind'])}",
            "",
            f"- operation_id: {_inline(operation['operation_id'])}",
            f"- status: {_inline(operation['status'])}",
            f"- started_at: {_inline(operation['started_at'])}",
            f"- completed_at: {_inline(operation['completed_at'])}",
            f"- summary_code: {_inline(operation['summary_code'])}",
            f"- redacted_summary: {_inline(operation['redacted_summary'])}",
            f"- exit_status: {_inline(operation['exit_status'])}",
            f"- changed_files: {_joined(operation['changed_files'])}",
            f"- artifact_sha256: {_inline(operation['artifact_sha256'])}",
            "",
        ])
    lines.extend([
        "## Command evidence",
        "",
        "- commands: none",
        "- The host action protocol does not persist argv, environment, or raw output; "
        "no command evidence is inferred from action receipts.",
        "",
        "## Outcome",
        "",
        f"- verification: {_inline(run_log['verification'])}",
        f"- publication: {_inline(run_log['publication'])}",
        f"- requires_reconciliation: {_inline(projection['requires_reconciliation'])}",
        f"- updated_at: {_inline(run_log['updated_at'])}",
    ])
    return "\n".join(lines) + "\n"


def render_mission_final_summary(projection: dict) -> str:
    summary = projection["final_summary"]
    if summary is None:
        raise StateError("active mission has no final summary")
    state = projection["state"]
    binding = projection["binding"]
    run_log = projection["run_log"]
    goal = summary["goals"][0]
    if summary["mission_id"] != state["mission_id"] or binding["mission_id"] != state["mission_id"]:
        raise StateError("mission final summary identity drift")
    if goal["goal_id"] != state["goal_id"] or binding["goal_id"] != state["goal_id"]:
        raise StateError("mission final summary Goal identity drift")
    if summary["final_state"] != state["state"] or goal["disposition"] != state["state"]:
        raise StateError("mission final summary disposition drift")
    if goal["binding_status"] != run_log["binding_status"]:
        raise StateError("mission final summary Binding Status drift")
    if goal["verification"] != run_log["verification"]:
        raise StateError("mission final summary verification drift")
    if goal["commit_ids"] != state["commit_ids"]:
        raise StateError("mission final summary commit identity drift")
    lines = [
        "# Final summary",
        "",
        "- Route: autonomous host mission",
        f"- mission_id: {_inline(state['mission_id'])}",
        f"- goal_id: {_inline(state['goal_id'])}",
        f"- binding_id: {_inline(state['binding_id'])}",
        f"- attempt_id: {_inline(state['attempt_id'])}",
        f"- final_state: {_inline(summary['final_state'])}",
        f"- binding_status: {_inline(goal['binding_status'])}",
        f"- verification: {_inline(goal['verification'])}",
        f"- publication: {_inline(run_log['publication'])}",
        f"- worktree_id: {_inline(state['worktree_id'])}",
        f"- worktree_path: {_inline(state['worktree_path'])}",
        f"- branch_id: {_inline(state['branch_id'])}",
        f"- branch_name: {_inline(state['branch_name'])}",
        f"- commit_ids: {_joined(goal['commit_ids'])}",
        f"- pr_url: {_inline(goal['pr_url'])}",
        f"- Next input needed: {_inline(summary['next_input_needed'])}",
    ]
    if summary["residual_risks"]:
        lines.append("- Residual risks:")
        lines.extend(f"  - {_inline(risk)}" for risk in summary["residual_risks"])
    else:
        lines.append("- Residual risks: none")
    lines.append("- Replay artifacts:")
    lines.extend(f"  - {_inline(path)}" for path in summary["replay_artifacts"])
    lines.append(f"- completed_at: {_inline(summary['completed_at'])}")
    return "\n".join(lines) + "\n"
