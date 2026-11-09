"""Fictional/offline delivery and publication checks, NOT model judgment tests."""
import base64
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from recordprep import practice_profiles as api, summary_agents as sa
from recordprep.classification_profiles import KINDS, classifier_prompt, component
from recordprep.document_naming import compile_naming_profile
from recordprep.profile_contract import ProfileError
from recordprep.profile_customization import initial_candidate
from recordprep.profile_workflows import ProfileEditor
from recordprep.prompt_inspection import inspect_prompt
from recordprep.recognition_contract import load_recognition
from recordprep.summary_profiles import compile_summary
from recordprep.transcript_layout import (draft_layout_payload, finalize_layout_draft,
    read_resolved_layout, resolve_rt_ct_split, TranscriptLayoutError)
import test_report_first_pages as pipeline
from test_dependency_report_naming import DATE_RULE

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = 'california-criminal-law'
TOPICS = ('criminal_charges_and_case_posture', 'defendant_circumstances',
          'allegation_interviews_and_evidence', 'prior_record_and_supervision',
          'victim_impact', 'sentencing_recommendation_and_reasons', 'custody_and_credits',
          'restitution_and_financial_obligations', 'disputed_issues_and_information_limits')
FORMS = ('information', 'complaint', 'indictment', 'verdict', 'notice-of-appeal',
         'abstract-of-judgment', 'jury-instructions', 'stipulation', 'jury-communication',
         'plea', 'counsel-waiver', 'probable-cause')


def criminal():
    return api.bundled_profile_for_identity(api.APPLICATION, IDENTITY)


def cases():
    return json.loads((ROOT/'tests/fixtures/criminal-documents-fictional.json').read_bytes())


