"""Instruction consistency and hearing-only presentation; no private data/model calls."""
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import summary_agents as sa, summary_profiles as sp
from test_profile_generation import bundled

PROJECT = Path(__file__).resolve().parents[1] / '.pi'


class HearingEditorialTests(unittest.TestCase):
    def test_shared_and_legacy_runtime_receive_editorial_priorities(self):
        for profile in (None, bundled('general'), bundled('california_dependency')):
            guidance = sa.effective_synthesis_config(PROJECT, 'hearings', profile=profile)['guidance']
            text = ' '.join(guidance.split())
            for phrase in (
                "Respect the reader's time", 'substantive purpose or consequential result',
                'not the date, appearance roll call', 'opening or issue overview orients',
                'different grounds, relief, conditions or reservations',
                'conditional standard directions as unconditional',
                'doubled subjects/verbs', 'actor and duty bearer',
                'never invent a change', 'specific uncertainty briefly',
                "counsel's description of a prior ruling", 'No separate quality pass',
            ):
                self.assertIn(phrase, text)
            self.assertIn(sp.HEARING_QUOTE_CASE_GUIDANCE, guidance)
            self.assertNotIn('Python adds\none normalization notice', guidance)
            extraction = sa.effective_extraction_config(PROJECT, 'hearings', profile=profile)
            self.assertNotIn(sp.HEARING_READABILITY, extraction.guidance)
        skill = (PROJECT / 'skills/recordprep-synthesize-hearings/SKILL.md').read_text()
        self.assertIn('open with the substantive purpose', skill)
        self.assertIn('otherwise briefly attribute', skill)
        self.assertIn('never rewrite a stored quotation', skill)

    def test_preceding_builtin_is_recognized_without_reattaching_old_method(self):
        old = sp.PREVIOUS_HEARING_READABILITY + '\n' + sa.PREVIOUS_HEARING_READABILITY_GUIDANCE
        resolution = sa.resolve_phase_guidance('hearings', 'synthesize', old)
        self.assertEqual(resolution.origin, 'migrated')
        self.assertEqual(resolution.custom_guidance, '')
        self.assertIn(sp.HEARING_READABILITY, resolution.immutable_guidance)
        custom = '  Synthetic personal emphasis.\n\n'
        self.assertEqual(sa.resolve_phase_guidance('hearings', 'synthesize', custom).custom_guidance, custom)

    def test_hearing_core_changes_do_not_change_reports_or_extraction(self):
        profile = bundled('general')
        before = {(kind, phase): sp.compile_summary(profile, kind, phase).component_sha256
                  for kind in ('hearings', 'reports') for phase in ('extract', 'synthesize')}
        with patch.object(sp, 'HEARING_READABILITY', sp.HEARING_READABILITY + '\nSynthetic revision.'):
            after = {(kind, phase): sp.compile_summary(profile, kind, phase).component_sha256
                     for kind in ('hearings', 'reports') for phase in ('extract', 'synthesize')}
        self.assertNotEqual(before['hearings', 'synthesize'], after['hearings', 'synthesize'])
        for key in before.keys() - {('hearings', 'synthesize')}:
            self.assertEqual(before[key], after[key])
        self.assertEqual(sa.summary_renderer_version('reports'), 'recordprep-report-renderer-8')
        self.assertEqual(sa.summary_renderer_version('hearings'), 'recordprep-hearing-renderer-8')
        self.assertNotIn(sp.HEARING_READABILITY, sa.effective_synthesis_config(PROJECT, 'reports')['guidance'])


if __name__ == '__main__':
    unittest.main()
