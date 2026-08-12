#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def load(path: Path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class Backend:
    def __init__(self, pull_request, check_state):
        self.pull_request = pull_request
        self.check_state_value = check_state
        self.counts = {"find": 0, "push": 0, "create": 0, "check": 0}

    def find_pull_request(self, head, base, mission_id):
        del head, base, mission_id
        self.counts["find"] += 1
        return None

    def push(self, branch):
        del branch
        self.counts["push"] += 1

    def create_pull_request(self, head, base, mission_id, title, body):
        del head, base, mission_id, title, body
        self.counts["create"] += 1
        return self.pull_request

    def check_state(self, pull_request):
        del pull_request
        self.counts["check"] += 1
        return self.check_state_value


class Envelopes:
    def __init__(self, envelope):
        self.envelope = envelope
        self.calls = 0

    def read_fresh_verified(self, envelope_id, *, now):
        del envelope_id, now
        self.calls += 1
        return self.envelope


def main() -> int:
    expected = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))

    from pathfinder_core.adapters.github import (
        CheckState,
        GitHubPublisher,
        PullRequest,
        PullRequestIdentity,
    )
    from pathfinder_core.publication_controller import (
        PublicationController,
        VerifiedPublicationEnvelope,
    )
    from pathfinder_core.publication_journal import PublicationJournal

    contracts = load(
        root / "tests/contracts/fixtures/publication-controller-contracts.json"
    )
    request = contracts["request"]
    for name in ("request", "dispatch", "receipt"):
        schema = load(
            root / f"schemas/publication/publication-{name}.schema.json"
        )
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(contracts[name])

    require(
        request["schema_version"] == expected["request_schema_version"],
        "publication request schema version drift",
    )
    identity = expected["pull_request"]
    pull_request = PullRequest(
        "pr_example1",
        "https://github.com/example-owner/example-repo/pull/72",
        request["candidate"]["head_ref"],
        request["candidate"]["base_ref"],
        request["mission"]["mission_id"],
        PullRequestIdentity(
            request["repository"]["id"],
            request["repository"]["node_id"],
            identity["id"],
            identity["node_id"],
            identity["number"],
            identity["head_sha"],
            identity["base_sha"],
        ),
    )
    backend = Backend(pull_request, CheckState.SUCCESS)
    started = datetime.fromisoformat("2026-08-11T12:05:00+00:00")
    observed = datetime.fromisoformat("2026-08-11T12:06:00+00:00")
    envelope = VerifiedPublicationEnvelope(
        "publication_envelope_example1",
        "authenticated-host-storage",
        started.isoformat(),
        request,
    )
    envelopes = Envelopes(envelope)
    with tempfile.TemporaryDirectory() as directory:
        controller = PublicationController(
            PublicationJournal(Path(directory)),
            envelopes,
            GitHubPublisher(backend),
            clock=lambda: observed,
        )
        first = controller.publish(
            request["publication_request_id"],
            envelope.envelope_id,
            now=started,
        )
        second = controller.publish(
            request["publication_request_id"],
            "unused-on-replay",
            now=started,
        )

    require(first == second, "terminal publication receipt did not replay exactly")
    require(first.state == expected["state"], "publication disposition drift")
    require(
        first.receipt["schema_version"] == expected["receipt_schema_version"]
        and first.receipt["source"] == expected["source"],
        "authenticated publication receipt contract drift",
    )
    require(
        all(
            first.receipt["pull_request"][key] == value
            for key, value in identity.items()
        ),
        "publication receipt exact PR identity drift",
    )
    require(
        backend.counts == expected["first_call_counts"],
        "publication replay performed additional backend calls",
    )
    callers = []
    for path in (root / "pathfinder_core").rglob("*.py"):
        if path.name == "publication_controller.py":
            continue
        if "PublicationController(" in path.read_text():
            callers.append(path)
    for folder in ("scripts", "skills"):
        for path in (root / folder).rglob("*"):
            if path.is_file() and "PublicationController(" in path.read_text(
                errors="ignore"
            ):
                callers.append(path)
    require(
        len(callers) == expected["production_controller_callers"],
        "publication controller gained a production caller",
    )
    require(envelopes.calls == 1, "terminal replay reread the host envelope")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, IndexError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
