"""Installed offline SDK: real native tool, Python helper and bounded model loop."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_participant_stage import _build_record_fixture, _review_general_hearing

PROJECT = Path(__file__).resolve().parents[1]


class ParticipantNativeSDKTests(unittest.TestCase):
    def test_full_success_and_two_failures_settle_without_another_model_request(self):
        node = shutil.which('node')
        sdk = Path(os.environ.get('PI_METRICS_TEST_SDK', '/nonexistent'))
        fixture = PROJECT.parent / 'PiRunMetrics/tests/app_sdk_fixture.mjs'
        if not node or not (sdk / 'dist/index.js').is_file() or not fixture.is_file():
            self.skipTest('Installed offline SDK fixture required; never provision in tests')
        helper = PROJECT / '.pi/skills/recordprep-build-participant-index/scripts/participant_index.py'
        spec = importlib.util.spec_from_file_location('sdk_participant_helper', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for scenario in ('full', 'partial_complete', 'failure', 'no_progress'):
            failure = scenario in ('failure', 'no_progress')
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = _build_record_fixture(temporary, hearings=1)
                published = module.prepare(root)
                original = published.read_bytes()
                payload = json.loads(original)
                if scenario != 'no_progress':
                    payload['hearings'] = [_review_general_hearing(payload['hearings'][0], 1)]
                    if scenario == 'failure':
                        payload['hearings'][0]['end_page'] = 0
                    else:
                        payload['hearings'][0]['counsel'][0].pop('speaking_status')
                workspace = base / 'workspace'
                workspace.mkdir(mode=0o700)
                candidate = workspace / 'candidate.json'
                candidate.write_text(json.dumps(payload))
                skill = workspace / 'SKILL.md'
                skill.write_text((PROJECT / '.pi/resources/profile-participants.md').read_text())
                access = workspace / 'access.json'
                access.write_text(json.dumps(dict(root=str(root), candidate=str(candidate), reads=[str(skill)],
                                                 source_ranges=[[1, 8]], helper=str(helper),
                                                 python=sys.executable, stage='participants')))
                access.chmod(0o600)
                system = workspace / 'system.txt'
                system.write_text('Synthetic participant validation test.')
                plan = workspace / 'plan.json'
                frames = [dict(stopReason='toolUse', content=[dict(type='toolCall', id=f'validation-{i}',
                          name='recordprep_validate_candidate', arguments={'partial': scenario in ('partial_complete', 'no_progress')})])
                          for i in range(2 if failure else 1)]
                frames.insert(0, dict(stopReason='toolUse', content=[dict(type='toolCall', id='read-skill',
                    name='read', arguments={'path': str(skill)})]))
                plan.write_text(json.dumps({'frames': frames, 'followup': False}))
                capture = workspace / 'capture.json'
                env = os.environ | {'PI_METRICS_TEST_SDK': str(sdk), 'PI_METRICS_TEST_PLAN': str(plan),
                      'PI_METRICS_TEST_CAPTURE': str(capture), 'RECORDPREP_NATIVE_ACCESS_SPEC': str(access),
                      'RECORDPREP_APPLICATION_ROOT': str(PROJECT), 'RECORDPREP_PARTICIPANT_CANDIDATE': str(candidate),
                      'PI_RUN_METRICS_ENABLED': '0'}
                for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TMPDIR'):
                    path = base / key.lower()
                    path.mkdir(mode=0o700)
                    env[key] = str(path)
                result = subprocess.run([node, str(fixture), '--no-extensions', '--no-session',
                    '--extension', str(PROJECT / '.pi/extensions/recordprep-profile-native-tools.ts'),
                    '--tools', 'read,recordprep_validate_candidate', '--system-prompt', str(system),
                    'Validate the synthetic participant candidate.'],
                    cwd=workspace, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                captured = json.loads(capture.read_text())
                self.assertEqual(captured['calls'], 3 if failure else 2)
                self.assertIn('## Schema 4 entries', json.dumps(captured['messages']))
                self.assertEqual(captured['settled'], 1)
                self.assertEqual(published.read_bytes(), original)
                self.assertEqual((workspace / 'participant-validation-failed').exists(), failure)
                if scenario == 'failure':
                    self.assertIn('invalid page range', json.dumps(captured['messages']))
                elif scenario == 'no_progress':
                    self.assertIn('no hearing-review progress', json.dumps(captured['messages']))
                else:
                    repaired = json.loads(candidate.read_text())
                    self.assertEqual(repaired['hearings'][0]['counsel'][0]['speaking_status'], 'unknown')
