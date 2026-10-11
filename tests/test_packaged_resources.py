"""Keep declarative resources in standalone distribution metadata."""
import fnmatch
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackagedResourcesTests(unittest.TestCase):
    def test_every_bundled_profile_and_legacy_category_is_declared(self):
        declaration = (ROOT / "MANIFEST.in").read_text().split()
        self.assertEqual(declaration[:2], ["recursive-include", "recordprep/resources"])
        package = ROOT / "recordprep"
        included = {path for path in (ROOT / declaration[1]).rglob("*") if path.is_file()
                    and any(fnmatch.fnmatch(path.name, pattern) for pattern in declaration[2:])}
        required = {path for directory in ("practice_profiles", "summary_categories")
                    for path in (package / "resources" / directory).rglob("*") if path.is_file()}
        self.assertTrue(required)
        self.assertFalse(required - included, sorted(str(path.relative_to(package)) for path in required - included))


if __name__ == "__main__":
    unittest.main()
