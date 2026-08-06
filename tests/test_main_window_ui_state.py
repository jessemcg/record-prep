import json
import tempfile
import unittest
from pathlib import Path

from recordprep.ui.main_window import (
    PIPELINE_PHASES,
    PIPELINE_STEP_PHASE,
    SETTINGS_NAV_GROUPS,
    TEST_PROMPT_GROUPS,
    _first_incomplete_phase_id,
    _pipeline_split_validation_message,
    _phase_progress_text,
    _sanitize_terminal_log_text,
    _settings_destination_keys,
    _terminal_log_line,
    _test_prompt_input_kind,
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

        self.assertEqual(len(grouped), 19)
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertEqual(set(grouped), set(PIPELINE_STEP_PHASE))
        self.assertEqual(grouped[0], "create_files")
        self.assertEqual(
            grouped[-7:],
            [
                "number_transcript_pages",
                "build_participant_index",
                "create_summaries",
                "add_hearing_date_links",
                "organize_hearing_summary",
                "organize_report_summary",
                "build_source_map",
            ],
        )
        self.assertEqual(PIPELINE_PHASES[-1][1], "Agent Search")

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

    def test_manifest_refresh_preserves_pi_artifact_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "created_at": "original",
                        "files": {
                            "source_map": "artifacts/source_map.json",
                            "organized_hearings": "summaries/h_organized.txt",
                            "organized_reports": "summaries/r_organized.txt",
                            "transcript_page_numbers": "artifacts/numbers.json",
                            "transcript_page_number_series": "artifacts/series.md",
                            "participant_index": "artifacts/participants.json",
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
            self.assertEqual(
                payload["files"]["organized_hearings"],
                "summaries/h_organized.txt",
            )
            self.assertEqual(
                payload["pipeline"]["last_completed_step"],
                "build_source_map",
            )


if __name__ == "__main__":
    unittest.main()
