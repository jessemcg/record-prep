import json
import tempfile
import unittest
from pathlib import Path

from recordprep.transcript_layout import apply_manual_override
from unittest import mock

from recordprep.ui.main_window import (
    NO_RESOLVED_LAYOUT_STEP_IDS,
    PIPELINE_PHASES,
    PIPELINE_STEP_PHASE,
    SETTINGS_NAV_GROUPS,
    TEST_PROMPT_GROUPS,
    VISION_CLASSIFICATION_STEP_IDS,
    _case_context_matches_selection,
    _correct_toc_lines,
    case_identity_conflicts,
    _first_incomplete_phase_id,
    RecordPrepWindow,
    _layout_matches_legacy,
    _pipeline_split_validation_message,
    _participant_review_progress,
    _phase_progress_text,
    _read_pi_stage_status,
    _sanitize_terminal_log_text,
    _settings_destination_keys,
    _step_requires_resolved_layout,
    _terminal_log_line,
    _test_prompt_input_kind,
    StopRequested,
    _test_prompt_options,
    _transcript_summary,
    _write_manifest,
)


class MainWindowUiStateTests(unittest.TestCase):
    def test_pipeline_steps_are_grouped_once_in_pipeline_order(self) -> None:
        grouped = [
            step_id
            for _phase_id, _title, step_ids in PIPELINE_PHASES
            for step_id in step_ids
        ]

        self.assertEqual(len(grouped), 22)
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertEqual(set(grouped), set(PIPELINE_STEP_PHASE))
        self.assertEqual(grouped[0], "create_files")
        self.assertEqual(grouped[1], "detect_transcript_layout")
        self.assertEqual(grouped[2], "strip_characters")
        self.assertEqual(grouped[-9:],
            [
                "number_transcript_pages",
                "build_participant_index",
                "create_hearing_summaries",
                "create_report_summaries",
                "create_minute_order_summaries",
                "add_hearing_date_links",
                "build_summary_editions",
                "create_case_overview",
                "build_source_map",
            ],
        )
        self.assertEqual(PIPELINE_PHASES[-1][1], "Agent Search")
        self.assertEqual(
            PIPELINE_STEP_PHASE["detect_transcript_layout"],
            PIPELINE_STEP_PHASE["create_files"],
        )
        self.assertNotIn("detect_transcript_layout", VISION_CLASSIFICATION_STEP_IDS)

    def test_resume_uses_selected_run_through_target(self) -> None:
        root = Path("/tmp/recordprep-resume-test")
        row = mock.Mock()
        row.get_title.return_value = "Classification basic"
        handler = mock.Mock()
        harness = mock.Mock()
        harness._pipeline_running = False
        harness.selected_pdfs = []
        harness._resolve_case_root.return_value = root
        harness._selected_run_until_step.return_value = "classify_names"
        harness._resume_start_index.return_value = 0
        harness._pipeline_steps.return_value = [
            ("classify_basic", row, handler)
        ]
        harness._require_resolved_layout.return_value = True
        harness._run_until_dropdown = None

        with mock.patch("recordprep.ui.main_window.threading.Thread") as thread:
            RecordPrepWindow.on_resume_clicked(harness, mock.Mock())

        harness._resume_start_index.assert_called_once_with(
            root, "classify_names"
        )
        thread.assert_called_once_with(
            target=harness._run_steps_from_index,
            args=(0, root, "classify_names", True),
            daemon=True,
        )
        thread.return_value.start.assert_called_once_with()

    def test_case_identity_guard_warns_without_renaming(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "B355972_Desmond_P" / "0_record"
            root = base / "case_bundle"
            root.mkdir(parents=True)
            (base / "B355785_combined_record.pdf").write_bytes(b"pdf")
            (root / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../B355785_combined_record.pdf"]}),
                encoding="utf-8",
            )
            (root / "case_name.txt").write_text(
                "In_re_Keiven_L.", encoding="utf-8"
            )

            warnings = case_identity_conflicts(root)

            self.assertEqual(len(warnings), 1)
            self.assertIn("B355972", warnings[0])
            self.assertIn("B355785", warnings[0])
            self.assertIn("no files will be moved or renamed", warnings[0])
            self.assertTrue(root.is_dir())

    def test_case_identity_guard_accepts_matching_case_number(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "B355785_Keiven_L" / "0_record"
            root = base / "case_bundle"
            root.mkdir(parents=True)
            (root / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../B355785_combined_record.pdf"]}),
                encoding="utf-8",
            )

            self.assertEqual(case_identity_conflicts(root), [])

    def test_participant_activity_counts_reviewed_hearings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts").mkdir()
            hearings = []
            for index in range(44):
                hearings.append(
                    {
                        "id": f"hearing:{index + 1:04d}",
                        "warnings": (
                            ["Hearing reviewed."]
                            if index < 12
                            else ["Participant review has not been completed."]
                        ),
                    }
                )
            (root / "artifacts/participant_index.json").write_text(
                json.dumps({"hearings": hearings}), encoding="utf-8"
            )

            self.assertEqual(_participant_review_progress(root), (12, 44))

    def test_stage_status_ignores_foreign_runner_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "temp").mkdir()
            status = {
                "artifact": "recordprep-pi-stage-status",
                "schema_version": 1,
                "stage": "build_participant_index",
                "state": "stalled",
                "runner_pid": 123,
                "pi_pid": 456,
                "message": "No session activity while PI is using CPU.",
            }
            (root / "temp/.pi_stage_status.json").write_text(
                json.dumps(status), encoding="utf-8"
            )

            self.assertEqual(_read_pi_stage_status(root, 123), status)
            self.assertIsNone(_read_pi_stage_status(root, 999))

    def test_failed_or_stopped_stage_prevents_downstream_start(self) -> None:
        first_handler = mock.Mock(return_value=False)
        second_handler = mock.Mock(return_value=True)
        harness = mock.Mock()
        harness.selected_pdfs = []
        harness._pipeline_steps.return_value = [
            ("build_participant_index", mock.Mock(), first_handler),
            ("create_hearing_summaries", mock.Mock(), second_handler),
        ]
        harness._run_until_label.return_value = "end"
        harness._run_until_dropdown = None

        def idle_now(callback, *args):
            callback(*args)
            return 1

        with mock.patch(
            "recordprep.ui.main_window.load_classifier_settings",
            return_value={"local_vision_enabled": False},
        ), mock.patch(
            "recordprep.ui.main_window.GLib.idle_add", side_effect=idle_now
        ):
            RecordPrepWindow._run_steps_from_index(harness, 0, Path("/tmp/bundle"))

        first_handler.assert_called_once_with()
        second_handler.assert_not_called()
        harness._finish_run_all.assert_called_once_with(False)

    def test_stop_completion_clears_working_state_and_reports_stopped(self) -> None:
        harness = mock.Mock()
        harness._stop_event.is_set.return_value = True
        harness._pipeline_running = True
        harness._run_until_dropdown = None
        harness._run_pause_message = None
        harness._run_completion_message = None

        RecordPrepWindow._finish_run_all(harness, False)

        self.assertFalse(harness._pipeline_running)
        harness._stop_event.clear.assert_called_once_with()
        harness.stop_button.set_sensitive.assert_called_with(False)
        harness._stop_status.assert_called_once_with()
        harness.show_toast.assert_called_with("Pipeline stopped.")

    def test_phase_progress_reports_completion_and_activity(self) -> None:
        step_ids = ("one", "two", "three")

        self.assertEqual(_phase_progress_text(step_ids, {}), "0 of 3 complete")
        self.assertEqual(
            _phase_progress_text(step_ids, {"one": "Done", "two": "Page 4/20"}),
            "1 of 3 complete • Running",
        )
        self.assertEqual(
            _phase_progress_text(
                step_ids,
                {"one": "Done", "two": "Skipped", "three": "Done"},
            ),
            "3 of 3 complete",
        )

    def test_first_incomplete_phase_and_complete_pipeline(self) -> None:
        prepare_steps = set(PIPELINE_PHASES[0][2])
        all_steps = {
            step_id
            for _phase_id, _title, step_ids in PIPELINE_PHASES
            for step_id in step_ids
        }

        self.assertEqual(_first_incomplete_phase_id(set()), "prepare")
        self.assertEqual(_first_incomplete_phase_id(prepare_steps), "classify")
        self.assertIsNone(_first_incomplete_phase_id(all_steps))

    def test_transcript_summary_labels(self) -> None:
        self.assertEqual(
            _transcript_summary("split", 125),
            "RT + CT • RT through page 125",
        )
        self.assertEqual(
            _transcript_summary("rt_only", None),
            "Reporter's transcript only",
        )
        self.assertEqual(
            _transcript_summary("ct_only", None),
            "Clerk's transcript only",
        )

    def test_rt_ct_mode_requires_a_positive_split_page_before_launch(self) -> None:
        message = "Enter the last RT page before starting the pipeline."

        self.assertEqual(_pipeline_split_validation_message("split", None), message)
        self.assertEqual(_pipeline_split_validation_message("split", 0), message)
        self.assertIsNone(_pipeline_split_validation_message("split", 125))
        self.assertIsNone(_pipeline_split_validation_message("rt_only", None))
        self.assertIsNone(_pipeline_split_validation_message("ct_only", None))

    def test_settings_destinations_are_grouped_once(self) -> None:
        self.assertEqual(
            [(group_id, title) for group_id, title, _items in SETTINGS_NAV_GROUPS],
            [
                ("prepare", "Prepare"),
                ("classify", "Classify"),
                ("summarize", "Summarize"),
                ("agent", "Agent"),
            ],
        )
        destination_keys = _settings_destination_keys()
        self.assertEqual(len(destination_keys), 9)
        self.assertEqual(len(destination_keys), len(set(destination_keys)))
        self.assertEqual(destination_keys[0], "text-source")
        self.assertEqual(destination_keys[-1], "pi")

    def test_prompt_tests_are_grouped_and_use_adaptive_inputs(self) -> None:
        mode_ids = [
            mode_id
            for _group_id, _title, options in TEST_PROMPT_GROUPS
            for mode_id, _label in options
        ]
        self.assertEqual(len(mode_ids), 12)
        self.assertEqual(len(mode_ids), len(set(mode_ids)))
        self.assertEqual(len(_test_prompt_options("classification")), 9)
        self.assertEqual(len(_test_prompt_options("summarize")), 3)
        self.assertEqual(_test_prompt_input_kind("basic_rt"), "image")
        self.assertEqual(_test_prompt_input_kind("names_form"), "image")
        self.assertEqual(_test_prompt_input_kind("summarize_hearings"), "text")
        self.assertEqual(_test_prompt_input_kind("summarize_minutes"), "text")

    def test_terminal_log_sanitizes_untrusted_controls(self) -> None:
        self.assertEqual(
            _sanitize_terminal_log_text("hello\x1b[2J world", preserve_newlines=False),
            "hello[2J world",
        )
        line = _terminal_log_line("problem\x07", "ERROR")
        self.assertIn("[ERROR]", line)
        self.assertNotIn("\x07", line)

    def test_create_files_and_detection_are_the_only_unresolved_steps(self) -> None:
        self.assertEqual(
            NO_RESOLVED_LAYOUT_STEP_IDS,
            {"create_files", "detect_transcript_layout"},
        )
        self.assertFalse(_step_requires_resolved_layout("create_files"))
        self.assertFalse(_step_requires_resolved_layout("detect_transcript_layout"))
        for step_id in (
            "strip_characters",
            "infer_case",
            "classify_basic",
            "classify_advanced",
            "classify_dates",
            "classify_names",
            "build_toc",
            "find_boundaries",
            "number_transcript_pages",
            "build_participant_index",
            "create_hearing_summaries",
            "create_report_summaries",
            "create_minute_order_summaries",
            "create_case_overview",
            "build_source_map",
        ):
            self.assertTrue(_step_requires_resolved_layout(step_id))
        self.assertNotIn("detect_transcript_layout", VISION_CLASSIFICATION_STEP_IDS)

    def test_layout_legacy_mirror_matching_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            for page in (1, 2):
                (root / "text_pages" / f"{page:04d}.txt").write_text(
                    f"page {page}", encoding="utf-8"
                )
                (root / "image_pages" / f"{page:04d}.png").write_bytes(b"image")
            (root / "manifest.json").write_text(
                json.dumps({"rt_ct_split_mode": "split", "rt_ct_split_page": 1}),
                encoding="utf-8",
            )

            self.assertTrue(_layout_matches_legacy(root))
            apply_manual_override(root, mode="split", rt_end_file_page=1)
            self.assertTrue(_layout_matches_legacy(root))

            # A pi-agent resolution never touches manifest mirrors, so it can
            # disagree with the legacy split stored in the manifest.
            from recordprep.transcript_layout import (
                draft_layout_payload,
                finalize_layout_draft,
            )

            draft = draft_layout_payload(
                mode="rt_only",
                status="resolved",
                decision_source="pi-agent",
                confidence="high",
                method="text search",
                rt_end_file_page=2,
                search_summary="RT evidence spans the record.",
                evidence=[{"path": "text_pages/0002.txt", "kind": "text"}],
            )
            finalize_layout_draft(root, draft)
            self.assertFalse(_layout_matches_legacy(root))

    def test_old_bundle_without_artifact_is_detection_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            (root / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (root / "manifest.json").write_text(
                json.dumps(
                    {"rt_ct_split_mode": "split", "rt_ct_split_page": 1}
                ),
                encoding="utf-8",
            )
            from recordprep.transcript_layout import detection_status

            self.assertEqual(detection_status(root), ("pending", None))

    def test_manifest_refresh_preserves_pi_artifact_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "created_at": "original",
                        "files": {
                            "source_map": "artifacts/source_map.json",
                            "transcript_page_numbers": "artifacts/numbers.json",
                            "transcript_page_number_series": "artifacts/series.md",
                            "participant_index": "artifacts/participants.json",
                            "case_overview": "artifacts/case_overview.md",
                        },
                    }
                ),
                encoding="utf-8",
            )
            _write_manifest(
                root,
                [],
                pipeline_info={"last_completed_step": "build_source_map"},
            )
            payload = json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                payload["files"]["source_map"],
                "artifacts/source_map.json",
            )
            self.assertNotIn("organized_hearings", payload["files"])
            self.assertNotIn("organized_reports", payload["files"])
            self.assertEqual(
                payload["files"]["case_overview"],
                "artifacts/case_overview.md",
            )
            self.assertEqual(
                payload["pipeline"]["last_completed_step"],
                "build_source_map",
            )


