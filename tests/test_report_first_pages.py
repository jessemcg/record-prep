"""Report-start acceptance using production workers, synthetic pages and offline HTTP."""
import base64
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from recordprep.case_profiles import apply_case_profile
from recordprep.classification_profiles import KINDS, classifier_prompt, component, normalize_classifier, ClassifierResponseError
from recordprep.document_naming import compile_naming_profile
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_contract import ProfileError, LEGACY_CLASSIFICATION_TASKS
from recordprep.profile_workflows import ProfileEditor
from recordprep.report_pages import REPORT_TYPES, report_detection_mode, report_ranges, report_check_signature
from recordprep.transcript_layout import apply_manual_override
import test_classification_profiles as classification_fixtures
from test_profile_generation import changed
from test_structured_classification import bundle, legacy, ROOT


class ReportContractTests(unittest.TestCase):
    def test_fourth_task_and_stage_local_fingerprints(self):
        b=bundle();self.assertEqual(b.manifest['schema_version'],8)
        self.assertEqual(b.resource('classification_tasks')['schema_version'],3)
        before={stage:component(b,stage) for stage in ('basic','advanced','corrected','dates','names')}
        e=ProfileEditor(b);e.resources['classification_tasks']['first_pages']['first_report']+=' Literal α {x} {{quote:source}}'
        s=e.snapshot()
        for stage,value in before.items():self.assertEqual(component(s,stage)!=value,stage in ('advanced','corrected'))
        for answer in ('YES','no'):
            self.assertEqual(normalize_classifier({'first_page':answer},'first_report'),{'first_page':answer.lower()})
        for answer in ('','unknown','CT_report_first_page'):
            with self.assertRaises(ValueError):normalize_classifier({'first_page':answer},'first_report')
        for answer in ('CT_report_first_page','RT_body_first_page'):
            with self.assertRaises(ClassifierResponseError):normalize_classifier({'page_type':answer},'ct')

    def test_schema7_and_custom_v2_remain_literal_and_use_fixed_fallback(self):
        e=ProfileEditor(bundle());e.manifest['schema_version']=7
        e.resources['classification_tasks']=json.loads((ROOT/'recordprep/resources/profile_baselines/dependency-1.7.0-shared/classification-v2.json').read_bytes())
        e.resources['classification_tasks']['page_types']['ct']['CT_report']='Custom footer-only recognition α {x} {{quote:source}}'
        old=e.snapshot();before=old.files
        self.assertIn('Custom footer-only',classifier_prompt(old,'ct')[0])
        self.assertNotIn('Detention Report',classifier_prompt(old,'ct')[0])
        self.assertIn('Check each page independently',classifier_prompt(old,'first_report')[0])
        draft=editable_profile(old)
        self.assertEqual(draft.manifest['schema_version'],8)
        self.assertEqual(draft.resources['classification_tasks']['schema_version'],3)
        self.assertEqual(draft.resources['classification_tasks']['page_types'],old.resource('classification_tasks')['page_types'])
        self.assertEqual(old.files,before)
        for mutation in ('missing','extra','blank','boolean','legacy-schema'):
            bad=ProfileEditor(bundle())
            if mutation=='missing':del bad.resources['classification_tasks']['first_pages']['first_report']
            if mutation=='extra':bad.resources['classification_tasks']['first_pages']['first_unknown']='No'
            if mutation=='blank':bad.resources['classification_tasks']['first_pages']['first_report']=' '
            if mutation=='boolean':bad.resources['classification_tasks']['schema_version']=True
            if mutation=='legacy-schema':bad.manifest['schema_version']=7
            with self.subTest(mutation=mutation),self.assertRaises(ProfileError):bad.snapshot()

    def test_unknown_flat_prose_and_inert_dates_survive_editing_with_new_editable_task(self):
        e=ProfileEditor(legacy())
        e.resources['classification_tasks']['ct']+=' Custom whole-task prose {x} α {{quote:source}}'
        e.resources['classification_tasks']['date_hearing']='Literal inert private date guidance.'
        old=e.snapshot();before=old.files
        draft=editable_profile(old);tasks=draft.resources['classification_tasks']
        self.assertEqual(tasks['schema_version'],3)
        for key in LEGACY_CLASSIFICATION_TASKS:self.assertEqual(tasks[key],old.resource('classification_tasks')[key])
        self.assertIn('first_report',tasks)
        tasks['first_report']='A custom report opening {literal} α'
        saved=draft.snapshot()
        self.assertIn(tasks['first_report'],classifier_prompt(saved,'first_report')[0])
        self.assertEqual(classifier_prompt(saved,'ct'),classifier_prompt(old,'ct'))
        self.assertEqual(classifier_prompt(saved,'date_hearing'),classifier_prompt(old,'date_hearing'))
        self.assertEqual(old.files,before)

    def test_report_flags_are_complete_or_fully_historical(self):
        historical=[{'page_type':'CT_report'}]*2
        self.assertFalse(report_detection_mode(historical))
        with self.assertRaisesRegex(ValueError,'Run Advanced'):report_detection_mode(historical,required=True)
        modern=[{'page_type':'CT_report_first_page','report_first_page':'yes'},
                {'page_type':'CT_report','report_first_page':'no'}]
        self.assertTrue(report_detection_mode(modern))
        for bad in (modern+[{'page_type':'CT_report'}],
                    [{'page_type':'CT_report_first_page'}],
                    [{'page_type':'CT_report','report_first_page':'yes'}],
                    [{'page_type':'CT_report','report_first_page':False}]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):report_detection_mode(bad)
        self.assertNotEqual(report_check_signature(historical),report_check_signature(modern))
        self.assertEqual(report_check_signature([]),[])

    def test_gaps_separators_orphans_and_adjacent_starts_are_not_healed(self):
        entries=[('0001.txt','ct_report',1),('0002.txt','ct_report_first_page',2),
                 ('0003.txt','ct_report_first_page',3),('0005.txt','ct_report',5),
                 ('0006.txt','ct_form',6),('0007.txt','ct_report_first_page',7)]
        ranges=report_ranges(entries,0,modern=True)
        self.assertEqual([(r.start_file,r.end_file,r.start_detected) for r in ranges],
                         [('0001.txt','0001.txt',False),('0002.txt','0002.txt',True),
                          ('0003.txt','0003.txt',True),('0005.txt','0005.txt',False),('0007.txt','0007.txt',True)])
        self.assertEqual(report_ranges(entries,7,modern=True),[])
        legacy_ranges=report_ranges([('0001.txt','ct_report',1),('0002.txt','ct_report',2)],0,modern=False)
        self.assertEqual([(r.start_file,r.end_file,r.start_detected) for r in legacy_ranges],[('0001.txt','0002.txt',True)])


