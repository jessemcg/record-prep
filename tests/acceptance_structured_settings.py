"""Current schema-10 GTK acceptance, synthetic store, no network or real settings.

Run from a disposable source/HOME/XDG. --interactive leaves the reference and
settings available for native desktop checks. --screenshots PATH captures only
these authored/public resources; style/font overrides are process-local.
"""
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch
import gi
gi.require_version('Gtk','4.0');gi.require_version('Adw','1');gi.require_version('Gsk','4.0')
from gi.repository import Adw, Gtk, GLib
from recordprep import practice_profiles as api
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile
from recordprep.profile_integration import preview
from recordprep.classification_reference_ui import ClassificationReference
from recordprep.classifier_prompts import classifier_document
from recordprep.prompt_inspection import FIXED_TASKS
from recordprep.prompt_inspector_ui import PromptInspector
from recordprep.ui.main_window import RecordPrepWindow

root=Path(tempfile.mkdtemp(prefix='recordprep-neutral-ui.'))
app=Adw.Application(application_id='org.synthetic.RecordPrep.NeutralSettings')
windows=[];failures=[]
def descendants(widget):
    child=widget.get_first_child()
    while child is not None:
        yield child
        yield from descendants(child)
        child=child.get_next_sibling()

def schedule(delay,callback):
    def guarded():
        try:return callback()
        except Exception as exc:
            import traceback
            traceback.print_exc();failures.append(type(exc).__name__);app.quit()
            return GLib.SOURCE_REMOVE
    GLib.timeout_add(delay,guarded)

