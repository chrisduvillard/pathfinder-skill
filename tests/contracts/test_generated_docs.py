import copy
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.render_protected_surfaces import (
    load_policy,
    main,
    render_policy_table,
    replace_generated_region,
)


ROOT = Path(__file__).resolve().parents[2]


class GeneratedDocsTests(unittest.TestCase):
    def test_committed_protected_surface_table_matches_canonical_policy(self):
        policy = load_policy(ROOT / "policies" / "protected-surfaces.v1.json")
        document = (ROOT / "docs" / "protected-surfaces.md").read_text(encoding="utf-8")
        self.assertEqual(
            document,
            replace_generated_region(document, render_policy_table(policy)),
        )

    def test_policy_change_changes_the_generated_table(self):
        policy = load_policy(ROOT / "policies" / "protected-surfaces.v1.json")
        changed = copy.deepcopy(policy)
        changed["rules"][0]["patterns"].append("sessions/**")
        self.assertNotEqual(render_policy_table(policy), render_policy_table(changed))

    def test_duplicate_policy_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1,"rules":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_policy(path)

    def test_missing_or_duplicate_generated_markers_are_rejected(self):
        table = "generated table"
        for document in (
            "no markers\n",
            "<!-- pathfinder:generated:protected-surfaces:v1:begin -->\n"
            "first\n<!-- pathfinder:generated:protected-surfaces:v1:begin -->\n"
            "second\n<!-- pathfinder:generated:protected-surfaces:v1:end -->\n",
        ):
            with self.subTest(document=document), self.assertRaisesRegex(
                ValueError, "exactly one generated protected-surface region"
            ):
                replace_generated_region(document, table)

    def test_cli_check_rejects_stale_table_and_refresh_repairs_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policies").mkdir()
            (root / "docs").mkdir()
            shutil.copy(
                ROOT / "policies" / "protected-surfaces.v1.json",
                root / "policies" / "protected-surfaces.v1.json",
            )
            target = root / "docs" / "protected-surfaces.md"
            target.write_text(
                (ROOT / "docs" / "protected-surfaces.md")
                .read_text(encoding="utf-8")
                .replace("<code>auth</code>", "<code>stale-auth</code>", 1),
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main([str(root), "--check"]), 1)
                self.assertEqual(main([str(root)]), 0)
                self.assertEqual(main([str(root), "--check"]), 0)


if __name__ == "__main__":
    unittest.main()
