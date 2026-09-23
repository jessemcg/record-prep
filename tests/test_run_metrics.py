"""Passive adapter contract; synthetic commands and temporary roots only."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from recordprep import run_metrics

APP = 'recordprep'
WORKFLOWS = ('detect_transcript_layout', 'number_transcript_pages', 'build_participant_index', 'create_case_overview', 'build_source_map', 'recordprep-extract-hearing', 'recordprep-extract-report', 'recordprep-synthesize-hearings', 'recordprep-synthesize-reports')


class RunMetricsTests(unittest.TestCase):
    def test_every_identity_and_failure_mode_leaves_behavior_intact(self):
        source = Path(run_metrics.__file__).resolve().parents[1]
        if not (source.parent / 'PiRunMetrics/launch_adapter.py').is_file():
            self.skipTest('Optional sibling launch policy not present')
        with tempfile.TemporaryDirectory(prefix='metrics app ') as d:
            root = Path(d)
            fake = root / 'fake pi.py'
            fake.write_text('print("0.87.1")\n')
            prefix = [sys.executable, str(fake)]
            collector = root / 'observer.ts'
            collector.write_text('// synthetic\n')
            original = prefix + ['--no-extensions', '--tools', 'read', 'PRIVATE_CANARY']
            base = dict(os.environ, PI_RUN_METRICS_COLLECTOR=str(collector),
                        PI_RUN_METRICS_ROOT=str(root / 'archive'), PI_RUN_METRICS_ENABLED='1',
                        PI_RUN_METRICS_APP='parent', PI_RUN_METRICS_WORKFLOW='parent',
                        PI_RUN_METRICS_REVISION='inherited', PI_RUN_METRICS_DIRTY='invalid')
            for workflow in WORKFLOWS:
                for variant in ('enabled', 'disabled', 'missing', 'invalid', 'unwritable'):
                    env = dict(base)
                    if variant == 'disabled': env['PI_RUN_METRICS_ENABLED'] = '0'
                    if variant == 'missing': env['PI_RUN_METRICS_COLLECTOR'] = str(root / 'missing')
                    if variant == 'invalid': env['PI_RUN_METRICS_ROOT'] = 'relative'
                    if variant == 'unwritable': env['PI_RUN_METRICS_ROOT'] = '/dev/null/runs'
                    with self.subTest(workflow=workflow, variant=variant), contextlib.redirect_stderr(io.StringIO()):
                        argv, child = run_metrics.instrument(original, env, workflow, prefix)
                        if variant in ('enabled', 'unwritable'):
                            self.assertEqual(argv[2:4], ['--extension', str(collector)])
                            self.assertEqual(argv[:2] + argv[4:], original)
                        else:
                            self.assertEqual(argv, original)
                        self.assertEqual(child['PI_RUN_METRICS_APP'], APP)
                        self.assertEqual(child['PI_RUN_METRICS_WORKFLOW'], workflow)
                        self.assertNotEqual(child.get('PI_RUN_METRICS_REVISION'), 'inherited')
                        self.assertNotIn('PRIVATE_CANARY', str({k:v for k,v in child.items() if k.startswith('PI_RUN_METRICS_')}))
            self.assertFalse((root / 'archive').exists())
            with contextlib.redirect_stderr(io.StringIO()):
                argv, child = run_metrics.instrument(original, base, WORKFLOWS[0], prefix, project=root / 'absent')
            self.assertEqual(argv, original)
            self.assertNotIn('PI_RUN_METRICS_APP', child)


if __name__ == '__main__':
    unittest.main()
