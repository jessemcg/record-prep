import json
import tempfile
import unittest
from pathlib import Path

from recordprep import manifest


class SummaryLinkTests(unittest.TestCase):
    """Legacy inline-link support lives in editions/Focus; the Add-links
    pipeline step itself was retired with the digest-first summaries."""

    def test_manifest_omits_removed_consolidated_summary_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case_bundle"
            root.mkdir()

            manifest._write_manifest(root, [])

            payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

        self.assertIn("summarized_hearings", payload["files"])
        self.assertIn("summarized_reports", payload["files"])
        self.assertNotIn("consolidated_hearings", payload["files"])
        self.assertNotIn("consolidated_reports", payload["files"])


if __name__ == "__main__":
    unittest.main()
