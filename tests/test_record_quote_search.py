"""Record-wide existence verification, not page attribution; synthetic data only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep import record_quote_search as search
from recordprep import focus_record_categories
from test_summary_quote_policy import summary_fixture


class RecordQuoteSearchTests(unittest.TestCase):
    def test_reported_first_then_elsewhere_and_bounded_reused_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for page, text in ((1, 'First source.'), (23, 'Discussion started here.'),
                               (24, 'I HAVE NO OBJECTION TO THE BIOLOGICAL ELEVATION TODAY')):
                (root / f'{page:04d}.txt').write_text(text)
            scanner = search.RecordQuoteSearch(root)
            quote = 'I HAVE NO OBJECTION TO THE BIOLOGICAL ELEVATION TODAY'
            with patch.object(scanner, '_page', wraps=scanner._page) as pages:
                self.assertTrue(scanner.matches(quote, 24))
                self.assertEqual([c.args[0] for c in pages.call_args_list], [24])
            with patch.object(scanner, '_page', wraps=scanner._page) as pages:
                self.assertTrue(scanner.matches(quote, 23))
                self.assertEqual([c.args[0] for c in pages.call_args_list], [23, 1, 24])
            with patch.object(search, 'prepare_search_page', wraps=search.prepare_search_page) as prepare:
                self.assertTrue(scanner.matches(quote, 23))
                prepare.assert_not_called()
            with patch.object(search, 'MAX_CACHE_CHARS', 12):
                small = search.RecordQuoteSearch(root)
                self.assertTrue(small.matches(quote, 23))
                self.assertLessEqual(small._cache_chars, 12)

    def test_no_cross_page_join_no_summary_search_and_duplicates_are_ok(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'text_pages').mkdir()
            (root / 'text_pages/0001.txt').write_text('first half of the')
            (root / 'text_pages/0002.txt').write_text('quotation ends here')
            (root / 'text_pages/notes.txt').write_text('made up wording')
            (root / 'summaries').mkdir()
            (root / 'summaries/final.txt').write_text('made up wording')
            scanner = search.RecordQuoteSearch(root / 'text_pages')
            self.assertFalse(scanner.matches('first half of the quotation ends here', 1))
            self.assertFalse(scanner.matches('made up wording', 1))
            (root / 'text_pages/0001.txt').write_text('repeated words')
            (root / 'text_pages/0002.txt').write_text('repeated words')
            self.assertTrue(scanner.matches('repeated words', 1))
            self.assertFalse(scanner.matches('   ', 1))

    def test_page_preprocessing_uses_that_pages_classification_not_quote_kind(self):
        from test_transcript_quote_search import transcript, QUOTE
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'text_pages').mkdir()
            (root / 'artifacts').mkdir()
            (root / 'text_pages/0001.txt').write_text('A report with no quotation.')
            (root / 'text_pages/0002.txt').write_text(transcript())
            (root / 'artifacts/hearing_boundaries.json').write_text(json.dumps([
                {'start_page': 2, 'end_page': 2}]))
            scanner = search.RecordQuoteSearch(root / 'text_pages')
            self.assertEqual(scanner.reading_pages, {2})
            self.assertTrue(scanner.matches(QUOTE, 1))
            (root / 'artifacts/report_boundaries.json').write_text(json.dumps([
                {'start_page': 2, 'end_page': 2}]))
            conflicting = search.RecordQuoteSearch(root / 'text_pages')
            self.assertFalse(conflicting.matches(QUOTE, 1))

    def test_canonical_row_keeps_model_page_hash_and_no_invented_offsets(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            (root / 'artifacts/motion_boundaries.json').write_text(json.dumps([
                {'start_page': '0001', 'end_page': '0001', 'motion_name': 'Synthetic motion',
                 'motion_date': '', 'motion_date_basis': 'unknown'}]))
            (root / 'text_pages/0001.txt').write_text('Discussion starts here.')
            (root / 'text_pages/0024.txt').write_text('No objection to the biological elevation today.')
            protected = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                         for p in (root / 'text_pages').iterdir()}
            for kind in sa.SUMMARY_KINDS:
                config = sa.effective_extraction_config(project, kind)
                with patch('warnings.warn'):
                    item = sa.build_work_items(root, config)[0]
                self.assertNotIn('No objection', sa.item_source_payload(item, root / 'text_pages', {}))
                row = sa.canonicalize_extraction_candidate({'categories': [{
                    'id': config.definitions[0].identifier, 'digest': {'text': 'A response was given.',
                    'evidence': [{'text': 'No objection to the biological elevation today', 'file_page': 1}]}}]},
                    item, root / 'text_pages')
                q = row['categories'][0]['digest']['evidence'][0]
                self.assertTrue(q['verified'])
                self.assertEqual(q['file_page'], 1)
                self.assertEqual(q['source_sha256'], hashlib.sha256(protected[root / 'text_pages/0001.txt'][0]).hexdigest())
                self.assertNotIn('source_start', q)
                text = sa.serialize_digest_markdown(kind, 'Synthetic', [row])
                self.assertIn('Model-reported file page 1 — Verified', text)
                self.assertEqual(sa.parse_digest_markdown(text, kind, 'Synthetic'), [row])
                # Historical visible grammar stays readable without relabeling rows.
                self.assertEqual(sa.parse_digest_markdown(text.replace('Model-reported file page', 'File page'),
                                                          kind, 'Synthetic'), [row])
            self.assertEqual(protected, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})

    def test_unrelated_record_page_change_invalidates_generation_not_document_input(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            config = sa.effective_extraction_config(project, 'reports')
            before = sa.build_work_items(root, config)[0]
            other = root / 'text_pages/0099.txt'
            other.write_text('A new searchable source page.')
            after = sa.build_work_items(root, config)[0]
            self.assertEqual(before.input_sha256, after.input_sha256)
            self.assertNotEqual(before.generation_sha256, after.generation_sha256)
            other.write_text('Changed searchable source.')
            changed = sa.build_work_items(root, config)[0]
            self.assertNotEqual(after.generation_sha256, changed.generation_sha256)

    def test_stop_and_unsafe_source_are_not_silent_no_hits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '0001.txt').write_text('source')
            def stop():
                raise InterruptedError('synthetic stop')
            scanner = search.RecordQuoteSearch(root, check_stop=stop)
            with self.assertRaises(InterruptedError):
                scanner.matches('missing', 1)
            (root / '0002.txt').symlink_to(root / '0001.txt')
            scanner = search.RecordQuoteSearch(root)
            with self.assertRaises((ValueError, OSError)):
                scanner.matches('missing', 1)

    def test_focus_classification_mirror_pinned(self):
        self.assertEqual(hashlib.sha256(Path(focus_record_categories.__file__).read_bytes()).hexdigest(),
                         '5c75dec26412059e88ffe20e867e33ac990bee7cf4f90eaafe5fb1b41b0dd391')


if __name__ == '__main__':
    unittest.main()
