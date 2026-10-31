"""Native stages invalidate only their own or shared generation dependencies."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import native_freshness as nf, summary_agents as sa

PROJECT = Path(__file__).resolve().parents[1]


class NativeFreshnessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / '.pi'
        shutil.copytree(PROJECT / '.pi', self.project)
        self.runner = self.project / 'scripts/run_recordprep_skill.py'

    def codes(self):
        return {stage: nf.stage_code_digest(self.project, stage) for stage in nf.STEPS}

    def test_overview_runner_change_leaves_participants_current(self):
        before = self.codes()
        self.runner.write_text(self.runner.read_text().replace('APPLICATION INPUT MANIFEST', 'UPDATED OVERVIEW MANIFEST'))
        after = self.codes()
        self.assertEqual(before['participants'], after['participants'])
        self.assertNotEqual(before['overview'], after['overview'])

    def test_participant_and_shared_runner_changes_are_detected(self):
        original = self.runner.read_text()
        before = self.codes()
        self.runner.write_text(original.replace('reads.append(worklist)', 'reads.append(worklist.resolve())'))
        after = self.codes()
        self.assertNotEqual(before['participants'], after['participants'])
        self.assertEqual(before['overview'], after['overview'])
        self.runner.write_text(original.replace('env["TMPDIR"] = str(workspace / "tmp")', 'env["TMPDIR"] = str(workspace / "different-tmp")'))
        for stage, digest in self.codes().items():
            self.assertNotEqual(before[stage], digest)

    def test_unrelated_summary_runner_changes_do_not_stale_native_stages(self):
        before = self.codes()
        self.runner.write_text(self.runner.read_text() + '\ndef unrelated_summary_helper():\n    return "new summary behavior"\n')
        self.assertEqual(before, self.codes())

    def test_stage_core_projection_and_unknown_shared_conditions(self):
        source = '''
PARTICIPANT_CORE = "participants"
OVERVIEW_CORE = "overview"
def entry(stage):
    if stage == "participants":
        return PARTICIPANT_CORE
    else:
        if unknown_runtime_condition:
            return OVERVIEW_CORE
        return "fallback"
'''
        participant = nf.projected_code(source, 'participants', ('entry',))
        self.assertEqual(participant, nf.projected_code(source.replace('"overview"', '"overview updated"'), 'participants', ('entry',)))
        overview = nf.projected_code(source, 'overview', ('entry',))
        self.assertNotEqual(overview, nf.projected_code(source.replace('"fallback"', '"changed"'), 'overview', ('entry',)))

    def test_normalizer_changes_only_participant_runtime(self):
        before = self.codes()
        original = sa._resource_sha256
        with patch.object(sa, '_resource_sha256', side_effect=lambda p: 'changed' if Path(p).name == 'participant_candidates.py' else original(p)):
            after = self.codes()
        self.assertNotEqual(before['participants'], after['participants'])
        self.assertEqual(before['overview'], after['overview'])

    def test_stage_prompts_and_model_settings_remain_dependencies(self):
        from recordprep.native_profiles import compile_native
        from test_profile_generation import bundled
        profile = bundled('general')
        before = {s: compile_native(profile, s, self.project)[1]['components'] for s in nf.STEPS}
        prompt = self.project / 'resources/profile-overview.md'
        prompt.write_text(prompt.read_text() + '\nNew overview-only instructions.\n')
        after = {s: compile_native(profile, s, self.project)[1]['components'] for s in nf.STEPS}
        self.assertEqual(before['participants'], after['participants'])
        self.assertNotEqual(before['overview'], after['overview'])
        with patch.object(nf, 'runtime_identity', return_value={'model': 'one'}):
            runtime = {s: nf.runtime_digest(self.project, s) for s in nf.STEPS}
        with patch.object(nf, 'runtime_identity', return_value={'model': 'two'}):
            for stage in nf.STEPS:
                self.assertNotEqual(runtime[stage], nf.runtime_digest(self.project, stage))

    def test_pre_expansion_legacy_is_not_equivalent_to_delivered_skills(self):
        manifest = json.loads((PROJECT / 'recordprep/resources/native_runtime_compat.json').read_text())
        identity = {'provider': 'synthetic', 'model': 'test', 'thinking': 'low', 'system': 'x', 'auto_exit': 'y', 'inherited': None}
        with patch.object(nf, 'runtime_identity', return_value=identity):
            expected = nf.runtime_digest(self.project, 'participants')
            self.assertTrue(nf.runtime_matches(expected, expected, self.project, 'participants'))
            for stage in nf.STEPS:
                for legacy in manifest[stage]['legacy']:
                    recorded = sa.sha256_json(identity | legacy)
                    self.assertFalse(nf.runtime_matches(recorded, nf.runtime_digest(self.project, stage), self.project, stage))
                    # Even refreshing a historical code guard must not bless
                    # pre-expansion delivery as equivalent to the corrected run.
                    with patch.object(nf, 'stage_code_digest', return_value=manifest[stage]['stage_code_sha256']):
                        self.assertFalse(nf.runtime_matches(recorded, nf.runtime_digest(self.project, stage), self.project, stage))
            self.assertFalse(nf.runtime_matches('unknown', expected, self.project, 'participants'))
            self.assertFalse(nf.runtime_matches(recorded, nf.runtime_digest(self.project, 'overview'), self.project, 'overview'))
            with patch.object(nf, 'runtime_identity', return_value=identity | {'model': 'different'}):
                self.assertFalse(nf.runtime_matches(recorded, nf.runtime_digest(self.project, 'participants'), self.project, 'participants'))
            self.runner.write_text(self.runner.read_text().replace('reads.append(worklist)', 'reads.append(worklist.resolve())'))
            self.assertFalse(nf.runtime_matches(recorded, nf.runtime_digest(self.project, 'participants'), self.project, 'participants'))
