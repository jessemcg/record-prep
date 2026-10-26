"""Public baseline promoted from the reviewed Dependency editor guidance.

Never read a real personal store/configuration: the bundle is self-contained.
"""
import hashlib
import unittest

from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import editable_profile


class DependencyBundledGuidanceTests(unittest.TestCase):
    def test_promoted_guidance_bytes(self):
        result = api.validate_profile_directory(api.bundled_profile_directory("california_dependency"))
        self.assertIsNotNone(result.draft, result.issues)
        files = dict(result.draft.files)
        # Deliberate public instruction edits should explicitly update these baselines.
        expected = {
            "case-name.md": "ac60cda00e130e635e15cb7be406317b18a24c0416b7abf2a904b8792dfa016a",
            "classification-tasks.json": "ff5f02032aa081923badf4c40c5df19cb137af8be0c8a4512536fe0dbc97c189",
            "naming.json": "a8801e6912ee939a468d3cf8e18f4b8953aa25c696fcd13346f3f6585cc68b16",
            "reports.json": "f0ee91c592bcd555ba3b8e3f36f9835a9664b194a46195bdb8a02615c2d81c37",
        }
        for path, digest in expected.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(files[path]).hexdigest(), digest)

    def test_bundle_already_matches_current_editor_resources(self):
        bundled = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        self.assertEqual(bundled.manifest["schema_version"], 6)
        edited = editable_profile(bundled).snapshot()
        self.assertEqual(edited.files, bundled.files)
        self.assertEqual(set(bundled.manifest["resources"]), {
            "classification_tasks", "case_name", "naming", "hearings", "reports", "policies", "minutes",
        })
        self.assertEqual(bundled.resource("policies"), {})


if __name__ == "__main__":
    unittest.main()