class CriminalCatalogTests(unittest.TestCase):
    def test_shape_stable_ids_and_source_title_contracts(self):
        profile = criminal()
        self.assertEqual((profile.manifest['version'], profile.manifest['schema_version'],
                          profile.manifest['profile_api']), ('1.0.0', 14, 1))
        self.assertEqual(set(profile.manifest['resources']), {'naming', 'reports', 'policies', 'case_name'})
        self.assertEqual(profile.resource('policies'), {})
        naming = profile.resource('naming')
        self.assertEqual(naming['schema_version'], 5)
        self.assertEqual([r['id'] for r in naming['reports']], ['report-probation'])
        self.assertEqual([r['id'] for r in naming['forms']], ['form-'+f for f in FORMS])
        self.assertEqual(tuple(t['id'] for t in profile.resource('reports')), TOPICS)
        for kind in ('report', 'form'):
            contract = compile_naming_profile(profile, kind)
            self.assertEqual(contract.mode, 'matched_rules')
            for card in naming[kind+'s']:
                self.assertEqual(card['naming_mode'], 'source_title')
                extra = {'date':'January 02, 2026'} if kind == 'report' else {}
                for title in ('AMENDED SOURCE TITLE — COUNT 2', ''):
                    result = contract.normalize({'name':title, 'rule_id':card['id'], **extra})
                    self.assertEqual((result.name, result.rule_id), (title or card['name'], card['id']))
                    if kind == 'report': self.assertEqual(result.date, 'January 2, 2026')
                self.assertEqual(contract.normalize({'name':'', 'rule_id':'unknown', **extra}).name, '')
                view = inspect_prompt({k:profile.resource(k) for k in profile.manifest['resources']},
                                      kind, ROOT/'.pi', template=False, snapshot=profile)
                self.assertFalse(view.issues)
                self.assertEqual(view.components[0][1], contract.prompt)
        self.assertIn(DATE_RULE, compile_naming_profile(profile, 'report').prompt)

    def test_eligibility_and_topic_guardrails_delivered_without_new_methods(self):
        profile = criminal()
        report = compile_naming_profile(profile, 'report').prompt
        for text in ('short memoranda and one-page updates', 'no title is discernible',
                     'supplied first page', 'solely from probation stationery',
                     'victim-completed statements', 'police reports', 'motions/sentencing briefs',
                     'titles or dates match', 'leave the name empty'):
            self.assertIn(text, report)
        prompt = compile_summary(profile, 'reports', 'extract').prompt
        for text in ('conditional preplea', 'No defendant interview does not establish lack of remorse',
                     'proposed findings/orders at the end', 'Do not recalculate',
                     'reserved jurisdiction', 'appellate merit', 'no material responsive content'):
            self.assertIn(text, prompt)
        dependency = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        for stage in ('basic', 'advanced', 'dates'):
            self.assertEqual(component(profile, stage), component(dependency, stage))
        self.assertNotEqual(component(profile, 'names'), component(dependency, 'names'))
        for kind in ('hearings', 'motions'):
            for phase in ('extract', 'synthesize'):
                self.assertEqual(compile_summary(profile, kind, phase).prompt,
                                 compile_summary(dependency, kind, phase).prompt)
        # Never read/import legacy Dependency settings while resolving Criminal.
        with patch('recordprep.ui.main_window._read_config', side_effect=AssertionError('private config')):
            self.assertIsNone(initial_candidate(profile))

    def test_store_selection_personal_history_reset_and_stale_guards_for_both(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = api.ProfileStore(api.APPLICATION, config_root=root/'config', data_root=root/'data')
            catalog = api.profile_catalog(store=store, customization=lambda _:None)
            self.assertEqual([c.snapshot.ref.specialty_id for c in catalog], [api.DEFAULT_PROFILE_ID, IDENTITY])
            self.assertEqual(api.default_profile_candidate(store=store).ref, catalog[0].snapshot.ref)
            self.assertEqual(list(root.iterdir()), [])
            for entry in catalog:
                base = entry.snapshot
                registry = store.read_registry()
                original = store.managed_save(base, expected_head=None,
                    expected_default=registry['default'], personal=False, use_for_new_cases=True)
                self.assertFalse(next(c for c in api.profile_catalog(store=store, customization=lambda _:None)
                                      if c.snapshot.ref == original).personal)
                self.assertEqual(api.default_profile_candidate(store=store).ref, original)
                editor = ProfileEditor(base)
                editor.resources['naming']['reports'][0]['guidance'] += ' Synthetic personal change.'
                saved = editor.managed_save(store, expected_head=original.content_sha256,
                    expected_default=asdict(original), validate=lambda p:compile_naming_profile(p, 'report'),
                    can_modify=lambda:True)
                self.assertEqual(api.default_profile_candidate(store=store).ref, saved)
                with self.assertRaises(ProfileError):
                    store.managed_save(base, expected_head=original.content_sha256, expected_default=asdict(saved))
                with self.assertRaises(ProfileError):
                    store.delete_profile(saved, expected_default=asdict(saved))
                reset = api.bundled_profile_for_identity(api.APPLICATION, base.ref.specialty_id)
                store.managed_save(reset, expected_head=saved.content_sha256, expected_default=asdict(saved))
                self.assertEqual(store.load_profile_snapshot(original).files, base.files)
                self.assertIn('Synthetic personal change', str(store.load_profile_snapshot(saved).resource('naming')))
                self.assertEqual(api.default_profile_candidate(store=store).files, base.files)
                copy = ProfileEditor.create(base, 'Fictional copy '+base.ref.specialty_id).snapshot()
                self.assertEqual(copy.resource('naming'), base.resource('naming'))
                self.assertIsNone(api.bundled_profile_for_identity(api.APPLICATION, copy.ref.specialty_id))

    def test_historical_and_shared_bytes_unchanged(self):
        pins = {
            'resources/classification/recognition-v1.json':'4c564fc3a40fc01fecadce36cc01f91ea8b8732d6d0d07a214a033d73543fb8e',
            'resources/classification/recognition-v2.json':'6eab77900d4b5b22dba2b8ef6881d6a1b3d2f3e915c41b63ad0fdcbdcb3af7d0',
            'profile_contract.py':'19a0338331c5a924d28c386eb5ac488d163824e44fe186381fff3ccaef0fe35c',
            'profile_artifacts.py':'087bb081fcc96d5940513948f87c4a0eb710b11188966069db3f042fcb1f6784',
            'resources/practice_profiles/california_dependency/profile.json':'35770359f38ae86b58008f36d976ccd73ca1aa7e8223bd5752e41decf0d52e0b',
            'resources/practice_profiles/california_dependency/naming.json':'87908963abe477eabd160363a4c8f4cfb9f3804247e4de7b47e52a7e57f03af9',
        }
        for path, digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/'recordprep'/path).read_bytes()).hexdigest(), digest, path)


