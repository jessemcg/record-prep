import json
import os
import tempfile
import unittest
from pathlib import Path

from recordprep.pi_bundle import (
    expected_prepare_bundle_paths,
    pi_step_complete,
    prepare_bundle_complete,
    source_map_prerequisite_issues,
    validate_case_overview_output,
    validate_participant_index_output,
    validate_pi_step_outputs,
    validate_prepare_bundle_outputs,
    validate_summary_source_outputs,
    validate_transcript_numbering_outputs,
)


def _case_overview_text() -> str:
    return """---
artifact: recordprep-case-overview
schema_version: 1
status: nonauthoritative-orientation
---

# Case Overview

> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.

## Parties and Roles

The synthetic record concerns one child and two parents. The available summaries distinguish the parents from relatives, service providers, and agency personnel without attempting to list every participant or attorney.

## Procedural Posture

The summarized matter proceeds through initial detention, later review, and a final recorded order. This overview describes only the posture reflected in the supplied summaries and does not determine the merits of any claim.

## Key Events

- January 2, 2025: The court conducted the first summarized proceeding.
- February 3, 2025: A report supplied additional family and service information.
- March 4, 2025: The court reviewed progress and issued another summarized order.
- April 5, 2025: The available summaries describe the final included event.

## Principal Issues

The apparent issues concern placement, participation in services, family contact, and the orders made at the summarized proceedings. Any issue omitted from the summaries may still appear in the underlying source pages.

## Record Scope

The available material includes summarized hearings, reports, and minute orders from January through April 2025. The overview does not establish that the bundle is complete, and all details require verification against mapped source pages.
"""


class PiBundleTests(unittest.TestCase):
    def _build_valid_bundle(self, root: Path) -> None:
        (root / "artifacts").mkdir(parents=True)
        (root / "summaries").mkdir()
        (root / "text_pages").mkdir()
        (root / "text_pages/0001.txt").write_text("record page 1", encoding="utf-8")
        hearing = root / "summaries/hearings_sum_case.txt"
        reports = root / "summaries/reports_sum_case.txt"
        hearing.write_text("hearing summary", encoding="utf-8")
        reports.write_text("report summary", encoding="utf-8")
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
                                {
                                    "text_path": "text_pages/0001.txt",
                                    "file_page": 1,
                                    "citation_label": "",
                                    "citation_key": "",
                                    "note": "Explicit no-witness index.",
                                }
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
        overview = root / "artifacts/case_overview.md"
        overview.write_text(_case_overview_text(), encoding="utf-8")
        source_map = root / "artifacts/source_map.json"
        source_map.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "paths": {"case_overview": "artifacts/case_overview.md"},
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
                "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
                "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
                "participant_index": "artifacts/participant_index.json",
                "case_overview": "artifacts/case_overview.md",
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
        os.utime(overview, (newest + 1, newest + 1))
        os.utime(source_map, (newest + 2, newest + 2))

    def test_valid_bundle_and_expected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            self.assertEqual(validate_prepare_bundle_outputs(root), [])
            self.assertTrue(prepare_bundle_complete(root))
            self.assertEqual(
                expected_prepare_bundle_paths(root)["case_overview"].name,
                "case_overview.md",
            )
            for step_id in (
                "number_transcript_pages",
                "build_participant_index",
                "create_case_overview",
                "build_source_map",
            ):
                self.assertEqual(validate_pi_step_outputs(step_id, root), [])
                self.assertTrue(pi_step_complete(step_id, root))
            self.assertEqual(validate_transcript_numbering_outputs(root), [])
            self.assertEqual(validate_summary_source_outputs(root), [])
            self.assertEqual(validate_case_overview_output(root), [])
            self.assertEqual(source_map_prerequisite_issues(root), [])

    def test_case_overview_requires_versioning_word_count_and_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            overview = root / "artifacts/case_overview.md"
            overview.write_text("# Case Overview\n\nToo short.\n", encoding="utf-8")

            malformed = validate_case_overview_output(root)

            self.assertTrue(any("missing required versioning" in issue for issue in malformed))
            self.assertTrue(any("at least 150 prose words" in issue for issue in malformed))

            overview.write_text(_case_overview_text(), encoding="utf-8")
            participant = root / "artifacts/participant_index.json"
            future = overview.stat().st_mtime + 2
            os.utime(participant, (future, future))

            self.assertIn(
                "artifacts/case_overview.md is stale.",
                validate_case_overview_output(root),
            )

    def test_stale_source_map_and_missing_manifest_key_are_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["files"]["case_overview"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            source_map = root / "artifacts/source_map.json"
            os.utime(source_map, (1, 1))

            issues = validate_prepare_bundle_outputs(root)

            self.assertIn(
                "manifest.json files.case_overview must be artifacts/case_overview.md.",
                issues,
            )
            self.assertIn("source_map.json is stale.", issues)
            self.assertFalse(prepare_bundle_complete(root))

    def test_source_summaries_are_required_without_organized_derivatives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._build_valid_bundle(root)
            (root / "summaries/reports_sum_case.txt").unlink()

            issues = validate_summary_source_outputs(root)

            self.assertIn("the source report summary is missing or ambiguous.", issues)

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


if __name__ == "__main__":
    unittest.main()
