import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from pathfinder_core.__main__ import main
from pathfinder_core.errors import PolicyError
from pathfinder_core.mission_host import HostMissionController
from pathfinder_core.mission_views import write_mission_views
from pathfinder_core.projections import build_mission_projection
from pathfinder_core.rendering import render_mission_final_summary, render_run_log

from tests.core.test_repository import make_repository
from tests.integration.test_one_goal_mission import (
    BOUNDARY,
    NOW,
    goal_binding,
    host_receipt,
    local_authorization,
)


class MissionViewTests(unittest.TestCase):
    def make_run(self, directory: str, *, ignored: bool = True):
        root = Path(directory) / "repo"
        make_repository(root)
        if ignored:
            exclude = root / ".git" / "info" / "exclude"
            exclude.write_text(exclude.read_text() + "\n.agent-work/\n")
        output = root / ".agent-work" / "pathfinder" / "mission-run"
        output.mkdir(parents=True)
        controller = HostMissionController(output / "mission-state", clock=lambda: NOW)
        controller.start(
            binding=goal_binding(),
            authorization=local_authorization(),
            runtime_boundary=BOUNDARY,
        )
        return root, output, controller

    def advance(self, controller: HostMissionController, count: int) -> None:
        for _step in range(count):
            action = controller.next()["action"]
            controller.record(host_receipt(action))

    def finish(self, controller: HostMissionController) -> None:
        self.advance(controller, 5)
        controller.next()

    def test_active_refresh_writes_replaceable_run_log_views_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            result = write_mission_views(root, controller.root, output)
            self.assertEqual(result["state"], "authorized")
            self.assertEqual(
                [Path(path).name for path in result["artifacts"]],
                ["07-run-log.json", "07-run-log.md"],
            )
            self.assertNotEqual((output / "07-run-log.json").stat().st_mode & 0o200, 0)
            self.assertIn("state: authorized", (output / "07-run-log.md").read_text())
            self.assertFalse((output / "08-final-summary.json").exists())

    def test_terminal_refresh_writes_and_seals_all_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            self.finish(controller)
            result = write_mission_views(root, controller.root, output)
            self.assertEqual(result["state"], "awaiting-review")
            self.assertEqual(len(result["artifacts"]), 4)
            for path in map(Path, result["artifacts"]):
                self.assertEqual(path.stat().st_mode & 0o222, 0)
            summary = json.loads((output / "08-final-summary.json").read_text())
            self.assertEqual(summary["final_state"], "awaiting-review")
            self.assertIn("branch_name: pathfinder/auto/test-goal", (output / "08-final-summary.md").read_text())

    def test_tampered_views_are_repaired_without_mutating_mission_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            self.finish(controller)
            write_mission_views(root, controller.root, output)
            state_path = controller.root / "state.json"
            before = hashlib.sha256(state_path.read_bytes()).hexdigest()
            for name in (
                "07-run-log.json", "07-run-log.md",
                "08-final-summary.json", "08-final-summary.md",
            ):
                path = output / name
                path.chmod(0o600)
                path.write_text("tampered\n")
            write_mission_views(root, controller.root, output)
            after = hashlib.sha256(state_path.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(
                json.loads((output / "07-run-log.json").read_text())["mission_id"],
                goal_binding()["mission_id"],
            )
            self.assertIn("# Final summary", (output / "08-final-summary.md").read_text())

    def test_interrupted_view_write_is_repairable_and_does_not_mutate_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            self.finish(controller)
            state_path = controller.root / "state.json"
            before = hashlib.sha256(state_path.read_bytes()).hexdigest()
            from pathfinder_core import mission_views

            original = mission_views._write_view
            writes = 0

            def interrupt_third_write(path, content):
                nonlocal writes
                writes += 1
                if writes == 3:
                    raise RuntimeError("simulated view interruption")
                return original(path, content)

            with mock.patch.object(mission_views, "_write_view", side_effect=interrupt_third_write):
                with self.assertRaisesRegex(RuntimeError, "simulated view interruption"):
                    write_mission_views(root, controller.root, output)
            self.assertTrue((output / "07-run-log.json").exists())
            self.assertTrue((output / "08-final-summary.json").exists())
            self.assertFalse((output / "07-run-log.md").exists())
            self.assertEqual(before, hashlib.sha256(state_path.read_bytes()).hexdigest())
            write_mission_views(root, controller.root, output)
            self.assertTrue((output / "07-run-log.md").exists())
            self.assertTrue((output / "08-final-summary.md").exists())

    def test_symlink_target_is_rejected_before_any_view_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            target = Path(directory) / "outside.md"
            target.write_text("outside\n")
            try:
                (output / "07-run-log.md").symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            with self.assertRaisesRegex(PolicyError, "must not be a symlink"):
                write_mission_views(root, controller.root, output)
            self.assertFalse((output / "07-run-log.json").exists())
            self.assertEqual(target.read_text(), "outside\n")

    def test_unignored_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory, ignored=False)
            with self.assertRaisesRegex(PolicyError, "not confirmed ignored"):
                write_mission_views(root, controller.root, output)
            self.assertFalse((output / "07-run-log.json").exists())

    def test_renderers_are_deterministic_and_cli_reports_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output, controller = self.make_run(directory)
            self.finish(controller)
            projection = build_mission_projection(controller.root)
            self.assertEqual(render_run_log(projection), render_run_log(projection))
            self.assertEqual(
                render_mission_final_summary(projection),
                render_mission_final_summary(projection),
            )
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main([
                    "artifacts", "mission-view",
                    "--repo-root", str(root),
                    "--state-dir", str(controller.root),
                    "--output-dir", str(output),
                    "--json",
                ])
            self.assertEqual(code, 0, stderr.getvalue())
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["state"], "awaiting-review")
            self.assertEqual(len(result["artifacts"]), 4)


if __name__ == "__main__":
    unittest.main()