def run(*_):
    parent=Adw.ApplicationWindow(application=app,title='Synthetic RecordPrep — no case')
    parent.menu_button=Gtk.MenuButton(icon_name='open-menu-symbolic')
    parent.set_content(parent.menu_button)
    parent._open_classification_reference=lambda *args:RecordPrepWindow._open_classification_reference(parent,*args)
    parent.on_settings=lambda *_:None
    parent._on_action_save_settings=lambda *_:None
    # Exercise the production main-menu action, even with unavailable profile storage.
    with patch.object(api,'profile_store',side_effect=ValueError('Synthetic unavailable storage')):
        RecordPrepWindow._setup_menu(parent,app)
        app.lookup_action('classification-reference').activate(None)
    reference=parent._classification_reference
    assert len(reference.cards)==19
    assert reference.get_title()=='App-owned Classification'
    windows.extend((parent,reference))
    store=api.ProfileStore('recordprep',config_root=root/'config',data_root=root/'data')
    with patch('recordprep.profile_customization.initial_candidate',return_value=None):
        candidates=list(api.profile_catalog(store=store))
    b=candidates[0].snapshot
    w=ProfileEditorWindow(parent,editable_profile(b),store,expected_head=None,can_modify=lambda:True,
        preview=lambda s:preview(s,Path(__file__).resolve().parents[1]/'.pi'),on_saved=Mock(),candidates=candidates)
    windows.append(w);w.set_title('Synthetic RecordPrep — Document naming and Summaries')
    if '--interactive' in sys.argv:
        w._select_page('report-naming')
        w._topic_expanders['topic:naming-reports:report-agency'].set_expanded(True)
        w.present();return
    def check():
        assert list(w.nav_groups)==['Document naming','Summaries']
        assert list(w.nav_rows)==['report-naming','form-naming','hearings-topics','reports-topics']
        assert not w._recognition_cards and 'classification_tasks' not in w.editor.resources
        assert not hasattr(w,'_classification_reference')
        for key in ('report-naming','form-naming'):
            widgets=list(descendants(w.pages[key]))
            text='\n'.join(x.get_text() for x in widgets if isinstance(x,Gtk.Label))
            assert 'Page types and all four first-page detectors' not in text
            assert 'Enter each approved name and optional' not in text
            assert not any(isinstance(x,Gtk.Button) and x.get_label() in
                           ('Classification reference…','App-owned Classification') for x in widgets)
        assert not store.registry_path.exists()
        reference.search.set_text('CT_proof_of_service');reference._find()
        assert reference.cards['CT_proof_of_service'][0].get_visible()
        reference.search.set_text('');reference._find()
        reference._prompts();inspector=reference.prompt_inspector
        assert inspector.tasks==FIXED_TASKS and len(inspector.tasks)==8
        assert inspector.recognition is reference.contract
        for index,(task,_) in enumerate(inspector.tasks):
            inspector.selector.set_selected(index);inspector._refresh()
            assert not inspector.mode.get_visible() and not inspector.mode_note.get_visible()
            assert inspector.text.get_editable() is False
            assert classifier_document(task).render() in inspector.text.get_buffer().get_text(*inspector.text.get_buffer().get_bounds(),True)
            assert not inspector.status.get_text()
        with patch('recordprep.recognition_contract.RESOURCE',root/'missing-recognition.json'):
            inspector._refresh()
            assert not inspector.status.get_label()
            broken=PromptInspector(reference,'Application classification')
            assert 'No profile fallback' in broken.status.get_label()
            assert broken.text.get_buffer().get_text(*broken.text.get_buffer().get_bounds(),True).strip()=='{}'
            broken.destroy()
        inspector.selector.set_selected(0);inspector.search.set_text('RT_body');inspector._find()
        textbuffer=inspector.text.get_buffer()
        assert textbuffer.get_text(*textbuffer.get_selection_bounds(),True)=='RT_body'
        clipboard=Mock()
        with patch.object(type(inspector),'get_clipboard',return_value=clipboard):inspector._copy()
        clipboard.set.assert_called_once_with(textbuffer.get_text(*textbuffer.get_bounds(),True))
        inspector.destroy()
        reports=w.editor.resources['naming']['reports']
        assert len(reports)==1 and reports[0]['id']=='report-agency'
        assert reports[0]['name']=='Child Welfare Agency Report'
        for card in reports:
            view=w._topic_editors['topic:naming-reports:'+card['id']].get_child()
            assert view.get_wrap_mode()==Gtk.WrapMode.WORD_CHAR
            assert view.get_buffer().get_text(*view.get_buffer().get_bounds(),True)==card['guidance']
            assert 'only the fallback when the document clearly qualifies' in card['guidance']
        mode = next(x for x in descendants(w._topic_expanders['topic:naming-reports:report-agency'].get_child()) if isinstance(x, Gtk.DropDown))
        assert mode.get_selected() == 1
        mode.set_selected(0); assert reports[0].get('naming_mode', 'fixed') == 'fixed'
        mode.set_selected(1); assert reports[0]['naming_mode'] == 'source_title'
        form_mode = next(x for x in descendants(w._topic_expanders['topic:naming-forms:form-01'].get_child()) if isinstance(x, Gtk.DropDown))
        assert form_mode.get_selected() == 0
        form_mode.set_selected(1)
        assert w.editor.resources['naming']['forms'][0]['naming_mode'] == 'source_title'
        form_mode.set_selected(0)
        assert 'naming_mode' not in w.editor.resources['naming']['forms'][0]
        value=reports[0];detail='topic:naming-reports:'+value['id']
        editor=w._topic_editors[detail];buffer=editor.get_child().get_buffer()
        buffer.insert_at_cursor(' Authored fictional naming clue.')
        assert w._save(),w.message.get_text()
        assert w._topic_editors[detail] is editor and buffer.get_can_undo()
        buffer.undo();assert w._dirty()
        # Naming inspection remains a frozen draft; summary semantics are unchanged.
        for category,page in [('Document naming','report-naming'),('Summaries','hearings-topics')]:
            w._select_page(page);w._inspect_prompts(category)
            current=w.prompt_inspector;current.mode.set_selected(1)
            assert current.get_modal() and not current.status.get_text(),current.status.get_text()
            if category=='Document naming':
                from recordprep.document_naming import compile_naming_profile
                current.selector.set_selected(0);current._refresh()
                text=current.text.get_buffer().get_text(*current.text.get_buffer().get_bounds(),True)
                assert compile_naming_profile(w.editor.snapshot(),'report').prompt in text
                assert 'document\'s own title on its cover/first page' in text
                assert 'Child Welfare Agency Report' in text
                assert 'Memoranda, letters, addenda, supplemental information' in text
            current.destroy()
        ref=w.editor.base.ref;value['name']='';assert not w._save();assert w.editor.base.ref==ref
        # Invalid naming cannot contaminate standalone fixed inspection.
        app.lookup_action('classification-reference').activate(None)
        other=parent._classification_reference;other._prompts()
        assert not other.prompt_inspector.status.get_text()
        other.prompt_inspector.destroy();other.destroy()
        mode.set_selected(0)
        w._reset().response('reset')
        assert mode.get_selected() == 1
        assert w.editor.snapshot().files==b.files,w.message.get_text()
        assert w._topic_editors[detail] is editor and not w._dirty()
        print('Application recognition / naming / summaries GTK acceptance PASS',flush=True)
        if '--screenshots' not in sys.argv:
            for window in windows:window.destroy()
            app.quit();return GLib.SOURCE_REMOVE
        destination=Path(sys.argv[sys.argv.index('--screenshots')+1]);destination.mkdir(parents=True,exist_ok=False)
        steps=[('reference-light',reference,None,850,760,False,11),
               ('reference-narrow',reference,None,480,760,False,11),
               ('reference-dark',reference,None,480,760,True,11),
               ('reference-large-font',reference,None,480,760,False,18),
               ('naming-home',w,'home',850,760,False,11),
               ('report-names',w,'report-naming',480,760,False,11),
               ('report-names-about',w,'report-naming',480,1000,False,11),
               ('report-agency',w,'report-naming',700,1000,False,11),
               ('report-prompts',w,'report-prompts',700,760,False,11),
               ('form-names',w,'form-naming',480,760,False,11),
               ('summary-topics',w,'hearings-topics',850,760,False,11),
               ('fixed-prompts',reference,'prompts',700,760,False,11)]
        def next_step():
            if not steps:
                for window in windows:window.destroy()
                app.quit();return GLib.SOURCE_REMOVE
            name,target,page,width,height,dark,font=steps.pop(0)
            fresh_reference = target is reference and page is None
            if fresh_reference:
                target=ClassificationReference(parent)
            else:
                target.set_visible(False)
            Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)
            Gtk.Settings.get_default().set_property('gtk-font-name',f'Sans {font}')
            if page=='home':w._navigation.view.pop_to_tag('home');w.nav_groups['Document naming'].set_expanded(True)
            elif page=='prompts':reference._prompts();target=reference.prompt_inspector
            elif page=='report-prompts':
                w._inspect_prompts('Document naming');target=w.prompt_inspector
                target.mode.set_selected(1);target.selector.set_selected(0);target._refresh()
            elif page:
                w._select_page(page)
                if page in ('report-naming','form-naming'):
                    next(x for x in descendants(w.pages[page]) if isinstance(x,Gtk.Expander)
                         and x.get_label()=='About classification').set_expanded(name.endswith('-about'))
                for key,card in w._topic_expanders.items():
                    if key.startswith('topic:naming-') or key.startswith('topic:hearings:'):
                        card.set_expanded(key=='topic:naming-reports:report-agency' if name=='report-agency' else True)
            target.set_default_size(width,height);target.present()
            # Observe a full frame before snapshotting; a just-created paintable
            # can otherwise have no node for a stable already-mapped widget.
            paintable=Gtk.WidgetPaintable.new(target)
            target.queue_draw()
            def capture():
                snapshot=Gtk.Snapshot()
                paintable.snapshot(snapshot,target.get_width(),target.get_height());node=snapshot.to_node()
                if node is None:raise RuntimeError('No rendered GTK frame; visual acceptance incomplete.')
                target.get_renderer().render_texture(node,None).save_to_png(str(destination/(name+'.png')))
                print(name,target.get_width(),target.get_height(),flush=True)
                if page in ('prompts','report-prompts') or fresh_reference:target.destroy()
                schedule(350,next_step);return GLib.SOURCE_REMOVE
            schedule(500,capture);return GLib.SOURCE_REMOVE
        schedule(350,next_step);return GLib.SOURCE_REMOVE
    schedule(500,check)
app.connect('activate',run)
raise SystemExit(app.run([]) or bool(failures))
