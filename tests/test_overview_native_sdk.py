"""Offline SDK exercises overview reads/continuations and candidate-only writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class OverviewNativeSDKTests(unittest.TestCase):
    def test_exact_manifest_inputs_are_readable_without_discovery(self):
        sdk = Path(os.environ.get('PI_METRICS_TEST_SDK', '/nonexistent'))
        fixture = PROJECT.parent / 'PiRunMetrics/tests/app_sdk_fixture.mjs'
        node = shutil.which('node')
        if not node or not (sdk / 'dist/index.js').is_file() or not fixture.is_file():
            self.skipTest('Installed offline SDK fixture required')
        for ct_only in (False, True):
            with self.subTest(ct_only=ct_only), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / 'bundle'
                root.mkdir()
                workspace = base / 'workspace'
                workspace.mkdir(mode=0o700)
                reads = []
                for name in ['hearings_sum_Synthetic Case.txt', 'reports_sum_Synthetic Case.txt',
                             'minutes_sum_Synthetic Case.txt', 'transcript_layout.json'] + ([] if ct_only else ['participant_index.json']):
                    p = root / name
                    p.write_text('Synthetic beginning.\nSynthetic continuation.\n')
                    reads.append(str(p))
                skill = workspace / 'SKILL.md'
                skill.write_text((PROJECT / '.pi/resources/profile-overview.md').read_text())
                reads.append(str(skill))
                candidate = workspace / 'overview-candidate.md'
                spec = workspace / 'native-access.json'
                spec.write_text(json.dumps(dict(root=str(root), candidate=str(candidate), reads=reads,
                    source_ranges=[], helper=None, python='/usr/bin/python3', stage='overview')))
                spec.chmod(0o600)
                system = workspace / 'system.txt'
                system.write_text('Synthetic offline overview acceptance.')
                frames = []
                for i, path in enumerate(reads):
                    frames.append(dict(stopReason='toolUse', content=[dict(type='toolCall', id=f'read-{i}',
                        name='read', arguments={'path': path, 'offset': 1, 'limit': 1})]))
                frames.append(dict(stopReason='toolUse', content=[dict(type='toolCall', id='continue',
                    name='read', arguments={'path': reads[0], 'offset': 2, 'limit': 1})]))
                frames.append(dict(stopReason='toolUse', content=[dict(type='toolCall', id='write',
                    name='write', arguments={'path': str(candidate), 'content': 'Synthetic overview candidate.'})]))
                frames.append(dict(stopReason='stop', content=[dict(type='text', text='Finished.')]))
                plan = workspace / 'plan.json'
                plan.write_text(json.dumps({'frames': frames, 'followup': False}))
                capture = workspace / 'capture.json'
                env = os.environ | {'PI_METRICS_TEST_SDK': str(sdk), 'PI_METRICS_TEST_PLAN': str(plan),
                    'PI_METRICS_TEST_CAPTURE': str(capture), 'RECORDPREP_NATIVE_ACCESS_SPEC': str(spec),
                    'PI_RUN_METRICS_ENABLED': '0'}
                for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'TMPDIR'):
                    p = base / key.lower(); p.mkdir(mode=0o700); env[key] = str(p)
                before = {p: p.read_bytes() for p in root.iterdir()}
                result = subprocess.run([node, str(fixture), '--no-extensions', '--no-session',
                    '--extension', str(PROJECT / '.pi/extensions/recordprep-profile-native-tools.ts'),
                    '--tools', 'read,write,edit', '--system-prompt', str(system),
                    'Read these exact paths: ' + json.dumps(reads)], cwd=workspace, env=env,
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                captured = json.loads(capture.read_text())
                self.assertEqual(captured['calls'], len(frames))
                results = [m for m in captured['messages'] if m.get('role') == 'toolResult']
                self.assertTrue(results)
                self.assertFalse(any(m.get('isError') for m in results))
                self.assertIn('Synthetic continuation.', json.dumps(results))
                self.assertEqual(candidate.read_text(), 'Synthetic overview candidate.')
                self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})
