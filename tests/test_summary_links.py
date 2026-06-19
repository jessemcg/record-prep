import json
import tempfile
import threading
import unittest
from pathlib import Path

import recordprep


class SummaryLinkTests(unittest.TestCase):
    def test_add_page_links_uses_regular_summary_text_and_is_idempotent(self) -> None:
        hearing_text = "\n".join(
            [
                "Hearings Summary",
                "",
                "January 5, 2024",
                "",
                "Mother appeared and requested services.",
                "",
                "January 7, 2024 [Hearing](page:0099)",
                "",
                "The court set review. [:M](page:0098)",
            ]
        )
        hearing_entries = [
            {"date": "January 5, 2024", "start_page": "12"},
            {"date": "January 7, 2024", "start_page": "14"},
        ]
        minute_entries = [
            {"date": "January 5, 2024", "start_page": "13"},
            {"date": "January 6, 2024", "start_page": "15"},
        ]

        linked_hearings, modified, inserted = (
            recordprep._add_page_links_to_hearing_summary_text(
                hearing_text,
                hearing_entries,
                minute_entries,
            )
        )

        self.assertEqual(modified, 2)
        self.assertEqual(inserted, 1)
        self.assertIn(
            "January 5, 2024 [Hearing](page:0012) [Minute Order](page:0013)",
            linked_hearings,
        )
        self.assertIn("January 6, 2024 [Minute Order](page:0015)", linked_hearings)
        self.assertIn("January 7, 2024 [Hearing](page:0014)", linked_hearings)
        self.assertNotIn("[:M](page:0098)", linked_hearings)

        rerun_hearings, rerun_modified, rerun_inserted = (
            recordprep._add_page_links_to_hearing_summary_text(
                linked_hearings,
                hearing_entries,
                minute_entries,
            )
        )

        self.assertEqual(rerun_hearings, linked_hearings)
        self.assertEqual(rerun_modified, 3)
        self.assertEqual(rerun_inserted, 0)

    def test_add_links_step_leaves_report_summary_unchanged(self) -> None:
        class DummyRow:
            def set_sensitive(self, _value: bool) -> None:
                pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case_bundle"
            (root / "summaries").mkdir(parents=True)
            (root / "artifacts").mkdir()
            (root / "case_name.txt").write_text("Test_Case", encoding="utf-8")
            summaries_path, reports_path = recordprep._summary_output_paths(root)
            summaries_path.write_text(
                "January 5, 2024\n\nThe hearing happened.",
                encoding="utf-8",
            )
            report_text = "Jurisdiction Report\n\nThe report described placement."
            reports_path.write_text(report_text, encoding="utf-8")
            (root / "artifacts" / "hearing_boundaries.json").write_text(
                json.dumps([{"date": "January 5, 2024", "start_page": "12"}]),
                encoding="utf-8",
            )
            (root / "artifacts" / "minutes_boundaries.json").write_text(
                "[]",
                encoding="utf-8",
            )

            window = recordprep.RecordPrepWindow.__new__(recordprep.RecordPrepWindow)
            window.selected_pdfs = []
            window._stop_event = threading.Event()
            window.step_add_hearing_date_links_row = DummyRow()
            window._resolve_case_root = lambda: root

            self.assertTrue(window._run_step_add_hearing_date_links())

            self.assertIn(
                "January 5, 2024 [Hearing](page:0012)",
                summaries_path.read_text(encoding="utf-8"),
            )
            self.assertEqual(reports_path.read_text(encoding="utf-8"), report_text)

    def test_manifest_omits_removed_consolidated_summary_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "case_bundle"
            root.mkdir()

            recordprep._write_manifest(root, [])

            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

        self.assertIn("summarized_hearings", manifest["files"])
        self.assertIn("summarized_reports", manifest["files"])
        self.assertNotIn("consolidated_hearings", manifest["files"])
        self.assertNotIn("consolidated_reports", manifest["files"])


if __name__ == "__main__":
    unittest.main()
