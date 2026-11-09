"""Universal hearing method; report topics and historical evidence stay independent."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep.hearing_guidance import application_catalog, application_guidance, application_metadata
from recordprep.profile_contract import compile_stage_profile
from recordprep.profile_workflows import ProfileEditor
from recordprep.summary_profiles import compile_summary, summary_topics
from recordprep.prompt_inspection import inspect_prompt, DraftInspectionState
from test_practice_profiles import historical_snapshot
from test_structured_classification import bundle, ROOT
from summary_agent_fixtures import synthetic_facts_row


class ApplicationHearingTopicsTests(unittest.TestCase):
    def test_every_profile_and_legacy_config_uses_identical_fixed_topics(self):
        profiles = [bundle()]
        for version in range(1, 14):
            if version in (11, 12):
                from test_application_motion_naming import historical
                from recordprep.motion_guidance import NEUTRAL_MOTION_NAMING
                base = historical(NEUTRAL_MOTION_NAMING, version)
            else:
                base = historical_snapshot(bundle(), version)
            editor = ProfileEditor(base)
            editor.resources['hearings'][0].update(title='CANARY TITLE', guidance='CANARY exclude defendants')
            profiles.append(editor.snapshot())
        baseline = sa.ExtractionConfig('hearings', 'CANARY', additional_guidance='CANARY')
        self.assertEqual(baseline.guidance, application_guidance('extract'))
        self.assertEqual(baseline.additional_guidance, '')
        for profile in profiles:
            before = profile.files
            config = sa.ExtractionConfig('hearings', 'CANARY', additional_guidance='CANARY', profile=profile)
            self.assertEqual(config.fingerprint, baseline.fingerprint)
            self.assertEqual(config.definitions, baseline.definitions)
            for phase in ('extract', 'synthesize'):
                compiled = compile_summary(profile, 'hearings', phase)
                self.assertEqual(compiled.prompt, application_guidance(phase))
                self.assertFalse(compiled.provenance)
            for stage in ('hearing_extraction', 'hearing_synthesis'):
                self.assertEqual(compile_stage_profile(profile, stage, core_contract=b'fixed').resources, ())
            self.assertEqual(profile.files, before)
        topics = application_catalog()
        self.assertEqual(topics[0]['title'], 'Appearances')
        self.assertIn('Which parties appeared', topics[0]['guidance'])
        self.assertIn('Silence does not establish absence', topics[0]['guidance'])
        self.assertNotIn('parent', topics[0]['guidance'].lower())
        historical = historical_snapshot(bundle(), 10).resource('hearings')
        self.assertEqual(topics[1:], historical[1:])

    def test_report_topics_remain_editable_and_motion_and_hearing_stay_fixed(self):
        base = bundle(); editor = ProfileEditor(base)
        editor.resources['reports'][0]['guidance'] += ' CANARY probation focus.'
        changed = editor.snapshot()
        for phase in ('extract', 'synthesize'):
            self.assertNotEqual(compile_summary(base, 'reports', phase), compile_summary(changed, 'reports', phase))
            for kind in ('hearings', 'motions'):
                self.assertEqual(compile_summary(base, kind, phase), compile_summary(changed, kind, phase))

    def test_draft_projection_preserves_old_bytes_and_report_resources(self):
        old = historical_snapshot(bundle(), 10); before = old.files
        editor = ProfileEditor(old); editor.use_current_schema(); current = editor.snapshot()
        self.assertEqual(current.manifest['schema_version'], 14)
        self.assertNotIn('hearings', current.manifest['resources'])
        self.assertNotIn('hearings.json', dict(current.files))
        for name in ('reports', 'naming'):
            self.assertEqual(current.resource(name), old.resource(name))
        self.assertEqual(old.files, before)

    def test_inspection_ignores_invalid_drafts_and_shows_fixed_topics(self):
        draft = DraftInspectionState({'hearings': [{'guidance': 'CANARY'}]}, (), ('INVALID CANARY',), None)
        for phase in ('extract', 'synthesize'):
            for template in (True, False):
                view = inspect_prompt({}, 'hearings-' + phase, ROOT / '.pi', template=template, draft=draft)
                self.assertFalse(view.issues)
                self.assertIn(application_guidance(phase), view.display_text())
                self.assertNotIn('CANARY', view.display_text())

    def test_old_and_new_digest_formats_roundtrip_without_relabeling(self):
        for historical in (True, False):
            row = synthetic_facts_row('hearings', historical=historical)
            text = sa.serialize_digest_markdown('hearings', 'Synthetic', [row])
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'digest.md'; path.write_text(text)
                before = path.read_bytes()
                rows = sa.parse_digest_markdown(path.read_text(), 'hearings', 'Synthetic')
                self.assertEqual(rows, [row])
                self.assertEqual(path.read_bytes(), before)
            self.assertIn('Parent Appearances' if historical else '### Appearances', text)
            if not historical:
                self.assertEqual(row['application_metadata'], application_metadata())
                self.assertNotIn('profile_metadata', row)

    def test_historical_profile_digest_keeps_its_recorded_heading(self):
        from dataclasses import asdict
        profile = historical_snapshot(bundle(), 10)
        row = synthetic_facts_row('hearings', historical=True)
        catalog = [{'id': t['id'], 'title': t['title']} for t in profile.resource('hearings')]
        catalog[0]['title'] = 'Historical attendance focus'
        row.update(schema_version=3, profile_metadata={'category_catalog': catalog,
            'profile_provenance': {'schema_version': 1, 'profile_ref': asdict(profile.ref),
                                   'components': {'hearing_extraction': 'a' * 64}}})
        original = copy.deepcopy(row)
        text = sa.serialize_digest_markdown('hearings', 'Synthetic', [row])
        self.assertEqual(sa.parse_digest_markdown(text, 'hearings', 'Synthetic'), [original])
        self.assertIn('Historical attendance focus', text)
        self.assertNotIn('application_metadata', text)
        self.assertFalse(sa._row_ownership_current(row, 'hearings'))
        self.assertEqual(row, original)

    def test_application_topic_changes_stale_hearings_not_reports(self):
        from recordprep import hearing_guidance
        before = {kind: sa.ExtractionConfig(kind, 'fixture', profile=bundle()).fingerprint
                  for kind in ('hearings', 'reports', 'motions')}
        changed = application_catalog(); changed[0]['guidance'] += ' Synthetic application change.'
        with patch.object(hearing_guidance, 'HEARING_TOPICS', changed):
            after = {kind: sa.ExtractionConfig(kind, 'fixture', profile=bundle()).fingerprint
                     for kind in before}
        self.assertNotEqual(before['hearings'], after['hearings'])
        self.assertEqual(before['reports'], after['reports'])
        self.assertEqual(before['motions'], after['motions'])

    def test_current_config_is_profile_independent_and_old_rows_are_not_current(self):
        with patch.object(sa, 'summary_stage_settings', return_value={
                'extract_prompt': 'CANARY', 'synthesize_prompt': 'CANARY'}), patch(
                'recordprep.pi_runtime.resolve_stage_model_identity') as identity:
            identity.return_value.provider = 'synthetic'; identity.return_value.model_id = 'model'; identity.return_value.thinking = 'low'
            for phase, compiler in [('extract', sa.effective_extraction_config), ('synthesize', sa.effective_synthesis_config)]:
                a = compiler(ROOT / '.pi', 'hearings')
                b = compiler(ROOT / '.pi', 'hearings', profile=bundle())
                self.assertEqual(a.fingerprint if phase == 'extract' else a, b.fingerprint if phase == 'extract' else b)
        from types import SimpleNamespace
        item = SimpleNamespace(kind='hearings', item_id='hearing:0001', generation_sha256='same')
        old = synthetic_facts_row('hearings', historical=True, generation_sha256='same')
        self.assertFalse(sa._row_is_current([item], [old], item.item_id))
        current = synthetic_facts_row('hearings', generation_sha256='same')
        self.assertTrue(sa._row_is_current([item], [current], item.item_id))
