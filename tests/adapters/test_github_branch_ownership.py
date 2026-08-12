import copy
import unittest
from dataclasses import replace
from pathlib import Path

from pathfinder_core.adapters.github_branch_ownership import (
    GitHubControllerBranchOwnershipProver,
)
from pathfinder_core.adapters.github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    PageResponse,
    RequestAudit,
)
from pathfinder_core.adapters.github_publication_reconciliation import (
    ControllerPusherProof,
)
from pathfinder_core.storage import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_PATH = "/repos/example-owner/example-repo"
EVIDENCE_COMPLETED = "2026-08-11T12:08:20+00:00"
OBSERVED = "2026-08-11T12:08:21+00:00"
COMPLETED = "2026-08-11T12:08:23+00:00"


def pusher():
    return ControllerPusherProof(
        source="authenticated-controller-publication",
        last_pusher_id=97531,
        actor_node_id="U_kgDOBot1234",
        actor_login="pathfinder-publication[bot]",
        publication_receipt_id="publication_receipt_example1",
        publication_receipt_sha256="a" * 64,
        repository_id=123456789,
        repository_node_id="R_kgDOExample1",
        repository_owner="example-owner",
        repository_name="example-repo",
        pull_request_id=987654321,
        pull_request_node_id="PR_kwDOExample1",
        pull_request_number=72,
        head_ref="pathfinder/auto/example1",
        head_sha="c" * 40,
        base_ref="main",
        base_sha="b" * 40,
        receipt_observed_at="2026-08-11T12:06:00+00:00",
        graphql_observed_at="2026-08-11T12:08:10+00:00",
    )


def credential_receipt(**overrides):
    document = {
        "schema_version": 1,
        "credential_receipt_id": "publication_credential_receipt_fixture1",
        "source": "authenticated-host-credential-store",
        "credential_id": "publication_credential_fixture1",
        "kind": "installation-token",
        "boundary": "publication-only",
        "permissions": {
            "checks": "read",
            "contents": "write",
            "metadata": "read",
            "pull_requests": "write",
            "statuses": "read",
        },
        "repository_selection": "selected",
        "repository_ids": [123456789],
        "app_id": 86420,
        "app_node_id": "A_kgDOPublisher1",
        "installation_id": 13579,
        "installation_account_id": 123456789,
        "actor_id": 97531,
        "actor_node_id": "U_kgDOBot1234",
        "login": "pathfinder-publication[bot]",
        "issued_at": "2026-08-11T12:00:00+00:00",
        "expires_at": "2026-08-11T13:00:00+00:00",
        "verified_at": "2026-08-11T12:00:00+00:00",
        "suspended": False,
        "receipt_sha256": "0" * 64,
    }
    document.update(overrides)
    document["receipt_sha256"] = canonical_sha256(
        document, "receipt_sha256"
    )
    return document


def audit(request_id, observed_at, target):
    return RequestAudit(
        request_id,
        observed_at,
        target=target,
        status=200,
        permission_qualified=True,
    )


def rule(rule_type):
    result = {"type": rule_type}
    if rule_type == "update":
        result["parameters"] = {"update_allows_fetch_and_merge": False}
    return result


def effective_rule(rule_type):
    return rule(rule_type) | {
        "ruleset_source_type": "Repository",
        "ruleset_source": "example-owner/example-repo",
        "ruleset_id": 7002,
    }


def ruleset_response():
    return EndpointResponse(
        {
            "id": 7002,
            "node_id": "RRS_kgDOOwnership1",
            "name": "Pathfinder controller branches",
            "target": "branch",
            "source_type": "Repository",
            "source": "example-owner/example-repo",
            "enforcement": "active",
            "bypass_actors": [{
                "actor_id": 86420,
                "actor_type": "Integration",
                "bypass_mode": "always",
            }],
            "conditions": {
                "ref_name": {
                    "include": ["refs/heads/pathfinder/auto/*"],
                    "exclude": [],
                }
            },
            "rules": [rule(value) for value in ("creation", "deletion", "update")],
            "created_at": "2026-08-10T09:00:00+00:00",
            "updated_at": "2026-08-10T09:00:00+00:00",
        },
        audit(
            "req-ownership-ruleset-1",
            OBSERVED,
            f"{REPOSITORY_PATH}/rulesets/7002",
        ),
    )


def effective_rules():
    items = tuple(effective_rule(value) for value in (
        "creation", "deletion", "update"
    ))
    return PageResponse(
        items,
        1,
        len(items),
        True,
        False,
        None,
        (audit(
            "req-ownership-effective-1",
            "2026-08-11T12:08:22+00:00",
            f"{REPOSITORY_PATH}/rules/branches/pathfinder/auto/example1",
        ),),
    )


def branch_ref():
    return EndpointResponse(
        {
            "ref": "refs/heads/pathfinder/auto/example1",
            "node_id": "REF_kgDOBranch1",
            "url": "https://api.github.com/ref",
            "object": {
                "type": "commit",
                "sha": "c" * 40,
                "url": "https://api.github.com/commit",
            },
        },
        audit(
            "req-ownership-ref-1",
            COMPLETED,
            f"{REPOSITORY_PATH}/git/ref/heads/pathfinder/auto/example1",
        ),
    )


