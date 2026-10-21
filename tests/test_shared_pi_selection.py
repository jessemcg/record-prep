"""One shared PI selection, using only synthetic files and offline children."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from recordprep import minute_summaries as minutes, pi_runtime as pi, summary_agents as sa
from recordprep import summary_preflight as sp
from recordprep.paths import pi_settings_path
from test_pi_resources import _load_runner_module, PI_DIR


class SharedPiSelectionTests(unittest.TestCase):
    def test_retired_keys_identity_fingerprints_and_staged_children(self):
        runner = _load_runner_module()
        for external in (False, True):
            with self.subTest(external=external), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                project = base / 'source/.pi'
                shutil.copytree(PI_DIR, project)
                selected = base / 'external' if external else project.parent
                selected.mkdir(exist_ok=True)
                prefs = selected / 'pi/settings.json' if external else project / 'settings.json'
                prefs.parent.mkdir(exist_ok=True)
                shared = {'defaultProvider': 'synthetic', 'defaultModel': 'accounts/models/shared',
                          'defaultThinkingLevel': 'high'}
                prefs.write_text(json.dumps(shared))
                guidance = '  Personal guidance.\t\n\n'
                raw = {'summarize_minutes_prompt': guidance}
                for phase in ('extract', 'synthesize'):
                    for kind in ('hearings', 'reports'):
                        raw[f'summarize_{kind}_{"prompt" if phase == "extract" else "synthesis_prompt"}'] = guidance
                    for scope in ('', 'hearings_', 'reports_'):
                        for field in ('provider', 'model', 'thinking'):
                            raw[f'summary_{phase}_{scope}pi_{field}'] = 'RETIRED'
                config = selected / 'config.json'
                config.write_text(json.dumps(raw))
                environment = {'RECORDPREP_CONFIG_DIR': str(selected)} if external else {}
                with patch.dict(os.environ, environment):
                    if not external:
                        os.environ.pop('RECORDPREP_CONFIG_DIR', None)
                    def effective():
                        return ([sa.effective_extraction_config(project, k) for k in ('hearings', 'reports')],
                                [sa.effective_synthesis_config(project, k) for k in ('hearings', 'reports')],
                                minutes.stage_config(project)[1])
                    before = effective()
                    self.assertEqual(before[2]['additional_guidance'], guidance)
                    cases = [(kind, phase, f'recordprep-{phase if phase == "synthesize" else "extract"}-{kind if phase == "synthesize" else kind[:-1]}')
                             for kind in ('hearings', 'reports') for phase in ('extract', 'synthesize')]
                    cases.append(('minutes', 'synthesize', minutes.SKILL_NAME))
                    for kind, phase, skill in cases:
                        settings = minutes.stage_config(project)[0] if kind == 'minutes' else runner._summary_stage_settings(project, kind)
                        if kind != 'minutes':
                            self.assertEqual(settings[phase + '_prompt'], guidance)
                        capacity = sp.resolve_stage_capacity(settings, phase, pi_settings_path(project), models=[
                            pi.PiModel(provider='synthetic', model_id='accounts/models/shared', name='Shared', context_window=1000000)])
                        self.assertTrue(capacity.known)
                        self.assertEqual((capacity.identity.provider, capacity.identity.model_id, capacity.identity.thinking),
                                         ('synthetic', 'accounts/models/shared', 'high'))
                        workspace, staged, staged_skill = runner._staged_workspace(project, skill, base)
                        try:
                            self.assertEqual(json.loads((staged / 'settings.json').read_text()), dict(shared, enableSkillCommands=True))
                            command = runner._base_child_command(['fake-pi'], staged, staged_skill, 'fake-tools', 'synthetic', settings, phase)
                            for flag in ('--provider', '--model', '--thinking'):
                                self.assertNotIn(flag, command)
                            self.assertNotIn('RETIRED', str(command))
                        finally:
                            shutil.rmtree(workspace)
                    # Same identity as the former explicit override: no artificial config/hash change.
                    for kind in ('hearings', 'reports'):
                        old = sa.summary_stage_settings(project, kind) | {
                            f'{phase}_{field}': shared[key] for phase in ('extract', 'synthesize')
                            for field, key in [('provider', 'defaultProvider'), ('model', 'defaultModel'), ('thinking', 'defaultThinkingLevel')]}
                        current_extract = sa.effective_extraction_config(project, kind)
                        current_synthesis = sa.effective_synthesis_config(project, kind)
                        with patch.object(sa, 'summary_stage_settings', return_value=old):
                            self.assertEqual(current_extract, sa.effective_extraction_config(project, kind))
                            self.assertEqual(current_synthesis, sa.effective_synthesis_config(project, kind))
                    config.write_text(json.dumps({k: 'OTHER RETIRED' if k.startswith('summary_') else v for k, v in raw.items()}))
                    self.assertEqual(before, effective())
                    for field, value in [('defaultModel', 'accounts/models/changed'), ('defaultThinkingLevel', 'low')]:
                        prefs.write_text(json.dumps(shared | {field: value}))
                        after = effective()
                        for old_group, new_group in zip(before[:2], after[:2]):
                            for old, new in zip(old_group, new_group):
                                self.assertNotEqual(old, new)
                        self.assertNotEqual(before[2], after[2])
                    # Removing retired keys has no fingerprint effect either.
                    prefs.write_text(json.dumps(shared))
                    config.write_text(json.dumps({k: v for k, v in raw.items() if not k.startswith('summary_')}))
                    self.assertEqual(before, effective())

    def test_legacy_guidance_save_preserves_retired_values(self):
        from recordprep.ui import main_window as ui
        raw = {'summary_extract_hearings_pi_model': '  old/kind  ',
               'summary_synthesize_pi_thinking': 'medium', 'unrelated': [1, 2]}
        with patch.object(ui, '_read_config', return_value=raw.copy()), patch.object(ui, '_write_config') as write:
            ui.save_summarize_settings(api_url='', model_id='', api_key='', disable_reasoning=False,
                minutes_target_chars='1', minutes_max_pages='1', hearings_prompt='  custom\n',
                reports_prompt='', minutes_prompt=' custom minutes\n', extract_model='ignored')
        saved = write.call_args.args[0]
        for key, value in raw.items():
            self.assertEqual(saved[key], value)
        self.assertNotIn('summary_extract_pi_model', saved)
        self.assertEqual(saved['summarize_hearings_prompt'], '  custom\n')
        self.assertEqual(saved['summarize_minutes_prompt'], ' custom minutes\n')
