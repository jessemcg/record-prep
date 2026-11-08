"""Advisory anchors: delivery, compatibility and faithful nonfatal storage.

Synthetic only. No model judgment or record-wide uniqueness claim is tested.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import summary_agents as sa, summary_profiles as sp
from recordprep import summary_quote_policy as policy
from recordprep.prompt_inspection import inspect_prompt
from test_minute_summaries import fixture
from test_structured_classification import bundle

ROOT = Path(__file__).resolve().parents[1]


def summary_fixture(base):
    from tests.test_summary_agent_pipeline import _participant_index
    root, project = fixture(base, 1)
    boundary = {'start_page': '0001', 'end_page': '0001', 'date': 'March 1, 2025'}
    (root / 'artifacts/hearing_boundaries.json').write_text(json.dumps([boundary]))
    (root / 'artifacts/report_boundaries.json').write_text(json.dumps([
        dict(boundary, report_name='Synthetic report', report_date='March 1, 2025')]))
    (root / 'artifacts/participant_index.json').write_text(json.dumps(_participant_index([(1, 1, 'March 1, 2025')])))
    return root, project


class QuotePolicyTests(unittest.TestCase):
    def test_policy_parity_and_previous_builtins(self):
        self.assertEqual((sa.QUOTE_MIN_WORDS, sa.QUOTE_MAX_WORDS), (6, 12))
        self.assertEqual(sa.SUMMARY_EXTRACTION_CONTRACT_VERSION, 5)
        self.assertIn('two-to-five-word', sp.PREVIOUS_EXTRACTION)
        for kind, previous in (
            ('hearings', sa.PREVIOUS_SHORT_QUOTE_HEARING_EXTRACTION_GUIDANCE),
            ('reports', sa.PREVIOUS_SHORT_QUOTE_REPORT_EXTRACTION_GUIDANCE),
        ):
            self.assertIn('two-to-five-word', previous)
            self.assertIn(previous, sa.HISTORICAL_BUILTIN_GUIDANCE[(kind, 'extract')])
            for old in sa.HISTORICAL_BUILTIN_GUIDANCE[(kind, 'extract')]:
                resolved = sa.resolve_phase_guidance(kind, 'extract', old)
                self.assertEqual(resolved.origin, 'migrated')
                self.assertEqual(resolved.custom_guidance, '')
                self.assertIn(policy.EXTRACTION_QUOTE_GUIDANCE.strip(), resolved.immutable_guidance)
            custom = '  Personal focus.\r\nKeep this byte-for-byte.  \n'
            resolved = sa.resolve_phase_guidance(kind, 'extract', custom)
            self.assertEqual(resolved.origin, 'custom')
            self.assertEqual(resolved.custom_guidance, custom)
        with tempfile.TemporaryDirectory() as td:
            _root, project = fixture(Path(td), 1)
            for profile in (None, bundle()):
                for kind in sa.SUMMARY_KINDS:
                    config = sa.effective_extraction_config(project, kind, profile=profile)
                    self.assertIn(policy.EXTRACTION_QUOTE_GUIDANCE.strip(), config.guidance)
                    self.assertNotIn('two-to-five', config.guidance)
                    self.assertNotIn('three-to-five', config.guidance)
                    view = inspect_prompt({}, kind + '-extract', ROOT / '.pi')
                    self.assertEqual(view.issues, ())
                    self.assertIn(policy.EXTRACTION_QUOTE_GUIDANCE.strip(), view.display_text())

    def test_inclusive_length_boundaries_only_warn_and_count_whitespace(self):
        for count in (5, 6, 8, 10, 12, 13):
            phrase = ' '.join(['source'] * count)
            flags = sa.quote_convention_flags('report:0001', 'report:0001/topic/1', phrase)
            expected = ([f'quote_length_out_of_range:report:0001:report:0001/topic/1:{count}']
                        if count in (5, 13) else [])
            self.assertEqual(flags, expected)
        phrase = "mother's  in-home\nvisits remain supervised each Saturday"
        self.assertEqual(len(sa._normalized_words(phrase)), 7)
        self.assertEqual(sa.quote_convention_flags('report:0001', 'q', phrase), [])

    def test_outliers_and_historical_short_quotes_roundtrip_unchanged(self):
        phrases = [
            'remains supervised',  # Historical short quotation remains readable.
            'visits remain supervised each Saturday',
            'supervised visitation at the community center every Saturday',
            'the court finds that notice has been given as required by law today',
        ]
        with tempfile.TemporaryDirectory() as td:
            root, project = summary_fixture(Path(td))
            for kind in sa.SUMMARY_KINDS:
                config = sa.effective_extraction_config(project, kind)
                # A synthetic motion boundary; no saved groups means singleton scope.
                if kind == 'motions':
                    (root / 'artifacts/motion_boundaries.json').write_text(json.dumps([
                        {'start_page': '0001', 'end_page': '0001', 'motion_name': 'Motion to inspect',
                         'motion_date': '', 'motion_date_basis': 'unknown'}]))
                page = root / 'text_pages/0001.txt'
                # Report fixture boundaries also start on this page.
                page.write_text('Before.\n' + '\n'.join(phrases) + '\nAfter.')
                with patch('warnings.warn'):
                    item = sa.build_work_items(root, config)[0]
                source_page = root / f'text_pages/{item.start_page:04d}.txt'
                source_page.write_bytes(page.read_bytes())
                raw = source_page.read_text()
                watched = (source_page.read_bytes(), source_page.stat().st_mtime_ns)
                topic = config.definitions[0].identifier
                prose = 'The source describes the contested supervision condition.'
                row = sa.canonicalize_extraction_candidate({'categories': [
                    {'id': topic, 'digest': {'text': prose, 'evidence': [
                        {'text': phrase, 'file_page': item.start_page} for phrase in phrases]}}
                ]}, item, root / 'text_pages')
                evidence = row['categories'][0]['digest']['evidence']
                original = copy.deepcopy(evidence)
                for quote, phrase in zip(evidence, phrases):
                    self.assertTrue(quote['verified'])
                    self.assertEqual(quote['text'], phrase)
                    self.assertEqual(raw[quote['source_start']:quote['source_end']], phrase)
                    self.assertEqual(quote['source_sha256'], hashlib.sha256(source_page.read_bytes()).hexdigest())
                markdown = sa.serialize_digest_markdown(kind, 'Synthetic', [row])
                rows = sa.parse_digest_markdown(markdown, kind, 'Synthetic')
                self.assertEqual(rows, [row])
                placeholders = ' '.join('{{quote:' + q['quote_id'] + '}}' for q in evidence)
                sections, flags = sa.normalize_synthesis_sections(rows, [
                    {'item_id': item.item_id, 'paragraphs': [placeholders]}])
                self.assertTrue(any(f.endswith(':5') for f in flags if f.startswith('quote_length_out_of_range:')))
                self.assertTrue(any(f.endswith(':13') for f in flags if f.startswith('quote_length_out_of_range:')))
                final = sa.render_final_summary(kind, 'Synthetic', rows, sections,
                                               {item.item_id: (item.start_page, None)})
                for phrase in phrases:
                    self.assertIn(phrase, final)
                fallback, _ = sa.normalize_synthesis_sections(rows, [])
                self.assertIn(prose, sa.render_final_summary(kind, 'Synthetic', rows, fallback,
                                                            {item.item_id: (item.start_page, None)}))
                # Exercise canonical disk publication too: outliers never request
                # repair, prevent publication, or mutate the evidence bank.
                sa.publish_digests(root, kind, [item], config, rows)
                published = sa.reload_published_digest_rows(root, kind, [item])
                self.assertEqual(published[0]['categories'][0]['digest']['evidence'], original)
                self.assertEqual(rows[0]['categories'][0]['digest']['evidence'], original)
                self.assertEqual(watched, (source_page.read_bytes(), source_page.stat().st_mtime_ns))

    def test_old_contract_checkpoints_stale_without_rewriting_and_new_reuse(self):
        from recordprep import minute_summaries
        with tempfile.TemporaryDirectory() as td, patch('recordprep.case_profiles.resolve_case_profile', return_value=None):
            root, project = summary_fixture(Path(td))
            before_minute = minute_summaries.stage_config(project)[1]
            def publish(config, items):
                rows = [sa.canonicalize_extraction_candidate({'categories': [
                    {'id': config.definitions[0].identifier,
                     'digest': {'text': 'Useful saved digest.', 'evidence': []}}]},
                    item, root / 'text_pages') for item in items]
                sa.publish_digests(root, 'reports', items, config, rows)
            with patch.object(sa, 'SUMMARY_EXTRACTION_CONTRACT_VERSION', 4):
                previous = sa.effective_extraction_config(project, 'reports')
                publish(previous, sa.build_work_items(root, previous))
            watched = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                       for p in (root / 'summaries').iterdir() if p.is_file()}
            current = sa.effective_extraction_config(project, 'reports')
            old = copy.deepcopy(current.fingerprint_payload())
            old['content_contract'] = 4
            self.assertNotEqual(sa.sha256_json(old), current.fingerprint)
            # Check via actual checkpoint reader; no automatic regeneration or writes.
            self.assertTrue(sa.summary_stage_freshness_issues(root, 'reports', project_dir=project))
            self.assertEqual(watched, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched})
            items = sa.build_work_items(root, current)
            _rows, pending = sa.validate_digest_state(root, 'reports', items, current)
            self.assertEqual(pending, [item.item_id for item in items])
            publish(current, items)
            _rows, pending = sa.validate_digest_state(root, 'reports', items, current)
            self.assertEqual(pending, [])
            self.assertEqual(before_minute, minute_summaries.stage_config(project)[1])
