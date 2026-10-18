"""Plain-English minute instructions and label-v2 publication; offline fiction only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import unittest

from recordprep import minute_summaries as minutes, summary_agents as sa
from recordprep.case_profiles import apply_case_profile
from recordprep.profile_store import ProfileStore
from test_minute_summaries import fixture
from test_profile_generation import bundled, changed, seed_profile_preparation


class PlainMinuteTests(unittest.TestCase):
    def test_shared_skill_core_tool_and_both_public_profiles_agree(self):
        with TemporaryDirectory() as td:
            _root, project = fixture(Path(td), 1)
            skill = (project / 'skills' / minutes.SKILL_NAME / 'SKILL.md').read_text()
            tool = (project / 'extensions/recordprep-profile-minute-tools.ts').read_text()
            self.assertIn('Translate procedural terms faithfully', skill)
            self.assertIn('a hearing granted into relief granted', skill)
            self.assertIn('deadline essential', skill)
            self.assertIn('No substantive orders recorded.', skill)
            self.assertIn('There are no leading dashes/bullets', skill)
            for specialty in ('general', 'california_dependency'):
                profile = bundled(specialty)
                config = minutes.stage_config(project, profile=profile)[1]
                self.assertEqual(config['contract_version'], 8)
                self.assertEqual(config['presentation'], 'recordprep-minute-compact-labels-2')
                for text in (skill, minutes.PROFILE_MINUTE_CORE, tool, profile.resource('minutes')):
                    with self.subTest(specialty=specialty, text=text[:60]):
                        self.assertIn('plain English', text)
                        self.assertIn('No substantive orders recorded.', text)
                        self.assertIn('sanction', text)
                        self.assertIn('filing', text)
                self.assertIn('Appearances / Orders / Next', config['guidance'])
                self.assertNotIn('Main rulings', config['guidance'])
                self.assertNotIn('- Appearances:', profile.resource('minutes'))
                self.assertNotIn('juvenile', minutes.PROFILE_MINUTE_CORE.lower())
                self.assertNotIn('parent', minutes.PROFILE_MINUTE_CORE.lower())

    def test_candidate_text_is_not_mechanically_deleted_or_translated(self):
        # Instructions select/translate. Python must not silently censor a real
        # substantive order merely because it contains a filing-related word.
        from test_minute_compact import candidate, item
        data = candidate() | {'orders': 'An actually imposed sanction for improper filing. A substantive deadline remains.'}
        row = minutes.normalize_candidate(data, item(), profile=bundled('general'))
        self.assertEqual(row['orders'], data['orders'])
        self.assertEqual(minutes.render_compact_entry(item(), row)[2], 'Orders: ' + data['orders'])

    def test_contract7_remains_readonly_then_explicit_generation_changes_only_minutes(self):
        for specialty in ('general', 'california_dependency'):
            with self.subTest(specialty=specialty), TemporaryDirectory() as td:
                base = Path(td)
                root, project = fixture(base, 2)
                # An exact preceding public default remains pinned and unchanged.
                prior_text = next(text for text, name in minutes._HISTORICAL_MINUTE_GUIDANCE.items()
                                  if name == specialty and 'into Main rulings.' in text)
                profile = changed(bundled(specialty), 'minutes', prior_text)
                original_files = deepcopy(profile.files)
                store = ProfileStore('recordprep', config_root=base / 'config', data_root=base / 'data')
                store.accept_profile(profile, expected_previous_digest=None)
                apply_case_profile(root, profile.ref, expected_previous=None, store=store)
                sources = [root / f'text_pages/{i:04d}.txt' for i in (1, 2)]
                sources[0].write_text('Application for confidentiality denied without prejudice. Clerk to file status memo.')
                sources[1].write_text('Clerk to file status memo. Review report calendar. Possible sanctions for late filing.')
                def value(current, *, old=False):
                    return {'artifact': 'recordprep-minute-candidate',
                            'hearing': 'Confidentiality motion' if current.ordinal == 1 else 'Administrative review',
                            'appearances': [], 'next_hearing': 'Not stated.',
                            'orders': (('Application denied without prejudice; clerk to file status memo.' if current.ordinal == 1
                                        else 'Clerk to file status memo; possible sanctions for late filing.') if old else
                                       ('The court denied the confidentiality request, but it may be renewed.' if current.ordinal == 1
                                        else 'No substantive orders recorded.'))}
                with patch('recordprep.case_profiles.profile_store', return_value=store):
                    seed_profile_preparation(root, profile, project)
                    settings, config = minutes.stage_config(project, profile=profile)
                    previous = config | {'contract_version': 7, 'presentation': minutes.LEGACY_COMPACT_PRESENTATION}
                    with patch.object(minutes, 'stage_config', return_value=(settings, previous)):
                        minutes.run_stage(root, project, lambda current, *_: value(current, old=True))
                    final = sa.summary_final_path(root, 'minutes')
                    self.assertEqual(final.read_text().count('- Main rulings:'), 2)
                    unrelated = root / 'summaries/reports_sum_Fictional.txt'
                    unrelated.write_text('Unrelated report artifact stays unchanged.\n')
                    stable = [*sources, unrelated, store.registry_path, project.parent / 'config.json',
                              store.data_root / 'snapshots' / profile.ref.content_sha256 / 'minutes.md']
                    protected = [final, minutes.checkpoint_path(root), minutes.meta_path(root), *stable]
                    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}
                    self.assertTrue(minutes.freshness_issues(root, project))
                    self.assertFalse(minutes.stage_complete(root, project))
                    self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                    with self.assertRaisesRegex(RuntimeError, 'fictional failure'):
                        minutes.run_stage(root, project, Mock(side_effect=RuntimeError('fictional failure')))
                    self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected})
                    generate = Mock(side_effect=lambda current, *_: value(current))
                    minutes.run_stage(root, project, generate)
                    self.assertEqual(generate.call_count, 2)
                    text = final.read_text()
                    self.assertIn('Orders: The court denied the confidentiality request, but it may be renewed.', text)
                    self.assertIn('Orders: No substantive orders recorded.', text)
                    self.assertNotIn('status memo', text)
                    self.assertNotIn('Main rulings', text)
                    self.assertNotIn('\n- ', text)
                    self.assertNotIn('**', text)  # Focus styles label spans, not fake quotation links.
                    entries = text.rstrip('\n').split('\n\n')[1:]
                    self.assertEqual(len(entries), 2)  # Exactly one blank line between entries.
                    for entry in entries:
                        lines = entry.splitlines()
                        self.assertEqual(len(lines), 4)  # No blank line inside an entry.
                        self.assertTrue(lines[1].startswith('Appearances: '))
                        self.assertTrue(lines[2].startswith('Orders: '))
                        self.assertTrue(lines[3].startswith('Next: '))
                    self.assertEqual(minutes.freshness_issues(root, project), [])
                    generate.reset_mock()
                    minutes.run_stage(root, project, generate)
                    generate.assert_not_called()
                    self.assertEqual({p: before[p] for p in stable},
                                     {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in stable})
                    self.assertEqual(profile.files, original_files)


if __name__ == '__main__':
    unittest.main()
