import copy
import unittest

from pathfinder_core.adapters.github_candidate_rest import GitHubCandidateRESTReader
from pathfinder_core.adapters.github_evidence_credentials import (
    EVIDENCE_BOUNDARY,
    REQUIRED_READ_PERMISSIONS,
    GitHubEvidenceCredential,
)
from pathfinder_core.adapters.github_get import GitHubGETClient
from pathfinder_core.adapters.github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
)
from tests.adapters.test_github_branch_ownership import pusher
from tests.adapters.test_github_get import FixtureGETTransport, response


def raw_pull():
    proof = pusher()
    side = lambda ref, sha: {
        "repo": {"id": proof.repository_id, "node_id": proof.repository_node_id},
        "ref": ref,
        "sha": sha,
    }
    return {
        "id": proof.pull_request_id,
        "node_id": proof.pull_request_node_id,
        "number": proof.pull_request_number,
        "state": "open",
        "draft": False,
        "user": {"id": 22222, "login": "author"},
        "head": side(proof.head_ref, proof.head_sha),
        "base": side(proof.base_ref, proof.base_sha),
        "merged": False,
        "merge_commit_sha": None,
        "merged_at": None,
        "merged_by": None,
    }


def raw_ref(name, sha):
    return {
        "ref": f"refs/heads/{name}",
        "node_id": "REF_kgDOFixture1",
        "url": "https://api.github.com/ref",
        "object": {
            "type": "commit",
            "sha": sha,
            "url": "https://api.github.com/commit",
        },
    }


def object_evidence(*, second_binary=True):
    return {
        "source": "authenticated-controller-git-diff",
        "receipt_id": "object_evidence_candidate1",
        "files": [
            {
                "path": "docs/guide.md",
                "previous_path": None,
                "object_kind": "regular-file",
                "binary": False,
            },
            {
                "path": "assets/logo.png",
                "previous_path": None,
                "object_kind": "regular-file",
                "binary": second_binary,
            },
        ],
    }


def raw_files():
    return [
        {
            "filename": "docs/guide.md",
            "status": "modified",
            "sha": "e" * 40,
            "additions": 2,
            "deletions": 1,
            "changes": 3,
            "patch": "@@ -1 +1 @@\n-old\n+new",
        },
        {
            "filename": "assets/logo.png",
            "status": "modified",
            "sha": "f" * 40,
            "additions": 0,
            "deletions": 0,
            "changes": 0,
        },
    ]


