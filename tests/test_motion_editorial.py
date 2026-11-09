"""Motion selection/delivery/fallback contracts; invented records, no providers.

Prompt assertions establish delivered instructions, not live editorial quality.
Scripted prose below demonstrates storage/fallback mechanics, not model compliance.
"""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from recordprep import motion_guidance as guidance, summary_agents as sa, summary_prompts
from recordprep.profile_contract import json_bytes, validate_contents
from recordprep.prompt_inspection import DraftInspectionState, inspect_prompt
from test_minute_summaries import fixture
from test_structured_classification import bundle

ROOT = Path(__file__).resolve().parents[1]


def historical_custom_profile():
    from test_practice_profiles import historical_snapshot
    current = historical_snapshot(bundle(), version=13)
    files, manifest = dict(current.files), current.manifest
    manifest['schema_version'] = 11
    manifest['resources']['motion_naming'] = 'historical-motion-naming.json'
    files['historical-motion-naming.json'] = json_bytes({'schema_version': 1, 'motions': []})
    manifest['resources']['motions'] = 'historical-motions.json'
    files['historical-motions.json'] = json_bytes([
        {'id': 'boilerplate', 'title': 'CANARY',
         'guidance': 'CANARY: retain all hearing times, addresses and caption particulars.'}])
    files['profile.json'] = json_bytes(manifest)
    return validate_contents(tuple(files.items()), 'recordprep')


