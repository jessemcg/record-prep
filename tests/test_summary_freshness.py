"""Current-generation freshness tests for the summary stages.

All fixtures are synthetic; no real case material appears here.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from recordprep import summary_agents as sa
from tests.summary_agent_fixtures import publish_valid_summary
from tests.test_summary_agent_pipeline import BundleBuilder

PROJECT_PI_DIR = sa.DEFAULT_PROJECT_PI_DIR


class FreshnessTests(unittest.TestCase):
    def _build_bundle(self, root: Path) -> None:
        builder = BundleBuilder(root)
        builder.add_pages(1, 2, "h1")
        builder.add_pages(3, 4, "r1")
        builder.finish(
            hearings=[(1, 2, "March 3, 2025")],
            reports=[(3, 4, "April 4, 2025", "Report")],
        )

    def _publish_fresh(self, root: Path) -> None:
        publish_valid_summary(
            root,
            "hearings",
            [  # type: ignore[list-item]
                __import__(
                    "tests.summary_agent_fixtures",
                    fromlist=["synthetic_facts_row"],
                ).synthetic_facts_row("hearings", start=1, end=2)
            ],
            "Hearings Summary\n\nMarch 3, 2025 — Hearing\n\nProse.\n",
        )
        fixtures = __import__(
            "tests.summary_agent_fixtures", fromlist=["synthetic_facts_row"]
        )
        publish_valid_summary(
            root,
            "reports",
            [fixtures.synthetic_facts_row("reports", start=3, end=4)],
            "Reports Summary\n\nApril 4, 2025 - Report\n\nProse.\n",
        )

    def test_fresh_bundle_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            status = sa.summary_stage_status(root, "hearings", use_cache=False)
            self.assertEqual(status.integrity_issues, ())
            self.assertEqual(status.freshness_issues, ())
            self.assertTrue(status.complete)
            reports = sa.summary_stage_status(root, "reports", use_cache=False)
            self.assertTrue(reports.complete)

    def test_participant_change_stales_only_hearings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            index_path = root / "artifacts" / "participant_index.json"
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            payload["hearings"][0]["counsel"] = [
                {
                    "role_id": "county_counsel",
                    "name": "Synthetic Counsel",
                    "appearance_status": "appeared",
                }
            ]
            index_path.write_text(json.dumps(payload), encoding="utf-8")

            hearings = sa.summary_stage_status(root, "hearings", use_cache=False)
            self.assertTrue(
                any("hearing:0001" in issue for issue in hearings.freshness_issues)
            )
            reports = sa.summary_stage_status(root, "reports", use_cache=False)
            self.assertEqual(reports.freshness_issues, ())
            self.assertTrue(reports.complete)
            self.assertFalse(hearings.complete)

    def test_effective_model_change_stales_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            staged_pi = Path(temporary) / ".pi"
            staged_pi.mkdir()
            (staged_pi / "settings.json").write_text(
                json.dumps(
                    {
                        "defaultProvider": "other",
                        "defaultModel": "accounts/other/models/other-model",
                    }
                ),
                encoding="utf-8",
            )
            issues = sa.summary_stage_freshness_issues(
                root, "hearings", project_dir=staged_pi
            )
            self.assertTrue(
                any("regeneration-pending" in issue for issue in issues), issues
            )

    def test_schema3_metadata_is_readable_but_freshness_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            final_meta_path = sa.summary_final_meta_path(root, "hearings")
            meta = json.loads(final_meta_path.read_text(encoding="utf-8"))
            meta["schema_version"] = 3
            meta.pop("synthesis_config_sha256", None)
            final_meta_path.write_text(json.dumps(meta), encoding="utf-8")

            issues = sa.summary_stage_freshness_issues(root, "hearings")
            self.assertTrue(
                any("predates dependency fingerprints" in issue for issue in issues)
            )
            # Readable, not corrupt: integrity validation stays clean.
            self.assertEqual(sa.validate_final_meta(root, "hearings"), [])

    def test_synthesis_config_change_flags_final_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            final_meta_path = sa.summary_final_meta_path(root, "hearings")
            meta = json.loads(final_meta_path.read_text(encoding="utf-8"))
            meta["synthesis_config_sha256"] = "0" * 64
            final_meta_path.write_text(json.dumps(meta), encoding="utf-8")
            issues = sa.summary_stage_freshness_issues(root, "hearings")
            self.assertTrue(
                any(
                    "synthesized under a different configuration" in issue
                    for issue in issues
                ),
                issues,
            )

    def test_duplicate_item_ids_and_overlapping_ranges_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "a")
            builder.add_pages(2, 3, "b")
            builder.finish(
                hearings=[(1, 2, "March 3, 2025"), (2, 3, "April 4, 2025")],
                reports=[],
            )
            with self.assertRaisesRegex(ValueError, "overlaps"):
                sa.build_work_items(root, sa.effective_extraction_config(PROJECT_PI_DIR, "hearings"))

    def test_status_cache_invalidates_on_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_bundle(root)
            self._publish_fresh(root)
            first = sa.summary_stage_status(root, "hearings")
            self.assertTrue(first.complete)
            # Same-signature read is served from the snapshot cache.
            cached = sa.summary_stage_status(root, "hearings")
            self.assertIs(first, cached)
            # A source-page change invalidates the snapshot.
            page = root / "text_pages" / "0001.txt"
            page.write_text(page.read_text(encoding="utf-8") + " appended.\n")
            second = sa.summary_stage_status(root, "hearings")
            self.assertIsNot(first, second)
            self.assertFalse(second.complete)


if __name__ == "__main__":
    unittest.main()
