"""Resume/Create/layout regressions: source and completed work must survive."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep.ui import main_window as ui
from recordprep.transcript_layout import apply_manual_override, read_resolved_layout


class ResumePreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'case_bundle'
        for directory in ('text_pages', 'image_pages', 'classification', 'artifacts'):
            (self.root / directory).mkdir(parents=True)
        for i in (1, 2):
            (self.root / f'text_pages/{i:04d}.txt').write_text('Synthetic source page')
            (self.root / f'image_pages/{i:04d}.png').write_bytes(b'synthetic image')
        apply_manual_override(self.root, mode='split', rt_end_file_page=1)
        (self.root / 'classification/CT_basic.jsonl').write_text('completed classification sentinel')
        self.pdf = self.base / 'source.pdf'
        self.pdf.write_bytes(b'synthetic PDF; extraction forbidden')
        self.owner = SimpleNamespace(
            selected_pdfs=[self.pdf], _bundle_reset_required=False,
            _rt_ct_split_pending=1, _rt_ct_split_mode_pending='split',
            _resolve_case_root=lambda: self.root, _load_rt_ct_split=Mock(), show_toast=Mock(),
            _raise_if_stop_requested=Mock(), _safe_update_manifest=Mock(),
            _finish_step=Mock(), _stop_status_if_idle=Mock(), _stop_button_if_idle=Mock(),
            step_one_row=Mock(), _append_log_message=Mock(),
            _step_artifact_complete=lambda *args: True,
        )
        self.owner._has_layout_dependent_work = lambda root: ui.RecordPrepWindow._has_layout_dependent_work(self.owner, root)
        self.owner._resume_step_complete = ui.RecordPrepWindow._resume_step_complete.__get__(self.owner, ui.RecordPrepWindow)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_same_manual_layout_is_a_byte_and_mtime_preserving_noop(self):
        before = self.snapshot()
        self.assertTrue(ui.RecordPrepWindow._try_apply_manual_layout(self.owner))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.owner._bundle_reset_required)
        self.assertIsNone(self.owner._rt_ct_split_pending)

    def test_different_manual_layout_is_blocked_before_any_write(self):
        self.owner._rt_ct_split_mode_pending = 'ct_only'
        before = self.snapshot()
        self.assertFalse(ui.RecordPrepWindow._try_apply_manual_layout(self.owner))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(read_resolved_layout(self.root)['mode'], 'split')
        self.assertFalse(self.owner._bundle_reset_required)

    def test_create_files_never_resets_existing_work_on_any_entry_path(self):
        from recordprep.text_processing_completion import publish
        publish(self.root)
        for reset, changed in ((True, False), (False, True), (False, False)):
            with self.subTest(reset=reset, changed=changed):
                self.owner._bundle_reset_required = reset
                before = self.snapshot()
                with patch.object(ui, '_bundle_inputs_changed', return_value=changed), \
                     patch.object(ui, '_reset_generated_case_bundle') as erase, \
                     patch.object(ui, '_merge_pdfs') as merge, \
                     patch.object(ui, '_write_manifest') as manifest, \
                     patch.object(ui, '_generate_text_files') as text, \
                     patch.object(ui, '_generate_image_page_files') as images, \
                     patch.object(ui.GLib, 'idle_add', side_effect=lambda fn, *a: fn(*a)):
                    ok = ui.RecordPrepWindow._run_step_one(self.owner)
                self.assertEqual(ok, not (reset or changed))
                for mock in (erase, merge, manifest, text, images): mock.assert_not_called()
                self.assertEqual(self.snapshot(), before)

    def test_source_refill_invalidates_processing_receipt_before_extraction(self):
        from recordprep.text_processing_completion import RECEIPT, publish
        publish(self.root)
        self.owner._has_layout_dependent_work = lambda root: False
        self.owner._step_artifact_complete = lambda *args: False

        def check_receipt_then_stop(*args):
            self.assertFalse((self.root / RECEIPT).exists())
            raise ui.StopRequested()

        with patch.object(ui, '_bundle_inputs_changed', return_value=False), \
             patch.object(ui, '_write_manifest'), \
             patch.object(ui, 'load_text_source_setting', return_value='embedded'), \
             patch.object(ui, '_generate_text_files', side_effect=check_receipt_then_stop) as extract, \
             patch.object(ui.GLib, 'idle_add', side_effect=lambda fn, *args: fn(*args)):
            self.assertFalse(ui.RecordPrepWindow._run_step_one(self.owner))
        extract.assert_called_once()
        self.assertFalse((self.root / RECEIPT).exists())

    def test_resume_rejects_reset_or_missing_sources_before_work_starts(self):
        self.owner._pipeline_steps = lambda: [('create_files', Mock(), Mock()), ('build_participant_index', Mock(), Mock())]
        with patch.object(ui, '_bundle_inputs_changed', return_value=False):
            self.owner._bundle_reset_required = True
            with self.assertRaisesRegex(ValueError, 'Resume never resets'):
                ui.RecordPrepWindow._resume_start_index(self.owner, self.root, None)
            self.owner._bundle_reset_required = False
            self.owner._step_artifact_complete = lambda *args: False
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'source pages are incomplete'):
                ui.RecordPrepWindow._resume_start_index(self.owner, self.root, None)
            self.assertEqual(self.snapshot(), before)

    def test_resume_does_not_silently_regenerate_stale_published_classification(self):
        (self.root / 'classification/profile-basic.json').write_text('{}')
        self.owner._pipeline_steps = lambda: [('classify_basic', Mock(get_title=lambda: 'Classification basic'), Mock())]
        self.owner._step_artifact_complete = lambda *a: False
        before = self.snapshot()
        with patch.object(ui, '_bundle_inputs_changed', return_value=False):
            self.assertIsNone(ui.RecordPrepWindow._resume_start_index(self.owner, self.root, None))
        self.assertEqual(self.snapshot(), before)

    def test_reopened_resume_skips_completed_stages_and_runs_only_pending(self):
        completed = Mock(return_value=True)
        pending = Mock(return_value=True)
        self.owner._pipeline_steps = lambda: [('create_files', Mock(), completed), ('classify_basic', Mock(), completed),
                                             ('build_participant_index', Mock(), pending)]
        self.owner._step_artifact_complete = lambda step, *a: step != 'build_participant_index'
        self.owner._start_step = Mock()
        self.owner._finish_run_all = Mock()
        before = self.snapshot()
        with patch.object(ui, '_bundle_inputs_changed', return_value=False), \
             patch.object(ui, 'load_classifier_settings', return_value={}), patch.object(ui.GLib, 'idle_add') as idle:
            start = ui.RecordPrepWindow._resume_start_index(self.owner, self.root, None)
            self.assertEqual(start, 2)
            ui.RecordPrepWindow._run_steps_from_index(self.owner, 0, self.root, skip_completed_steps=True)
        statuses = [call.args[2] for call in idle.call_args_list
                    if call.args[0] == self.owner._finish_step]
        self.assertEqual(statuses, ['Already complete', 'Already complete'])
        completed.assert_not_called()
        pending.assert_called_once()
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
