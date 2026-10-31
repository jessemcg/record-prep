"""Current flat Classification / Summaries acceptance; synthetic production GTK.

Run in a disposable checkout/environment. CLASSIFICATION_GUIDANCE_HOLD=1 keeps
this synthetic window open for native desktop observation; close discards drafts.
PROFILE_OWNERSHIP_SCENARIO=current|naming-v2|invalid selects public/synthetic data.
No private settings, case, model discovery or provider calls.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
TEMP = tempfile.TemporaryDirectory(prefix='classification-guidance-')
ROOT = Path(TEMP.name)
for key in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','PI_CODING_AGENT_DIR'):
    directory = ROOT / key.lower(); directory.mkdir()
    os.environ[key] = str(directory)
os.environ['PI_RUN_METRICS_ENABLED'] = '0'

import gi
gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')
from gi.repository import Adw, GLib, Gtk
from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile, CLASSIFICATION_PAGES, CLASSIFICATION_EXPLANATION, CLASSIFICATION_PROGRESSION
from recordprep.profile_workflows import ProfileEditor
from recordprep.settings_navigation import descendants
from recordprep.classification_profiles import classifier_prompt
from recordprep.profile_integration import preview


def drain():
    end = time.monotonic() + .2
    while time.monotonic() < end:
        while GLib.MainContext.default().pending(): GLib.MainContext.default().iteration(False)
        time.sleep(.005)


Adw.init()
app = Adw.Application(application_id='org.synthetic.RecordPrep.OwnershipAcceptance'); app.register(None)
parent = Adw.ApplicationWindow(application=app)
store = api.ProfileStore('recordprep',config_root=ROOT/'config',data_root=ROOT/'data')
base = api.bundled_profile_for_identity('recordprep',api.DEFAULT_PROFILE_ID)
e = ProfileEditor(base)
scenario = os.environ.get('PROFILE_OWNERSHIP_SCENARIO','current')
if scenario in ('naming-v2','invalid'):
    e.manifest['schema_version'] = 6
    e.resources['naming'] = json.loads((HERE/'tests/fixtures/naming-v2/california_dependency.json').read_bytes())
    e.resources['naming']['report_guidance'] += ' Synthetic custom naming guidance.'
w = ProfileEditorWindow(parent,editable_profile(e.snapshot()),store,expected_head=None,
    can_modify=lambda: True,preview=lambda snapshot: preview(snapshot,HERE/'.pi'),on_saved=lambda _ref: None,candidates=[])
w.present(); drain()
before = copy.deepcopy(w.editor.resources); original_files = base.files
assert list(w.pages) == [key for key,_,_ in CLASSIFICATION_PAGES] + ['hearings-topics','reports-topics','minutes']
assert set(w.nav_groups) == {'Classification','Summaries'}
assert 'date_hearing' not in w.pages and 'date_minute' not in w.pages
assert len(w._recognition_cards) == 19
for key,title,stage in CLASSIFICATION_PAGES:
    w._select_page(key); drain()
    assert w.nav_rows[key].get_title() == title and w.nav_rows[key].get_subtitle() == stage
    disclosure = next(x for x in descendants(w.pages[key]) if isinstance(x,Gtk.Expander) and x.get_label() == 'About classification')
    assert not disclosure.get_expanded()
    disclosure.set_expanded(True); drain()
    label = next(x for x in descendants(disclosure) if isinstance(x,Gtk.Label) and CLASSIFICATION_EXPLANATION in x.get_text())
    assert label.get_text().endswith(CLASSIFICATION_PROGRESSION)
    # Disclosure is in the ordinary page scroller, never its own capped scroller.
    assert label.get_ancestor(Gtk.ScrolledWindow) is w.pages[key]
    assert label.get_height() + label.get_margin_top() + label.get_margin_bottom() >= label.measure(Gtk.Orientation.VERTICAL,label.get_width())[1]
    disclosure.set_expanded(False)
for key in ('hearings-topics','reports-topics','minutes'):
    w._select_page(key); drain()
    disclosure = next(x for x in descendants(w.pages[key]) if isinstance(x,Gtk.Expander) and x.get_label() == 'About summaries')
    disclosure.set_expanded(True); drain()
    label = next(x for x in descendants(disclosure) if isinstance(x,Gtk.Label) and 'across all its pages' in x.get_text())
    assert label.get_ancestor(Gtk.ScrolledWindow) is w.pages[key]
    assert label.get_height() + label.get_margin_top() + label.get_margin_bottom() >= label.measure(Gtk.Orientation.VERTICAL,label.get_width())[1]
    disclosure.set_expanded(False)
assert w.editor.resources == before and base.files == original_files
assert not store.registry_path.exists()
for task in ('date_hearing','date_minute'):
    assert 'long-form U.S. date' in classifier_prompt(w.editor.snapshot(),task)[0]
if scenario == 'invalid':
    w._select_page('report-naming')
    w._replace_buffer(w._legacy_naming_buffer,'{ invalid synthetic naming α')
    assert not w._save()
    w._inspect_prompts('Classification'); w.prompt_inspector.mode.set_selected(1)
    assert w.prompt_inspector.snapshot is None
    assert 'invalid' in w.prompt_inspector.status.get_text().lower()
else:
    w._select_page('rt' if scenario == 'current' else 'report-naming')
print('CURRENT CLASSIFICATION / SUMMARIES GTK ACCEPTANCE PASSED: '+scenario,flush=True)
if os.environ.get('CLASSIFICATION_GUIDANCE_HOLD'):
    loop = GLib.MainLoop()
    def finished():
        if w._closing:
            loop.quit()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE
    GLib.timeout_add(100,finished)
    loop.run()
w.destroy(); parent.destroy(); drain(); TEMP.cleanup()
