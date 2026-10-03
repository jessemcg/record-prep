"""Synthetic UI delegation and completion tests for independent summary stages."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep.ui.main_window import CONFIG_KEY_RUN_UNTIL_STEP, RecordPrepWindow, load_run_until_step_setting
from recordprep import minute_summaries as minutes, summary_agents as sa
from tests.test_minute_summaries import fixture, candidate


class RunUntilMigrationTests(unittest.TestCase):
    def test_retired_and_aggregate_summary_targets_migrate_to_minute_orders(self):
        for legacy in ("create_summaries", "create_raw", "create_preoptimized", "create_optimized"):
            with tempfile.TemporaryDirectory() as temporary:
                config = Path(temporary) / "config.json"
                config.write_text(json.dumps({CONFIG_KEY_RUN_UNTIL_STEP: legacy}))
                with mock.patch("recordprep.ui.main_window.CONFIG_FILE", config):
                    self.assertEqual(load_run_until_step_setting(), "create_minute_order_summaries")
                self.assertEqual(json.loads(config.read_text())[CONFIG_KEY_RUN_UNTIL_STEP], "create_minute_order_summaries")

    def test_current_summary_targets_are_not_migrated(self):
        for step in ("create_hearing_summaries", "create_report_summaries", "create_minute_order_summaries"):
            with tempfile.TemporaryDirectory() as temporary:
                config = Path(temporary) / "config.json"
                config.write_text(json.dumps({CONFIG_KEY_RUN_UNTIL_STEP: step}))
                with mock.patch("recordprep.ui.main_window.CONFIG_FILE", config):
                    self.assertEqual(load_run_until_step_setting(), step)


class SummaryStepDelegationTests(unittest.TestCase):
    def test_each_handler_delegates_without_direct_api_or_manifest_mutation(self):
        for step, row in (("create_hearing_summaries", "step_hearing_summaries_row"),
                          ("create_report_summaries", "step_report_summaries_row"),
                          ("create_minute_order_summaries", "step_minute_order_summaries_row")):
            for result in (True, False):
                with self.subTest(step=step, result=result):
                    harness = mock.Mock()
                    harness._run_pi_skill_step.return_value = result
                    self.assertIs(getattr(RecordPrepWindow, "_run_step_" + step)(harness), result)
                    harness._run_pi_skill_step.assert_called_once_with(step, getattr(harness, row))
                    harness._request_plain_text.assert_not_called()
                    harness._safe_update_manifest.assert_not_called()

    def test_each_completion_predicate_routes_to_its_own_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "case_name.txt").write_text("Synthetic")
            for step, kind in (("create_hearing_summaries", "hearings"), ("create_report_summaries", "reports")):
                with mock.patch.object(sa, "summary_stage_complete", return_value=True) as check:
                    self.assertTrue(RecordPrepWindow._step_artifact_complete(mock.Mock(), step, root, []))
                    check.assert_called_once_with(root, kind)

    def test_minute_completion_requires_current_rows_not_legacy_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, project = fixture(Path(temporary), 1)
            final = sa.summary_final_path(root, "minutes")
            final.parent.mkdir()
            final.write_text("Legacy minutes")
            with mock.patch.object(minutes, "PROJECT_PI_DIR", project):
                def complete():
                    return RecordPrepWindow._step_artifact_complete(mock.Mock(), "create_minute_order_summaries", root, [])
                self.assertFalse(complete())
                minutes.run_stage(root, project, mock.Mock(return_value=candidate()))
                self.assertTrue(complete())
                final.write_text("tampered")
                self.assertFalse(complete())


if __name__ == "__main__":
    unittest.main()
