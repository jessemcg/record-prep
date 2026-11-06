"""Synthetic inspector-only minutes acceptance; optional local Computer Use hold.

Run only in a disposable source/environment. MINUTE_UI_HOLD=1 leaves the fixed
inspector open; Close ends the hold. No model/network/settings-save operation.
"""
import copy
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='recordprep-fixed-minutes-ui-') as temporary:
    root = Path(temporary)
    for key in ('HOME', 'RECORDPREP_CONFIG_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
                'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'PI_CODING_AGENT_DIR'):
        path = root / key.lower()
        path.mkdir(mode=0o700)
        os.environ[key] = str(path)
    os.environ['PI_RUN_METRICS_ENABLED'] = '0'
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Adw, Gtk, GLib
    from recordprep import practice_profiles as api
    from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile
    from recordprep.settings_navigation import descendants
    from recordprep.prompt_inspection import inspect_prompt
    from recordprep.paths import resource_root

    def drain():
        until = time.monotonic() + .25
        while time.monotonic() < until:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(.01)

    def inventory():
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for key in ('recordprep_config_dir', 'xdg_config_home', 'xdg_data_home', 'pi_coding_agent_dir')
                for p in (root / key).rglob('*') if p.is_file()}

    Adw.init()
    app = Adw.Application(application_id='org.synthetic.RecordPrep.FixedMinutes')
    app.register(None)
    parent = Adw.ApplicationWindow(application=app)
    snapshot = api.bundled_profile_for_identity('recordprep', api.DEFAULT_PROFILE_ID)
    editor = editable_profile(snapshot)
    store = api.ProfileStore('recordprep', config_root=root/'profiles', data_root=root/'snapshots')
    w = ProfileEditorWindow(parent, editor, store, expected_head=None,
                            can_modify=lambda: True, preview=lambda _: None, on_saved=Mock())
    w.set_title('Synthetic RecordPrep — fixed minutes acceptance')
    w.present()
    drain()
    assert set(w.pages) == {'report-naming', 'form-naming', 'hearings-topics', 'reports-topics'}
    assert 'minutes' not in editor.resources
    before = inventory()
    topic_buffers = {k: e.get_child().get_buffer() for k, e in w._topic_editors.items()}
    for page in ('hearings-topics', 'reports-topics'):
        w._select_page(page)
        disclosure = next(x for x in descendants(w.pages[page])
                          if isinstance(x, Gtk.Expander) and x.get_label() == 'About summaries')
        disclosure.set_expanded(True)
        assert not any(isinstance(x, Gtk.ScrolledWindow) for x in descendants(disclosure))
        w._inspect_prompts('Summaries')
        view = w.prompt_inspector
        for task in ('hearings-extract', 'reports-extract'):
            view.selector.set_selected(next(i for i, (k, _) in enumerate(view.tasks) if k == task))
            for mode in (0, 1):
                view.mode.set_selected(mode)
                view._refresh()
                assert view.mode.get_visible()
                assert view.mode_note.get_visible() == (mode == 1)
                assert not view.status.get_text()
        view.close()
        drain()
    # A malformed unrelated draft must not leak into the fixed view.
    saved_naming = copy.deepcopy(editor.resources['naming'])
    editor.resources['naming'] = {'schema_version': 999, 'canary': 'INVALID-UNRELATED-DRAFT'}
    w._inspect_prompts('Summaries')
    view = w.prompt_inspector
    view.selector.set_selected(next(i for i, (k, _) in enumerate(view.tasks) if k == 'minutes'))
    view._refresh()
    drain()
    assert not view.mode.get_visible() and not view.mode_note.get_visible()
    assert not view.status.get_text()
    text = view.text.get_buffer().get_text(*view.text.get_buffer().get_bounds(), True)
    assert text == inspect_prompt({}, 'minutes', resource_root()).display_text()
    assert 'INVALID-UNRELATED-DRAFT' not in text
    assert 'April 9, 2030 — Administrative review' in text
    assert 'May 7, 2030 — Motion to compel' in text
    assert not view.text.get_editable()
    assert view.search.get_visible()
    assert inventory() == before
    assert {k: e.get_child().get_buffer() for k, e in w._topic_editors.items()} == topic_buffers
    print(f'PASS: fixed minutes inspector; invalid unrelated draft ignored; topic modes/buffers retained; no writes; PID {os.getpid()}', flush=True)
    if os.environ.get('MINUTE_UI_HOLD') == '1':
        print('HOLD: close only the synthetic Full prompts inspector to finish', flush=True)
        while view.get_visible():
            GLib.MainContext.default().iteration(True)
    view.destroy()
    drain()
    editor.resources['naming'] = saved_naming
    assert inventory() == before
    assert not store.registry_path.exists()
    w.set_focus(None)
    w.destroy()
    parent.destroy()
    drain()
    print('PASS: synthetic windows closed without Save or model work', flush=True)
