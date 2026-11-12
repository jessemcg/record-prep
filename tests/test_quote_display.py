"""Case-only display never changes canonical evidence or extraction contracts."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from recordprep import summary_agents as sa
from recordprep.quote_display import NORMALIZATION_NOTICE, QUOTE_CASE_GUIDANCE, display_quote
from recordprep.summary_editions import build_summary_edition

PROJECT = Path(__file__).resolve().parents[1]
ITEM = 'hearing:0001'
QUOTE = ITEM + '/court_orders_and_reasons/1'


def row(text='JCO TO THE MOTHER'):
    return {'item_id': ITEM, 'ordinal': 1, 'kind': 'hearings', 'label': 'Synthetic hearing',
            'start_page': 1, 'end_page': 1,
            'categories': [{'id': 'court_orders_and_reasons', 'digest': {
                'text': 'The court made an order.', 'evidence': [
                    {'quote_id': QUOTE, 'text': text, 'file_page': 1, 'verified': True}]}}]}


def entry(proposal, paragraph=None):
    return {'item_id': ITEM, 'paragraphs': [paragraph or 'The court ordered {{quote:' + QUOTE + '}}.'],
            'quote_capitalizations': proposal}


class QuoteDisplayTests(unittest.TestCase):
    def test_all_narrative_skills_require_capitalization_check(self):
        self.assertIn('For EVERY used quote id', QUOTE_CASE_GUIDANCE)
        for kind in ('hearings', 'reports', 'motions'):
            with self.subTest(kind=kind):
                skill = (PROJECT / '.pi/skills' / ('recordprep-synthesize-' + kind) / 'SKILL.md').read_text()
                self.assertNotIn('## Quotation capitalization', skill)
                self.assertIn('For EVERY used quote id', skill)
                self.assertIn('Only quote-free sections may omit the map', skill)
                self.assertIn('`quote_selections`', skill)
                self.assertNotIn('optional quote_capitalizations', skill)

    def test_sentence_initial_word_adjustment_for_all_narrative_kinds(self):
        for kind, prefix in (('hearings', 'hearing'), ('reports', 'report'), ('motions', 'motion')):
            with self.subTest(kind=kind):
                source = row('The ICWA reviewer joined by Webex')
                item = prefix + ':0001'
                quote = item + '/court_orders_and_reasons/1'
                source.update(kind=kind, item_id=item)
                source['categories'][0]['digest']['evidence'][0]['quote_id'] = quote
                before = copy.deepcopy(source)
                candidate = {'item_id': item, 'paragraphs': ['The author stated that {{quote:' + quote + '}}.'],
                             'quote_capitalizations': {quote: 'the ICWA reviewer joined by Webex'}}
                sections, flags = sa.normalize_synthesis_sections([source], [candidate])
                text = sa.render_final_summary(kind, 'Synthetic', [source], sections, {item: (1, None)})
                self.assertIn('that “the ICWA reviewer joined by Webex”', text)
                self.assertNotIn('quote_capitalization_rejected:' + item, flags)
                self.assertEqual(source, before)
                candidate.pop('quote_capitalizations')
                sections, _ = sa.normalize_synthesis_sections([source], [candidate])
                text = sa.render_final_summary(kind, 'Synthetic', [source], sections, {item: (1, None)})
                self.assertIn('that “The ICWA reviewer joined by Webex”', text)

    def test_characterwise_case_only_for_any_source_capitalization(self):
        for original, proposed in [('RECEIVED THE REPORT', 'received the report'),
                                   ('VIA WEBEX', 'via Webex'), ('ICWA JV-190', 'ICWA JV-190'),
                                   ('I AM HERE', 'I am here'), ('ÉTAT CIVIL', 'État civil'),
                                   ('The support remained unstable', 'the support remained unstable'),
                                   ('the ICWA and Webex review', 'The ICWA and Webex review'),
                                   ('Mixed Case', 'mixed case')]:
            self.assertEqual(display_quote(original, proposed), proposed)
        for original, proposed in [('NO ORDER', 'an order'), ('NO ORDER', 'no  order'),
                                   ('NO ORDER', 'no order.'), ('NO ORDER', None),
                                   ('NO ORDER', ['no order']), ('NO ORDER', {'text': 'no order'}),
                                   ('SS', 'ß'), ('ß', 'SS'), ('İ', 'i'), ('A-B', 'a–b'),
                                   ('"YES"', '“yes”'), ('not safe', 'safe')]:
            self.assertEqual(display_quote(original, proposed), original)

    def test_source_preserved_and_hearing_normalization_has_no_announcement(self):
        source = row()
        before = copy.deepcopy(source)
        sections, flags = sa.normalize_synthesis_sections([source], [entry({QUOTE: 'JCO to the mother'})])
        text = sa.render_final_summary('hearings', 'Synthetic', [source], sections, {ITEM: (1, None)})
        self.assertIn('“JCO to the mother”', text)
        self.assertNotIn(NORMALIZATION_NOTICE, text)
        self.assertEqual(source, before)
        self.assertNotIn('quote_capitalization_rejected:' + ITEM, flags)
        self.assertTrue(sa.find_quote_span_relaxed('JCO to the mother', 'THE COURT ORDERED JCO TO THE MOTHER TODAY.'))

    def test_report_normalization_preserves_source_without_announcement(self):
        source = copy.deepcopy(row())
        source.update(item_id='report:0001', kind='reports')
        quote = 'report:0001/court_orders_and_reasons/1'
        source['categories'][0]['digest']['evidence'][0]['quote_id'] = quote
        before = copy.deepcopy(source)
        sections, _ = sa.normalize_synthesis_sections([source], [{
            'item_id': source['item_id'], 'paragraphs': ['The court ordered {{quote:' + quote + '}}.'],
            'quote_capitalizations': {quote: 'JCO to the mother'}}])
        text = sa.render_final_summary('reports', 'Synthetic', [source], sections, {source['item_id']: (1, None)})
        self.assertIn('“JCO to the mother”', text)
        self.assertNotIn(NORMALIZATION_NOTICE, text)
        self.assertEqual(source, before)

    def test_rejected_and_unknown_proposals_fall_back_without_prose_loss(self):
        for proposal in ({QUOTE: 'different words'}, {QUOTE: 42}, {'other/id': 'changed'}, [], None):
            with self.subTest(proposal=proposal):
                sections, flags = sa.normalize_synthesis_sections([row()], [entry(proposal)])
                text = sa.render_final_summary('hearings', '', [row()], sections, {ITEM: (1, None)})
                self.assertIn('The court ordered “JCO TO THE MOTHER”.', text)
                self.assertNotIn(NORMALIZATION_NOTICE, text)
                self.assertIn('quote_capitalization_rejected:' + ITEM, flags)

    def test_unused_or_replaced_proposals_do_not_add_notice(self):
        for entries in ([entry({QUOTE: 'JCO to the mother'}, 'Paraphrase only.')],
                        [entry({QUOTE: 'JCO to the mother'}), entry({})],
                        [entry({QUOTE: 'JCO to the mother'}, '{{quote:unknown}}')]):
            sections, _ = sa.normalize_synthesis_sections([row()], entries)
            text = sa.render_final_summary('hearings', '', [row()], sections, {ITEM: (1, None)})
            self.assertNotIn(NORMALIZATION_NOTICE, text)
        sections, _ = sa.normalize_synthesis_sections([row()], [entry({QUOTE: 'JCO to the mother'})])
        self.assertNotIn(NORMALIZATION_NOTICE, sa.render_final_summary('hearings', '', [row()], sections, {}))

    def test_renderer_revalidates_direct_candidates_and_keeps_legacy_callers(self):
        self.assertEqual(sa.render_quote_text(row(), QUOTE), '“JCO TO THE MOTHER”')
        self.assertEqual(sa.render_quote_text(row(), QUOTE, 'altered words'), '“JCO TO THE MOTHER”')
        sections = [sa.SynthesisSectionCandidate(ITEM, entry({})['paragraphs'])]
        self.assertNotIn(NORMALIZATION_NOTICE, sa.render_final_summary('hearings', '', [row()], sections, {ITEM: (1, None)}))

    def test_both_profiles_and_legacy_get_code_owned_rule(self):
        from test_profile_generation import bundled
        from recordprep.summary_profiles import compile_summary, HEARING_QUOTE_CASE_GUIDANCE, REPORT_QUOTE_CASE_GUIDANCE
        for profile in (bundled('general'), bundled('california_dependency')):
            for kind in ('hearings', 'reports'):
                rule = HEARING_QUOTE_CASE_GUIDANCE if kind == 'hearings' else REPORT_QUOTE_CASE_GUIDANCE
                self.assertIn(rule, compile_summary(profile, kind, 'synthesize').prompt)
                self.assertNotIn(rule, compile_summary(profile, kind, 'extract').prompt)
        self.assertIn(HEARING_QUOTE_CASE_GUIDANCE, sa.effective_synthesis_config(PROJECT / '.pi', 'hearings')['guidance'])

    def test_synthesis_wrapper_changes_do_not_stale_extraction(self):
        from test_profile_generation import bundled
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / '.pi'
            shutil.copytree(PROJECT / '.pi', project)
            for profile in (None, bundled('general')):
                extraction = sa.effective_extraction_config(project, 'hearings', profile=profile)
                synthesis = sa.effective_synthesis_config(project, 'hearings', profile=profile)
                wrapper = project / 'extensions/recordprep-summary-synthesis-tools.ts'
                wrapper.write_text(wrapper.read_text() + '\n// Changed synthesis schema\n')
                self.assertEqual(extraction, sa.effective_extraction_config(project, 'hearings', profile=profile))
                self.assertNotEqual(synthesis, sa.effective_synthesis_config(project, 'hearings', profile=profile))

    def test_pdf_edition_keeps_display_phrase_for_search_without_hearing_notice(self):
        sections, _ = sa.normalize_synthesis_sections([row()], [entry({QUOTE: 'JCO to the mother'})])
        text = sa.render_final_summary('hearings', '', [row()], sections, {ITEM: (1, None)})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'summaries/synthetic.txt'
            source.parent.mkdir(); source.write_text(text)
            edition = build_summary_edition('hearings', source, root)
            self.assertNotIn(NORMALIZATION_NOTICE, '\n'.join(p.text for p in edition.pages))
            self.assertEqual([q.phrase for p in edition.pages for q in p.quotes], ['JCO to the mother'])

    def test_real_offline_sdk_accepts_schema_and_preserves_display_map(self):
        sdk = Path(os.environ.get('PI_METRICS_TEST_SDK', '/nonexistent'))
        fixture = PROJECT.parent / 'PiRunMetrics/tests/app_sdk_fixture.mjs'
        node = shutil.which('node')
        if not node or not (sdk / 'dist/index.js').is_file() or not fixture.is_file():
            self.skipTest('Installed offline SDK fixture required')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate = base / 'candidate.json'
            dataset = base / 'dataset.json'
            dataset_row = row('The ICWA reviewer joined by Webex')
            second_quote = ITEM + '/court_orders_and_reasons/2'
            dataset_row['categories'][0]['digest']['evidence'].append({
                'quote_id': second_quote, 'text': 'I agree', 'file_page': 1, 'verified': True})
            dataset.write_text(json.dumps({'artifact': 'recordprep-summary-digest-dataset', 'kind': 'hearings',
                'total_rows': 1, 'rows': [dataset_row],
                'documents': ['Synthetic digest.'], 'candidate_path': str(candidate)}))
            frames = []
            for i, (name, args) in enumerate([
                ('recordprep_get_facts', {'ordinal': 1}),
                ('recordprep_submit_summary_section', {'item_id': ITEM, 'paragraphs': ['Paraphrase only.']}),
                ('recordprep_submit_summary_section', {'item_id': ITEM, 'paragraphs': [
                    '{{quote:' + QUOTE + '}} and {{quote:' + QUOTE + '}}.']}),
                ('recordprep_submit_summary_section', entry({QUOTE: 'The ICWA reviewer joined by Webex'},
                    '{{quote:' + QUOTE + '}}. {{quote:' + second_quote + '}}.')),
                ('recordprep_submit_summary_section', entry({QUOTE: ''})),
                ('recordprep_submit_summary_section', entry({QUOTE: 'The ICWA reviewer joined by Webex'})),
                ('recordprep_submit_summary_section', entry({QUOTE: 'the ICWA reviewer joined by Webex'},
                    'The clerk reported that {{quote:' + QUOTE + '}}.')),
                ('recordprep_submit_summary_section', {
                    **entry({QUOTE: 'the ICWA reviewer joined'},
                            'The clerk reported that {{quote:' + QUOTE + '}}.'),
                    'quote_selections': {QUOTE: 'The ICWA reviewer joined'}}),
                ('recordprep_finish_summary', {})]):
                frames.append({'stopReason': 'toolUse', 'content': [{'type': 'toolCall', 'id': str(i), 'name': name, 'arguments': args}]})
            plan = base / 'plan.json'; plan.write_text(json.dumps({'frames': frames, 'followup': False}))
            capture = base / 'capture.json'
            system = base / 'system.txt'; system.write_text('Synthetic offline quote acceptance.')
            env = os.environ | {'PI_METRICS_TEST_SDK': str(sdk), 'PI_METRICS_TEST_PLAN': str(plan),
                'PI_METRICS_TEST_CAPTURE': str(capture), 'RECORDPREP_SUMMARY_MODE': 'synthesize',
                'RECORDPREP_SUMMARY_DATASET': str(dataset), 'PI_RUN_METRICS_ENABLED': '0'}
            for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TMPDIR'):
                p = base / key.lower(); p.mkdir(mode=0o700); env[key] = str(p)
            result = subprocess.run([node, str(fixture), '--no-extensions', '--no-session',
                '--extension', str(PROJECT / '.pi/extensions/recordprep-summary-synthesis-tools.ts'),
                '--tools', 'recordprep_get_facts,recordprep_submit_summary_section,recordprep_finish_summary',
                '--system-prompt', str(system), 'Synthetic test.'], cwd=base, env=env,
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            captured = json.loads(capture.read_text())
            results = [m for m in captured['messages'] if m.get('role') == 'toolResult']
            self.assertEqual(len(results), 9)
            self.assertFalse(any(m.get('isError') for m in results))
            feedback = [json.dumps(m.get('content', [])) for m in results]
            self.assertIn('Capitalization decisions missing for 1 used quote(s)', feedback[2])
            self.assertIn('complete original text', feedback[2])
            self.assertIn('section remains recorded', feedback[2])
            self.assertIn('Capitalization decisions missing for 1 used quote(s)', feedback[3])
            self.assertIn(second_quote, feedback[3])
            self.assertIn('Capitalization decisions missing for 1 used quote(s)', feedback[4])
            for index in (0, 1, 5, 6, 7, 8):
                self.assertNotIn('Capitalization decisions missing', feedback[index])
            payload = json.loads(candidate.read_text())
            self.assertEqual(payload['sections'][0]['quote_capitalizations'], {QUOTE: 'the ICWA reviewer joined'})
            self.assertEqual(payload['sections'][0]['quote_selections'], {QUOTE: 'The ICWA reviewer joined'})
            source = row('The ICWA reviewer joined by Webex')
            sections, _ = sa.normalize_synthesis_sections([source], payload['sections'])
            text = sa.render_final_summary('hearings', '', [source], sections, {ITEM: (1, None)})
            self.assertIn('“the ICWA reviewer joined”', text)
            self.assertNotIn('by Webex', text)
