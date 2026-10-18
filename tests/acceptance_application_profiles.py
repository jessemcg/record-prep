"""Actual GTK application profile selection/save/storage; synthetic data only."""
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(tempfile.mkdtemp(prefix='recordprep-app-profiles-'))
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'RECORDPREP_CONFIG_DIR'):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.pop('RECORDPREP_PROFILE_DIR', None)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import GLib
from recordprep.ui.main_window import RecordPrepApp
from recordprep import practice_profiles as api, profile_integration as integration
from recordprep.profile_portability import save_portable_profiles, use_directory

bundle = ROOT / 'bundle'
(bundle / '.recordprep').mkdir(parents=True)
pin = bundle / '.recordprep/practice-profile.json'
pin.write_text('Historical missing revision: not current instruction authority.')
sentinel = bundle / 'old-summary.txt'
sentinel.write_text('Synthetic stored output stays readable.')
before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (pin, sentinel)}
app = RecordPrepApp()
app.set_application_id('org.synthetic.RecordPrepApplicationProfiles')
errors = []


def drain():
    end = time.monotonic() + .15
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def run():
    try:
        window = app.get_active_window()
        window.set_title('Synthetic application profiles — RecordPrep')
        window._resolve_case_root = lambda: bundle
        integration.update_indicator(window)
        assert window._title_widget.get_subtitle() == 'General Court Record'
        manager = integration.open_manager(window, HERE / '.pi')
        dependency = next(i for i, candidate in enumerate(manager.options)
                          if candidate.snapshot.ref.specialty_id == 'california-juvenile-dependency')
        manager.selector._choose(dependency)
        drain()
        selected = api.default_profile_candidate()
        assert selected.ref.specialty_id == 'california-juvenile-dependency'
        assert window._title_widget.get_subtitle() == selected.manifest['display_name']
        editor = manager._edit()
        drain()
        editor.editor.resources['minutes'] += '\nSynthetic saved orientation emphasis.\n'
        assert editor._save()
        drain()
        assert editor.saved_dialog is None
        assert api.default_profile_candidate().ref != selected.ref
        assert manager.selected_ref == api.default_profile_candidate().ref
        assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
        # The same app-wide choice remains when the case is cleared.
        window._resolve_case_root = lambda: None
        integration.update_indicator(window)
        assert window._title_widget.get_subtitle() == selected.manifest['display_name']
        destination = ROOT / 'portable'
        old_store = api.profile_store()
        save_portable_profiles(old_store, destination)
        use_directory(destination)
        assert api.profile_store().config_root == destination
        assert not manager.can_modify()  # Old editor cannot save into old storage.
        editor.close()
        window._resolve_case_root = lambda: bundle
        manager = integration.open_manager(window, HERE / '.pi')
        assert manager.store.config_root == destination
        assert manager.storage_button.get_child().get_text() == 'Profile storage…'
        editor = manager._edit()
        drain()
        assert editor.case_notice.get_visible()
        assert 'selected application profile' in editor.case_notice.get_text()
        assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
        print('APPLICATION PROFILES GTK ACCEPTANCE PASSED; synthetic root:', ROOT, flush=True)
        if os.environ.get('PROFILE_ACCEPT_HOLD'):
            GLib.timeout_add_seconds(60, lambda: (editor.destroy(), app.quit(), False)[-1])
        else:
            editor.destroy()
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False

app.connect('activate', lambda *_: GLib.idle_add(run))
app.run([])
if errors:
    raise SystemExit(1)
