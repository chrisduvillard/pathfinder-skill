from __future__ import annotations

import json
import sys
from pathlib import Path


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text())


def fail(message: str) -> int:
    print(json.dumps({"error": "cross_artifact", "message": message}))
    return 1


def main() -> int:
    root = Path(sys.argv[1])
    candidates = load(root, "03-candidates.json")
    verification = load(root, "03b-verification.json")
    binding = load(root, "06-goal-binding.json")
    run_log = load(root, "07-run-log.json")
    summary = load(root, "08-final-summary.json")
    mission_ids = {document["mission_id"] for document in (candidates, verification, binding, run_log, summary)}
    if len(mission_ids) != 1:
        return fail("mission_id mismatch across sidecars")
    candidate_ids = {item["candidate_id"] for item in candidates["candidates"]}
    verified_ids = {item["candidate_id"] for item in verification["results"]}
    if not verified_ids.issubset(candidate_ids):
        return fail("verification references an unknown candidate_id")
    if not set(binding["selected_candidate_ids"]).issubset(candidate_ids):
        return fail("Goal Binding references an unknown candidate_id")
    if run_log["binding_id"] != binding["binding_id"]:
        return fail("run log binding_id does not match Goal Binding")
    if summary["goals"][0]["goal_id"] != binding["goal_id"]:
        return fail("final summary goal_id does not match Goal Binding")
    if summary["goals"][0]["binding_status"] != run_log["binding_status"]:
        return fail("final summary binding_status does not match run log")
    if summary["final_state"] == "awaiting-review" and run_log["publication"] != "awaiting-review":
        return fail("awaiting-review summary lacks awaiting-review publication evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
