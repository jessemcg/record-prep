"""Scripted production-worker acceptance, not a visual recognition quality test."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_report_first_pages as reports
from recordprep.case_profiles import apply_case_profile
from recordprep.document_naming import compile_motion_naming, compile_naming_profile
from recordprep.classification_profiles import KINDS, classifier_prompt
from recordprep.motion_pages import motion_preparation_available
from recordprep import summary_agents as sa


class MotionPipelineTests(unittest.TestCase):
    prepare = reports.ReportPipelineTests.prepare
    rows = reports.ReportPipelineTests.rows
    write_rows = reports.ReportPipelineTests.write_rows
    run_steps = reports.ReportPipelineTests.run_steps

    def setUp(self):
        reports.ReportPipelineTests.setUp(self)
        previous = self.profile.ref
        self.profile = reports.bundle()
        self.store.accept_profile(self.profile, expected_previous_digest=None)
        apply_case_profile(self.root, self.profile.ref, expected_previous=previous, store=self.store)
        self.prompts = {classifier_prompt(self.profile, kind)[0]: kind for kind in KINDS}
        for kind in ('motion', 'report', 'form'):
            self.prompts[compile_naming_profile(self.profile, kind).prompt] = kind

    def respond(self, request, **kwargs):
        payload = json.loads(request.data)
        task = self.prompts[payload['messages'][0]['content']]
        image = payload['messages'][1]['content'][0]['image_url']['url'].split(',', 1)[1]
        page = int(base64.b64decode(image).decode().split()[-1])
        self.calls.append((task, page))
        if task == 'motion':
            return json.dumps({'name': self.names.get(page, ''), 'rule_id': 'motion-papers',
                               'date': 'November 1, 2026', 'date_basis': 'filed'})
        if task == 'ct':
            return json.dumps({'page_type': self.kinds[page]})
        if task.startswith('first_'):
            return json.dumps({'first_page': 'yes' if page in self.starts else 'no'})
        return json.dumps({'date': '', 'name': ''})

    def test_every_motion_page_checked_and_independent_papers_published(self):
        titles = {1: 'Motion for Protective Order', 3: 'Opposition to Motion for Protective Order',
                  5: 'Reply in Support of Motion', 7: 'Declaration of Fictional Engineer',
                  9: 'Supplemental Points and Authorities', 11: 'Motion for Protective Order'}
        self.prepare(['CT_motion'] * 12 + ['CT_form', 'CT_notice', 'CT_proof_of_service',
                                          'CT_minute_order', 'CT_report', 'CT_other'],
                     set(titles) | {13, 16, 17}, titles)
        sources = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                   for folder in ('text_pages', 'image_pages') for p in (self.root / folder).iterdir()}
        self.run_steps('_run_step_two', '_run_step_advanced', '_run_step_dates')
        dated = self.rows('dates')
        for row in dated[:12]:
            row.update(name='Stale inherited title', date='January 1, 2000', date_basis='document')
        self.write_rows('dates', dated)
        self.run_steps('_run_step_names', '_run_step_six', '_run_step_seven', '_run_step_correct_boundaries')
        self.assertEqual([p for task, p in self.calls if task == 'first_motion'], list(range(1, 13)))
        self.assertEqual([p for task, p in self.calls if task == 'motion'], sorted(titles))
        for row in self.rows('names')[:12]:
            first = int(Path(row['file_name']).stem) in titles
            self.assertEqual(row['motion_first_page'], 'yes' if first else 'no')
            if not first:
                for key in ('name', 'date', 'date_basis', 'naming_rule_id'):
                    self.assertNotIn(key, row)
        bounds = json.loads((self.root / 'artifacts/motion_boundaries.json').read_text())
        self.assertEqual([(r['start_page'], r['end_page']) for r in bounds],
                         [(f'{n:04d}', f'{n + 1:04d}') for n in sorted(titles)])
        self.assertEqual([r['motion_id'] for r in bounds], [f'motion:{n:04d}' for n in sorted(titles)])
        self.assertTrue(all(r['motion_date_basis'] == 'filed' for r in bounds))
        toc = (self.root / 'artifacts/toc.txt').read_text()
        self.assertIn('MOTIONS', toc)
        self.assertEqual(toc.count('Motion for Protective Order'), 3)  # Includes opposition qualifier.
        items = sa.build_work_items(self.root, sa.ExtractionConfig('motions', '', profile=self.profile))
        self.assertEqual(len(items), 6)
        self.assertTrue(all(i.end_page == i.start_page + 1 and not i.participant_context for i in items))
        for item in items:
            spec = sa.build_work_spec(item, sa.ExtractionConfig('motions', ''), self.root, self.root / 'candidate.json')
            self.assertIn(f'Synthetic source page {item.start_page}.', str(spec))
            self.assertIn(f'Synthetic source page {item.end_page}.', str(spec))
        self.assertEqual(sources, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sources})

    def test_legacy_missing_motion_preparation_is_not_empty_boundary(self):
        self.prepare(['CT_other'], set(), {})
        self.run_steps('_run_step_two', '_run_step_advanced', '_run_step_dates', '_run_step_names')
        self.assertTrue(motion_preparation_available(self.root, self.rows('names')))
        self.run_steps('_run_step_six', '_run_step_seven')
        path = self.root / 'artifacts/motion_boundaries.json'
        self.assertEqual(json.loads(path.read_text()), [])
        path.unlink()  # Synthetic historical bundle with no motion-preparation evidence.
        metadata = self.root / 'classification/profile-advanced.json'
        value = json.loads(metadata.read_text()); value.pop('motion_checks_version')
        metadata.write_text(json.dumps(value))
        self.assertFalse(motion_preparation_available(self.root, self.rows('names')))
        self.run_steps('_run_step_seven')
        self.assertFalse(path.exists())

    def test_motion_source_map_documents_and_manifest_keys(self):
        self.prepare(['CT_motion', 'CT_motion'], {1}, {1: 'Declaration of Fictional Engineer'})
        self.run_steps('_run_step_two', '_run_step_advanced', '_run_step_dates', '_run_step_names',
                       '_run_step_six', '_run_step_seven')
        script = reports.ROOT / '.pi/skills/recordprep-build-source-map/scripts/build_source_map.py'
        spec = importlib.util.spec_from_file_location('motion_test_source_map', script)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        documents = module.boundary_documents(self.root, {})
        motion = next(d for d in documents if d['type'] == 'motion')
        self.assertEqual(motion['id'], 'motion:0001')
        self.assertIn('motion:0001', motion['aliases'])
        self.assertEqual(motion['motion_date_basis'], 'filed')
        self.assertEqual(motion['motion_name'], 'Declaration of Fictional Engineer')
        self.ui._write_manifest(self.root, [])
        manifest = json.loads((self.root / 'manifest.json').read_text())
        self.assertEqual(manifest['files']['motion_boundaries'], 'artifacts/motion_boundaries.json')
        self.assertNotIn('summarized_motions', manifest['files'])


class MotionEmptyStageTests(unittest.TestCase):
    def test_zero_motion_stage_without_pi_and_missing_preserves_prior_final(self):
        from test_pi_resources import _load_runner_module
        runner = _load_runner_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'case'; (root / 'artifacts').mkdir(parents=True)
            (root / 'text_pages').mkdir()
            (root / 'case_name.txt').write_text('Fictional_Case')
            boundary = root / 'artifacts/motion_boundaries.json'; boundary.write_text('[]')
            project = Path(temp) / 'project'; project.mkdir()
            with patch.object(runner, '_resolve_pi_command', side_effect=AssertionError('No Pi for zero items')), \
                 patch.object(runner, '_run_extraction_child', side_effect=AssertionError('No extraction')), \
                 patch.object(runner, '_run_synthesis_child', side_effect=AssertionError('No synthesis')), \
                 patch.dict('os.environ', {'HOME': temp, 'XDG_CACHE_HOME': str(Path(temp) / 'cache'),
                                           'XDG_CONFIG_HOME': str(Path(temp) / 'config')}):
                stage = runner.SkillStage('create_motion_summaries', 'Create motion summaries',
                                         runner.SUMMARY_SKILL_NAMES['motions']['extract'],
                                         runner.SUMMARY_TOOL_ALLOWLISTS['extract'])
                self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                final = sa.summary_final_path(root, 'motions')
                meta = sa.load_final_meta(root, 'motions')
                self.assertEqual(meta['item_ids'], [])
                self.assertEqual(meta['kind'], 'motions')
                self.assertEqual(meta['final_text_sha256'], hashlib.sha256(final.read_bytes()).hexdigest())
                before = final.read_bytes(), final.stat().st_mtime_ns
                boundary.unlink()
                with self.assertRaisesRegex(ValueError, 'Find boundaries'):
                    runner._run_summary_stage(stage, root, project)
                self.assertEqual((final.read_bytes(), final.stat().st_mtime_ns), before)
