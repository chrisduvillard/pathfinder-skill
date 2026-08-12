from __future__ import annotations

import re
from datetime import datetime
from typing import Mapping, Sequence

from .github_get import GitHubGETClient
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)


_CONTEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/()@,+-]{0,99}")
_SHA = re.compile(r"[0-9a-f]{40}")
_RUN_STATUSES = {"queued", "in_progress", "completed"}
_RUN_CONCLUSIONS = {
    "success", "failure", "neutral", "cancelled", "skipped", "timed_out",
    "action_required", "stale", None,
}
_STATUS_STATES = {"pending", "success", "failure", "error"}
_PERMITTED_ACTOR_TYPES = {"User", "Bot", "Integration"}
_RUN_FIELDS = {
    "id", "node_id", "name", "head_sha", "external_id", "url",
    "html_url", "details_url", "status", "conclusion", "started_at",
    "completed_at", "output", "check_suite", "app", "pull_requests",
    "deployment",
}
_STATUS_FIELDS = {
    "url", "avatar_url", "id", "node_id", "state", "description",
    "target_url", "context", "created_at", "updated_at", "creator",
}
_COMBINED_STATUS_FIELDS = {
    "state", "statuses", "sha", "total_count", "repository", "commit_url",
    "url",
}


def _fail(surface: str, detail: str) -> GitHubObservationError:
    return GitHubObservationError(ObservationOutcome.FIELD_UNKNOWN, surface, detail)


def _positive_int(value: object, surface: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise _fail(surface, "GitHub check identity is malformed")
    return value


def _timestamp(value: object, surface: str, *, nullable: bool = False):
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise _fail(surface, "GitHub check timestamp is malformed")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(surface, "GitHub check timestamp is malformed") from None
    if parsed.utcoffset() is None:
        raise _fail(surface, "GitHub check timestamp has no UTC offset")
    return value


def _time_key(value: str, identity: int) -> tuple[datetime, int]:
    return datetime.fromisoformat(value.replace("Z", "+00:00")), identity


class GitHubCheckRunReader:
    """Walk suites first so GitHub's 1,000-suite shortcut cannot hide runs."""

    def __init__(self, client: GitHubGETClient):
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub check reads require an installation token")
        self.client = client

    def read_all(
        self,
        *,
        owner: str,
        name: str,
        sha: str,
        request_limit: int | None = None,
    ) -> PageResponse:
        limit = self.client.max_pages if request_limit is None else request_limit
        if not 1 <= limit <= self.client.max_pages:
            raise ValueError("GitHub check request limit is out of bounds")
        if (
            re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?",
                owner,
            ) is None
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) is None
            or re.fullmatch(r"[0-9a-f]{40}", sha) is None
        ):
            raise ValueError("invalid exact GitHub check collection identity")
        suites = self.client.get_pages(
            "check-runs",
            f"/repos/{owner}/{name}/commits/{sha}/check-suites",
            item_key="check_suites",
            total_key="total_count",
            page_limit=limit,
        )
        if not suites.complete or suites.truncated:
            return PageResponse(
                (), suites.pages, 0, False, True, suites.last_cursor,
                suites.audits,
            )
        suite_ids = []
        for index, suite in enumerate(suites.items):
            suite_id = suite.get("id")
            if (
                not isinstance(suite_id, int)
                or isinstance(suite_id, bool)
                or suite_id < 1
                or suite.get("head_sha") != sha
            ):
                raise GitHubObservationError(
                    ObservationOutcome.FIELD_UNKNOWN,
                    f"check-suites[{index}]",
                    "GitHub check suite identity or head SHA differs",
                )
            suite_ids.append(suite_id)
        if len(set(suite_ids)) != len(suite_ids):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN,
                "check-suites",
                "GitHub check suite identity is duplicated",
            )

        runs: list[Mapping[str, object]] = []
        audits = list(suites.audits)
        pages = suites.pages
        seen_run_ids = set()
        for suite_id in suite_ids:
            remaining = limit - pages
            if remaining < 1:
                return PageResponse(
                    tuple(runs), pages, len(runs), False, True, None,
                    tuple(audits),
                )
            page = self.client.get_pages(
                "check-runs",
                f"/repos/{owner}/{name}/check-suites/{suite_id}/check-runs",
                item_key="check_runs",
                total_key="total_count",
                page_limit=remaining,
            )
            pages += page.pages
            audits.extend(page.audits)
            for index, run in enumerate(page.items):
                run_id = run.get("id")
                suite = run.get("check_suite")
                if (
                    not isinstance(run_id, int)
                    or isinstance(run_id, bool)
                    or run_id < 1
                    or run_id in seen_run_ids
                    or not isinstance(suite, Mapping)
                    or suite.get("id") != suite_id
                    or run.get("head_sha") != sha
                ):
                    raise GitHubObservationError(
                        ObservationOutcome.FIELD_UNKNOWN,
                        f"check-runs[{suite_id}][{index}]",
                        "GitHub check run identity, suite, or head SHA differs",
                    )
                seen_run_ids.add(run_id)
                runs.append(run)
            if not page.complete or page.truncated:
                return PageResponse(
                    tuple(runs), pages, len(runs), False, True,
                    page.last_cursor, tuple(audits),
                )
        request_ids = [audit.request_id for audit in audits]
        if len(set(request_ids)) != len(request_ids):
            raise GitHubObservationError(
                ObservationOutcome.FIELD_UNKNOWN,
                "check-runs",
                "GitHub check collection reused a request id",
            )
        return PageResponse(
            tuple(runs), pages, len(runs), True, False, None, tuple(audits)
        )