class GitHubCandidateRESTReaderTests(unittest.TestCase):
    def reader(self, *, pull=None, head=None, base=None, files=None, merged=None):
        proof = pusher()
        payloads = (
            pull or raw_pull(),
            head or raw_ref(proof.head_ref, proof.head_sha),
            base or raw_ref(proof.base_ref, proof.base_sha),
            files or raw_files(),
            [],
            merged or raw_pull(),
        )
        results = []
        for index, payload in enumerate(payloads, 1):
            results.append(response(
                data=payload,
                headers={"X-GitHub-Request-Id": f"candidate-request-{index}"},
            ))
        transport = FixtureGETTransport(*results)
        credential = GitHubEvidenceCredential(
            "test-candidate-observer-installation-token",
            kind="installation-token",
            permissions={name: "read" for name in REQUIRED_READ_PERMISSIONS},
            boundary=EVIDENCE_BOUNDARY,
        )
        reader = GitHubCandidateRESTReader(GitHubGETClient(
            credential,
            transport=transport,
            clock=lambda: "2026-08-11T12:08:10+00:00",
            sleeper=lambda _seconds: None,
        ))
        return reader, transport

    def test_normalizes_exact_candidate_diff_deployments_and_merge_state(self):
        proof = pusher()
        reader, transport = self.reader()
        snapshot = reader.read_all(
            controller_pusher=proof,
            object_evidence=object_evidence(),
        )

        self.assertEqual(snapshot.pull_request.data["head"]["sha"], proof.head_sha)
        self.assertEqual(snapshot.refs.data, {
            "head": {"ref": proof.head_ref, "sha": proof.head_sha},
            "base": {"ref": proof.base_ref, "sha": proof.base_sha},
        })
        self.assertEqual(
            snapshot.changed_files.items[0]["patch_bytes"],
            len(raw_files()[0]["patch"].encode("utf-8")),
        )
        self.assertEqual(snapshot.changed_files.items[1]["patch_bytes"], 0)
        self.assertEqual(snapshot.deployments.items, ())
        self.assertFalse(snapshot.merged_state.data["merged"])
        repository = "/repos/example-owner/example-repo"
        self.assertEqual([call["path"] for call in transport.calls], [
            f"{repository}/pulls/72",
            f"{repository}/git/ref/heads/{proof.head_ref}",
            f"{repository}/git/ref/heads/{proof.base_ref}",
            f"{repository}/pulls/72/files?per_page=100",
            f"{repository}/deployments?sha={proof.head_sha}&per_page=100",
            f"{repository}/pulls/72",
        ])

    def test_ref_candidate_or_merge_identity_drift_fails_closed(self):
        proof = pusher()
        changed = raw_pull()
        changed["head"]["sha"] = "d" * 40
        reader, _transport = self.reader(pull=changed)
        with self.assertRaises(GitHubObservationError) as caught:
            reader.read_all(
                controller_pusher=proof, object_evidence=object_evidence()
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.FIELD_UNKNOWN)

        changed_ref = raw_ref(proof.head_ref, "d" * 40)
        reader, _transport = self.reader(head=changed_ref)
        with self.assertRaisesRegex(GitHubObservationError, "ref differs"):
            reader.read_all(
                controller_pusher=proof, object_evidence=object_evidence()
            )

        changed_merge = raw_pull()
        changed_merge["number"] = 73
        reader, _transport = self.reader(merged=changed_merge)
        with self.assertRaisesRegex(GitHubObservationError, "merge state differs"):
            reader.read_all(
                controller_pusher=proof, object_evidence=object_evidence()
            )

    def test_omitted_nonbinary_patch_or_object_mismatch_fails_closed(self):
        files = copy.deepcopy(raw_files())
        del files[0]["patch"]
        reader, _transport = self.reader(files=files)
        with self.assertRaises(GitHubObservationError) as caught:
            reader.read_all(
                controller_pusher=pusher(), object_evidence=object_evidence()
            )
        self.assertEqual(caught.exception.outcome, ObservationOutcome.DIFF_INCOMPLETE)

        reader, _transport = self.reader()
        mismatched = object_evidence()
        mismatched["files"][1]["path"] = "assets/other.png"
        with self.assertRaisesRegex(GitHubObservationError, "differ"):
            reader.read_all(
                controller_pusher=pusher(), object_evidence=mismatched
            )

    def test_malformed_file_and_merge_state_are_typed_fail_closed(self):
        files = copy.deepcopy(raw_files())
        files[0]["filename"] = ["not", "a", "path"]
        reader, _transport = self.reader(files=files)
        with self.assertRaises(GitHubObservationError) as caught:
            reader.read_all(
                controller_pusher=pusher(), object_evidence=object_evidence()
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.DIFF_INCOMPLETE
        )

        merged = raw_pull()
        merged["merged"] = 0
        reader, _transport = self.reader(merged=merged)
        with self.assertRaises(GitHubObservationError) as caught:
            reader.read_all(
                controller_pusher=pusher(), object_evidence=object_evidence()
            )
        self.assertEqual(
            caught.exception.outcome, ObservationOutcome.MALFORMED_RESPONSE
        )

    def test_reader_is_unconstructed_and_owns_no_secret_or_mutation_route(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        source_path = (
            root / "pathfinder_core" / "adapters" / "github_candidate_rest.py"
        )
        source = source_path.read_text()
        for forbidden in (
            "os.environ", "def merge", "def publish", "def push",
            "GitHubHTTPSGETTransport",
        ):
            self.assertNotIn(forbidden, source)
        callers = []
        for path in (root / "pathfinder_core").rglob("*.py"):
            if path == source_path:
                continue
            if "GitHubCandidateRESTReader(" in path.read_text():
                callers.append(path.relative_to(root).as_posix())
        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
