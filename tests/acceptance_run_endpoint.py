"""Real Run through dropdown + Run from here; synthetic handlers, no model calls."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock, patch

TEMP = tempfile.TemporaryDirectory(prefix='recordprep-run-endpoint-')
ROOT = Path(TEMP.name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'RECORDPREP_CONFIG_DIR'):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.pop('RECORDPREP_PROFILE_DIR', None)

from gi.repository import GLib
from recordprep.ui.main_window import RecordPrepApp

app = RecordPrepApp()
app.set_application_id('org.synthetic.RecordPrepRunEndpoint')
errors = []


def drain():
    end = time.monotonic() + .15
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def check():
    try:
        window = app.get_active_window()
        window.set_title('Synthetic Run through acceptance')
        bundle = ROOT / 'bundle'
        bundle.mkdir()
        window._resolve_case_root = lambda: bundle
        window._require_resolved_layout = lambda **kwargs: True
        calls = []
        steps = [(step, row, lambda step=step: calls.append(step) or True)
                 for step, row, _handler in window._pipeline_steps()]
        window._pipeline_steps = lambda: steps
        ids = [step for step, _, _ in steps]
        start = 'create_hearing_summaries'
        start_index = ids.index(start)
        for endpoint in ('create_report_summaries', start, None):
            calls.clear()
            window._run_until_dropdown.set_selected(window._run_until_values.index(endpoint))
            with patch('recordprep.ui.main_window.threading.Thread') as thread:
                window.on_run_from_step_clicked(start)
            assert thread.call_args.kwargs['args'] == (start_index, bundle, endpoint)
            assert not window._run_until_dropdown.get_sensitive()
            thread.call_args.kwargs['target'](*thread.call_args.kwargs['args'])
            drain()
            stop = ids.index(endpoint) + 1 if endpoint else len(ids)
            assert calls == ids[start_index:stop], calls
            assert not window._pipeline_running
            assert window._run_until_dropdown.get_sensitive()
        window._run_until_dropdown.set_selected(window._run_until_values.index('build_participant_index'))
        calls.clear()
        with patch('recordprep.ui.main_window.threading.Thread') as thread, \
             patch.object(window, 'show_toast') as toast:
            window.on_run_from_step_clicked(start)
        thread.assert_not_called()
        assert not calls and not window._pipeline_running
        assert 'at or after' in toast.call_args.args[0]
        assert window._run_until_dropdown.get_sensitive()
        window._run_until_dropdown.set_selected(window._run_until_values.index('create_report_summaries'))
        print('RUN FROM HERE / RUN THROUGH GTK ACCEPTANCE PASSED', flush=True)
        if os.environ.get('ENDPOINT_ACCEPT_HOLD'):
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
