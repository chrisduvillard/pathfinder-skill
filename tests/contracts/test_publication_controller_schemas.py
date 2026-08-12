import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from pathfinder_core.merge_policy import canonical_sha256
from tests.contracts.test_intent_schemas import reject_duplicate_keys


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "publication"
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"


def load(path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)


class PublicationControllerSchemaTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load(FIXTURES / "publication-controller-contracts.json")

    def validate(self, name, document):
        schema = load(SCHEMAS / f"publication-{name}.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).validate(document)

    def test_request_dispatch_and_receipt_are_closed_and_canonical(self):
        fields = {
            "request": "request_sha256",
            "dispatch": "dispatch_sha256",
            "receipt": "receipt_sha256",
        }
        for name, field in fields.items():
            with self.subTest(name=name):
                self.validate(name, self.bundle[name])
                self.assertEqual(
                    self.bundle[name][field],
                    canonical_sha256(self.bundle[name], field),
                )

    def test_receipt_projects_the_merge_authorization_candidate_exactly(self):
        authorization = load(FIXTURES / "publication-contracts.json")[
            "authorization"
        ]
        receipt = self.bundle["receipt"]
        candidate = authorization["candidate"]
        self.assertEqual(
            candidate["publication_receipt_id"],
            receipt["publication_receipt_id"],
        )
        self.assertEqual(
            candidate["mission_state_sha256"],
            receipt["mission"]["mission_state_sha256"],
        )
        self.assertEqual(
            candidate["pull_request"],
            {
                key: receipt["pull_request"][key]
                for key in (
                    "id",
                    "node_id",
                    "number",
                    "head_ref",
                    "head_sha",
                    "base_ref",
                    "base_sha",
                )
            },
        )
        self.assertEqual(candidate["diff"], receipt["diff"])

    def test_unknown_or_incomplete_exact_identity_fails_closed(self):
        for mutation in ("unknown", "missing-node", "non-github-url"):
            with self.subTest(mutation=mutation), self.assertRaises(Exception):
                changed = copy.deepcopy(self.bundle["receipt"])
                if mutation == "unknown":
                    changed["trusted"] = True
                elif mutation == "missing-node":
                    del changed["pull_request"]["node_id"]
                else:
                    changed["pull_request"]["url"] = "https://example.com/pull/72"
                if "receipt_sha256" in changed:
                    changed["receipt_sha256"] = canonical_sha256(
                        changed, "receipt_sha256"
                    )
                self.validate("receipt", changed)

    def test_default_routes_have_zero_publication_controller_callers(self):
        callers = []
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            if path.name == "publication_controller.py":
                continue
            if "PublicationController(" in path.read_text():
                callers.append(path)
        for folder in ("scripts", "skills", ".codex-plugin", ".claude-plugin"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and "PublicationController(" in path.read_text(
                    errors="ignore"
                ):
                    callers.append(path)
        self.assertEqual(callers, [])


if __name__ == "__main__":
    unittest.main()
