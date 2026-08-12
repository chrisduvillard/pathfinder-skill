#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    document = load(Path(sys.argv[1]))
    root = Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))
    authority = load(
        root / "tests/contracts/fixtures/publication-contracts.json"
    )
    journal = load(
        root / "tests/contracts/fixtures/publication-journal-contracts.json"
    )
    observer = load(
        root / "tests/adapters/fixtures/github-merge-observer.json"
    )

    schema_documents = (
        ("policy", authority["policy"]),
        ("authorization", authority["authorization"]),
        ("evidence", journal["initial_evidence"]),
        ("evidence", journal["evidence"]),
        ("readiness-proof", journal["readiness_proof"]),
        ("intent", journal["intent"]),
        ("result", journal["result"]),
    )
    for name, value in schema_documents:
        schema = load(root / f"schemas/publication/merge-{name}.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(value)
    for value, field in (
        (authority["policy"], "policy_sha256"),
        (authority["authorization"], "authorization_sha256"),
        (journal["initial_evidence"], "evidence_sha256"),
        (journal["evidence"], "evidence_sha256"),
        (journal["readiness_proof"], "proof_sha256"),
        (journal["intent"], "intent_sha256"),
        (journal["result"], "result_sha256"),
    ):
        require(
            value[field] == canonical_document_sha256(value, field),
            f"{field} differs from the canonical document hash",
        )

    evidence = journal["evidence"]
    authorization = authority["authorization"]
    require(
        evidence["repository"]["merge_methods"]
        == document["repository"]["merge_methods"],
        "normalized repository merge methods differ from the eval expectation",
    )
    permission = document["permission_response"]
    raw_review = observer["responses"]["reviews"]["items"][0]
    require(
        permission["requested_reviewer"] == permission["user"]
        == raw_review["repository_permission"]["user"],
        "permission response user does not match the requested reviewer",
    )
    require(
        permission["permission"] in {"write", "admin"}
        and evidence["reviews"][0]["repository_permission"]
        == permission["permission"]
        == raw_review["repository_permission"]["permission"],
        "reviewer lacks normalized write/admin permission",
    )
    require(
        evidence["mergeability"]["review_decision"]
        == document["pull_request"]["review_decision"]
        == "APPROVED",
        "closed GitHub review decision is not approved",
    )
    require(
        evidence["repository"]["merge_methods"]["squash"] is True
        and any(
            rule["rule_type"] == "pull_request"
            and "squash" in rule["allowed_merge_methods"]
            for rule in evidence["active_rules"]
        ),
        "repository and active rule do not both allow squash",
    )
    require(
        all(
            source["active_rules_sha256"]
            == canonical_sha256(sorted(
                (
                    {
                        "rule_type": rule["rule_type"],
                        "parameters_sha256": rule["parameters_sha256"],
                    }
                    for rule in evidence["active_rules"]
                    if rule["ruleset_id"] == source["id"]
                ),
                key=lambda item: item["rule_type"],
            ))
            for source in evidence["source_rulesets"]
        ),
        "source and active rule semantic hashes differ",
    )
    observed_pull = {
        key: evidence["pull_request"][key]
        for key in authorization["candidate"]["pull_request"]
    }
    require(
        observed_pull == authorization["candidate"]["pull_request"],
        "observed pull request differs from the authenticated candidate",
    )
    require(
        {
            "diff_sha256": evidence["diff"]["diff_sha256"],
            "changed_files_sha256": evidence["diff"]["changed_files_sha256"],
            "object_evidence_sha256": evidence["diff"]["object_evidence"][
                "files_sha256"
            ],
        }
        == authorization["candidate"]["diff"],
        "observed diff differs from the authenticated candidate",
    )
    require(
        evidence["checks"][0]["creator_actor_type"] == "Integration"
        and evidence["checks"][0]["creator_actor_id"]
        == evidence["checks"][0]["app_id"],
        "check creator identity is absent or inconsistent",
    )
    require(
        evidence["observation"]["policy_read"]["source"]
        == "host-policy-store"
        and evidence["observation"]["policy_read"]["receipt_id"].startswith(
            "policy_read_"
        ),
        "host policy read receipt is absent",
    )
    readiness = journal["readiness_proof"]
    require(
        journal["intent"]["bindings"]["readiness_proof_sha256"]
        == journal["result"]["binding"]["readiness_proof_sha256"]
        == readiness["proof_sha256"],
        "intent/result do not bind the readiness proof",
    )
    require(
        journal["intent"]["bindings"]["initial_evidence_sha256"]
        == readiness["initial_snapshot"]["evidence_sha256"]
        and journal["intent"]["bindings"]["reread_evidence_sha256"]
        == readiness["reread_snapshot"]["evidence_sha256"]
        == evidence["evidence_sha256"],
        "intent does not bind both readiness snapshots",
    )

    from pathfinder_core.adapters.github_merge_observer import (
        GitHubMergeObserver,
        ObservationOutcome,
    )
    from pathfinder_core.merge_policy import MergePolicyEvaluator
    from pathfinder_core.protected_surfaces import ProtectedSurfaceRegistry
    from tests.adapters.test_github_merge_observer import FixtureObservationBackend

    observation = GitHubMergeObserver(
        FixtureObservationBackend(observer["responses"])
    ).observe(bindings=evidence["bindings"], **observer["context"])
    require(
        observation.outcome is ObservationOutcome.OBSERVED,
        "actual observer rejected the complete fixture",
    )
    require(
        observation.evidence["mergeability"]["review_decision"] == "APPROVED"
        and observation.evidence["reviews"][0]["repository_permission"]
        in {"write", "admin"}
        and observation.evidence["checks"][0]["creator_actor_type"]
        == "Integration",
        "actual observer omitted required review/check provenance",
    )
    require(
        observation.evidence["source_rulesets"][0]["bypass_actor_keys"]
        == [document["rules"]["bypass_actor"]["normalized_key"]]
        and observer["responses"]["bypass-actors"]["items"][0]
        == {
            "ruleset_id": 7001,
            "actor_type": document["rules"]["bypass_actor"]["actor_type"],
            "actor_id": document["rules"]["bypass_actor"]["actor_id"],
            "bypass_mode": document["rules"]["bypass_actor"]["bypass_mode"],
        },
        "actual observer omitted ruleset bypass actor mode",
    )

    evaluator = MergePolicyEvaluator()
    single = evaluator.evaluate(
        authority["policy"],
        authorization,
        ProtectedSurfaceRegistry.load().to_document(),
        evidence,
        now=datetime.fromisoformat("2026-08-11T12:08:30+00:00"),
    )
    require(single.eligible, "actual pure evaluator rejected the current fixture")
    require(not single.intent_ready, "single-snapshot verdict became intent-ready")
    evaluation = evaluator.evaluate_reread(
        authority["policy"],
        authorization,
        ProtectedSurfaceRegistry.load().to_document(),
        journal["initial_evidence"],
        evidence,
        now=datetime.fromisoformat("2026-08-11T12:08:30+00:00"),
    )
    require(
        evaluation.intent_ready and evaluation.proof is not None,
        "actual two-snapshot evaluator rejected the schema-valid fixture",
    )
    require(
        evaluation.proof.to_document() == readiness,
        "journal readiness proof differs from actual evaluator replay",
    )
    return 0


def load(path: Path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)


def canonical_sha256(value) -> str:
    import hashlib

    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def canonical_document_sha256(value, field: str) -> str:
    return canonical_sha256({key: item for key, item in value.items() if key != field})


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, IndexError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
