"""Settings adapters preserve legacy identities and stage only selected preferences."""
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from recordprep import paths, pi_runtime as pi, summary_agents as sa, native_freshness as nf
from recordprep import classification_profiles as cp, minute_summaries as minutes, case_name_stage as caption

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / 'tests/fixtures/public_install_baseline.json').read_text())


class ExternalSettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.project = self.root / 'source/.pi'
        shutil.copytree(ROOT / '.pi', self.project)
        self.external = self.root / 'external'; self.external.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(('RECORDPREP_', 'PI_', 'XDG_'))}
        env.update(HOME=str(self.root), PI_CODING_AGENT_DIR=str(self.root / 'agent'), PI_RUN_METRICS_ENABLED='0')
        manager = patch.dict(os.environ, env, clear=True); manager.start(); self.addCleanup(manager.stop)
        self.write(self.project / 'settings.json', BASELINE['pi_settings'])
        self.write(self.project.parent / 'config.json', BASELINE['config'])
        self.spec = importlib.util.spec_from_file_location('public_settings_runner', self.project / 'scripts/run_recordprep_skill.py')
        self.runner = importlib.util.module_from_spec(self.spec)
        import sys
        sys.modules[self.spec.name] = self.runner; self.addCleanup(sys.modules.pop, self.spec.name, None)
        self.spec.loader.exec_module(self.runner)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value))

    def assert_baseline(self):
        self.assertEqual(nf.runtime_identity(self.project), BASELINE['identity'])
        for phase in ('native', 'extract', 'synthesize'):
            self.assertEqual(pi.resolve_stage_model_identity({}, phase, paths.pi_settings_path(self.project)).payload(), BASELINE['models'][phase])
        norm = lambda o: dataclasses.asdict(o) if dataclasses.is_dataclass(o) else o
        current = {
            'classifier': cp.model_identity(cp.load_model_settings(self.project)),
            'extraction': {k: norm(sa.effective_extraction_config(self.project, k)) for k in ('hearings', 'reports')},
            'synthesis': {k: norm(sa.effective_synthesis_config(self.project, k)) for k in ('hearings', 'reports')},
            'minutes': minutes.stage_config(self.project)[1], 'caption_model': caption._model_settings(self.project),
        }
        actual = json.loads(json.dumps(current))
        # Delivery is now explicit in all summary identities; the newly active
        # unassigned extraction skill/system/extension bytes are also hashed.
        # Normalize only those reviewed additions for the historical aggregate.
        from recordprep.summary_prompts import SKILL_DELIVERY_CONTRACT
        for kind in ('hearings', 'reports'):
            self.assertEqual(sa.effective_extraction_config(self.project, kind).fingerprint_payload()['skill_delivery'], SKILL_DELIVERY_CONTRACT)
            self.assertEqual(len(current['extraction'][kind]['runtime_contract_sha256']), 64)
            current['extraction'][kind]['runtime_contract_sha256'] = ''
            self.assertEqual(current['synthesis'][kind].pop('skill_delivery'), SKILL_DELIVERY_CONTRACT)
        self.assertEqual(current['minutes'].pop('skill_delivery'), SKILL_DELIVERY_CONTRACT)
        # The frozen fixture intentionally selected fixture/extract and low
        # summary reasoning. Those retired keys now inherit fixture/model/high.
        # Assert the real identity, then normalize ONLY those known identity
        # differences for the historical content/resource contract hashes below.
        for kind in ('hearings', 'reports'):
            self.assertEqual(current['extraction'][kind]['model'], 'fixture/model')
            self.assertEqual(current['synthesis'][kind]['thinking'], 'high')
            current['extraction'][kind]['model'] = 'fixture/extract'
            current['synthesis'][kind]['thinking'] = 'low'
        self.assertEqual(current['minutes']['thinking'], 'high')
        current['minutes']['thinking'] = 'low'
        # Frozen pre-installer fixture remains historical. Reviewed aggregates
        # retain the hearing/report editorial and plain-English minute contracts.
        changed_contracts = {
            'extraction': '13b7cc7fb8e042404848aa5be3a23465dda8a5def9a7ef8b59cb82d49f7979c9',
            'synthesis': '4f8bb1a7cbdb6314058f4f2f8ad87833e8c57bd5178141608148dd3a57bf3a56',
            'minutes': '11b5a941b0d370a71c9893d413a3d839c5fe51ffb7c1715a9b185da02e2597a0',
        }
        for key, value in current.items():
            with self.subTest(identity=key): self.assertEqual(sa.sha256_json(value), changed_contracts.get(key, BASELINE[key + '_sha256']))
        return actual

    def test_legacy_and_external_identical_effective_identities(self):
        legacy = self.assert_baseline()
        original = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.project / 'settings.json', self.project.parent / 'config.json')}
        self.write(self.external / 'pi/settings.json', BASELINE['pi_settings']); self.write(self.external / 'config.json', BASELINE['config'])
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)):
            # Source preferences deliberately disagree, and cannot leak into public work.
            self.write(self.project / 'settings.json', {'defaultProvider': 'foreign', 'defaultModel': 'wrong'})
            self.write(self.project.parent / 'config.json', {'classifier_model_id': 'wrong'})
            source_bytes = (self.project / 'settings.json').read_bytes()
            self.assertEqual(self.assert_baseline(), legacy)
            self.assertEqual(paths.resource_root(self.project), self.project)
            workspace, staged, skill = self.runner._staged_workspace(self.project, 'recordprep-extract-hearing', self.root)
            try:
                self.assertEqual(json.loads((staged / 'settings.json').read_text()), BASELINE['pi_settings'])
                self.assertTrue(skill.is_dir()); self.assertEqual((self.project / 'settings.json').read_bytes(), source_bytes)
            finally: shutil.rmtree(workspace)
        # The independent legacy staging API preserves exact bytes, not just JSON.
        self.project.joinpath('settings.json').write_bytes(original[self.project / 'settings.json'][0])
        staged = self.root / 'staged.json'; paths.stage_pi_settings(self.project, staged)
        self.assertEqual(json.loads(staged.read_text()), dict(json.loads(original[self.project / 'settings.json'][0]), enableSkillCommands=True))

    def test_missing_public_preferences_stay_empty_until_explicit_save(self):
        before = (self.project / 'settings.json').read_bytes()
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)):
            self.assertEqual(paths.effective_pi_settings(self.project), {})
            self.assertIsNone(pi.current_project_pi_model()); self.assertIsNone(pi.current_project_pi_thinking_level())
            self.assertFalse((self.external / 'pi/settings.json').exists())
            pi.save_project_pi_model(pi.PiModel('synthetic', 'chosen', 'Chosen'))
            pi.save_project_pi_thinking_level('low')
            target = self.external / 'pi/settings.json'
            self.assertEqual(pi.current_project_pi_model(), ('synthetic', 'chosen'))
            self.assertEqual(pi.current_project_pi_thinking_level(), 'low')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
            self.assertFalse(list(target.parent.glob('.*.tmp')))
            # Explicit settings-file arguments are still usable by tests/staging.
            self.assertEqual(pi.current_project_pi_model(self.project / 'settings.json'), ('synthetic', 'fixture/model'))
        self.assertEqual((self.project / 'settings.json').read_bytes(), before)

    def test_malformed_existing_preferences_never_repaired(self):
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)):
            for content in ('{bad', '[]'):
                target = self.external / 'pi/settings.json'; target.parent.mkdir(exist_ok=True); target.write_text(content)
                with self.subTest(content=content):
                    with self.assertRaises(pi.PiSettingsError): pi.save_project_pi_model(pi.PiModel('s', 'm', 'M'))
                    self.assertEqual(target.read_text(), content)
                    self.assertTrue(any('preferences are invalid' in issue for issue in self.runner._resource_issues(self.project)))
            target = self.external / 'config.json'; target.write_text('{bad')
            with self.assertRaises(ValueError): paths.atomic_private_json(target, {})
            self.assertEqual(target.read_text(), '{bad')
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR='relative'):
            with self.assertRaises(ValueError): paths.application_config_path()

    def test_model_discovery_uses_selected_workspace_and_removes_it(self):
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)):
            seen = []
            def query(command, request, **kw):
                cwd = kw['cwd']; seen.append(cwd)
                self.assertNotEqual(cwd, ROOT)
                self.assertEqual(json.loads((cwd / '.pi/settings.json').read_text()), {})
                return {'success': True, 'data': {'models': []}}
            with patch.object(pi, '_query_pi_rpc', query): self.assertEqual(pi.available_pi_models(['synthetic']), [])
            self.assertFalse(seen[0].exists())

    def test_changed_preferences_invalidate_effective_fingerprints(self):
        self.write(self.external / 'pi/settings.json', BASELINE['pi_settings']); self.write(self.external / 'config.json', BASELINE['config'])
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)):
            before = nf.runtime_digest(self.project, 'participants')
            extraction = sa.effective_extraction_config(self.project, 'hearings')
            minute = minutes.stage_config(self.project)[1]
            self.write(self.external / 'pi/settings.json', BASELINE['pi_settings'] | {'defaultModel': 'changed'})
            self.assertNotEqual(before, nf.runtime_digest(self.project, 'participants'))
            self.assertNotEqual(minute, minutes.stage_config(self.project)[1])
            changed = sa.effective_extraction_config(self.project, 'hearings')
            self.assertNotEqual(extraction, changed)
            self.write(self.external / 'config.json', BASELINE['config'] | {'summary_extract_pi_model': 'changed-extract'})
            self.assertEqual(changed, sa.effective_extraction_config(self.project, 'hearings'))

    def test_pre_delivery_native_fingerprints_are_no_longer_equivalent(self):
        self.assert_baseline()
        for stage in nf.STEPS:
            with self.subTest(stage=stage):
                self.assertFalse(nf.runtime_matches(BASELINE['runtime'][stage], nf.runtime_digest(self.project, stage), self.project, stage))
                self.assertFalse(nf.runtime_matches('unknown', nf.runtime_digest(self.project, stage), self.project, stage))
        source = self.project / 'SYSTEM.md'; source.write_text(source.read_text() + '\nChanged\n')
        for stage in nf.STEPS:
            self.assertFalse(nf.runtime_matches(BASELINE['runtime'][stage], nf.runtime_digest(self.project, stage), self.project, stage))

    def test_public_native_child_and_capacity_use_selected_preferences(self):
        from types import SimpleNamespace
        root = self.root / 'case'; (root / 'text_pages').mkdir(parents=True)
        (root / 'text_pages/0001.txt').write_text('Synthetic v. Example')
        (root / 'case_name.txt').write_text('Prior_Name')
        self.write(self.external / 'pi/settings.json', BASELINE['pi_settings'])
        self.write(self.project / 'settings.json', {'defaultProvider': 'foreign', 'defaultModel': 'wrong'})
        workspaces = []
        def child(command, *, cwd, env, **kwargs):
            workspaces.append(Path(cwd))
            self.assertEqual(json.loads((Path(cwd) / '.pi/settings.json').read_text()), BASELINE['pi_settings'])
            self.assertEqual(command[command.index('--tools') + 1], 'read,write,edit')
            spec = json.loads(Path(env['RECORDPREP_CASE_NAME_ACCESS_SPEC']).read_text())
            Path(spec['candidate']).write_text('Synthetic_v._Example')
            return SimpleNamespace(pid=os.getpid(), wait=lambda **kw: 0)
        with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(self.external)), \
             patch.object(self.runner, '_resolve_pi_command', return_value=['/usr/bin/true']), \
             patch.object(self.runner, '_check_pi_version'), patch.object(self.runner, 'StageMonitor'), \
             patch.object(self.runner.sys.stdin, 'isatty', return_value=False), \
             patch.object(self.runner.subprocess, 'Popen', side_effect=child), \
             patch('recordprep.run_metrics.instrument', side_effect=lambda command, env, *args: (command, env)):
            self.assertEqual(self.runner._run_stage(self.runner.STAGES['infer_case'], root, self.project), 0)
            from recordprep import summary_preflight
            with patch.object(summary_preflight, 'resolve_stage_capacity') as capacity:
                self.runner._stage_capacity('extract', 'hearings', {}, self.project, [])
                self.assertEqual(capacity.call_args.args[2], self.external / 'pi/settings.json')
        self.assertTrue(workspaces); self.assertTrue(all(not p.exists() for p in workspaces))
        self.assertEqual(json.loads((self.project / 'settings.json').read_text())['defaultModel'], 'wrong')

    def test_filesystem_discovery_restricted_path(self):
        self.assertIsNone(pi.find_pi(self.root, path_env='/nonexistent'))
        self.assertEqual(pi.discover_pi_agent_command(self.root, path_env='/nonexistent'), 'pi')
        for location in ('custom-agent/bin/pi', '.pi/agent/bin/pi', '.local/bin/pi', '.local/share/pi-node/node-test/bin/pi'):
            with self.subTest(location=location):
                p = self.root / location; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('#!/bin/sh\nexit 99\n'); p.chmod(0o700)
                with patch.dict(os.environ, PI_CODING_AGENT_DIR=str(self.root / 'custom-agent')):
                    self.assertEqual(pi.find_pi(self.root, path_env='/nonexistent'), str(p))
                p.unlink()


if __name__ == '__main__': unittest.main()
