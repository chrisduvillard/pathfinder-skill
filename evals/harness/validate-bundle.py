from __future__ import annotations

import json
import sys
from pathlib import Path


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate key: {key}")
        value[key] = item
    return value


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(), object_pairs_hook=unique_pairs)


def fail(message: str) -> int:
    print(json.dumps({"error": "cross_artifact", "message": message}))
    return 1


def verification_error(candidates: dict, verification: dict) -> str | None:
    if candidates["mission_id"] != verification["mission_id"]:
        return "mission_id mismatch across candidate and verification sidecars"
    candidate_ids = [item["candidate_id"] for item in candidates["candidates"]]
    if len(candidate_ids) != len(set(candidate_ids)):
        return "duplicate candidate_id in candidates sidecar"
    verified_ids = [item["candidate_id"] for item in verification["results"]]
    if len(verified_ids) != len(set(verified_ids)):
        return "duplicate candidate_id in verification sidecar"
    if not set(verified_ids).issubset(candidate_ids):
        return "verification references an unknown candidate_id"
    return None


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(json.dumps({
            "error": "usage",
            "message": "validate-bundle.py ROOT [--verification-results]",
        }))
        return 2
    root = Path(sys.argv[1])
    try:
        candidates = load(root, "03-candidates.json")
        verification = load(root, "03b-verification.json")
        error = verification_error(candidates, verification)
        if error:
            return fail(error)
        if len(sys.argv) == 3:
            if sys.argv[2] != "--verification-results":
                print(json.dumps({"error": "usage", "message": "unknown option"}))
                return 2
            for result in verification["results"]:
                print("\t".join((result["candidate_id"], result["verdict"], result["final_grade"])))
            return 0
        binding = load(root, "06-goal-binding.json")
        run_log = load(root, "07-run-log.json")
        summary = load(root, "08-final-summary.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"error": "invalid_json", "message": str(error)}))
        return 1
    mission_ids = {
        document["mission_id"]
        for document in (candidates, verification, binding, run_log, summary)
    }
    if len(mission_ids) != 1:
        return fail("mission_id mismatch across sidecars")
    candidate_ids = {item["candidate_id"] for item in candidates["candidates"]}
    if not set(binding["selected_candidate_ids"]).issubset(candidate_ids):
        return fail("Goal Binding references an unknown candidate_id")
    rejected_ids = {
        item["candidate_id"]
        for item in verification["results"]
        if item["verdict"] == "rejected"
    }
    if rejected_ids.intersection(binding["selected_candidate_ids"]):
        return fail("Goal Binding selects a rejected candidate_id")
    if run_log["binding_id"] != binding["binding_id"]:
        return fail("run log binding_id does not match Goal Binding")
    goal = summary["goals"][0]
    if goal["goal_id"] != binding["goal_id"]:
        return fail("final summary goal_id does not match Goal Binding")
    if goal["binding_status"] != run_log["binding_status"]:
        return fail("final summary binding_status does not match run log")
    if goal["verification"] != run_log["verification"]:
        return fail("final summary verification does not match run log")
    if summary["final_state"] != goal["disposition"]:
        return fail("final summary state does not match Goal disposition")
    if summary["final_state"] == "awaiting-review" and run_log["publication"] != "awaiting-review":
        return fail("awaiting-review summary lacks awaiting-review publication evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
