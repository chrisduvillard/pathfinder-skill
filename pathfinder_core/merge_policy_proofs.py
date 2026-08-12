from __future__ import annotations

from datetime import datetime

from .merge_policy_types import CheckRequirement, DenyCode


ELIGIBLE_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
ELIGIBLE_PERMISSIONS = frozenset({"admin", "write"})


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp has no UTC offset")
    return parsed


def evaluate_reviews(
    policy, authorization, evidence, required_approvals: int, blocks
) -> tuple[int, ...]:
    pull = evidence["pull_request"]
    completed = _time(evidence["observation"]["completed_at"])
    decision = evidence["mergeability"]["review_decision"]
    if decision == "UNKNOWN":
        blocks.add(DenyCode.REVIEW_STATE_UNKNOWN, "mergeability.review_decision", "review decision is unknown")
    elif decision == "CHANGES_REQUESTED":
        blocks.add(DenyCode.CHANGES_REQUESTED, "mergeability.review_decision", "GitHub reports requested changes")
    elif decision == "REVIEW_REQUIRED":
        blocks.add(DenyCode.INDEPENDENT_REVIEW_MISSING, "mergeability.review_decision", "GitHub still requires review")
    effective = {}
    review_ids = set()
    for review in evidence["reviews"]:
        if review["id"] in review_ids:
            blocks.add(DenyCode.REVIEW_DRIFT, f"reviews.{review['id']}", "review id is duplicated")
        review_ids.add(review["id"])
        try:
            submitted = _time(review["submitted_at"])
        except (TypeError, ValueError):
            blocks.add(DenyCode.REVIEW_STATE_UNKNOWN, "reviews", "review time is invalid")
            continue
        if submitted > completed:
            blocks.add(DenyCode.REVIEW_DRIFT, f"reviews.{review['id']}", "review postdates observation")
        if review["state"] == "PENDING":
            blocks.add(DenyCode.REVIEW_STATE_UNKNOWN, f"reviews.{review['id']}", "review is pending")
        if (review["state"] == "DISMISSED") != review["dismissed"]:
            blocks.add(
                DenyCode.REVIEW_STATE_UNKNOWN,
                f"reviews.{review['id']}",
                "review dismissal fields disagree",
            )
        if review["state"] not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"} and not review["dismissed"]:
            continue
        previous = effective.get(review["actor_id"])
        if previous is not None and submitted == _time(previous["submitted_at"]):
            blocks.add(DenyCode.REVIEW_DRIFT, f"reviews.{review['actor_id']}", "latest review is ambiguous")
        if previous is None or (submitted, review["id"]) > (
            _time(previous["submitted_at"]), previous["id"]
        ):
            effective[review["actor_id"]] = review

    excluded = {
        pull["author_id"], pull["last_pusher_id"], evidence["actor"]["actor_id"],
        *authorization["implementation_actor_ids"],
        *(item["creator_actor_id"] for item in evidence["checks"]),
    }
    human_reviewers = set(
        policy["review_requirements"]["human_reviewer_actor_ids"]
    )
    approvals = []
    for actor_id, review in sorted(effective.items()):
        if review["state"] == "CHANGES_REQUESTED" and not review["dismissed"]:
            blocks.add(DenyCode.CHANGES_REQUESTED, f"reviews.{review['id']}", "effective changes are requested")
        if (
            review["state"] == "APPROVED" and not review["dismissed"]
            and review["commit_sha"] == evidence["mergeability"]["required_sha"]
            and review["actor_type"] == "User"
            and review["repository_permission"] in ELIGIBLE_PERMISSIONS
            and review["author_association"] in ELIGIBLE_ASSOCIATIONS
            and actor_id in human_reviewers
            and actor_id not in excluded
        ):
            approvals.append(actor_id)
    if any(request["as_code_owner"] for request in evidence["review_requests"]):
        blocks.add(DenyCode.CODE_OWNER_REVIEW_MISSING, "review_requests", "code-owner review is still requested")
    if any(not thread["resolved"] and not thread["outdated"] for thread in evidence["review_threads"]):
        blocks.add(DenyCode.UNRESOLVED_THREAD, "review_threads", "a current review thread is unresolved")
    if len(approvals) < required_approvals:
        blocks.add(DenyCode.INDEPENDENT_REVIEW_MISSING, "reviews", "independent approval floor is unmet")
    return tuple(approvals)


