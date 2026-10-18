"""Shared PI GTK acceptance; synthetic settings/discovery only, no provider calls.

MODEL_DROPDOWN_HOLD=1 leaves the experiment-owned settings window for native
Computer Use observation. Close only that window to finish.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory(prefix='recordprep-shared-model-ui-')
ROOT = Path(TEMP.name)
for key in ('HOME', 'RECORDPREP_CONFIG_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'PI_CODING_AGENT_DIR'):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
from recordprep.ui import main_window as ui
from gi.repository import Adw, GLib, Gtk, Pango

Adw.init()
app = Adw.Application(application_id='org.synthetic.RecordPrepSharedPI')
app.register(None)
config = Path(os.environ['RECORDPREP_CONFIG_DIR']) / 'config.json'
prefs = config.parent / 'pi/settings.json'
prefs.parent.mkdir()
models = [ui.PiModel(provider='example-provider', model_id=f'accounts/provider/models/variant-{variant}',
                     name=f'Example Model with a shared long beginning — variant-{variant}')
          for variant in ('alpha', 'beta')]
raw = {'summary_extract_pi_model': '  retired/model  ', 'summary_synthesize_reports_pi_thinking': 'medium',
       'summarize_hearings_prompt': '  Custom guidance.\t\n', 'unrelated': {'keep': True},
       'pi_agent_command': 'synthetic-pi'}
config.write_text(json.dumps(raw))
prefs.write_text(json.dumps({'defaultProvider': models[0].provider, 'defaultModel': models[0].model_id,
                             'defaultThinkingLevel': 'low', 'otherPreference': True}))


def drain():
    until = time.monotonic() + .3
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def create():
    window = ui.SettingsWindow(app)
    window.set_title('Synthetic RecordPrep — shared PI settings')
    window.present()
    drain()
    return window


with patch.object(ui, 'CONFIG_FILE', config), \
        patch.object(ui, 'available_pi_models', return_value=models) as discovery, \
        patch.object(ui, 'resolve_pi_agent_argv', return_value=['synthetic-pi']):
    window = create()
    assert list(window._settings_group_rows) == ['ocr', 'classify', 'agent']
    assert window._prompt_stack.get_visible_child_name() == 'ocr'
    for group, key in [('ocr', 'ocr'), ('classify', 'classify-basic'), ('agent', 'pi')]:
        row = window._settings_group_rows[group]
        assert isinstance(row, Adw.ActionRow) and not isinstance(row, Adw.ExpanderRow)
        row.emit('activated')
        drain()
        assert window._prompt_stack.get_visible_child_name() == key
    assert not hasattr(window, '_summarize_widgets')
    titles = []
    def inspect(widget):
        if isinstance(widget, Adw.ComboRow): titles.append(widget.get_title())
        child = widget.get_first_child()
        while child:
            inspect(child)
            child = child.get_next_sibling()
    inspect(window._prompt_stack)
    assert titles.count('PI model') == titles.count('PI reasoning effort') == 1
    assert not any('Synthesis' in title or 'Extraction model' == title for title in titles)
    row = window._pi_model_row
    factory = row.get_list_factory()
    item = Gtk.ListItem()
    factory.emit('setup', item)
    label = item.get_child()
    assert label.get_width_chars() == 64 and label.get_max_width_chars() == 80
    assert label.get_wrap() and label.get_wrap_mode() == Pango.WrapMode.WORD_CHAR
    assert label.get_ellipsize() == Pango.EllipsizeMode.NONE
    for model in models:
        ui._bind_pi_model_list_item(factory, SimpleNamespace(
            get_item=lambda: Gtk.StringObject.new(model.label), get_child=lambda: label))
        assert label.get_label() == model.label
    before_refresh = discovery.call_count
    window._pi_model_refresh_button.emit('clicked')
    drain()
    assert discovery.call_count == before_refresh + 1 and row.get_sensitive()
    row.set_selected(1)
    assert models[1].model_id in row.get_subtitle()
    reasoning = window._agent_widgets.pi_thinking_level_row
    reasoning.set_selected(next(i for i, (_, v) in enumerate(ui.PI_THINKING_LEVEL_OPTIONS) if v == 'high'))
    window._save_settings()
    drain()
    assert json.loads(prefs.read_text()) == {'defaultProvider': models[1].provider,
        'defaultModel': models[1].model_id, 'defaultThinkingLevel': 'high', 'otherPreference': True}
    saved = json.loads(config.read_text())
    for key, value in raw.items(): assert saved[key] == value
    assert {key for key in saved if key.startswith('summary_')} == {key for key in raw if key.startswith('summary_')}
    window = create()
    assert window._selected_pi_model().settings_key == models[1].settings_key
    assert ui.PI_THINKING_LEVEL_OPTIONS[window._agent_widgets.pi_thinking_level_row.get_selected()][1] == 'high'
    original = (config.read_bytes(), prefs.read_bytes())
    window._pi_model_row.set_selected(0)
    window.close()  # Cancel/close writes nothing.
    drain()
    assert original == (config.read_bytes(), prefs.read_bytes())
    # Discovery failures and unavailable saved models do not choose a fallback.
    with patch.object(ui, 'available_pi_models', side_effect=ui.PiRuntimeError('Synthetic discovery failure')):
        window = create()
        assert not window._pi_model_row.get_sensitive()
        assert window._selected_pi_model().settings_key == models[1].settings_key
        window.close()
    with patch.object(ui, 'available_pi_models', return_value=[models[0]]):
        window = create()
        assert window._selected_pi_model().settings_key == models[1].settings_key
        assert 'unavailable' in window._pi_model_row.get_selected_item().get_string()
        window.close()
    assert original == (config.read_bytes(), prefs.read_bytes())
    # A fresh config must not acquire retired keys.
    config.write_text('{}')
    window = create()
    window._save_settings()
    assert not any(k.startswith(('summary_extract_', 'summary_synthesize_')) for k in json.loads(config.read_text()))
    # Keep realistic legacy preservation data for manual observation.
    config.write_text(json.dumps(saved))
    window = create()
    window._settings_group_rows['agent'].emit('activated')
    drain()
    print(f'SHARED PI GTK ACCEPTANCE PASSED pid={os.getpid()}', flush=True)
    if os.environ.get('MODEL_DROPDOWN_HOLD'):
        loop = GLib.MainLoop()
        window.connect('close-request', lambda *_: (loop.quit(), False)[1])
        loop.run()
    window.destroy()
TEMP.cleanup()
