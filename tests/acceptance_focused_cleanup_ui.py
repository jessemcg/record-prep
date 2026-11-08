"""Bounded synthetic production UI acceptance, never the user's bundle/settings.

FOCUSED_UI_HOLD_MS optionally keeps the grouping window available for local desktop
observation. The fixture lives under tempfile and all windows belong to this process.
FOCUSED_UI_PHASE optionally limits pipeline captures to classify/organize/summarize.
Missing compositor snapshots are reported separately, never as visual acceptance.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

base = Path(tempfile.mkdtemp(prefix='recordprep-focused-ui-'))
for key in ('HOME', 'RECORDPREP_CONFIG_DIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
            'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'PI_CODING_AGENT_DIR'):
    path = base / key.lower()
    path.mkdir(mode=0o700)
    os.environ[key] = str(path)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'
os.environ['GSETTINGS_BACKEND'] = 'memory'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib
from recordprep.ui.main_window import RecordPrepWindow
from recordprep import motion_groups as mg, profile_editor_ui as editor
from recordprep.settings_navigation import descendants


def drain(seconds=.25):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def files():
    return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in base.rglob('*')
            if p.is_file() and p.suffix != '.png'}


def capture(window, name):
    paintable = Gtk.WidgetPaintable.new(window)
    window.queue_draw()
    drain(.8)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, window.get_width(), window.get_height())
    node = snapshot.to_node()
    if node is None:
        print('VISUAL UNAVAILABLE: compositor returned no rendered node for ' + name, flush=True)
        return
    window.get_renderer().render_texture(node, None).save_to_png(str(base / (name + '.png')))


Adw.init()
# Process-local only: make expanded-row layouts deterministic, without changing
# desktop settings or the application's protected disclosure presentation code.
Gtk.Settings.get_default().set_property('gtk-enable-animations', False)
app = Adw.Application(application_id='org.synthetic.RecordPrep.FocusedCleanup')
app.register(None)
main = RecordPrepWindow(app)
main.set_title('Synthetic RecordPrep — focused cleanup')
main.set_default_size(1040, 1000)
main.present()
drain(3)
for row, phrase in ((main.step_names_row, 'motion-paper names'), (main.step_six_row, 'motions'),
                   (main.step_seven_row, 'motion papers'), (main.step_correct_boundaries_row, 'single-page reports'),
                   (main.step_hearing_summaries_row, 'proceedings, arguments, and rulings'),
                   (main.step_minute_order_summaries_row, 'compact appearances, orders, and next-hearing')):
    assert phrase in row.get_subtitle()
phases = ('classify', 'organize', 'summarize')
if os.environ.get('FOCUSED_UI_PHASE'):
    assert os.environ['FOCUSED_UI_PHASE'] in phases
    phases = (os.environ['FOCUSED_UI_PHASE'],)
for phase in phases:
    main._phase_rows[phase].set_expanded(True)
    drain()
    scroller = next(w for w in descendants(main) if isinstance(w, Gtk.ScrolledWindow)
                    and main.step_list.is_ancestor(w))
    adjustment = scroller.get_vadjustment()
    adjustment.set_value(adjustment.get_upper() - adjustment.get_page_size())
    drain()
    capture(main, 'pipeline-' + phase)
# Call the unchanged production disclosure builder and inspect its rendered widgets.
explainer_window = Adw.Window(title='Synthetic protected explainers', transient_for=main,
                             default_width=780, default_height=700)
body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
scroll = Gtk.ScrolledWindow(child=body)
explainer_window.set_content(scroll)
for category, explanation, progression, title in (
    ('Document naming', editor.CLASSIFICATION_EXPLANATION, editor.CLASSIFICATION_PROGRESSION, 'About classification'),
    ('Summaries', editor.SUMMARY_EXPLANATION, editor.SUMMARY_PROGRESSION, 'About summaries'),
):
    editor.ProfileEditorWindow._explanation(SimpleNamespace(_inspect_prompts=Mock()), body, category)
    expander = body.get_last_child()
    assert isinstance(expander, Gtk.Expander) and expander.get_label() == title
    assert not expander.get_expanded()
    label = next(w for w in descendants(expander.get_child()) if isinstance(w, Gtk.Label)
                 and w.get_text() == explanation + '\n\n' + progression)
    assert label.get_wrap() and not any(isinstance(w, Gtk.ScrolledWindow) for w in descendants(expander))
    expander.set_expanded(True)
explainer_window.present()
drain()
capture(explainer_window, 'protected-explainers')
explainer_window.destroy()

bundle = base / 'fictional-bundle'
(bundle / 'artifacts').mkdir(parents=True)
physical = [{'motion_name': title, 'start_page': start, 'end_page': end,
             'motion_date': 'April 9, 2030', 'motion_date_basis': 'filed'}
            for title, start, end in (
                ('Notice and Motion to Compel Inspection', 5, 6),
                ('Supporting Declaration of Example Engineer', 7, 8),
                ('Separate Statement Supporting Inspection', 11, 12),
                ('Memorandum Supporting Inspection', 13, 15))]
inventory = mg.inventory_from_boundaries(physical)
proposal = {'lead_paper_id': 'motion:0005', 'member_paper_ids': [p['paper_id'] for p in inventory],
            'filing_role': 'motion/application', 'display_title': 'Motion to compel inspection',
            'filing_party': 'Applicant Vale', 'relationship_notes': 'The papers expressly support the same inspection request.'}
value = mg.normalize_candidate({'groups': [proposal], 'coverage_status': 'complete',
    'findings': ['<b>Fictional advisory note; literal text, not markup.</b>']}, inventory, 'a' * 64)
value['coverage_status'] = 'incomplete'  # Historical review is displayed as saved.
(bundle / mg.PATH).write_text(json.dumps(value))
before = files()
with patch.object(main, '_resolve_case_root', return_value=bundle):
    main._show_motion_grouping(None)
drain()
windows = Gtk.Window.get_toplevels()
grouping = next(windows.get_item(i) for i in range(windows.get_n_items())
                if windows.get_item(i).get_title() == 'Motion grouping')
view = next(w for w in descendants(grouping) if isinstance(w, Gtk.TextView))
text = view.get_buffer().get_text(*view.get_buffer().get_bounds(), True)
assert not view.get_editable()
for phrase in ('Review coverage: incomplete', '1 entry / 4 physical papers', 'Components:',
               'Relationship explanation:', 'Notes:', '<b>Fictional advisory note; literal text, not markup.</b>',
               'source pages 11–12', 'Filing party: Applicant Vale', 'lead source page 5', '(filed)'):
    assert phrase in text
assert view.get_buffer().get_tag_table().get_size() == 0
assert before == files(), 'Viewing changed fixture/settings bytes or mtime'
capture(grouping, 'grouping')
print(json.dumps({'mechanics': 'PASS', 'pid': os.getpid(), 'evidence': str(base),
    'checks': ['production pipeline subtitles', 'read-only plain-text grouping',
               'saved historical status', 'exact member spans and titles', 'no view-time writes',
               'protected explanation + progression, wrapping and natural expansion']}), flush=True)
drain(int(os.environ.get('FOCUSED_UI_HOLD_MS', '0')) / 1000)
grouping.destroy()
main.destroy()
drain()
