"""Offline SDK capture at real summary-child launch boundaries; no provider work."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from recordprep import minute_summaries as minutes, summary_agents as sa, summary_prompts
from recordprep.prompt_inspection import SUMMARY_TASKS, TOOLS, inspect_prompt, tool_audit
from test_minute_summaries import fixture, candidate
from test_pi_resources import _load_runner_module
from test_structured_classification import ROOT, bundle


class CapturedLaunch(Exception):
    pass


class SummarySkillDeliveryTests(unittest.TestCase):
    def sdk_capture(self, plan, base):
        if not shutil.which('node'):
            self.skipTest('Node unavailable')
        base.mkdir()
        spec = base / 'plan.json'
        spec.write_text(json.dumps(plan))
        capture = base / 'capture.json'
        env = os.environ.copy()
        for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TMPDIR'):
            path = base / key
            path.mkdir(mode=0o700)
            env[key] = str(path)
        for key in ('RECORDPREP_SUMMARY_WORK_SPEC', 'RECORDPREP_SUMMARY_DATASET', 'RECORDPREP_MINUTE_WORK_SPEC'):
            env.pop(key, None)
        result = subprocess.run(['node', str(ROOT / 'tests/offline_prompt_sdk.mjs'), str(spec), str(capture)],
                                cwd=base, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(capture.read_bytes())

    def test_actual_production_launches_expand_complete_skills_in_both_modes(self):
        for profile in (None, bundle()):
            for task, _label in SUMMARY_TASKS:
                with self.subTest(profile=profile is not None, task=task), tempfile.TemporaryDirectory() as temporary:
                    base = Path(temporary)
                    root, project = fixture(base, 1)
                    runner = _load_runner_module()
                    workspaces = base / 'workspaces'
                    workspaces.mkdir()
                    observed = []
                    item = NS(item_id='synthetic:0001', ordinal=1, label='Synthetic', start_page=1, end_page=1,
                              source='Synthetic source only.')
                    phase = 'minutes' if task == 'minutes' else task.split('-')[1]
                    kind = 'minutes' if phase == 'minutes' else task.split('-')[0]

                    def capture_child(child):
                        command = child.command
                        staged = Path(command[command.index('--skill') + 1])
                        plan = {'system': Path(command[command.index('--system-prompt') + 1]).read_text(),
                                'skill': str(staged), 'extension': command[command.index('--extension') + 1],
                                'tools': command[command.index('--tools') + 1].split(','), 'launch': command[-1]}
                        skill_name = staged.parent.name
                        self.assertTrue(plan['launch'].startswith('/skill:' + skill_name + ' '))
                        self.assertEqual(set(plan['tools']), set(TOOLS[phase]))
                        if profile is not None:
                            resources = {k: profile.resource(k) for k in profile.manifest['resources']}
                            view = inspect_prompt(resources, task, ROOT / '.pi', template=False, snapshot=profile)
                            self.assertEqual(view.issues, ())
                            self.assertEqual(staged.read_text(), view.components[1][1])
                            self.assertEqual(plan['launch'].split('\n', 1)[0], view.components[2][1].split('\n', 1)[0])
                        else:
                            self.assertEqual(staged.read_bytes(), (project / 'skills' / skill_name / 'SKILL.md').read_bytes())
                        context = self.sdk_capture(plan, base / 'sdk')
                        user = next(m for m in context['messages'] if m['role'] == 'user')
                        message = user['content'] if isinstance(user['content'], str) else user['content'][0]['text']
                        self.assertTrue(message.startswith('<skill name="' + skill_name + '"'))
                        observed.append(child.workspace)
                        # No synthetic candidate is published; the runner must clean staging.
                        raise CapturedLaunch()

                    with patch.object(runner._SummaryChildRunner, 'run', capture_child):
                        with self.assertRaises(CapturedLaunch):
                            if phase == 'extract':
                                config = sa.effective_extraction_config(project, kind, profile=profile)
                                with patch.object(sa, 'build_work_spec', return_value={'source': item.source}):
                                    runner._run_extraction_child(root, project, ['synthetic-pi'], item, config, {}, workspaces, base / 'candidate.json')
                            elif phase == 'synthesize':
                                config = sa.effective_synthesis_config(project, kind, profile=profile)
                                runner._run_synthesis_child(root, project, ['synthetic-pi'], [], config, {}, kind, workspaces, base / 'candidate.json')
                            else:
                                settings, config = minutes.stage_config(project, profile=profile)
                                def generate_once(_root, _project, generate, **_kwargs):
                                    generate(item, settings, config)
                                with patch.object(minutes, 'run_stage', side_effect=generate_once), \
                                        patch.object(runner, '_resolve_pi_command', return_value=['synthetic-pi']), \
                                        patch.object(runner, '_check_pi_version'), \
                                        patch('recordprep.summary_preflight.pi_runtime.available_pi_models', return_value=[]), \
                                        patch.dict(os.environ, {'XDG_CACHE_HOME': str(base / 'cache')}):
                                    runner._run_minute_stage(root, project)
                    self.assertEqual(len(observed), 1)
                    self.assertFalse(observed[0].exists())

    def test_prior_newline_command_reproduces_the_failure_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            skill = ROOT / '.pi/skills/recordprep-extract-hearing/SKILL.md'
            launch = '/skill:recordprep-extract-hearing\nRun the loaded extraction skill now.'
            context = self.sdk_capture({'system': 'Synthetic system.', 'skill': str(skill),
                'extension': str(ROOT / '.pi/extensions/recordprep-summary-tools.ts'),
                'tools': list(TOOLS['extract']), 'launch': launch, 'expectExpanded': False}, base / 'sdk')
            user = next(m for m in context['messages'] if m['role'] == 'user')
            text = user['content'] if isinstance(user['content'], str) else user['content'][0]['text']
            self.assertEqual(text, launch)
            self.assertNotIn('<skill name=', text)

    def test_delivery_identity_changes_every_summary_mode_not_profile_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            _root, project = fixture(Path(temporary), 1)
            for profile in (None, bundle()):
                for kind in ('hearings', 'reports'):
                    extraction = sa.effective_extraction_config(project, kind, profile=profile)
                    synthesis = sa.effective_synthesis_config(project, kind, profile=profile)
                    payload = extraction.fingerprint_payload()
                    self.assertEqual(payload['skill_delivery'], summary_prompts.SKILL_DELIVERY_CONTRACT)
                    old = copy.deepcopy(payload)
                    old.pop('skill_delivery')
                    self.assertNotEqual(sa.sha256_json(old), extraction.fingerprint)
                    self.assertEqual(synthesis['skill_delivery'], summary_prompts.SKILL_DELIVERY_CONTRACT)
                    old = copy.deepcopy(synthesis)
                    old.pop('skill_delivery')
                    self.assertNotEqual(sa.sha256_json(old), sa.sha256_json(synthesis))
                config = minutes.stage_config(project, profile=profile)[1]
                old = copy.deepcopy(config)
                old.pop('skill_delivery')
                self.assertNotEqual(sa.sha256_json(old), sa.sha256_json(config))

    def test_enabled_unassigned_extraction_skill_bytes_are_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temporary:
            _root, project = fixture(Path(temporary), 1)
            for kind, skill in (('hearings', 'recordprep-extract-hearing'), ('reports', 'recordprep-extract-report')):
                before = sa.effective_extraction_config(project, kind)
                path = project / 'skills' / skill / 'SKILL.md'
                path.write_text(path.read_text() + '\nSynthetic instruction change.\n')
                after = sa.effective_extraction_config(project, kind)
                self.assertNotEqual(before.runtime_contract_sha256, after.runtime_contract_sha256)
                self.assertNotEqual(before.fingerprint, after.fingerprint)

    def test_old_minute_checkpoint_is_readable_but_not_reused_as_fixed_delivery(self):
        with tempfile.TemporaryDirectory() as temporary, patch('recordprep.case_profiles.resolve_case_profile', return_value=None):
            root, project = fixture(Path(temporary), 1)
            settings, current = minutes.stage_config(project)
            previous = copy.deepcopy(current)
            previous.pop('skill_delivery')
            with patch.object(minutes, 'stage_config', return_value=(settings, previous)):
                minutes.run_stage(root, project, Mock(return_value=candidate()))
            watched = [minutes.checkpoint_path(root), minutes.meta_path(root), sa.summary_final_path(root, 'minutes')]
            original = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched}
            self.assertTrue(minutes.load_rows(root))
            self.assertTrue(minutes.freshness_issues(root, project))
            self.assertEqual(original, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched})
            failed = Mock(side_effect=RuntimeError('Synthetic failure'))
            with self.assertRaises(RuntimeError):
                minutes.run_stage(root, project, failed)
            failed.assert_called_once()
            self.assertEqual(original, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in watched})
            generate = Mock(return_value=candidate())
            minutes.run_stage(root, project, generate)
            generate.assert_called_once()
            generate.reset_mock()
            minutes.run_stage(root, project, generate)
            generate.assert_not_called()

    def test_missing_delivery_audit_is_reported_not_silently_verified(self):
        manifest = json.loads((ROOT / 'recordprep/resources/prompt-tools.json').read_bytes())
        manifest.pop('skill_command_audit')
        cases = [manifest] + [manifest | {'skill_command_audit': value}
                              for value in (None, True, {}, {'expands': True}, {'expands': 'true'})]
        for value in cases:
            with self.subTest(audit=value.get('skill_command_audit')), \
                    patch('recordprep.prompt_inspection.json.loads', return_value=value):
                self.assertTrue(any('not verify Pi skill expansion' in issue for issue in tool_audit(ROOT / '.pi', 'extract')[1]))
