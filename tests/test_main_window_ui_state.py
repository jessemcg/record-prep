import unittest

from recordprep.ui.main_window import (
    PIPELINE_PHASES,
    PIPELINE_STEP_PHASE,
    SETTINGS_NAV_GROUPS,
    TEST_PROMPT_GROUPS,
    _first_incomplete_phase_id,
    _phase_progress_text,
    _run_action_label,
    _settings_destination_keys,
    _test_prompt_input_kind,
    _test_prompt_options,
    _transcript_summary,
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
        self.assertEqual(grouped[-1], "create_rag_index")

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

    def test_run_and_transcript_summary_labels(self) -> None:
        self.assertEqual(_run_action_label(None), "Run all steps")
        self.assertEqual(
            _run_action_label("Create summaries"),
            "Run through Create summaries",
        )
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

    def test_settings_destinations_are_grouped_once(self) -> None:
        self.assertEqual(
            [(group_id, title) for group_id, title, _items in SETTINGS_NAV_GROUPS],
            [
                ("prepare", "Prepare"),
                ("classify", "Classify"),
                ("summarize", "Summarize"),
                ("index", "Index"),
            ],
        )
        destination_keys = _settings_destination_keys()
        self.assertEqual(len(destination_keys), 11)
        self.assertEqual(len(destination_keys), len(set(destination_keys)))
        self.assertEqual(destination_keys[0], "text-source")
        self.assertEqual(destination_keys[-1], "rag")

    def test_prompt_tests_are_grouped_and_use_adaptive_inputs(self) -> None:
        mode_ids = [
            mode_id
            for _group_id, _title, options in TEST_PROMPT_GROUPS
            for mode_id, _label in options
        ]
        self.assertEqual(len(mode_ids), 15)
        self.assertEqual(len(mode_ids), len(set(mode_ids)))
        self.assertEqual(len(_test_prompt_options("classification")), 9)
        self.assertEqual(len(_test_prompt_options("optimize")), 3)
        self.assertEqual(len(_test_prompt_options("summarize")), 3)
        self.assertEqual(_test_prompt_input_kind("basic_rt"), "image")
        self.assertEqual(_test_prompt_input_kind("names_form"), "image")
        self.assertEqual(_test_prompt_input_kind("optimize_hearings"), "text")
        self.assertEqual(_test_prompt_input_kind("summarize_minutes"), "text")


if __name__ == "__main__":
    unittest.main()