class _PreflightHarness:
    """Minimal MainWindow stand-in used to exercise launch preflights.

    Keeps real case config and GTK widgets out of the tests; only the
    launch-authority surface (selection, root resolution, toasts) is
    provided.
    """

    def __init__(
        self,
        selected_pdfs: list[Path] | None = None,
        override_root: Path | None = None,
    ) -> None:
        self.selected_pdfs = list(selected_pdfs or [])
        self.override_root = override_root
        self.warnings: list[str] = []

    @property
    def _source_row(self) -> None:
        return None

    def _resolve_case_root(self) -> Path | None:
        if self.override_root is not None:
            return self.override_root
        if self.selected_pdfs:
            parents = {path.parent for path in self.selected_pdfs}
            if len(parents) != 1:
                return None
            return parents.pop() / "case_bundle"
        return None

    def show_toast(self, message: str, kind: str = "INFO") -> None:
        if kind == "WARN":
            self.warnings.append(message)

    def _current_rt_ct_split_selection(self) -> tuple[str, int | None]:
        return "auto", None

    def _require_resolved_layout(self, **kwargs: bool) -> bool:
        return RecordPrepWindow._require_resolved_layout(self, **kwargs)


class _SourceRowHarness(_PreflightHarness):
    """Adds the source-row presentation surface for summary tests."""

    def __init__(
        self,
        selected_pdfs: list[Path] | None = None,
        override_root: Path | None = None,
    ) -> None:
        super().__init__(selected_pdfs, override_root)
        self.title: str | None = None
        self.subtitle: str | None = None
        self.selected_label = self._FakeLabel()

    @property
    def _source_row(self) -> "_SourceRowHarness":
        return self

    def set_title(self, value: str) -> None:
        self.title = value

    def set_subtitle(self, value: str) -> None:
        self.subtitle = value

    class _FakeLabel:
        def __init__(self) -> None:
            self.last_text: str | None = None

        def set_text(self, value: str) -> None:
            self.last_text = value

    def _update_source_summary(
        self,
        split_page: int | None = None,
        split_mode: str | None = None,
    ) -> None:
        return RecordPrepWindow._update_source_summary(self, split_page, split_mode)

    def _load_case_context(self) -> None:
        return RecordPrepWindow._load_case_context(self)

    def _load_rt_ct_split(self) -> None:
        return None

    def _update_toc_button(self) -> None:
        return None

    def _refresh_step_statuses_from_artifacts(self) -> None:
        return None


