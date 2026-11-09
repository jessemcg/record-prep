"""Synthetic native UI checks; no settings saves, providers or maintained instance.

Use --bundle from prepare_motion_acceptance.py --grouped. Optional
MOTION_UI_HOLD_MS holds the fixed inspector for local Computer Use observation.
A missing compositor snapshot is reported separately, never called visual acceptance.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock, patch

parser = argparse.ArgumentParser()
parser.add_argument('--bundle', type=Path, required=True)
args = parser.parse_args()
bundle = args.bundle.resolve()
if (not bundle.is_relative_to(Path(tempfile.gettempdir()).resolve()) or
        (bundle / '.motion-acceptance-fixture').read_text() != 'synthetic-disposable-motion-fixture-v1\n'):
    raise SystemExit('Requires the disposable synthetic motion fixture.')
root = Path(tempfile.mkdtemp(prefix='recordprep-grouped-motion-ui-'))
for key in ('HOME', 'RECORDPREP_CONFIG_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'PI_CODING_AGENT_DIR'):
    path = root / key.lower(); path.mkdir(mode=0o700); os.environ[key] = str(path)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
os.environ['GSETTINGS_BACKEND'] = 'memory'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from recordprep.ui import main_window as module
from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile
from recordprep.settings_navigation import descendants
from recordprep.prompt_inspection import inspect_prompt
from recordprep.paths import resource_root


def drain(seconds=.35):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while GLib.MainContext.default().pending(): GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def inventory():
    return {p: (p.read_bytes(), p.stat().st_mtime_ns) for base in (root, bundle)
            for p in base.rglob('*') if p.is_file() and p.suffix != '.png'}


def capture(window, name):
    paintable = Gtk.WidgetPaintable.new(window); snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    node = snapshot.to_node()
    if node is None:
        print('VISUAL UNAVAILABLE: compositor returned no rendered node for ' + name, flush=True)
        return
    window.get_renderer().render_texture(node, None).save_to_png(str(root / (name + '.png')))


Adw.init()
application = Adw.Application(application_id='com.mcglaw.RecordPrep.GroupedMotionAcceptance.p' + str(os.getpid()))
application.register(None)
main = module.RecordPrepWindow(application)
main.set_title('Synthetic RecordPrep — grouped motions')
main.present(); main._phase_rows['organize'].set_expanded(True); drain()
assert list(main._step_rows_by_id).index('organize_motion_papers') < list(main._step_rows_by_id).index('build_toc')
assert main.step_motion_organization_row.get_title() == 'Organize motion papers'
assert any(isinstance(w, Gtk.Button) and w.get_label() == 'View grouping' for w in descendants(main.step_motion_organization_row))
with patch.object(main, '_resolve_case_root', return_value=bundle):
    assert main._run_step_six(), 'Actual Build TOC worker failed'
    drain()
    toc = (bundle / 'artifacts/toc.txt').read_text()
    assert any('Motion to compel inspection' in line and int(line.rsplit(' ', 1)[1]) == 5 for line in toc.splitlines())
    assert not any('Supporting Declaration' in line for line in toc.splitlines())
    before = inventory()
    main._show_motion_grouping(None); drain()
    windows = Gtk.Window.get_toplevels()
    grouping = next(windows.get_item(i) for i in range(windows.get_n_items()) if windows.get_item(i).get_title() == 'Motion grouping')
    view = next(w for w in descendants(grouping) if isinstance(w, Gtk.TextView))
    text = view.get_buffer().get_text(*view.get_buffer().get_bounds(), True)
    assert not view.get_editable() and 'Supporting Declaration' in text and 'Motion to compel inspection' in text
    capture(grouping, 'grouping'); grouping.destroy(); drain()
snapshot = api.bundled_profile_for_identity('recordprep', api.DEFAULT_PROFILE_ID)
editor = editable_profile(snapshot)
store = api.ProfileStore('recordprep', config_root=root / 'profiles', data_root=root / 'snapshots')
settings = ProfileEditorWindow(main, editor, store, expected_head=None, can_modify=lambda: True,
                               preview=lambda _: None, on_saved=Mock())
settings.present(); drain()
assert set(settings.pages) == {'report-naming', 'form-naming', 'reports-topics'}
assert 'motions' not in editor.resources
original = copy.deepcopy(editor.resources['naming'])
editor.resources['naming'] = {'schema_version': 999, 'canary': 'INVALID-UNRELATED-MOTION-DRAFT'}
settings._inspect_prompts('Summaries'); inspector = settings.prompt_inspector
for task in ('motion-organization', 'motions-extract', 'motions-synthesize'):
    inspector.selector.set_selected(next(i for i, (key, _) in enumerate(inspector.tasks) if key == task))
    inspector._refresh(); drain()
    text = inspector.text.get_buffer().get_text(*inspector.text.get_buffer().get_bounds(), True)
    assert text == inspect_prompt({}, task, resource_root()).display_text()
    assert 'INVALID-UNRELATED-MOTION-DRAFT' not in text
    if task != 'motion-organization':
        assert 'Request' in text and 'Reasons' in text
    else:
        assert 'ORGANIZE SELECTED PHYSICAL MOTION PAPERS' in text
    assert not inspector.status.get_text() and not inspector.mode.get_visible() and not inspector.text.get_editable()
assert inventory() == before and not store.registry_path.exists()
capture(inspector, 'fixed-motion-prompts')
print(json.dumps({'mechanics': 'PASS', 'pid': os.getpid(), 'root': str(root),
                  'checks': ['native grouping row', 'real TOC lead anchor', 'read-only members', 'two editable summary pages',
                             'three fixed inspectors', 'invalid unrelated draft isolated', 'no settings/bundle writes during inspection']}), flush=True)
hold = int(os.environ.get('MOTION_UI_HOLD_MS', '0'))
if hold: drain(hold / 1000)
inspector.destroy(); editor.resources['naming'] = original
settings.destroy(); main.destroy(); drain()
