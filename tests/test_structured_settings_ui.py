"""Additional production GTK compatibility and retained-card checks."""
import copy
import unittest
from unittest.mock import Mock, patch
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_workflows import ProfileEditor
from recordprep.settings_navigation import descendants
from test_structured_classification import bundle, legacy, ROOT
import test_unified_settings as unified
from test_unified_settings import Gtk, Adw, drain, dispose


class StructuredSettingsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Gtk.init_check():raise unittest.SkipTest('GTK display unavailable')
        Adw.init();cls.app=Adw.Application(application_id='org.synthetic.RecordPrep.StructuredUITests');cls.app.register(None)
    setUp=unified.UnifiedSettingsTests.setUp
    profile_window=unified.UnifiedSettingsTests.profile_window

    def test_unknown_legacy_prose_is_not_split_and_reset_retains_summaries(self):
        w,store=self.profile_window();e=ProfileEditor(legacy())
        raw='Custom {literal} RT guidance; do not split me.'
        e.resources['classification_tasks']['rt']=raw
        e.resources['naming']['report_guidance']+=' Unrecognized custom recognition.'
        old=e.snapshot();w.editor=editable_profile(old);w._render()
        self.assertEqual(w.editor.manifest['schema_version'],6)
        self.assertEqual(w.editor.resources['classification_tasks']['rt'],raw)
        self.assertEqual(w.editor.resources['naming'],old.resource('naming'))
        topic='topic:hearings:'+w.editor.resources['hearings'][0]['id']
        scroll=w._topic_editors[topic];card=w._topic_expanders[topic];card.set_expanded(True)
        self.assertTrue(w._save());previous=w.editor.base.ref
        self.assertEqual(store.load_profile_snapshot(previous).resource('classification_tasks')['rt'],raw)
        w._reset().response('reset');drain()
        self.assertEqual(w.editor.snapshot().files,bundle().files,w.message.get_text())
        self.assertIs(w._topic_editors[topic],scroll);self.assertIs(w._topic_expanders[topic],card)
        self.assertTrue(card.get_expanded());self.assertEqual(len(w._recognition_cards),19)
        self.assertEqual(store.load_profile_snapshot(previous).resource('classification_tasks')['rt'],raw)

    def test_mixed_exact_resource_draft_and_literal_compatibility_inspection(self):
        e=ProfileEditor(legacy());e.resources['naming']['report_guidance']+=' Custom.'
        old=e.snapshot();draft=editable_profile(old)
        self.assertEqual(draft.resources['classification_tasks']['schema_version'],3)
        self.assertEqual(draft.resources['naming'],old.resource('naming'))
        self.assertEqual(draft.manifest['schema_version'],6)
        self.assertEqual(old.resource('classification_tasks').get('schema_version'),None)

    def test_catalog_editing_keeps_ct_independent_and_first_pages_has_four_cards(self):
        from recordprep.classification_profiles import classifier_prompt
        w,store=self.profile_window()
        self.assertEqual(w.nav_rows['report-naming'].get_title(),'Report Names')
        self.assertEqual(w.nav_rows['form-naming'].get_title(),'Form Names')
        before=classifier_prompt(w.editor.snapshot(),'ct')
        self.assertIn('first_report',w._recognition_cards)
        self.assertFalse(hasattr(w,'_catalog_previews'))
        for kind,key in (('report','CT_report'),('form','CT_form')):
            w._select_page('ct');w._recognition_cards[key][0].set_expanded(True)
            rule_scroll=w._recognition_cards[key][1]
            rule_text=w.editor.resources['classification_tasks']['page_types']['ct'][key]
            self.assertFalse(any(isinstance(x,Gtk.Button) and (x.get_label() or '').startswith('Edit ')
                                 for x in descendants(w._recognition_cards[key][0])))
            w._select_page(kind+'-naming')
            card=w.editor.resources['naming'][kind+'s'][0]
            detail='topic:naming-'+kind+'s:'+card['id']
            w._topic_expanders[detail].set_expanded(True);drain()
            entry=next(x for x in descendants(w.pages[kind+'-naming']) if isinstance(x,Gtk.Entry) and x.get_text()==card['name'])
            entry.set_text('Synthetic '+kind)
            editor=w._topic_editors[detail];editor.get_child().get_buffer().set_text('Literal α {recognition} clue.')
            self.assertIs(w._recognition_cards[key][1],rule_scroll)
            self.assertEqual(w.editor.resources['classification_tasks']['page_types']['ct'][key],rule_text)
            self.assertFalse(store.registry_path.exists())
            self.assertEqual(classifier_prompt(w.editor.snapshot(),'ct'),before)
        self.assertTrue(w._save())
        saved=store.load_profile_snapshot(w.editor.base.ref)
        self.assertEqual(saved.resource('naming')['reports'][0]['name'],'Synthetic report')
        self.assertEqual(classifier_prompt(saved,'ct'),before)

    def test_report_start_save_and_reset_keep_recognition_buffers_and_undo(self):
        w,_store=self.profile_window()
        rule=w._recognition_cards['CT_report'][1]
        start=w._recognition_cards['first_report'][1]
        buffer=start.get_child().get_buffer()
        w._select_page('first-pages');w._recognition_cards['first_report'][0].set_expanded(True)
        literal='Literal α {report} {{quote:source}} opening.'
        buffer.insert_at_cursor(literal)
        self.assertIn(literal,w.editor.resources['classification_tasks']['first_pages']['first_report'])
        self.assertTrue(w._save(),w.message.get_text())
        self.assertIs(w._recognition_cards['first_report'][1],start)
        self.assertTrue(buffer.get_can_undo())
        buffer.undo();self.assertTrue(w._dirty())
        w._reset().response('reset');drain()
        self.assertIs(w._recognition_cards['first_report'][1],start)
        self.assertIs(w._recognition_cards['CT_report'][1],rule)
        self.assertEqual(w.editor.resources['classification_tasks']['first_pages']['first_report'],
                         bundle().resource('classification_tasks')['first_pages']['first_report'])
        self.assertFalse(w._dirty())

    def test_complete_legacy_naming_buffer_and_invalid_inspection(self):
        import json
        from recordprep.classification_profiles import classifier_prompt
        root = self.root
        for version in (1, 2):
            with self.subTest(version=version):
                self.root = root / str(version)
                self.root.mkdir()
                w, store = self.profile_window()
                from recordprep.profile_integration import preview
                w.preview = lambda snapshot: preview(snapshot,ROOT/'.pi')
                e = ProfileEditor(legacy())
                naming = ({'mode': 'approved_titles', 'report_titles': ['Synthetic report'],
                           'form_titles': ['Synthetic form'], 'guidance': 'Literal matching guidance.'}
                          if version == 1 else json.loads((ROOT/'tests/fixtures/naming-v2/california_dependency.json').read_bytes()))
                naming['guidance' if version == 1 else 'report_guidance'] += ' Unknown synthetic guidance.'
                e.resources['naming'] = naming
                w.editor = editable_profile(e.snapshot()); w._render()
                buffer = w._legacy_naming_buffer
                self.assertIsNotNone(buffer)
                for page in ('report-naming','form-naming'):
                    w._select_page(page)
                    views = [x for x in descendants(w.pages[page]) if isinstance(x,Gtk.TextView)]
                    self.assertEqual(len(views),1); self.assertIs(views[0].get_buffer(),buffer)
                value = copy.deepcopy(naming)
                value['report_titles'] = ['Changed synthetic report']
                if version == 1:
                    value['form_titles'] = ['Changed synthetic form']
                else:
                    value['form_rules'] = [{'name':'Changed synthetic form','title':'Changed synthetic heading','code':'SYN-2'}]
                    value['form_guidance'] = 'Require the synthetic heading and code on the supplied first page.'
                text = json.dumps(value,ensure_ascii=False,indent=2)
                w._replace_buffer(buffer,text)
                buffer.select_range(buffer.get_iter_at_offset(5),buffer.get_iter_at_offset(2))
                w._select_page('ct'); w._select_page('report-naming')
                self.assertTrue(buffer.get_can_undo())
                self.assertTrue(w._save(),w.message.get_text())
                saved = store.load_profile_snapshot(w.editor.base.ref); files = saved.files
                self.assertEqual(saved.resource('naming'),value)
                self.assertIn('Changed synthetic report',classifier_prompt(saved,'report')[0])
                from recordprep.document_naming import compile_naming_profile
                from recordprep.ui import main_window as ui
                from types import SimpleNamespace as NS
                image = self.root/'0001.png'; image.write_bytes(b'synthetic page image')
                worker = NS(_raise_if_stop_requested=lambda:None,_extract_response_text=lambda p:p,_extract_json_payload=lambda p:p)
                for kind in ('report','form'):
                    contract = compile_naming_profile(saved,kind)
                    name = 'Changed synthetic '+kind
                    response = {'name':name,**({'date':'March 5, 2030'} if kind == 'report' else {})}
                    self.assertEqual(contract.normalize(response).name,name)
                    self.assertEqual(contract.normalize({'name':'Unapproved synthetic name','date':''}).name,'')
                    captured = []
                    def post(request,**kwargs):
                        captured.append(json.loads(request.data)); return json.dumps(response)
                    with patch.object(ui,'_post_json_with_retries',side_effect=post):
                        ui.RecordPrepWindow._classify_image(worker,{'api_url':'https://synthetic.invalid','model_id':'offline','prompt':'INACTIVE_CANARY',
                            'profile_snapshot':saved,'profile_kind':kind},'0001.txt',image)
                    self.assertEqual(captured[0]['messages'][0]['content'],contract.prompt)
                    if version == 2 and kind == 'form':
                        self.assertIn('SYN-2',contract.prompt)
                        self.assertIn('Changed synthetic heading',contract.prompt)
                baseline = w._saved_state
                w._replace_buffer(buffer,'{ invalid raw naming α')
                self.assertFalse(w._save()); self.assertEqual(w._saved_state,baseline)
                w._inspect_prompts('Classification'); inspector = w.prompt_inspector
                self.addCleanup(dispose,inspector)
                inspector.mode.set_selected(1)
                self.assertIsNone(inspector.snapshot)
                self.assertIn('invalid',inspector.status.get_text().lower())
                displayed = inspector.text.get_buffer().get_text(*inspector.text.get_buffer().get_bounds(),True)
                self.assertIn('{ invalid raw naming α',displayed)
                self.assertNotIn('Changed synthetic report',displayed)
                # Inspector is frozen even if its parent draft is changed by a test.
                buffer.undo()
                self.assertFalse(w._legacy_naming_error)
                inspector._refresh()
                self.assertIn('invalid',inspector.status.get_text().lower())
                self.assertEqual(saved.files,files)
                inspector.destroy(); drain()
                self.assertFalse(w._dirty())
                self.assertTrue(w._save())
                buffer.undo(); self.assertTrue(w._dirty())
                self.assertTrue(w._close_request())
                w.unsaved_dialog.response('keep'); drain()
                self.assertTrue(w.get_visible())
                # Reset deliberately replaces the compatibility resource; no
                # discarded raw buffer may leak back into current inspection.
                w._reset().response('reset'); drain()
                self.assertIsNone(w._legacy_naming_buffer)
                self.assertEqual(w.editor.snapshot().files,bundle().files)
                self.assertEqual(store.load_profile_snapshot(saved.ref).files,files)
                w._inspect_prompts('Classification'); current = w.prompt_inspector
                self.addCleanup(dispose,current)
                current.mode.set_selected(1)
                self.assertIsNotNone(current.snapshot)
                self.assertFalse(current.status.get_text(),current.status.get_text())

    def test_frozen_invalid_inspector_does_not_discover_or_write(self):
        w,store=self.profile_window()
        w.editor.resources['classification_tasks']['page_types']['rt']['RT_body']=''
        before=copy.deepcopy(w.editor.resources)
        with patch('recordprep.profile_integration.preview',side_effect=AssertionError('persistence preview')),patch('recordprep.pi_runtime.available_pi_models',side_effect=AssertionError('model discovery')):
            w._select_page('rt');w._inspect_prompts('Classification');inspector=w.prompt_inspector
            self.addCleanup(dispose,inspector)
            self.assertTrue(inspector.get_modal());self.assertEqual(inspector.mode.get_selected(),0)
            inspector.mode.set_selected(1)
            self.assertIn('validation issue',inspector.status.get_text())
            self.assertEqual(w.editor.resources,before);self.assertFalse(store.registry_path.exists())
            self.assertEqual(inspector.resources,before)