class GitHubControllerBranchOwnershipTests(unittest.TestCase):
    def prove(self, **overrides):
        values = {
            "controller_pusher": pusher(),
            "publication_credential_receipt": credential_receipt(),
            "ruleset": ruleset_response(),
            "effective_rules": effective_rules(),
            "branch_ref": branch_ref(),
            "evidence_completed_at": EVIDENCE_COMPLETED,
            "observed_at": OBSERVED,
            "completed_at": COMPLETED,
            "ownership_id": "controller_branch_ownership_fixture1",
        }
        values.update(overrides)
        return GitHubControllerBranchOwnershipProver.prove(**values)

    def test_proves_sole_publication_app_control_through_exact_ref_reread(self):
        document = self.prove()
        self.assertEqual(document["publisher"]["app_id"], 86420)
        self.assertEqual(
            document["ruleset"]["required_rules"],
            ["creation", "deletion", "update"],
        )
        self.assertEqual(document["head_sha"], "c" * 40)
        self.assertEqual(
            document["ownership_sha256"],
            canonical_sha256(document, "ownership_sha256"),
        )
        GitHubControllerBranchOwnershipProver.validate_document(document)

    def test_missing_rule_or_extra_bypass_actor_fails_closed(self):
        page = effective_rules()
        page = replace(
            page,
            items=page.items[:-1],
            total_count=page.total_count - 1,
        )
        with self.assertRaisesRegex(GitHubObservationError, "not all active"):
            self.prove(effective_rules=page)

        response = ruleset_response()
        changed = copy.deepcopy(response.data)
        changed["bypass_actors"].append({
            "actor_id": 7,
            "actor_type": "User",
            "bypass_mode": "always",
        })
        with self.assertRaisesRegex(GitHubObservationError, "sole"):
            self.prove(ruleset=replace(response, data=changed))

    def test_publisher_ref_and_request_identity_drift_fail_closed(self):
        with self.assertRaisesRegex(GitHubObservationError, "pusher identities"):
            self.prove(publication_credential_receipt=credential_receipt(actor_id=7))

        malformed = credential_receipt()
        malformed["permissions"]["contents"] = "read"
        malformed["receipt_sha256"] = canonical_sha256(
            malformed, "receipt_sha256"
        )
        with self.assertRaisesRegex(GitHubObservationError, "receipt is invalid"):
            self.prove(publication_credential_receipt=malformed)

        response = branch_ref()
        changed = copy.deepcopy(response.data)
        changed["object"]["sha"] = "d" * 40
        with self.assertRaisesRegex(GitHubObservationError, "no longer points"):
            self.prove(branch_ref=replace(response, data=changed))

        page = effective_rules()
        bad_audit = replace(page.audits[0], target=f"{REPOSITORY_PATH}/rulesets")
        with self.assertRaisesRegex(GitHubObservationError, "not qualified"):
            self.prove(effective_rules=replace(page, audits=(bad_audit,)))

    def test_fetch_and_merge_or_nondedicated_ruleset_fails_closed(self):
        response = ruleset_response()
        changed = copy.deepcopy(response.data)
        changed["rules"][2]["parameters"][
            "update_allows_fetch_and_merge"
        ] = True
        with self.assertRaisesRegex(GitHubObservationError, "fetch-and-merge"):
            self.prove(ruleset=replace(response, data=changed))

        changed = copy.deepcopy(response.data)
        changed["rules"].append({"type": "required_linear_history"})
        with self.assertRaisesRegex(GitHubObservationError, "dedicated"):
            self.prove(ruleset=replace(response, data=changed))

    def test_stale_incomplete_or_reused_requests_fail_closed(self):
        with self.assertRaisesRegex(GitHubObservationError, "stale or out of order"):
            self.prove(evidence_completed_at="2026-08-11T12:08:22+00:00")

        page = replace(effective_rules(), complete=False, truncated=True)
        with self.assertRaisesRegex(GitHubObservationError, "incomplete"):
            self.prove(effective_rules=page)

        response = branch_ref()
        reused = replace(response.audit, request_id="req-ownership-effective-1")
        with self.assertRaisesRegex(GitHubObservationError, "reused"):
            self.prove(branch_ref=replace(response, audit=reused))

    def test_prover_is_pure_uncalled_and_owns_no_client_or_mutation(self):
        inputs = copy.deepcopy((
            credential_receipt(), ruleset_response(), effective_rules(), branch_ref()
        ))
        self.prove(
            publication_credential_receipt=inputs[0],
            ruleset=inputs[1],
            effective_rules=inputs[2],
            branch_ref=inputs[3],
        )
        self.assertEqual(
            inputs,
            (credential_receipt(), ruleset_response(), effective_rules(), branch_ref()),
        )
        source_path = (
            ROOT / "pathfinder_core" / "adapters" / "github_branch_ownership.py"
        )
        source = source_path.read_text()
        for forbidden in (
            "GitHubGETClient", "GitHubGraphQLClient", "GitHubHTTPS",
            "os.environ", "def merge", "def publish", "def push",
        ):
            self.assertNotIn(forbidden, source)
        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path == source_path or path.name == "github_evidence_composer.py":
                continue
            if "GitHubControllerBranchOwnershipProver." in path.read_text():
                callers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