class FreshPdfStartupTests(unittest.TestCase):
    def test_fresh_pdf_selection_passes_preflight_with_allow_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            harness = _PreflightHarness(selected_pdfs=[pdf])

            self.assertTrue(
                harness._require_resolved_layout(allow_unresolved=True)
            )
            self.assertEqual(harness.warnings, [])
            self.assertFalse((Path(temporary) / "case_bundle").exists())

    def test_fresh_pdf_selection_rejected_without_allow_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            harness = _PreflightHarness(selected_pdfs=[pdf])

            self.assertFalse(
                harness._require_resolved_layout(allow_unresolved=False)
            )
            self.assertEqual(
                harness.warnings, ["Choose PDF files or a case bundle first."]
            )

    def test_layout_preflight_distinguishes_missing_and_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            (root / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (root / "image_pages/0001.png").write_bytes(b"image")
            harness = _PreflightHarness(override_root=root)

            self.assertFalse(harness._require_resolved_layout())
            self.assertIn("Run Detect transcript layout", harness.warnings[-1])

            apply_manual_override(root, mode="ct_only")
            (root / "text_pages/0001.txt").write_text(
                "externally changed text", encoding="utf-8"
            )
            self.assertFalse(harness._require_resolved_layout())
            self.assertIn("is stale", harness.warnings[-1])
            self.assertNotIn("before starting", harness.warnings[-1])

    def test_partial_text_processing_stop_rebinds_but_stays_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            for page in (1, 2):
                (root / "text_pages" / f"{page:04d}.txt").write_text(
                    f"page {page}\x00 text", encoding="utf-8"
                )
                (root / "image_pages" / f"{page:04d}.png").write_bytes(b"image")
            apply_manual_override(root, mode="rt_only")

            harness = mock.Mock()
            harness.selected_pdfs = []
            harness._resolve_case_root.return_value = root
            harness._raise_if_stop_requested.side_effect = [
                None,
                None,
                StopRequested(),
            ]
            with mock.patch(
                "recordprep.ui.main_window.GLib.idle_add",
                side_effect=lambda function, *args: function(*args),
            ):
                completed = RecordPrepWindow._run_step_strip_nonstandard(harness)

            self.assertFalse(completed)
            self.assertNotIn("\x00", (root / "text_pages/0001.txt").read_text())
            self.assertIn("\x00", (root / "text_pages/0002.txt").read_text())
            from recordprep.transcript_layout import diagnose_layout

            self.assertEqual(diagnose_layout(root).code, "resolved")
            finish_success = harness._finish_step.call_args.args[-1]
            self.assertIsNone(finish_success)
            harness._safe_update_manifest.assert_not_called()

    def test_partial_text_processing_error_rebinds_but_stays_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            for page in (1, 2):
                (root / "text_pages" / f"{page:04d}.txt").write_text(
                    f"page {page}\x00 text", encoding="utf-8"
                )
                (root / "image_pages" / f"{page:04d}.png").write_bytes(b"image")
            apply_manual_override(root, mode="rt_only")

            harness = mock.Mock()
            harness.selected_pdfs = []
            harness._resolve_case_root.return_value = root
            calls = 0

            def fail_second_page(text: str) -> str:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("recoverable normalization error")
                return text

            with (
                mock.patch(
                    "recordprep.ui.main_window._convert_html_tables",
                    side_effect=fail_second_page,
                ),
                mock.patch(
                    "recordprep.ui.main_window.GLib.idle_add",
                    side_effect=lambda function, *args: function(*args),
                ),
            ):
                completed = RecordPrepWindow._run_step_strip_nonstandard(harness)

            self.assertFalse(completed)
            from recordprep.transcript_layout import diagnose_layout

            self.assertEqual(diagnose_layout(root).code, "resolved")
            finish_success = harness._finish_step.call_args.args[-1]
            self.assertFalse(finish_success)
            harness._safe_update_manifest.assert_not_called()

    def test_stale_layout_blocks_local_server_start_in_worker_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "text_pages").mkdir(parents=True)
            (root / "image_pages").mkdir()
            (root / "text_pages/0001.txt").write_text("one", encoding="utf-8")
            (root / "image_pages/0001.png").write_bytes(b"image")
            apply_manual_override(root, mode="ct_only")
            (root / "text_pages/0001.txt").write_text("stale text", encoding="utf-8")

            harness = mock.Mock()
            harness._resolve_case_root.return_value = root
            row = mock.Mock()
            row.get_title.return_value = "Classify pages"
            handler = mock.Mock()
            with mock.patch(
                "recordprep.ui.main_window.GLib.idle_add",
                side_effect=lambda function, *args: function(*args),
            ):
                RecordPrepWindow._run_single_step_thread(
                    harness, handler, row, "classify_basic"
                )

            harness._ensure_local_vision_server_running.assert_not_called()
            handler.assert_not_called()
            self.assertIn(
                "is stale", harness.show_toast.call_args_list[0].args[0]
            )

    def test_no_selection_and_no_bundle_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing_root = Path(temporary) / "missing" / "case_bundle"
            harness = _PreflightHarness(override_root=missing_root)

            self.assertFalse(
                harness._require_resolved_layout(allow_unresolved=True)
            )
            self.assertEqual(
                harness.warnings, ["Choose PDF files or a case bundle first."]
            )

    def test_pdfs_from_different_parents_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "a" / "record.pdf"
            second = Path(temporary) / "b" / "record.pdf"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"dummy")
            second.write_bytes(b"dummy")
            harness = _PreflightHarness(selected_pdfs=[first, second])

            self.assertFalse(
                harness._require_resolved_layout(allow_unresolved=True)
            )
            self.assertEqual(
                harness.warnings, ["Choose PDF files or a case bundle first."]
            )

    def test_persisted_context_not_current_without_manifest_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            root = Path(temporary) / "case_bundle"

            self.assertFalse(
                _case_context_matches_selection("Prior Case Name", root, [pdf])
            )
            self.assertFalse(
                _case_context_matches_selection("", root, [pdf])
            )

    def test_persisted_context_current_when_manifest_exactly_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            (root / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../record.pdf"]}),
                encoding="utf-8",
            )

            self.assertTrue(
                _case_context_matches_selection("Prior Case Name", root, [pdf])
            )

            # Normalization: a selection spelled through a `..` component
            # still matches the manifest record of the same file.
            self.assertTrue(
                _case_context_matches_selection(
                    "Prior Case Name",
                    root,
                    [Path(temporary) / "sub" / ".." / "record.pdf"],
                )
            )

    def test_changed_selection_does_not_inherit_old_case_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.pdf"
            second = Path(temporary) / "second.pdf"
            first.write_bytes(b"dummy")
            second.write_bytes(b"dummy")
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            (root / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../first.pdf"]}),
                encoding="utf-8",
            )

            self.assertFalse(
                _case_context_matches_selection("Prior Case Name", root, [second])
            )
            self.assertTrue(
                _case_context_matches_selection("Prior Case Name", root, [first])
            )

    def test_load_case_context_keeps_pdf_selection_presentation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            harness = _SourceRowHarness(selected_pdfs=[pdf])
            harness.selected_label.last_text = "Selected: record.pdf"

            with mock.patch(
                "recordprep.ui.main_window.load_case_context",
                return_value=("Prior Case Name", Path(temporary)),
            ):
                harness._load_case_context()

            self.assertEqual(harness.selected_label.last_text, "Selected: record.pdf")

    def test_fresh_selection_summary_shows_pdf_and_detection_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            harness = _SourceRowHarness(selected_pdfs=[pdf])

            with mock.patch(
                "recordprep.ui.main_window.load_case_context",
                return_value=("Prior Case Name", Path(temporary)),
            ):
                harness._update_source_summary(split_mode="auto")

            self.assertEqual(harness.title, "record.pdf")
            self.assertEqual(
                harness.subtitle, "record.pdf • Detection pending"
            )

    def test_existing_bundle_selection_keeps_case_name_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pdf = Path(temporary) / "record.pdf"
            pdf.write_bytes(b"dummy")
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            (root / "manifest.json").write_text(
                json.dumps({"input_pdfs": ["../record.pdf"]}),
                encoding="utf-8",
            )
            harness = _SourceRowHarness(selected_pdfs=[pdf])

            with mock.patch(
                "recordprep.ui.main_window.load_case_context",
                return_value=("Prior Case Name", Path(temporary)),
            ):
                harness._update_source_summary(split_mode="auto")

            self.assertEqual(harness.title, "Prior Case Name")
            self.assertEqual(
                harness.subtitle, "record.pdf • Detection pending"
            )


