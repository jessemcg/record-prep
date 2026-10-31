"""Real native/caption launch -> installed SDK, entirely synthetic and offline."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from recordprep import case_name_stage as caption, native_freshness as freshness
from recordprep import summary_agents as sa, summary_prompts
from recordprep.skill_commands import SKILL_DELIVERY_CONTRACT, skill_launch
from recordprep.case_profiles import apply_case_profile
from recordprep.profile_store import ProfileStore
from recordprep.transcript_layout import apply_manual_override
from test_participant_stage import _build_record_fixture
from test_pi_resources import _load_runner_module
from test_profile_generation import bundled, seed_profile_preparation

PROJECT = Path(__file__).resolve().parents[1]


class CapturedSpawn(Exception):
    pass


def frame(tool, path, content=None):
    args = {'path': str(path)}
    if content is not None:
        args['content'] = content
    return {'stopReason': 'toolUse', 'content': [{'type': 'toolCall', 'id': tool + str(path), 'name': tool, 'arguments': args}]}


class NativeSkillDeliveryTests(unittest.TestCase):
    def capture(self, plan, base, env, real_popen):
        if not shutil.which('node'):
            self.skipTest('Installed Node/SDK required; never provision in tests')
        base.mkdir()
        spec = base / 'plan.json'
        spec.write_text(json.dumps(plan))
        output = base / 'capture.json'
        env = env.copy()
        for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TMPDIR'):
            path = base / key
            path.mkdir(mode=0o700)
            env[key] = str(path)
        # The production Popen interception must not intercept the offline Node child.
        with patch.object(subprocess, 'Popen', real_popen):
            result = subprocess.run([shutil.which('node'), str(PROJECT / 'tests/offline_prompt_sdk.mjs'), str(spec), str(output)],
                                    cwd=base, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(output.read_bytes())

    def test_all_actual_native_launches_expand_and_keep_tool_boundaries(self):
        canonical = [('infer_case', None), ('detect_transcript_layout', None), ('number_transcript_pages', None),
                     ('build_participant_index', None), ('create_case_overview', None), ('build_source_map', None)]
        variants = canonical + [('build_participant_index', 'rt_only'), ('create_case_overview', 'rt_only'),
                                ('create_case_overview', 'ct_only'), ('infer_case', 'caption-profile')]
        for step, mode in variants:
            with self.subTest(step=step, mode=mode), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project = base / 'project/.pi'
                shutil.copytree(PROJECT / '.pi', project)
                (project / 'settings.json').write_text(json.dumps({'defaultProvider': 'synthetic', 'defaultModel': 'synthetic', 'defaultThinkingLevel': 'low'}))
                root = _build_record_fixture(str(base), hearings=1)
                (root / 'case_name.txt').write_text('Prior_Synthetic_Name')
                unrelated = root / 'unrelated_synthetic.txt'
                unrelated.write_text('Existing synthetic file outside every access spec.')
                runner = _load_runner_module()
                store = ProfileStore('recordprep', config_root=base / 'config', data_root=base / 'data')
                profile = bundled('general') if mode else None
                if profile is not None:
                    store.accept_profile(profile, expected_previous_digest=None)
                    apply_case_profile(root, profile.ref, expected_previous=None, store=store)
                if mode in ('rt_only', 'ct_only'):
                    payload = json.loads((root / 'artifacts/transcript_page_numbers.json').read_text())
                    payload['entries'] = [e for e in payload['entries'] if e['record_type'] == 'RT']
                    (root / 'artifacts/transcript_page_numbers.json').write_text(json.dumps(payload))
                    (root / 'artifacts/transcript_page_number_series.md').write_text('# Synthetic RT series\nRT 1–8\n')
                    apply_manual_override(root, mode=mode)
                if step == 'create_case_overview':
                    for kind in ('hearings', 'reports', 'minutes'):
                        p = sa.summary_final_path(root, kind)
                        p.parent.mkdir(exist_ok=True)
                        p.write_text('Synthetic summary for ' + kind + '.\n')
                    (root / 'artifacts/participant_index.json').write_text('{}')
                real_popen = subprocess.Popen
                observed = []

                def child(command, *, cwd, env, **_kwargs):
                    workspace = Path(cwd)
                    skill = Path(command[command.index('--skill') + 1])
                    launch = command[-1]
                    self.assertTrue(launch.startswith('/skill:' + skill.parent.name + ' '))
                    self.assertEqual(json.loads((workspace / '.pi/settings.json').read_text())['enableSkillCommands'], True)
                    extensions = [command[i + 1] for i, value in enumerate(command) if value == '--extension']
                    tools = command[command.index('--tools') + 1].split(',')
                    self.assertIn(str(workspace / '.pi/extensions/recordprep-auto-exit.ts'), extensions)
                    if step == 'infer_case':
                        self.assertEqual(tools, ['read', 'write', 'edit'])
                        self.assertEqual(skill.read_bytes(), (project / 'skills' / skill.parent.name / 'SKILL.md').read_bytes())
                        spec = json.loads(Path(env['RECORDPREP_CASE_NAME_ACCESS_SPEC']).read_text())
                        self.assertEqual(len(spec['reads']), 3)
                        self.assertTrue(all(Path(p).parent == workspace for p in spec['reads']))
                        self.assertIn(caption.CASE_NAME_PROMPT, launch)
                        allowed = Path(spec['reads'][0])
                        private = Path(spec['candidate'])
                    elif mode:
                        native = 'participants' if step == 'build_participant_index' else 'overview'
                        self.assertEqual(skill.read_bytes(), (project / f'resources/profile-{native}.md').read_bytes())
                        self.assertEqual(tools, ['read', 'write', 'edit'] + (['recordprep_validate_candidate'] if native == 'participants' else []))
                        spec = json.loads(Path(env['RECORDPREP_NATIVE_ACCESS_SPEC']).read_text())
                        self.assertIn(str(skill), spec['reads'])
                        self.assertNotIn(str(skill.parent), spec['reads'])
                        if native == 'overview':
                            self.assertIn('APPLICATION INPUT MANIFEST', launch)
                            participant_path = str(root / 'artifacts/participant_index.json')
                            self.assertEqual(participant_path in spec['reads'], mode != 'ct_only')
                            self.assertEqual(participant_path in launch, mode != 'ct_only')
                        allowed = Path(spec['reads'][0])
                        private = Path(spec['candidate'])
                    else:
                        self.assertEqual(tools, runner.STAGES[step].tools.split(','))
                        self.assertEqual(skill.read_bytes(), (project / 'skills' / skill.parent.name / 'SKILL.md').read_bytes())
                    plan = {'system': Path(command[command.index('--system-prompt') + 1]).read_text(),
                            'skill': str(skill), 'extensions': extensions, 'tools': tools, 'launch': launch,
                            'bindExtensions': True}
                    # Execute real SDK read/write tools under the actual caption/native guard.
                    if step == 'infer_case' or mode:
                        blocked = root / 'case_name.txt'
                        before = blocked.read_bytes()
                        plan['frames'] = [frame('read', allowed), frame('read', unrelated),
                                          frame('write', blocked, 'MUST NOT PUBLISH'),
                                          frame('write', private, 'Synthetic private candidate.')]
                    context = self.capture(plan, base / 'sdk', env, real_popen)
                    if mode is None and step in ('infer_case', 'detect_transcript_layout'):
                        negative = {key: value for key, value in plan.items() if key != 'frames'}
                        negative['launch'] = launch.replace(' ', '\n', 1)
                        negative['expectExpanded'] = False
                        self.capture(negative, base / 'sdk-old-newline', env, real_popen)
                    if step == 'infer_case' or mode:
                        results = context['tool_results']
                        self.assertEqual([bool(r.get('isError')) for r in results], [False, True, True, False])
                        self.assertEqual(blocked.read_bytes(), before)
                        self.assertEqual(private.read_text(), 'Synthetic private candidate.')
                    observed.append(workspace)
                    raise CapturedSpawn()

                with patch('recordprep.case_profiles.profile_store', return_value=store), \
                        patch('recordprep.case_profiles.resolve_case_profile', return_value=profile), \
                        patch('recordprep.pi_bundle.case_overview_prerequisite_issues', return_value=[]), \
                        patch('recordprep.pi_bundle.source_map_prerequisite_issues', return_value=[]), \
                        patch.object(runner, '_pi_command', return_value=['/usr/bin/true']), \
                        patch.object(runner, '_resolve_pi_command', return_value=['/usr/bin/true']), \
                        patch.object(runner, '_check_pi_version'), \
                        patch('recordprep.run_metrics.instrument', side_effect=lambda command, env, *args: (command, env)), \
                        patch.object(runner.sys.stdin, 'isatty', return_value=False), \
                        patch.dict(os.environ, {'XDG_CACHE_HOME': str(base / 'cache')}):
                    if mode in ('rt_only', 'ct_only'):
                        seed_profile_preparation(root, profile, project)
                    before = {p: p.read_bytes() for p in (root / 'text_pages').glob('*.txt')}
                    before[root / 'case_name.txt'] = (root / 'case_name.txt').read_bytes()
                    before[unrelated] = unrelated.read_bytes()
                    with patch.object(runner.subprocess, 'Popen', side_effect=child), self.assertRaises(CapturedSpawn):
                        runner._run_stage(runner.STAGES[step], root, project)
                    self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertEqual(len(observed), 1)
                self.assertFalse(observed[0].exists())

    def test_caption_old_delivery_metadata_is_not_current_and_is_not_rewritten(self):
        from test_case_name_stage import CaseNameStageTests
        fixture = CaseNameStageTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        guard, ref, candidate, _spec, _prompt = fixture.prepared()
        caption.publish(fixture.root, fixture.project, guard, ref, candidate)
        self.assertTrue(caption.is_current(fixture.root, fixture.project))
        metadata = fixture.root / caption.METADATA
        payload = json.loads(metadata.read_text())
        payload['inputs'].pop('skill_delivery')
        payload['inputs'].pop('skill_launch_sha256')
        metadata.write_text(json.dumps(payload))
        paths = (metadata, fixture.root / 'case_name.txt')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        self.assertFalse(caption.is_current(fixture.root, fixture.project))
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths})

    def test_shared_helper_changes_invalidate_native_stage_code(self):
        original = sa._resource_sha256
        before = {stage: freshness.stage_code_digest(PROJECT / '.pi', stage) for stage in freshness.STEPS}
        with patch.object(sa, '_resource_sha256', side_effect=lambda p: 'changed' if Path(p).name == 'skill_commands.py' else original(p)):
            after = {stage: freshness.stage_code_digest(PROJECT / '.pi', stage) for stage in freshness.STEPS}
        for stage in before:
            self.assertNotEqual(before[stage], after[stage])

    def test_summary_launch_api_and_identity_are_preserved(self):
        self.assertIs(summary_prompts.skill_launch, skill_launch)
        self.assertEqual(summary_prompts.SKILL_DELIVERY_CONTRACT, SKILL_DELIVERY_CONTRACT)
        literal = 'Literal α {"x": 1} {{quote:source}}\n\nKeep this return.'
        self.assertEqual(skill_launch('synthetic', literal), '/skill:synthetic ' + literal)

    def test_no_production_launch_reconstructs_a_newline_skill_command(self):
        # One code-owned builder for every actual /skill invocation.
        for directory in (PROJECT / 'recordprep', PROJECT / '.pi/scripts'):
            for path in directory.rglob('*.py'):
                text = path.read_text()
                if path.name != 'skill_commands.py':
                    self.assertNotIn('/skill:{', text, str(path))
