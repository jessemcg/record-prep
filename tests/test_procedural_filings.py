"""Function-first classification contracts; synthetic expectations, not model accuracy."""
import json
from pathlib import Path
import unittest

from recordprep import practice_profiles as api
from recordprep.classification_profiles import classifier_prompt, component
from recordprep.document_naming import compile_motion_naming
from recordprep.motion_guidance import ORGANIZATION_GUIDANCE
from recordprep.motion_pages import build_motion_boundaries
from recordprep.motion_groups import inventory_from_boundaries, normalize_candidate
from recordprep.recognition_contract import load_recognition, RecognitionContract
from recordprep.profile_editor_ui import CLASSIFICATION_PAGES, CLASSIFICATION_EXPLANATION

ROOT = Path(__file__).resolve().parents[1]


class ProceduralFilingTests(unittest.TestCase):
    def test_shared_rules_are_function_first_and_profile_independent(self):
        profiles = [None] + [api.bundled_profile_for_identity(api.APPLICATION, identity)
                            for identity in ('california-juvenile-dependency', 'california-criminal-law')]
        for task in ('ct', 'first_motion', 'first_form'):
            prompts = [classifier_prompt(profile, task)[0] for profile in profiles]
            self.assertEqual(len(set(prompts)), 1)
            for specific in ('JV-180', 'section 388', 'de facto parent'):
                self.assertNotIn(specific, prompts[0])
        ct = dict(load_recognition().descriptions('ct'))
        self.assertIn('Standardized forms, custom-written and handwritten papers are equally eligible', ct['CT_motion'])
        self.assertIn('status, recognition or participation rights', ct['CT_motion'])
        self.assertIn('Initiating pleadings commencing a proceeding', ct['CT_motion'])
        self.assertIn('Administrative requests that only update records', ct['CT_form'])
        self.assertIn('Procedural filings (legacy label CT_form)', ct['CT_form'])
        self.assertNotIn('court request forms remain CT_form', ct['CT_motion'])
        self.assertIn('Standardized request forms use this same check', classifier_prompt(None, 'first_motion')[0])
        naming = compile_motion_naming(None).prompt
        self.assertIn('Standardized forms, custom-written and handwritten requests are equally eligible', naming)
        self.assertIn('Standardized substantive requests classified as motion papers are eligible lead requests', ORGANIZATION_GUIDANCE)
        self.assertIn(('form-naming', 'Procedural Filing Names', 'Names'), CLASSIFICATION_PAGES)
        self.assertIn('procedural filings', CLASSIFICATION_EXPLANATION)

    def test_old_contract_is_preserved_and_explicit_stage_identity_changes(self):
        old = json.loads((ROOT/'recordprep/resources/classification/recognition-v3.json').read_text())
        historical = RecognitionContract(old['contract_id'],
            tuple((side, tuple(entries.items())) for side, entries in old['page_types'].items()),
            tuple(old['first_pages'].items()))
        self.assertIn('Qualifying standardized court request forms', dict(historical.descriptions('ct'))['CT_motion'])
        for stage in ('basic', 'advanced'):
            self.assertNotEqual(component(None, stage, contract=historical), component(None, stage))
        self.assertEqual(component(None, 'dates', contract=historical), component(None, 'dates'))

    def test_standardized_requests_and_support_reach_one_group_with_exact_pages(self):
        # Authored classifications/model proposals exercise downstream plumbing, not AI judgment.
        for title in ('Request to Change Court Order (JV-180; section 388)',
                      'De Facto Parent Request', 'Application to Modify an Injunction'):
            with self.subTest(title=title):
                rows = [
                    {'file_name': '0001.txt', 'page_type': 'CT_motion_first_page',
                     'motion_first_page': 'yes', 'name': title, 'naming_rule_id': 'motion-papers'},
                    {'file_name': '0002.txt', 'page_type': 'CT_motion', 'motion_first_page': 'no'},
                    {'file_name': '0003.txt', 'page_type': 'CT_motion_first_page',
                     'motion_first_page': 'yes', 'name': 'Supporting Declaration', 'naming_rule_id': 'motion-papers'},
                    {'file_name': '0004.txt', 'page_type': 'CT_form_first_page', 'name': 'Notification of Address'},
                    {'file_name': '0005.txt', 'page_type': 'CT_minute_order_first_page'},
                    {'file_name': '0006.txt', 'page_type': 'CT_other'},
                ]
                inventory = inventory_from_boundaries(build_motion_boundaries(rows, -1))
                self.assertEqual([(p['start_page'], p['end_page']) for p in inventory], [(1, 2), (3, 3)])
                self.assertEqual(inventory[0]['source_title'], title)
                proposal = {'lead_paper_id': 'motion:0001',
                    'member_paper_ids': ['motion:0001', 'motion:0003'],
                    'filing_role': 'motion/application', 'display_title': title,
                    'evidence': 'Synthetic request expressly references the attached supporting declaration.'}
                saved = normalize_candidate({'groups': [proposal], 'coverage_status': 'complete'}, inventory, 'a' * 64)
                self.assertEqual(len(saved['groups']), 1)
                self.assertEqual(saved['groups'][0]['member_paper_ids'], ['motion:0001', 'motion:0003'])
                self.assertEqual(saved['inventory'], inventory)

    def test_dependency_catalog_excludes_requests_but_retains_initiating_petition(self):
        profile = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        forms = profile.resource('naming')['forms']
        self.assertNotIn('JV-180', str(forms))
        self.assertNotIn('De Facto Parent', str(forms))
        self.assertIn('JV-100', str(forms))
        self.assertEqual(len(forms), 5)
