"""Frozen tracked dependency definitions, not a private-settings export.

When profile-era producers arrive, keep these fixtures fixed and direct these
assertions to the frozen legacy reader and the bundled Dependency catalog.
"""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from recordprep import summary_categories, practice_profiles

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/practice_profiles/legacy-dependency-v1.json"


def source_literals(path: Path, names: set[str]) -> dict:
    result = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    value = ast.literal_eval(node.value)
                    result[target.id] = sorted(value) if isinstance(value, set) else value
    return result


class LegacyProfileBaselineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_existing_categories_and_guidance_remain_exact(self):
        for kind, expected in self.fixture["categories"].items():
            guidance = summary_categories.load_category_descriptions(kind)
            actual = [{"id": item.identifier, "title": item.title, "guidance": guidance[item.identifier]}
                      for item in summary_categories.category_contracts(kind)]
            self.assertEqual(actual, expected)
        self.assertEqual(len(self.fixture["categories"]["hearings"]), 6)
        self.assertEqual(len(self.fixture["categories"]["reports"]), 12)

    def test_both_participant_validators_keep_legacy_roles(self):
        expected = self.fixture["roles"]
        publisher = source_literals(ROOT / "recordprep/pi_bundle.py", set(expected))
        self.assertEqual(publisher, expected)
        helper = source_literals(
            ROOT / ".pi/skills/recordprep-build-participant-index/scripts/participant_index.py",
            {"ROLE_IDS", "PARTICIPANT_ROLE_IDS"})
        self.assertEqual(helper["ROLE_IDS"], expected["valid_roles"])
        self.assertEqual(helper["PARTICIPANT_ROLE_IDS"], expected["valid_participant_roles"])

    def test_dependency_bundle_preserves_legacy_categories_and_roles(self):
        result = practice_profiles.validate_profile_directory(
            practice_profiles.bundled_profile_directory("california_dependency"))
        self.assertEqual(result.issues, ())
        for kind, expected in self.fixture["categories"].items():
            current = result.draft.resource(kind)
            for actual, historical in zip(current, expected, strict=True):
                if actual["id"] == "agency_recommendations":
                    self.assertEqual(actual["id"], historical["id"])
                    self.assertEqual(actual["title"], historical["title"])
                    self.assertIn("wherever they appear", actual["guidance"])
                    self.assertIn("clear distinction from actual court", actual["guidance"])
                else:
                    self.assertEqual(actual, historical)
        roles = result.draft.resource("roles")
        for key, legacy_key in (("counsel", "valid_roles"), ("participants", "valid_participant_roles")):
            self.assertEqual({entry["id"] for entry in roles[key]},
                             set(self.fixture["roles"][legacy_key]) | {"unknown", "other"})
        self.assertEqual(result.draft.resource("policies"), {})

    def test_general_has_neutral_categories_and_no_selectable_policies(self):
        result = practice_profiles.validate_profile_directory(practice_profiles.bundled_profile_directory("general"))
        self.assertEqual(result.issues, ())
        self.assertEqual(len(result.draft.resource("hearings")), 6)
        self.assertEqual(len(result.draft.resource("reports")), 7)
        self.assertEqual(result.draft.resource("hearings")[0]["id"], "party_appearances")
        self.assertEqual(result.draft.resource("policies"), {})
        self.assertNotIn("dependency", " ".join(data.decode() for _name, data in result.draft.files).lower())

    def test_no_premature_artifact_schema_transition(self):
        expected = self.fixture["summary_formats"]
        self.assertEqual(source_literals(ROOT / "recordprep/summary_agents.py", set(expected)), expected)


if __name__ == "__main__":
    unittest.main()
