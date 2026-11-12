"""Structured information accounting, pure composition, adapters and freshness."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from recordprep import practice_profiles as api
from recordprep.profile_contract import ProfileError, validate_contents, json_bytes, CLASSIFICATION_PAGE_TYPES
from recordprep.profile_workflows import ProfileEditor
from recordprep.classification_profiles import classifier_prompt, component, normalize_classifier, ClassifierResponseError
from recordprep.document_naming import compile_naming_profile
from recordprep.prompt_inspection import inspect_prompt, tool_audit, CLASSIFICATION_TASKS, SUMMARY_TASKS
from recordprep.structured_guidance import effective_resource
from recordprep.summary_profiles import compile_summary, draft_summary_guidance
from recordprep.summary_prompts import extraction_document, synthesis_document, minute_document

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'tests/fixtures/structured_classification_baseline'


def bundle():
    return api.bundled_profile_for_identity('recordprep', api.DEFAULT_PROFILE_ID)


def legacy():
    from test_practice_profiles import historical_snapshot
    e = ProfileEditor(historical_snapshot(bundle(), version=6))
    e.manifest['resources']['classification_tasks'] = 'classification-tasks.json'
    for name, path in [('classification_tasks','classification-tasks.json'),('naming','naming.json')]:
        e.resources[name] = json.loads((BASE/path).read_bytes())
    return e.snapshot()


class StructuredClassificationTests(unittest.TestCase):
    def test_information_accounting_and_summary_bytes(self):
        review = json.loads((ROOT/'docs/structured-classification-information-map.json').read_bytes())
        self.assertEqual(len(review['clauses']), 198)
        for file,digest in review['baseline_sha256'].items():
            self.assertEqual(hashlib.sha256((BASE/file).read_bytes()).hexdigest(), digest)
        from recordprep.recognition_contract import load_recognition
        contract = load_recognition()
        t = {'page_types': {side: dict(entries) for side, entries in contract.page_types},
             'first_pages': dict(contract.first_pages)}
        old = json.loads((BASE/'classification-tasks.json').read_bytes())
        for side, keys in CLASSIFICATION_PAGE_TYPES.items():
            self.assertEqual(set(t['page_types'][side]), set(keys))
        self.assertNotIn('classification_tasks', bundle().manifest['resources'])
        report=t['page_types']['ct']['CT_report']
        self.assertIn('prepared for or directed to the court',report)
        self.assertIn('continuation pages',report)
        self.assertIn('not judicial action',report)
        for card in bundle().resource('naming')['reports']:
            self.assertNotIn(card['name'],report)
        self.assertEqual(len(t['first_pages']), 5)
        self.assertNotIn('CFS 6.7', json.dumps(t))
        self.assertNotIn('DCFS 4216', json.dumps(t))
        for path in ('reports.json',):
            self.assertEqual(dict(bundle().files)[path], (BASE/path).read_bytes())
        self.assertNotIn('date_hearing', t)
        self.assertNotIn('apply in order', json.dumps(t))

    def test_names_and_form_evidence(self):
        from test_document_naming import BUNDLED_REPORT_TITLES, FORM_RULES
        b = bundle(); n = b.resource('naming')
        self.assertEqual(tuple(e['name'] for e in n['reports']), BUNDLED_REPORT_TITLES)
        self.assertEqual(len(n['forms']), 5)
        for card, (name,heading,code) in zip(n['forms'], (r for r in FORM_RULES if r[2] != 'JV-180')):
            self.assertEqual(card['name'],name)
            self.assertIn(heading,card['guidance']); self.assertIn(code,card['guidance'])
        self.assertNotIn('Parential', json.dumps(n))
        self.assertEqual(len(n['reports']), 1)
        self.assertIn('only the fallback when the document clearly qualifies', n['reports'][0]['guidance'])
        self.assertNotIn('Hearing Date near the DETENTION REPORT heading',compile_naming_profile(b,'report').prompt)
        for kind in ('report','form'):
            c=compile_naming_profile(b,kind)
            for name in c.allowed_names:
                self.assertEqual(c.normalize({'name':name,'date':'', 'rule_id':'report-agency'} if kind=='report' else {'name':name}).name,name)
            self.assertEqual(c.normalize({'name':'unapproved','date':'January 1, 2026'}).name,'')
        self.assertNotIn('CFS 6.7',compile_naming_profile(b,'report').allowed_names)

    def test_best_fit_and_canonical_order(self):
        from recordprep.recognition_contract import load_recognition
        b=bundle(); e=ProfileEditor(legacy())
        contract = load_recognition()
        for side in ('rt','ct'):
            before=classifier_prompt(b,side)[0]
            self.assertIn('Compare all category descriptions and choose the single best-supported fit.',before)
            for removed in ('Category order is organizational', 'Do not use first match',
                            'decision cascade, weights, early exits', 'preferred category',
                            'Category-specific exclusions remain', 'If legacy guidance contains ordering language'):
                self.assertNotIn(removed,before)
            descriptions=before.split('\n\nCategory Descriptions\n\n')
            self.assertEqual(len(descriptions),2)
            keys=CLASSIFICATION_PAGE_TYPES[side]
            self.assertTrue(descriptions[1].startswith(keys[0]+'\n'))
            self.assertTrue(descriptions[1].endswith(dict(contract.descriptions(side))[keys[-1]]))
            self.assertNotIn('apply in order',before); self.assertNotIn('Decision rule (in order)',before)
            self.assertNotIn('date_minute',before)
            e.resources['classification_tasks'][side] = 'RETIRED_PRIVATE_CANARY'
            self.assertEqual(before,classifier_prompt(e.snapshot(),side)[0])
        for value in ('CT_report','invented',''):
            with self.assertRaises(ClassifierResponseError): normalize_classifier({'page_type':value},'rt')
        self.assertEqual(normalize_classifier({'page_type':'rt_certificate'},'rt'),{'page_type':'RT_certificate'})

    def test_exact_adapters_preserve_original_reference(self):
        old=legacy(); before=old.files
        for kind,_ in CLASSIFICATION_TASKS:
            self.assertEqual(classifier_prompt(old,kind) == classifier_prompt(bundle(),kind), kind not in ('report', 'form'))
        self.assertEqual(old.files,before)
        e=ProfileEditor(old); e.resources['classification_tasks']['rt']+=' Custom prose.'
        value=effective_resource(e.resources['classification_tasks'],'classification_tasks')
        self.assertEqual(value,e.resources['classification_tasks'])
        self.assertNotIn('page_types',value)
        c=compile_naming_profile(old,'report')
        self.assertEqual(c.profile_ref,old.ref)

    def test_stage_local_inputs_and_inactive_dates(self):
        b=bundle(); baseline={s:component(b,s) for s in ('basic','advanced','dates','names')}
        e=ProfileEditor(legacy()); e.resources['classification_tasks']['rt']+=' literal {json} α'
        changed=e.snapshot()
        for stage in baseline:
            self.assertEqual(component(changed,stage) == baseline[stage], stage != 'names')
        # Historical adapters preserve their old empty-description naming catalog.
        self.assertEqual(component(changed,'names'),component(legacy(),'names'))
        old=legacy(); e=ProfileEditor(old)
        e.resources['classification_tasks']['date_hearing']='PRIVATE LEGACY DATE OVERRIDE'
        self.assertEqual(component(old,'dates'),component(e.snapshot(),'dates'))
        self.assertNotIn('PRIVATE LEGACY',classifier_prompt(e.snapshot(),'date_hearing')[0])
        from recordprep.ui import main_window as ui
        config={ui.CONFIG_KEY_CLASSIFY_DATES_HEARING_PROMPT:'INACTIVE_HEARING_CANARY',
                ui.CONFIG_KEY_CLASSIFY_DATES_MINUTE_PROMPT:'INACTIVE_MINUTE_CANARY'}
        before=dict(config)
        with patch.object(ui,'_read_config',return_value=config),patch.object(ui,'_write_config',side_effect=AssertionError('date config write')):
            fixed=ui.load_classify_dates_settings()
        self.assertEqual(config,before)
        self.assertEqual(fixed['hearing_prompt'],classifier_prompt(b,'date_hearing')[0])
        self.assertEqual(fixed['minute_prompt'],classifier_prompt(b,'date_minute')[0])
        n=ProfileEditor(b); n.resources['naming']['forms'][0]['name']='Changed form'
        self.assertNotEqual(component(b,'names'),component(n.snapshot(),'names'))
        for phase in ('extract','synthesize'):
            self.assertEqual(compile_summary(b,'hearings',phase).component_sha256,compile_summary(n.snapshot(),'hearings',phase).component_sha256)

    def test_invalid_structured_resources_fail_closed(self):
        for change in ('unknown','cross','empty','oversize','duplicate-id','duplicate-name'):
            from test_practice_profiles import historical_snapshot
            e=ProfileEditor(historical_snapshot(bundle(), version=8))
            if change=='unknown': e.resources['classification_tasks']['page_types']['rt']['RT_fake']='x'
            if change=='cross': e.resources['classification_tasks']['page_types']['rt']['CT_report']='x'
            if change=='empty': e.resources['classification_tasks']['first_pages']['first_hearing']=' '
            if change=='oversize': e.resources['classification_tasks']['page_types']['rt']['RT_body']='x'*8193
            if change=='duplicate-id': e.resources['naming']['forms'][1]['id']=e.resources['naming']['forms'][0]['id']
            if change=='duplicate-name': e.resources['naming']['forms'][1]['name']=e.resources['naming']['forms'][0]['name'].lower()
            with self.subTest(change=change),self.assertRaises(ProfileError):e.snapshot()

    def test_all_inspections_offline_literal_invalid_draft(self):
        e=ProfileEditor(bundle()); literal='α {"x": 1} {{quote:hearing:0001/orders/1}}'
        e.resources['naming']['reports'][0]['guidance']=literal
        e.resources['reports'][0]['guidance']=literal
        for task,_ in (*CLASSIFICATION_TASKS,*SUMMARY_TASKS):
            with self.subTest(task=task):
                view=inspect_prompt(e.resources,task,ROOT/'.pi',template=False,snapshot=e.snapshot())
                self.assertEqual(view.issues,())
                self.assertTrue(view.display_text())
        self.assertIn(literal,inspect_prompt(e.resources,'reports-extract',ROOT/'.pi',template=False).display_text())
        self.assertNotIn(literal,inspect_prompt(e.resources,'hearings-extract',ROOT/'.pi',template=False).display_text())
        self.assertNotIn(literal,inspect_prompt(e.resources,'rt',ROOT/'.pi',template=False).components[0][1])
        self.assertEqual(classifier_prompt(e.snapshot(),'rt')[0],inspect_prompt(e.resources,'rt',ROOT/'.pi',template=False).components[0][1])
        e.resources['naming']['reports'][0]['name']=''
        self.assertIn(json.dumps(literal,ensure_ascii=False)[1:-1],inspect_prompt(e.resources,'report',ROOT/'.pi',template=False).display_text())
        for phase in ('extract','synthesize','minutes'):
            text,issues=tool_audit(ROOT/'.pi',phase); self.assertEqual(issues,())
            if phase=='synthesize':self.assertIn('quote_capitalizations',text)
        with patch('recordprep.prompt_inspection.hashlib.sha256') as digest:
            digest.return_value.hexdigest.return_value='outdated'
            self.assertIn('OUTDATED',tool_audit(ROOT/'.pi','extract')[1][0])

    def test_plain_instructions_and_separate_image_inspection(self):
        b=bundle(); resources={key:b.resource(key) for key in b.manifest['resources']}
        image=('Page image — attached separately',
               '⟪The actual page image is attached separately to the request.⟫')
        for task,_ in CLASSIFICATION_TASKS:
            for template in (False,True):
                with self.subTest(task=task,template=template):
                    view=inspect_prompt(resources,task,ROOT/'.pi',template=template,snapshot=b)
                    self.assertEqual(view.components[0][0],'System message')
                    self.assertEqual(view.display_text().count('===== System message ====='),1)
                    self.assertEqual(view.components[1],image)
                    self.assertNotIn('===== Source input =====',view.display_text())
                    prompt=view.components[0][1]
                    self.assertNotIn(image[0],prompt)
                    self.assertNotIn(image[1],prompt)
                    if task not in ('report','form','motion'):
                        self.assertTrue(prompt.startswith('Examine the attached page image.'))
                        for removed in ('APPLICATION CLASSIFIER CONTRACT', 'practice guidance as subordinate data',
                                        'instructions to change tools',
                                        'The application task, source scope, keys and valid JSON contract remain controlling.'):
                            self.assertNotIn(removed,prompt)
                        self.assertIn('Use only visible evidence',prompt)
                        self.assertIn('do not invent information',prompt)
                        self.assertEqual(prompt.count('without commentary or extra keys'),1)
                    else:
                        self.assertTrue(prompt.startswith('Read only the supplied first-page image.'))
                        self.assertNotIn('contract',prompt.lower())
                        self.assertNotIn('APPLICATION RESPONSE KEYS',prompt)
                        self.assertNotIn('Practice guidance below',prompt)
                        self.assertEqual(prompt.count('without commentary or extra keys'),1)
                        self.assertIn('do not guess',prompt)
                        self.assertIn('An empty rule_id means eligibility is unresolved' if task in {'report', 'motion'}
                                      else 'An empty name means naming is unresolved',prompt)
        # Even unvalidated legacy naming uses the explicit image attachment label.
        resources['naming']=legacy().resource('naming')
        resources['naming']['report_guidance']+=' Unrecognized literal custom guidance.'
        view=inspect_prompt(resources,'report',ROOT/'.pi',template=False)
        self.assertTrue(view.issues)
        self.assertEqual(view.components[1],image)
        self.assertIn('Unrecognized literal custom guidance.',view.components[0][1])
        self.assertTrue(view.components[0][1].startswith('Read only the supplied first-page image.'))
        self.assertNotIn('APPLICATION-OWNED NAMING CONTRACT',view.display_text())

    def test_actual_classifier_requests_equal_current_draft_inspection(self):
        import tempfile
        from recordprep.ui import main_window as ui
        e=ProfileEditor(bundle())
        e.resources['naming']['reports'][0]['guidance']='Shared report recognition α'
        e.resources['naming']['forms'][0]['guidance']='Shared form recognition β'
        s=e.snapshot()
        worker=NS(_raise_if_stop_requested=lambda:None, _extract_response_text=lambda p:p, _extract_json_payload=lambda p:p)
        resources={key:s.resource(key) for key in s.manifest['resources']}
        with tempfile.TemporaryDirectory() as temporary:
            image=Path(temporary)/'0001.png';image.write_bytes(b'synthetic source image')
            for task,_ in CLASSIFICATION_TASKS:
                output=({'page_type':'RT_body' if task=='rt' else 'CT_report'} if task in ('rt','ct') else
                        {'first_page':'yes'} if task.startswith('first_') else {'date':''} if task.startswith('date_') else
                        {'name':'',**({'date':''} if task=='report' else {})})
                captured=[]
                def post(request,**kwargs):
                    captured.append(json.loads(request.data));return json.dumps(output)
                settings={'api_url':'https://synthetic.invalid','model_id':'synthetic','prompt':'INACTIVE_CANARY',
                          'profile_snapshot':s,'profile_kind':task}
                with patch.object(ui,'_post_json_with_retries',side_effect=post):
                    ui.RecordPrepWindow._classify_image(worker,settings,'0001.txt',image)
                self.assertEqual(captured[0]['messages'][0]['content'],inspect_prompt(resources,task,ROOT/'.pi',template=False,snapshot=s).components[0][1])
                self.assertEqual(captured[0]['messages'][1]['content'][0]['type'],'image_url')
                self.assertEqual('Shared report recognition α' in captured[0]['messages'][0]['content'], task=='report')
                self.assertEqual('Shared form recognition β' in captured[0]['messages'][0]['content'], task=='form')

    def test_summary_shared_guidance_and_launch_bytes(self):
        b=bundle()
        golden=json.loads((ROOT/'tests/fixtures/summary-inspection-golden.json').read_bytes())
        # Keep frozen historical fixtures intact. Hearings now use fixed neutral
        # topics and canonical skills. Current synthesis adds verified-only quote
        # selection and case-only display; report editorial examples live in SKILL.
        golden.update({
            'hearings-extract': {
                'component_sha256': '0e28b2e1917718b7a2a07e9a4143ae4d4321ff6e235d2f7147a1cb1eafdb4abd',
                'prompt_sha256': '0e28b2e1917718b7a2a07e9a4143ae4d4321ff6e235d2f7147a1cb1eafdb4abd',
                'staged_skill_sha256': '3c214b2bdd260641d8d992312b03bb52394a6d6e2f663cef2b1da80658682492'},
            'hearings-synthesize': {
                'component_sha256': '45ff809b583b88c3161eb66ee4d7dfcc6621f92c66d904bb000ecf1d5c7f450e',
                'prompt_sha256': '45ff809b583b88c3161eb66ee4d7dfcc6621f92c66d904bb000ecf1d5c7f450e',
                'staged_skill_sha256': '631398ad339c9984e31617a84774945ea2d391aaca98b39e7dce604bd060024a'},
            'reports-synthesize': {
                'component_sha256': '79bfcca8b3d4f9fb89e5035a79c56a42841e883d57a76741883d97c3185e91f4',
                'prompt_sha256': 'a978435792fa34f6542a57eda04dbe6fe6ef67e17a0f9d3555603885942e1666',
                'staged_skill_sha256': 'e333541348ae794ecf827d5e159fad2a1d8ced73410d8b41ee5eb38c51d57754'},
            'reports-extract': {
                'component_sha256': 'a4ca4965b769f7256618640fcb6ec17844450e83e8b940001f683c0f9d354710',
                'prompt_sha256': '99d0ed45fbe6d67ed15f68bd45cf2ae972d976d532a3606a7f870ced9dec2f86',
                'staged_skill_sha256': '4649e4af6c1a492987223d37db3e0102d7bf6f604ecec5c6cb4e928661c9cc41'},
        })
        for kind in ('hearings','reports'):
            for phase in ('extract','synthesize'):
                c=compile_summary(b,kind,phase)
                self.assertEqual(c.prompt,draft_summary_guidance(b.resource(kind) if kind == 'reports' else [],kind,phase))
                self.assertEqual(c.component_sha256,golden[kind+'-'+phase]['component_sha256'])
                self.assertEqual(hashlib.sha256(c.prompt.encode()).hexdigest(),golden[kind+'-'+phase]['prompt_sha256'])
                from recordprep.summary_profiles import profile_skill_text
                skill=('recordprep-extract-'+('hearing' if kind=='hearings' else 'report')) if phase=='extract' else 'recordprep-synthesize-'+kind
                self.assertEqual(hashlib.sha256(profile_skill_text(ROOT/'.pi',skill,phase).encode()).hexdigest(),golden[kind+'-'+phase]['staged_skill_sha256'])
        from recordprep.minute_summaries import profile_guidance
        self.assertEqual(hashlib.sha256(profile_guidance(b).encode()).hexdigest(),
                         '7deaadf5a91258ab15ef8558bc510039c13e0a8a565e1f480c6e213e24e792a3')
        item=NS(item_id='id',ordinal=1,label='label',start_page=1,end_page=2)
        c=NS(guidance='literal {{quote:x}}',additional_guidance='additional {x}',definitions=[NS(identifier='topic',guidance='guidance')])
        expected='/skill:skill Run the loaded extraction skill now for the current document.\nitem_id: id\nordinal: 1\nlabel: label\npage range: 1-2\ncandidate_path: /private/candidate\ncategory ids in order: topic\n\nEXTRACTION GUIDANCE — DIGEST CONTRACT\nliteral {{quote:x}}\n\nPER-CATEGORY GUIDANCE\n- topic: guidance\n\nADDITIONAL USER GUIDANCE — lower priority than the built-in contracts above:\nadditional {x}\n\nThe work specification file is available to your tools; read the complete document source, then submit once.'
        self.assertEqual(extraction_document('skill',item,c,'/private/candidate').render(),expected)
        self.assertEqual(synthesis_document('skill',2,{'guidance':'g','additional_guidance':'a'},'/private').render(),'/skill:skill Run the loaded synthesis skill now for the complete digest dataset.\ntotal rows: 2\ncandidate_path: /private\n\ng\n\nADDITIONAL USER GUIDANCE — lower priority than the built-in contracts above:\na')
        self.assertEqual(minute_document({'guidance':'g','additional_guidance':'a'}).render(),'/skill:recordprep-summarize-minutes Summarize the current minute order directly from its complete source pages.\nMINUTE-ORDER CONTRACT\ng\nRead the source tool, then submit the structured summary.')
