import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import StateError
from pathfinder_core.migrations import migrate_intent, migrate_mission
from pathfinder_core.storage import MissionStore

from tests.integration.test_one_goal_mission import initial_state


class MigrationTests(unittest.TestCase):
    def write_intent(self, root, kind, clarity="clarity: resolved", version=1):
        path = Path(root) / ".pathfinder" / f"{kind}.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"# {kind}\n<!-- pathfinder:{kind} v{version} -->\ncompletion: complete\n{clarity}\n")
        return path

    def test_v1_legacy_intent_migrates_without_granting_clarity(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [self.write_intent(directory, kind) for kind in ("charter", "roadmap", "doctrine")]
            backup = Path(directory) / "backup"
            result = migrate_intent(directory, backup)
            self.assertEqual(sorted(result["changed"]), ["charter.md", "doctrine.md", "roadmap.md"])
            self.assertFalse(result["intent_clarity_granted"])
            for path in paths:
                self.assertIn("intent_clarity: unresolved", path.read_text())
                self.assertIn("clarity: resolved", (backup / path.name).read_text())

    def test_current_v1_intent_is_a_valid_noop_with_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("charter", "roadmap", "doctrine"):
                self.write_intent(directory, kind, "intent_clarity: unresolved")
            result = migrate_intent(directory, Path(directory) / "backup")
            self.assertEqual(result["changed"], [])

    def test_crlf_intent_migrates_without_losing_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("charter", "roadmap", "doctrine"):
                path = self.write_intent(directory, kind)
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            migrate_intent(directory, Path(directory) / "backup")
            for kind in ("charter", "roadmap", "doctrine"):
                content = (Path(directory) / ".pathfinder" / f"{kind}.md").read_bytes()
                self.assertIn(b"intent_clarity: unresolved\r\n", content)

    def test_unknown_intent_version_stops_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("charter", "roadmap", "doctrine"):
                self.write_intent(directory, kind, version=2 if kind == "roadmap" else 1)
            backup = Path(directory) / "backup"
            with self.assertRaisesRegex(StateError, "unsupported roadmap"):
                migrate_intent(directory, backup)
            self.assertFalse(backup.exists())

    def test_failed_write_restores_all_intent_files(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [self.write_intent(directory, kind) for kind in ("charter", "roadmap", "doctrine")]
            before = {path: path.read_bytes() for path in paths}
            from pathfinder_core import migrations
            real_write = migrations._atomic_write
            calls = 0

            def fail_second(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected migration failure")
                real_write(path, content)

            with mock.patch("pathfinder_core.migrations._atomic_write", side_effect=fail_second):
                with self.assertRaises(OSError):
                    migrate_intent(directory, Path(directory) / "backup")
            for path in paths:
                self.assertEqual(path.read_bytes(), before[path])

    def test_current_mission_is_validated_and_backed_up(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "mission"
            MissionStore(state_dir).initialize(initial_state())
            backup = Path(directory) / "mission-backup"
            result = migrate_mission(state_dir, backup)
            self.assertEqual(result["changed"], [])
            self.assertTrue((backup / "state.json").is_file())


if __name__ == "__main__":
    unittest.main()
