"""Ownership regressions: public fixtures, synthetic edits, no private state."""
import copy
import json
import unittest
from unittest.mock import patch

from test_structured_classification import bundle, legacy, ROOT
from test_practice_profiles import historical_snapshot, synthetic_files
from recordprep.profile_workflows import ProfileEditor
from recordprep.profile_contract import validate_contents, CLASSIFICATION_PAGE_TYPES
from recordprep.classification_profiles import classifier_prompt, component
from recordprep.structured_guidance import effective_resource
from recordprep.profile_editor_ui import editable_profile
from recordprep.profile_customization import legacy_customization_editor
from recordprep.summary_profiles import compile_summary

STAGES = ('basic', 'advanced', 'corrected', 'dates', 'names')


def components(snapshot):
    return {stage: component(snapshot, stage) for stage in STAGES}


class OwnershipTests(unittest.TestCase):
    def test_retired_dates_do_not_select_runtime_adapter_but_editing_is_lossless(self):
        old = legacy()
        for representation in ('flat', 'legacy-v3'):
            for date in ('date_hearing', 'date_minute'):
                with self.subTest(representation=representation, date=date):
                    editor = ProfileEditor(old)
                    tasks = editor.resources['classification_tasks']
                    tasks[date] = 'Retained inactive date text α {literal}.\n'
                    if representation == 'legacy-v3':
                        from recordprep.classifier_prompts import REPORT_FIRST_CLUES
                        tasks.update(schema_version=3, first_report=REPORT_FIRST_CLUES)
                    snapshot = editor.snapshot(); before = snapshot.files
                    self.assertNotEqual(snapshot.ref, old.ref)
                    self.assertEqual(components(snapshot), components(old))
                    draft = editable_profile(snapshot)
                    self.assertEqual(draft.resources['classification_tasks'][date], tasks[date])
                    self.assertEqual(components(draft.snapshot()), components(snapshot))
                    self.assertEqual(snapshot.files, before)
                    self.assertEqual(draft.snapshot().resource('classification_tasks')[date], tasks[date])

    def test_unknown_active_content_and_custom_report_start_are_never_adapted(self):
        for task in ('rt', 'ct', 'first_hearing', 'first_minute', 'first_form', 'first_report'):
            editor = editable_profile(legacy()) if task == 'first_report' else ProfileEditor(legacy())
            if task == 'first_report':
                # Lossless editing representation, not structured cards.
                editor = ProfileEditor(legacy())
                editor.resources['classification_tasks'].update(schema_version=3, first_report='Custom report opening.')
            else:
                editor.resources['classification_tasks'][task] += ' Custom active clue.'
            value = copy.deepcopy(editor.resources['classification_tasks'])
            self.assertEqual(effective_resource(value, 'classification_tasks'), value)
            self.assertEqual(editor.resources['classification_tasks'], value)

    def test_active_legacy_edits_are_stage_local_without_replacing_unknown_prose(self):
        from recordprep.classifier_prompts import REPORT_FIRST_CLUES
        for representation in ('flat','legacy-v3'):
            for task in ('rt','ct','first_hearing','first_minute','first_form','first_report'):
                e = ProfileEditor(legacy())
                if representation == 'legacy-v3' or task == 'first_report':
                    e.resources['classification_tasks'].update(schema_version=3,first_report=REPORT_FIRST_CLUES)
                before = e.snapshot(); baseline = components(before)
                literal = e.resources['classification_tasks'][task] + ' Unknown active clue α.'
                e.resources['classification_tasks'][task] = literal
                changed = e.snapshot()
                self.assertIn(literal,classifier_prompt(changed,task)[0])
                self.assertEqual(changed.resource('classification_tasks')[task],literal)
                expected = {'basic','corrected'} if task in ('rt','ct') else {'advanced','corrected'}
                self.assertEqual({stage for stage in STAGES if component(changed,stage) != baseline[stage]},expected,(representation,task))
                for other in ('rt','ct','first_hearing','first_minute','first_form','first_report'):
                    if task != other:
                        self.assertEqual(classifier_prompt(before,other),classifier_prompt(changed,other),(task,other))

    def test_retired_only_initialization_is_noop(self):
        config = {key: 'INACTIVE_CANARY' for key in (
            'classify_dates_hearing_prompt', 'classify_dates_minute_prompt', 'case_name_prompt',
            'summarize_hearings_prompt', 'summarize_reports_prompt', 'summarize_hearings_synthesis_prompt',
            'summarize_reports_synthesis_prompt', 'participants_prompt', 'overview_prompt')}
        before = copy.deepcopy(config)
        self.assertEqual(legacy_customization_editor(config).snapshot().files, bundle().files)
        self.assertEqual(config, before)

    def test_schema_one_neutral_fallbacks_and_inspection_parity(self):
        from recordprep.prompt_inspection import inspect_prompt
        from recordprep.classifier_prompts import FIRST_TASKS
        snapshot = validate_contents(tuple(synthetic_files('recordprep').items()), 'recordprep')
        resources = {name: snapshot.resource(name) for name in snapshot.manifest['resources']}
        for side, keys in CLASSIFICATION_PAGE_TYPES.items():
            prompt = classifier_prompt(snapshot, side)[0]
            descriptions = prompt.split('Category Descriptions\n\n', 1)[1]
            for key in keys:
                self.assertIn(key + '\n', descriptions)
                self.assertTrue(descriptions.split(key + '\n', 1)[1].strip())
            self.assertNotIn('Dependency', prompt)
            self.assertNotIn('juvenile', prompt.lower())
            self.assertNotIn('Preserve custom whitespace', prompt)
            self.assertEqual(prompt, inspect_prompt(resources, side, ROOT/'.pi', template=False, snapshot=snapshot).components[0][1])
        for task in FIRST_TASKS:
            prompt = classifier_prompt(snapshot, task)[0]
            self.assertIn('recognition clues', [s.identity for s in __import__('recordprep.classifier_prompts', fromlist=['classifier_document']).classifier_document({}, task).sections])
            self.assertNotIn('conditions of release', prompt)
            self.assertEqual(prompt, inspect_prompt(resources, task, ROOT/'.pi', template=False, snapshot=snapshot).components[0][1])

    def test_schema_and_naming_mutation_matrix(self):
        naming_values = [json.loads((ROOT/'tests/fixtures/naming-v2/general.json').read_bytes()),
                         legacy().resource('naming'), bundle().resource('naming'),
                         synthetic_files('recordprep')]
        # Explicitly include naming v1, v2, v3 and v4; all are legal in schemas 1–6.
        naming_values[-1] = {'mode': 'approved_titles', 'report_titles': ['Synthetic report'],
                             'form_titles': ['Synthetic form'], 'guidance': 'Use source evidence.'}
        for schema in range(1, 9):
            if schema == 7:
                e = ProfileEditor(bundle()); e.manifest['schema_version'] = 7
                e.resources['classification_tasks']['schema_version'] = 2
                e.resources['classification_tasks']['first_pages'].pop('first_report')
                original = e.snapshot()
            else:
                original = historical_snapshot(bundle(), version=schema)
            for naming in naming_values if schema <= 6 else [bundle().resource('naming')]:
                editor = ProfileEditor(original); editor.resources['naming'] = copy.deepcopy(naming)
                snapshot = editor.snapshot(); baseline = components(snapshot)
                for resource in ('classification', 'case_name', 'hearing_extraction', 'report_extraction',
                                 'hearing_synthesis', 'report_synthesis', 'participants', 'overview'):
                    if resource not in editor.resources: continue
                    change = ProfileEditor(snapshot); change.resources[resource] += '\nINACTIVE_CANARY'
                    changed = change.snapshot()
                    self.assertNotEqual(changed.ref, snapshot.ref)
                    self.assertEqual(components(changed), baseline, (schema, resource))
                    for kind in ('hearings', 'reports'):
                        for phase in ('extract', 'synthesize'):
                            self.assertEqual(compile_summary(snapshot, kind, phase).component_sha256,
                                             compile_summary(changed, kind, phase).component_sha256)
                if schema >= 2:
                    for task, stages in (('RT_body', {'basic','corrected'}), ('first_report', {'advanced','corrected'})):
                        change = ProfileEditor(snapshot)
                        owner = change.resources['classification_tasks']['page_types']['rt'] if task == 'RT_body' else change.resources['classification_tasks']['first_pages']
                        if task not in owner:
                            # Schema 7 supports three custom starts, with a fixed report fallback.
                            task = 'first_hearing'
                        owner[task] += ' Synthetic active clue.'
                        after = components(change.snapshot())
                        self.assertEqual({s for s in STAGES if after[s] != baseline[s]}, stages)
                for kind in ('hearings','reports'):
                    change = ProfileEditor(snapshot); change.resources[kind][0]['guidance'] += ' Active topic.'
                    changed = change.snapshot()
                    self.assertEqual(components(changed), baseline)
                    for other in ('hearings','reports'):
                        for phase in ('extract','synthesize'):
                            self.assertEqual(compile_summary(snapshot,other,phase).component_sha256 == compile_summary(changed,other,phase).component_sha256, kind != other)

    def test_exact_allowlist_and_unknown_active_mutation_matrix(self):
        from recordprep.structured_guidance import _BASE, structured_resources
        from recordprep.classifier_prompts import REPORT_FIRST_CLUES
        sources = [_BASE/'classification-tasks.json', _BASE/'classification-v2.json',
                   _BASE.parent/'dependency-1.7.0-initial/classification-v2.json',
                   _BASE.parent/'dependency-1.7.0-shared/classification-v2.json',
                   _BASE.parent/'dependency-1.8.0/classification-v3.json',
                   _BASE.parent/'dependency-1.8.0/classification-v3-unwrapped.json']
        for source in sources:
            for custom in (False, True):
                e = ProfileEditor(legacy()); tasks = json.loads(source.read_bytes())
                if custom:
                    owner, key = (tasks['page_types']['rt'], 'RT_body') if 'page_types' in tasks else (tasks,'rt')
                    owner[key] += ' Unknown active prose α.'
                e.resources['classification_tasks'] = tasks
                baseline = e.snapshot()
                for date in ('date_hearing','date_minute') if 'page_types' not in tasks else ():
                    changed = ProfileEditor(baseline); changed.resources['classification_tasks'][date] = 'INACTIVE_CANARY'
                    self.assertEqual(components(baseline),components(changed.snapshot()))
                if custom:
                    self.assertEqual(effective_resource(tasks,'classification_tasks'),tasks)
                else:
                    self.assertEqual(components(baseline),components(bundle()))
                if 'page_types' not in tasks:
                    wrapped = copy.deepcopy(tasks); wrapped.update(schema_version=3,first_report=REPORT_FIRST_CLUES)
                    self.assertEqual(effective_resource(wrapped,'classification_tasks'),effective_resource(tasks,'classification_tasks') if not custom else wrapped)
                before = copy.deepcopy(e.resources)
                structured_resources(e.resources)
                self.assertEqual(e.resources,before)

    def test_retired_roles_policies_and_minute_stage_isolation(self):
        from recordprep.minute_summaries import profile_guidance
        old = historical_snapshot(bundle(),version=2)
        for resource in ('roles','policies','minutes'):
            e = ProfileEditor(old)
            if resource == 'roles': e.resources[resource]['counsel'][0]['guidance'] += ' INACTIVE_CANARY'
            elif resource == 'policies': e.resources[resource] = {'attendance':'legacy_first_page_parents','report_scope':'exclude_formal_proposals'}
            else: e.resources[resource] += '\nActive minute emphasis.'
            changed = e.snapshot()
            self.assertNotEqual(old.ref,changed.ref)
            self.assertEqual(components(old),components(changed))
            for kind in ('hearings','reports'):
                for phase in ('extract','synthesize'):
                    self.assertEqual(compile_summary(old,kind,phase).component_sha256,compile_summary(changed,kind,phase).component_sha256)
            self.assertEqual(profile_guidance(old) == profile_guidance(changed),resource != 'minutes')

    def test_read_inspect_and_edit_leave_snapshot_bytes_and_mtimes_unchanged(self):
        import tempfile
        from pathlib import Path
        from recordprep.profile_workflows import export_profile
        from recordprep import practice_profiles as api
        from recordprep.prompt_inspection import freeze_draft, inspect_prompt
        old = ProfileEditor(legacy())
        old.resources['classification_tasks']['date_minute'] = 'Retained custom inactive date.'
        original = old.snapshot()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)/'snapshot'
            export_profile(original,destination)
            def inventory():
                return {str(p.relative_to(destination)):(p.read_bytes(),p.stat().st_mtime_ns) for p in destination.rglob('*') if p.is_file()}
            before = inventory()
            loaded = api.validate_profile_directory(destination).draft
            draft = editable_profile(loaded)
            frozen = freeze_draft(draft)
            self.assertEqual(frozen.issues,())
            for task in ('rt','ct','first_report','date_hearing','report','form','hearings-extract','minutes'):
                inspect_prompt(draft.resources,task,ROOT/'.pi',template=False,draft=frozen)
            self.assertEqual(inventory(),before)
            self.assertEqual(loaded.files,original.files)

    def test_freeze_raw_invalid_repaired_duplicate_and_unrelated_tasks(self):
        from recordprep.prompt_inspection import freeze_draft, inspect_prompt
        e = ProfileEditor(legacy())
        raw = '{ invalid naming α'
        frozen = freeze_draft(e,raw_resources={'naming':raw})
        self.assertIsNone(frozen.snapshot)
        self.assertNotIn('naming',frozen.resources)
        shown = inspect_prompt(e.resources,'report',ROOT/'.pi',template=False,draft=frozen)
        self.assertIn(raw,shown.display_text()); self.assertTrue(shown.issues)
        other = inspect_prompt(e.resources,'rt',ROOT/'.pi',template=False,draft=frozen)
        self.assertEqual(other.components[0][1],classifier_prompt(e.snapshot(),'rt')[0])
        self.assertTrue(other.issues)
        e.resources['naming']['report_guidance'] += ' Parent later changed.'
        self.assertIn(raw,inspect_prompt(e.resources,'report',ROOT/'.pi',template=False,draft=frozen).display_text())
        repaired = freeze_draft(e,raw_resources={'naming':json.dumps(e.resources['naming'])})
        self.assertIsNotNone(repaired.snapshot); self.assertFalse(repaired.issues)
        duplicate = freeze_draft(e,raw_resources={'naming':'{"mode":"source_title","mode":"approved_titles"}'})
        self.assertIsNone(duplicate.snapshot); self.assertTrue(duplicate.issues)
        bad_shape = freeze_draft(e,raw_resources={'naming':'{"unsupported":"literal draft"}'})
        self.assertIsNone(bad_shape.snapshot)
        self.assertIn('{"unsupported":"literal draft"}',inspect_prompt(e.resources,'report',ROOT/'.pi',template=False,draft=bad_shape).display_text())

    def test_extraction_configuration_compiles_once_and_keeps_bytes(self):
        from recordprep.summary_agents import ExtractionConfig
        for kind in ('hearings', 'reports'):
            with patch('recordprep.summary_agents.compile_summary', wraps=compile_summary) as compile_call:
                config = ExtractionConfig(kind, '', profile=bundle())
                payload = config.fingerprint_payload(); fingerprint = config.fingerprint
                for _ in range(100):
                    self.assertEqual(config.fingerprint, fingerprint)
                    self.assertEqual(config.fingerprint_payload(), payload)
                    self.assertTrue(config.definitions)
                self.assertEqual(compile_call.call_count, 1)
                self.assertEqual(config.guidance, compile_summary(bundle(),kind,'extract').prompt)
