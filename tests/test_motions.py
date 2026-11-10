"""Fictional, offline motion mechanics; no private config/case/provider reads."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from recordprep.document_naming import compile_motion_naming
from recordprep.motion_pages import build_motion_boundaries, motion_detection_mode
from recordprep.profile_contract import validate_contents, json_bytes, ProfileError
from recordprep import summary_agents as sa
from recordprep.classification_review import selected_documents, _proposal_row
from recordprep.recognition_contract import load_recognition
from test_structured_classification import bundle


class MotionTests(unittest.TestCase):
    def test_current_bundle_and_strict_resources(self):
        profile = bundle()
        self.assertEqual(profile.manifest['schema_version'], 14)
        self.assertEqual(profile.ref.version, '1.19.0')
        self.assertNotIn('motion_naming', profile.manifest['resources'])
        contract = compile_motion_naming(profile)
        self.assertIn('1,024', contract.prompt)
        self.assertIn('filed', contract.prompt)
        self.assertIn('first_motion', dict(load_recognition().first_pages))
        for change in ({'schema_version': 2}, {'extra': 'not allowed'},
                       {'motions': [{'id': 'motion-papers', 'name': 'Paper', 'guidance': '', 'naming_mode': 'invented'}]}):
            files = dict(profile.files)
            from recordprep.motion_guidance import NEUTRAL_MOTION_NAMING
            manifest = profile.manifest
            manifest['schema_version'] = 12
            manifest['resources']['motion_naming'] = 'motion-naming.json'
            files['profile.json'] = json_bytes(manifest)
            files['motion-naming.json'] = json_bytes(NEUTRAL_MOTION_NAMING | change)
            with self.assertRaises(ProfileError):
                validate_contents(tuple(files.items()), 'recordprep')

    def test_actual_titles_date_basis_long_titles_and_independent_fields(self):
        contract = compile_motion_naming(bundle())
        for title in ('Motion for a Protective Order', 'Opposition to Motion for a Protective Order',
                      'Reply in Support of Motion', 'Supplemental Points and Authorities',
                      'Declaration of Fictional Engineer', 'Amended Application for Inspection'):
            result = contract.normalize({'name': title, 'rule_id': 'motion-papers',
                                         'date': 'November 1, 2026', 'date_basis': 'filed'})
            self.assertEqual((result.name, result.date, result.date_basis, result.rule_id),
                             (title, 'November 1, 2026', 'filed', 'motion-papers'))
        title = 'Long ' + 'x' * 1019
        self.assertEqual(len(title), 1024)
        self.assertEqual(contract.normalize({'name': title, 'rule_id': 'motion-papers', 'date': '', 'date_basis': 'unknown'}).name, title)
        self.assertEqual(contract.normalize({'name': title + 'x', 'rule_id': 'motion-papers'}).name, '')
        self.assertEqual(contract.normalize({'name': '', 'rule_id': 'motion-papers'}).name, 'Motion Paper')
        self.assertEqual(contract.normalize({'name': 'Title', 'rule_id': 'unknown', 'date': 'November 1, 2026', 'date_basis': 'document'}).date_basis, 'document')
        self.assertEqual(contract.normalize({'name': 'Title', 'rule_id': 'unknown'}).name, '')
        result = contract.normalize({'name': 'Title', 'rule_id': 'motion-papers', 'date': 'February 31, 2026', 'date_basis': 'filed'})
        self.assertEqual((result.name, result.date, result.date_basis), ('Title', '', 'unknown'))
        for basis in ('hearing', 'service', 'unknown', None):
            result = contract.normalize({'name': 'Title', 'rule_id': 'motion-papers',
                                         'date': 'November 1, 2026', 'date_basis': basis})
            self.assertEqual((result.name, result.date, result.date_basis), ('Title', '', 'unknown'))

    def test_explicit_starts_gaps_unnamed_and_same_titles(self):
        rows = [self.row(1, False), self.row(2, True, 'Motion'), self.row(3, False),
                self.row(4, True, ''), self.row(5, False), self.row(6, True, 'Motion'),
                self.row(8, False), self.row(9, True, 'Reply')]
        result = build_motion_boundaries(rows, 0)
        self.assertEqual([(r['motion_id'], r['start_page'], r['end_page']) for r in result],
                         [('motion:0002', '0002', '0003'), ('motion:0006', '0006', '0006'), ('motion:0009', '0009', '0009')])
        self.assertEqual(result[0]['motion_date_basis'], 'unknown')
        self.assertEqual(build_motion_boundaries([{'file_name': '0001.txt', 'page_type': 'CT_motion', 'name': 'Historical'}], 0), [])
        with self.assertRaises(ValueError):
            motion_detection_mode([{'page_type': 'CT_motion'}], required=True)
        self.assertEqual(build_motion_boundaries([{'file_name': '0001.txt', 'page_type': 'CT_report_first_page', 'name': 'Report'}], 0), [])

    @staticmethod
    def row(page, first, name=''):
        return {'file_name': f'{page:04d}.txt', 'page_type': 'CT_motion_first_page' if first else 'CT_motion',
                'motion_first_page': 'yes' if first else 'no', **({'name': name, 'naming_rule_id': 'motion-papers', 'date_basis': 'unknown'} if first else {})}

    def test_old_profile_uses_application_rules_without_writes(self):
        from test_practice_profiles import historical_snapshot
        profile = historical_snapshot(bundle(), version=13)
        files, manifest = dict(profile.files), profile.manifest
        for name in ('motions', 'motion_naming'):
            if name in manifest['resources']:
                files.pop(manifest['resources'].pop(name))
        manifest['schema_version'] = 10
        files['profile.json'] = json_bytes(manifest)
        old = validate_contents(tuple(files.items()), 'recordprep')
        original = old.files
        self.assertEqual(compile_motion_naming(old), compile_motion_naming(None))
        from recordprep.profile_workflows import ProfileEditor
        editor = ProfileEditor(old)
        self.assertEqual(editor.snapshot().files, original)
        editor.use_current_schema()
        self.assertEqual(editor.snapshot().manifest['schema_version'], 14)
        self.assertNotIn('motion_naming', editor.resources)
        self.assertEqual(old.files, original)
        self.assertTrue(compile_motion_naming(None).rules)

    def test_resume_skips_missing_preparation_but_not_a_checked_empty_selection(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from recordprep.ui.main_window import RecordPrepWindow
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            window = SimpleNamespace(selected_pdfs=[], show_toast=Mock(),
                _pipeline_steps=lambda: [('create_motion_summaries', None, None),
                                         ('create_case_overview', None, None)],
                _resume_step_complete=lambda step, root: False)
            self.assertEqual(RecordPrepWindow._resume_start_index(window, root, None), 1)
            self.assertIn('Skipped', window.show_toast.call_args.args[0])
            (root / 'artifacts').mkdir()
            (root / 'artifacts/motion_boundaries.json').write_text('[]')
            self.assertEqual(RecordPrepWindow._resume_start_index(window, root, None), 0)

    def test_selected_projection_and_cleanup(self):
        rows = {r['file_name']: r for r in [self.row(1, True, 'Motion'), self.row(2, False), self.row(3, True, 'Opposition')]}
        self.assertEqual([(d['kind'], d['start'], d['end']) for d in selected_documents(rows)],
                         [('motion', '0001.txt', '0002.txt'), ('motion', '0003.txt', '0003.txt')])
        original = copy.deepcopy(rows)
        proposal = {'file_name': '0001.txt', 'before': {'page_type': 'CT_motion_first_page'}, 'after': {'page_type': 'CT_other'}}
        row = _proposal_row(proposal, rows, {'motion': compile_motion_naming(bundle())})
        for field in ('name', 'naming_rule_id', 'motion_first_page', 'date', 'date_basis'):
            self.assertNotIn(field, row)
        self.assertEqual(rows, original)

    def test_complete_motion_payloads_ids_and_empty_vs_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'text_pages').mkdir()
            (root / 'artifacts').mkdir()
            for page in range(1, 7):
                (root / 'text_pages' / f'{page:04d}.txt').write_text(f'Fictional page {page}: source evidence.')
            rows = [self.row(1, True, 'Motion for Protective Order'), self.row(2, False),
                    self.row(3, True, 'Opposition'), self.row(4, False), self.row(5, True, 'Reply'), self.row(6, False)]
            boundary = root / 'artifacts/motion_boundaries.json'
            boundary.write_text(json.dumps(build_motion_boundaries(rows, 0)))
            config = sa.ExtractionConfig(kind='motions', guidance=sa.default_guidance('motions', 'extract'))
            items = sa.build_work_items(root, config)
            self.assertEqual([i.item_id for i in items], ['motion:0001', 'motion:0003', 'motion:0005'])
            self.assertEqual([(i.start_page, i.end_page) for i in items], [(1, 2), (3, 4), (5, 6)])
            for item in items:
                self.assertFalse(item.participant_context)
                payload = sa.build_work_spec(item, config, root, root / 'private-candidate.json')
                self.assertIn(f'Fictional page {item.start_page}', str(payload))
                self.assertIn(f'Fictional page {item.end_page}', str(payload))
            boundary.write_text('[]')
            self.assertEqual(sa.build_work_items(root, config), [])
            boundary.unlink()
            with self.assertRaisesRegex(ValueError, 'Find boundaries'):
                sa.build_work_items(root, config)