class CriminalPipelineTests(unittest.TestCase):
    # Reuse production-worker harness, without inheriting or duplicating its tests.
    setUp = pipeline.ReportPipelineTests.setUp
    prepare = pipeline.ReportPipelineTests.prepare
    respond = pipeline.ReportPipelineTests.respond
    rows = pipeline.ReportPipelineTests.rows
    run_steps = pipeline.ReportPipelineTests.run_steps

    def test_scripted_criminal_documents_boundaries_correction_and_digest_runner(self):
        import pymupdf
        self.profile = criminal()
        self.store.accept_profile(self.profile, expected_previous_digest=None)
        self.store.set_default(self.profile.ref)
        self.prompts = {classifier_prompt(self.profile, kind)[0]:kind for kind in KINDS}
        for kind in ('report', 'form'):
            self.prompts[compile_naming_profile(self.profile, kind).prompt] = kind
        from recordprep.document_naming import compile_motion_naming
        self.prompts[compile_motion_naming(self.profile).prompt] = 'motion'
        examples = cases()
        self.assertEqual(len({c['id'] for c in examples}), len(examples))
        self.prepare([c['type'] for c in examples], {i for i,c in enumerate(examples,1) if c['start']}, {})
        images = {}
        for i, case in enumerate(examples,1):
            (self.root/f'text_pages/{i:04d}.txt').write_text(case['text'])
            with pymupdf.open() as pdf:
                page = pdf.new_page()
                self.assertGreaterEqual(page.insert_textbox(pymupdf.Rect(40,40,550,750),case['text'],fontsize=12),0)
                image = page.get_pixmap().tobytes('png')
            (self.root/f'image_pages/{i:04d}.png').write_bytes(image)
            images[image] = i
        from recordprep.transcript_layout import apply_manual_override
        apply_manual_override(self.root, mode='ct_only')
        before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for folder in ('text_pages','image_pages')
                  for p in (self.root/folder).iterdir()}
        def scripted(request, **kwargs):
            payload = json.loads(request.data)
            task = self.prompts[payload['messages'][0]['content']]
            image = payload['messages'][1]['content'][0]['image_url']['url'].split(',',1)[1]
            i = images[base64.b64decode(image)]; case = examples[i-1]
            self.calls.append((task,i))
            if task == 'ct': answer = {'page_type':case['type']}
            elif task.startswith('first_'): answer = {'first_page':'yes' if case['start'] else 'no'}
            elif task == 'motion':
                answer = {'name':case['text'].splitlines()[0], 'rule_id':'motion-papers',
                          'date':'', 'date_basis':'unknown'}
            elif task in ('report','form'):
                answer = {'name':case['reply'], **({'rule_id':case['rule_id']} if 'rule_id' in case else {})}
                if task == 'report': answer['date'] = 'January 02, 2026'
            else: answer = {'date':''}
            return json.dumps(answer)
        with patch.object(self.ui, '_post_json_with_retries', side_effect=scripted):
            self.run_steps('_run_step_two','_run_step_advanced','_run_step_dates','_run_step_names',
                           '_run_step_six','_run_step_seven','_run_step_correct_boundaries')
        named = self.rows('names')
        self.assertEqual(len(named),len(examples))
        for i,(row,case) in enumerate(zip(named,examples),1):
            if case['type'] in ('CT_report','CT_form'):
                self.assertEqual(row.get('name',''),case['name'],case['id'])
                self.assertEqual(row.get('naming_rule_id',''),case.get('rule_id',''),case['id'])
            if case['id'].startswith('embedded-'):
                self.assertEqual(row['page_type'],'CT_other')
                self.assertNotIn(('first_hearing',i),self.calls)
        bounds = json.loads((self.root/'artifacts/report_boundaries.json').read_bytes())
        self.assertEqual([(int(b['start_page']),int(b['end_page'])) for b in bounds],
                         [(1,2),(3,3),(5,5),(6,6),(7,7),(8,8),(9,9),(10,10)])
        self.assertEqual(json.loads((self.root/'artifacts/hearing_boundaries.json').read_bytes()), [])
        from recordprep.classification_review import capture, _proposal_row
        _, _, _, _, guidance, contracts = capture(self.root, ROOT/'.pi')
        for task in ('ct','first_form'):
            self.assertIn(classifier_prompt(self.profile,task)[0],guidance)
        row = {'file_name':'0001.txt','page_type':'CT_report_first_page','report_first_page':'yes','name':''}
        corrected = _proposal_row({'file_name':'0001.txt','before':{'name':'','naming_rule_id':None},
            'after':{'name':'PRESENTENCE REPORT','naming_rule_id':'report-probation'}},
            {'0001.txt':row},contracts)
        self.assertEqual(corrected['naming_rule_id'],'report-probation')
        self.assertEqual(corrected['name'],'PRESENTENCE REPORT')
        self.run_fake_summary()
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in before})

    def run_fake_summary(self):
        project = self.root/'synthetic-project'
        shutil.copytree(ROOT/'.pi',project/'.pi')
        (project/'config.json').write_text('{}')
        spec = importlib.util.spec_from_file_location('criminal_summary_runner',project/'.pi/scripts/run_recordprep_skill.py')
        runner = importlib.util.module_from_spec(spec);sys.modules[spec.name] = runner
        self.addCleanup(sys.modules.pop,spec.name,None);spec.loader.exec_module(runner)
        config = sa.ExtractionConfig('reports','',profile=self.profile)
        self.assertEqual(tuple(d.identifier for d in config.definitions),TOPICS)
        items = sa.build_work_items(self.root,config)
        source = sa.item_source_payload(items[0],self.root/'text_pages',{})
        self.assertIn('PROPOSED FINDINGS AND ORDERS',source)
        self.assertNotIn('VICTIM IMPACT STATEMENT',source)
        # Script authored digests, including source-exact quotes and nulls. These
        # assertions prove delivery/codec fidelity, not a model's interpretation.
        digests = {
            TOPICS[0]:('The recommendation is conditional on conviction.','If convicted, probation recommends supervised treatment rather than custody'),
            TOPICS[5]:('Probation proposes treatment; no order has adopted it.','The court has not adopted these proposals'),
            TOPICS[6]:('Counsel disputes the proposed actual credit figure.','counsel claims 28 actual days'),
            TOPICS[7]:('Restitution is requested, with a separate fine recommendation.','Restitution of $300 is requested, not ordered'),
            TOPICS[8]:('No defendant interview was available, without an inference about remorse.','No defendant interview was available'),
        }
        candidate = {'categories':[{'id':identifier,'digest':{'text':text,'evidence':[{'text':quote,'file_page':2}]}}
                                   for identifier,(text,quote) in digests.items()]}
        stage = runner.SkillStage('create_report_summaries','Create report summaries','recordprep-extract-report','')
        with patch('recordprep.case_profiles.profile_store',return_value=self.store), \
             patch.object(runner,'_resolve_pi_command',return_value=['offline-pi']), \
             patch.object(runner,'_check_pi_version'), \
             patch.object(runner,'_stage_capacity',return_value=None), \
             patch.object(runner,'_report_capacity'), \
             patch.object(runner,'_run_extraction_child',side_effect=lambda *a:
                          candidate if a[3].start_page == 1 else {'categories':[]}) as extract, \
             patch.object(runner,'_run_synthesis_child',return_value=([],[])) as synthesize:
            self.assertEqual(runner._run_summary_stage(stage,self.root,project/'.pi'),0)
            self.assertEqual(extract.call_count,len(items))
            self.assertEqual(synthesize.call_count,1)
            self.assertEqual(sa.validate_summary_agent_outputs(self.root,'reports'),[])
            document = sa.load_digest_markdown(self.root,'reports')
            self.assertEqual(tuple(c['id'] for c in document[0]['categories']),TOPICS)
            self.assertIsNone(document[0]['categories'][1]['digest'])
            for category in document[0]['categories']:
                if category['digest']:
                    evidence = category['digest']['evidence'][0]
                    self.assertTrue(evidence['verified'])
                    self.assertIn(category['id'],evidence['quote_id'])
            text = sa.serialize_digest_markdown('reports','Synthetic',document)
            self.assertEqual(sa.parse_digest_markdown(text,'reports','Synthetic'),document)
            for prose,_ in digests.values():
                self.assertIn(prose,sa.summary_final_path(self.root,'reports').read_text())
            self.assertEqual(runner._run_summary_stage(stage,self.root,project/'.pi'),0)
            self.assertEqual(extract.call_count,len(items))
            self.assertEqual(synthesize.call_count,1)