def evaluate_checks(evidence, required, enforced, blocks) -> None:
    checks = evidence["checks"]
    expected_sha = evidence["mergeability"]["required_sha"]
    completed = _time(evidence["observation"]["completed_at"])
    check_ids = set()
    for item in checks:
        identity = (item["source"], item["id"])
        if identity in check_ids:
            blocks.add(
                DenyCode.CHECK_EVIDENCE_INCOMPLETE,
                f"checks.{item['source']}.{item['id']}",
                "check id is duplicated",
            )
        check_ids.add(identity)
        if item["completed_at"] is not None and _time(item["completed_at"]) > completed:
            blocks.add(
                DenyCode.CHECK_EVIDENCE_INCOMPLETE,
                f"checks.{item['source']}.{item['id']}",
                "check completion postdates observation",
            )
    enforced_contexts = {item.context for item in enforced}
    observed_required = {
        CheckRequirement(item["context"], item["app_id"])
        for item in checks
        if item["required"] and item["source"] == "check-run" and item["app_id"] is not None
    }
    observed_status_contexts = {
        item["context"] for item in checks
        if item["required"] and item["source"] == "commit-status"
    }
    if not observed_required <= enforced or not observed_status_contexts <= enforced_contexts:
        blocks.add(DenyCode.RULESET_DRIFT, "checks.required", "required evidence is absent from policy rules")

    for requirement in sorted(required):
        context_checks = [
            item for item in checks
            if item["source"] == "check-run" and item["context"] == requirement.context
        ]
        app_checks = [item for item in context_checks if item["app_id"] == requirement.app_id]
        if not app_checks:
            code = DenyCode.UNEXPECTED_CHECK_APP if context_checks else DenyCode.REQUIRED_CHECK_UNPROVEN
            blocks.add(code, requirement.context, "required check run is missing or has the wrong app")
            continue
        current = [item for item in app_checks if item["sha"] == expected_sha]
        if not current:
            blocks.add(DenyCode.CHECK_SHA_DRIFT, requirement.context, "required check is on another SHA")
            continue
        if requirement in enforced and not any(item["required"] for item in current):
            blocks.add(DenyCode.REQUIRED_CHECK_UNPROVEN, requirement.context, "GitHub did not mark the check as required")
        _latest_check(current, requirement.context, blocks)

        statuses = [
            item for item in checks
            if item["source"] == "commit-status" and item["context"] == requirement.context
        ]
        if statuses:
            current_statuses = [item for item in statuses if item["sha"] == expected_sha]
            if not current_statuses:
                blocks.add(DenyCode.CHECK_SHA_DRIFT, requirement.context, "same-name status is on another SHA")
            else:
                _latest_check(current_statuses, requirement.context, blocks)


def _latest_check(items, context: str, blocks) -> None:
    if any(
        item["status"] != "completed"
        and (item["conclusion"] is not None or item["completed_at"] is not None)
        for item in items
    ):
        blocks.add(DenyCode.CHECK_EVIDENCE_INCOMPLETE, context, "pending check has terminal fields")
        return
    if any(item["status"] == "completed" and item["completed_at"] is None for item in items):
        blocks.add(DenyCode.CHECK_EVIDENCE_INCOMPLETE, context, "completed check has no timestamp")
        return
    if any(item["status"] != "completed" for item in items):
        blocks.add(DenyCode.REQUIRED_CHECK_PENDING, context, "required check is pending")
        return
    if any(item["conclusion"] is None for item in items):
        blocks.add(DenyCode.CHECK_EVIDENCE_INCOMPLETE, context, "completed check has no conclusion")
        return

    def key(item):
        return _time(item["completed_at"]).timestamp(), item["id"]

    ordered = sorted(items, key=key)
    if len(ordered) > 1 and (
        ordered[-1]["completed_at"], ordered[-1]["id"]
    ) == (
        ordered[-2]["completed_at"], ordered[-2]["id"]
    ):
        blocks.add(DenyCode.CHECK_EVIDENCE_INCOMPLETE, context, "latest check is ambiguous")
        return
    latest = ordered[-1]
    if latest["conclusion"] != "success":
        blocks.add(DenyCode.REQUIRED_CHECK_FAILED, context, "required check did not succeed")
