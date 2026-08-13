from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def load(path: Path) -> dict:
    def unique(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise ValueError(f"duplicate key: {key}")
            document[key] = value
        return document

    return json.loads(path.read_text(), object_pairs_hook=unique)


def fail(message: str) -> int:
    print(json.dumps({"error": "prompt_replay", "message": message}))
    return 1


def facts(document: str) -> dict[str, str]:
    result = {}
    for line in document.splitlines():
        if not line.startswith("- ") or ": " not in line:
            continue
        key, value = line[2:].split(": ", 1)
        if key in result:
            raise ValueError(f"duplicate replay fact: {key}")
        result[key] = value
    return result


def exercise_actual_writer(binding: dict, project_root: Path, writer=None) -> None:
    from pathfinder_core.artifacts import REQUEST_NAME, write_saved_prompt_goal
    from pathfinder_core.repository import goal_scope
    from pathfinder_core.rendering import render_final_summary, render_goal_command
    from pathfinder_core.storage import write_atomic

    writer = writer or write_saved_prompt_goal

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "repository"
        subprocess.run(
            ["git", "init", str(root)], capture_output=True, text=True, check=True
        )
        for key, value in (
            ("user.name", "Pathfinder Replay"),
            ("user.email", "pathfinder@example.invalid"),
        ):
            subprocess.run(
                ["git", "-C", str(root), "config", key, value],
                capture_output=True,
                text=True,
                check=True,
            )
        (root / "tracked.txt").write_text("static replay fixture\n")
        subprocess.run(
            ["git", "-C", str(root), "add", "tracked.txt"],
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "commit", "-m", "fixture"],
            capture_output=True,
            text=True,
            check=True,
        )
        exclude = root / ".git" / "info" / "exclude"
        exclude.write_text(exclude.read_text() + "\n.agent-work/\n")
        output = root / ".agent-work" / "pathfinder" / "prompt-replay"
        output.mkdir(parents=True)
        request_path = output / REQUEST_NAME
        request = {
            "schema_version": 2,
            "objective": binding["objective"],
            "capabilities": binding["capabilities"],
            "scope": goal_scope(root),
            "proof_requirements": binding["proof_requirements"],
            "protected_surfaces": binding["protected_surfaces"],
            "runtime_boundary_required": True,
            "residual_risks": [],
            "next_input_needed": "explicit approval to run the saved Goal",
            "recorded_at": binding["created_at"],
        }
        write_atomic(request_path, request)
        result = writer(
            root, output, request_path, consume_request=True
        )
        if request_path.exists() or len(result["artifacts"]) != 4:
            raise ValueError("actual prompt writer did not complete the four-artifact contract")
        expected = {
            "06-goal-command.md",
            "06-goal-binding.json",
            "08-final-summary.md",
            "08-final-summary.json",
        }
        if {Path(path).name for path in result["artifacts"]} != expected:
            raise ValueError("actual prompt writer artifact set drift")
        if any(
            stat.S_IMODE(Path(path).stat().st_mode) & 0o222
            for path in result["artifacts"]
        ):
            raise ValueError("actual prompt writer left a canonical artifact writable")
        generated_binding = load(output / "06-goal-binding.json")
        generated_summary = load(output / "08-final-summary.json")
        for document, schema_name in (
            (generated_binding, "goal-binding.schema.json"),
            (generated_summary, "final-summary.schema.json"),
        ):
            schema = load(project_root / "schemas" / "artifacts" / schema_name)
            errors = list(Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(document))
            if errors:
                raise ValueError(
                    f"actual prompt writer generated invalid {schema_name}: "
                    f"{errors[0].message}"
                )
        expected_binding_inputs = {
            "schema_version": 2,
            "objective": request["objective"],
            "capabilities": request["capabilities"],
            "scope": request["scope"],
            "proof_requirements": request["proof_requirements"],
            "protected_surfaces": request["protected_surfaces"],
            "runtime_boundary_required": True,
            "created_at": request["recorded_at"],
        }
        if any(
            generated_binding.get(field) != value
            for field, value in expected_binding_inputs.items()
        ) or generated_binding.get("objective_source") != "user-prompt":
            raise ValueError("actual prompt writer drifted from its canonical request inputs")
        for field in ("mission_id", "goal_id", "binding_id"):
            if result.get(field) != generated_binding.get(field):
                raise ValueError(f"actual prompt writer returned a mismatched {field}")
        goals = generated_summary.get("goals", [])
        if (
            generated_summary.get("mission_id") != generated_binding["mission_id"]
            or generated_summary.get("final_state") != "goal-saved"
            or len(goals) != 1
            or goals[0].get("goal_id") != generated_binding["goal_id"]
            or goals[0].get("binding_status") != "not-run"
            or goals[0].get("verification") != "not-run"
        ):
            raise ValueError("actual prompt writer generated inconsistent terminal state")
        if (output / "06-goal-command.md").read_text() != render_goal_command(
            generated_binding
        ):
            raise ValueError("actual prompt writer generated a noncanonical Goal view")
        if (output / "08-final-summary.md").read_text() != render_final_summary(
            generated_binding, generated_summary
        ):
            raise ValueError("actual prompt writer generated a noncanonical summary view")