class GitHubCheckEvidenceReader:
    """Project exact check runs and commit statuses into the observer contract."""

    def __init__(self, client: GitHubGETClient):
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub check evidence requires an installation token")
        self.client = client
        self.runs = GitHubCheckRunReader(client)

    @staticmethod
    def _requirements(
        values: Sequence[Mapping[str, object]],
    ) -> frozenset[tuple[str, int]]:
        requirements = []
        for index, value in enumerate(values):
            surface = f"required-checks[{index}]"
            if not isinstance(value, Mapping) or set(value) != {
                "context", "app_id",
            }:
                raise _fail(surface, "required check identity is not closed")
            context = value["context"]
            app_id = _positive_int(value["app_id"], surface)
            if not isinstance(context, str) or _CONTEXT.fullmatch(context) is None:
                raise _fail(surface, "required check context is malformed")
            requirements.append((context, app_id))
        if len(requirements) != len(set(requirements)):
            raise _fail("required-checks", "required check identity is duplicated")
        return frozenset(requirements)

    @staticmethod
    def _run(
        value: Mapping[str, object],
        index: int,
        *,
        sha: str,
        required: frozenset[tuple[str, int]],
    ) -> dict[str, object]:
        surface = f"check-runs[{index}]"
        needed = {
            "id", "name", "app", "head_sha", "check_suite", "status",
            "conclusion", "completed_at", "pull_requests",
        }
        if needed - value.keys() or set(value) - _RUN_FIELDS:
            raise _fail(surface, "GitHub check run fields are missing or unknown")
        run_id = _positive_int(value["id"], surface)
        name = value["name"]
        app = value["app"]
        status = value["status"]
        conclusion = value["conclusion"]
        completed_at = _timestamp(
            value["completed_at"], surface, nullable=True
        )
        if (
            not isinstance(name, str)
            or _CONTEXT.fullmatch(name) is None
            or value["head_sha"] != sha
            or not isinstance(app, Mapping)
            or not isinstance(value["check_suite"], Mapping)
            or not isinstance(value["pull_requests"], list)
            or status not in _RUN_STATUSES
            or conclusion not in _RUN_CONCLUSIONS
        ):
            raise _fail(surface, "GitHub check run identity or state is unknown")
        app_id = _positive_int(app.get("id"), f"{surface}.app")
        slug = app.get("slug")
        if (
            not isinstance(slug, str)
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,98}[A-Za-z0-9])?", slug)
            is None
            or (status == "completed") != (completed_at is not None)
            or (status == "completed") != (conclusion is not None)
        ):
            raise _fail(surface, "GitHub check App or terminal state is unknown")
        return {
            "id": run_id,
            "name": name,
            "app": {"id": app_id},
            "head_sha": sha,
            "required": (name, app_id) in required,
            "status": status,
            "conclusion": conclusion,
            "completed_at": completed_at,
        }

    @staticmethod
    def _status(
        value: Mapping[str, object],
        index: int,
        *,
        sha: str,
        required_contexts: frozenset[str],
    ) -> dict[str, object]:
        surface = f"commit-statuses[{index}]"
        needed = {"id", "context", "creator", "state", "updated_at"}
        if needed - value.keys() or set(value) - _STATUS_FIELDS:
            raise _fail(surface, "GitHub commit status fields are missing or unknown")
        status_id = _positive_int(value["id"], surface)
        context = value["context"]
        creator = value["creator"]
        if (
            not isinstance(context, str)
            or _CONTEXT.fullmatch(context) is None
            or value["state"] not in _STATUS_STATES
            or not isinstance(creator, Mapping)
        ):
            raise _fail(surface, "GitHub commit status identity or state is unknown")
        creator_id = _positive_int(creator.get("id"), f"{surface}.creator")
        creator_type = creator.get("type")
        if creator_type not in _PERMITTED_ACTOR_TYPES:
            raise _fail(surface, "GitHub commit status creator type is unknown")
        return {
            "id": status_id,
            "context": context,
            "creator": {"id": creator_id, "type": creator_type},
            "sha": sha,
            "required": context in required_contexts,
            "state": value["state"],
            "updated_at": _timestamp(value["updated_at"], surface),
        }

    def _statuses(
        self,
        *,
        owner: str,
        name: str,
        repository_id: int,
        sha: str,
        required_contexts: frozenset[str],
        request_limit: int,
    ) -> PageResponse:
        combined = self.client.get_json(
            "commit-statuses",
            f"/repos/{owner}/{name}/commits/{sha}/status?per_page=1",
        )
        payload = combined.data
        if (
            not isinstance(payload, Mapping)
            or set(payload) != _COMBINED_STATUS_FIELDS
            or not isinstance(payload.get("statuses"), list)
        ):
            raise GitHubObservationError(
                ObservationOutcome.MALFORMED_RESPONSE,
                "commit-statuses",
                "GitHub combined status envelope is malformed",
            )
        total = payload.get("total_count")
        state = payload.get("state")
        repository = payload.get("repository")
        repository_owner = (
            repository.get("owner") if isinstance(repository, Mapping) else None
        )
        if (
            not isinstance(total, int)
            or isinstance(total, bool)
            or total < 0
            or state not in _STATUS_STATES
            or payload.get("sha") != sha
            or not isinstance(repository, Mapping)
            or repository.get("id") != repository_id
            or repository.get("name") != name
            or repository.get("full_name") != f"{owner}/{name}"
            or not isinstance(repository_owner, Mapping)
            or repository_owner.get("login") != owner
        ):
            raise _fail(
                "commit-statuses",
                "GitHub combined status identity or state differs",
            )
        if request_limit < 2:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "commit-statuses",
                "GitHub status history has no remaining request budget",
            )
        history = self.client.get_pages(
            "commit-statuses",
            f"/repos/{owner}/{name}/commits/{sha}/statuses",
            page_limit=request_limit - 1,
        )
        if not history.complete or history.truncated:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "commit-statuses",
                "GitHub status history pagination is incomplete",
            )
        statuses = []
        seen_ids = set()
        latest = {}
        for item in history.items:
            if not isinstance(item, Mapping):
                raise GitHubObservationError(
                    ObservationOutcome.MALFORMED_RESPONSE,
                    "commit-statuses",
                    "GitHub commit status item is not an object",
                )
            normalized = self._status(
                item, len(statuses), sha=sha,
                required_contexts=required_contexts,
            )
            if normalized["id"] in seen_ids:
                raise _fail(
                    "commit-statuses", "GitHub commit status id is duplicated"
                )
            seen_ids.add(normalized["id"])
            statuses.append(normalized)
            previous = latest.get(normalized["context"])
            key = _time_key(normalized["updated_at"], normalized["id"])
            if previous is None or key > _time_key(
                previous["updated_at"], previous["id"]
            ):
                latest[normalized["context"]] = normalized
        current_statuses = sorted(
            latest.values(), key=lambda item: (item["context"], item["id"])
        )
        states = {item["state"] for item in current_statuses}
        derived_state = (
            "failure"
            if states & {"error", "failure"}
            else "pending"
            if not states or "pending" in states
            else "success"
        )
        if total != len(current_statuses) or state != derived_state:
            raise _fail(
                "commit-statuses",
                "GitHub combined status differs from its complete status history",
            )
        audits = (combined.audit, *history.audits)
        request_ids = [audit.request_id for audit in audits]
        if len(request_ids) != len(set(request_ids)):
            raise _fail(
                "commit-statuses", "GitHub status request id is duplicated"
            )
        return PageResponse(
            tuple(current_statuses), 1 + history.pages, len(current_statuses),
            True, False, None, audits,
        )

    def read_all(
        self,
        *,
        owner: str,
        name: str,
        repository_id: int,
        sha: str,
        required_checks: Sequence[Mapping[str, object]],
    ) -> tuple[PageResponse, PageResponse]:
        if (
            not isinstance(repository_id, int)
            or isinstance(repository_id, bool)
            or repository_id < 1
            or _SHA.fullmatch(sha) is None
            or self.client.max_pages < 4
        ):
            raise ValueError("invalid exact GitHub check evidence identity or budget")
        required = self._requirements(required_checks)
        check_page = self.runs.read_all(
            owner=owner, name=name, sha=sha,
            request_limit=self.client.max_pages - 2,
        )
        if not check_page.complete or check_page.truncated:
            raise GitHubObservationError(
                ObservationOutcome.PAGINATION_INCOMPLETE,
                "check-runs",
                "GitHub check run collection exhausted the request budget",
            )
        normalized_runs = []
        seen_runs = set()
        for index, item in enumerate(check_page.items):
            normalized = self._run(
                item, index, sha=sha, required=required
            )
            identity = (normalized["name"], normalized["app"]["id"])
            if identity in seen_runs:
                raise _fail(
                    "check-runs", "GitHub current check identity is duplicated"
                )
            seen_runs.add(identity)
            normalized_runs.append(normalized)
        normalized_check_page = PageResponse(
            tuple(normalized_runs), check_page.pages, check_page.total_count,
            True, False, None, check_page.audits,
        )
        remaining = self.client.max_pages - check_page.pages
        status_page = self._statuses(
            owner=owner,
            name=name,
            repository_id=repository_id,
            sha=sha,
            required_contexts=frozenset(context for context, _app in required),
            request_limit=remaining,
        )
        request_ids = [
            audit.request_id
            for audit in (*normalized_check_page.audits, *status_page.audits)
        ]
        if len(request_ids) != len(set(request_ids)):
            raise _fail("checks", "GitHub check evidence reused a request id")
        return normalized_check_page, status_page
