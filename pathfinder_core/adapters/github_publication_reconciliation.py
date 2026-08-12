from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from ..storage import canonical_sha256, read_json
from .github_graphql import (
    PULL_REQUEST_QUERY_SHA256,
    GraphQLPullRequestSnapshot,
)
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    RequestAudit,
)


_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")


def _fail(detail: str) -> GitHubObservationError:
    return GitHubObservationError(
        ObservationOutcome.FIELD_UNKNOWN,
        "publication-pusher",
        detail,
    )


def _time(value: object, detail: str) -> datetime:
    if not isinstance(value, str):
        raise _fail(detail)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(detail) from None
    if parsed.utcoffset() is None:
        raise _fail(detail)
    return parsed


@dataclass(frozen=True)
class ControllerPusherProof:
    """Exact controller actor projected from a durable publication receipt."""

    source: str
    last_pusher_id: int
    actor_node_id: str
    actor_login: str
    publication_receipt_id: str
    publication_receipt_sha256: str
    repository_id: int
    pull_request_id: int
    pull_request_node_id: str
    pull_request_number: int
    head_ref: str
    head_sha: str
    receipt_observed_at: str
    graphql_observed_at: str


class GitHubPublicationReconciler:
    """Bind an authenticated controller push to one current GraphQL PR view."""

    _schema_root = (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "publication"
    )

    @classmethod
    def _document(
        cls, label: str, document: object, hash_field: str
    ) -> Mapping[str, object]:
        if not isinstance(document, Mapping):
            raise _fail(f"publication {label} is not an object")
        try:
            Draft202012Validator(
                read_json(
                    cls._schema_root / f"publication-{label}.schema.json"
                ),
                format_checker=FormatChecker(),
            ).validate(document)
        except (SchemaError, ValidationError, KeyError, TypeError):
            raise _fail(
                f"publication {label} is malformed or incomplete"
            ) from None
        try:
            valid_hash = document[hash_field] == canonical_sha256(
                document, hash_field
            )
        except (KeyError, TypeError, ValueError):
            valid_hash = False
        if not valid_hash:
            raise _fail(f"publication {label} hash differs")
        return document

    @staticmethod
    def _graphql_times(
        snapshot: GraphQLPullRequestSnapshot,
    ) -> tuple[datetime, datetime, str]:
        if not isinstance(snapshot, GraphQLPullRequestSnapshot):
            raise _fail("GraphQL pull request snapshot is malformed")
        if snapshot.query_sha256 != PULL_REQUEST_QUERY_SHA256:
            raise _fail("GraphQL query binding differs")
        if not snapshot.requests:
            raise _fail("GraphQL request audit is missing")
        if any(not isinstance(audit, RequestAudit) for audit in snapshot.requests):
            raise _fail("GraphQL request audit is malformed")
        request_ids = [audit.request_id for audit in snapshot.requests]
        if (
            any(
                not isinstance(request_id, str)
                or _REQUEST_ID.fullmatch(request_id) is None
                for request_id in request_ids
            )
            or len(request_ids) != len(set(request_ids))
        ):
            raise _fail("GraphQL request audit is ambiguous")
        observations = [
            _time(audit.observed_at, "GraphQL observation time is malformed")
            for audit in snapshot.requests
        ]
        if observations != sorted(observations):
            raise _fail("GraphQL observation timeline is not ordered")
        return (
            observations[0],
            observations[-1],
            snapshot.requests[-1].observed_at,
        )

    @classmethod
    def reconcile(
        cls,
        *,
        publication_request: object,
        publication_receipt: object,
        graphql: GraphQLPullRequestSnapshot,
    ) -> ControllerPusherProof:
        request = cls._document(
            "request", publication_request, "request_sha256"
        )
        receipt = cls._document(
            "receipt", publication_receipt, "receipt_sha256"
        )
        graph_start, _graph_end, graph_time_text = cls._graphql_times(graphql)
        receipt_time = _time(
            receipt["observed_at"], "publication receipt time is malformed"
        )
        if graph_start < receipt_time:
            raise _fail("GraphQL pull request observation predates publication")

        repository = receipt["repository"]
        pull = receipt["pull_request"]
        push = receipt["head_push"]
        request_repository = request["repository"]
        request_candidate = request["candidate"]
        request_actor = request["publication_actor"]
        graph_repository = graphql.repository
        graph_pull = graphql.pull_request
        if not all(
            isinstance(value, Mapping)
            for value in (
                repository,
                pull,
                push,
                request_repository,
                request_candidate,
                request_actor,
                graph_repository,
                graph_pull,
            )
        ):
            raise _fail("publication or GraphQL identity is not an object")

        if (
            receipt["publication_request_id"]
            != request["publication_request_id"]
            or receipt["request_sha256"] != request["request_sha256"]
            or repository != request_repository
            or any(
                pull[key] != request_candidate[key]
                for key in ("head_ref", "head_sha", "base_ref", "base_sha")
            )
            or push
            != {
                "source": "authenticated-controller-publication",
                "actor_id": request_actor["actor_id"],
                "actor_node_id": request_actor["actor_node_id"],
                "login": request_actor["login"],
                "repository_id": request_repository["id"],
                "head_ref": request_candidate["head_ref"],
                "head_sha": request_candidate["head_sha"],
            }
        ):
            raise _fail("publication request and receipt identities differ")

        expected_mission = {
            key: request["mission"][key]
            for key in (
                "mission_id",
                "binding_id",
                "mission_authorization_id",
                "authorization_snapshot_sha256",
                "mission_state_sha256",
            )
        }
        expected_checks = sorted(
            (
                check["context"],
                check["app_id"],
                request_candidate["head_sha"],
            )
            for check in request["required_checks"]
        )
        observed_checks = sorted(
            (check["context"], check["app_id"], check["sha"])
            for check in receipt["checks"]["observations"]
        )
        suffix = str(request["publication_request_id"]).removeprefix(
            "publication_request_"
        )
        expected_url = (
            f"https://github.com/{request_repository['owner']}/"
            f"{request_repository['name']}/pull/{pull['number']}"
        )
        if (
            receipt["mission"] != expected_mission
            or receipt["diff"] != request_candidate["diff"]
            or observed_checks != expected_checks
            or receipt["checks"]["polls"] > request["max_check_polls"]
            or receipt["publication_receipt_id"]
            != f"publication_receipt_{suffix}"
            or pull["url"] != expected_url
        ):
            raise _fail("publication request and receipt bindings differ")

        expected_repository = {
            key: repository[key] for key in ("id", "node_id", "owner", "name")
        }
        if dict(graph_repository) != expected_repository:
            raise _fail("publication and GraphQL repository identities differ")
        exact_pull = {
            "id": pull["id"],
            "node_id": pull["node_id"],
            "number": pull["number"],
            "head_ref": pull["head_ref"],
            "head_sha": pull["head_sha"],
            "base_ref": pull["base_ref"],
            "base_sha": pull["base_sha"],
            "head_repository_id": repository["id"],
            "head_repository_node_id": repository["node_id"],
            "base_repository_id": repository["id"],
            "base_repository_node_id": repository["node_id"],
        }
        if any(graph_pull.get(key) != value for key, value in exact_pull.items()):
            raise _fail("publication and GraphQL pull request identities differ")
        if (
            push["repository_id"] != repository["id"]
            or push["head_ref"] != pull["head_ref"]
            or push["head_sha"] != pull["head_sha"]
        ):
            raise _fail("publication push and pull request identities differ")

        return ControllerPusherProof(
            source="authenticated-controller-publication",
            last_pusher_id=push["actor_id"],
            actor_node_id=push["actor_node_id"],
            actor_login=push["login"],
            publication_receipt_id=receipt["publication_receipt_id"],
            publication_receipt_sha256=receipt["receipt_sha256"],
            repository_id=repository["id"],
            pull_request_id=pull["id"],
            pull_request_node_id=pull["node_id"],
            pull_request_number=pull["number"],
            head_ref=pull["head_ref"],
            head_sha=pull["head_sha"],
            receipt_observed_at=receipt["observed_at"],
            graphql_observed_at=graph_time_text,
        )
