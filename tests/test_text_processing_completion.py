"""Synthetic regression coverage: raw OCR must never skip text processing."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from recordprep.output_presence import step_outputs_present
from recordprep.text_processing_completion import RECEIPT, publish
from recordprep.transcript_layout import apply_manual_override
from recordprep.ui.main_window import RecordPrepWindow, StopRequested


class TextProcessingCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'text_pages').mkdir()
        (self.root / 'image_pages').mkdir()
        for page in (1, 2):
            (self.root / f'text_pages/{page:04d}.txt').write_text(f'Page {page}\x00 text')
            (self.root / f'image_pages/{page:04d}.png').write_bytes(b'image')
        apply_manual_override(self.root, mode='rt_only')
        self.owner = Mock()
        self.owner.selected_pdfs = []
        self.owner._resolve_case_root.return_value = self.root

    def assert_complete(self, expected):
        self.assertEqual(step_outputs_present('strip_characters', self.root), expected)
        self.assertEqual(RecordPrepWindow._resume_step_complete(
            self.owner, 'strip_characters', self.root), expected)
        self.assertEqual(RecordPrepWindow._step_artifact_complete(
            self.owner, 'strip_characters', self.root), expected)

    def run_worker(self):
        with patch('recordprep.ui.main_window.GLib.idle_add',
                   side_effect=lambda function, *args: function(*args)):
            return RecordPrepWindow._run_step_strip_nonstandard(self.owner)

    def test_raw_pages_pending_then_success_survives_reopen(self):
        self.assert_complete(False)
        self.assertTrue(self.run_worker())
        self.assert_complete(True)
        self.owner = Mock(selected_pdfs=[])
        self.assert_complete(True)
        self.assertEqual(list((self.root / 'artifacts').glob('.text-processing-*')), [])

    def test_resume_selects_processing_instead_of_skipping_it(self):
        self.owner._bundle_reset_required = False
        self.owner._pipeline_steps.return_value = [
            ('detect_transcript_layout', Mock(), Mock()),
            ('strip_characters', Mock(), Mock()),
        ]
        self.owner._resume_step_complete.side_effect = lambda step, root: (
            RecordPrepWindow._resume_step_complete(self.owner, step, root))
        self.assertEqual(RecordPrepWindow._resume_start_index(self.owner, self.root, None), 1)
        self.assertTrue(self.run_worker())
        self.assertIsNone(RecordPrepWindow._resume_start_index(self.owner, self.root, None))

    def test_stop_and_error_remove_previous_success(self):
        for error in (StopRequested(), RuntimeError('synthetic failure')):
            with self.subTest(error=type(error).__name__):
                publish(self.root)
                self.owner._raise_if_stop_requested.side_effect = [None, None, error]
                self.assertFalse(self.run_worker())
                self.assert_complete(False)
                self.owner._raise_if_stop_requested.side_effect = None

    def test_stop_after_last_page_does_not_publish(self):
        self.owner._raise_if_stop_requested.side_effect = [None, None, None, StopRequested()]
        self.assertFalse(self.run_worker())
        self.assert_complete(False)

    def test_publication_failure_does_not_mark_complete(self):
        real_replace = os.replace

        def fail_receipt(source, target):
            if Path(target) == self.root / RECEIPT:
                raise OSError('failure')
            return real_replace(source, target)

        with patch('recordprep.text_processing_completion.os.replace', side_effect=fail_receipt):
            self.assertFalse(self.run_worker())
        self.assert_complete(False)
        self.assertEqual(list((self.root / 'artifacts').glob('.text-processing-*')), [])

    def test_receipt_without_text_is_not_complete(self):
        publish(self.root)
        for path in (self.root / 'text_pages').glob('*.txt'):
            path.unlink()
        self.assert_complete(False)
