"""Current synthetic profile workflow acceptance entry point.

The former sidebar/Focus-shared widget script is retired historical evidence.
Its retained-buffer, guarded Save, Close, Reset and deletion assertions now live
in discoverable production-GTK tests rather than obsolete widget-name checks.
Run this entry point in a disposable RecordPrep checkout/environment.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE/'tests')]
with tempfile.TemporaryDirectory(prefix='profile-workflow-acceptance-') as temporary:
    for key in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','PI_CODING_AGENT_DIR'):
        path = Path(temporary)/key.lower(); path.mkdir(); os.environ[key] = str(path)
    os.environ['PI_RUN_METRICS_ENABLED'] = '0'
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'test_profile_workflows', 'test_profile_reset', 'test_profile_deletion',
        'test_unified_settings', 'test_structured_settings_ui',
    ])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
