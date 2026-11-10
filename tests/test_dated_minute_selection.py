"""Fictional minute eligibility/recognition contracts, never model-accuracy claims."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from recordprep import minute_selection as selection
from recordprep import classification_review as review
from recordprep.classifier_prompts import classifier_document
from recordprep.recognition_contract import load_recognition

PROJECT = Path(__file__).resolve().parents[1]


def rows():
    kinds = ['CT_minute_order', 'CT_minute_order_first_page', 'CT_minute_order',
             'CT_minute_order_first_page', 'CT_minute_order', 'CT_minute_order_first_page',
             'CT_minute_order', 'CT_other', 'CT_minute_order_first_page']
    return [dict(file_name=f'{i:04d}.txt', page_type=kind,
                 **({'date': 'March 5, 2026'} if i in (2, 6, 9) else {}))
            for i, kind in enumerate(kinds, 1)]


class PureSelectionTests(unittest.TestCase):
    def test_supported_calendar_dates_and_invalid_values(self):
        for value in ['March 5, 2026', 'Mar 5, 2026', '3/5/26', '03/05/2026',
                      '2026-03-05', ' Wednesday,  March\n 5, 2026 ', 'Wednesday,\nMar 5, 2026']:
            with self.subTest(value=value):
                self.assertEqual(selection.recognized_date(value).isoformat(), '2026-03-05')
        for value in [None, '', '  ', 'Date unresolved', 'unknown', 'TBD', 20260305, False,
                      [], {}, 'February 30, 2026', '2/29/25', '2026-13-01', 'March 5, 0000']:
            with self.subTest(value=value):
                self.assertIsNone(selection.recognized_date(value))
        self.assertIsNotNone(selection.recognized_date('February 29, 2024'))

    def test_range_first_partition_no_bridges_or_same_day_loss(self):
        source = rows()
        before = copy.deepcopy(source)
        candidates = selection.candidate_ranges(list(reversed(source)), 0)
        self.assertEqual([(c.start_file, c.end_file) for c in candidates],
                         [('0002.txt','0003.txt'), ('0004.txt','0005.txt'),
                          ('0006.txt','0007.txt'), ('0009.txt','0009.txt')])
        kept, omitted = selection.partition_candidates(candidates)
        self.assertEqual([c.start_file for c in kept], ['0002.txt','0006.txt','0009.txt'])
        self.assertEqual([c.source_range for c in omitted], ['0004–0005'])
        self.assertEqual(source, before)
        # A date on the body cannot rescue an undated start; a gap ends a range.
        source[4]['date'] = 'March 5, 2026'
        source = [r for r in source if r['file_name'] != '0007.txt']
        kept, omitted = selection.partition_candidates(selection.candidate_ranges(source, 0))
        self.assertEqual(kept[1].end_file, '0006.txt')
        self.assertEqual(len(omitted), 1)
        self.assertEqual([c.start_file for c in selection.candidate_ranges(source, 6)], ['0009.txt'])

    def test_adjacent_starts_and_leading_continuations(self):
        source = rows()[:4]
        source[2]['page_type'] = 'CT_minute_order_first_page'
        self.assertEqual([(c.start_file, c.end_file) for c in selection.candidate_ranges(source, 0)],
                         [('0002.txt','0002.txt'), ('0003.txt','0003.txt'), ('0004.txt','0004.txt')])
        self.assertEqual(selection.candidate_ranges(source[:1], 0), [])

    def test_structural_errors_not_date_omissions(self):
        for source in [[rows()[0], rows()[0]], [{'file_name': 'bad', 'page_type': 'CT_other'}],
                       [{'file_name':'0000.txt','page_type':'CT_other'}], [None]]:
            with self.assertRaises(ValueError): selection.candidate_ranges(source, 0)
        for boundaries in [{}, [None], [{'date':''}],
                           [dict(start_page='0002',end_page='0001',date='')],
                           [dict(start_page='x',end_page='0002',date='')],
                           [dict(start_page='0001',end_page='0002',date='')]*2]:
            with self.assertRaises(ValueError): selection.filter_boundaries(boundaries)

    def test_filter_preserves_retained_metadata_and_bounded_reporting(self):
        source = [dict(start_page='0001',end_page='0002',date='3/5/26',custom={'literal':True}),
                  dict(start_page='0003',end_page='0004',date='Date unresolved')]
        before = copy.deepcopy(source)
        kept, omitted = selection.filter_boundaries(source)
        self.assertIs(kept[0], source[0])
        self.assertEqual(source, before)
        messages = selection.omission_messages(omitted * 41)
        self.assertEqual(len(messages), 4)
        self.assertTrue(all(message.count('0003–0004') <= 20 for message in messages))
        self.assertIn('missing dates do not prove misclassification', messages[0])

    def test_supported_historical_boundary_extents_keep_metadata(self):
        entry = {'start': '0001.txt', 'end': 2, 'date': '3/5/26', 'extra': 'literal'}
        kept, omitted = selection.filter_boundaries([entry])
        self.assertIs(kept[0], entry)
        self.assertEqual(omitted, [])

    def test_review_projection_keeps_undated_candidates_and_ending_hints(self):
        source = {r['file_name']:r for r in rows()}
        docs = review.selected_documents(source)
        self.assertEqual(len(docs), 4)
        hints = review.prioritized_worklist(source)['priority_1_hearing_and_minute_starts']
        self.assertIn('0006.txt', hints[1]['ending_neighbors'])
        corrected = copy.deepcopy(source)
        corrected['0004.txt']['date'] = 'March 5, 2026'
        audit = {'changes':[{'file_name':'0004.txt'}]}
        kept, audit = review.retain_effective_changes(source, corrected, audit)
        self.assertEqual(len(audit['changes']), 1)
        self.assertEqual(selection.omission_warnings(kept.values()), [])
        self.assertEqual(selection.omission_warnings(source.values())[0]['end_page'], '0005')


class RecognitionIsolationTests(unittest.TestCase):
    def test_historical_resource_bytes_and_all_unrelated_prompts_are_frozen(self):
        from recordprep.recognition_contract import RecognitionContract
        digests = [
            '4c564fc3a40fc01fecadce36cc01f91ea8b8732d6d0d07a214a033d73543fb8e',
            '6eab77900d4b5b22dba2b8ef6881d6a1b3d2f3e915c41b63ad0fdcbdcb3af7d0',
            '70d81ba03d9c7cff41b19b8ed1bdb563944ad611aba07ffcc2b7bc68d62e22b0',
            '2ea57dc2162a8ea4ef34530a409680bab5b18f5638cee15792112cb25eac4c43',
        ]
        for version, digest in enumerate(digests,1):
            path = PROJECT / f'recordprep/resources/classification/recognition-v{version}.json'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
        old = json.loads((PROJECT / 'recordprep/resources/classification/recognition-v4.json').read_text())
        historical = RecognitionContract(old['contract_id'],
            tuple((side,tuple(values.items())) for side,values in old['page_types'].items()),
            tuple(old['first_pages'].items()))
        for task in ('rt','first_hearing','date_hearing','first_form','first_report','first_motion'):
            self.assertEqual(classifier_document(task,historical).render(),classifier_document(task).render())

    def test_only_minute_boundary_definitions_changed(self):
        old = json.loads((PROJECT / 'recordprep/resources/classification/recognition-v4.json').read_text())
        new = json.loads((PROJECT / 'recordprep/resources/classification/recognition-v5.json').read_text())
        self.assertEqual(old['schema_version'], new['schema_version'])
        self.assertEqual(old['page_types']['rt'], new['page_types']['rt'])
        self.assertEqual(old['page_types']['ct'].keys(), new['page_types']['ct'].keys())
        for key, value in old['page_types']['ct'].items():
            if key not in {'CT_minute_order','CT_form','CT_other'}:
                self.assertEqual(value, new['page_types']['ct'][key])
        for key, value in old['first_pages'].items():
            if key != 'first_minute': self.assertEqual(value, new['first_pages'][key])
        contract = load_recognition()
        definition = dict(contract.descriptions('ct'))['CT_minute_order']
        self.assertIn(definition, classifier_document('ct', contract).render())
        self.assertIn(definition, classifier_document('date_minute', contract).render())
        minute_date = classifier_document('date_minute', contract).render()
        for text in ['top-of-page hearing fields', 'conflicting or unreadable', 'Never borrow',
                     'filing/service stamps', 'print/template-revision', 'future settings']:
            self.assertIn(text, minute_date)

    def test_hearing_prompt_frozen_render_hash(self):
        # Frozen pre-change rendered hearing-date hash, generated from HEAD before editing.
        self.assertEqual(hashlib.sha256(classifier_document('date_hearing').render().encode()).hexdigest(),
                         HEARING_DATE_SHA256)

    def test_fictional_scenarios_express_contrasts_not_a_substring_classifier(self):
        cases = json.loads((PROJECT / 'tests/fixtures/minute-recognition-fictional.json').read_text())
        self.assertEqual(len(cases), 12)
        self.assertEqual({c['type'] for c in cases}, {'CT_minute_order','CT_form','CT_other','CT_report',
                                                    'CT_index','CT_notice','CT_proof_of_service'})
        # Expected interpretations are authored review scenarios, not predictions
        # asserted from a fake model or a deterministic word gate.
        self.assertTrue(all(c['visible'] and c['rationale'] for c in cases))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        from recordprep.ui import main_window as ui
        self.ui = ui
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('text_pages','image_pages','artifacts','classification'):
            (self.root / folder).mkdir()
        self.source = rows()
        for row in self.source:
            (self.root / 'text_pages' / row['file_name']).write_text('Fictional preserved source')
            (self.root / 'image_pages' / (row['file_name'][:-4]+'.png')).write_bytes(b'fictional image')
        (self.root / 'classification/CT_basic_advanced_corrected_dates_names.jsonl').write_text(
            ''.join(json.dumps(row)+'\n' for row in self.source))
        from recordprep.transcript_layout import apply_manual_override
        apply_manual_override(self.root, mode='ct_only')
        self.worker = SimpleNamespace(_resolve_case_root=lambda:self.root, _raise_if_stop_requested=lambda:None,
            selected_pdfs=[], _safe_update_manifest=Mock(), show_toast=Mock(), _finish_step=Mock(),
            _stop_status_if_idle=Mock(), _stop_button_if_idle=Mock(), _update_toc_button=Mock())
        for key in ('step_six_row','step_seven_row','step_correct_boundaries_row'):
            setattr(self.worker,key,Mock())
        self.worker._append_boundary_entry = lambda *args: ui.RecordPrepWindow._append_boundary_entry(self.worker,*args)
        self.stack = __import__('contextlib').ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(ui.GLib,'idle_add',side_effect=lambda fn,*args:fn(*args)))
        self.stack.enter_context(patch.object(ui,'load_classifier_settings',return_value={}))

    def test_same_selection_for_every_profile_context_and_source_preservation(self):
        paths = [p for d in ('text_pages','image_pages','classification') for p in (self.root/d).iterdir()]
        before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        from test_profile_generation import bundled, changed
        custom = changed(bundled('general'),'minutes','Historical user minute prose')
        # Assignment resolution is orthogonal to this selection contract. Freeze
        # publication provenance to test GUI preparation with each resolved value.
        for profile in (None, bundled('california_dependency'), bundled('general'), custom):
            with self.subTest(profile=profile.ref if profile else None), \
                    patch('recordprep.case_profiles.resolve_case_profile',return_value=profile), \
                    patch('recordprep.boundary_profiles.boundary_inputs',return_value={'contract_version':6}), \
                    patch('recordprep.boundary_profiles.case_profile_publication',side_effect=lambda *a:__import__('contextlib').nullcontext()), \
                    patch('recordprep.boundary_profiles.read_case_profile_ref',return_value=profile.ref if profile else None):
                self.assertTrue(self.ui.RecordPrepWindow._run_step_six(self.worker), self.worker.show_toast.call_args_list)
                self.assertTrue(self.ui.RecordPrepWindow._run_step_seven(self.worker), self.worker.show_toast.call_args_list)
                bounds = json.loads((self.root/'artifacts/minutes_boundaries.json').read_text())
                self.assertEqual([(b['start_page'],b['end_page']) for b in bounds],
                                 [('0002','0003'),('0006','0007'),('0009','0009')])
                toc = (self.root/'artifacts/toc.txt').read_text()
                self.assertNotIn('Date unresolved',toc)
                self.assertNotIn('0004',toc)
                # Saved legacy undated entries are only pruned by explicit filter.
                bounds.append(dict(start_page='0004',end_page='0005',date='',unknown='retained source'))
                (self.root/'artifacts/minutes_boundaries.json').write_text(json.dumps(bounds))
                self.assertTrue(self.ui.RecordPrepWindow._run_step_correct_boundaries(self.worker), self.worker.show_toast.call_args_list)
                self.assertEqual(len(json.loads((self.root/'artifacts/minutes_boundaries.json').read_text())),3)
                messages = '\n'.join(str(call) for call in self.worker.show_toast.call_args_list)
                self.assertIn('0004–0005',messages)
                self.assertIn('1 minute entries without recognized dates',messages)
        self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})

    def test_downstream_counts_agree_without_losing_any_physical_source_page(self):
        from recordprep import minute_summaries as minutes
        import importlib.util
        script = PROJECT / '.pi/skills/recordprep-build-source-map/scripts/build_source_map.py'
        spec = importlib.util.spec_from_file_location('dated_minute_source_map',script)
        source_map = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(source_map)
        with patch('recordprep.case_profiles.resolve_case_profile',return_value=None):
            self.assertTrue(self.ui.RecordPrepWindow._run_step_seven(self.worker))
        items = minutes.build_items(self.root, {})
        pages, by_number, _ = source_map.build_pages(self.root, {})
        documents = source_map.boundary_documents(self.root, by_number)
        minute_docs = [d for d in documents if d['type']=='minute_order']
        self.assertEqual(len(items),3)
        self.assertEqual(len(minute_docs),len(items))
        source_map.annotate_pages(by_number, documents, {})
        self.assertEqual([p['file_page'] for p in pages],list(range(1,10)))
        self.assertEqual(by_number[4]['document_ids'],[])
        self.assertEqual(by_number[5]['document_ids'],[])
        # Historical readers deliberately do not reapply eligibility on load.
        path = self.root / 'artifacts/minutes_boundaries.json'
        stored = json.loads(path.read_text())
        stored.append(dict(start_page='0004',end_page='0005',date='',legacy_note='literal'))
        path.write_text(json.dumps(stored))
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.assertEqual(len(minutes.build_items(self.root,{})),4)
        self.assertEqual(len(source_map.boundary_documents(self.root,by_number)),4)
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)

    def test_minute_only_saved_artifact_filter_does_not_skip(self):
        path = self.root / 'artifacts/minutes_boundaries.json'
        kept = dict(start_page='0002',end_page='0003',date='3/5/26',custom='unchanged')
        path.write_text(json.dumps([kept, dict(start_page='0004',end_page='0005',date='TBD')]))
        with patch('recordprep.case_profiles.resolve_case_profile',return_value=None):
            self.assertTrue(self.ui.RecordPrepWindow._run_step_correct_boundaries(self.worker))
        self.assertEqual(json.loads(path.read_text()),[kept])
        self.assertIn('1 total', str(self.worker.show_toast.call_args_list))

    def test_stop_or_selection_resource_change_preserves_prior_outputs(self):
        from recordprep.boundary_profiles import boundary_inputs
        with patch('recordprep.case_profiles.resolve_case_profile',return_value=None):
            self.assertTrue(self.ui.RecordPrepWindow._run_step_six(self.worker))
            self.assertTrue(self.ui.RecordPrepWindow._run_step_seven(self.worker))
            paths = list((self.root/'artifacts').iterdir())
            before = {p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
            expected = boundary_inputs(self.root,None,{})
            self.assertEqual(expected['contract_version'],6)
            self.assertEqual(expected['minute_selection'],selection.SELECTION_ID)
            for method in ('_run_step_six','_run_step_seven','_run_step_correct_boundaries'):
                # First stage snapshot succeeds; publication sees a changed helper.
                with patch('recordprep.boundary_profiles.boundary_inputs',
                           side_effect=[expected,expected | {'minute_selection_sha256':'changed'}]):
                    self.assertFalse(getattr(self.ui.RecordPrepWindow,method)(self.worker))
                self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})
                with patch.object(self.worker,'_raise_if_stop_requested',side_effect=self.ui.StopRequested):
                    self.assertFalse(getattr(self.ui.RecordPrepWindow,method)(self.worker))
                self.assertEqual(before,{p:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})

    def test_corrupt_saved_minute_boundaries_preserve_prior_outputs(self):
        for name in ('hearing','report'):
            (self.root/f'artifacts/{name}_boundaries.json').write_text('[]')
        path = self.root/'artifacts/minutes_boundaries.json'
        for payload in ('not json','{}','[null]', '[{"date":""}]'):
            path.write_text(payload)
            before = (path.read_bytes(),path.stat().st_mtime_ns)
            with patch('recordprep.case_profiles.resolve_case_profile',return_value=None):
                self.assertFalse(self.ui.RecordPrepWindow._run_step_correct_boundaries(self.worker))
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)


HEARING_DATE_SHA256 = '778ecc567fc7384ae8f0c40888a382f0f306bdd66765865fa0c31e2830467571'
