"""Real GTK badges and Resume over synthetic historical files; no model calls."""
import os
from pathlib import Path
import sys
import tempfile

TEMP = tempfile.TemporaryDirectory(prefix='recordprep-presence-ui-')
ROOT = Path(TEMP.name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'RECORDPREP_CONFIG_DIR'):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.pop('RECORDPREP_PROFILE_DIR', None)

from gi.repository import GLib
from unittest.mock import Mock
from recordprep.ui.main_window import RecordPrepApp
from test_output_presence import OUTPUTS, seed_outputs

app = RecordPrepApp()
app.set_application_id('org.synthetic.RecordPrepOutputPresence')
errors = []


def check():
    try:
        window = app.get_active_window()
        window.set_title('Synthetic completed-output badges')
        root = ROOT / 'bundle'
        root.mkdir()
        seed_outputs(root)
        window._resolve_case_root = lambda: root
        window._resume_is_available = lambda: False  # Exercise Resume explicitly below.
        window._step_artifact_complete = Mock(side_effect=AssertionError('Do not validate freshness for badges'))
        window._refresh_step_statuses_from_artifacts()
        assert all(window._step_status_values[step] == 'Done' for step in OUTPUTS)
        window._step_artifact_complete.assert_not_called()
        path = root / 'summaries/reports_sum_Synthetic.txt'
        path.unlink()
        window._refresh_step_statuses_from_artifacts()
        assert window._step_status_values['create_report_summaries'] == 'Pending'
        assert all(window._step_status_values[step] == 'Done' for step in OUTPUTS if step != 'create_report_summaries')
        path.touch()
        window._refresh_step_statuses_from_artifacts()
        assert all(window._step_status_values[step] == 'Done' for step in OUTPUTS)
        # The actual Resume selector/worker uses existing outputs, not historical
        # settings. Only Create files keeps its separate source-preservation gate.
        window.selected_pdfs = []
        window._bundle_reset_required = False
        def source_only(step_id, *_args):
            if step_id != 'create_files':
                raise AssertionError('Resume must not check historical stage freshness')
            return True
        window._step_artifact_complete = Mock(side_effect=source_only)
        assert window._resume_start_index(root, None) is None
        original_steps = window._pipeline_steps()
        calls = []
        window._pipeline_steps = lambda: [(step, row, lambda s=step: calls.append(s) or True)
                                          for step, row, _handler in original_steps]
        path.unlink()
        assert window._resume_start_index(root, None) == [step for step, *_ in original_steps].index('create_report_summaries')
        window._run_steps_from_index(0, root, 'create_report_summaries', skip_completed_steps=True)
        assert calls == ['create_report_summaries'], calls
        path.touch()
        window._refresh_step_statuses_from_artifacts()
        print('OUTPUT-PRESENCE/RESUME GTK ACCEPTANCE PASSED: all 21 complete; only missing report stage dispatched', flush=True)
        if os.environ.get('PRESENCE_ACCEPT_HOLD'):
            GLib.timeout_add_seconds(30, lambda: (app.quit(), False)[1])
        else:
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False

app.connect('activate', lambda *_: GLib.idle_add(check))
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
