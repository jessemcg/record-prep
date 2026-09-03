"""Focused tests for the three independently runnable summary steps.

Synthetic only: no real case material. These tests cover the run-until
migration of the retired aggregate summary target, per-category completion
predicates, and category isolation: rerunning one summary category rewrites
only its own output file.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep.ui.main_window import (
    CONFIG_KEY_RUN_UNTIL_STEP,
    CONFIG_KEY_SUMMARIZE_API_KEY,
    CONFIG_KEY_SUMMARIZE_API_URL,
    CONFIG_KEY_SUMMARIZE_MODEL_ID,
    StopRequested,
    _minutes_summary_output_path,
    _summary_output_paths,
    load_run_until_step_setting,
    RecordPrepWindow,
)


def _idle_now(callback, *args):
    callback(*args)
    return 1


def _make_harness(root: Path, stop_after: int = 0) -> mock.Mock:
    harness = mock.Mock()
    harness.selected_pdfs = []
    harness._resolve_case_root.return_value = root
    stop_calls = 0

    def raise_if_requested():
        nonlocal stop_calls
        stop_calls += 1
        if stop_after and stop_calls > stop_after:
            raise StopRequested()

    harness._raise_if_stop_requested.side_effect = raise_if_requested
    harness._request_plain_text.return_value = "Synthetic summary paragraph."
    # Bind the real shared summary-step preparation onto the harness.
    harness._prepare_summary_step = RecordPrepWindow._prepare_summary_step.__get__(
        harness, RecordPrepWindow
    )
    return harness


def _build_bundle(temporary: str, *, participant_index: bool = True) -> Path:
    root = Path(temporary) / "case_bundle"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir(parents=True)
    (root / "case_name.txt").write_text("IsoCase", encoding="utf-8")
    (root / "text_pages/0001.txt").write_text(
        "Hearing page one.\nTHE COURT: Good morning.", encoding="utf-8"
    )
    (root / "text_pages/0002.txt").write_text(
        "Report and minute-order page two.", encoding="utf-8"
    )
    transcript = {
        "schema_version": 2,
        "entries": [
            {"file_page": 1, "citation_label": "RT 1"},
            {"file_page": 2, "citation_label": "RT 2"},
        ],
    }
    (root / "artifacts/transcript_page_numbers.json").write_text(
        json.dumps(transcript), encoding="utf-8"
    )
    (root / "artifacts/hearing_boundaries.json").write_text(
        json.dumps(
            [{"date": "March 3, 2025", "start_page": "0001", "end_page": "0001"}]
        ),
        encoding="utf-8",
    )
    (root / "artifacts/report_boundaries.json").write_text(
        json.dumps(
            [
                {
                    "report_name": "Detention Report",
                    "report_date": "March 3, 2025",
                    "report_label": "Detention Report March 3, 2025",
                    "start_page": "0002",
                    "end_page": "0002",
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "artifacts/minutes_boundaries.json").write_text(
        json.dumps(
            [{"date": "March 3, 2025", "start_page": "0002", "end_page": "0002"}]
        ),
        encoding="utf-8",
    )
    if participant_index:
        hearing = {
            "id": "hearing:0001",
            "start_page": 1,
            "end_page": 1,
            "warnings": ["Hearing reviewed synthetically."],
            "witness_status": "none",
            "witness_evidence": [
                {
                    "text_path": "text_pages/0001.txt",
                    "file_page": 1,
                    "citation_label": "RT 1",
                    "citation_key": "RT:1",
                    "note": "Explicit no-witness index.",
                }
            ],
            "witnesses": [],
            "counsel": [],
            "participants": [],
        }
        (root / "artifacts/participant_index.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "source": "record-participant-index",
                    "warnings": [],
                    "hearings": [hearing],
                }
            ),
            encoding="utf-8",
        )
    return root


def _seed_summaries(root: Path) -> tuple[Path, Path, Path]:
    summaries_dir = root / "summaries"
    summaries_dir.mkdir(exist_ok=True)
    hearings, reports = _summary_output_paths(root)
    minutes = _minutes_summary_output_path(root)
    hearings.write_text("OLD HEARINGS", encoding="utf-8")
    reports.write_text("OLD REPORTS", encoding="utf-8")
    minutes.write_text("OLD MINUTES", encoding="utf-8")
    return hearings, reports, minutes


class RunUntilMigrationTests(unittest.TestCase):
    def test_retired_and_aggregate_summary_targets_migrate_to_minute_orders(self) -> None:
        for legacy in (
            "create_summaries",
            "create_raw",
            "create_preoptimized",
            "create_optimized",
        ):
            with tempfile.TemporaryDirectory() as temporary:
                config_path = Path(temporary) / "config.json"
                with mock.patch(
                    "recordprep.ui.main_window.CONFIG_FILE", config_path
                ):
                    config_path.write_text(
                        json.dumps({CONFIG_KEY_RUN_UNTIL_STEP: legacy}),
                        encoding="utf-8",
                    )
                    self.assertEqual(
                        load_run_until_step_setting(),
                        "create_minute_order_summaries",
                    )
                    self.assertEqual(
                        json.loads(config_path.read_text(encoding="utf-8"))[
                            CONFIG_KEY_RUN_UNTIL_STEP
                        ],
                        "create_minute_order_summaries",
                    )

    def test_current_summary_targets_are_not_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                for step_id in (
                    "create_hearing_summaries",
                    "create_report_summaries",
                    "create_minute_order_summaries",
                ):
                    config_path.write_text(
                        json.dumps({CONFIG_KEY_RUN_UNTIL_STEP: step_id}),
                        encoding="utf-8",
                    )
                    self.assertEqual(load_run_until_step_setting(), step_id)


class SummaryCompletionTests(unittest.TestCase):
    def test_each_summary_step_observes_only_its_own_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            hearings, reports, minutes = _seed_summaries(root)

            def complete(step_id: str) -> bool:
                return RecordPrepWindow._step_artifact_complete(
                    mock.Mock(), step_id, root, []
                )

            self.assertTrue(complete("create_hearing_summaries"))
            self.assertTrue(complete("create_report_summaries"))
            self.assertTrue(complete("create_minute_order_summaries"))

            hearings.unlink()
            self.assertFalse(complete("create_hearing_summaries"))
            self.assertTrue(complete("create_report_summaries"))
            self.assertTrue(complete("create_minute_order_summaries"))

            reports.unlink()
            self.assertFalse(complete("create_hearing_summaries"))
            self.assertFalse(complete("create_report_summaries"))
            self.assertTrue(complete("create_minute_order_summaries"))

            minutes.unlink()
            self.assertFalse(complete("create_hearing_summaries"))
            self.assertFalse(complete("create_report_summaries"))
            self.assertFalse(complete("create_minute_order_summaries"))


class SummaryStepIsolationTests(unittest.TestCase):
    def _run(self, harness: mock.Mock, handler_name: str) -> bool:
        with tempfile.TemporaryDirectory() as config_temporary:
            config_path = Path(config_temporary) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        CONFIG_KEY_SUMMARIZE_API_URL: "http://localhost:9999/v1/chat",
                        CONFIG_KEY_SUMMARIZE_MODEL_ID: "synthetic-model",
                        CONFIG_KEY_SUMMARIZE_API_KEY: "synthetic-key",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ), mock.patch(
                "recordprep.ui.main_window.GLib.idle_add", side_effect=_idle_now
            ):
                handler = getattr(RecordPrepWindow, handler_name)
                return handler(harness)

    def test_rerunning_hearings_preserves_report_and_minute_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            hearings, reports, minutes = _seed_summaries(root)
            harness = _make_harness(root)

            self.assertTrue(
                self._run(harness, "_run_step_create_hearing_summaries")
            )

            self.assertNotEqual(
                hearings.read_text(encoding="utf-8"), "OLD HEARINGS"
            )
            self.assertIn("Hearings Summary", hearings.read_text(encoding="utf-8"))
            self.assertEqual(reports.read_text(encoding="utf-8"), "OLD REPORTS")
            self.assertEqual(minutes.read_text(encoding="utf-8"), "OLD MINUTES")
            self.assertEqual(
                harness._safe_update_manifest.call_args.args[1][
                    "last_completed_step"
                ],
                "create_hearing_summaries",
            )
            harness.show_toast.assert_called_with(
                "Create hearing summaries complete."
            )

    def test_rerunning_reports_preserves_hearing_and_minute_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            hearings, reports, minutes = _seed_summaries(root)
            harness = _make_harness(root)

            self.assertTrue(
                self._run(harness, "_run_step_create_report_summaries")
            )

            self.assertEqual(hearings.read_text(encoding="utf-8"), "OLD HEARINGS")
            self.assertNotEqual(
                reports.read_text(encoding="utf-8"), "OLD REPORTS"
            )
            self.assertIn("Reports Summary", reports.read_text(encoding="utf-8"))
            self.assertEqual(minutes.read_text(encoding="utf-8"), "OLD MINUTES")
            self.assertEqual(
                harness._safe_update_manifest.call_args.args[1][
                    "last_completed_step"
                ],
                "create_report_summaries",
            )
            harness.show_toast.assert_called_with(
                "Create report summaries complete."
            )

    def test_rerunning_minutes_preserves_hearing_and_report_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            hearings, reports, minutes = _seed_summaries(root)
            harness = _make_harness(root)

            self.assertTrue(
                self._run(harness, "_run_step_create_minute_order_summaries")
            )

            self.assertEqual(hearings.read_text(encoding="utf-8"), "OLD HEARINGS")
            self.assertEqual(reports.read_text(encoding="utf-8"), "OLD REPORTS")
            self.assertNotEqual(
                minutes.read_text(encoding="utf-8"), "OLD MINUTES"
            )
            self.assertIn("Minutes Summary", minutes.read_text(encoding="utf-8"))
            self.assertEqual(
                harness._safe_update_manifest.call_args.args[1][
                    "last_completed_step"
                ],
                "create_minute_order_summaries",
            )
            harness.show_toast.assert_called_with(
                "Create minute-order summaries complete."
            )

    def test_report_and_minute_runs_do_not_require_participant_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(
                temporary, participant_index=False
            )
            harness = _make_harness(root)

            self.assertTrue(
                self._run(harness, "_run_step_create_report_summaries")
            )
            self.assertTrue(
                self._run(harness, "_run_step_create_minute_order_summaries")
            )

    def test_hearing_run_requires_participant_index_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary, participant_index=False)
            hearings, _reports, _minutes = _seed_summaries(root)
            harness = _make_harness(root)

            self.assertFalse(
                self._run(harness, "_run_step_create_hearing_summaries")
            )

            self.assertEqual(hearings.read_text(encoding="utf-8"), "OLD HEARINGS")
            harness._safe_update_manifest.assert_not_called()
            self.assertIn(
                "Participant index validation failed",
                harness.show_toast.call_args.args[0],
            )

    def test_hearing_stop_preserves_existing_file_and_blocks_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = _build_bundle(temporary)
            hearings, _reports, _minutes = _seed_summaries(root)
            # First call passes in _prepare_summary_step; second call is the
            # hearing loop guard, then the window guard raises.
            harness = _make_harness(root, stop_after=2)

            completed = self._run(harness, "_run_step_create_hearing_summaries")

            self.assertFalse(completed)
            self.assertEqual(hearings.read_text(encoding="utf-8"), "OLD HEARINGS")
            harness._safe_update_manifest.assert_not_called()
            finish_success = harness._finish_step.call_args.args[-1]
            self.assertIsNone(finish_success)


if __name__ == "__main__":
    unittest.main()
