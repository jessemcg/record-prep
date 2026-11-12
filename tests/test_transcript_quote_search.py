"""Synthetic Focus transcript-search regressions; never rewrite case data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import summary_agents as sa, record_quote_search as record_search
from recordprep import focus_transcript_reading as projection
from recordprep.quote_search import prepare_search_page, quote_matches_focus_search
from test_summary_quote_policy import summary_fixture

QUOTE = 'ALSO PRESENT IN THE COURTROOM ARE PATERNAL GRANDMOTHER'


def transcript(style='detached'):
    rows = ['THE COURT CONTINUES ITS REVIEW OF THE MATERIAL BEFORE IT'] * 28
    rows[9] = 'THE CLERK: ALSO PRESENT IN THE'
    rows[10] = 'COURTROOM ARE PATERNAL GRANDMOTHER AND OTHER FAMILY MEMBERS'
    rows[14] = 'THE COURT: THE REVIEW PERIOD IS 12 MONTHS FROM THIS DATE'
    if style == 'detached':
        return '\n\n'.join(f'{i}\n\n{line}' for i, line in enumerate(rows, 1))
    if style == 'bar':
        return '\n\n'.join(f'{i:2} | {line}' for i, line in enumerate(rows, 1))
    if style == 'plain':
        return '\n\n'.join(f'{i:2}  {line}' for i, line in enumerate(rows, 1))
    if style == 'flat':
        return ' '.join(f'{i} {line}' for i, line in enumerate(rows, 1))
    raise ValueError(style)


class TranscriptQuoteSearchTests(unittest.TestCase):
    def test_vendored_focus_module_identity(self):
        # Byte-identical Focus/focus/transcript_reading.py at adoption. Update only
        # after a reviewed upstream change plus actual-Focus conformance testing.
        self.assertEqual(hashlib.sha256(Path(projection.__file__).read_bytes()).hexdigest(),
                         '168ab3437f0edece873b27d72bf4d982c320463b172d1d101f447488186b2ec7')

    def test_standalone_gutter_regression_and_other_layouts(self):
        for style in ('detached', 'bar', 'plain', 'flat'):
            with self.subTest(style=style):
                source = transcript(style)
                layout = projection.search_layout(source)
                self.assertIsNotNone(layout)
                projected, _ = projection.search_projection(source, layout=layout)
                self.assertIn('12 MONTHS', projected)  # Real quantities survive.
                self.assertTrue(quote_matches_focus_search(QUOTE, source, transcript=True))
                self.assertNotIn('11\n\nCOURTROOM', projected)
                self.assertEqual(source, transcript(style))
                if style == 'detached':
                    self.assertFalse(quote_matches_focus_search(QUOTE, source))
                self.assertFalse(quote_matches_focus_search(
                    QUOTE.replace('GRANDMOTHER', 'GRANDFATHER'), source, transcript=True))

    def test_nontranscripts_ambiguous_lists_tables_and_limits_remain_raw(self):
        cases = [
            'ALSO PRESENT IN THE\n\n11\n\nCOURTROOM ARE PATERNAL GRANDMOTHER',
            '\n\n'.join(f'{i}\n\nThis numbered requirement is independently material.' for i in range(1, 29)),
            '1 | EXHIBIT 1: Statement.\n2 | EXHIBIT 2: Report.\n3 | EXHIBIT 3: Letter.',
            '1 | Name   Amount   Date\n2 | Alpha   12   Today\n3 | Beta   13   Tomorrow',
            transcript() + 'x' * projection.MAX_PAGE_BYTES,
            '1\n\nA short list\n\n2\n\nA second item',
        ]
        from recordprep.quote_search import normalize_text_for_search
        for source in cases:
            with self.subTest(size=len(source)):
                self.assertIsNone(projection.search_layout(source))
                self.assertEqual(prepare_search_page(source, transcript=True), normalize_text_for_search(source))
        self.assertEqual(prepare_search_page(transcript()), normalize_text_for_search(transcript()))

    def test_canonical_pipeline_scope_cache_hashes_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            (root / 'artifacts/motion_boundaries.json').write_text(json.dumps([
                {'start_page': '0001', 'end_page': '0001', 'motion_name': 'Synthetic motion',
                 'motion_date': '', 'motion_date_basis': 'unknown'}]))
            page = root / 'text_pages/0001.txt'
            page.write_text(transcript())
            protected = (page.read_bytes(), page.stat().st_mtime_ns)
            boundary_paths = {kind: root / 'artifacts' / f'{sa.SUMMARY_KIND_LABELS[kind]}_boundaries.json'
                              for kind in sa.SUMMARY_KINDS}
            boundaries = {kind: path.read_text() for kind, path in boundary_paths.items()}
            (root / 'artifacts/minutes_boundaries.json').write_text('[]')
            for kind in sa.SUMMARY_KINDS:
                # Focus's strict index rejects contradictory synthetic boundaries.
                # Only the current document owns this page in each test scenario.
                for other, path in boundary_paths.items():
                    path.write_text(boundaries[other] if other == kind else '[]')
                config = sa.effective_extraction_config(project, kind)
                with patch('warnings.warn'):
                    item = sa.build_work_items(root, config)[0]
                candidate = {'categories': [{'id': config.definitions[0].identifier,
                    'digest': {'text': 'The clerk described the appearances.', 'evidence': [
                        {'text': QUOTE, 'file_page': 1},
                        {'text': QUOTE, 'file_page': 1},
                        {'text': QUOTE, 'file_page': 2},
                    ]}}]}
                with patch.object(record_search, 'prepare_search_page', wraps=prepare_search_page) as prepare:
                    row = sa.canonicalize_extraction_candidate(candidate, item, root / 'text_pages')
                prepare.assert_called_once_with(transcript(), transcript=kind == 'hearings')
                quotes = row['categories'][0]['digest']['evidence']
                self.assertEqual(len(quotes), 2)  # Out-of-scope page remains rejected.
                for quote in quotes:
                    self.assertEqual(quote['verified'], kind == 'hearings')
                    self.assertEqual(quote['text'], QUOTE)
                    self.assertEqual(quote['source_sha256'], hashlib.sha256(protected[0]).hexdigest())
                    self.assertNotIn('source_start', quote)  # No projected offsets masquerade as source offsets.
                self.assertEqual(sa.parse_digest_markdown(
                    sa.serialize_digest_markdown(kind, 'Synthetic', [row]), kind, 'Synthetic'), [row])
                self.assertEqual((page.read_bytes(), page.stat().st_mtime_ns), protected)

    def test_record_search_tracks_transcript_contract_all_kinds_and_old_rows_stay_literal(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            for kind in sa.SUMMARY_KINDS:
                payload = sa.effective_extraction_config(project, kind).fingerprint_payload()
                self.assertIn('transcript_search_contract', payload)
            config = sa.effective_extraction_config(project, 'hearings')
            old_payload = config.fingerprint_payload()
            old_payload.pop('transcript_search_contract')
            page = root / 'text_pages/0001.txt'
            page.write_text(transcript())
            with patch.object(sa.ExtractionConfig, 'fingerprint_payload', return_value=old_payload):
                items = sa.build_work_items(root, config)
                with patch.object(record_search.RecordQuoteSearch, 'matches', return_value=False):
                    rows = [sa.canonicalize_extraction_candidate({'categories': [{
                        'id': config.definitions[0].identifier, 'digest': {'text': 'Appearance.',
                        'evidence': [{'text': QUOTE, 'file_page': 1}]}}]}, items[0], root / 'text_pages')]
                sa.publish_digests(root, 'hearings', items, config, rows)
            protected = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                         for p in (root / 'summaries').iterdir() if p.is_file()}
            current = sa.build_work_items(root, config)
            _, pending = sa.validate_digest_state(root, 'hearings', current, config)
            self.assertEqual(pending, [item.item_id for item in current])
            saved = sa.reload_published_digest_rows(root, 'hearings', items)
            self.assertFalse(saved[0]['categories'][0]['digest']['evidence'][0]['verified'])
            self.assertEqual(protected, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})


if __name__ == '__main__':
    unittest.main()
