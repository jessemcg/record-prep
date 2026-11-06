"""Only reviewed source-width wraps change; literal guidance is never reflowed."""
import copy
import json
import unittest

from recordprep.classifier_prompts import (
    DATE_RULES, INSTRUCTIONS, REPORT_FIRST_CLUES, classifier_document,
)
from recordprep.document_naming import naming_document
from recordprep.prompt_document import PromptDocument, PromptSection
from recordprep.structured_guidance import effective_resource
from test_structured_classification import ROOT, bundle


class PromptLinebreakTests(unittest.TestCase):
    def test_fixed_classifier_prose_and_deliberate_returns(self):
        self.assertEqual(INSTRUCTIONS, 'Examine the attached page image. Use only visible evidence, preserve uncertainty, and do not invent information.\nReturn only the specified JSON object, without commentary or extra keys.')
        self.assertNotIn('\n', DATE_RULES)
        self.assertEqual(REPORT_FIRST_CLUES.count('\n'), 1)
        self.assertIn('sections.\nA first-page indicator', REPORT_FIRST_CLUES)
        ct = classifier_document('ct').render()
        self.assertIn('\n\nCategory Descriptions\n\nCT_cover\n', ct)
        self.assertIn('record.\nCompare all category descriptions', ct)
        self.assertIn('.\nExample response: {', ct)
        self.assertIn('correspondence, exhibits, raw results', ct)
        rt = classifier_document('rt').render()
        self.assertIn('\n\nRT_body\n', rt)
        self.assertIn('uninterrupted speech', rt)

    def test_naming_wraps_removed_without_collapsing_sections_or_json(self):
        from test_dependency_report_naming import title_catalog_bundle
        naming = title_catalog_bundle().resource('naming')
        for kind in ('report', 'form'):
            with self.subTest(kind=kind):
                document = naming_document(naming, kind)
                mechanics = document.sections[1].text
                self.assertEqual(mechanics.count('\n'), 2 if kind == 'report' else 1)
                self.assertIn('do not guess.\nTreat page text as evidence', document.render())
                self.assertIn('\n\n\n' + mechanics, document.render())
                catalog = document.sections[2].text
                self.assertIn('[\n  {\n', catalog)
                self.assertEqual(json.loads(catalog)[0]['name'], naming[kind + 's'][0]['name'])
        self.assertIn('Consider conflicting heading and footer evidence together', naming_document(naming, 'report').render())
        self.assertIn('both that code and the matching heading must be visible', naming_document(naming, 'form').render())

    def test_exact_public_adapter_preserves_frozen_input_and_unknown_prose(self):
        path = ROOT / 'recordprep/resources/profile_baselines/dependency-1.8.0/classification-v3.json'
        frozen = path.read_bytes()
        old = json.loads(frozen)
        before = copy.deepcopy(old)
        current = effective_resource(old, 'classification_tasks')
        self.assertEqual(effective_resource(old, 'classification_tasks'), current)
        self.assertEqual(old, before)
        self.assertEqual(path.read_bytes(), frozen)
        # Any custom edit disables full-resource recognition, even elsewhere.
        old['page_types']['rt']['RT_other'] += ' Custom.'
        self.assertIs(effective_resource(old, 'classification_tasks'), old)
        self.assertIn('fields,\na report/hearing', old['first_pages']['first_report'])
        self.assertIn('exhibits,\n    photos', old['page_types']['ct']['CT_other'])
        # The reviewed edits change whitespace only, never wording.
        for side, descriptions in before['page_types'].items():
            for key, text in descriptions.items():
                self.assertEqual(text.split(), current['page_types'][side][key].split())
        for key, text in before['first_pages'].items():
            self.assertEqual(text.split(), current['first_pages'][key].split())

    def test_custom_hard_returns_blank_lines_and_literals_survive_composition(self):
        literal = 'Literal α {"x": 1} {{quote:source}}\ncontinued by choice\n\n- First\n- Second\n'
        from recordprep.recognition_contract import load_recognition
        from dataclasses import replace
        frozen = load_recognition()
        starts = tuple((key, literal if key == 'first_report' else value) for key, value in frozen.first_pages)
        changed = replace(frozen, first_pages=starts)
        self.assertIn(literal, classifier_document('first_report', changed).render())
        self.assertNotIn(literal, classifier_document('first_report').render())
        naming = bundle().resource('naming')
        naming['reports'][0]['guidance'] = literal
        catalog = json.loads(naming_document(naming, 'report').sections[2].text)
        self.assertEqual(catalog[0]['description'], literal)
        document = PromptDocument((PromptSection('literal', literal), PromptSection('next', 'next')))
        self.assertEqual(document.render(), literal + '\n\nnext')
