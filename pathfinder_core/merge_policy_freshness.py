from __future__ import annotations

from datetime import datetime, timedelta

from .merge_policy_types import DenyCode


MAX_SNAPSHOT_AGE = timedelta(seconds=60)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed


def evaluate_snapshot_window(policy, evidence, now: datetime, blocks) -> None:
    observation = evidence["observation"]
    try:
        observed = _time(observation["observed_at"])
        completed = _time(observation["completed_at"])
        host_expiry = _time(observation["expires_at"])
        policy_age = timedelta(
            seconds=policy["freshness"]["max_snapshot_age_seconds"]
        )
        hard_expiry = observed + min(MAX_SNAPSHOT_AGE, policy_age)
        current = observed <= completed <= now < min(host_expiry, hard_expiry)
    except (TypeError, ValueError):
        current = False
    if not current:
        blocks.add(
            DenyCode.EVIDENCE_EXPIRED,
            "observation",
            "evidence exceeds its host expiry or effective freshness window",
        )


def compare_complete_reread(initial, reread, blocks) -> None:
    try:
        ordered = _time(initial["observation"]["completed_at"]) < _time(
            reread["observation"]["observed_at"]
        )
    except (TypeError, ValueError):
        ordered = False
    if not ordered:
        blocks.add(
            DenyCode.EVIDENCE_EXPIRED,
            "reread.observation",
            "complete reread must start after the initial snapshot completes",
        )

    initial_ids = {item["request_id"] for item in initial["observation"]["requests"]}
    reread_ids = {item["request_id"] for item in reread["observation"]["requests"]}
    if (
        initial["evidence_id"] == reread["evidence_id"]
        or initial["evidence_sha256"] == reread["evidence_sha256"]
        or initial_ids & reread_ids
        or initial["observation"]["policy_read"]["receipt_id"]
        == reread["observation"]["policy_read"]["receipt_id"]
    ):
        blocks.add(
            DenyCode.IDENTITY_DRIFT,
            "reread.observation",
            "reread must have a new evidence identity and disjoint request ids",
        )
    if (
        initial["observation"]["policy_read"]["policy_id"]
        != reread["observation"]["policy_read"]["policy_id"]
        or initial["observation"]["policy_read"]["policy_sha256"]
        != reread["observation"]["policy_read"]["policy_sha256"]
    ):
        blocks.add(
            DenyCode.IDENTITY_DRIFT,
            "reread.policy_read",
            "host policy changed between complete snapshots",
        )

    initial_merge = {
        key: value for key, value in initial["mergeability"].items()
        if key != "review_decision"
    }
    reread_merge = {
        key: value for key, value in reread["mergeability"].items()
        if key != "review_decision"
    }
    domains = (
        (DenyCode.IDENTITY_DRIFT, "reread.authority", initial["bindings"], reread["bindings"]),
        (DenyCode.IDENTITY_DRIFT, "reread.repository", initial["repository"], reread["repository"]),
        (DenyCode.IDENTITY_DRIFT, "reread.actor", initial["actor"], reread["actor"]),
        (
            DenyCode.IDENTITY_DRIFT,
            "reread.pull_request",
            (initial["pull_request"], initial_merge),
            (reread["pull_request"], reread_merge),
        ),
        (DenyCode.DIFF_DRIFT, "reread.diff", initial["diff"], reread["diff"]),
        (
            DenyCode.RULESET_DRIFT,
            "reread.rules",
            (
                initial["classic_protection"], initial["active_rules"],
                initial["source_rulesets"], initial["bypass_memberships"],
            ),
            (
                reread["classic_protection"], reread["active_rules"],
                reread["source_rulesets"], reread["bypass_memberships"],
            ),
        ),
        (
            DenyCode.REVIEW_DRIFT,
            "reread.reviews",
            (
                initial["mergeability"]["review_decision"], initial["reviews"],
                initial["review_requests"], initial["review_threads"],
            ),
            (
                reread["mergeability"]["review_decision"], reread["reviews"],
                reread["review_requests"], reread["review_threads"],
            ),
        ),
        (DenyCode.CHECK_EVIDENCE_INCOMPLETE, "reread.checks", initial["checks"], reread["checks"]),
        (
            DenyCode.FIELD_UNKNOWN,
            "reread.completeness",
            (
                initial["observation"]["rest_api_version"],
                initial["observation"]["graphql_query_sha256"], initial["pagination"],
                initial["unknown_reasons"], initial["unsupported_reasons"],
            ),
            (
                reread["observation"]["rest_api_version"],
                reread["observation"]["graphql_query_sha256"], reread["pagination"],
                reread["unknown_reasons"], reread["unsupported_reasons"],
            ),
        ),
    )
    for code, surface, before, after in domains:
        if before != after:
            blocks.add(code, surface, "complete reread differs; start a new snapshot cycle")
