from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .github_get import GitHubGETClient
from .github_merge_observer import (
    EndpointResponse,
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)
from .github_publication_reconciliation import ControllerPusherProof


_REPOSITORY_PART = re.compile(r"[A-Za-z0-9_.-]+")
_BRANCH = re.compile(r"[A-Za-z0-9._/-]{1,255}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_FILE_STATUSES = frozenset({
    "added", "removed", "modified", "renamed", "copied", "changed",
    "unchanged",
})


def _fail(
    surface: str,
    detail: str,
    outcome: ObservationOutcome = ObservationOutcome.MALFORMED_RESPONSE,
) -> GitHubObservationError:
    return GitHubObservationError(outcome, surface, detail)


def _mapping(value: object, surface: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _fail(surface, "GitHub REST response is not an object")
    return value


def _required(
    value: object, required: set[str], surface: str
) -> Mapping[str, object]:
    raw = _mapping(value, surface)
    if not required <= set(raw):
        raise _fail(surface, "GitHub REST response is incomplete")
    return raw


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "GitHub REST identity is malformed")
    return value


def _count(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _fail(surface, "GitHub changed-file count is malformed")
    return value


@dataclass(frozen=True)
class GitHubCandidateRESTSnapshot:
    pull_request: EndpointResponse
    refs: EndpointResponse
    changed_files: PageResponse
    deployments: PageResponse
    merged_state: EndpointResponse


class GitHubCandidateRESTReader:
    """Normalize exact PR, ref, diff, deployment, and merge-state GETs."""

    def __init__(self, client: GitHubGETClient):
        if not isinstance(client, GitHubGETClient):
            raise TypeError("GitHub candidate reader requires a fixed GET client")
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub candidate reader requires an installation credential")
        self.client = client

    @property
    def credential(self):
        return self.client.credential

    @staticmethod
    def _paths(proof: ControllerPusherProof) -> tuple[str, str, str]:
        if not isinstance(proof, ControllerPusherProof):
            raise _fail(
                "candidate",
                "controller pusher proof is missing",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        identity = (
            proof.repository_owner,
            proof.repository_name,
            proof.head_ref,
            proof.base_ref,
            proof.head_sha,
            proof.base_sha,
        )
        if (
            any(not isinstance(value, str) for value in identity)
            or _REPOSITORY_PART.fullmatch(proof.repository_owner) is None
            or _REPOSITORY_PART.fullmatch(proof.repository_name) is None
            or _BRANCH.fullmatch(proof.head_ref) is None
            or _BRANCH.fullmatch(proof.base_ref) is None
            or _COMMIT.fullmatch(proof.head_sha) is None
            or _COMMIT.fullmatch(proof.base_sha) is None
            or not isinstance(proof.pull_request_number, int)
            or isinstance(proof.pull_request_number, bool)
            or proof.pull_request_number < 1
        ):
            raise _fail(
                "candidate",
                "controller candidate identity is malformed",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        repository = f"/repos/{proof.repository_owner}/{proof.repository_name}"
        pull = f"{repository}/pulls/{proof.pull_request_number}"
        return repository, pull, f"{repository}/git/ref/heads"

    @staticmethod
    def _repository_side(
        value: object,
        *,
        side: str,
        proof: ControllerPusherProof,
    ) -> dict[str, object]:
        raw = _required(value, {"repo", "ref", "sha"}, f"pull-request.{side}")
        repository = _required(
            raw["repo"], {"id", "node_id"}, f"pull-request.{side}.repo"
        )
        expected_ref = proof.head_ref if side == "head" else proof.base_ref
        expected_sha = proof.head_sha if side == "head" else proof.base_sha
        if (
            repository["id"] != proof.repository_id
            or repository["node_id"] != proof.repository_node_id
            or raw["ref"] != expected_ref
            or raw["sha"] != expected_sha
        ):
            raise _fail(
                f"pull-request.{side}",
                "GitHub REST candidate differs from the authenticated publication",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        return {
            "repo": {"id": repository["id"], "node_id": repository["node_id"]},
            "ref": raw["ref"],
            "sha": raw["sha"],
        }

    @classmethod
    def _pull_request(
        cls, response: EndpointResponse, proof: ControllerPusherProof
    ) -> EndpointResponse:
        raw = _required(
            response.data,
            {"id", "node_id", "number", "state", "draft", "user", "head", "base"},
            "pull-request",
        )
        user = _required(raw["user"], {"id"}, "pull-request.user")
        if (
            raw["id"] != proof.pull_request_id
            or raw["node_id"] != proof.pull_request_node_id
            or raw["number"] != proof.pull_request_number
            or raw["state"] != "open"
            or not isinstance(raw["draft"], bool)
        ):
            raise _fail(
                "pull-request",
                "GitHub REST pull request differs from the authenticated publication",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        return EndpointResponse(
            {
                "id": _positive_int(raw["id"], "pull-request"),
                "node_id": raw["node_id"],
                "number": _positive_int(raw["number"], "pull-request"),
                "state": raw["state"],
                "draft": raw["draft"],
                "user": {"id": _positive_int(user["id"], "pull-request.user")},
                "head": cls._repository_side(raw["head"], side="head", proof=proof),
                "base": cls._repository_side(raw["base"], side="base", proof=proof),
            },
            response.audit,
            response.extra_audits,
        )

    @staticmethod
    def _ref(
        response: EndpointResponse,
        *,
        name: str,
        sha: str,
        surface: str,
    ) -> dict[str, str]:
        raw = _required(response.data, {"ref", "object"}, surface)
        obj = _required(raw["object"], {"type", "sha"}, f"{surface}.object")
        if (
            raw["ref"] != f"refs/heads/{name}"
            or obj["type"] != "commit"
            or obj["sha"] != sha
        ):
            raise _fail(
                surface,
                "GitHub ref differs from the authenticated publication",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        return {"ref": name, "sha": sha}

    @staticmethod
    def _object_records(value: object) -> dict[tuple[object, object], bool]:
        raw = _required(value, {"source", "receipt_id", "files"}, "object-evidence")
        if raw["source"] != "authenticated-controller-git-diff" or not isinstance(
            raw["files"], list
        ):
            raise _fail(
                "object-evidence",
                "controller object evidence is malformed",
                ObservationOutcome.DIFF_INCOMPLETE,
            )
        records: dict[tuple[object, object], bool] = {}
        for index, value in enumerate(raw["files"]):
            item = _required(
                value,
                {"path", "previous_path", "object_kind", "binary"},
                f"object-evidence.files[{index}]",
            )
            key = (item["path"], item["previous_path"])
            if (
                not isinstance(item["path"], str)
                or not isinstance(item["previous_path"], (str, type(None)))
                or not isinstance(item["object_kind"], str)
                or not isinstance(item["binary"], bool)
                or key in records
            ):
                raise _fail(
                    "object-evidence",
                    "controller object evidence is ambiguous",
                    ObservationOutcome.DIFF_INCOMPLETE,
                )
            records[key] = item["binary"]
        return records

    @classmethod
    def _changed_files(
        cls, page: PageResponse, object_evidence: object
    ) -> PageResponse:
        records = cls._object_records(object_evidence)
        normalized = []
        seen = set()
        for index, value in enumerate(page.items):
            raw = _required(
                value,
                {"filename", "status", "sha", "additions", "deletions", "changes"},
                f"changed-files[{index}]",
            )
            previous = raw.get("previous_filename")
            key = (raw["filename"], previous)
            if (
                not isinstance(raw["filename"], str)
                or not isinstance(previous, (str, type(None)))
                or not isinstance(raw["status"], str)
                or raw["status"] not in _FILE_STATUSES
                or not isinstance(raw["sha"], str)
                or _COMMIT.fullmatch(raw["sha"]) is None
                or key in seen
            ):
                raise _fail(
                    "changed-files",
                    "GitHub changed-file identity or status is ambiguous",
                    ObservationOutcome.DIFF_INCOMPLETE,
                )
            seen.add(key)
            binary = records.get(key)
            if binary is None:
                raise _fail(
                    "changed-files",
                    "GitHub changed files differ from controller object evidence",
                    ObservationOutcome.DIFF_INCOMPLETE,
                )
            patch = raw.get("patch")
            if patch is None:
                if not binary:
                    raise _fail(
                        "changed-files",
                        "a non-binary GitHub patch was omitted",
                        ObservationOutcome.DIFF_INCOMPLETE,
                    )
                patch_bytes = 0
            elif not isinstance(patch, str):
                raise _fail("changed-files", "GitHub changed-file patch is malformed")
            else:
                patch_bytes = len(patch.encode("utf-8"))
            normalized.append({
                "filename": raw["filename"],
                "previous_filename": previous,
                "status": raw["status"],
                "sha": raw["sha"],
                "additions": _count(raw["additions"], "changed-files"),
                "deletions": _count(raw["deletions"], "changed-files"),
                "changes": _count(raw["changes"], "changed-files"),
                "patch_bytes": patch_bytes,
            })
        if page.complete and seen != set(records):
            raise _fail(
                "changed-files",
                "complete GitHub changed files differ from controller object evidence",
                ObservationOutcome.DIFF_INCOMPLETE,
            )
        return PageResponse(
            tuple(normalized),
            page.pages,
            page.total_count,
            page.complete,
            page.truncated,
            page.last_cursor,
            page.audits,
        )

    @staticmethod
    def _merged_state(
        response: EndpointResponse, proof: ControllerPusherProof
    ) -> EndpointResponse:
        raw = _required(
            response.data,
            {
                "id", "node_id", "number", "head", "base", "merged",
                "merge_commit_sha", "merged_at", "merged_by",
            },
            "merged-state",
        )
        if (
            raw["id"] != proof.pull_request_id
            or raw["node_id"] != proof.pull_request_node_id
            or raw["number"] != proof.pull_request_number
        ):
            raise _fail(
                "merged-state",
                "GitHub merge state differs from the authenticated pull request",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        if not isinstance(raw["merged"], bool):
            raise _fail("merged-state", "GitHub merged state is malformed")
        GitHubCandidateRESTReader._repository_side(
            raw["head"], side="head", proof=proof
        )
        GitHubCandidateRESTReader._repository_side(
            raw["base"], side="base", proof=proof
        )
        merged_by = raw["merged_by"]
        if merged_by is not None:
            actor = _required(
                merged_by, {"id", "node_id", "login"}, "merged-state.merged-by"
            )
            merged_by = {
                "id": _positive_int(actor["id"], "merged-state.merged-by"),
                "node_id": actor["node_id"],
                "login": actor["login"],
            }
        proof_fields = (raw["merge_commit_sha"], raw["merged_at"], merged_by)
        if (
            not raw["merged"] and any(value is not None for value in proof_fields)
        ):
            raise _fail(
                "merged-state",
                "unmerged GitHub pull request carries merge proof fields",
                ObservationOutcome.FIELD_UNKNOWN,
            )
        return EndpointResponse(
            {
                "merged": raw["merged"],
                "merge_commit_sha": raw["merge_commit_sha"],
                "merged_at": raw["merged_at"],
                "merged_by": merged_by,
            },
            response.audit,
            response.extra_audits,
        )

    def read_all(
        self,
        *,
        controller_pusher: ControllerPusherProof,
        object_evidence: Mapping[str, object],
    ) -> GitHubCandidateRESTSnapshot:
        repository, pull_target, refs_target = self._paths(controller_pusher)
        pull_request = self._pull_request(
            self.client.get_endpoint("pull-request", pull_target),
            controller_pusher,
        )
        head_response = self.client.get_endpoint(
            "refs", f"{refs_target}/{controller_pusher.head_ref}"
        )
        base_response = self.client.get_endpoint(
            "refs", f"{refs_target}/{controller_pusher.base_ref}"
        )
        refs = EndpointResponse(
            {
                "head": self._ref(
                    head_response,
                    name=controller_pusher.head_ref,
                    sha=controller_pusher.head_sha,
                    surface="refs.head",
                ),
                "base": self._ref(
                    base_response,
                    name=controller_pusher.base_ref,
                    sha=controller_pusher.base_sha,
                    surface="refs.base",
                ),
            },
            head_response.audit,
            (base_response.audit,),
        )
        changed_files = self._changed_files(
            self.client.get_pages("changed-files", f"{pull_target}/files"),
            object_evidence,
        )
        deployments = self.client.get_pages(
            "deployments",
            f"{repository}/deployments?sha={controller_pusher.head_sha}",
        )
        merged_state = self._merged_state(
            self.client.get_endpoint("merged-state", pull_target),
            controller_pusher,
        )
        return GitHubCandidateRESTSnapshot(
            pull_request, refs, changed_files, deployments, merged_state
        )
