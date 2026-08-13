#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import copy
import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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


@dataclass(frozen=True)
class Snapshot:
    evidence: dict


@dataclass(frozen=True)
class Collection:
    snapshot: Snapshot
    envelope: dict


class Collector:
    def __init__(self):
        self.calls = []

    def collect_from_verified_host(self, **values):
        self.calls.append(copy.deepcopy(values["publication_records"]))
        return Collection(
            Snapshot({"evidence_id": "merge_evidence_contract1"}),
            {"authenticated": True},
        )


def publication_controller(root, request, backend, times):
    from pathfinder_core.adapters.github import GitHubPublisher
    from pathfinder_core.publication_controller import (
        PublicationController,
        VerifiedPublicationEnvelope,
    )
    from pathfinder_core.publication_journal import PublicationJournal
    from tests.core.test_publication_controller import EnvelopeReader

    envelope = VerifiedPublicationEnvelope(
        "publication_envelope_example1",
        "authenticated-host-storage",
        datetime.fromisoformat("2026-08-11T12:05:00+00:00").isoformat(),
        request,
    )
    return PublicationController(
        PublicationJournal(root),
        EnvelopeReader(envelope),
        GitHubPublisher(backend),
        clock=lambda: next(times),
    )


def orchestrator(publication, collector):
    from pathfinder_core.trusted_host_publication import (
        TrustedHostPublicationEvidenceController,
    )

    return TrustedHostPublicationEvidenceController(
        publication=publication,
        collector=collector,
        collection_inputs=object(),
        policy_backend=object(),
    )


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
    return None


