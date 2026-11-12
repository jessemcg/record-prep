"""Fictional expanded-sentence, display fidelity and delivery regressions.

These deterministic candidates demonstrate mechanics, not live writing quality.
"""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from recordprep import summary_agents as sa, summary_profiles as sp, motion_guidance as mg
from recordprep.prompt_inspection import inspect_prompt
from recordprep.quote_display import QUOTE_CASE_GUIDANCE, NORMALIZATION_NOTICE
from recordprep.synthesis_fidelity import QUOTATION_INTEGRATION_GUIDANCE
from recordprep.summary_editions import build_summary_edition, validate_edition_payload
from test_profile_generation import bundled
from test_motion_editorial import historical_custom_profile

ROOT = Path(__file__).resolve().parents[1]


def fixture(kind, original='The ICWA reviewer used Webex but did not approve access'):
    item = sa.SUMMARY_ITEM_PREFIXES[kind] + ':0001'
    topic = 'request' if kind == 'motions' else sa.SUMMARY_CATEGORY_IDS[kind][0]
    quote = item + '/' + topic + '/1'
    row = {'item_id': item, 'ordinal': 1, 'kind': kind, 'label': 'Fictional inspection',
           'start_page': 1, 'end_page': 2, 'input_sha256': 'a' * 64,
           'categories': [{'id': topic, 'digest': {'text': 'The reviewer did not approve access.',
               'evidence': [{'quote_id': quote, 'text': original, 'file_page': 1,
                             'source_start': 10, 'source_end': 10 + len(original), 'verified': True}]}}]}
    return row, quote


def submission(row, quote, display, paragraphs=None):
    return {'item_id': row['item_id'],
            'paragraphs': paragraphs or ['The engineer reported that {{quote:' + quote + '}}.'],
            'quote_capitalizations': {quote: display}}


