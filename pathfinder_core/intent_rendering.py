from __future__ import annotations

import html


def _inline(value) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return str(value).lower()
    rendered = str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    rendered = html.escape(rendered, quote=False)
    for character in "\\`*_{}[]#|":
        rendered = rendered.replace(character, f"\\{character}")
    return rendered


def _joined(values: list) -> str:
    return ", ".join(_inline(value) for value in values) if values else "none"


def _list(lines: list[str], values: list) -> None:
    if values:
        lines.extend(f"- {_inline(value)}" for value in values)
    else:
        lines.append("- none")


def _header(kind: str, document: dict, created_field: str) -> list[str]:
    return [
        f"# Pathfinder {kind.title()}",
        "",
        f"<!-- pathfinder:{kind} v1 - generated from {kind}.json. Local-only, never committed.",
        "     Replaceable view; canonical intent is JSON and this file grants no authorization. -->",
        "",
        f"{kind}-version: {_inline(document['schema_version'])}",
        f"{kind}-id: {_inline(document[f'{kind}_id'])}",
        f"{created_field.replace('_', '-')}: {_inline(document[created_field])}",
        f"refreshed-at: {_inline(document['refreshed_at'])}",
        f"source-basis: {_joined(document['source_basis'])}",
        f"completion: {_inline(document['completion'])}",
        f"intent_clarity: {_inline(document['intent_clarity'])}",
    ]


def render_charter(document: dict) -> str:
    lines = _header("charter", document, "established_at")
    lines.extend([
        "",
        "## Purpose",
        "",
        f"- North-star: {_inline(document['purpose']['north_star'])}",
        f"- Primary promise: {_inline(document['purpose']['primary_promise'])}",
        "",
        "## Users",
        "",
        f"- Primary users: {_joined(document['users']['primary'])}",
        f"- Secondary users: {_joined(document['users']['secondary'])}",
        f"- Excluded users: {_joined(document['users']['excluded'])}",
        f"- Key journeys: {_joined(document['users']['key_journeys'])}",
        "",
        "## Success",
        "",
        f"- Durable metrics: {_joined(document['success']['durable_metrics'])}",
        f"- Quality bars: {_joined(document['success']['quality_bars'])}",
        f"- Tradeoffs: {_joined(document['success']['tradeoffs'])}",
        "",
        "## Constraints",
        "",
        f"- Technical constraints: {_joined(document['constraints']['technical'])}",
        f"- Product constraints: {_joined(document['constraints']['product'])}",
        f"- Protected areas: {_joined(document['constraints']['protected_surfaces'])}",
        "",
        "## Non-goals",
        "",
    ])
    _list(lines, document["non_goals"])
    lines.extend([
        "",
        "## Finished State",
        "",
        f"- {_inline(document['finished_state'])}",
        "",
        "## Autonomy Policy",
        "",
        f"- May derive automatically: {_joined(document['autonomy_policy']['may_derive'])}",
        f"- Human review required: {_joined(document['autonomy_policy']['human_review_required'])}",
        f"- Never unattended: {_joined(document['autonomy_policy']['never_unattended'])}",
    ])
    return "\n".join(lines) + "\n"


def render_roadmap(document: dict) -> str:
    lines = _header("roadmap", document, "created_at")
    lines.extend(["", "## Future State", ""])
    _list(lines, document["future_state"])
    lines.extend(["", "## Milestones"])
    if not document["items"]:
        lines.extend(["", "- none"])
    for item in document["items"]:
        eligibility = item["execution_eligibility"]
        lines.extend([
            "",
            f"### {_inline(item['item_id'])}",
            "",
            f"- status: {_inline(item['status'])}",
            f"- priority: {_inline(item['priority'])}",
            f"- rationale: {_inline(item['rationale'])}",
            f"- depends-on: {_joined(item['depends_on'])}",
            f"- evidence: {_joined(item['evidence'])}",
            f"- safety: {_inline(item['safety'])}",
            f"- desired-outcome: {_inline(item['desired_outcome'])}",
            "- execution-eligibility:",
            f"  - status: {_inline(eligibility['status'])}",
            f"  - reasons: {_joined(eligibility['reasons'])}",
            f"  - evaluated-at: {_inline(eligibility['evaluated_at'])}",
            f"  - base-commit: {_inline(eligibility['base_commit'])}",
        ])
    lines.extend(["", "## Open Questions"])
    if not document["open_questions"]:
        lines.extend(["", "- none"])
    for question in document["open_questions"]:
        lines.extend([
            "",
            f"### {_inline(question['question_id'])}",
            "",
            f"- question: {_inline(question['question'])}",
            f"- blocked-item-ids: {_joined(question['blocked_item_ids'])}",
        ])
    return "\n".join(lines) + "\n"


def render_doctrine(document: dict) -> str:
    lines = _header("doctrine", document, "created_at")
    sections = (
        ("End Goal", [document["end_goal"]]),
        ("Product Philosophy", document["product_philosophy"]),
        ("User Intent", document["user_intent"]),
        ("Quality Bars", document["quality_bars"]),
        ("Improvement Heuristics", document["improvement_heuristics"]),
    )
    for heading, values in sections:
        lines.extend(["", f"## {heading}", ""])
        _list(lines, values)
    policy = document["autonomous_mission_policy"]
    lines.extend([
        "",
        "## Autonomous Mission Policy",
        "",
        f"- May derive and edit: {_joined(policy['may_derive_and_edit'])}",
        f"- Requires extra proof: {_joined(policy['requires_extra_proof'])}",
        f"- Human review required: {_joined(policy['human_review_required'])}",
        f"- Never unattended: {_joined(policy['never_unattended'])}",
        "",
        "## Irreversible/External Hard Stops",
        "",
    ])
    _list(lines, document["hard_stops"])
    return "\n".join(lines) + "\n"
