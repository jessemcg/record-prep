"""Display-only end-trimming: synthetic evidence, rendering and search integration."""
import copy
from pathlib import Path
import tempfile
import unittest

from recordprep import summary_agents as sa
from recordprep.quote_display import display_quote, valid_quote_selection
from recordprep.summary_editions import build_summary_edition
from test_quote_display import row


class QuoteSelectionTests(unittest.TestCase):
    def test_exact_whole_word_contiguous_selection(self):
        original = 'The eastern support remained unstable after the repair'
        for selection in (original, 'eastern support remained unstable',
                          'remained unstable after the repair', 'The eastern support remained unstable'):
            with self.subTest(selection=selection):
                self.assertTrue(valid_quote_selection(original, selection))
        for selection in ('', ' ', None, [], {}, 3, 'eastern support unstable',
                          'Eastern support remained unstable', 'support … unstable',
                          'he eastern support', 'The eastern supp', ' unstable '):
            with self.subTest(selection=selection):
                self.assertFalse(valid_quote_selection(original, selection))
        self.assertFalse(valid_quote_selection('not-established yet', 'established yet'))
        self.assertFalse(valid_quote_selection("didn't agree", 't agree'))
        self.assertFalse(valid_quote_selection('cafe\u0301 reopened', 'cafe'))
        self.assertFalse(valid_quote_selection('yes ...', '...'))
        self.assertTrue(valid_quote_selection('theme then the end', 'the'))

    def test_validation_is_literal_not_a_meaning_check(self):
        self.assertTrue(valid_quote_selection('not safe to reopen', 'safe to reopen'))
        # Such a reversal is forbidden by instructions, not claimed to be detected
        # by substring validation. Never advertise this check as semantic proof.

    def test_case_adjustment_applies_only_to_valid_selected_span(self):
        self.assertEqual(display_quote('The ICWA reviewer joined by Webex',
                                       'the ICWA reviewer joined', 'The ICWA reviewer joined'),
                         'the ICWA reviewer joined')
        self.assertEqual(display_quote('The ICWA reviewer joined', 'the reviewer joined',
                                       'The reviewer joined'), 'The ICWA reviewer joined')
        self.assertEqual(display_quote('The ICWA reviewer joined by Webex', 'different words',
                                       'The ICWA reviewer joined'), 'The ICWA reviewer joined')

    def test_all_kinds_render_selected_phrase_to_txt_pdf_map_and_search(self):
        for kind, prefix in (('hearings', 'hearing'), ('reports', 'report'), ('motions', 'motion')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                source = row('The eastern support remained unstable after the repair')
                item = prefix + ':0001'; quote = item + '/court_orders_and_reasons/1'
                source.update(kind=kind, item_id=item)
                source['categories'][0]['digest']['evidence'][0].update(
                    quote_id=quote, source_sha256='f' * 64, source_start=20,
                    source_end=20 + len(source['categories'][0]['digest']['evidence'][0]['text']))
                before = copy.deepcopy(source)
                selected = 'eastern support remained unstable'
                payload = {'item_id': item, 'paragraphs': ['The engineer found that the {{quote:' + quote + '}}.'],
                           'quote_selections': {quote: selected}, 'quote_capitalizations': {quote: selected}}
                sections, flags = sa.normalize_synthesis_sections([source], [payload])
                self.assertFalse(any(f.startswith('quote_selection_rejected') for f in flags))
                self.assertEqual(sections[0].quote_selections, {quote: selected})
                text = sa.render_final_summary(kind, 'Synthetic', [source], sections, {item: (1, None)})
                self.assertIn('the “eastern support remained unstable”', text)
                self.assertNotIn('after the repair', text)
                self.assertEqual(source, before)
                self.assertTrue(sa.find_quote_span_relaxed(selected.upper(),
                    source['categories'][0]['digest']['evidence'][0]['text']))
                root = Path(temporary); path = root / 'summaries/synthetic.txt'
                path.parent.mkdir(); path.write_text(text)
                edition = build_summary_edition(kind, path, root)
                self.assertEqual([q.phrase for page in edition.pages for q in page.quotes], [selected])
                self.assertEqual(path.read_text(), text)

    def test_rejected_unused_unknown_and_malformed_selections_keep_original(self):
        source = row('The eastern support remained unstable')
        quote = source['categories'][0]['digest']['evidence'][0]['quote_id']
        for selection in ({quote: 'The support unstable'}, {quote: ''}, {quote: 42},
                          {'other/id': 'support'}, [], None):
            with self.subTest(selection=selection):
                sections, flags = sa.normalize_synthesis_sections([source], [{
                    'item_id': source['item_id'], 'paragraphs': ['{{quote:' + quote + '}}.'],
                    'quote_selections': selection}])
                self.assertIn('quote_selection_rejected:' + source['item_id'], flags)
                self.assertEqual(sections[0].quote_selections, {})
                self.assertIn('“The eastern support remained unstable”',
                    sa.render_final_summary('hearings', '', [source], sections, {source['item_id']: (1, None)}))
        sections, flags = sa.normalize_synthesis_sections([source], [{
            'item_id': source['item_id'], 'paragraphs': ['Paraphrase.'],
            'quote_selections': {quote: 'support'}}])
        self.assertEqual(sections[0].quote_selections, {})
        self.assertIn('quote_selection_rejected:' + source['item_id'], flags)

    def test_last_submission_wins_and_old_mapless_candidates_remain_valid(self):
        source = row('The support remained unstable')
        item = source['item_id']; quote = source['categories'][0]['digest']['evidence'][0]['quote_id']
        first = {'item_id': item, 'paragraphs': ['{{quote:' + quote + '}}.'],
                 'quote_selections': {quote: 'support remained unstable'}}
        second = {'item_id': item, 'paragraphs': first['paragraphs']}
        sections, _ = sa.normalize_synthesis_sections([source], [first, second])
        self.assertEqual(sections[0].quote_selections, {})
        self.assertIn('“The support remained unstable”',
                      sa.render_final_summary('hearings', '', [source], sections, {item: (1, None)}))
        self.assertEqual(sa.render_quote_text(source, quote, 'invented', 'not in evidence'),
                         '“The support remained unstable”')
        direct = sa.SynthesisSectionCandidate(item, first['paragraphs'],
            quote_capitalizations={quote: 'Support remained unstable'},
            quote_selections={quote: 'support remained unstable'})
        self.assertIn('“Support remained unstable”',
            sa.render_final_summary('hearings', '', [source], [direct], {item: (1, None)}))
        direct.quote_selections[quote] = 'fabricated selection'
        self.assertIn('“The support remained unstable”',
            sa.render_final_summary('hearings', '', [source], [direct], {item: (1, None)}))
        sections, _ = sa.normalize_synthesis_sections([source], [dict(first, paragraphs=['{{quote:unknown}}'])])
        self.assertEqual(sections[0].quote_selections, {})
