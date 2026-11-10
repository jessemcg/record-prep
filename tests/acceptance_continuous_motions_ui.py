"""Isolated synthetic GTK continuity adoption; no Pi or user configuration."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, required=True); args = parser.parse_args()
bundle = args.bundle.resolve()
assert bundle.is_relative_to(Path(tempfile.gettempdir()).resolve()) and (bundle / '.continuous-motion-fixture').read_text() == 'fictional-only\n'
base = Path(tempfile.mkdtemp(prefix='continuous-motion-ui-'))
for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'PI_CODING_AGENT_DIR', 'RECORDPREP_CONFIG_DIR'):
    directory = base / key.lower(); directory.mkdir(mode=0o700); os.environ[key] = str(directory)
os.environ.update(PI_RUN_METRICS_ENABLED='0', GSETTINGS_BACKEND='memory', RECORDPREP_PI_COMMAND='/nonexistent/pi')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from recordprep.ui import main_window as ui
ui.Vte = None  # Exercise the application's ordinary non-VTE activity surface.
from recordprep.ui.main_window import RecordPrepWindow, StopRequested
from recordprep.settings_navigation import descendants
from recordprep import motion_groups as mg, summary_agents as sa
from prepare_continuous_motion_acceptance import publish_summaries_and_map


def drain(seconds=.2):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while GLib.MainContext.default().pending(): GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def snapshot():
    return {p: (p.read_bytes(), p.stat().st_mtime_ns) for directory in ('text_pages', 'classification') for p in (bundle / directory).iterdir()}


Adw.init(); app = Adw.Application(application_id='com.mcglaw.RecordPrep.ContinuousAcceptance.p' + str(os.getpid())); app.register(None)
main = RecordPrepWindow(app); main.set_title('Synthetic RecordPrep — continuous motion packets'); main.present(); drain()
originals = snapshot()
# Explicitly adopt on this disposable fixture, from named-only saved boundaries.
(bundle / mg.PATH).unlink()
from recordprep.motion_pages import build_motion_boundaries
rows = [json.loads(line) for line in (bundle / 'classification/CT_basic_advanced_corrected_dates_names.jsonl').read_text().splitlines()]
(bundle / 'artifacts/motion_boundaries.json').write_text(json.dumps(build_motion_boundaries(rows, -1)))
with patch.object(main, '_resolve_case_root', return_value=bundle), \
     patch.object(main, '_run_pi_skill_step', side_effect=AssertionError('Pi lifecycle used')):
    manifest = (bundle / 'manifest.json').read_bytes()
    assert main._run_step_motion_organization(); drain()
    assert (bundle / 'manifest.json').read_bytes() == manifest
    saved = bundle / mg.PATH; before = saved.read_bytes(), saved.stat().st_mtime_ns
    assert main._run_step_motion_organization(); drain()
    assert (saved.read_bytes(), saved.stat().st_mtime_ns) == before
    with patch.object(main, '_raise_if_stop_requested', side_effect=StopRequested()):
        assert not main._run_step_motion_organization()
    assert (saved.read_bytes(), saved.stat().st_mtime_ns) == before
    with patch.object(main, '_resolve_case_root', side_effect=[bundle, base / 'different-selection']):
        assert not main._run_step_motion_organization()
    assert (saved.read_bytes(), saved.stat().st_mtime_ns) == before
    assert main._activity_terminal is None
    assert main._run_step_six(); drain()
    toc = (bundle / 'artifacts/toc.txt').read_text()
    assert toc.count('Request to Change Fictional Order') == 1 and 'Unnamed' not in toc
    assert toc.count('Separate Named Motion') == 1
    assert main._run_step_seven(); drain()
    assert main._run_step_correct_boundaries(); drain()
    boundaries = json.loads((bundle / 'artifacts/motion_boundaries.json').read_text())
    assert [(r['motion_id'], r['motion_name']) for r in boundaries] == [('motion:0011', 'Request to Change Fictional Order'), ('motion:0014', ''), ('motion:0021', 'Separate Named Motion')]
    assert [sa.item_source_pages(it) for it in sa.build_work_items(bundle, sa.ExtractionConfig('motions', ''))] == [(11, 12, 13, 14, 15), (21,)]
    main._show_motion_grouping(None); drain()
    windows = Gtk.Window.get_toplevels()
    grouping = next(windows.get_item(i) for i in range(windows.get_n_items()) if windows.get_item(i).get_title() == 'Motion grouping')
    view = next(w for w in descendants(grouping) if isinstance(w, Gtk.TextView))
    text = view.get_buffer().get_text(*view.get_buffer().get_bounds(), True)
    assert not view.get_editable() and 'Unnamed motion paper' in text and 'Selected-inventory accounting: complete' in text
    assert '17–18' in text and 'not legal relationship review' in text
    assert snapshot() == originals
    publish_summaries_and_map(bundle)
    print(json.dumps(dict(status='PASS', pid=os.getpid(), bundle=str(bundle), checks=['Python lifecycle without Pi', 'Stop', 'mtime reuse', 'TOC two entries', 'physical boundary rebuild/filter retains unnamed', 'two summary work items', 'digest/edition/source-map publication', 'read-only grouping'])), flush=True)
    drain(int(os.environ.get('MOTION_UI_HOLD_MS', '0')) / 1000)
    grouping.destroy(); main.destroy(); drain()
