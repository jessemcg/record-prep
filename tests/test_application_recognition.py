"""Application ownership, frozen requests and unassigned publication; offline only."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from recordprep import recognition_contract as recognition
from recordprep.classifier_prompts import classifier_document
from recordprep.classification_profiles import ClassificationRun, component, output_names, stage_issues
from recordprep.profile_contract import CLASSIFICATION_PAGE_TYPES, CLASSIFICATION_FIRST_PAGE_TYPES
from recordprep.prompt_inspection import FIXED_TASKS, freeze_draft, inspect_prompt
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_workflows import ProfileEditor
from test_structured_classification import ROOT, bundle, legacy
import test_classification_profiles as fixtures


class ResourceTests(unittest.TestCase):
    def test_complete_neutral_resource_and_deterministic_order(self):
        frozen = recognition.load_recognition()
        for side, keys in CLASSIFICATION_PAGE_TYPES.items():
            self.assertEqual(tuple(dict(frozen.descriptions(side))), keys)
            self.assertTrue(all(text.strip() for _, text in frozen.descriptions(side)))
        self.assertEqual(tuple(dict(frozen.first_pages)), tuple(CLASSIFICATION_FIRST_PAGE_TYPES))
        self.assertEqual(recognition.TITLES['RT_body'], 'Hearing body')
        self.assertEqual(recognition.TITLES['CT_notice'], 'Hearing notice')
        for task, _ in FIXED_TASKS:
            prompt = classifier_document(task, frozen).render()
            for specialty in ('juvenile', 'dependency', 'CFS 6.7', 'DCFS 4216', 'Detention Report', 'JV-'):
                self.assertNotIn(specialty, prompt)
        with tempfile.TemporaryDirectory() as temporary:
            data = json.loads(recognition.RESOURCE.read_bytes())
            data['page_types']['ct'] = dict(reversed(list(data['page_types']['ct'].items())))
            data['first_pages'] = dict(reversed(list(data['first_pages'].items())))
            path = Path(temporary)/'resource.json'; path.write_text(json.dumps(data))
            self.assertEqual(recognition.load_recognition(path), frozen)

    def test_authored_examples_cover_taxonomy_and_functional_exclusions(self):
        examples=json.loads((ROOT/'tests/fixtures/recognition-fictional.json').read_bytes())
        self.assertEqual(len({row['id'] for row in examples}),len(examples))
        self.assertEqual({row['type'] for row in examples},{key for keys in CLASSIFICATION_PAGE_TYPES.values() for key in keys})
        self.assertEqual({row['task'] for row in examples if 'task' in row},set(CLASSIFICATION_FIRST_PAGE_TYPES) - {'first_motion'})
        for row in examples:
            self.assertTrue(row['visible'])
            if row.get('ineligible_for_form_work'):
                self.assertIn(row['type'],('CT_notice','CT_proof_of_service'))
                self.assertNotIn('task',row)
        # These are authored semantic expectations, NOT a model/image-accuracy test.

    def test_missing_invalid_duplicate_oversized_and_unsupported_fail_without_fallback(self):
        original = json.loads(recognition.RESOURCE.read_bytes())
        variants = []
        for mutation in ('top', 'side', 'missing-type', 'unknown-type', 'cross-type', 'missing-start',
                         'unknown-start', 'empty', 'oversize-text', 'bool', 'identity', 'bad-text'):
            value = copy.deepcopy(original)
            if mutation == 'top': value['unexpected'] = True
            if mutation == 'side': value['page_types']['cr'] = {}
            if mutation == 'missing-type': del value['page_types']['rt']['RT_cover']
            if mutation == 'unknown-type': value['page_types']['rt']['RT_new'] = 'No'
            if mutation == 'cross-type': value['page_types']['rt']['CT_report'] = 'No'
            if mutation == 'missing-start': del value['first_pages']['first_report']
            if mutation == 'unknown-start': value['first_pages']['first_other'] = 'No'
            if mutation == 'empty': value['first_pages']['first_form'] = '  '
            if mutation == 'oversize-text': value['first_pages']['first_form'] = 'x'*8193
            if mutation == 'bool': value['schema_version'] = True
            if mutation == 'identity': value['contract_id'] = 'unknown'
            if mutation == 'bad-text': value['page_types']['ct']['CT_report'] = ['No']
            variants.append((mutation, json.dumps(value).encode()))
        variants += [('duplicate', b'{"schema_version":1,"schema_version":1}'),
                     ('invalid-utf8', b'\xff'), ('oversize-file', b' '* (256*1024+1))]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'resource.json'
            with self.assertRaisesRegex(ValueError, 'No profile fallback'):
                recognition.load_recognition(path)
            for mutation, data in variants:
                with self.subTest(mutation=mutation):
                    path.write_bytes(data)
                    with self.assertRaisesRegex(ValueError, 'No profile fallback'):
                        recognition.load_recognition(path)

    def test_prompt_content_is_stage_local_and_display_titles_are_not_inputs(self):
        original = recognition.load_recognition()
        stages = ('basic','advanced','dates','names')
        baseline = {stage: component(bundle(),stage,contract=original) for stage in stages}
        for side in ('rt','ct'):
            changed = replace(original, page_types=tuple((s, tuple((k, v+' Synthetic rule.' if s==side and k.endswith('_other') else v)
                              for k,v in entries)) for s,entries in original.page_types))
            for stage in stages:
                self.assertEqual(component(bundle(),stage,contract=changed) != baseline[stage], stage == 'basic')
        for task in CLASSIFICATION_FIRST_PAGE_TYPES:
            changed = replace(original, first_pages=tuple((k,v+' Synthetic clue.' if k==task else v) for k,v in original.first_pages))
            for stage in stages:
                self.assertEqual(component(bundle(),stage,contract=changed) != baseline[stage], stage == 'advanced')
        with patch.dict(recognition.TITLES, {'RT_body':'Cosmetic title'}):
            self.assertEqual(component(bundle(),'basic'),baseline['basic'])
        self.assertEqual(component(None,'dates'),component(bundle(),'dates'))

    def test_inspection_and_preview_do_not_depend_on_profile_or_valid_naming_draft(self):
        editor=editable_profile(legacy())
        frozen=freeze_draft(editor,raw_resources={'naming':'{ malformed naming'})
        self.assertIsNone(frozen.snapshot)
        for task,_ in FIXED_TASKS:
            for template in (False, True):
                view=inspect_prompt({},task,ROOT/'.pi',template=template,draft=frozen)
                self.assertFalse(view.issues)
                self.assertEqual(view.components[0][1],classifier_document(task).render())
        from recordprep.profile_integration import preview
        old=ProfileEditor(legacy());old.resources['classification_tasks']['rt']='RETIRED_CANARY'
        previews=preview(old.snapshot(),ROOT/'.pi')
        self.assertNotIn('RETIRED_CANARY',str(previews))

    def test_explicit_saves_create_schema9_without_rewriting_old_revisions_or_naming(self):
        from recordprep import practice_profiles as api
        from test_practice_profiles import historical_snapshot
        for version in range(1,9):
            with self.subTest(version=version),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);store=api.ProfileStore('recordprep',config_root=root/'config',data_root=root/'data')
                old=historical_snapshot(bundle(),version)
                store.accept_profile(old,expected_previous_digest=None)
                before={p:(p.read_bytes(),p.stat().st_mtime_ns) for p in store.data_root.rglob('*') if p.is_file()}
                editor=ProfileEditor(old)
                ref=editor.managed_save(store,expected_head=old.ref.content_sha256,expected_default=None,
                    validate=lambda snapshot:classifier_document('ct'),can_modify=lambda:True)
                saved=store.load_profile_snapshot(ref)
                self.assertEqual(saved.manifest['schema_version'],11)
                self.assertEqual(saved.manifest['profile_api'],1)
                self.assertNotIn('classification_tasks',saved.manifest['resources'])
                self.assertEqual(saved.resource('naming'),old.resource('naming'))
                self.assertEqual(store.load_profile_snapshot(old.ref).files,old.files)
                # Snapshot files, unlike the mutable registry, are immutable.
                for path,content in before.items():
                    if 'snapshots' in path.parts:self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),content)
                created=ProfileEditor.create(old,'Fictional neutral practice').snapshot()
                self.assertEqual(created.manifest['schema_version'],11)
                self.assertEqual(created.resource('naming'),old.resource('naming'))

    def test_retired_configuration_is_inert_and_ordinary_saves_do_not_create_keys(self):
        from recordprep.ui import main_window as ui
        retired = {'classifier_prompt','classifier_rt_prompt','classifier_ct_prompt',
                   'advanced_classify_hearing_prompt','advanced_classify_minute_prompt','advanced_classify_form_prompt'}
        for config in ({}, {key:'RETIRED_CANARY' for key in retired}):
            before=copy.deepcopy(config)
            with patch.object(ui,'_read_config',side_effect=lambda:copy.deepcopy(config)), patch.object(ui,'_write_config') as save:
                basic=ui.load_classifier_settings(); advanced=ui.load_advanced_classify_settings()
                self.assertNotIn('RETIRED_CANARY',str((basic,advanced)))
                ui.save_classifier_settings('https://synthetic.invalid','fake','','INACTIVE','INACTIVE',False,1)
                saved=save.call_args.args[0]
                for key in retired:
                    self.assertEqual(key in saved,key in before)
                    if key in before:self.assertEqual(saved[key],before[key])
                count=save.call_count
                ui.save_advanced_classify_settings('INACTIVE','INACTIVE','INACTIVE')
                self.assertEqual(save.call_count,count)
            self.assertEqual(config,before)


class UnassignedRunTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.ClassificationProfileTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.root,self.settings,self.store=fixture.root,fixture.settings,fixture.store
        for target in ('recordprep.classification_profiles.resolve_case_profile','recordprep.case_profiles.resolve_case_profile'):
            patcher=patch(target,return_value=None);patcher.start();self.addCleanup(patcher.stop)

    def row(self, run, kind='CT_other'):
        (run.directory/output_names(run.stage)[1]).write_text(json.dumps({'file_name':'0001.txt','page_type':kind})+'\n')

    def inventory(self):
        return {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in (self.root/'classification').iterdir() if p.name not in {'review-required','workflow-v2.json'}}

    def test_all_structural_stages_private_current_reusable_and_nullable_metadata(self):
        from recordprep.ui import main_window as ui
        from recordprep.output_presence import step_outputs_present
        worker=SimpleNamespace(_expected_classification_file_names=lambda root:(set(),{'0001.txt'},False,True))
        worker._jsonl_complete_for_expected=lambda *args:ui.RecordPrepWindow._jsonl_complete_for_expected(worker,*args)
        steps={'basic':'classify_basic','advanced':'classify_advanced',
               'dates':'classify_dates'}
        for stage in ('basic','advanced','dates'):
            run=ClassificationRun.begin(self.root,stage,self.settings)
            self.assertNotEqual(run.directory,self.root/'classification')
            self.assertIsNotNone(run.contract)
            self.row(run);run.publish(self.settings)
            metadata=json.loads((self.root/'classification'/f'profile-{stage}.json').read_text())
            self.assertIsNone(metadata['profile_ref'])
            self.assertFalse(stage_issues(self.root,stage,None,self.settings))
            paths=[self.root/'classification'/name for name in output_names(stage)]
            with patch.object(ui,'load_classifier_settings',return_value=self.settings):
                self.assertTrue(ui.RecordPrepWindow._classification_output_complete(worker,self.root,*paths))
            with patch.object(recognition,'RESOURCE',self.root/'missing-resource.json'):
                self.assertTrue(step_outputs_present(steps[stage],self.root))
            before=self.inventory()
            repeat=ClassificationRun.begin(self.root,stage,self.settings)
            self.assertEqual(repeat.directory,run.directory)
            self.assertEqual(self.inventory(),before)
            self.assertTrue((repeat.directory/output_names(stage)[1]).is_file())

    def test_unassigned_names_stays_literal_without_overwriting_recorded_profile_names(self):
        with patch.object(recognition,'RESOURCE',self.root/'missing-recognition.json'):
            run=ClassificationRun.begin(self.root,'names',self.settings)
            self.assertEqual(run.directory,self.root/'classification')
            self.assertIsNone(run.contract)
            run.publish(self.settings)
        marker=self.root/'classification/profile-names.json'
        marker.write_text('{"historical":"synthetic recorded profile naming"}\n')
        before=self.inventory()
        with self.assertRaisesRegex(ValueError,'unassigned naming contract'):
            ClassificationRun.begin(self.root,'names',self.settings)
        self.assertEqual(self.inventory(),before)

    def test_stale_canonical_is_not_a_checkpoint_and_new_rule_changes_only_private_work(self):
        canonical=self.root/'classification/CT_basic.jsonl'
        canonical.write_text('{"file_name":"0001.txt","page_type":"CT_form"}\n')
        before=self.inventory()
        run=ClassificationRun.begin(self.root,'basic',self.settings)
        self.assertFalse((run.directory/canonical.name).exists())
        self.assertEqual(self.inventory(),before)
        self.row(run)
        resource=json.loads(recognition.RESOURCE.read_bytes());resource['page_types']['ct']['CT_other']+=' Authored change.'
        path=self.root/'new-resource.json';path.write_text(json.dumps(resource))
        worker=SimpleNamespace(_raise_if_stop_requested=lambda:None,_extract_response_text=lambda p:p,_extract_json_payload=lambda p:p)
        from recordprep.ui import main_window as ui
        with patch.object(recognition,'RESOURCE',path),patch.object(ui,'_post_json_with_retries',return_value='{"page_type":"CT_other"}') as post:
            ui.RecordPrepWindow._classify_image(worker,run.payload(self.settings,'ct'),'0001.txt',self.root/'image_pages/0001.png')
            prompt=json.loads(post.call_args.args[0].data)['messages'][0]['content']
            self.assertNotIn('Authored change.',prompt)
            with self.assertRaisesRegex(ValueError,'changed'):run.publish(self.settings)
            newer=ClassificationRun.begin(self.root,'basic',self.settings)
            self.assertNotEqual(newer.directory,run.directory)
            self.assertFalse((newer.directory/canonical.name).exists())
        self.assertEqual(self.inventory(),before)

    def test_source_model_selection_and_upstream_changes_preserve_canonical(self):
        run=ClassificationRun.begin(self.root,'basic',self.settings);self.row(run);run.publish(self.settings)
        before=self.inventory()
        with self.assertRaisesRegex(ValueError,'changed'):run.publish(self.settings|{'model_id':'changed'})
        with patch('recordprep.classification_profiles.read_case_profile_ref',return_value=bundle().ref):
            with self.assertRaisesRegex(ValueError,'changed'):run.publish(self.settings)
        advanced=ClassificationRun.begin(self.root,'advanced',self.settings);self.row(advanced)
        basic=self.root/'classification/CT_basic.jsonl';basic.write_text(basic.read_text()+'\n')
        changed=self.inventory()
        with self.assertRaisesRegex(ValueError,'upstream'):advanced.publish(self.settings)
        self.assertEqual(self.inventory(),changed)
        basic.write_bytes(before[basic.name][0])
        (self.root/'image_pages/0001.png').write_bytes(b'changed image')
        with self.assertRaisesRegex(ValueError,'changed'):run.publish(self.settings)
        self.assertEqual(basic.read_bytes(),before[basic.name][0])

    def test_aborted_work_does_not_touch_canonical_and_resumes_privately(self):
        canonical=self.root/'classification/CT_basic.jsonl';canonical.write_text('Historical bytes, not a new checkpoint.\n')
        before=self.inventory()
        run=ClassificationRun.begin(self.root,'basic',self.settings);self.row(run)
        # No publish on Stop/error; a subsequent identical run retains private rows.
        repeat=ClassificationRun.begin(self.root,'basic',self.settings)
        self.assertEqual(repeat.directory,run.directory)
        self.assertEqual(self.inventory(),before)
        repeat.publish(self.settings)
        self.assertIn('CT_other',canonical.read_text())
