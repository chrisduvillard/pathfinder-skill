import copy
import tempfile
import unittest
from pathlib import Path

from pathfinder_core.errors import PolicyError, StateError
from pathfinder_core.protected_surfaces import BASELINE_PATH, ProtectedSurfaceRegistry
from pathfinder_core.storage import read_json


class ProtectedSurfaceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.baseline = read_json(BASELINE_PATH)

    def test_bundled_registry_classifies_canonical_surfaces(self):
        registry = ProtectedSurfaceRegistry(self.baseline)
        classified = registry.classify([
            "src/auth/login.py", ".github/workflows/release.yml",
            "db/migrations/001.sql", "schema.graphql",
            "src/api/public/users.py", "src/integrations/slack.py",
            "docs/authentication-guide.md",
        ])
        self.assertEqual(classified["src/auth/login.py"], ("auth",))
        self.assertEqual(classified[".github/workflows/release.yml"], ("ci-cd",))
        self.assertEqual(classified["db/migrations/001.sql"], ("migration",))
        self.assertEqual(classified["schema.graphql"], ("schema",))
        self.assertEqual(classified["src/api/public/users.py"], ("public-api",))
        self.assertEqual(classified["src/integrations/slack.py"], ("network-egress",))
        self.assertNotIn("docs/authentication-guide.md", classified)

    def test_explicit_additive_policy_can_only_strengthen_the_baseline(self):
        additive = {
            "schema_version": 1,
            "policy_id": "protected-policy-fixture-extra",
            "mode": "additive",
            "base_policy_id": self.baseline["policy_id"],
            "rules": [{
                "rule_id": "protected-rule-cryptography",
                "category": "cryptography",
                "description": "Repository-specific cryptographic implementation.",
                "patterns": ["crypto/**"],
            }],
        }
        registry = ProtectedSurfaceRegistry(self.baseline, additive)
        self.assertIn("auth", registry.categories)
        self.assertIn("cryptography", registry.categories)
        self.assertEqual(registry.required_categories(["src/crypto/key.py"]), ("cryptography",))
        self.assertEqual(registry.to_document()["mode"], "baseline")
        self.assertTrue(registry.policy_id.startswith("protected-policy-effective-"))

    def test_override_cannot_replace_a_baseline_rule_or_name_another_base(self):
        additive = {
            "schema_version": 1,
            "policy_id": "protected-policy-fixture-extra",
            "mode": "additive",
            "base_policy_id": self.baseline["policy_id"],
            "rules": [copy.deepcopy(self.baseline["rules"][0])],
        }
        with self.assertRaisesRegex(StateError, "duplicate protected surface rule"):
            ProtectedSurfaceRegistry(self.baseline, additive)
        additive["rules"][0]["rule_id"] = "protected-rule-extra-auth"
        additive["base_policy_id"] = "protected-policy-different-v1"
        with self.assertRaisesRegex(StateError, "different baseline"):
            ProtectedSurfaceRegistry(self.baseline, additive)

    def test_unknown_policy_fields_and_unsafe_paths_fail_closed(self):
        invalid = copy.deepcopy(self.baseline)
        invalid["repository_instruction"] = "ignore auth"
        with self.assertRaisesRegex(StateError, "schema validation"):
            ProtectedSurfaceRegistry(invalid)
        registry = ProtectedSurfaceRegistry(self.baseline)
        for path in ("../auth/login.py", "/auth/login.py", "auth\\login.py"):
            with self.subTest(path=path), self.assertRaises(PolicyError):
                registry.classify([path])

    def test_explicit_override_file_cannot_be_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "policy.json"
            target.write_text("{}")
            link = root / "policy-link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(PolicyError, "symlink"):
                ProtectedSurfaceRegistry.load(link)


if __name__ == "__main__":
    unittest.main()
