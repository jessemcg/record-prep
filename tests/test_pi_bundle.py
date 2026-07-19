import json
import os
import tempfile
import unittest
from pathlib import Path

from recordprep.pi_bundle import (
    expected_organized_summary_path,
    expected_prepare_bundle_paths,
    legacy_organized_summary_path,
    pi_step_complete,
    prepare_bundle_complete,
    source_map_prerequisite_issues,
    validate_organized_summary_output,
    validate_pi_step_outputs,
    validate_prepare_bundle_outputs,
    validate_transcript_numbering_outputs,
)


class PiBundleTests(unittest.TestCase):
    def _build_valid_bundle(self, root: Path) -> None:
        (root / "artifacts").mkdir(parents=True)
        (root / "summaries").mkdir()
        (root / "text_pages").mkdir()
        (root / "text_pages/0001.txt").write_text("record page 1", encoding="utf-8")
        hearing = root / "summaries/hearings_sum_case.txt"
        reports = root / "summaries/reports_sum_case.txt"
        hearing.write_text("hearing", encoding="utf-8")
        reports.write_text("reports", encoding="utf-8")
        hearing_organized = root / "summaries/hearings_sum_case_organized.txt"
        reports_organized = root / "summaries/reports_sum_case_organized.txt"
        hearing_organized.write_text("organized hearing", encoding="utf-8")
        reports_organized.write_text("organized reports", encoding="utf-8")
        transcript = root / "artifacts/transcript_page_numbers.json"
        transcript.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "entries": [{}],
                    "citation_series": [],
                }
            ),
            encoding="utf-8",
        )
        series = root / "artifacts/transcript_page_number_series.md"
        series.write_text("# Series\n", encoding="utf-8")
        source_map = root / "artifacts/source_map.json"
        source_map.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pages": [],
                    "citation_series": [],
                }
            ),
            encoding="utf-8",
        )
        manifest = {
            "files": {
                "summarized_hearings": "summaries/hearings_sum_case.txt",
                "summarized_reports": "summaries/reports_sum_case.txt",
                "organized_hearings": "summaries/hearings_sum_case_organized.txt",
                "organized_reports": "summaries/reports_sum_case_organized.txt",
                "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
                "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
                "source_map": "artifacts/source_map.json",
            }
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        newest = max(
            hearing.stat().st_mtime,
            reports.stat().st_mtime,
            transcript.stat().st_mtime,
            series.stat().st_mtime,
        )
        os.utime(hearing_organized, (newest + 1, newest + 1))
        os.utime(reports_organized, (newest + 1, newest + 1))
        os.utime(source_map, (newest + 2, newest + 2))

    def test_valid_bundle_and_expected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            self.assertEqual(validate_prepare_bundle_outputs(root), [])
            self.assertTrue(prepare_bundle_complete(root))
            paths = expected_prepare_bundle_paths(root)
            self.assertEqual(
                paths["organized_hearings"].name,
                "hearings_sum_case_organized.txt",
            )
            for step_id in (
                "number_transcript_pages",
                "organize_hearing_summary",
                "organize_report_summary",
                "build_source_map",
            ):
                self.assertEqual(validate_pi_step_outputs(step_id, root), [])
                self.assertTrue(pi_step_complete(step_id, root))
            self.assertEqual(validate_transcript_numbering_outputs(root), [])
            self.assertEqual(validate_organized_summary_output(root, "reports"), [])
            self.assertEqual(source_map_prerequisite_issues(root), [])

    def test_stale_source_map_and_missing_manifest_key_are_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["files"]["organized_reports"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            source_map = root / "artifacts/source_map.json"
            os.utime(source_map, (1, 1))
            issues = validate_prepare_bundle_outputs(root)
            self.assertIn(
                "manifest.json files.organized_reports must be "
                "summaries/reports_sum_case_organized.txt.",
                issues,
            )
            self.assertIn("source_map.json is stale.", issues)
            self.assertFalse(prepare_bundle_complete(root))

    def test_report_name_ending_in_period_has_only_one_period_before_organized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "summaries").mkdir()
            source = root / "summaries/reports_sum_In_re_M.S-D..txt"
            source.write_text("reports", encoding="utf-8")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "files": {
                            "summarized_reports": source.relative_to(root).as_posix(),
                        }
                    }
                ),
                encoding="utf-8",
            )

            expected = expected_organized_summary_path(root, "reports")
            legacy = legacy_organized_summary_path(root, "reports")

            self.assertIsNotNone(expected)
            self.assertIsNotNone(legacy)
            self.assertEqual(
                expected.name,
                "reports_sum_In_re_M.S-D._organized.txt",
            )
            self.assertEqual(
                legacy.name,
                "reports_sum_In_re_M.S-D.._organized.txt",
            )


if __name__ == "__main__":
    unittest.main()
