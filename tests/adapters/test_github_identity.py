import copy
import unittest
from datetime import datetime

from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
    GitHubEvidenceCredentialReceipt,
)
from pathfinder_core.adapters.github_identity import GitHubIdentityVerifier
from pathfinder_core.adapters.github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)
from pathfinder_core.merge_credentials import (
    MERGE_EXECUTOR_BOUNDARY,
    REQUIRED_MERGE_PERMISSIONS,
    GitHubMergeCredential,
)


NOW = "2026-08-11T12:08:10+00:00"
TOKEN = "fixture-secret-token-abcdefghijklmnopqrstuvwxyz"
REPOSITORY_ID = 123456789
REPOSITORY_NODE_ID = "R_kgDOExample1"
OWNER_ID = 24680


def evidence_credential(kind="installation-token"):
    return GitHubEvidenceCredential(
        TOKEN,
        kind=kind,
        permissions=(
            {name: "read" for name in REQUIRED_READ_PERMISSIONS}
            if kind == "installation-token"
            else {}
        ),
        boundary=EVIDENCE_BOUNDARY,
    )


def evidence_receipt(**overrides):
    values = {
        "credential_receipt_id": "evidence_credential_receipt_fixture1",
        "source": "authenticated-host-credential-store",
        "credential_id": "evidence_credential_fixture1",
        "kind": "installation-token",
        "boundary": EVIDENCE_BOUNDARY,
        "permissions": {name: "read" for name in REQUIRED_READ_PERMISSIONS},
        "repository_selection": "selected",
        "repository_ids": [REPOSITORY_ID],
        "app_id": 86420,
        "app_node_id": "A_kgDOObserver1",
        "installation_id": 97531,
        "installation_account_id": OWNER_ID,
        "actor_id": 112233,
        "actor_node_id": "U_kgDOObserver1",
        "login": "pathfinder-observer[bot]",
        "issued_at": "2026-08-11T12:00:00+00:00",
        "expires_at": "2026-08-11T13:00:00+00:00",
        "verified_at": NOW,
        "suspended": False,
    }
    values.update(overrides)
    return GitHubEvidenceCredentialReceipt(**values)


def merge_receipt():
    return GitHubMergeCredential(
        TOKEN,
        credential_receipt_id="merge_credential_receipt_fixture1",
        source="authenticated-host-credential-store",
        credential_id="merge_credential_fixture1",
        kind="installation-token",
        boundary=MERGE_EXECUTOR_BOUNDARY,
        permissions=REQUIRED_MERGE_PERMISSIONS,
        repository_ids=[REPOSITORY_ID],
        app_id=24681,
        app_node_id="A_kgDOMergeApp1",
        installation_id=97532,
        installation_account_id=OWNER_ID,
        actor_id=112234,
        actor_node_id="U_kgDOMergeBot1",
        login="pathfinder-merge[bot]",
        issued_at="2026-08-11T12:00:00+00:00",
        expires_at="2026-08-11T13:00:00+00:00",
        verified_at=NOW,
        repository_selection="selected",
        suspended=False,
    ).receipt_document()


def endpoint(data, request_id):
    return EndpointResponse(data, RequestAudit(request_id, NOW))


def observer_app_response():
    return {"id": 86420, "node_id": "A_kgDOObserver1", "slug": "observer"}


def merge_app_response():
    return {"id": 24681, "node_id": "A_kgDOMergeApp1", "slug": "merge"}


def installation_response(*, merge=False):
    return {
        "id": 97532 if merge else 97531,
        "app_id": 24681 if merge else 86420,
        "account": {
            "id": OWNER_ID,
            "node_id": "O_kgDOOwner1",
            "login": "example-owner",
        },
        "repository_selection": "selected",
        "permissions": dict(
            REQUIRED_MERGE_PERMISSIONS
            if merge
            else {name: "read" for name in REQUIRED_READ_PERMISSIONS}
        ),
        "suspended_at": None,
    }


def actor_response(*, merge=False):
    return {
        "id": 112234 if merge else 112233,
        "node_id": "U_kgDOMergeBot1" if merge else "U_kgDOObserver1",
        "login": "pathfinder-merge[bot]" if merge else "pathfinder-observer[bot]",
        "type": "Bot",
        "site_admin": False,
    }


def repository_response():
    return {
        "id": REPOSITORY_ID,
        "node_id": REPOSITORY_NODE_ID,
        "owner": {
            "id": OWNER_ID,
            "node_id": "O_kgDOOwner1",
            "login": "example-owner",
        },
        "name": "example-repo",
        "full_name": "example-owner/example-repo",
        "default_branch": "main",
        "archived": False,
        "disabled": False,
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
    }


class FakeClient:
    def __init__(self, credential, responses):
        self.credential = credential
        self.responses = {
            key: list(value) if isinstance(value, tuple) else [value]
            for key, value in responses.items()
        }
        self.calls = []

    def get_endpoint(self, surface, target):
        self.calls.append((surface, target))
        values = self.responses.get(target, [])
        if not values:
            raise AssertionError(f"unexpected identity request: {target}")
        return values.pop(0)