class FluidQuotationTests(unittest.TestCase):
    def test_all_kinds_sentence_mixed_lower_and_upper_case_through_txt_pdf_and_map(self):
        spellings = [
            ('The ICWA reviewer used Webex but did not approve access',
             'the ICWA reviewer used Webex but did not approve access'),
            ('The ICWA Reviewer used Webex but did not approve access',
             'the ICWA reviewer used Webex but did not approve access'),
            ('THE ICWA REVIEWER USED WEBEX BUT DID NOT APPROVE ACCESS',
             'the ICWA reviewer used Webex but did not approve access'),
            ('the ICWA reviewer used Webex but did not approve access',
             'The ICWA reviewer used Webex but did not approve access')]
        for kind in sa.SUMMARY_KINDS:
            for original, display in spellings:
                with self.subTest(kind=kind, original=original), tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    row, quote = fixture(kind, original)
                    before = copy.deepcopy(row)
                    source = root / 'text_pages/0001.txt'
                    source.parent.mkdir()
                    source.write_text('Fictional ' + original + '.\n' + original + '.')
                    protected = (source.read_bytes(), source.stat().st_mtime_ns)
                    sections, flags = sa.normalize_synthesis_sections([row], [submission(row, quote, display)])
                    self.assertFalse(any(f.startswith('quote_capitalization_rejected') for f in flags))
                    text = sa.render_final_summary(kind, 'Fictional', [row], sections, {row['item_id']: (1, None)})
                    self.assertIn('“' + display + '”', text)
                    self.assertNotIn(NORMALIZATION_NOTICE, text)
                    self.assertEqual(row, before)
                    final = root / 'summaries' / (kind + '.txt')
                    final.parent.mkdir(); final.write_text(text)
                    edition = build_summary_edition(kind, final, root)
                    self.assertEqual(validate_edition_payload(edition.page_map, kind=kind, root_dir=root,
                                     source_text=text, pdf_bytes=edition.pdf_bytes), [])
                    self.assertEqual([q.phrase for p in edition.pages for q in p.quotes], [display])
                    self.assertEqual(final.read_text(), text)
                    self.assertEqual(protected, (source.read_bytes(), source.stat().st_mtime_ns))
                    # Source matcher itself is unchanged; display variants preserve positions.
                    self.assertEqual(sa.find_quote_span_relaxed(display, source.read_text()),
                                     sa.find_quote_span_relaxed(original, source.read_text()))

    def test_all_kinds_reject_non_case_changes_without_losing_otherwise_usable_prose(self):
        original = 'The reviewer did not approve access'
        for kind in sa.SUMMARY_KINDS:
            for proposed in ('the reviewer did approve access', 'the reviewer did not approve entry',
                             'the  reviewer did not approve access', original + '.',
                             'The reviewer did not approve accesſ', None, 7, [], {}):
                with self.subTest(kind=kind, proposed=proposed):
                    row, quote = fixture(kind, original)
                    sections, flags = sa.normalize_synthesis_sections([row], [submission(row, quote, proposed)])
                    self.assertIn('quote_capitalization_rejected:' + row['item_id'], flags)
                    text = sa.render_final_summary(kind, '', [row], sections, {row['item_id']: (1, None)})
                    self.assertIn('The engineer reported that “' + original + '”.', text)
                    self.assertEqual(sa.render_quote_text(row, quote, proposed), '“' + original + '”')

    def test_surviving_section_and_used_exact_ids_control_case_map(self):
        for kind in sa.SUMMARY_KINDS:
            row, quote = fixture(kind, 'The support remained unstable after repair')
            valid = submission(row, quote, 'the support remained unstable after repair')
            cases = [([valid, {'item_id': row['item_id'], 'paragraphs': ['Replacement paraphrase.']}], {}),
                     ([submission(row, quote, valid['quote_capitalizations'][quote], ['Paraphrase only.'])], {}),
                     ([submission(row, quote, valid['quote_capitalizations'][quote], ['{{quote:unknown}}'])], {}),
                     ([dict(valid, quote_capitalizations={'unknown': 'anything'})], {}),
                     ([dict(valid, quote_capitalizations=[])], {})]
            for candidates, expected in cases:
                sections, _ = sa.normalize_synthesis_sections([row], candidates)
                self.assertEqual(sections[0].quote_capitalizations, expected)
            sections, _ = sa.normalize_synthesis_sections([row], [valid])
            self.assertEqual(sections[0].quote_capitalizations, valid['quote_capitalizations'])
            self.assertEqual(sa.render_quote_text(row, quote, valid['quote_capitalizations'][quote]),
                             '“the support remained unstable after repair”')
            direct = sa.SynthesisSectionCandidate(row['item_id'], valid['paragraphs'],
                       quote_capitalizations={quote: 'Changed wording'})
            text = sa.render_final_summary(kind, '', [row], [direct], {row['item_id']: (1, None)})
            self.assertIn('“The support remained unstable after repair”', text)

    def test_rule_reaches_inspection_and_effective_composition_for_every_assignment(self):
        for profile in (None, bundled('general'), bundled('california_dependency'),
                        bundled('california_criminal'), historical_custom_profile()):
            for kind in sa.SUMMARY_KINDS:
                config = sa.effective_synthesis_config(ROOT / '.pi', kind, profile=profile)
                self.assertIn(QUOTE_CASE_GUIDANCE, config['guidance'])
                self.assertEqual(config['guidance'].count(QUOTATION_INTEGRATION_GUIDANCE), 1)
                extraction = sa.effective_extraction_config(ROOT / '.pi', kind, profile=profile)
                self.assertNotIn(QUOTE_CASE_GUIDANCE, extraction.guidance)
                self.assertNotIn(QUOTATION_INTEGRATION_GUIDANCE, extraction.guidance)
                view = inspect_prompt({}, kind + '-synthesize', ROOT / '.pi', template=False, snapshot=profile)
                self.assertEqual(view.issues, ())
                text = view.display_text()
                self.assertIn(QUOTE_CASE_GUIDANCE, text)
                self.assertIn(QUOTATION_INTEGRATION_GUIDANCE, text)
                self.assertIn('sentence-case, mixed-case or lowercase quotes', text)
                self.assertNotIn('For all-caps quotes, optionally', text)
                if kind != 'hearings':
                    skill = (ROOT / '.pi/skills' / ('recordprep-synthesize-' + kind) / 'SKILL.md').read_text()
                    self.assertIn(skill.split('---', 2)[2].strip(), text)
                    normalized = ' '.join(skill.split())
                    for phrase in ('Let the quotation carry the proposition', 'first-person',
                                   'entire sentence' if kind == 'motions' else 'entire resulting sentence'):
                        self.assertIn(phrase, normalized)

    def test_hearing_editorial_and_shared_motion_extraction_method_are_protected(self):
        # Baseline 23948d9. Intentional changes here require a separate editorial scope.
        self.assertEqual(hashlib.sha256(sp.HEARING_READABILITY.encode()).hexdigest(),
                         '3d93853d55044da6caf8494477d32cce61992bb6047ba821375400839d329811')
        self.assertEqual(hashlib.sha256(mg.EDITORIAL.encode()).hexdigest(), '5f03d3766f25c87d1079cf4144039eef376392b16105429d57604b4bdd828b92')
        # Only the requested verified-only anchor selection rule changes the skill.
        self.assertEqual(hashlib.sha256((ROOT / '.pi/skills/recordprep-synthesize-hearings/SKILL.md').read_bytes()).hexdigest(),
                         '631398ad339c9984e31617a84774945ea2d391aaca98b39e7dce604bd060024a')

    def test_followup_fidelity_examples_preserve_condition_and_attribution(self):
        text = ' '.join(QUOTATION_INTEGRATION_GUIDANCE.split())
        for phrase in ('Choose the material point before choosing an anchor',
                       'A clause with its own subject and finite verb is not a noun phrase',
                       'same rationale across adjacent paragraphs',
                       'condition and the act it qualifies',
                       "not-established into disproved", "opponent's assertion",
                       'employment/ownership/allegiance', 'unsupported pronoun',
                       'procedural metadata is not judicial speech',
                       'Supporting declarant Sal Reed', 'not a separate review pass'):
            self.assertIn(phrase, text)
        row, quote = fixture('reports', 'only after the ventilation system has been repaired')
        paragraphs = ['The engineer recommended reopening {{quote:' + quote + '}}.',
                      'The archive reviewer attended remotely but did not assess the damaged supports.']
        sections, _ = sa.normalize_synthesis_sections([row], [{
            'item_id': row['item_id'], 'paragraphs': paragraphs}])
        final = sa.render_final_summary('reports', '', [row], sections, {row['item_id']: (1, None)})
        self.assertIn('The engineer recommended reopening “only after the ventilation system has been repaired”.', final)
        self.assertIn(paragraphs[1], final)
        # Demonstrates the examples' grammatical rendering, not a semantic model gate.

    def test_fictional_report_sentences_expand_with_no_doubled_subject_or_modal(self):
        examples = [('only after the damaged supports were repaired', 'only after the damaged supports were repaired',
                     'The engineer recommended reopening ', '.',
                     'The engineer recommended reopening “only after the damaged supports were repaired”.'),
                    ('The eastern support remained unstable after the repair', 'the eastern support remained unstable after the repair',
                     'The engineer reported that ', '.',
                     'The engineer reported that “the eastern support remained unstable after the repair”.'),
                    ('I cannot certify the structure as safe', 'I cannot certify the structure as safe',
                     '', ', the engineer explained.',
                     '“I cannot certify the structure as safe”, the engineer explained.')]
        for original, display, prefix, suffix, expected in examples:
            row, quote = fixture('reports', original)
            sections, _ = sa.normalize_synthesis_sections([row], [submission(row, quote, display,
                [prefix + '{{quote:' + quote + '}}' + suffix])])
            text = sa.render_final_summary('reports', '', [row], sections, {row['item_id']: (1, None)})
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()
