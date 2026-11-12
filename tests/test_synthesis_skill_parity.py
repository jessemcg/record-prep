"""Keep all three narrative synthesis skills aligned without hiding their differences."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1] / '.pi/skills'
HEADINGS = ['Synthesis', 'Document-specific focus', 'Quotation integration',
            'Reading a digest block', 'Procedure']


def skill(kind):
    return (ROOT / f'recordprep-synthesize-{kind}/SKILL.md').read_text()


def sections(text):
    parts = re.split(r'^## (.+)\n', text, flags=re.M)
    return parts[0], dict(zip(parts[1::2], parts[2::2]))


class SynthesisSkillParityTests(unittest.TestCase):
    def test_matching_descriptions_headings_and_shared_sections(self):
        hearing_intro, hearings = sections(skill('hearings'))
        self.assertEqual(list(hearings), HEADINGS)
        for kind, singular in (('reports', 'report'), ('motions', 'motion packet')):
            intro, other = sections(skill(kind))
            expected = hearing_intro.replace('recordprep-synthesize-hearings', f'recordprep-synthesize-{kind}')
            expected = expected.replace('per hearing ', f'per {singular} ')
            expected = expected.replace('the Hearings Summary', f'the {kind.title()} Summary')
            self.assertEqual(expected, intro)
            self.assertEqual(list(other), HEADINGS)
            for heading in HEADINGS:
                with self.subTest(kind=kind, heading=heading):
                    if heading == 'Document-specific focus':
                        self.assertNotEqual(hearings[heading], other[heading])
                    else:
                        self.assertEqual(hearings[heading], other[heading])

    def test_shared_objective_quote_grammar_and_explicit_decisions(self):
        for kind in ('hearings', 'reports', 'motions'):
            text = ' '.join(skill(kind).split())
            with self.subTest(kind=kind):
                for phrase in ('Write a concise, cohesive narrative', "Respect the reader's time",
                               'A colon is acceptable when the lead-in is not redundant',
                               'A complete spoken statement needs brief supported attribution',
                               'actor and duty bearer', 'doubled subjects/verbs',
                               'For EVERY used quote id', 'unchanged as an explicit retain',
                               'You may trim whole words from either end',
                               'No internal deletions, splicing, ellipses or rewriting',
                               'Use direct quotations only from entries explicitly marked Verified',
                               'not in an extra model pass'):
                    self.assertIn(phrase, text)
                self.assertNotIn('`{{quote:', text)
                self.assertNotIn('Editorial method', text)
                self.assertNotIn('## Quotation capitalization', text)

    def test_only_document_focus_contains_kind_specific_priorities(self):
        _, hearings = sections(skill('hearings'))
        _, reports = sections(skill('reports'))
        hearing = ' '.join(hearings['Document-specific focus'].split())
        report = ' '.join(reports['Document-specific focus'].split())
        for phrase in ('substantive purpose or consequential result',
                       'conditional standard directions', 'counsel\'s account of a prior ruling',
                       'different grounds, relief and reservations'):
            self.assertIn(phrase, hearing)
        for phrase in ('main attributed conclusion', 'recommendation from an order',
                       'Do not relabel an old event as a new development',
                       'Never reuse an evidence quote already quoted in an earlier report'):
            self.assertIn(phrase, report)
        _, motions = sections(skill('motions'))
        motion = ' '.join(motions['Document-specific focus'].split())
        for phrase in ('asked the court to do or not do', 'Write the narrative in past tense',
                       'Preserve the tense inside direct quotations exactly',
                       'what the party objected to and why', 'do not re-segment',
                       'grouping does not imply agreement', 'without unnecessary legalese'):
            self.assertIn(phrase, motion)
