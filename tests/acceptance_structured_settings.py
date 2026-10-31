"""Production editor with isolated synthetic stores; no maintained app or cases.

Run from a disposable checkout with synthetic HOME/XDG. --interactive keeps the
real editor open for native desktop acceptance; otherwise run bounded assertions.
"""
import copy
import os
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

root=Path(tempfile.mkdtemp(prefix='recordprep-structured-ui.'))
app=Adw.Application(application_id='org.synthetic.RecordPrep.StructuredSettings')
windows=[]
failures=[]
def schedule(delay,callback):
    def guarded():
        try:return callback()
        except Exception as exc:
            import traceback
            traceback.print_exc();failures.append(type(exc).__name__)
            app.quit();return GLib.SOURCE_REMOVE
    GLib.timeout_add(delay,guarded)
def run(*_):
    parent=Adw.ApplicationWindow(application=app)
    store=api.ProfileStore('recordprep',config_root=root/'config',data_root=root/'data')
    with patch('recordprep.profile_customization.initial_candidate',return_value=None):
        candidates=list(api.profile_catalog(store=store))
    b=candidates[0].snapshot
    w=ProfileEditorWindow(parent,editable_profile(b),store,expected_head=None,can_modify=lambda:True,
       preview=lambda s:preview(s,Path(__file__).resolve().parents[1]/'.pi'),on_saved=Mock(),candidates=candidates)
    windows.extend((parent,w));w.set_title('Synthetic RecordPrep — structured settings');w.present()
    w.nav_groups['Classification'].set_expanded(True)
    if '--interactive' in sys.argv:return
    def check():
        assert len(w._recognition_cards)==19
        assert 'first_report' in w._recognition_cards
        assert list(w.nav_rows)[:5]==['rt','ct','first-pages','report-naming','form-naming']
        assert 'date_hearing' not in w.pages
        assert w.nav_rows['report-naming'].get_title()=='Report Names'
        assert w.nav_rows['form-naming'].get_title()=='Form Names'
        assert not w.editor.resources['naming']['reports'][0]['guidance']
        assert not hasattr(w,'_catalog_previews')
        from recordprep.classification_profiles import classifier_prompt
        ct_prompt=classifier_prompt(w.editor.snapshot(),'ct')[0]
        assert 'Report Names' not in ct_prompt and 'Form Names' not in ct_prompt
        assert 'Check each page independently' in classifier_prompt(w.editor.snapshot(),'first_report')[0]
        assert not store.registry_path.exists()
        card,scroll=w._recognition_cards['RT_body'];card.set_expanded(True)
        buffer=scroll.get_child().get_buffer();buffer.insert_at_cursor(' Synthetic α {json}.')
        w._select_page('ct');w._select_page('rt');assert w._save()
        assert scroll.get_child().get_buffer() is buffer and buffer.get_can_undo()
        buffer.undo();assert w._dirty()
        for category,page in [('Classification','rt'),('Summaries','hearings-topics')]:
            w._select_page(page);w._inspect_prompts(category)
            inspector=w.prompt_inspector
            inspector.mode.set_selected(1)
            assert inspector.get_modal()
            assert inspector.text.get_buffer().get_char_count()>1000
            assert not inspector.status.get_text(),inspector.status.get_text()
            inspector.destroy()
        names=w.editor.resources['naming']['reports'];identity=names[0]['id'];key='topic:naming-reports:'+identity
        expander=w._topic_expanders[key];expander.set_expanded(True)
        editor=w._topic_editors[key];buf=editor.get_child().get_buffer();buf.insert_at_cursor(' Synthetic recognition clue.')
        assert w._save();assert w._topic_editors[key] is editor
        # Invalid Save preserves literal draft, selected revision and buffer.
        ref=w.editor.base.ref;names[0]['name']='';assert not w._save();assert w.editor.base.ref==ref
        w._reset().response('reset')
        assert w.editor.snapshot().files==b.files,w.message.get_text()
        assert w._topic_editors[key] is editor and w._recognition_cards['RT_body'][1] is scroll
        assert not w._dirty()
        print('Structured GTK acceptance PASS',flush=True)
        if '--screenshots' in sys.argv:
            destination=Path(sys.argv[sys.argv.index('--screenshots')+1]);destination.mkdir(parents=True,exist_ok=False)
            steps=[('light-home','home',None,900,800,False,11),
                   ('light-rt-narrow','rt','RT_body',480,760,False,11),
                   ('light-ct-narrow','ct','CT_report',480,760,False,11),
                   ('first-pages','first-pages','first_hearing',480,760,False,11),
                   ('report-names','report-naming','topic:naming-reports:'+names[0]['id'],480,760,False,11),
                   ('form-names','form-naming','topic:naming-forms:'+w.editor.resources['naming']['forms'][0]['id'],480,760,False,11),
                   ('dark-rt-narrow','rt','RT_body',480,760,True,11),
                   ('enlarged-first-pages','first-pages','first_hearing',480,760,False,18),
                   ('classification-inspector','ct','inspect-classification',480,760,False,11),
                   ('report-first-page','first-pages','first_report',480,760,False,11),
                   ('report-first-inspector','first-pages','inspect-report',700,760,False,11),
                   ('summary-inspector','hearings-topics','inspect-summary',900,800,False,11)]
            def next_step():
                if not steps:
                    w.destroy();parent.destroy();app.quit();return GLib.SOURCE_REMOVE
                name,page,card,width,height,dark,font=steps.pop(0)
                Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark else Adw.ColorScheme.FORCE_LIGHT)
                Gtk.Settings.get_default().set_property('gtk-font-name',f'Sans {font}')
                w.set_default_size(width,height)
                if page=='home':
                    w._navigation.view.pop_to_tag('home')
                    w.nav_groups['Summaries'].set_expanded(True)
                else:w._select_page(page)
                if card in w._recognition_cards:w._recognition_cards[card][0].set_expanded(True)
                if card in w._topic_expanders:w._topic_expanders[card].set_expanded(True)
                target=w
                if card and card.startswith('inspect-'):
                    w._inspect_prompts('Summaries' if card=='inspect-summary' else 'Classification')
                    target=w.prompt_inspector;target.set_default_size(width,height)
                    if card=='inspect-report':target.selector.set_selected(next(i for i,(key,_) in enumerate(target.tasks) if key=='first_report'))
                    target.mode.set_selected(1)
                def capture():
                    paintable=Gtk.WidgetPaintable.new(target);snapshot=Gtk.Snapshot()
                    paintable.snapshot(snapshot,target.get_width(),target.get_height())
                    node=snapshot.to_node()
                    if node is None:
                        raise RuntimeError('No rendered GTK frame is available in this desktop session; screenshot/visual acceptance is incomplete.')
                    texture=target.get_renderer().render_texture(node,None)
                    texture.save_to_png(str(destination/(name+'.png')))
                    print(name,target.get_width(),target.get_height(),flush=True)
                    if target is not w:target.destroy()
                    schedule(350,next_step);return GLib.SOURCE_REMOVE
                schedule(500,capture);return GLib.SOURCE_REMOVE
            schedule(350,next_step)
        else:
            w.destroy();parent.destroy();app.quit()
        return GLib.SOURCE_REMOVE
    schedule(500,check)
app.connect('activate',run)
raise SystemExit(app.run([]) or bool(failures))
