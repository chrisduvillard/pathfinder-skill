import argparse
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from pathfinder_core.__main__ import _parser
from pathfinder_core.merge_policy import canonical_sha256
from tests.contracts.test_intent_schemas import reject_duplicate_keys


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "publication"
FIXTURES = ROOT / "tests" / "contracts" / "fixtures"


def command_names(parser):
    names = set()
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, child in action.choices.items():
            names.add(name)
            names.update(command_names(child))
    return names


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

    def test_publication_request_requires_explicit_github_authorization(self):
        for field, value in (
            ("explicit_request", False),
            ("publication_target", "local-branch"),
            ("limits", {
                "max_goals": 1,
                "max_attempts": 2,
                "max_wall_seconds": 3600,
                "max_total_prs": 2,
            }),
        ):
            with self.subTest(field=field), self.assertRaises(Exception):
                changed = copy.deepcopy(self.bundle["request"])
                changed["authorization"][field] = value
                changed["mission"]["authorization_snapshot_sha256"] = (
                    canonical_sha256(changed["authorization"])
                )
                changed["request_sha256"] = canonical_sha256(
                    changed, "request_sha256"
                )
                self.validate("request", changed)

    def test_default_packaged_routes_have_zero_publication_or_merge_composition(self):
        packaged = {}
        for path in (ROOT / "pathfinder_core").rglob("*.py"):
            packaged[path.relative_to(ROOT).as_posix()] = path.read_text()
        for folder in (
            "scripts",
            "skills",
            ".agents",
            ".codex-plugin",
            ".claude-plugin",
        ):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file():
                    packaged[path.relative_to(ROOT).as_posix()] = path.read_text(
                        errors="ignore"
                    )

        constructor_owners = {
            token: {
                path
                for path, source in packaged.items()
                if token in source and path != owner
            }
            for token, owner in (
                (
                    "PublicationController(",
                    "pathfinder_core/publication_controller.py",
                ),
                ("MergeExecutor(", "pathfinder_core/merge_executor.py"),
            )
        }
        self.assertEqual(
            constructor_owners,
            {"PublicationController(": set(), "MergeExecutor(": set()},
        )
        self.assertEqual(
            {
                path
                for path, source in packaged.items()
                if "ExactGitHubBackend" in source
                and path != "pathfinder_core/adapters/github.py"
            },
            set(),
        )
        exact_backend_methods = (
            "def preflight(",
            "def push_exact(",
            "def find_pull_request_exact(",
            "def create_pull_request_exact(",
            "def check_observations_exact(",
        )
        self.assertEqual(
            {
                path
                for path, source in packaged.items()
                if path != "pathfinder_core/adapters/github.py"
                and all(method in source for method in exact_backend_methods)
            },
            set(),
        )

        enabled_paths = {
            "pathfinder_core/__main__.py",
            "pathfinder_core/mission_host.py",
            "pathfinder_core/goal_pack.py",
            "pathfinder_core/adapters/github.py",
        }
        enabled = "\n".join(
            source
            for path, source in packaged.items()
            if path in enabled_paths
            or path.startswith(
                (
                    "scripts/",
                    "skills/",
                    ".agents/",
                    ".codex-plugin/",
                    ".claude-plugin/",
                )
            )
        )
        for forbidden in (
            "PublicationController",
            "MergeExecutor",
            "GitHubMergeBackend",
            "GitHubMergeCredential",
            "HostMergeCredentialReader",
            "merge_credentials",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, enabled)

        self.assertTrue(
            command_names(_parser()).isdisjoint(
                {
                    "publish",
                    "publication",
                    "merge",
                    "merge-status",
                    "merge-evaluate",
                    "merge-execute",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
