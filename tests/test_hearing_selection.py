"""Fictional-only acceptance of readability, dataset shrink and navigation policy."""
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import summary_agents as sa, boundary_profiles as bp, native_freshness as nf
from recordprep.summary_profiles import compile_summary, HEARING_READABILITY, HEARING_QUOTE_COVERAGE
from recordprep.ui import main_window as ui
from test_profile_generation import bundled, seed_profile_preparation
from tests.summary_agent_fixtures import synthetic_facts_row

ROOT = Path(__file__).resolve().parents[1]


class ParagraphTests(unittest.TestCase):
    def test_explicit_breaks_soft_wraps_empty_entries_and_placeholder_order(self):
        row = synthetic_facts_row('hearings')
        category = row['categories'][0]
        category['digest'] = {'text': 'A material condition.', 'evidence': [
            {'quote_id': row['item_id'] + '/' + category['id'] + '/1', 'text': 'EXACT SOURCE',
             'file_page': 1, 'verified': True}]}
        q = '{{quote:' + category['digest']['evidence'][0]['quote_id'] + '}}'
        payload = [{'item_id': row['item_id'], 'paragraphs': [
            ' First\r\nsoft wrap ' + q + '\r\n \t\r\nSecond paragraph.\n\n\nThird.', '', '\r\n', 'Fourth.'],
            'quote_capitalizations': {category['digest']['evidence'][0]['quote_id']: 'Exact source'}}]
        sections, flags = sa.normalize_synthesis_sections([row], payload)
        self.assertEqual(sections[0].paragraphs, ['First soft wrap ' + q, 'Second paragraph.', 'Third.', 'Fourth.'])
        direct = sa.SynthesisSectionCandidate(row['item_id'], payload[0]['paragraphs'])
        text = sa.render_final_summary('hearings', '', [row], [direct], {row['item_id']: (1, None)})
        self.assertIn('First soft wrap “EXACT SOURCE”\n\nSecond paragraph.\n\nThird.\n\nFourth.', text)
        rendered = sa.render_section_paragraphs(row, sections[0].paragraphs, sections[0].quote_capitalizations)
        self.assertEqual(rendered[0], 'First soft wrap “Exact source”')
        self.assertNotIn('unknown_placeholder', ' '.join(flags))
        self.assertEqual(sa.normalize_paragraphs(['One.\n\nTwo.', 'Three.']), ['One.', 'Two.', 'Three.'])
        self.assertEqual(sa.normalize_paragraphs(['One.\r \rTwo.']), ['One.', 'Two.'])
        from recordprep.summary_editions import build_summary_edition, validate_edition_payload
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'summaries').mkdir()
            source = root / 'summaries/hearings_sum_Fictional.txt'
            source.write_text(text)
            edition = build_summary_edition('hearings', source, root)
            self.assertEqual(validate_edition_payload(edition.page_map, kind='hearings', root_dir=root,
                                                     source_text=text, pdf_bytes=edition.pdf_bytes), [])
            self.assertEqual([quote.phrase for page in edition.pages for quote in page.quotes], ['EXACT SOURCE'])

    def test_unknown_placeholder_still_falls_back_and_missing_anchors_are_nonfatal(self):
        row = synthetic_facts_row('hearings')
        row['categories'][0]['digest'] = {'text': 'First.\n\nSecond.', 'evidence': []}
        sections, flags = sa.normalize_synthesis_sections([row], [{'item_id': row['item_id'], 'paragraphs': ['Bad {{quote:unknown}}.']}])
        self.assertEqual(sections[0].paragraphs, ['First.', 'Second.'])
        self.assertTrue(any(f.startswith('unknown_placeholder_fallback:') for f in flags))
        sections, flags = sa.normalize_synthesis_sections([row], [{'item_id': row['item_id'], 'paragraphs': ['Appropriate paraphrase.']}])
        self.assertEqual(sections[0].paragraphs, ['Appropriate paraphrase.'])

    def test_profile_and_unassigned_contracts_and_custom_bytes(self):
        profile = bundled('general')
        for phrase in (HEARING_READABILITY,):
            self.assertIn(phrase, compile_summary(profile, 'hearings', 'synthesize').prompt)
            self.assertIn(phrase, sa.default_guidance('hearings', 'synthesize'))
        self.assertIn(HEARING_QUOTE_COVERAGE, compile_summary(profile, 'hearings', 'extract').prompt)
        self.assertIn(HEARING_QUOTE_COVERAGE, sa.default_guidance('hearings', 'extract'))
        for phase, old in [('extract', sa.PREVIOUS_HEARING_QUOTE_COVERAGE_GUIDANCE),
                           ('synthesize', sa.PREVIOUS_HEARING_READABILITY_GUIDANCE)]:
            self.assertEqual(sa.resolve_phase_guidance('hearings', phase, old).origin, 'migrated')
            custom = '  Genuine custom guidance.\n\n'
            self.assertEqual(sa.resolve_phase_guidance('hearings', phase, custom).custom_guidance, custom)
        self.assertNotIn(HEARING_QUOTE_COVERAGE, compile_summary(profile, 'reports', 'extract').prompt)


