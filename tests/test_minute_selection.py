"""Shared minute selection, profile isolation and real runner staging; offline only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from recordprep import minute_summaries as minutes, summary_agents as sa
from recordprep.case_profiles import apply_case_profile
from recordprep.profile_store import ProfileStore
from test_minute_summaries import fixture
from test_pi_resources import _load_runner_module
from test_profile_generation import bundled, changed, seed_profile_preparation


class MinuteSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root, self.project = fixture(self.directory, 1)
        self.skill = self.project / 'skills' / minutes.SKILL_NAME / 'SKILL.md'

    def bind(self, profile):
        store = ProfileStore('recordprep', config_root=self.directory / 'config',
                             data_root=self.directory / 'data')
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        return store

    @staticmethod
    def candidate():
        return {'artifact': 'recordprep-minute-candidate', 'hearing': 'Review hearing',
                'appearances': [], 'positions': '',
                'orders': 'The court continued the hearing; the existing restriction remains.',
                'next_hearing': 'Review: June 3, 9 a.m.'}

    def test_shared_skill_selects_result_without_specialty_or_field_inventory(self):
        text = self.skill.read_text()
        self.assertIn('Select the result, not an inventory', text)
        self.assertIn('not a miniature hearing narrative', text)
        self.assertIn('one or two decisive findings or orders', text)
        self.assertIn('qualification needed to state a selected outcome accurately', text)
        self.assertIn('Fictional examples', text)
        self.assertNotIn("juvenile court's actual orders", text)
        self.assertNotIn("Count a parent as", text)
        for name in ('general', 'california_dependency'):
            profile = bundled(name)
            config = minutes.stage_config(self.project, profile=profile)[1]
            self.assertEqual(config['contract_version'], 8)
            self.assertEqual(config['presentation'], minutes.COMPACT_PRESENTATION)
            self.assertIn('Fields are containers', config['guidance'])
            self.assertIn('profile supplies specialty focus', ' '.join(config['guidance'].split()))
            self.assertIn('Do not supply a separate positions narrative', config['guidance'])
            self.assertIn('MINUTE CONTRACT', config['guidance'])
            self.assertEqual(minutes.minute_profile_text(profile), profile.resource('minutes'))
        self.assertNotIn('juvenile', minutes.PROFILE_MINUTE_CORE.lower())
        self.assertNotIn('parent', minutes.PROFILE_MINUTE_CORE.lower())

    def test_custom_profile_bytes_preserved_but_shared_method_has_priority(self):
        profile = changed(bundled('general'), 'minutes',
                          '  Synthetic specialty focus: contractual relief.\n')
        before = profile.files
        guidance = minutes.profile_guidance(profile)
        self.assertTrue(guidance.endswith(profile.resource('minutes')))
        self.assertIn('specialty focus subordinate to that shared method', guidance)
        self.assertEqual(profile.files, before)
        # Fixed complete-order attendance is not replaced by the legacy parent rule.
        self.assertIn('use explicit evidence from any page', guidance)
        self.assertIn("alone establishes neither a client's presence nor absence", guidance)
        self.assertNotIn('FIRST PAGE only', guidance)

    def test_canonical_skill_is_fingerprinted_in_both_modes_not_removed_alternate(self):
        self.assertFalse((self.project / 'resources/profile-minutes.md').exists())
        for profile in (None, bundled('general')):
            before = minutes.stage_config(self.project, profile=profile)[1]
            relative = f'skills/{minutes.SKILL_NAME}/SKILL.md'
            self.assertIn(relative, before['resources'])
            self.assertNotIn('resources/profile-minutes.md', before['resources'])
            contents = self.skill.read_text()
            self.skill.write_text(contents + '\nSynthetic selection clarification.\n')
            after = minutes.stage_config(self.project, profile=profile)[1]
            self.assertNotEqual(before['resources'][relative], after['resources'][relative])
            self.skill.write_text(contents)

    def test_actual_runner_stages_visible_skill_and_profile_focus_for_both_specialties(self):
        # Fresh stores/cases for each specialty; no provider process or credentials.
        for name in ('general', 'california_dependency'):
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root, project = fixture(base, 1)
                profile = bundled(name)
                store = ProfileStore('recordprep', config_root=base / 'config', data_root=base / 'data')
                store.accept_profile(profile, expected_previous_digest=None)
                apply_case_profile(root, profile.ref, expected_previous=None, store=store)
                runner = _load_runner_module()
                observed = {}

                def child_run(child):
                    staged = child.workspace / '.pi/skills' / minutes.SKILL_NAME / 'SKILL.md'
                    self.assertEqual(staged.read_bytes(), (project / 'skills' / minutes.SKILL_NAME / 'SKILL.md').read_bytes())
                    command = child.command
                    self.assertEqual(command[command.index('--tools') + 1], minutes.TOOLS)
                    self.assertIn(profile.resource('minutes'), command[-1])
                    self.assertIn('Fields are containers', command[-1])
                    self.assertEqual([p.name for p in (child.workspace / '.pi/extensions').iterdir()],
                                     ['recordprep-profile-minute-tools.ts'])
                    spec = json.loads(Path(child.env_overrides['RECORDPREP_MINUTE_WORK_SPEC']).read_text())
                    self.assertIn('FIRST PAGE', spec['source'])
                    Path(spec['candidate_path']).write_text(json.dumps(self.candidate()))
                    observed['workspace'] = child.workspace
                    return 0

                with patch('recordprep.case_profiles.profile_store', return_value=store), \
                        patch.object(runner, '_resolve_pi_command', return_value=['synthetic-pi']), \
                        patch.object(runner, '_check_pi_version'), \
                        patch('recordprep.summary_preflight.pi_runtime.available_pi_models', return_value=[]), \
                        patch.object(runner._SummaryChildRunner, 'run', child_run), \
                        patch.dict('os.environ', {'XDG_CACHE_HOME': str(base / 'cache')}):
                    seed_profile_preparation(root, profile, project)
                    self.assertEqual(runner._run_minute_stage(root, project), 0)
                    self.assertEqual(minutes.freshness_issues(root, project), [])
                    self.assertFalse(observed['workspace'].exists())
                    text = sa.summary_final_path(root, 'minutes').read_text()
                    self.assertIn('existing restriction remains', text)
                    self.assertNotIn('Reported.', text)
                    self.assertEqual(minutes.load_rows(root)[0]['positions'], '')

    def test_changed_method_stales_without_writes_then_explicit_run_reuses_new_rows(self):
        profile = bundled('general')
        store = self.bind(profile)
        with patch('recordprep.case_profiles.profile_store', return_value=store):
            seed_profile_preparation(self.root, profile, self.project)
            # A synthetic former application method, not rewritten private guidance.
            with patch.object(minutes, 'PROFILE_MINUTE_CORE', 'Historical synthetic method'):
                minutes.run_stage(self.root, self.project, Mock(return_value=self.candidate()))
                self.assertTrue(minutes.stage_complete(self.root, self.project))
            # Application-owned constants are loaded at process startup, so a
            # changed-method launch also begins with an empty UI status cache.
            minutes._STATUS_CACHE.clear()
            final = sa.summary_final_path(self.root, 'minutes')
            paths = (final, minutes.checkpoint_path(self.root), minutes.meta_path(self.root))
            before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
            self.assertTrue(minutes.freshness_issues(self.root, self.project))
            self.assertFalse(minutes.stage_complete(self.root, self.project))
            self.assertEqual(len(minutes.load_rows(self.root)), 1)
            self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns) for p in paths], before)
            # Failed explicit regeneration preserves the old readable final/checkpoint.
            with self.assertRaises(RuntimeError):
                minutes.run_stage(self.root, self.project, Mock(side_effect=RuntimeError('offline failure')))
            self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns) for p in paths], before)
            generate = Mock(return_value=self.candidate())
            minutes.run_stage(self.root, self.project, generate)
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(minutes.freshness_issues(self.root, self.project), [])
            generate.reset_mock()
            minutes.run_stage(self.root, self.project, generate)
            generate.assert_not_called()

    def test_renderer_preserves_selected_conditions_and_does_not_enforce_length(self):
        profile = bundled('general')
        item = minutes.build_items(self.root, minutes.stage_config(self.project, profile=profile)[1])[0]
        candidate = self.candidate()
        candidate['orders'] = ' '.join(['A source-supported qualification.'] * 100)
        row = minutes.normalize_candidate(candidate, item, profile=profile)
        paragraph = minutes.render_paragraph(row)
        self.assertIn(candidate['orders'], paragraph)
        self.assertTrue(paragraph.endswith(candidate['next_hearing']))
        self.assertEqual(row['positions'], '')


if __name__ == '__main__':
    unittest.main()