def verifier(**overrides):
    observer_app = FakeClient(evidence_credential("app-jwt"), {
        "/app": endpoint(observer_app_response(), "observer-app-request"),
        "/repos/example-owner/example-repo/installation": endpoint(
            installation_response(), "observer-installation-request"
        ),
    })
    observer_installation = FakeClient(evidence_credential(), {
        "/users/pathfinder-observer%5Bbot%5D": endpoint(
            actor_response(), "observer-actor-request"
        ),
        "/repos/example-owner/example-repo": endpoint(
            repository_response(), "repository-request"
        ),
        "/users/pathfinder-merge%5Bbot%5D": endpoint(
            actor_response(merge=True), "merge-actor-request"
        ),
    })
    merge_app = FakeClient(evidence_credential("app-jwt"), {
        "/app": endpoint(merge_app_response(), "merge-app-request"),
        "/repos/example-owner/example-repo/installation": endpoint(
            installation_response(merge=True), "merge-installation-request"
        ),
    })
    clients = {
        "observer_app": observer_app,
        "observer_installation": observer_installation,
        "merge_app": merge_app,
    }
    clients.update(overrides)
    return GitHubIdentityVerifier(**clients), clients


class GitHubIdentityVerifierTests(unittest.TestCase):
    def test_exact_observer_and_merge_identities_cross_check_live_responses(self):
        value, clients = verifier()
        observer = value.verify_observer(
            evidence_receipt(),
            owner="example-owner",
            name="example-repo",
            repository_node_id=REPOSITORY_NODE_ID,
            observed_at=datetime.fromisoformat(NOW),
        )
        merge = value.verify_merge_actor(
            merge_receipt(),
            owner="example-owner",
            name="example-repo",
            repository_id=REPOSITORY_ID,
            observed_at=datetime.fromisoformat(NOW),
        )
        self.assertEqual(observer.repository["id"], REPOSITORY_ID)
        self.assertEqual(observer.repository["default_branch"], "main")
        self.assertEqual(len(observer.requests), 4)
        self.assertEqual(merge.actor["user"]["id"], 112234)
        self.assertEqual(merge.actor["permissions"], {"administration": "none"})
        self.assertEqual(len(merge.requests), 3)
        self.assertEqual(
            [target for _surface, target in clients["merge_app"].calls],
            ["/app", "/repos/example-owner/example-repo/installation"],
        )

    def test_observer_identity_drift_and_suspension_fail_closed(self):
        cases = (
            ("app-id", observer_app_response(), "id", 999),
            ("installation", installation_response(), "repository_selection", "all"),
            ("suspension", installation_response(), "suspended_at", NOW),
            ("actor-type", actor_response(), "type", "User"),
            ("repository", repository_response(), "node_id", "R_kgDODifferent1"),
        )
        for name, original, key, replacement in cases:
            with self.subTest(name=name):
                changed = copy.deepcopy(original)
                changed[key] = replacement
                value, clients = verifier()
                if name == "app-id":
                    clients["observer_app"].responses["/app"] = [
                        endpoint(changed, "changed-request")
                    ]
                elif name in {"installation", "suspension"}:
                    clients["observer_app"].responses[
                        "/repos/example-owner/example-repo/installation"
                    ] = [endpoint(changed, "changed-request")]
                elif name == "actor-type":
                    clients["observer_installation"].responses[
                        "/users/pathfinder-observer%5Bbot%5D"
                    ] = [endpoint(changed, "changed-request")]
                else:
                    clients["observer_installation"].responses[
                        "/repos/example-owner/example-repo"
                    ] = [endpoint(changed, "changed-request")]
                with self.assertRaises(GitHubObservationError) as caught:
                    value.verify_observer(
                        evidence_receipt(), owner="example-owner",
                        name="example-repo",
                        repository_node_id=REPOSITORY_NODE_ID,
                        observed_at=datetime.fromisoformat(NOW),
                    )
                self.assertEqual(
                    caught.exception.outcome,
                    ObservationOutcome.ACTOR_IDENTITY_UNKNOWN,
                )

    def test_merge_receipt_hash_time_repository_and_live_permission_fail_closed(self):
        tampered = merge_receipt()
        tampered["actor_id"] += 1
        value, _clients = verifier()
        with self.assertRaises(GitHubObservationError) as caught:
            value.verify_merge_actor(
                tampered, owner="example-owner", name="example-repo",
                repository_id=REPOSITORY_ID,
                observed_at=datetime.fromisoformat(NOW),
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.ACTOR_IDENTITY_UNKNOWN
        )

        value, _clients = verifier()
        with self.assertRaises(GitHubObservationError):
            value.verify_merge_actor(
                merge_receipt(), owner="example-owner", name="example-repo",
                repository_id=999,
                observed_at=datetime.fromisoformat(NOW),
            )

        value, clients = verifier()
        widened = installation_response(merge=True)
        widened["permissions"]["administration"] = "write"
        clients["merge_app"].responses[
            "/repos/example-owner/example-repo/installation"
        ] = [endpoint(widened, "widened-request")]
        with self.assertRaises(GitHubObservationError):
            value.verify_merge_actor(
                merge_receipt(), owner="example-owner", name="example-repo",
                repository_id=REPOSITORY_ID,
                observed_at=datetime.fromisoformat(NOW),
            )


if __name__ == "__main__":
    unittest.main()