def main() -> int:
    if len(sys.argv) != 3:
        return fail("usage: validate-prompt-replay.py ARTIFACT_DIR PROJECT_ROOT")
    artifact_dir = Path(sys.argv[1])
    project_root = Path(sys.argv[2])
    sys.path.insert(0, str(project_root))
    from pathfinder_core.rendering import render_final_summary, render_goal_command

    try:
        replay = load(artifact_dir / "replay.json")
        paths = replay["artifact_paths"]
        if paths != [
            "00-session.md",
            "01-blind-discovery.md",
            "06-goal-command.md",
            "06-goal-binding.json",
            "08-final-summary.md",
            "08-final-summary.json",
        ]:
            return fail("prompt replay artifact set drift")
        for name in paths:
            path = artifact_dir / name
            if not path.is_file() or path.is_symlink():
                return fail(f"claimed prompt artifact missing or symlinked: {name}")
        actual = sorted(
            path.name for path in artifact_dir.iterdir() if path.name != "replay.json"
        )
        if actual != sorted(paths):
            return fail("prompt replay contains undeclared extra artifacts")
        session = facts((artifact_dir / "00-session.md").read_text())
        discovery = facts((artifact_dir / "01-blind-discovery.md").read_text())
        if session.get("route") != "prompt-to-goal" or session.get(
            "explicit execution approval"
        ) != "no" or session.get("final state") != "goal-saved":
            return fail("session artifact does not record the unexecuted prompt route")
        if discovery.get("research mode") != "static inspection only" or discovery.get(
            "commands run"
        ) != "none":
            return fail("discovery artifact does not prove static-only research")
        binding = load(artifact_dir / "06-goal-binding.json")
        summary = load(artifact_dir / "08-final-summary.json")
        if binding["objective_source"] != "user-prompt":
            return fail("prompt replay Goal Binding has the wrong objective source")
        for field in (
            "changed_files",
            "checks_run_with_exit_results",
            "criteria_satisfied",
            "scope_deviations",
            "protected_area_status",
            "runtime_boundary_observed",
            "complexity_notes",
            "remaining_risks",
            "next_input_needed_if_blocked",
        ):
            if not re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])",
                binding["objective"],
            ):
                return fail(f"prompt replay objective omits exact completion field: {field}")
        if binding["mission_id"] != summary["mission_id"]:
            return fail("prompt replay mission identity drift")
        if binding["goal_id"] != summary["goals"][0]["goal_id"]:
            return fail("prompt replay Goal identity drift")
        if summary["final_state"] != "goal-saved":
            return fail("prompt replay must remain unexecuted")
        if (artifact_dir / "06-goal-command.md").read_text() != render_goal_command(binding):
            return fail("prompt Goal view is not the deterministic controller rendering")
        if (artifact_dir / "08-final-summary.md").read_text() != render_final_summary(binding, summary):
            return fail("prompt summary view is not the deterministic controller rendering")
        exercise_actual_writer(binding, project_root)
    except (
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
