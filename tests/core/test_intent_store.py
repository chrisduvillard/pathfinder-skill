import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pathfinder_core.errors import StateError
from pathfinder_core.intent_store import INTENT_KINDS, IntentStore
from pathfinder_core.storage import MissionLock
from tests.contracts.test_intent_schemas import CHARTER, DOCTRINE, ROADMAP


GOLDENS = Path(__file__).parent / "fixtures" / "intent"


def documents():
    return {
        "charter": copy.deepcopy(CHARTER),
        "roadmap": copy.deepcopy(ROADMAP),
        "doctrine": copy.deepcopy(DOCTRINE),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class IntentStoreTests(unittest.TestCase):
    def test_json_is_canonical_and_views_match_goldens(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IntentStore(Path(directory))
            store.write_all(documents())
            self.assertEqual(store.load_all(), documents())
            for kind in INTENT_KINDS:
                expected = (GOLDENS / f"{kind}.md").read_text(encoding="utf-8")
                actual = (store.root / f"{kind}.md").read_text(encoding="utf-8")
                self.assertEqual(actual, expected)

    def test_all_documents_validate_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = documents()
            del invalid["roadmap"]["future_state"]
            with self.assertRaisesRegex(StateError, "schema validation"):
                IntentStore(root).write_all(invalid)
            self.assertFalse((root / ".pathfinder").exists())

    def test_load_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IntentStore(Path(directory))
            store.write_all(documents())
            path = store.root / "charter.json"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    '"schema_version": 1',
                    '"schema_version": 1, "schema_version": 1',
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(StateError, "duplicate JSON key"):
                store.load("charter")

    def test_tampered_views_rerender_without_changing_json_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IntentStore(Path(directory))
            store.write_all(documents())
            before = {
                kind: sha256(store.root / f"{kind}.json") for kind in INTENT_KINDS
            }
            for kind in INTENT_KINDS:
                (store.root / f"{kind}.md").write_text("tampered\n", encoding="utf-8")
            store.refresh_views()
            after = {
                kind: sha256(store.root / f"{kind}.json") for kind in INTENT_KINDS
            }
            self.assertEqual(after, before)
            for kind in INTENT_KINDS:
                expected = (GOLDENS / f"{kind}.md").read_text(encoding="utf-8")
                self.assertEqual(
                    (store.root / f"{kind}.md").read_text(encoding="utf-8"),
                    expected,
                )

    def test_untrusted_values_cannot_create_markdown_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            intent = documents()
            intent["charter"]["purpose"]["north_star"] = (
                "Keep <safe>\n# forged [link](https://invalid)"
            )
            store = IntentStore(Path(directory))
            store.write_all(intent)
            view = (store.root / "charter.md").read_text(encoding="utf-8")
            self.assertNotIn("\n# forged", view)
            self.assertIn(
                r"Keep &lt;safe&gt; \# forged \[link\](https://invalid)",
                view,
            )

    def test_interrupted_view_replace_preserves_canonical_json_and_old_view(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IntentStore(Path(directory))
            store.write_all(documents())
            json_before = sha256(store.root / "charter.json")
            view_before = (store.root / "charter.md").read_bytes()
            with mock.patch("pathfinder_core.intent_store.os.replace", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    store.refresh_views()
            self.assertEqual(sha256(store.root / "charter.json"), json_before)
            self.assertEqual((store.root / "charter.md").read_bytes(), view_before)

    def test_intent_lock_prevents_concurrent_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            store = IntentStore(Path(directory))
            store.write_all(documents())
            with MissionLock(store.lock_path):
                with self.assertRaisesRegex(StateError, "lock is already held"):
                    store.refresh_views()

    def test_symlinked_intent_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "outside"
            target.mkdir()
            (root / ".pathfinder").symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(StateError, "must not be a symlink"):
                IntentStore(root).write_all(documents())


if __name__ == "__main__":
    unittest.main()