class EmbeddedTranscriptTests(unittest.TestCase):
    def test_resource_and_skill_clarifications_delivered(self):
        contract = load_recognition()
        self.assertEqual(contract.identity,'recordprep-recognition-v3')
        definitions = dict(contract.descriptions('ct'))
        for text in ('custom-written or handwritten', 'unused/unsigned', 'written stipulations',
                     'court responses', 'Motion advocacy', 'record-authentication'):
            self.assertIn(text,definitions['CT_form'])
        self.assertIn('embedded preliminary-hearing',definitions['CT_other'])
        self.assertIn('normally classify that embedded material as CT_other',definitions['CT_cover'])
        self.assertIn('internal index',definitions['CT_index'])
        self.assertIn('new instruction number',dict(contract.first_pages)['first_form'])
        skill = (ROOT/'.pi/skills/recordprep-detect-transcript-layout/SKILL.md').read_text()
        for text in ('outer pagination', 'do not reopen RT', 'genuinely standalone RT',
                     'conflicting outer-collection evidence', 'preserve every', 'needs_review'):
            self.assertIn(text,skill)
        numbering = (ROOT/'.pi/skills/recordprep-number-transcript-pages/SKILL.md').read_text()
        for text in ('CT 211, not RT 7 or CT 54', 'ambiguous/missing', 'docket overlay'):
            self.assertIn(text,numbering)

    def test_scripted_ct_citations_preserve_outer_numbers_and_honest_unknowns(self):
        from recordprep.pi_bundle import normalize_transcript_numbering_labels, validate_transcript_numbering_outputs
        with tempfile.TemporaryDirectory() as td:
            root = Path(td);(root/'text_pages').mkdir();(root/'artifacts').mkdir()
            texts = ('Outer CT 210; embedded reporter cover 1',
                     'Outer CT 211; Q/A; reporter page 7; docket overlay 54',
                     'No legible outer CT number; reporter page 8; docket overlay 55',
                     'No page number visible')
            entries = []
            for i,(text,number,status) in enumerate(zip(texts,(210,211,None,None),
                                                       ('selected','selected','ambiguous','missing')),1):
                (root/f'text_pages/{i:04d}.txt').write_text(text)
                entries.append({'file_name':f'{i:04d}.txt','file_page':i,'record_type':'CT',
                    'page_type':'CT_other','transcript_page_number':number,'status':status,
                    'citation_prefix':'CT' if number else '',
                    'citation_label':f'CT p. {number}' if number else '',
                    'citation_key':f'CT:{number}' if number else ''})
            payload = {'schema_version':2,'entries':entries,'citation_series':[{'citation_prefix':'CT'}]}
            path = root/'artifacts/transcript_page_numbers.json';path.write_text(json.dumps(payload))
            (root/'artifacts/transcript_page_number_series.md').write_text('# Transcript Page Breakdown\n')
            before = {p:p.read_bytes() for p in (root/'text_pages').iterdir()}
            self.assertEqual(validate_transcript_numbering_outputs(root),[])
            self.assertEqual(normalize_transcript_numbering_labels(root),['0001.txt','0002.txt'])
            actual = json.loads(path.read_bytes())['entries']
            self.assertEqual([e['citation_label'] for e in actual],['CT 210','CT 211','',''])
            self.assertEqual([e['status'] for e in actual],['selected','selected','ambiguous','missing'])
            self.assertEqual([e['transcript_page_number'] for e in actual],[210,211,None,None])
            self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_v3_changes_explicit_basic_advanced_not_dates_or_names(self):
        from dataclasses import replace
        current = load_recognition()
        previous = json.loads((ROOT/'recordprep/resources/classification/recognition-v2.json').read_bytes())
        historical = replace(current, identity=previous['contract_id'],
            page_types=tuple((side,tuple(previous['page_types'][side].items())) for side in ('rt','ct')),
            first_pages=tuple(previous['first_pages'].items()))
        for profile in (None, criminal(), api.bundled_profile_for_identity(api.APPLICATION,api.DEFAULT_PROFILE_ID)):
            for stage in ('basic','advanced','dates','names'):
                if profile is None and stage=='names': continue  # Unassigned naming uses its separate compatibility path.
                self.assertEqual(component(profile,stage,contract=current)!=component(profile,stage,contract=historical),
                                 stage in ('basic','advanced'))

    def test_scripted_layout_artifacts_route_outer_collections_not_enclosed_transcripts(self):
        scenarios = [
            ('split',['RT cover','RT hearing','CT cover and index','embedded reporter cover',
                      'embedded Q/A','later CT stipulation'],2),
            ('ct_only',['CT cover and index','embedded preliminary Q/A','later CT abstract'],None),
            ('rt_only',['Standalone RT preliminary hearing cover','Q/A','Reporter certificate'],3),
            (None,['CT cover','separate RT volume cover','RT hearing'],None),
        ]
        for mode,pages,rt_end in scenarios:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                for folder in ('text_pages','image_pages'): (root/folder).mkdir()
                for i,text in enumerate(pages,1):
                    (root/f'text_pages/{i:04d}.txt').write_text(text)
                    (root/f'image_pages/{i:04d}.png').write_bytes(b'fictional')
                before = {p:p.read_bytes() for folder in ('text_pages','image_pages') for p in (root/folder).iterdir()}
                draft = draft_layout_payload(mode=mode, status='resolved' if mode else 'needs_review',
                    decision_source='pi-agent',confidence='high' if mode else 'low',method='scripted fixture',
                    rt_end_file_page=rt_end,ct_start_file_page=rt_end+1 if mode=='split' else 1 if mode=='ct_only' else None,
                    search_summary='Scripted outer collection decision; embedded pages remain enclosed.',
                    evidence=[{'path':'text_pages/0001.txt','kind':'text'}],
                    warnings=[] if mode else ['Separate CT to RT collections require review.'])
                finalize_layout_draft(root,draft)
                if mode:
                    resolved = read_resolved_layout(root)
                    self.assertEqual(resolved['mode'],mode)
                    split = resolve_rt_ct_split(root,root/'text_pages')
                    self.assertEqual(split[4],mode)
                    if mode=='split': self.assertEqual(split[:2],(2,3))
                else:
                    self.assertIsNone(read_resolved_layout(root))
                    with self.assertRaises(TranscriptLayoutError):resolve_rt_ct_split(root,root/'text_pages')
                self.assertEqual(before,{p:p.read_bytes() for p in before})
