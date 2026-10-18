"""Canonical report editorial skill and real offline staging/publication.

Fictional inspection data only; no paid calls or private settings/case access.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from recordprep import summary_agents as sa, summary_preflight as preflight
from recordprep import summary_profiles as sp
from recordprep.case_profiles import apply_case_profile
from recordprep.profile_store import ProfileStore
from recordprep.quote_display import NORMALIZATION_NOTICE
from recordprep.summary_editions import build_summary_edition, validate_edition_payload
from test_pi_resources import _load_runner_module
from test_profile_generation import bundled, seed_profile_preparation

PROJECT = Path(__file__).resolve().parents[1] / '.pi'
SKILL = 'recordprep-synthesize-reports'


class ReportEditorialTests(unittest.TestCase):
    def test_canonical_skill_encodes_the_approved_editorial_method(self):
        skill = (PROJECT / 'skills' / SKILL / 'SKILL.md').read_text()
        text = ' '.join(skill.split())
        for phrase in (
            "respect the reader's time", "main attributed conclusion", "qualification needed",
            "Do not open with filing metadata", "Digest categories organize extraction",
            "each fact its fullest treatment in its best place once", "short and focused",
            "opener should orient", "favorable observations, contrary evidence",
            "attribute the specific discrepancy", "expanded quotation", "actor and duty bearer",
            "never repair, shorten, rewrite or reassign", "No separate quality pass",
            "Do not apply the minute summaries' one-or-two-outcome", "Fictional examples",
            "Do not add editorial introductions or capitalization-normalization announcements",
        ):
            self.assertIn(phrase, text)
        self.assertIn('only after repairs', text)

    def test_profile_staging_fingerprints_and_capacity_use_the_same_visible_report_skill(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / '.pi'
            shutil.copytree(PROJECT, project)
            source = project / 'skills' / SKILL / 'SKILL.md'
            self.assertEqual(sp.profile_skill_text(project, SKILL, 'synthesize'), source.read_text())
            self.assertEqual(preflight.stage_static_components(project, SKILL, profile_phase='synthesize')['skill_chars'],
                             len(source.read_text()))
            for profile in (None, bundled('general'), bundled('california_dependency')):
                with self.subTest(profile=profile.ref.specialty_id if profile else 'unassigned'):
                    before = {(kind, phase): (sa.effective_extraction_config(project, kind, profile=profile).fingerprint
                              if phase == 'extract' else sa.sha256_json(sa.effective_synthesis_config(project, kind, profile=profile)))
                              for kind in ('hearings', 'reports') for phase in ('extract', 'synthesize')}
                    contents = source.read_text()
                    source.write_text(contents + '\nSynthetic report editorial clarification.\n')
                    after = {(kind, phase): (sa.effective_extraction_config(project, kind, profile=profile).fingerprint
                             if phase == 'extract' else sa.sha256_json(sa.effective_synthesis_config(project, kind, profile=profile)))
                             for kind in ('hearings', 'reports') for phase in ('extract', 'synthesize')}
                    self.assertNotEqual(before['reports', 'synthesize'], after['reports', 'synthesize'])
                    for key in before.keys() - {('reports', 'synthesize')}:
                        self.assertEqual(before[key], after[key])
                    config = sa.effective_synthesis_config(project, 'reports', profile=profile)
                    self.assertEqual(config['skill_sha256'], sa._resource_sha256(source))
                    self.assertIn(sp.REPORT_QUOTE_CASE_GUIDANCE, config['guidance'])
                    self.assertNotIn('Python adds\none normalization notice', config['guidance'])
                    self.assertEqual(config['renderer_version'], 'recordprep-report-renderer-8')
                    source.write_text(contents)
            # Hearing profile staging remains the existing generic template.
            self.assertIn('# Digest synthesis', sp.profile_skill_text(project, 'recordprep-synthesize-hearings', 'synthesize'))

    def test_actual_report_child_stages_canonical_skill_and_old_rendering_reruns_synthesis_only(self):
        for specialty in (None, 'general', 'california_dependency'):
            with self.subTest(specialty=specialty), tempfile.TemporaryDirectory() as td:
                base = Path(td)
                root = base / 'bundle'
                (root / 'text_pages').mkdir(parents=True)
                (root / 'artifacts').mkdir()
                (root / 'case_name.txt').write_text('Fictional inspection')
                (root / 'text_pages/0001.txt').write_text(
                    'The inspector recommended reopening ONLY AFTER REPAIRS. No further movement was observed, '
                    'but safety for reopening was not established.')
                (root / 'artifacts/report_boundaries.json').write_text(json.dumps([
                    {'start_page': 1, 'end_page': 1, 'report_name': 'Inspection report', 'date': 'April 9, 2030'}]))
                project = base / 'project/.pi'
                shutil.copytree(PROJECT, project)
                (project.parent / 'config.json').write_text('{}')
                runner = _load_runner_module()
                profile = bundled(specialty) if specialty else None
                store = ProfileStore('recordprep', config_root=base / 'config', data_root=base / 'data')
                if profile:
                    store.accept_profile(profile, expected_previous_digest=None)
                    apply_case_profile(root, profile.ref, expected_previous=None, store=store)
                category = profile.resource('reports')[0]['id'] if profile else sa.REPORT_CATEGORY_IDS[0]
                def extraction(*_args):
                    return {'categories': [{'id': category, 'digest': {
                        'text': 'The inspector recommended reopening only after repairs. No further movement was observed, '
                                'but safety for reopening was not established.',
                        'evidence': [{'file_page': 1, 'text': 'ONLY AFTER REPAIRS'}]}}]}
                workspaces = []
                def child_run(child):
                    staged = child.workspace / '.pi/skills' / SKILL / 'SKILL.md'
                    self.assertEqual(staged.read_bytes(), (project / 'skills' / SKILL / 'SKILL.md').read_bytes())
                    dataset = json.loads(Path(child.env_overrides['RECORDPREP_SUMMARY_DATASET']).read_text())
                    self.assertEqual(dataset['kind'], 'reports')
                    record = dataset['rows'][0]
                    evidence = record['categories'][0]['digest']['evidence'][0]
                    quote = evidence['quote_id']
                    Path(dataset['candidate_path']).write_text(json.dumps({
                        'artifact': 'recordprep-summary-synthesis-candidate', 'sections': [{
                            'item_id': record['item_id'],
                            'paragraphs': ['The inspector recommended reopening {{quote:' + quote + '}}.',
                                           'No further movement was observed, but safety for reopening was not established.'],
                            'quote_capitalizations': {quote: 'only after repairs'}}]}))
                    workspaces.append(child.workspace)
                    return 0
                stage = runner.SkillStage('create_report_summaries', 'Create report summaries', 'recordprep-extract-report', '')
                from contextlib import nullcontext
                legacy = patch('recordprep.case_profiles.resolve_case_profile', return_value=None) if profile is None else nullcontext()
                with legacy, patch('recordprep.case_profiles.profile_store', return_value=store), \
                     patch.object(runner, '_resolve_pi_command', return_value=['synthetic-pi']), \
                     patch.object(runner, '_check_pi_version'), \
                     patch.object(runner, '_stage_capacity', return_value=None), \
                     patch.object(runner, '_report_capacity'), \
                     patch('recordprep.summary_preflight.pi_runtime.available_pi_models', return_value=[]), \
                     patch.object(runner, '_run_extraction_child', side_effect=extraction) as extract, \
                     patch.object(runner._SummaryChildRunner, 'run', child_run):
                    if profile:
                        seed_profile_preparation(root, profile, project)
                    self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                    self.assertEqual(extract.call_count, 1)
                    self.assertEqual(len(workspaces), 1)
                    final = sa.summary_final_path(root, 'reports')
                    current = final.read_text()
                    self.assertIn('“only after repairs”', current)
                    self.assertNotIn(NORMALIZATION_NOTICE, current)
                    digests = sa.summary_digest_path(root, 'reports')
                    digest_before = digests.read_bytes()
                    rows_before = copy.deepcopy(sa.load_digest_markdown(root, 'reports'))
                    self.assertEqual(rows_before[0]['categories'][0]['digest']['evidence'][0]['text'], 'ONLY AFTER REPAIRS')
                    meta_path = sa.summary_final_meta_path(root, 'reports')
                    old = current.replace('Reports Summary\n', 'Reports Summary\n\n' + NORMALIZATION_NOTICE + '\n', 1)
                    final.write_text(old)
                    metadata = json.loads(meta_path.read_text())
                    previous_config = sa.effective_synthesis_config(project, 'reports', profile=profile) | {
                        'renderer_version': 'recordprep-summary-renderer-7'}
                    metadata.update(renderer_version='recordprep-summary-renderer-7', final_text_sha256=sa.sha256_text(old),
                                    synthesis_config_sha256=sa.sha256_json(previous_config))
                    meta_path.write_text(json.dumps(metadata))
                    stable = (project.parent / 'config.json', root / 'text_pages/0001.txt')
                    if profile:
                        stable += (store.registry_path,)
                    protected = (final, meta_path, digests, *stable)
                    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
                    self.assertTrue(sa.summary_stage_freshness_issues(root, 'reports', project_dir=project))
                    self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                    self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                    self.assertEqual(extract.call_count, 1)
                    self.assertEqual(len(workspaces), 2)
                    self.assertEqual(final.read_text(), current)
                    self.assertEqual(digests.read_bytes(), digest_before)  # Normal explicit publication may refresh mtime.
                    self.assertEqual(sa.load_digest_markdown(root, 'reports'), rows_before)
                    self.assertEqual(sa.summary_stage_freshness_issues(root, 'reports', project_dir=project), [])
                    if profile:
                        # Profile runs skip current synthesis; the legacy explicit
                        # resynthesis behavior is intentionally not changed here.
                        self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                        self.assertEqual(len(workspaces), 2)
                    self.assertTrue(all(not p.exists() for p in workspaces))
                    for path in stable:
                        self.assertEqual(before[path], (path.read_bytes(), path.stat().st_mtime_ns))
                    if specialty == 'general':
                        edition = build_summary_edition('reports', final, root)
                        self.assertEqual(validate_edition_payload(edition.page_map, kind='reports', root_dir=root,
                                         source_text=current, pdf_bytes=edition.pdf_bytes), [])
                        self.assertEqual([q.phrase for page in edition.pages for q in page.quotes], ['only after repairs'])
                        self.assertNotIn(NORMALIZATION_NOTICE, '\n'.join(page.text for page in edition.pages))


if __name__ == '__main__':
    unittest.main()
