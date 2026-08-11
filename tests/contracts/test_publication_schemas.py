import copy
import hashlib
import json
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from tests.contracts.test_intent_schemas import reject_duplicate_keys


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = ROOT / "schemas" / "publication"
FIXTURE_PATH = ROOT / "tests" / "contracts" / "fixtures" / "publication-contracts.json"
NOW = datetime.fromisoformat("2026-08-11T12:05:00+00:00")
HASH_FIELDS = {"policy": "policy_sha256", "authorization": "authorization_sha256"}


def load_json(path):
    return json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)


def canonical_sha256(document, hash_field):
    payload = {key: value for key, value in document.items() if key != hash_field}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_schema(name, document):
    schema = load_json(SCHEMA_ROOT / f"merge-{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


def validate_contract_pair(policy, authorization, now=NOW):
    validate_schema("policy", policy)
    validate_schema("authorization", authorization)

    for name, document in (("policy", policy), ("authorization", authorization)):
        hash_field = HASH_FIELDS[name]
        if document[hash_field] != canonical_sha256(document, hash_field):
            raise ValidationError(f"{hash_field} does not match canonical document")
        issued = datetime.fromisoformat(document["issued_at"])
        expires = datetime.fromisoformat(document["expires_at"])
        if not issued <= now < expires:
            raise ValidationError(f"{name} validity window is not current")

    if authorization["policy"] != {
        "policy_id": policy["policy_id"],
        "policy_sha256": policy["policy_sha256"],
    }:
        raise ValidationError("authorization policy binding drift")
    if authorization["repository"] != policy["repository"]:
        raise ValidationError("authorization repository binding drift")
    if authorization["merge_method"] != policy["merge_method"]:
        raise ValidationError("authorization merge method drift")


def mutate_contracts(bundle, case):
    documents = {
        "policy": copy.deepcopy(bundle["policy"]),
        "authorization": copy.deepcopy(bundle["authorization"]),
    }
    document = documents[case["document"]]
    parent = document
    for segment in case["path"][:-1]:
        parent = parent[segment]
    final = case["path"][-1]
    if case["operation"] == "remove":
        del parent[final]
    else:
        parent[final] = case["value"]
    hash_field = HASH_FIELDS[case["document"]]
    if hash_field in document:
        document[hash_field] = canonical_sha256(document, hash_field)
    return documents


class PublicationSchemaTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_json(FIXTURE_PATH)

    def test_publication_schemas_are_valid_and_closed(self):
        for path in sorted(SCHEMA_ROOT.glob("*.json")):
            with self.subTest(path=path.name):
                schema = load_json(path)
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema["additionalProperties"])

    def test_valid_policy_and_authorization_are_bound_and_current(self):
        validate_contract_pair(self.bundle["policy"], self.bundle["authorization"])

    def test_negative_contract_fixtures_fail_closed(self):
        for case in self.bundle["negative_cases"]:
            with self.subTest(case=case["name"]), self.assertRaises(ValidationError):
                changed = mutate_contracts(self.bundle, case)
                validate_contract_pair(changed["policy"], changed["authorization"])

    def test_unknown_fields_are_rejected_even_with_a_fresh_hash(self):
        changed = copy.deepcopy(self.bundle["policy"])
        changed["repository_controlled_override"] = True
        changed["policy_sha256"] = canonical_sha256(changed, "policy_sha256")
        with self.assertRaises(ValidationError):
            validate_contract_pair(changed, self.bundle["authorization"])

    def test_repository_identity_must_match_across_both_keys(self):
        authorization = copy.deepcopy(self.bundle["authorization"])
        authorization["repository"]["name"] = "another-repo"
        authorization["authorization_sha256"] = canonical_sha256(
            authorization, "authorization_sha256"
        )
        with self.assertRaisesRegex(ValidationError, "repository binding drift"):
            validate_contract_pair(self.bundle["policy"], authorization)

    def test_existing_mission_authorization_still_has_no_merge_target(self):
        existing = load_json(
            ROOT / "schemas" / "mission" / "authorization-snapshot.schema.json"
        )
        self.assertEqual(
            existing["properties"]["publication_target"]["enum"],
            ["none", "local-branch", "github-awaiting-review"],
        )

    def test_fixture_loader_rejects_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads(
                '{"policy":{"policy_id":"first","policy_id":"second"}}',
                object_pairs_hook=reject_duplicate_keys,
            )


if __name__ == "__main__":
    unittest.main()
