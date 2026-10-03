"""Real summary child wrapper/command builder/extension and installed offline SDK."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT.parent / 'PiRunMetrics/tests'))
from sdk_acceptance import Acceptance, tool, stop

spec = importlib.util.spec_from_file_location('recordprep_sdk_runner', PROJECT / '.pi/scripts/run_recordprep_skill.py')
runner = importlib.util.module_from_spec(spec); sys.modules[spec.name] = runner; spec.loader.exec_module(runner)


class RecordPrepCollectionAcceptance(unittest.TestCase):
    def test_extraction_and_synthesis_outcomes_remain_candidate_not_pipeline_success(self):
        h = Acceptance('recordprep')
        try:
            resources = h.resources(PROJECT / '.pi')
            candidate = h.workspace / 'candidate.json'
            work_spec = h.workspace / 'spec.json'
            work_spec.write_text(json.dumps({'source': 'CANARY complete synthetic source', 'item_id': 'synthetic-item', 'candidate_path': str(candidate)}))
            dataset = h.workspace / 'dataset.json'
            dataset.write_text(json.dumps({'artifact': 'synthetic', 'kind': 'reports', 'total_rows': 1, 'candidate_path': str(candidate),
                'rows': [{'item_id': 'synthetic-item', 'ordinal': 1, 'label': 'CANARY synthetic label', 'categories': []}], 'documents': ['CANARY synthetic digest']}))
            extra = {}; skill = ''; mode = ''
            def factory(env):
                staged = h.workspace / '.pi'; shutil.copytree(resources, staged)
                command = runner._base_child_command([str(h.pi)], staged, staged/'skills'/skill, tools, h.prompt.read_text(), {}, mode)
                return command, env
            def execute(argv, env):
                output = io.StringIO()
                with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
                    child = runner._SummaryChildRunner(argv, 'synthetic child', h.workspace, .01, 30, extra,
                        metrics_workflow=skill, metrics_prefix=[str(h.pi)])
                    code = child.run()
                    if child.process and child.process.stdout: child.process.stdout.close()
                self.assertNotIn('CANARY', output.getvalue())
                return SimpleNamespace(returncode=code, stdout=output.getvalue(), stderr='')
            for mode, skill in [('extract', 'recordprep-extract-hearing'), ('extract', 'recordprep-extract-report'),
                               ('synthesize', 'recordprep-synthesize-hearings'), ('synthesize', 'recordprep-synthesize-reports')]:
                extra = {'RECORDPREP_SUMMARY_MODE': mode, 'RECORDPREP_SUMMARY_WORK_SPEC': str(work_spec), 'RECORDPREP_SUMMARY_DATASET': str(dataset)}
                tools = ('recordprep_get_source,recordprep_submit_extraction' if mode == 'extract' else
                         'recordprep_synthesis_scratchpad,recordprep_get_facts,recordprep_submit_summary_section,recordprep_finish_summary')
                if mode == 'extract':
                    frames = [tool('recordprep_get_source', {}), tool('recordprep_submit_extraction', {'categories': []})]
                    expected = {'source.served': 1, 'extraction.candidate_accepted': 1}
                else:
                    frames = [tool('recordprep_synthesis_scratchpad', {'action': 'replace', 'notes': 'CANARY private scratchpad'}),
                              tool('recordprep_get_facts', {'ordinal': 2}),
                              tool('recordprep_submit_summary_section', {'item_id': 'CANARY unknown item', 'paragraphs': []}),
                              tool('recordprep_submit_summary_section', {'item_id': 'synthetic-item', 'paragraphs': ['CANARY "typed quote" {{quote:CANARY-private-id}}']}),
                              tool('recordprep_finish_summary', {})]
                    expected = {'scratchpad.replaced': 1, 'facts.input_rejected': 1, 'section.input_rejected': 1,
                                'section.recorded': 1, 'section.advisory_feedback': 1, 'section.invalid_quote_feedback': 1,
                                'finish.candidate_accepted': 1, 'finish.coverage_feedback': 1}
                with self.subTest(skill=skill):
                    records, capture = h.run(factory, frames, execute=execute)
                    self.assertFalse(capture['persistent_session'])
                    self.assertEqual(records[0]['app_observations']['recordprep_summary']['counts'], expected)
                    self.assertEqual(records[1]['app_observations']['recordprep_summary']['counts'], {})
                    self.assertFalse(records[0]['app_observations']['recordprep_summary']['incomplete'])
                    self.assertEqual(sum(t['execution_errors'] for t in records[0]['tools'].values()), 0)
            mode = 'extract'; skill = 'recordprep-extract-report'; tools = 'recordprep_get_source,recordprep_submit_extraction'
            # A real candidate write error, returned normally as REJECTED.
            value = json.loads(work_spec.read_text()); value['candidate_path'] = str(h.workspace/'missing-parent/candidate.json'); work_spec.write_text(json.dumps(value))
            extra['RECORDPREP_SUMMARY_MODE'] = mode
            records, _ = h.run(factory, [tool('recordprep_submit_extraction', {'categories': []}), stop()], execute=execute)
            self.assertEqual(records[0]['app_observations']['recordprep_summary']['counts'], {'extraction.publication_failed': 1})
            self.assertEqual(records[0]['tools']['recordprep_submit_extraction']['execution_errors'], 0)
            # Missing prerequisites keep their existing thrown execution-error semantics.
            extra['RECORDPREP_SUMMARY_WORK_SPEC'] = ''
            records, _ = h.run(factory, [tool('recordprep_get_source', {}), stop()], execute=execute)
            self.assertEqual(records[0]['app_observations']['recordprep_summary']['counts'], {'source.prerequisite_unavailable': 1})
            self.assertEqual(records[0]['tools']['recordprep_get_source']['execution_errors'], 1)
        finally: h.close()

    def test_minute_tools_with_installed_offline_sdk_and_private_output(self):
        h = Acceptance('recordprep')
        try:
            resources = h.resources(PROJECT / '.pi')
            candidate = h.workspace / 'minute-candidate.json'
            spec = h.workspace / 'minute-spec.json'
            spec.write_text(json.dumps({
                'source': 'CANARY FIRST PAGE: Mother present in person.',
                'item_id': 'minute:0001', 'candidate_path': str(candidate),
            }))
            skill = 'recordprep-summarize-minutes'
            def factory(env):
                staged = h.workspace / '.pi'
                shutil.copytree(resources, staged)
                command = runner._base_child_command(
                    [str(h.pi)], staged, staged/'skills'/skill,
                    'recordprep_get_minute_source,recordprep_submit_minute_summary',
                    h.prompt.read_text(), {}, 'synthesize', 'recordprep-minute-tools.ts',
                )
                return command, env
            def execute(argv, env):
                output = io.StringIO()
                with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
                    child = runner._SummaryChildRunner(
                        argv, 'synthetic minute child', h.workspace, .01, 30,
                        {'RECORDPREP_MINUTE_WORK_SPEC': str(spec)},
                        metrics_workflow=skill, metrics_prefix=[str(h.pi)],
                    )
                    code = child.run()
                    if child.process and child.process.stdout:
                        child.process.stdout.close()
                self.assertNotIn('CANARY', output.getvalue())
                return SimpleNamespace(returncode=code, stdout=output.getvalue(), stderr='')
            frames = [tool('recordprep_get_minute_source', {}), tool('recordprep_submit_minute_summary', {
                'hearing': 'CANARY Review', 'reporting': 'reported',
                'parents': [{'parent': 'Mother', 'status': 'present', 'first_page_evidence': 'Mother present in person.'}],
                'orders': 'CANARY Continued.',
            })]
            records, capture = h.run(factory, frames, execute=execute)
            self.assertFalse(capture['persistent_session'])
            self.assertEqual({row['workflow'] for row in records}, {skill})
            self.assertEqual(json.loads(candidate.read_text())['artifact'], 'recordprep-minute-candidate')
            self.assertEqual(sum(t['execution_errors'] for t in records[0]['tools'].values()), 0)
        finally:
            h.close()

    def test_native_stage_actual_wrapper_does_not_treat_settlement_as_valid_layout(self):
        h = Acceptance('recordprep')
        try:
            resources = h.resources(PROJECT/'.pi')
            bundle = h.root/'synthetic-bundle'; (bundle/'text_pages').mkdir(parents=True)
            (bundle/'text_pages/0001.txt').write_text('CANARY synthetic transcript page')
            stage = runner.STAGES['detect_transcript_layout']
            def execute(argv, env):
                stdout = io.StringIO()
                env = dict(env, RECORDPREP_PI_COMMAND_ARGC='1', RECORDPREP_PI_COMMAND_ARG_0=str(h.pi))
                with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(stdout):
                    result = runner._run_stage(stage, bundle, resources)
                self.assertEqual(result, 3)  # No actual validated layout was published.
                return SimpleNamespace(returncode=0, stdout=stdout.getvalue(), stderr='')
            def normalize(capture):
                cwd = capture['cwd']
                self.assertTrue(Path(cwd).is_relative_to(Path(h.env['XDG_CACHE_HOME'])/'recordprep-pi-workspaces'))
                return json.loads(json.dumps(capture).replace(cwd, '<generated-native-stage-workspace>'))
            records, _ = h.run(lambda env: ([str(h.pi)], env), [tool('read', {'path': str(h.workspace/'synthetic.txt')}), stop()], execute=execute, normalize=normalize)
            self.assertEqual({r['workflow'] for r in records}, {'detect_transcript_layout'})
        finally: h.close()


if __name__ == '__main__': unittest.main()
