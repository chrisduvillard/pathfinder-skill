import unittest

from pathfinder_core.adapters.github_check_policy import (
    GitHubRequiredCheckProjector,
)
from pathfinder_core.adapters.github_get import QualifiedFeatureResponse
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
    RequestAudit,
)


def audit(request_id, *, target=None, status=None, qualified=None):
    return RequestAudit(
        request_id,
        "2026-08-12T12:00:00+00:00",
        None,
        target,
        status,
        qualified,
    )


def classic(checks=()):
    contexts = [item[0] for item in checks]
    return QualifiedFeatureResponse(
        {
            "url": "https://api.github.com/repos/owner/repo/branches/main/protection",
            "required_status_checks": {
                "url": "https://api.github.com/status-checks",
                "strict": True,
                "contexts": contexts,
                "contexts_url": "https://api.github.com/contexts",
                "checks": [
                    {"context": context, "app_id": app_id}
                    for context, app_id in checks
                ],
            },
        },
        200,
        audit(
            "classic-1",
            target="/repos/owner/repo/branches/main/protection",
            status=200,
            qualified=True,
        ),
    )


def rule(rule_id, checks, *, rule_type="required_status_checks"):
    parameters = (
        {
            "required_status_checks": [
                {"context": context, "integration_id": app_id}
                for context, app_id in checks
            ],
            "strict_required_status_checks_policy": True,
        }
        if rule_type == "required_status_checks"
        else {}
    )
    return {
        "type": rule_type,
        "ruleset_source_type": "Repository",
        "ruleset_source": "owner/repo",
        "ruleset_id": rule_id,
        "parameters": parameters,
    }


def page(*items, complete=True, truncated=False, last_cursor=None):
    return PageResponse(
        items,
        1,
        len(items),
        complete,
        truncated,
        last_cursor,
        (audit("rules-1"),),
    )


def project(classic_response, active_page, host=None):
    return GitHubRequiredCheckProjector.project(
        host_policy_checks=host or [{"context": "host", "app_id": 1}],
        classic_protection=classic_response,
        active_rules=active_page,
    )


class GitHubRequiredCheckProjectorTests(unittest.TestCase):
    def test_unions_host_classic_and_every_active_ruleset(self):
        result = project(
            classic((("classic", 2), ("shared", 3))),
            page(
                rule(71, (("ruleset", 4), ("shared", 3))),
                rule(72, (), rule_type="pull_request"),
            ),
        )
        self.assertEqual(result, (
            {"context": "classic", "app_id": 2},
            {"context": "host", "app_id": 1},
            {"context": "ruleset", "app_id": 4},
            {"context": "shared", "app_id": 3},
        ))

    def test_accepts_only_qualified_feature_absence(self):
        absent = QualifiedFeatureResponse(
            None,
            403,
            audit(
                "classic-1",
                target="/repos/owner/repo/branches/main/protection",
                status=403,
                qualified=True,
            ),
        )
        self.assertEqual(
            project(absent, page()),
            ({"context": "host", "app_id": 1},),
        )
        for changed in (
            QualifiedFeatureResponse({}, 403, absent.audit),
            QualifiedFeatureResponse(
                None,
                403,
                audit(
                    "classic-1",
                    target="/repos/owner/repo/branches/main/protection",
                    status=403,
                    qualified=False,
                ),
            ),
        ):
            with self.assertRaises(GitHubObservationError):
                project(changed, page())

    def test_unpinned_or_contradictory_classic_checks_fail_closed(self):
        unpinned = classic((("classic", None),))
        with self.assertRaises(GitHubObservationError) as caught:
            project(unpinned, page())
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        contradictory = classic((("classic", 2),))
        contradictory.data["required_status_checks"]["contexts"] = ["different"]
        with self.assertRaises(GitHubObservationError):
            project(contradictory, page())

    def test_incomplete_duplicate_or_unpinned_rules_fail_closed(self):
        reused_request = PageResponse(
            (rule(71, (("ruleset", 4),)),),
            2,
            1,
            True,
            False,
            None,
            (audit("rules-1"), audit("rules-1")),
        )
        for active in (
            page(rule(71, (("ruleset", 4),)), complete=False, truncated=True),
            reused_request,
            page(
                rule(71, (("ruleset", 4),)),
                rule(71, (("another", 5),)),
            ),
            page(rule(71, (("ruleset", None),))),
        ):
            with self.assertRaises(GitHubObservationError):
                project(classic(), active)

    def test_host_policy_must_be_nonempty_closed_and_unique(self):
        for host in (
            [],
            [{"context": "host"}],
            [
                {"context": "host", "app_id": 1},
                {"context": "host", "app_id": 1},
            ],
        ):
            with self.assertRaises(GitHubObservationError):
                GitHubRequiredCheckProjector.project(
                    host_policy_checks=host,
                    classic_protection=classic(),
                    active_rules=page(),
                )


if __name__ == "__main__":
    unittest.main()
