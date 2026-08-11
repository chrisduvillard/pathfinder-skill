import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import StateError
from pathfinder_core.__main__ import main
from pathfinder_core.intent_store import INTENT_KINDS
from pathfinder_core.migrations import activate_intent, migrate_intent, migrate_mission
from pathfinder_core.storage import MissionStore, read_json, write_atomic

from tests.contracts.test_intent_schemas import CHARTER, DOCTRINE, ROADMAP
from tests.integration.test_one_goal_mission import initial_state


GOLDENS = Path(__file__).parent / "fixtures" / "intent"


class MigrationTests(unittest.TestCase):
    def write_intent(self, root, kind, clarity="clarity: resolved", version=1):
        path = Path(root) / ".pathfinder" / f"{kind}.md"
        path.parent.mkdir(exist_ok=True)
        content = f"# {kind}\n<!-- pathfinder:{kind} v{version} -->\ncompletion: complete\n{clarity}\n"
        path.write_bytes(content.encode("utf-8"))
        return path

    def write_activation_inputs(self, root, intent=None):
        intent = intent or {"charter": CHARTER, "roadmap": ROADMAP, "doctrine": DOCTRINE}
        inputs = Path(root) / "inputs"
        inputs.mkdir(parents=True)
        paths = {}
        for kind in INTENT_KINDS:
            path = inputs / f"{kind}.json"
            write_atomic(path, intent[kind])
            paths[kind] = path
        return paths

    def activate(self, root, backup, inputs, confirmed=True, scoped_root="."):
        return activate_intent(
            root,
            backup,
            inputs,
            creator_confirmed=confirmed,
            scoped_root=scoped_root,
        )

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

    def test_creator_confirmed_activation_backs_up_exact_legacy_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            originals = {}
            for kind in INTENT_KINDS:
                path = self.write_intent(directory, kind)
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
                originals[kind] = path.read_bytes()
            inputs = self.write_activation_inputs(directory)
            backup = Path(directory) / "backup"
            result = self.activate(directory, backup, inputs)
            self.assertEqual(result["intent_clarity"], "resolved")
            self.assertFalse(result["authorization_granted"])
            self.assertFalse(result["autonomy_authorized"])
            for kind in INTENT_KINDS:
                self.assertEqual((backup / f"{kind}.md").read_bytes(), originals[kind])
                self.assertEqual(read_json(Path(directory) / ".pathfinder" / f"{kind}.json"), read_json(inputs[kind]))
                self.assertEqual(
                    (Path(directory) / ".pathfinder" / f"{kind}.md").read_text(encoding="utf-8"),
                    (GOLDENS / f"{kind}.md").read_text(encoding="utf-8"),
                )

    def test_activation_cli_requires_and_reports_creator_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.write_activation_inputs(directory)
            backup = Path(directory) / "backup"
            argv = [
                "migrate", "intent-activate", "--root", directory,
                "--backup-dir", str(backup),
                "--charter-json", str(inputs["charter"]),
                "--roadmap-json", str(inputs["roadmap"]),
                "--doctrine-json", str(inputs["doctrine"]),
                "--creator-confirmed", "--json",
            ]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(argv), 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result["creator_confirmed"])
            self.assertFalse(result["authorization_granted"])
            self.assertEqual(result["scoped_root"], ".")
            self.assertEqual(
                result["intent_dir"], str(Path(directory).resolve() / ".pathfinder")
            )

    def test_activation_cli_writes_only_the_selected_subproject_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "apps" / "api").mkdir(parents=True)
            inputs = self.write_activation_inputs(directory)
            backup = repo / "backup"
            argv = [
                "migrate", "intent-activate", "--root", directory,
                "--scoped-root", "apps/api", "--backup-dir", str(backup),
                "--charter-json", str(inputs["charter"]),
                "--roadmap-json", str(inputs["roadmap"]),
                "--doctrine-json", str(inputs["doctrine"]),
                "--creator-confirmed", "--json",
            ]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(argv), 0)
            result = json.loads(output.getvalue())
            namespace = (
                repo.resolve()
                / ".pathfinder"
                / "scopes"
                / "apps"
                / "api"
                / "intent"
            )
            self.assertEqual(result["scoped_root"], "apps/api")
            self.assertEqual(result["intent_dir"], str(namespace))
            self.assertTrue((namespace / "charter.json").is_file())
            self.assertFalse((repo / ".pathfinder" / "charter.json").exists())

    def test_scoped_activation_crash_removes_new_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "apps" / "api").mkdir(parents=True)
            inputs = self.write_activation_inputs(directory)
            with mock.patch(
                "pathfinder_core.intent_store._write_view_atomic",
                side_effect=OSError("injected scoped activation failure"),
            ):
                with self.assertRaises(OSError):
                    self.activate(
                        directory,
                        repo / "backup",
                        inputs,
                        scoped_root="apps/api",
                    )
            self.assertFalse((repo / ".pathfinder").exists())

    def test_missing_confirmation_or_document_preserves_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = self.write_intent(directory, "charter")
            original = legacy.read_bytes()
            inputs = self.write_activation_inputs(directory)
            for name, supplied, confirmed in (
                ("confirmation", inputs, False),
                ("document", {key: value for key, value in inputs.items() if key != "doctrine"}, True),
            ):
                with self.subTest(name=name):
                    backup = Path(directory) / f"backup-{name}"
                    with self.assertRaises(StateError):
                        self.activate(directory, backup, supplied, confirmed)
                    self.assertEqual(legacy.read_bytes(), original)
                    self.assertFalse(backup.exists())

    def test_invalid_or_unknown_json_stops_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = self.write_intent(directory, "charter")
            original = legacy.read_bytes()
            for name in ("invalid", "unknown"):
                with self.subTest(name=name):
                    inputs = self.write_activation_inputs(Path(directory) / name)
                    if name == "invalid":
                        inputs["roadmap"].write_text("{invalid", encoding="utf-8")
                    else:
                        stale = read_json(inputs["roadmap"])
                        stale["schema_version"] = 2
                        write_atomic(inputs["roadmap"], stale)
                    backup = Path(directory) / f"backup-{name}"
                    with self.assertRaises(StateError):
                        self.activate(directory, backup, inputs)
                    self.assertEqual(legacy.read_bytes(), original)
                    self.assertFalse(backup.exists())

    def test_activation_crash_restores_original_set(self):
        with tempfile.TemporaryDirectory() as directory:
            original_paths = [self.write_intent(directory, kind) for kind in INTENT_KINDS]
            originals = {path: path.read_bytes() for path in original_paths}
            inputs = self.write_activation_inputs(directory)
            from pathfinder_core import intent_store
            real_write = intent_store._write_view_atomic
            calls = 0

            def fail_second(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected activation failure")
                real_write(path, content)

            with mock.patch("pathfinder_core.intent_store._write_view_atomic", side_effect=fail_second):
                with self.assertRaises(OSError):
                    self.activate(directory, Path(directory) / "backup", inputs)
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)
            for kind in INTENT_KINDS:
                self.assertFalse((Path(directory) / ".pathfinder" / f"{kind}.json").exists())

    def test_symlinked_input_or_target_stops_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.write_activation_inputs(directory)
            original_roadmap = inputs["roadmap"]
            link = Path(directory) / "roadmap-link.json"
            link.symlink_to(inputs["roadmap"])
            inputs["roadmap"] = link
            backup = Path(directory) / "backup-input"
            with self.assertRaisesRegex(StateError, "regular roadmap JSON"):
                self.activate(directory, backup, inputs)
            self.assertFalse(backup.exists())

            inputs["roadmap"] = original_roadmap
            intent_dir = Path(directory) / ".pathfinder"
            intent_dir.mkdir()
            outside = Path(directory) / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            (intent_dir / "charter.md").symlink_to(outside)
            backup = Path(directory) / "backup-target"
            with self.assertRaisesRegex(StateError, "regular target"):
                self.activate(directory, backup, inputs)
            self.assertFalse(backup.exists())

    def test_incomplete_confirmed_json_remains_unresolved_and_unauthorized(self):
        with tempfile.TemporaryDirectory() as directory:
            intent = {
                "charter": copy.deepcopy(CHARTER),
                "roadmap": copy.deepcopy(ROADMAP),
                "doctrine": copy.deepcopy(DOCTRINE),
            }
            intent["roadmap"]["completion"] = "incomplete"
            inputs = self.write_activation_inputs(directory, intent)
            result = self.activate(directory, Path(directory) / "backup", inputs)
            self.assertEqual(result["intent_clarity"], "unresolved")
            self.assertFalse(result["authorization_granted"])
            self.assertFalse(result["autonomy_authorized"])

    def test_reactivation_repairs_view_without_changing_json_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            inputs = self.write_activation_inputs(directory)
            self.activate(directory, Path(directory) / "backup-1", inputs)
            charter_json = Path(directory) / ".pathfinder" / "charter.json"
            before = hashlib.sha256(charter_json.read_bytes()).hexdigest()
            (Path(directory) / ".pathfinder" / "charter.md").write_text(
                "tampered\n", encoding="utf-8"
            )
            self.activate(directory, Path(directory) / "backup-2", inputs)
            after = hashlib.sha256(charter_json.read_bytes()).hexdigest()
            self.assertEqual(after, before)
            self.assertEqual(
                (Path(directory) / ".pathfinder" / "charter.md").read_text(encoding="utf-8"),
                (GOLDENS / "charter.md").read_text(encoding="utf-8"),
            )

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
