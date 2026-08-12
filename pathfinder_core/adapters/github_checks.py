from __future__ import annotations

import re
from typing import Mapping

from .github_get import GitHubGETClient
from .github_merge_observer import (
    GitHubObservationError,
    ObservationOutcome,
    PageResponse,
)


class GitHubCheckRunReader:
    """Walk suites first so GitHub's 1,000-suite shortcut cannot hide runs."""

    def __init__(self, client: GitHubGETClient):
        if client.credential.kind != "installation-token":
            raise ValueError("GitHub check reads require an installation token")
        self.client = client

    def read_all(self, *, owner: str, name: str, sha: str) -> PageResponse:
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
            remaining = self.client.max_pages - pages
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