def constructor_calls(tree, *, module_name, symbol):
    aliases = {symbol}
    module_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.endswith(module_name):
                for imported in node.names:
                    if imported.name == symbol:
                        aliases.add(imported.asname or imported.name)
            if module == "pathfinder_core":
                for imported in node.names:
                    if imported.name == module_name:
                        module_aliases.add(imported.asname or imported.name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name.endswith(module_name):
                    module_aliases.add(imported.asname or imported.name)

    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted_name(node.func)
        if not name:
            continue
        direct = name in aliases
        qualified = name.endswith(f".{symbol}") and (
            module_name in name
            or name.rsplit(".", 1)[0] in module_aliases
        )
        if direct or qualified:
            lines.append(node.lineno)
    return lines


def attribute_calls(tree, names):
    return [
        (node.func.attr, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in names
    ]

def main() -> int:
    expected = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))

    from pathfinder_core.adapters.github_evidence_collector import (
        GitHubObservationError,
    )
    from pathfinder_core.storage import canonical_sha256
    from tests.adapters.test_github_evidence_collector import (
        GitHubAuthenticatedEvidenceCollectorTests,
        InputProvider as VerifiedInputProvider,
    )
    from tests.core.test_publication_controller import ExactBackend

    contracts = load(
        root / "tests/contracts/fixtures/publication-controller-contracts.json"
    )
    request = contracts["request"]
    records = {
        "state": "awaiting-review",
        "disposition": "awaiting-review",
        "request": contracts["request"],
        "dispatch": contracts["dispatch"],
        "receipt": contracts["receipt"],
    }
    # Exercise the real collector control flow with deterministic reader/store
    # fakes. This proves both journal-before-provider and exact-input-before-read
    # ordering instead of testing the predicates out of context.
    successful = GitHubAuthenticatedEvidenceCollectorTests()
    successful.setUp()
    inputs = successful.inputs()
    provider = VerifiedInputProvider(inputs["input_envelope"])
    result = successful.collector().collect_from_verified_host(
        policy_backend=inputs["policy_backend"],
        input_provider=provider,
        publication_records=records,
    )
    require(len(provider.calls) == 1, "terminal journal did not request one host input")
    require(
        result.snapshot.evidence["evidence_id"]
        == successful.helper.context["evidence_id"],
        "terminal journal did not reach evidence collection",
    )

    malformed_case = GitHubAuthenticatedEvidenceCollectorTests()
    malformed_case.setUp()
    malformed_inputs = malformed_case.inputs()
    malformed_provider = VerifiedInputProvider(
        malformed_inputs["input_envelope"]
    )
    malformed = {
        "state": "awaiting-review",
        "disposition": "awaiting-review",
        "request": copy.deepcopy(malformed_case.helper.publication_request),
        "dispatch": copy.deepcopy(malformed_case.dispatch),
        "receipt": copy.deepcopy(malformed_case.helper.publication_receipt),
    }
    malformed["request"]["request_sha256"] = "0" * 64
    try:
        malformed_case.collector().collect_from_verified_host(
            policy_backend=malformed_inputs["policy_backend"],
            input_provider=malformed_provider,
            publication_records=malformed,
        )
    except GitHubObservationError:
        pass
    else:
        raise ValueError("malformed journal reached the host input provider")
    require(
        malformed_provider.calls == [],
        "malformed journal requested host input",
    )
    require(
        malformed_case.identity.verify_observer.call_count == 0
        and malformed_case.graphql.read_pull_request.call_count == 0
        and malformed_case.candidate.calls == [],
        "malformed journal reached evidence readers",
    )

    drift_case = GitHubAuthenticatedEvidenceCollectorTests()
    drift_case.setUp()
    drift_inputs = drift_case.inputs()
    drift_provider = VerifiedInputProvider(drift_inputs["input_envelope"])
    changed = {
        "state": "awaiting-review",
        "disposition": "awaiting-review",
        "request": copy.deepcopy(drift_case.helper.publication_request),
        "dispatch": copy.deepcopy(drift_case.dispatch),
        "receipt": copy.deepcopy(drift_case.helper.publication_receipt),
    }
    changed["receipt"]["reused"] = not changed["receipt"]["reused"]
    changed["receipt"]["receipt_sha256"] = canonical_sha256(
        changed["receipt"], "receipt_sha256"
    )
    try:
        drift_case.collector().collect_from_verified_host(
            policy_backend=drift_inputs["policy_backend"],
            input_provider=drift_provider,
            publication_records=changed,
        )
    except GitHubObservationError:
        pass
    else:
        raise ValueError("changed publication receipt bypassed exact input binding")
    require(
        len(drift_provider.calls) == 1
        and len(drift_case.store.input_calls) == 1,
        "changed publication receipt did not reach authenticated input binding",
    )
    require(
        drift_case.identity.verify_observer.call_count == 0
        and drift_case.identity.verify_merge_actor.call_count == 0
        and drift_case.graphql.read_pull_request.call_count == 0
        and drift_case.reviews.read_all.call_count == 0
        and drift_case.checks.read_all.call_count == 0
        and drift_case.candidate.calls == []
        and drift_case.ownership.calls == []
        and drift_case.store.calls == [],
        "changed publication receipt reached downstream evidence reads",
    )

    started = datetime.fromisoformat("2026-08-11T12:05:00+00:00")
    observed = datetime.fromisoformat("2026-08-11T12:06:00+00:00")
    with tempfile.TemporaryDirectory() as directory:
        backend = ExactBackend()
        collector = Collector()
        controller = orchestrator(
            publication_controller(
                Path(directory), request, backend, iter((started, observed))
            ),
            collector,
        )
        first = controller.publish_and_collect(
            request["publication_request_id"],
            "publication_envelope_example1",
        )
        second = controller.publish_and_collect(
            request["publication_request_id"], "unused-on-replay"
        )
    require(first.state == expected["terminal_state"], "terminal state drift")
    require(first.state == second.state, "terminal replay disposition drift")
    require(
        {"push": backend.pushes, "create": backend.creates}
        == expected["replay_effect_counts"],
        "terminal replay repeated a remote publication effect",
    )
    require(
        len(collector.calls) == expected["replay_collection_calls"],
        "terminal replay collection count drift",
    )

    with tempfile.TemporaryDirectory() as directory:
        backend = ExactBackend(lose_create_response=True)
        collector = Collector()
        controller = orchestrator(
            publication_controller(
                Path(directory), request, backend, iter((started, observed))
            ),
            collector,
        )
        request_id = request["publication_request_id"]
        try:
            controller.publish_and_collect(
                request_id, "publication_envelope_example1"
            )
        except RuntimeError as error:
            require(
                "lost create response" in str(error),
                "lost response failed for the wrong reason",
            )
        else:
            raise ValueError("lost response unexpectedly returned a disposition")
        pending = controller.publish_and_collect(request_id, "unused-on-replay")
        recovered = controller.reconcile_and_collect(request_id)
    require(
        pending.state == "reconcile-required"
        and recovered.state == expected["terminal_state"],
        "lost response did not require read-only reconciliation",
    )
    require(
        {"push": backend.pushes, "create": backend.creates}
        == expected["lost_response_effect_counts"],
        "lost-response recovery repeated a remote publication effect",
    )
    require(
        len(collector.calls) == expected["lost_response_collection_calls"],
        "lost-response collection count drift",
    )

    sources = {}
    trees = {}
    for path in (root / "pathfinder_core").rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        sources[relative] = path.read_text()
        trees[relative] = ast.parse(sources[relative], filename=relative)

    callers = []
    for relative, tree in trees.items():
        if relative == "pathfinder_core/trusted_host_publication.py":
            continue
        for line in constructor_calls(
            tree,
            module_name="trusted_host_publication",
            symbol="TrustedHostPublicationEvidenceController",
        ):
            callers.append(f"{relative}:{line}")
    require(
        len(callers) == expected["production_orchestrator_callers"],
        f"zero-merge orchestrator gained a production caller: {callers}",
    )

    executor_callers = []
    for relative, tree in trees.items():
        if relative == "pathfinder_core/merge_executor.py":
            continue
        for line in constructor_calls(
            tree,
            module_name="merge_executor",
            symbol="MergeExecutor",
        ):
            executor_callers.append(f"{relative}:{line}")
    require(
        executor_callers == [],
        f"merge executor gained a packaged caller: {executor_callers}",
    )

    unexpected_merge_calls = []
    for relative, tree in trees.items():
        if relative == "pathfinder_core/merge_executor.py":
            continue
        for name, line in attribute_calls(tree, {"merge"}):
            unexpected_merge_calls.append(f"{relative}:{line}:{name}")
    require(
        unexpected_merge_calls == [],
        f"package gained a merge sink outside the isolated executor: {unexpected_merge_calls}",
    )

    enabled_routes = {
        "pathfinder_core/__main__.py",
        "pathfinder_core/mission_host.py",
        "pathfinder_core/goal_pack.py",
        "pathfinder_core/adapters/github.py",
        "pathfinder_core/merge_status.py",
    }
    forbidden_route_calls = []
    for relative in enabled_routes:
        for name, line in attribute_calls(
            trees[relative],
            {
                "execute",
                "merge",
                "publish_and_collect",
                "reconcile_and_collect",
                "collect_from_verified_host",
            },
        ):
            forbidden_route_calls.append(f"{relative}:{line}:{name}")
    require(
        forbidden_route_calls == [],
        f"enabled route gained publication or merge execution: {forbidden_route_calls}",
    )

    from pathfinder_core.__main__ import _parser

    parser = _parser()
    top_level = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    require(
        "merge" in top_level.choices,
        "merge observation command disappeared from the route map",
    )
    merge_commands = next(
        action
        for action in top_level.choices["merge"]._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    require(
        set(merge_commands.choices) == {"status", "evaluate"},
        "merge route map gained an execution command",
    )

    source = sources["pathfinder_core/trusted_host_publication.py"]
    for forbidden in (
        "os.environ",
        "subprocess",
        "GitHubMergeCredential(",
        "MergeExecutor",
        "GitHubMergeBackend",
        "def merge(",
        "def execute(",
    ):
        require(forbidden not in source, f"orchestrator gained forbidden surface: {forbidden}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, IndexError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
