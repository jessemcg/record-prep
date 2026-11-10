"""Native GTK acceptance with fictional state only; set CRIMINAL_PROFILE_HOLD=1 to inspect."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TEMP = tempfile.TemporaryDirectory(prefix='recordprep-criminal-ui-')
STATE = Path(TEMP.name)
for key in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME','PI_CONFIG','PI_CODING_AGENT_DIR'):
    path = STATE/key;path.mkdir(mode=0o700);os.environ[key] = str(path)
os.environ['RECORDPREP_CONFIG_DIR'] = str(STATE/'settings')
os.environ['PI_RUN_METRICS_ENABLED'] = '0'

from recordprep import practice_profiles as api
from recordprep.document_naming import compile_naming_profile
from recordprep.profile_manager_ui import ProfileManagerWindow, ProfileSelector
from recordprep.profile_integration import preview
from recordprep.profile_editor_ui import Gtk, Adw
from recordprep.settings_navigation import descendants
from recordprep.prompt_inspection import inspect_prompt
from gi.repository import GLib


def drain():
    until = time.monotonic()+.2
    while time.monotonic()<until:
        while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
        time.sleep(.005)


Adw.init()
app = Adw.Application(application_id='org.synthetic.RecordPrep.CriminalAcceptance')
app.register(None)
parent = Adw.ApplicationWindow(application=app,title='Synthetic RecordPrep — bundled profiles',
                              default_width=650,default_height=450)
store = api.ProfileStore(api.APPLICATION,config_root=STATE/'profiles-config',data_root=STATE/'profiles-data')
with patch.object(api,'profile_store',return_value=store), \
     patch('recordprep.profile_customization.initial_candidate',return_value=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20)
    box.set_margin_top(30);box.set_margin_start(30);box.set_margin_end(30)
    box.append(Gtk.Label(label='Synthetic acceptance only — no case files or providers'))
    manager = ProfileManagerWindow(parent,can_modify=lambda:True,preview=lambda p:preview(p,ROOT/'.pi'),
        on_select=lambda _:None,allow_legacy=False,has_case=False)
    box.append(manager);parent.set_content(box);parent.present();drain()
    assert not store.registry_path.exists()
    assert [c.snapshot.ref.specialty_id for c in manager.candidates] == [api.DEFAULT_PROFILE_ID,'california-criminal-law']
    assert manager.selector.get_selected()==0
    for identity, counts in ((api.DEFAULT_PROFILE_ID,(1,5,12)),('california-criminal-law',(1,11,9))):
        manager.selector._choose(next(i for i,c in enumerate(manager.options) if c.snapshot.ref.specialty_id==identity))
        drain()
        assert api.default_profile_candidate(store=store).ref.specialty_id==identity
        editor = manager._edit();drain()
        base = api.bundled_profile_for_identity(api.APPLICATION,identity)
        assert set(editor.pages)=={'report-naming','form-naming','reports-topics'}
        assert editor.nav_rows['form-naming'].get_title() == 'Procedural Filing Names'
        assert len(editor.editor.resources['reports'])==counts[2]
        assert len(editor.editor.resources['naming']['reports'])==counts[0]
        assert len(editor.editor.resources['naming']['forms'])==counts[1]
        for page in ('report-naming','form-naming','reports-topics'):
            editor._select_page(page);drain()
            assert editor._navigation.view.get_visible_page().get_tag()==page
        for kind in ('report','form'):
            snapshot = editor.editor.snapshot()
            view = inspect_prompt(editor.editor.resources,kind,ROOT/'.pi',template=False,snapshot=snapshot)
            assert not view.issues
            assert view.components[0][1]==compile_naming_profile(snapshot,kind).prompt
        # Fixed inspection is assignment-independent and ignores unrelated bad drafts.
        from recordprep import hearing_guidance, motion_guidance
        from recordprep.prompt_inspection import DraftInspectionState
        invalid = DraftInspectionState({}, (), ('INVALID SYNTHETIC DRAFT',), None)
        for task, expected in (
            ('hearings-extract', hearing_guidance.application_guidance('extract')),
            ('hearings-synthesize', hearing_guidance.application_guidance('synthesize')),
            ('motions-extract', motion_guidance.application_guidance('extract')),
            ('motions-synthesize', motion_guidance.application_guidance('synthesize')),
        ):
            view = inspect_prompt({}, task, ROOT/'.pi', template=False, draft=invalid)
            assert not view.issues
            assert expected in view.display_text()
        minute = inspect_prompt({}, 'minutes', ROOT/'.pi', template=False, draft=invalid)
        assert not minute.issues
        # Real retained buffer callback → Save → exact bundled reset, for both.
        card = editor._topic_editors['topic:naming-reports:'+base.resource('naming')['reports'][0]['id']]
        buffer = card.get_child().get_buffer()
        buffer.insert_at_cursor(' Synthetic UI customization.')
        assert editor._dirty() and editor._save()
        saved = editor.editor.base.ref
        assert store.load_profile_snapshot(saved).files != base.files
        editor._reset().response('reset');drain()
        assert not editor._dirty()
        assert editor.editor.snapshot().files==base.files
        assert 'Synthetic UI customization' in str(store.load_profile_snapshot(saved).resource('naming'))
        assert api.default_profile_candidate(store=store).files==base.files
        editor._new();drain()
        selectors = [w for w in descendants(editor.new_dialog) if isinstance(w,ProfileSelector)]
        assert len(selectors)==1
        assert selectors[0].names==['California Juvenile Dependency','California Criminal Law']
        assert selectors[0].get_selected()==0
        assert editor.delete_selector is None  # Both built-ins protected, even personal edits.
        editor.new_dialog.close();drain()
        editor.destroy();drain()
    # Leave the actual Criminal cards available for optional local Computer Use.
    manager._refresh(api.default_profile_candidate(store=store).ref)
    editor = manager._edit();editor.set_title('Synthetic Criminal — Profile settings')
    page = os.environ.get('CRIMINAL_PROFILE_PAGE','form-naming')
    editor._select_page(page)
    if page=='reports-topics':
        first = 'topic:reports:'+editor.editor.resources['reports'][0]['id']
    else:
        kind = 'reports' if page=='report-naming' else 'forms'
        first = 'topic:naming-'+kind+':'+editor.editor.resources['naming'][kind][0]['id']
    editor._topic_expanders[first].set_expanded(True)
    drain()
    print('CRIMINAL/DEPENDENCY GTK ACCEPTANCE PASSED: choices, bases, 3 destinations, 1/11/9 cards, prompt parity, Save/Reset/history',flush=True)
    if os.environ.get('CRIMINAL_PROFILE_HOLD'):
        loop = GLib.MainLoop()
        parent.connect('close-request',lambda *_:(loop.quit(),False)[1])
        loop.run()
    editor.destroy();parent.destroy();drain()
TEMP.cleanup()