class ReportPipelineTests(unittest.TestCase):
    def setUp(self):
        from recordprep.ui import main_window as ui
        self.ui=ui;fixture=classification_fixtures.ClassificationProfileTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.root=fixture.root;self.store=fixture.store
        n=fixture.profile.resource('naming')
        n['report_guidance']+='\n- **Second Approved Report**\n'
        n['form_guidance']+='\n- **Approved Form**\n'
        self.profile=changed(fixture.profile,'naming',n)
        self.store.accept_profile(self.profile,expected_previous_digest=fixture.profile.ref.content_sha256)
        apply_case_profile(self.root,self.profile.ref,expected_previous=fixture.profile.ref,store=self.store)
        self.settings=fixture.settings.copy()
        self.worker=SimpleNamespace(_resolve_case_root=lambda:self.root,_raise_if_stop_requested=lambda:None,
            _validate_vision_settings=lambda s:None,_classifier_worker_count=lambda s:1,selected_pdfs=[],
            _safe_update_manifest=Mock(),show_toast=Mock(),_finish_step=Mock(),_stop_status_if_idle=Mock(),
            _stop_button_if_idle=Mock(),_update_toc_button=Mock(),_extract_response_text=lambda p:p,_extract_json_payload=lambda p:p)
        for name in ('step_two_row','step_advanced_row','step_correct_advanced_row','step_dates_row','step_names_row',
                     'step_six_row','step_seven_row','step_correct_boundaries_row'):
            setattr(self.worker,name,Mock())
        self.worker._append_boundary_entry=lambda *a:ui.RecordPrepWindow._append_boundary_entry(self.worker,*a)
        self.worker._classify_image=lambda *a:ui.RecordPrepWindow._classify_image(self.worker,*a)
        self.worker._classify_image_with_page_type=lambda *a:ui.RecordPrepWindow._classify_image_with_page_type(self.worker,*a)
        self.worker._run_classifier_jobs=lambda jobs,workers:[f(*args) for f,args in jobs]
        self.kinds={};self.starts=set();self.names={};self.calls=[];self.first_answer=None
        self.prompts={classifier_prompt(self.profile,kind)[0]:kind for kind in KINDS}
        for kind in ('report','form'):self.prompts[compile_naming_profile(self.profile,kind).prompt]=kind
        for target in ('load_classifier_settings','load_advanced_classify_settings','load_classify_dates_settings','load_classify_names_settings'):
            p=patch.object(ui,target,return_value=self.settings);p.start();self.addCleanup(p.stop)
        p=patch.object(ui.GLib,'idle_add',side_effect=lambda f,*a:f(*a));p.start();self.addCleanup(p.stop)
        p=patch.object(ui,'_post_json_with_retries',side_effect=self.respond);p.start();self.addCleanup(p.stop)

    def prepare(self,kinds,starts,names):
        self.kinds=dict(enumerate(kinds,1));self.starts=set(starts);self.names=names
        for number in self.kinds:
            (self.root/f'text_pages/{number:04d}.txt').write_text(f'Synthetic source page {number}.')
            (self.root/f'image_pages/{number:04d}.png').write_bytes(f'image {number}'.encode())
        apply_manual_override(self.root,mode='ct_only')

    def respond(self,request,**kwargs):
        payload=json.loads(request.data);task=self.prompts[payload['messages'][0]['content']]
        image=payload['messages'][1]['content'][0]['image_url']['url'].split(',',1)[1]
        number=int(base64.b64decode(image).decode().split()[-1]);self.calls.append((task,number))
        if task=='ct':return json.dumps({'page_type':self.kinds[number]})
        if task.startswith('first_'):
            return json.dumps({'first_page':self.first_answer if self.first_answer is not None else
                               'yes' if number in self.starts else 'no'})
        if task=='report':return json.dumps({'name':self.names.get(number,''),'date':'January 2, 2026'})
        if task=='form':return json.dumps({'name':self.names.get(number,'')})
        return json.dumps({'date':''})

    def run_steps(self,*steps):
        for step in steps:
            self.assertTrue(getattr(self.ui.RecordPrepWindow,step)(self.worker),self.worker.show_toast.call_args_list)

    def rows(self,stage):
        from recordprep.classification_profiles import output_names
        path=self.root/'classification'/output_names(stage)[1]
        return [json.loads(line) for line in path.read_text().splitlines()]

    def write_rows(self,stage,rows):
        from recordprep.classification_profiles import output_names
        path=self.root/'classification'/output_names(stage)[1]
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows));return path

    def test_adjacent_named_unnamed_repeated_reports_and_forms_reach_only_correct_work_items(self):
        self.prepare(['CT_report']*6+['CT_form']+['CT_report']*2,{1,3,5,6,7,8},
                     {1:'Independent Report',3:'Not approved',5:'Independent Report',6:'Second Approved Report',
                      7:'Approved Form',8:'Also unapproved'})
        source={p:(p.read_bytes(),p.stat().st_mtime_ns) for folder in ('image_pages','text_pages') for p in (self.root/folder).iterdir()}
        self.run_steps('_run_step_two','_run_step_advanced','_run_step_correct_advanced','_run_step_dates')
        dated=self.rows('dates')
        for row in dated:
            if row['page_type'].lower() in REPORT_TYPES:
                row.update(name='Inherited old title',report_name='Inherited alias',date='January 1, 2000')
        self.write_rows('dates',dated)
        self.run_steps('_run_step_names','_run_step_six','_run_step_seven','_run_step_correct_boundaries')
        self.assertEqual([n for task,n in self.calls if task=='first_report'],[1,2,3,4,5,6,8,9])
        self.assertEqual([n for task,n in self.calls if task=='report'],[1,3,5,6,8])
        self.assertEqual([n for task,n in self.calls if task=='form'],[7])
        rows=self.rows('names')
        for n in (2,4,9):
            self.assertFalse(rows[n-1].get('name'));self.assertNotIn('report_name',rows[n-1]);self.assertNotIn('date',rows[n-1])
        for n in (3,8):self.assertFalse(rows[n-1].get('name'))
        bounds=json.loads((self.root/'artifacts/report_boundaries.json').read_text())
        self.assertEqual([(x['start_page'],x['end_page']) for x in bounds],[('0001','0002'),('0005','0005'),('0006','0006')])
        toc=(self.root/'artifacts/toc.txt').read_text();self.assertIn('Approved Form 0007',toc)
        self.assertEqual(toc.count('Independent Report'),2);self.assertNotIn('0003',toc);self.assertNotIn('0008',toc)
        from recordprep.summary_agents import build_work_items,ExtractionConfig,item_source_payload
        items=build_work_items(self.root,ExtractionConfig('reports','',profile=self.profile))
        self.assertEqual([(x.start_page,x.end_page) for x in items],[(1,2),(5,5),(6,6)])
        self.assertNotIn('Synthetic source page 3.',item_source_payload(items[0],self.root/'text_pages',{}))
        self.assertEqual(source,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in source})

    def test_basic_keeps_one_page_form_separator(self):
        self.prepare(['CT_report','CT_form','CT_report'],{1,2,3},{1:'Independent Report',2:'Approved Form',3:'Second Approved Report'})
        self.run_steps('_run_step_two')
        self.assertEqual([row['page_type'] for row in self.rows('basic')],['CT_report','CT_form','CT_report'])
        self.run_steps('_run_step_advanced','_run_step_correct_advanced','_run_step_dates','_run_step_names','_run_step_seven')
        bounds=json.loads((self.root/'artifacts/report_boundaries.json').read_text())
        self.assertEqual([(r['start_page'],r['end_page']) for r in bounds],[('0001','0001'),('0003','0003')])

    def test_missed_start_is_not_inferred_and_consecutive_positive_starts_are_not_collapsed(self):
        self.prepare(['CT_report']*3,{2,3},{1:'Independent Report',2:'Independent Report',3:'Independent Report'})
        self.run_steps('_run_step_two','_run_step_advanced','_run_step_correct_advanced','_run_step_dates','_run_step_names','_run_step_six','_run_step_seven','_run_step_correct_boundaries')
        self.assertEqual([n for task,n in self.calls if task=='report'],[2,3])
        bounds=json.loads((self.root/'artifacts/report_boundaries.json').read_text())
        self.assertEqual([(r['start_page'],r['end_page']) for r in bounds],[('0002','0002'),('0003','0003')])
        self.assertTrue(any('undetected report fragments' in str(call) for call in self.worker.show_toast.call_args_list))

    def test_old_or_partial_checks_block_new_naming_before_any_request_or_publication(self):
        self.prepare(['CT_report']*2,{1},{1:'Independent Report'})
        old=[{'file_name':f'{i:04d}.txt','page_type':'CT_report','name':'Historical title'} for i in (1,2)]
        dated=self.write_rows('dates',old);named=self.write_rows('names',old)
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in (dated,named)}
        self.assertFalse(self.ui.RecordPrepWindow._run_step_names(self.worker))
        self.assertEqual(self.calls,[])
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before})
        self.assertTrue(any('Run Advanced' in str(call) for call in self.worker.show_toast.call_args_list))
        self.run_steps('_run_step_six','_run_step_seven')  # Historical consumers remain read-only compatible.
        artifacts=[self.root/'artifacts'/name for name in ('toc.txt','report_boundaries.json','hearing_boundaries.json','minutes_boundaries.json')]
        before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in artifacts}
        partial=copy.deepcopy(old);partial[0].update(page_type='CT_report_first_page',report_first_page='yes')
        self.write_rows('names',partial)
        self.assertFalse(self.ui.RecordPrepWindow._run_step_six(self.worker))
        self.assertFalse(self.ui.RecordPrepWindow._run_step_seven(self.worker))
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before})

    def test_invalid_report_response_preserves_prior_advanced_output(self):
        self.prepare(['CT_report'],{1},{1:'Independent Report'});self.run_steps('_run_step_two')
        previous=self.write_rows('advanced',[{'file_name':'0001.txt','page_type':'CT_report'}])
        before=(previous.read_bytes(),previous.stat().st_mtime_ns);self.first_answer='unclear'
        self.assertFalse(self.ui.RecordPrepWindow._run_step_advanced(self.worker))
        self.assertEqual(before,(previous.read_bytes(),previous.stat().st_mtime_ns))

    def test_unassigned_old_checkpoints_cannot_skip_new_checks_or_reuse_old_run_names(self):
        self.root=self.root/'unassigned'
        for directory in ('text_pages','image_pages','classification'):(self.root/directory).mkdir(parents=True)
        self.prepare(['CT_report']*3,{1,3},{3:'Independent Report'})
        old=[{'file_name':f'{i:04d}.txt','page_type':'CT_report','name':'Inherited title','date':'January 1, 2000'} for i in (1,2,3)]
        for stage in ('basic','advanced','dates','names'):self.write_rows(stage,old)
        self.worker._classify_image=Mock(side_effect=lambda settings,filename,image:
            {'file_name':filename,**({'first_page':'yes' if int(Path(filename).stem) in self.starts else 'no'}
             if settings.get('profile_kind')=='first_report' else
             {'name':self.names.get(int(Path(filename).stem),''),'date':'January 2, 2026'})})
        self.run_steps('_run_step_advanced','_run_step_correct_advanced','_run_step_dates','_run_step_names','_run_step_seven')
        self.assertEqual([row['report_first_page'] for row in self.rows('advanced')],['yes','no','yes'])
        first_calls=[c for c in self.worker._classify_image.call_args_list if c.args[0].get('profile_kind')=='first_report']
        self.assertEqual(len(first_calls),3)
        self.assertEqual([row['report_first_page'] for row in self.rows('dates')],['yes','no','yes'])
        named=self.rows('names');self.assertFalse(named[0].get('name'));self.assertFalse(named[1].get('name'))
        self.assertEqual(named[2]['name'],'Independent Report')
        bounds=json.loads((self.root/'artifacts/report_boundaries.json').read_text())
        self.assertEqual([(r['start_page'],r['end_page']) for r in bounds],[('0003','0003')])
        before=self.worker._classify_image.call_count
        self.run_steps('_run_step_advanced')
        self.assertEqual(self.worker._classify_image.call_count,before)  # A fully checked checkpoint is resumable.


if __name__=='__main__':unittest.main()
