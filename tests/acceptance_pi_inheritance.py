"""Native Settings acceptance with temporary preferences and synthetic catalogs.
Run from a disposable tracked-source-only checkout. No OCR/Pi/case/model calls.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

os.umask(0o077)
ROOT = Path(tempfile.mkdtemp(prefix='recordprep-inheritance-'))
for key, directory in {'HOME': 'home', 'XDG_CONFIG_HOME': 'config', 'XDG_DATA_HOME': 'data',
                       'XDG_STATE_HOME': 'state', 'XDG_CACHE_HOME': 'cache',
                       'PI_CODING_AGENT_DIR': 'pi', 'RECORDPREP_CONFIG_DIR': 'app'}.items():
    os.environ[key] = str(ROOT / directory)
os.environ['GSETTINGS_BACKEND'] = 'memory'
from recordprep.ui import main_window as ui
from recordprep import pi_runtime as runtime
PREFS = ROOT / 'app/pi/settings.json'
MODEL = ui.PiModel('synthetic', 'chosen', 'Synthetic choice')
app = ui.Adw.Application(application_id='org.synthetic.RecordPrep.PiInheritance')
patches = []


def activate(application):
    config = {'synthetic_unknown': ['keep']}
    def write(value):
        config.clear(); config.update(value)
        (ROOT / 'saved-display.json').write_text(json.dumps(config))
    for name, value in (
        ('_read_config', lambda: dict(config)), ('_write_config', write),
        ('resolve_pi_agent_argv', lambda *a, **k: ['synthetic-pi']),
    ):
        p = patch.object(ui, name, value); p.start(); patches.append(p)
    p = patch.object(ui.SettingsWindow, '_load_pi_models', lambda self: None)
    p.start(); patches.append(p)
    windows = []
    def reopen():
        if windows: windows.pop().destroy()
        w = ui.SettingsWindow(application)
        w.set_title('Synthetic RecordPrep Pi inheritance')
        w._finish_pi_model_load(0, [MODEL], '', w._original_pi_model_key)
        w._settings_group_rows['agent'].set_expanded(True)
        windows.append(w); w.present()
        return w
    reopen()
    controls = ui.Adw.ApplicationWindow(application=application, title='RecordPrep inheritance controls')
    box = ui.Gtk.Box(orientation=ui.Gtk.Orientation.VERTICAL, spacing=8)
    controls.set_content(box)
    def inherited_save():
        w = windows[0]
        assert w._selected_pi_model() is None and not w._pi_model_selection_changed
        w.trigger_save()
        assert not PREFS.exists()
        assert config['synthetic_unknown'] == ['keep']
        print('PASS inherited/unrelated Save', flush=True)
    def choose_and_fail():
        w = windows[0]; w._pi_model_row.set_selected(1)
        w._finish_pi_model_load(0, [], 'Synthetic refresh failure; draft retained', MODEL.settings_key)
        assert w._selected_pi_model().settings_key == MODEL.settings_key
        assert w._pi_model_selection_changed
        print('PASS explicit draft survives refresh failure', flush=True)
    def save_reopen():
        windows[0].trigger_save()
        assert json.loads(PREFS.read_text()) == {'defaultProvider': 'synthetic', 'defaultModel': 'chosen'}
        w = reopen()
        assert w._selected_pi_model().settings_key == MODEL.settings_key
        assert w._original_pi_thinking_level is None
        assert config['synthetic_unknown'] == ['keep']
        print('PASS model-only Save/reopen; reasoning inherited', flush=True)
    steps = [inherited_save, choose_and_fail, save_reopen]
    for label, callback in zip(('1 Save inherited', '2 Choose and fail refresh', '3 Save and reopen'), steps):
        button = ui.Gtk.Button(label=label)
        button.connect('clicked', lambda _, f=callback: f()); box.append(button)
    done = ui.Gtk.Button(label='Finish acceptance')
    done.connect('clicked', lambda _: application.quit()); box.append(done)
    controls.present()
    print(f'ROOT={ROOT} PID={os.getpid()}', flush=True)
    if '--auto' in sys.argv:
        def run():
            for step in steps: step()
            application.quit(); return False
        ui.GLib.timeout_add(500, run)


app.connect('activate', activate)
app.run([])