class CorrectTocCompletionTests(unittest.TestCase):
    def _write_toc(self, root: Path, lines: list[str]) -> Path:
        toc_path = root / "artifacts" / "toc.txt"
        toc_path.parent.mkdir(parents=True, exist_ok=True)
        toc_path.write_text(
            "\n".join(lines).rstrip() + "\n", encoding="utf-8"
        )
        return toc_path

    def _toc_complete(self, root: Path, step_id: str) -> bool:
        return RecordPrepWindow._step_artifact_complete(
            mock.Mock(), step_id, root, []
        )

    def test_duplicate_minute_order_date_blocks_correct_toc_completion(
        self,
    ) -> None:
        toc_lines = [
            "FORMS",
            "\tParental Notification Form 0003",
            "",
            "REPORTS",
            "\tDetention Report March 3, 2025 0005",
            "",
            "MINUTE ORDERS",
            "\tMarch 3, 2025 0012",
            "\tMarch 3, 2025 0018",
            "\tApril 10, 2025 0022",
            "",
            "HEARINGS",
            "\tMarch 3, 2025 0025",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            self._write_toc(root, toc_lines)

            self.assertTrue(self._toc_complete(root, "build_toc"))
            self.assertFalse(self._toc_complete(root, "correct_toc"))

    def test_correction_keeps_first_entry_and_completes_step(self) -> None:
        toc_lines = [
            "MINUTE ORDERS",
            "\tMarch 3, 2025 0012",
            "\tMarch 3, 2025 0018",
            "\tApril 10, 2025 0022",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            toc_path = self._write_toc(root, toc_lines)

            corrected, removals = _correct_toc_lines(toc_lines)

            self.assertEqual(removals, 1)
            self.assertEqual(
                corrected,
                [
                    "MINUTE ORDERS",
                    "\tMarch 3, 2025 0012",
                    "\tApril 10, 2025 0022",
                ],
            )
            toc_path.write_text(
                "\n".join(corrected).rstrip() + "\n", encoding="utf-8"
            )

            self.assertTrue(self._toc_complete(root, "correct_toc"))

    def test_duplicate_looking_entries_outside_minute_orders_preserved(
        self,
    ) -> None:
        toc_lines = [
            "FORMS",
            "\tMarch 3, 2025 0003",
            "\tMarch 3, 2025 0004",
            "",
            "REPORTS",
            "\tMarch 3, 2025 0006",
            "\tMarch 3, 2025 0007",
            "",
            "MINUTE ORDERS",
            "\tMarch 3, 2025 0012",
            "\tMarch 3, 2025 0018",
            "",
            "HEARINGS",
            "\tMarch 3, 2025 0025",
            "\tMarch 3, 2025 0026",
        ]

        corrected, removals = _correct_toc_lines(toc_lines)

        self.assertEqual(removals, 1)
        self.assertEqual(corrected, toc_lines[:10] + toc_lines[11:])

    def test_distinct_minute_order_dates_preserved(self) -> None:
        toc_lines = [
            "MINUTE ORDERS",
            "\tMarch 3, 2025 0012",
            "\tApril 10, 2025 0018",
            "\tMay 15, 2025 0022",
        ]

        corrected, removals = _correct_toc_lines(toc_lines)

        self.assertEqual(removals, 0)
        self.assertEqual(corrected, toc_lines)

    def test_correction_is_idempotent(self) -> None:
        toc_lines = [
            "MINUTE ORDERS",
            "\tMarch 3, 2025 0012",
            "\tMarch 3, 2025 0018",
            "\tApril 10, 2025 0022",
        ]

        first_pass, first_removals = _correct_toc_lines(toc_lines)
        second_pass, second_removals = _correct_toc_lines(first_pass)

        self.assertEqual(first_removals, 1)
        self.assertEqual(second_removals, 0)
        self.assertEqual(second_pass, first_pass)

    def test_resume_starts_at_correct_toc_when_duplicates_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            self._write_toc(
                root,
                [
                    "MINUTE ORDERS",
                    "\tMarch 3, 2025 0012",
                    "\tMarch 3, 2025 0018",
                ],
            )
            harness = mock.Mock()
            harness.selected_pdfs = []
            harness._step_artifact_complete = (
                RecordPrepWindow._step_artifact_complete.__get__(
                    harness, RecordPrepWindow
                )
            )
            harness._pipeline_steps.return_value = [
                ("build_toc", mock.Mock(), mock.Mock()),
                ("correct_toc", mock.Mock(), mock.Mock()),
            ]

            start = RecordPrepWindow._resume_start_index(harness, root, None)

            self.assertEqual(start, 1)

            self._write_toc(root, ["MINUTE ORDERS", "\tMarch 3, 2025 0012"])

            start = RecordPrepWindow._resume_start_index(harness, root, None)

            self.assertIsNone(start)

    def test_missing_or_unreadable_toc_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            (root / "artifacts").mkdir(parents=True)

            self.assertFalse(self._toc_complete(root, "build_toc"))
            self.assertFalse(self._toc_complete(root, "correct_toc"))

            (root / "artifacts" / "toc.txt").mkdir()

            self.assertTrue(self._toc_complete(root, "build_toc"))
            self.assertFalse(self._toc_complete(root, "correct_toc"))


if __name__ == "__main__":
    unittest.main()