class TocPolicyTests(unittest.TestCase):
    def test_known_dates_normalize_but_unknowns_and_other_sections_survive(self):
        lines = ['REPORTS', '\tMarch 5, 2026 0001', '', 'MINUTE ORDERS',
                 '\tMarch 5, 2026 0002', '\t03/05/2026 0003', '\t2026-03-05 0004',
                 '\tThursday, March 5, 2026 0005', '\tMar 05, 2026 0006',
                 '\tDate unresolved 0007', '\tDate unresolved 0008', '\tunknown 0009',
                 '\tunknown 0010', '\tFebruary 30, 2026 0011', '\tFebruary 30, 2026 0012',
                 '', 'HEARINGS', '\tMarch 5, 2026 0013']
        result, count = ui._correct_toc_lines(lines)
        self.assertEqual(count, 4)
        self.assertEqual(result, lines[:5] + lines[9:])
        self.assertEqual(ui._correct_toc_lines(result), (result, 0))
        with self.assertRaises(ui.StopRequested):
            ui._correct_toc_lines(lines, Mock(side_effect=ui.StopRequested))

    def test_profile_completion_detects_duplicates_even_with_current_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'artifacts').mkdir()
            path = root / 'artifacts/toc.txt'
            original = 'MINUTE ORDERS\n\tMarch 5, 2026 0001\n\t03/05/2026 0002\n'
            path.write_text(original)
            worker = SimpleNamespace()
            with patch('recordprep.case_profiles.resolve_case_profile', return_value=Mock()), \
                 patch.object(bp, 'toc_issues', return_value=[]):
                self.assertFalse(ui.RecordPrepWindow._step_artifact_complete(worker, 'correct_toc', root))
                path.write_text('\n'.join(ui._correct_toc_lines(original.splitlines())[0]) + '\n')
                self.assertTrue(ui.RecordPrepWindow._step_artifact_complete(worker, 'correct_toc', root))


class ShrinkingDatasetTests(unittest.TestCase):
    def test_actual_runner_prunes_renumbers_reuses_and_republishes_metadata(self):
        from recordprep.case_profiles import apply_case_profile
        from recordprep.profile_store import ProfileStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'bundle'; (root / 'text_pages').mkdir(parents=True); (root / 'artifacts').mkdir()
            (root / 'case_name.txt').write_text('Fictional')
            for i in range(1,4): (root / f'text_pages/{i:04d}.txt').write_text('Distinct material condition applies.')
            boundaries = [{'start_page': i, 'end_page': i, 'report_name': f'Report {i}'} for i in range(1,4)]
            path = root / 'artifacts/report_boundaries.json'; path.write_text(json.dumps(boundaries))
            project = Path(temp) / 'project/.pi'; shutil.copytree(ROOT / '.pi', project)
            (project.parent / 'config.json').write_text('{}')
            spec = importlib.util.spec_from_file_location('shrinking_runner', project / 'scripts/run_recordprep_skill.py')
            runner = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runner; spec.loader.exec_module(runner)
            self.addCleanup(sys.modules.pop, spec.name, None)
            profile = bundled('general')
            store = ProfileStore('recordprep', config_root=Path(temp)/'config', data_root=Path(temp)/'data')
            store.accept_profile(profile, expected_previous_digest=None)
            apply_case_profile(root, profile.ref, expected_previous=None, store=store)
            stage = runner.SkillStage('create_report_summaries', 'Create report summaries', 'recordprep-extract-report', '')
            category = profile.resource('reports')[0]['id']
            def extraction(*args):
                return {'categories': [{'id': category, 'digest': {'text': 'A material condition applies.',
                    'evidence': [{'file_page': args[3].start_page, 'text': 'material condition'}]}}]}
            datasets = []
            def synthesis(*args):
                rows = args[3]; datasets.append(copy.deepcopy(rows))
                return [{'item_id': r['item_id'], 'paragraphs': ['A {{quote:' + r['categories'][0]['digest']['evidence'][0]['quote_id'] + '}} applies.']} for r in rows], []
            with patch('recordprep.case_profiles.profile_store', return_value=store), \
                 patch.object(runner, '_resolve_pi_command', return_value=['synthetic']), \
                 patch.object(runner, '_check_pi_version'), patch.object(runner, '_stage_capacity', return_value=None), \
                 patch.object(runner, '_report_capacity'), \
                 patch('recordprep.summary_preflight.pi_runtime.available_pi_models', return_value=[]), \
                 patch.object(runner, '_run_extraction_child', side_effect=extraction) as extract, \
                 patch.object(runner, '_run_synthesis_child', side_effect=synthesis) as synth:
                seed_profile_preparation(root, profile, project)
                self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                original = sa.load_digest_markdown(root, 'reports'); saved = copy.deepcopy(original)
                config = sa.effective_extraction_config(project, 'reports', profile=profile)
                path.write_text(json.dumps([boundaries[0], boundaries[2]]))
                seed_profile_preparation(root, profile, project)
                items = sa.build_work_items(root, config)
                reconciled, stale = sa.reconcile_digest_rows(original, items)
                self.assertEqual(stale, []); self.assertEqual(original, saved)
                self.assertEqual([r['ordinal'] for r in reconciled], [1,2])
                for row, old in zip(reconciled, (saved[0],saved[2])):
                    self.assertEqual(row | {'ordinal': old['ordinal']}, old)
                    self.assertIsNot(row, old)
                self.assertTrue(sa.summary_stage_freshness_issues(root, 'reports', project_dir=project))
                self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                self.assertEqual(extract.call_count, 3); self.assertEqual(synth.call_count, 2)
                rows = sa.load_digest_markdown(root, 'reports')
                self.assertEqual(rows, reconciled)
                self.assertEqual([r['ordinal'] for r in sa.build_dataset_overview(rows)['items']], [1,2])
                self.assertEqual(sa.validate_summary_agent_outputs(root, 'reports'), [])
                self.assertEqual(sa.summary_stage_freshness_issues(root, 'reports', project_dir=project), [])
                self.assertEqual(len(datasets[-1]), 2)
                self.assertEqual(runner._run_summary_stage(stage, root, project), 0)
                self.assertEqual(extract.call_count, 3); self.assertEqual(synth.call_count, 2)


if __name__ == '__main__': unittest.main()