class MotionEditorialTests(unittest.TestCase):
    def test_fixed_topics_select_requests_and_grounds_not_filing_particulars(self):
        topics = guidance.application_catalog()
        self.assertEqual([(t['id'], t['title']) for t in topics], [('request', 'Request'), ('reasons', 'Reasons')])
        self.assertIn('opposition', topics[0]['guidance'])
        self.assertIn('grounds for resisting', topics[1]['guidance'])
        self.assertIn('alternative relief', topics[0]['guidance'])
        for phase in ('extract', 'synthesize'):
            text = guidance.application_guidance(phase)
            for phrase in ('same narrow purpose', 'Exclude hearing dates/times/departments',
                           'street or mailing addresses', 'incident/tracking identifiers',
                           'counsel/firm/contact details', 'digest prose, quote selections and',
                           'not a prose checklist', 'not a sequence of component',
                           'substantive scope, conditions, alternative', 'material contrary evidence',
                           'negation, attribution and qualification', 'Separate opposition example',
                           'Separate reply example'):
                self.assertIn(phrase, text)
            for obsolete in ('only when needed to distinguish', 'Keep any omitted detail if material'):
                self.assertNotIn(obsolete, text)
            self.assertEqual(guidance.application_fingerprint(phase), hashlib.sha256(text.encode()).hexdigest())
        self.assertIn('Digest prose is also the final-summary fallback', guidance.application_guidance('extract'))
        self.assertIn('even if an older digest retained them', guidance.application_guidance('synthesize'))
        self.assertEqual(guidance.application_metadata(), {
            'application_contract': 'recordprep-motion-request-reasons-1',
            'category_catalog': [{'id': 'request', 'title': 'Request'}, {'id': 'reasons', 'title': 'Reasons'}]})

    def test_fixed_selection_reaches_launches_and_inspector_in_every_assignment(self):
        draft = DraftInspectionState({'motions': [{'guidance': 'CANARY'}]}, (), ('INVALID CANARY DRAFT',), None)
        with tempfile.TemporaryDirectory() as td:
            root, project = fixture(Path(td), 1)
            settings = project.parent / 'config.json'
            settings.write_text(json.dumps({'summarize_motions_prompt': 'CANARY KEEP BOILERPLATE',
                                             'summarize_motions_synthesis_prompt': 'CANARY KEEP ADDRESSES'}))
            watched = {settings: settings.read_bytes(), project / 'settings.json': (project / 'settings.json').read_bytes()}
            for profile in (None, bundle(), historical_custom_profile()):
                for phase in ('extract', 'synthesize'):
                    fixed = guidance.application_guidance(phase)
                    if phase == 'extract':
                        config = sa.effective_extraction_config(project, 'motions', profile=profile)
                        item = SimpleNamespace(item_id='motion:0001', ordinal=1, label='Motion to inspect', start_page=1, end_page=1)
                        launch = summary_prompts.extraction_document('recordprep-extract-motion', item, config, root / 'candidate.json').render()
                        self.assertEqual(config.guidance, fixed)
                        self.assertFalse(config.additional_guidance)
                    else:
                        config = sa.effective_synthesis_config(project, 'motions', profile=profile)
                        launch = summary_prompts.synthesis_document('recordprep-synthesize-motions', 1, config, root / 'candidate.json').render()
                        self.assertEqual(config['guidance'].strip(), fixed)
                        self.assertFalse(config['additional_guidance'])
                    view = inspect_prompt({}, 'motions-' + phase, ROOT / '.pi', template=False, snapshot=profile, draft=draft)
                    self.assertEqual(view.issues, ())
                    self.assertIn(fixed, view.display_text())
                    self.assertIn(fixed, launch)
                    self.assertNotIn('CANARY', launch + view.display_text())
                    self.assertIn('Exclude hearing dates/times/departments', view.components[1][1])
            self.assertEqual(watched, {p: p.read_bytes() for p in watched})

    def test_each_motion_phase_tracks_its_skill_and_shared_selection_only_affects_motions(self):
        with tempfile.TemporaryDirectory() as td:
            _root, project = fixture(Path(td), 1)
            profiles = (None, bundle(), historical_custom_profile())
            def configs():
                return {(kind, n): (sa.effective_extraction_config(project, kind, profile=p).fingerprint,
                                   sa.sha256_json(sa.effective_synthesis_config(project, kind, profile=p)))
                        for n, p in enumerate(profiles) for kind in ('hearings', 'reports', 'motions')}
            before = configs()
            skill = project / 'skills/recordprep-extract-motion/SKILL.md'
            skill.write_text(skill.read_text() + '\nFictional extraction selection refinement.\n')
            after = configs()
            for key in before:
                if key[0] == 'motions':
                    self.assertNotEqual(before[key][0], after[key][0])
                    self.assertEqual(before[key][1], after[key][1])
                else:
                    self.assertEqual(before[key], after[key])
            original = guidance.application_guidance
            with patch.object(guidance, 'application_guidance', side_effect=lambda phase:
                              original(phase) + '\nFictional shared selection refinement.'):
                shared = configs()
            for key in after:
                if key[0] == 'motions':
                    self.assertNotEqual(after[key][0], shared[key][0])
                    self.assertNotEqual(after[key][1], shared[key][1])
                else:
                    self.assertEqual(after[key], shared[key])

    def test_complete_sources_and_substantive_qualifications_survive_digest_fallback(self):
        # Complete source reads still include excluded material. Selection is in
        # model instructions, not a source/prose filter or a blocking quality gate.
        texts = (
            ('Motion for inspection', 'The applicant requests inspection of the machine, excluding privileged advice.',
             'The applicant says missing maintenance entries prevent it from testing whether inspections occurred.'),
            ('Opposition to inspection', 'The owner opposes access to health details and alternatively requests redaction.',
             'The owner says health details are irrelevant to whether inspections occurred; it does not oppose release of other entries.'),
            ('Reply on inspection', 'The applicant accepts redaction but maintains its request for inspection entries.',
             'The applicant says redaction answers the privacy objection without withholding the relevant entries.'),
        )
        with tempfile.TemporaryDirectory() as td:
            root, _project = fixture(Path(td), 1)
            boundaries = []
            boilerplate = 'Case DEMO-17; Department 8; hearing at 9 a.m.; street address in caption; counsel contact details.'
            for i, (title, request, reasons) in enumerate(texts):
                start = 1 + 2 * i
                (root / f'text_pages/{start:04d}.txt').write_text(boilerplate + '\n' + request)
                (root / f'text_pages/{start + 1:04d}.txt').write_text(reasons + '\nNotice and signature boilerplate.')
                boundaries.append({'start_page': f'{start:04d}', 'end_page': f'{start + 1:04d}', 'motion_name': title,
                                   'motion_date': '', 'motion_date_basis': 'unknown'})
            (root / 'artifacts/motion_boundaries.json').write_text(json.dumps(boundaries))
            sources = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (root / 'text_pages').iterdir()}
            config = sa.ExtractionConfig('motions', 'CANARY')
            with self.assertWarnsRegex(UserWarning, 'Grouping unavailable'):
                items = sa.build_work_items(root, config)
            self.assertEqual(len(items), 3)
            rows = []
            for item, (_title, request, reasons) in zip(items, texts):
                spec = sa.build_work_spec(item, config, root, root / 'candidate.json')
                self.assertIn(boilerplate, str(spec))
                self.assertIn(request, str(spec))
                self.assertIn(reasons, str(spec))
                row = sa.canonicalize_extraction_candidate({'categories': [
                    {'id': 'request', 'digest': {'text': request, 'evidence': []}},
                    {'id': 'reasons', 'digest': {'text': reasons, 'evidence': []}}]}, item, root / 'text_pages')
                rows.append(row)
            markdown = sa.serialize_digest_markdown('motions', 'Synthetic', rows)
            restored = sa.parse_digest_markdown(markdown, 'motions', 'Synthetic')
            self.assertEqual(restored, rows)
            sections, _flags = sa.normalize_synthesis_sections(restored, [])
            final = sa.render_final_summary('motions', 'Synthetic', restored, sections,
                                            {item.item_id: (item.start_page, None) for item in items})
            for _title, request, reasons in texts:
                self.assertIn(request, final)
                self.assertIn(reasons, final)
            self.assertNotIn(boilerplate, markdown + final)
            self.assertEqual(sources, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sources})
