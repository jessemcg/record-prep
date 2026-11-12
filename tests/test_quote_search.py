"""Synthetic regression tests for Focus-compatible verification; no private data."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep.quote_search import quote_matches_focus_search as matches
from test_summary_quote_policy import summary_fixture
from test_structured_classification import bundle


class QuoteSearchTests(unittest.TestCase):
    def test_focus_search_rules(self):
        cases = [
            ("I've reviewed the petition and the detention report",
             "21 I've reviewed the petition and the detention 22 report.", True),
            ("I've reviewed the petition", "I’VE reviewed\n the petition", True),
            ('the office report', 'the oﬃce report', True),
            ('the report', 'the\u00a0report', True),
            ('the report', 'the • report', True),
            ('the report', 'the\n\nreport', True),
            ('the report', 'the\n\n\nreport', False),
            ('the report', 'the 12345678 report', True),
            ('the report', 'the 123456789 report', False),
            ('the report', 'the 12 13 report', False),
            ('the report', 'the changed report', False),
            ('the report', 'the re port', True),
            ('the report', 'the "report"', True),
            ('new information', 'new 3 | information', True),
            ('new information', 'new|information', True),
            ('new information', 'new || information', True),
            ('new | information', 'new information', True),
            ('new information', 'new 3 | different information', False),
            ('court-ordered review', 'court-\nordered review', True),
            ('court-ordered review', 'court—ordered review', True),
            ('court ordered review', 'court ordered other review', False),
            ('the order', 'the or-\nder', False),
            ('the order', 'the or\u00adder', False),
            ('', 'any source', False),
            ('  ', 'any source', False),
        ]
        for quote, source, expected in cases:
            with self.subTest(quote=quote, source=source):
                self.assertEqual(matches(quote, source), expected)

    def test_canonical_verification_all_kinds_roundtrip_and_source_preservation(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            (root / 'artifacts/motion_boundaries.json').write_text(json.dumps([
                {'start_page': '0001', 'end_page': '0001', 'motion_name': 'Synthetic motion',
                 'motion_date': '', 'motion_date_basis': 'unknown'}]))
            page = root / 'text_pages/0001.txt'
            source = "I've reviewed the petition and the detention 22 | report. The other order."
            page.write_text(source)
            watched = (page.read_bytes(), page.stat().st_mtime_ns)
            for kind in sa.SUMMARY_KINDS:
                config = sa.effective_extraction_config(project, kind)
                with patch('warnings.warn'):
                    item = sa.build_work_items(root, config)[0]
                topic = config.definitions[0].identifier
                row = sa.canonicalize_extraction_candidate({'categories': [
                    {'id': topic, 'digest': {'text': 'The court reviewed the materials.', 'evidence': [
                        {'text': "I've reviewed the petition and the detention report", 'file_page': 1},
                        {'text': 'The other order', 'file_page': 1},
                        {'text': 'The invented order', 'file_page': 1},
                        {'text': 'The other order', 'file_page': 2},
                    ]}}]}, item, root / 'text_pages')
                evidence = row['categories'][0]['digest']['evidence']
                self.assertEqual([q['verified'] for q in evidence], [True, True, False])
                self.assertNotIn('source_start', evidence[0])
                exact = evidence[1]
                self.assertEqual(source[exact['source_start']:exact['source_end']], exact['text'])
                self.assertEqual(sa.parse_digest_markdown(
                    sa.serialize_digest_markdown(kind, 'Synthetic', [row]), kind, 'Synthetic'), [row])
                self.assertEqual(watched, (page.read_bytes(), page.stat().st_mtime_ns))

    def test_freshness_identifies_new_verification_without_rewriting_saved_digests(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            for kind in ('hearings', 'reports'):
                config = sa.effective_extraction_config(project, kind)
                old_payload = copy.deepcopy(config.fingerprint_payload())
                old_payload['quote_search_contract'] = 'focus-phrase-search-1'
                with patch.object(sa.ExtractionConfig, 'fingerprint_payload', return_value=old_payload):
                    items = sa.build_work_items(root, config)
                    rows = [sa.canonicalize_extraction_candidate({'categories': []}, item, root / 'text_pages')
                            for item in items]
                    sa.publish_digests(root, kind, items, config, rows)
                watched = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                           for p in (root / 'summaries').iterdir() if p.is_file()}
                current = sa.build_work_items(root, config)
                _, pending = sa.validate_digest_state(root, kind, current, config)
                self.assertEqual(pending, [i.item_id for i in current])
                self.assertEqual(watched, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched})

    def test_verified_only_guidance_all_profiles_and_no_extraction_instruction_leak(self):
        project = Path(__file__).resolve().parents[1] / '.pi'
        for profile in (None, bundle()):
            for kind in sa.SUMMARY_KINDS:
                synthesis = sa.effective_synthesis_config(project, kind, profile=profile)
                self.assertIn('VERIFIED QUOTATIONS ONLY', synthesis['guidance'])
                extraction = sa.effective_extraction_config(project, kind, profile=profile)
                self.assertNotIn('VERIFIED QUOTATIONS ONLY', extraction.guidance)
                self.assertEqual(extraction.fingerprint_payload()['quote_search_contract'], 'focus-phrase-search-2')


if __name__ == '__main__':
    unittest.main()
