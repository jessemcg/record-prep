"""Application-owned minutes: synthetic, offline ownership and preservation checks."""
from dataclasses import asdict
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from recordprep import minute_summaries as minutes, summary_agents as sa, boundary_profiles
from recordprep.profile_contract import compile_stage_profile, validate_contents, json_bytes, ProfileError
from recordprep.profile_workflows import ProfileEditor
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_customization import legacy_customization_editor
from recordprep.prompt_inspection import inspect_prompt, DraftInspectionState
from recordprep.summary_prompts import minute_document
from test_practice_profiles import historical_snapshot
from test_structured_classification import bundle, ROOT
from test_profile_generation import changed, bundled, seed_profile_preparation
from test_minute_summaries import fixture, candidate

CANARY = 'INACTIVE-MINUTE-CANARY α {private}'


def shipped_previous():
    folder = ROOT / 'tests/fixtures/minute_profile_1_10'
    return validate_contents(tuple((p.name, p.read_bytes()) for p in folder.iterdir()), 'recordprep')


class ApplicationMinuteTests(unittest.TestCase):
    def test_all_schemas_custom_and_unassigned_have_identical_components_and_prompts(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = fixture(Path(td), 1)
            config_path = project.parent / 'config.json'
            config_path.write_text(json.dumps({'summarize_minutes_prompt': CANARY}))
            protected = (config_path.read_bytes(), config_path.stat().st_mtime_ns)
            expected = minutes.stage_config(project)[1]
            profiles = [None, bundle(), bundled('general'), shipped_previous()]
            for version in range(1, 10):
                profiles.append(changed(historical_snapshot(bundle(), version), 'minutes', CANARY))
            for profile in profiles:
                original = profile.files if profile else None
                with self.subTest(schema=profile.manifest['schema_version'] if profile else None):
                    config = minutes.stage_config(project, profile=profile)[1]
                    self.assertEqual(config, expected)
                    self.assertNotIn(CANARY, json.dumps(config))
                    self.assertNotIn(CANARY, minute_document(config).render())
                    self.assertEqual(minutes.build_items(root, config), minutes.build_items(root, expected))
                    if profile:
                        compiled = compile_stage_profile(profile, 'minutes', core_contract=b'fixed')
                        self.assertEqual(compiled.resources, ())
                        self.assertEqual(compiled.component_sha256,
                            compile_stage_profile(bundle(), 'minutes', core_contract=b'fixed').component_sha256)
                        self.assertEqual(profile.files, original)
            self.assertEqual(protected, (config_path.read_bytes(), config_path.stat().st_mtime_ns))
            active_tool = (project / 'extensions' / minutes.EXTENSION_NAME).read_text()
            self.assertNotIn('under the profile', active_tool)
            for forbidden in ('section 388', 'juvenile', 'parents', 'FIRST PAGE only', 'PRACTICE GUIDANCE', 'ADDITIONAL USER GUIDANCE'):
                self.assertNotIn(forbidden, minute_document(expected).render())

    def test_ordinary_config_saves_preserve_legacy_minute_value_or_absence(self):
        from recordprep.ui import main_window as ui
        for present in (False, True):
            raw = {'unknown': ['preserve']}
            if present:
                raw['summarize_minutes_prompt'] = CANARY + '\n  literal spacing\t'
            with patch.object(ui, '_read_config', side_effect=lambda: copy.deepcopy(raw)), \
                 patch.object(ui, '_write_config') as write:
                ui.save_classifier_settings('https://synthetic.invalid', 'synthetic', 'fake-key',
                                            'inert', 'inert', False, '2')
            saved = write.call_args.args[0]
            self.assertEqual('summarize_minutes_prompt' in saved, present)
            if present:
                self.assertEqual(saved['summarize_minutes_prompt'], raw['summarize_minutes_prompt'])
            self.assertEqual(raw['unknown'], saved['unknown'])

    def test_neutral_multi_page_attendance_and_source_map_component(self):
        source = 'Applicant Alex Vale represented by counsel. Respondent Sam Reed is absent.'
        later = 'Alex Vale personally appeared remotely. Applicant Jo Lane did not appear.'
        item = minutes.MinuteItem('minute:0001', 1, 'May 7, 2030', 1, 2,
                                  source+'\n'+later, source, 'fictional', ((1, source), (2, later)))
        value = {'artifact': 'recordprep-minute-candidate', 'hearing': 'Motion to compel',
                 'appearances': [
                     {'person': 'Alex Vale', 'role_label': 'Applicant', 'status': 'present',
                      'evidence': [{'file_page': 2, 'text': 'Alex Vale personally appeared remotely.'}]},
                     {'person': 'Jo Lane', 'role_label': 'Applicant', 'status': 'not_present',
                      'evidence': [{'file_page': 2, 'text': 'Applicant Jo Lane did not appear.'}]},
                     {'person': 'Sam Reed', 'role_label': 'Respondent', 'status': 'not_present',
                      'evidence': [{'file_page': 1, 'text': 'Respondent Sam Reed is absent.'}]},
                     {'person': 'Pat Gray', 'role_label': 'Defendant', 'status': 'present',
                      'evidence': [{'file_page': 9, 'text': 'Unverifiable attendance'}]}],
                 'orders': 'Records must be supplied under the confidentiality order by May 21.',
                 'next_hearing': 'Unclear.'}
        row = minutes.normalize_candidate(value, item)
        self.assertEqual([p['status'] for p in row['appearances']],
                         ['present', 'not_present', 'not_present', 'unclear'])
        self.assertEqual(minutes.normalize_candidate(value, item, profile=shipped_previous()), row)
        lines = minutes.render_compact_entry(item, row)
        self.assertEqual(lines[1], "Appearances: Alex Vale present; Jo Lane absent; Respondent absent; Defendant's appearance unclear.")
        self.assertEqual(lines[2], 'Orders: '+value['orders'])
        self.assertEqual(lines[3], 'Next: Unclear.')
        self.assertEqual(row['positions'], '')
        from recordprep.publication_profiles import provenance
        with tempfile.TemporaryDirectory() as td:
            root, project = fixture(Path(td), 1)
            with patch('recordprep.publication_profiles.is_ct_only', return_value=True):
                before = provenance(shipped_previous(), root, project)
                after = provenance(changed(shipped_previous(), 'minutes', CANARY), root, project)
            self.assertEqual(before['components'], after['components'])
            self.assertEqual(before['components']['minutes'], minutes.application_contract(project)['component_sha256'])

    def test_exact_nonproduction_absence_evidence_and_no_semantic_inference(self):
        first = 'Applicant Vale remains in custody. Counsel Rowan appears for Vale.'
        later = 'Applicant Vale was not produced for this hearing.'
        item = minutes.MinuteItem('minute:0001', 1, 'April 9, 2030', 1, 2,
                                  first+'\n'+later, first, 'fictional', ((1, first), (2, later)))
        base = {'artifact': 'recordprep-minute-candidate', 'hearing': 'Review',
                'orders': 'No substantive orders recorded.', 'next_hearing': 'Not stated.'}
        for passage, page, submitted, expected in (
            (later, 2, 'not_present', 'not_present'),
            ('Vale was absent', 2, 'not_present', 'unclear'),
            (later, 1, 'not_present', 'unclear'),
            ('Counsel Rowan appears for Vale.', 1, 'unclear', 'unclear'),
            ('Applicant Vale remains in custody.', 1, 'unclear', 'unclear'),
        ):
            with self.subTest(passage=passage, page=page):
                value = base | {'appearances': [{'person': 'Vale', 'role_label': 'Applicant',
                    'status': submitted, 'evidence': [{'file_page': page, 'text': passage}]}]}
                row = minutes.normalize_candidate(value, item)
                self.assertEqual(row['appearances'][0]['status'], expected)
        # Counsel/custody fixtures submit unclear: the matcher verifies location,
        # not semantics. Neither test nor Python infers personal attendance.

    def test_fixed_guidance_distinguishes_attendance_and_current_future_settings(self):
        prompt = minutes.application_guidance()
        skill = (ROOT / '.pi/skills/recordprep-summarize-minutes/SKILL.md').read_text()
        for text in (prompt, skill):
            for phrase in ('not produced for THIS hearing', 'custody alone',
                           'short continuous verbatim passage from the declared supplied page',
                           'paraphrase', 'reconstruct',
                           'This matter is on calendar for a continued hearing',
                           'The court will revisit access at the next',
                           'Further review is set', 'hearing transcript',
                           'participant metadata', 'assumed missing page',
                           'return/production logistics', 'substantive disposition',
                           'supported scheduled date', 'silently repair source chronology'):
                self.assertIn(phrase.lower(), ' '.join(text.lower().split()))

    def test_instruction_hashes_invalidate_only_explicit_minute_work(self):
        with tempfile.TemporaryDirectory() as td, patch('recordprep.case_profiles.resolve_case_profile', return_value=None):
            root, project = fixture(Path(td), 1)
            minutes.run_stage(root, project, Mock(return_value=candidate()))
            before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in
                      (minutes.checkpoint_path(root), minutes.meta_path(root), sa.summary_final_path(root, 'minutes'))}
            with patch.object(minutes, 'APPLICATION_MINUTE_CORE', minutes.APPLICATION_MINUTE_CORE + '\nFictional refinement.'):
                self.assertTrue(minutes.freshness_issues(root, project))
                self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
                generate = Mock(return_value=candidate())
                minutes.run_stage(root, project, generate)
                generate.assert_called_once()
                generate.reset_mock()
                minutes.run_stage(root, project, generate)
                generate.assert_not_called()
            # Restore baseline instructions/rows before testing skill-only invalidation.
            minutes.run_stage(root, project, Mock(return_value=candidate()))
            skill_path = project / 'skills' / minutes.SKILL_NAME / 'SKILL.md'
            skill_path.write_text(skill_path.read_text() + '\nFictional refinement.')
            self.assertTrue(minutes.freshness_issues(root, project))
            generate = Mock(return_value=candidate())
            minutes.run_stage(root, project, generate); generate.assert_called_once()
            generate.reset_mock(); minutes.run_stage(root, project, generate); generate.assert_not_called()

    def test_schema10_projection_save_create_and_reset_omit_minutes_without_old_writes(self):
        old = shipped_previous()
        self.assertEqual(old.ref.content_sha256, '975fc7ddea124a0aa43cb83b77aef2cf0128f0af4e6c858fdf002dcbd80ee6c8')
        original = old.files
        for editor in (editable_profile(old), ProfileEditor.create(old, 'Synthetic'),
                       legacy_customization_editor({'summarize_minutes_prompt': CANARY}, base=old),
                       ProfileEditor(bundle())):
            naming_before = json_bytes(editor.resources['naming'])
            editor.use_current_schema()
            current = editor.snapshot()
            # Schema projection preserves each editor's own naming catalog.
            self.assertEqual(json_bytes(current.resource('naming')), naming_before)
            self.assertEqual(current.manifest['schema_version'], 14)
            self.assertNotIn('minutes', current.manifest['resources'])
            self.assertNotIn('minutes', editor.resources)
            self.assertNotIn('minutes.md', dict(current.files))
            self.assertNotIn(CANARY.encode(), b''.join(data for _, data in current.files))
            bad = dict(current.files)
            manifest = current.manifest
            manifest['resources']['minutes'] = 'minutes.md'
            bad['profile.json'] = json_bytes(manifest)
            bad['minutes.md'] = b'Forbidden reintroduction'
            with self.assertRaises(ProfileError):
                validate_contents(tuple(bad.items()), 'recordprep')
        self.assertEqual(old.files, original)
        for name in ('reports.json', 'policies.json', 'case-name.md'):
            self.assertEqual(dict(bundle().files)[name], dict(old.files)[name])

    def test_fixed_inspection_ignores_invalid_unrelated_draft(self):
        draft = DraftInspectionState({'minutes': CANARY}, (('naming', '{ invalid ' + CANARY),),
                                     ('Synthetic unrelated invalid draft',), None)
        expected = inspect_prompt({}, 'minutes', ROOT / '.pi')
        self.assertFalse(expected.issues)
        for template in (True, False):
            actual = inspect_prompt({'minutes': CANARY}, 'minutes', ROOT / '.pi', template=template, draft=draft)
            self.assertEqual(actual, expected)
            self.assertNotIn(CANARY, actual.display_text())
            self.assertEqual(actual.components[2][1], minute_document({'guidance': minutes.application_guidance()}).render())
        self.assertIn('April 9, 2030 — Administrative review', expected.display_text())
        self.assertIn('May 7, 2030 — Motion to compel', expected.display_text())

    def test_schema1_reader_keeps_parental_semantics_and_prose_literal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = {'item_id': 'minute:0001', 'fingerprint': 'old', 'hearing': 'Review',
                   'reporting': 'not_reported', 'parents': [
                       {'parent': 'Mother', 'status': 'not_present', 'first_page_evidence': ''}],
                   'orders': 'Historical literal order.', 'quality_flags': []}
            path = minutes.checkpoint_path(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'artifact': 'recordprep-minute-rows', 'schema_version': 1,
                                        'rows': [row], 'rows_sha256': sa.sha256_json([row])}))
            before = path.read_bytes(), path.stat().st_mtime_ns
            self.assertEqual(minutes.load_rows(root), [row])
            self.assertEqual(minutes.render_paragraph(row),
                             'Review. Not Reported. Mother did not appear. Historical literal order.')
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_historical_schema4_cannot_be_reused_even_with_current_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root, project = fixture(Path(td), 1)
            with patch('recordprep.case_profiles.resolve_case_profile', return_value=None), \
                 patch('recordprep.case_profiles.read_case_profile_ref', return_value=None):
                # Publication guard uses application selection; isolate the complete
                # unassigned path exactly as the existing legacy fixture harness.
                with patch('recordprep.case_profiles.case_profile_publication') as publication, \
                     patch('recordprep.boundary_profiles.require_current_boundaries'):
                    publication.return_value.__enter__.return_value = None
                    minutes.run_stage(root, project, Mock(return_value=candidate()))
                    checkpoint = minutes.checkpoint_path(root)
                    payload = json.loads(checkpoint.read_text())
                    payload.pop('application_contract')
                    payload.update(schema_version=4, profile_provenance={
                        'schema_version': 1, 'profile_ref': asdict(shipped_previous().ref),
                        'components': {'minutes': 'a'*64}})
                    checkpoint.write_text(json.dumps(payload))
                    before = (checkpoint.read_bytes(), checkpoint.stat().st_mtime_ns)
                    self.assertEqual(len(minutes.load_rows(root)), 1)
                    self.assertTrue(minutes.freshness_issues(root, project))
                    self.assertEqual(before, (checkpoint.read_bytes(), checkpoint.stat().st_mtime_ns))
                    generate = Mock(return_value=candidate())
                    minutes.run_stage(root, project, generate)
                    generate.assert_called_once()
                    self.assertEqual(json.loads(checkpoint.read_text())['schema_version'], 5)
                    generate.reset_mock()
                    minutes.run_stage(root, project, generate)
                    generate.assert_not_called()

    def test_unrelated_profile_revision_reuses_current_rows_without_model_work(self):
        from recordprep.profile_store import ProfileStore
        from recordprep.case_profiles import apply_case_profile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root, project = fixture(base, 1)
            old = shipped_previous()
            store = ProfileStore('recordprep', config_root=base/'profiles', data_root=base/'revisions')
            store.accept_profile(old, expected_previous_digest=None)
            apply_case_profile(root, old.ref, expected_previous=None, store=store)
            with patch('recordprep.case_profiles.profile_store', return_value=store):
                seed_profile_preparation(root, old, project)
                minutes.run_stage(root, project, Mock(return_value=candidate()))
                expected = json.loads(minutes.meta_path(root).read_text())
                for resource in ('minutes', 'naming', 'hearings', 'reports'):
                    editor = ProfileEditor(old)
                    if resource == 'minutes':
                        editor.resources[resource] = CANARY
                    elif resource == 'naming':
                        editor.resources[resource]['reports'][0]['guidance'] += CANARY
                    else:
                        editor.resources[resource][0]['guidance'] += CANARY
                    new = editor.snapshot()
                    store.accept_profile(new, expected_previous_digest=store.read_registry()['heads'][new.ref.specialty_id])
                    store.set_default(new.ref)
                    self.assertEqual(minutes.freshness_issues(root, project), [])
                    generate = Mock()
                    minutes.run_stage(root, project, generate)
                    generate.assert_not_called()
                    self.assertEqual(json.loads(minutes.meta_path(root).read_text()), expected)


if __name__ == '__main__':
    unittest.main()
