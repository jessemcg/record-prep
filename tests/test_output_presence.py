"""Presence-only badges are independent of current-generation validation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from recordprep.output_presence import step_outputs_present
from recordprep.ui.main_window import PIPELINE_PHASES, RecordPrepWindow


OUTPUTS = {
    'create_files': ['text_pages/0001.txt', 'image_pages/0001.png'],
    'strip_characters': ['artifacts/text_processing.complete', 'text_pages/0001.txt'],
    'detect_transcript_layout': ['artifacts/transcript_layout.json'],
    'infer_case': ['case_name.txt'],
    'classify_basic': ['classification/RT_basic.jsonl'],
    'classify_advanced': ['classification/RT_basic_advanced.jsonl'],
    'correct_classify_advanced': ['classification/RT_basic_advanced_corrected.jsonl'],
    'classify_dates': ['classification/RT_basic_advanced_corrected_dates.jsonl'],
    'classify_names': ['classification/RT_basic_advanced_corrected_dates_names.jsonl'],
    'build_toc': ['artifacts/toc.txt'],
    'correct_toc': ['artifacts/toc.txt'],
    'find_boundaries': ['artifacts/hearing_boundaries.json', 'artifacts/report_boundaries.json', 'artifacts/minutes_boundaries.json'],
    'correct_boundaries': ['artifacts/hearing_boundaries.json', 'artifacts/report_boundaries.json'],
    'number_transcript_pages': ['artifacts/transcript_page_numbers.json', 'artifacts/transcript_page_number_series.md'],
    'build_participant_index': ['artifacts/participant_index.json'],
    'create_hearing_summaries': ['summaries/hearings_sum_Synthetic.txt'],
    'create_report_summaries': ['summaries/reports_sum_Synthetic.txt'],
    'create_minute_order_summaries': ['summaries/minutes_sum_Synthetic.txt'],
    'build_summary_editions': [f'summaries/editions/{kind}_sum_Synthetic.{suffix}'
                              for kind in ('hearings', 'reports', 'minutes') for suffix in ('pdf', 'pages.json')],
    'create_case_overview': ['artifacts/case_overview.md'],
    'build_source_map': ['artifacts/source_map.json'],
}


def seed_outputs(root):
    for names in OUTPUTS.values():
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'Synthetic historical output; not current metadata.')


class OutputPresenceTests(unittest.TestCase):
    def test_all_steps_present_even_without_valid_or_current_metadata(self):
        self.assertEqual(set(OUTPUTS), {step for _, _, ids in PIPELINE_PHASES for step in ids})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_outputs(root)
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
            with patch('recordprep.practice_profiles.profile_store', side_effect=AssertionError('No profile lookup')), \
                 patch.object(Path, 'read_text', side_effect=AssertionError('No contents read')), \
                 patch.object(Path, 'read_bytes', side_effect=AssertionError('No hashes')):
                for step in OUTPUTS:
                    self.assertTrue(step_outputs_present(step, root), step)
            self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)
            for path in before:
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            self.assertTrue(all(step_outputs_present(step, root) for step in OUTPUTS))

    def test_missing_outputs_are_pending_and_directories_do_not_count(self):
        for step, names in OUTPUTS.items():
            with self.subTest(step=step), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.assertFalse(step_outputs_present(step, root))
                seed_outputs(root)
                missing = root / names[0]
                missing.unlink()
                self.assertFalse(step_outputs_present(step, root))
                missing.mkdir()
                self.assertFalse(step_outputs_present(step, root))

    def test_mixed_classification_requires_both_published_sides(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_outputs(root)
            self.assertTrue(step_outputs_present('classify_names', root))
            (root / 'classification/CT_basic.jsonl').touch()
            self.assertFalse(step_outputs_present('classify_names', root))
            (root / 'classification/CT_basic_advanced_corrected_dates_names.jsonl').touch()
            self.assertTrue(step_outputs_present('classify_names', root))

    def test_historical_summary_names_and_matching_edition_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'summaries'
            (directory / 'editions').mkdir(parents=True)
            for kind in ('hearings', 'reports', 'minutes'):
                (directory / f'summarized_{kind}.txt').touch()
                (directory / f'editions/summarized_{kind}.pdf').touch()
                (directory / f'editions/summarized_{kind}.pages.json').touch()
            self.assertTrue(step_outputs_present('create_hearing_summaries', root))
            self.assertTrue(step_outputs_present('create_report_summaries', root))
            self.assertTrue(step_outputs_present('create_minute_order_summaries', root))
            self.assertTrue(step_outputs_present('build_summary_editions', root))
            (directory / 'editions/summarized_reports.pages.json').rename(directory / 'editions/reports_sum_Other.pages.json')
            self.assertFalse(step_outputs_present('build_summary_editions', root))

    def test_ui_refresh_does_not_use_execution_freshness_for_badges(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed_outputs(root)
            owner = Mock()
            owner._pipeline_running = False
            owner._resolve_case_root.return_value = root
            owner._pipeline_steps.return_value = [(step, step, Mock()) for step in OUTPUTS]
            owner._step_artifact_complete.side_effect = AssertionError('Execution validation is not a badge')
            with patch('recordprep.ui.main_window.is_ct_only', return_value=False):
                RecordPrepWindow._refresh_step_statuses_from_artifacts(owner)
            self.assertEqual(owner._set_step_status.call_count, len(OUTPUTS))
            for step in OUTPUTS:
                owner._set_step_status.assert_any_call(step, 'Done')
            owner._step_artifact_complete.assert_not_called()
            (root / 'artifacts/case_overview.md').unlink()
            owner._set_step_status.reset_mock()
            with patch('recordprep.ui.main_window.is_ct_only', return_value=False):
                RecordPrepWindow._refresh_step_statuses_from_artifacts(owner)
            owner._set_step_status.assert_any_call('create_case_overview', 'Pending')
            owner._set_step_status.assert_any_call('build_source_map', 'Done')
