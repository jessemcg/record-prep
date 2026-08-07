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
    validate_participant_index_output,
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
        participant_index = root / "artifacts/participant_index.json"
        participant_index.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "source": "record-participant-index",
                    "hearings": [
                        {
                            "id": "hearing:0001",
                            "start_page": 1,
                            "end_page": 1,
                            "witness_status": "none",
                            "witness_evidence": [
                                {"text_path": "text_pages/0001.txt", "file_page": 1, "citation_label": "", "citation_key": "", "note": "Explicit no-witness index."}
                            ],
                            "counsel": [],
                            "participants": [],
                            "witnesses": [],
                            "warnings": [],
                        }
                    ],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )
        source_map = root / "artifacts/source_map.json"
        source_map.write_text(
            json.dumps(
                {
                    "schema_version": 2,
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
                "participant_index": "artifacts/participant_index.json",
                "source_map": "artifacts/source_map.json",
            }
        }
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        newest = max(
            hearing.stat().st_mtime,
            reports.stat().st_mtime,
            transcript.stat().st_mtime,
            series.stat().st_mtime,
            participant_index.stat().st_mtime,
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
                "build_participant_index",
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

    def test_organized_summaries_require_blank_lines_before_date_boundaries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            hearing = root / "summaries/hearings_sum_case_organized.txt"
            reports = root / "summaries/reports_sum_case_organized.txt"
            hearing.write_text(
                "Hearings Summary\n\n"
                "January 5, 2026 [Hearing](page:0001)\n\n"
                "First hearing summary.\n"
                "February 6, 2026 [Hearing](page:0002)\n",
                encoding="utf-8",
            )
            reports.write_text(
                "Reports Summary\n\n"
                "January 5, 2026 - Detention Report\n\n"
                "First report summary.\n"
                "February 6, 2026 - Jurisdiction Report\n",
                encoding="utf-8",
            )
            fresh_time = max(
                (root / "summaries/hearings_sum_case.txt").stat().st_mtime,
                (root / "summaries/reports_sum_case.txt").stat().st_mtime,
            ) + 2
            os.utime(hearing, (fresh_time, fresh_time))
            os.utime(reports, (fresh_time, fresh_time))

            self.assertIn(
                "missing before line(s): 6",
                validate_organized_summary_output(root, "hearings")[0],
            )
            self.assertIn(
                "missing before line(s): 6",
                validate_organized_summary_output(root, "reports")[0],
            )

            hearing.write_text(
                hearing.read_text(encoding="utf-8").replace(
                    "First hearing summary.\nFebruary",
                    "First hearing summary.\n\nFebruary",
                ),
                encoding="utf-8",
            )
            reports.write_text(
                reports.read_text(encoding="utf-8").replace(
                    "First report summary.\nFebruary",
                    "First report summary.\n\nFebruary",
                ),
                encoding="utf-8",
            )
            os.utime(hearing, (fresh_time, fresh_time))
            os.utime(reports, (fresh_time, fresh_time))

            self.assertEqual(validate_organized_summary_output(root, "hearings"), [])
            self.assertEqual(validate_organized_summary_output(root, "reports"), [])

    def test_participant_index_rejects_inferred_witnesses_and_counsel_confusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts").mkdir()
            payload = {
                "schema_version": 2,
                "source": "record-participant-index",
                "hearings": [{
                    "id": "hearing:0001",
                    "start_page": 10,
                    "end_page": 20,
                    "witness_status": "none",
                    "counsel": [{"role_id": "mothers_counsel", "name": "Jane Smith"}],
                    "participants": [],
                    "witnesses": [{
                        "id": "witness:1",
                        "name": "Jane Smith",
                        "examinations": [{"start_file_page": 21, "end_file_page": 22}],
                    }],
                }],
            }
            (root / "artifacts/participant_index.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )

            issues = validate_participant_index_output(root)

            self.assertTrue(any("cannot list witnesses when status is none" in issue for issue in issues))
            self.assertTrue(any("lists counsel as a witness" in issue for issue in issues))
            self.assertTrue(any("outside its page range" in issue for issue in issues))

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
