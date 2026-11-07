"""Nonempty motion summaries and advisory output handling; fictional/offline only."""
import json
from pathlib import Path
import tempfile
import unittest

from recordprep import summary_agents as sa
from test_structured_classification import bundle
import test_summary_agent_pipeline as pipeline_tests


class MotionSummaryResilienceTests(unittest.TestCase):
    def _bundle(self, temp):
        root = temp / 'bundle'
        builder = pipeline_tests.BundleBuilder(root)
        starts = (98, 102, 106, 110)
        titles = ('Motion for Protective Order', 'Opposition', 'Reply', 'Supporting Declaration')
        for start, marker in zip(starts, ('aa bb', 'cc dd', 'ee ff', 'gg hh')):
            builder.add_pages(start, start + 1, marker)
        boundaries = [dict(motion_id=f'motion:{start:04d}', start_page=f'{start:04d}',
                           end_page=f'{start + 1:04d}', motion_name=title,
                           motion_date='', motion_date_basis='unknown')
                      for start, title in zip(starts, titles)]
        (root / 'artifacts/motion_boundaries.json').write_text(json.dumps(boundaries))
        return root

    def _run(self, temp, root, script):
        acceptance = pipeline_tests.FakePiEndToEndTests()
        fake = temp / 'fake-pi'
        fake.write_text(script)
        fake.chmod(0o755)
        project = acceptance._staged_project(temp)
        log = temp / 'invocations.log'
        result = acceptance._run_stage('create_motion_summaries', root, project, fake, log)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = sa.load_digest_markdown(root, 'motions')
        self.assertEqual([r['item_id'] for r in rows],
                         ['motion:0098', 'motion:0102', 'motion:0106', 'motion:0110'])
        final = sa.summary_final_path(root, 'motions').read_text()
        self.assertEqual(sa.validate_final_meta(root, 'motions'), [])
        for row in rows:
            self.assertIn(row['label'], final)
        calls = [json.loads(line) for line in log.read_text().splitlines()
                 if '--version' not in line and 'rpc' not in line]
        # Four extractions plus one synthesis: no extra repair/quality pass.
        self.assertEqual(len(calls), 5)
        self.assertNotIn('QUOTEME', result.stdout + result.stderr)
        return rows, final, result

    def test_four_nonempty_motion_papers_publish_quotes_and_reload(self):
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            rows, final, _ = self._run(temp, self._bundle(temp), pipeline_tests.FakePiEndToEndTests.FAKE_PI)
            for row, marker in zip(rows, ('aa bb', 'cc dd', 'ee ff', 'gg hh')):
                quote = row['categories'][0]['digest']['evidence'][0]
                self.assertEqual(quote['quote_id'], f"{row['item_id']}/request/1")
                self.assertTrue(quote['verified'])
                self.assertIn(f'“{marker} unique phrase here”', final)
            self.assertNotIn('{{quote:', final)

    def test_profile_and_unassigned_motion_codec_preserves_imperfect_evidence(self):
        for profile in (None, bundle()):
            with self.subTest(profile=profile is not None), tempfile.TemporaryDirectory() as temporary:
                temp = Path(temporary)
                root = self._bundle(temp)
                config = sa.ExtractionConfig('motions', '', profile=profile)
                items = sa.build_work_items(root, config)
                rows = []
                for item in items:
                    category_id = (sa.extraction_metadata(profile, 'motions')['category_catalog'][0]['id']
                                   if profile else 'request')
                    candidate = {'item_id': 'invented', 'categories': [
                        {'id': category_id, 'digest': {
                            'text': 'The moving party requests protection, not a court ruling.',
                            'evidence': [{'text': 'unmatched source wording', 'file_page': item.start_page,
                                          'quote_id': 'invented-by-model'}]}},
                        {'id': 'unknown', 'digest': {'text': 'Unknown category'}}]}
                    row = sa.canonicalize_extraction_candidate(candidate, item, root / 'text_pages')
                    quote = row['categories'][0]['digest']['evidence'][0]
                    self.assertFalse(quote['verified'])
                    self.assertEqual(quote['quote_id'], f'{item.item_id}/{category_id}/1')
                    self.assertTrue(row['quality_flags'])
                    rows.append(row)
                text = sa.serialize_digest_markdown('motions', 'SynCase', rows)
                self.assertEqual(sa.parse_digest_markdown(text, 'motions', 'SynCase'), rows)
                self.assertIn('motion:0098/', sa.document_markdown_block(rows[0]))

    def test_imperfect_sections_keep_other_papers_and_digest_fallbacks(self):
        injection = '''    sections[0]["paragraphs"] = ["Bad reference {{quote:motion:9999/requested_relief/1}}."]
    sections[1]["paragraphs"] = None
    sections[2]["paragraphs"] = "Useful reply narrative kept as one paragraph."
'''
        script = pipeline_tests.FakePiEndToEndTests.FAKE_PI.replace(
            '    Path(dataset["candidate_path"]).write_text(json.dumps({',
            injection + '    Path(dataset["candidate_path"]).write_text(json.dumps({')
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            _, final, result = self._run(temp, self._bundle(temp), script)
            self.assertIn('Synthetic digest recorded by the fake agent.', final)
            self.assertIn('Useful reply narrative kept as one paragraph.', final)
            self.assertIn('“gg hh unique phrase here”', final)
            self.assertNotIn('Bad reference', final)
            self.assertIn('unknown_placeholder_fallback:motion:0098', result.stdout)
            self.assertIn('malformed_paragraphs_fallback:motion:0102', result.stdout)

    def test_unusable_extraction_output_does_not_cancel_other_papers(self):
        for output in ('missing', 'malformed'):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as temporary:
                injection = '''    if spec["ordinal"] == 2:
'''
                if output == 'malformed':
                    injection += '        Path(spec["candidate_path"]).write_text("not json")\n'
                injection += '        raise SystemExit(0)\n'
                script = pipeline_tests.FakePiEndToEndTests.FAKE_PI.replace(
                    '    categories = []\n', injection + '    categories = []\n')
                temp = Path(temporary)
                rows, final, result = self._run(temp, self._bundle(temp), script)
                self.assertTrue(all(c['digest'] is None for c in rows[1]['categories']))
                self.assertIn('candidate_unusable:all_null', rows[1]['quality_flags'])
                self.assertIn('“aa bb unique phrase here”', final)
                self.assertIn('“gg hh unique phrase here”', final)
                self.assertIn(f'extraction_candidate_{output}', result.stdout)

    def test_unusable_synthesis_output_uses_saved_digests_without_repair_call(self):
        for output, data in (('missing', None), ('malformed', 'not json'), ('nonobject', '[]')):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as temporary:
                injection = ''
                if data is not None:
                    injection += f'    Path(dataset["candidate_path"]).write_text({data!r})\n'
                injection += '    raise SystemExit(0)\n'
                script = pipeline_tests.FakePiEndToEndTests.FAKE_PI.replace(
                    '    sections = []\n', injection + '    sections = []\n')
                temp = Path(temporary)
                _, final, result = self._run(temp, self._bundle(temp), script)
                self.assertEqual(final.count('Synthetic digest recorded by the fake agent.'), 4)
                self.assertIn(f'synthesis_candidate_{output}', result.stdout)
                meta = sa.load_final_meta(temp / 'bundle', 'motions')
                self.assertIn(f'synthesis_candidate_{output}', meta['quality_flags'])

    def test_generated_ids_beyond_four_digits_round_trip_for_every_kind(self):
        from tests.summary_agent_fixtures import synthetic_facts_row
        for kind in sa.SUMMARY_KINDS:
            with self.subTest(kind=kind):
                category_id = sa.SUMMARY_CATEGORY_IDS[kind][0]
                row = synthetic_facts_row(kind, start=10000, end=10000, facts={category_id: [{
                    'text': 'Synthetic digest.',
                    'evidence': [{'text': 'source phrase', 'file_page': 10000}]}]})
                text = sa.serialize_digest_markdown(kind, 'SynCase', [row])
                self.assertEqual(sa.parse_digest_markdown(text, kind, 'SynCase'), [row])

    def test_malformed_paragraph_values_never_raise(self):
        from tests.summary_agent_fixtures import synthetic_facts_row
        row = synthetic_facts_row('motions', facts={'requested_relief': [{
            'text': 'A protective order is requested.', 'evidence': []}]})
        for paragraphs in (None, 42, True, {}, [None, 42]):
            with self.subTest(paragraphs=paragraphs):
                sections, flags = sa.normalize_synthesis_sections(
                    [row], [{'item_id': row['item_id'], 'paragraphs': paragraphs}])
                self.assertEqual(sections[0].paragraphs, ['A protective order is requested.'])
                self.assertTrue(flags)
