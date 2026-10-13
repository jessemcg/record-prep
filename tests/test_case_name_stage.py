"""Offline native caption boundary, publication, freshness and routing tests."""
import importlib.util
import json
import os
import shutil
import signal
import time
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import case_name_stage as stage
from recordprep.case_profiles import apply_case_profile
from recordprep import practice_profiles as api
from recordprep.ui import main_window as ui

PROJECT = Path(__file__).resolve().parents[1]


class CaseNameStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "case_bundle"
        (self.root / "text_pages").mkdir(parents=True)
        for page in range(1, 5):
            (self.root / "text_pages" / f"{page:04d}.txt").write_text(f"Smith v. Jones\nSynthetic page {page}")
        (self.root / "case_name.txt").write_text("Prior_Name")
        self.project = self.base / ".pi"
        shutil.copytree(PROJECT / ".pi", self.project)
        (self.project / "settings.json").write_text(json.dumps({"defaultProvider": "synthetic", "defaultModel": "caption-model", "defaultThinkingLevel": "low"}))
        self.workspace = self.base / "workspace"
        self.workspace.mkdir(mode=0o700)
        self.env = patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(self.base / "agent"), "XDG_CACHE_HOME": str(self.base / "cache"), "PI_RUN_METRICS_ENABLED": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def prepared(self):
        guard, ref, candidate, spec, prompt = stage.stage_inputs(self.root, self.project, self.workspace)
        candidate.write_text("Smith_v._Jones\n")
        return guard, ref, candidate, spec, prompt

    def test_staged_first_three_only_and_python_publication(self):
        guard, ref, candidate, spec, prompt = self.prepared()
        access = json.loads(spec.read_text())
        self.assertEqual(len(access["reads"]), 3)
        self.assertTrue(all(Path(path).parent == self.workspace for path in access["reads"]))
        self.assertNotIn("Synthetic page", prompt)
        self.assertNotIn("Synthetic page 4", "".join(Path(p).read_text() for p in access["reads"]))
        self.assertEqual((self.root / "case_name.txt").read_text(), "Prior_Name")
        self.assertFalse(stage.is_current(self.root, self.project))
        stage.publish(self.root, self.project, guard, ref, candidate)
        self.assertEqual((self.root / "case_name.txt").read_text(), "Smith_v._Jones")
        self.assertTrue(stage.is_current(self.root, self.project))
        (self.root / "text_pages/0004.txt").write_text("Changed out-of-scope page")
        self.assertTrue(stage.is_current(self.root, self.project))
        (self.root / "text_pages/0001.txt").write_text("Changed caption")
        self.assertFalse(stage.is_current(self.root, self.project))

    def test_stale_inputs_never_replace_name(self):
        changes = {
            "source": lambda: (self.root / "text_pages/0001.txt").write_text("Changed source"),
            "inventory": lambda: (self.root / "text_pages/0000.txt").write_text("New first page"),
            "model": lambda: (self.project / "settings.json").write_text('{"defaultModel":"changed"}'),
            "skill": lambda: (self.project / "skills" / stage.SKILL / "SKILL.md").write_text("Changed contract"),
            "output": lambda: (self.root / "case_name.txt").write_text("Concurrent_Name"),
        }
        for key, change in changes.items():
            with self.subTest(key=key):
                guard, ref, candidate, _, _ = self.prepared()
                change()
                before = (self.root / "case_name.txt").read_bytes()
                with self.assertRaises(ValueError):
                    stage.publish(self.root, self.project, guard, ref, candidate)
                self.assertEqual((self.root / "case_name.txt").read_bytes(), before)

    def test_profile_switch_rejects_publication(self):
        guard, ref, candidate, _, _ = self.prepared()
        store = api.ProfileStore("recordprep", config_root=self.base / "config", data_root=self.base / "data")
        profile = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
        store.accept_profile(profile, expected_previous_digest=None)
        apply_case_profile(self.root, profile.ref, expected_previous=None, store=store)
        with self.assertRaises(ValueError):
            stage.publish(self.root, self.project, guard, ref, candidate)
        self.assertEqual((self.root / "case_name.txt").read_text(), "Prior_Name")

    def test_stop_invalid_and_unknown_preserve_prior_output(self):
        guard, ref, candidate, _, _ = self.prepared()
        for value in ("", "unknown", "../evil", "Smith\nv Jones", "Case name is Smith", "A" * 121, "Smith/Other", "```Smith```", "1234", "Smith\x00Jones"):
            with self.subTest(value=repr(value)):
                candidate.write_text(value)
                with self.assertRaises(ValueError):
                    stage.publish(self.root, self.project, guard, ref, candidate)
                self.assertEqual((self.root / "case_name.txt").read_text(), "Prior_Name")
        candidate.write_text("Estate_of_Smith")
        def stopped():
            raise ValueError("Stopped")
        with self.assertRaisesRegex(ValueError, "Stopped"):
            stage.publish(self.root, self.project, guard, ref, candidate, check_stop=stopped)
        self.assertEqual((self.root / "case_name.txt").read_text(), "Prior_Name")

    def test_old_or_malformed_metadata_is_pending_without_rewriting(self):
        directory = self.root / "artifacts"
        directory.mkdir()
        path = self.root / stage.METADATA
        for value in ("[]", "{}", '{"schema_version":1}', "not json"):
            path.write_text(value)
            self.assertFalse(stage.is_current(self.root, self.project))
            self.assertEqual(path.read_text(), value)
            self.assertEqual((self.root / "case_name.txt").read_text(), "Prior_Name")

    def test_safe_caption_forms(self):
        for name in ("Smith_v._Jones", "People_v._Smith", "In_re_A.B.", "Estate_of_Smith", "In_the_Matter_of_Smith", "In_re_O’Neill", "In_re_Álvarez"):
            self.assertEqual(stage.validate_candidate(name.encode()), name)

    def test_linked_source_candidate_output_and_artifacts_fail_closed(self):
        guard, ref, candidate, _, _ = self.prepared()
        outside = self.base / "outside"
        outside.write_text("Private canary")
        candidate.unlink()
        candidate.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)):
            stage.publish(self.root, self.project, guard, ref, candidate)
        candidate.unlink()
        candidate.write_text("Smith_v_Jones")
        output = self.root / "case_name.txt"
        output.unlink()
        output.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)):
            stage.capture(self.root, self.project)
        output.unlink()
        output.write_text("Prior_Name")
        page = self.root / "text_pages/0001.txt"
        page.unlink()
        page.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)):
            stage.capture(self.root, self.project)
        page.unlink()
        page.write_text("Smith v Jones")
        (self.root / "artifacts").symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaises((OSError, ValueError)):
            stage.capture(self.root, self.project)
        self.assertEqual(outside.read_text(), "Private canary")

    def test_native_runner_reuses_shared_model_and_cleans_workspace(self):
        spec = importlib.util.spec_from_file_location("case_name_test_runner", PROJECT / ".pi/scripts/run_recordprep_skill.py")
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        spec.loader.exec_module(runner)
        workspaces = []
        def child(command, *, cwd, env, **kwargs):
            workspaces.append(Path(cwd))
            self.assertEqual(command[command.index("--tools") + 1], "read,write,edit")
            self.assertTrue(any(str(arg).endswith(stage.EXTENSION) for arg in command))
            self.assertNotIn("--model", command)
            self.assertNotIn("--provider", command)
            self.assertNotIn("--thinking", command)
            self.assertEqual((Path(cwd) / ".pi/settings.json").read_bytes(), (self.project / "settings.json").read_bytes())
            access = json.loads(Path(env["RECORDPREP_CASE_NAME_ACCESS_SPEC"]).read_text())
            Path(access["candidate"]).write_text("Smith_v._Jones")
            return SimpleNamespace(pid=os.getpid(), wait=lambda **kwargs: 0)
        with patch.object(runner, "_resolve_pi_command", return_value=["/usr/bin/true"]), patch.object(runner, "_check_pi_version"), patch.object(runner, "StageMonitor"), patch.object(runner.sys.stdin, "isatty", return_value=False), patch.object(runner.subprocess, "Popen", side_effect=child), patch("recordprep.run_metrics.instrument", side_effect=lambda command, env, *args: (command, env)):
            self.assertEqual(runner._run_stage(runner.STAGES["infer_case"], self.root, self.project), 0)
        self.assertTrue(stage.is_current(self.root, self.project))
        self.assertTrue(all(not workspace.exists() for workspace in workspaces))

    def test_real_runner_subprocess_success_failure_and_stale_source(self):
        fake = self.base / "synthetic-pi"
        fake.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
if "--version" in sys.argv:
    print("0.87.1")
    raise SystemExit(0)
spec = json.loads(Path(os.environ["RECORDPREP_CASE_NAME_ACCESS_SPEC"]).read_text())
assert len(spec["reads"]) == 3
mode = os.environ.get("CAPTION_TEST_MODE", "success")
if mode == "failure":
    raise SystemExit(7)
if mode != "missing":
    Path(spec["candidate"]).write_text("" if mode == "unknown" else "Smith_v_Jones")
if mode == "stale":
    (Path(os.environ["RECORDPREP_CASE_BUNDLE"]) / "text_pages/0000.txt").write_text("New first page")
if mode == "stop":
    import time
    Path(os.environ["CAPTION_TEST_READY"]).write_text(str(os.getpid()))
    time.sleep(60)
''')
        fake.chmod(0o700)
        env = os.environ | {"RECORDPREP_CASE_BUNDLE": str(self.root), "RECORDPREP_PI_PROJECT_DIR": str(self.project),
                            "RECORDPREP_PI_COMMAND_ARGC": "1", "RECORDPREP_PI_COMMAND_ARG_0": str(fake)}
        runner = PROJECT / ".pi/scripts/run_recordprep_skill.py"
        for mode in ("success", "failure", "missing", "unknown", "stale"):
            with self.subTest(mode=mode):
                before = (self.root / "case_name.txt").read_bytes()
                result = subprocess.run([sys.executable, str(runner), "infer_case"], env=env | {"CAPTION_TEST_MODE": mode},
                                        capture_output=True, text=True, timeout=20)
                if mode == "success":
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue(stage.is_current(self.root, self.project))
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual((self.root / "case_name.txt").read_bytes(), before)
                self.assertNotIn("Synthetic page", result.stdout)
                self.assertFalse(list((self.base / "cache/recordprep-pi-workspaces").iterdir()))
        before = (self.root / "case_name.txt").read_bytes()
        ready = self.base / "ready"
        process = subprocess.Popen([sys.executable, str(runner), "infer_case"],
                                   env=env | {"CAPTION_TEST_MODE": "stop", "CAPTION_TEST_READY": str(ready),
                                              "RECORDPREP_PI_STALL_POLL_INTERVAL": "0.05"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists())
            process.send_signal(signal.SIGTERM)
            out, err = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 130, out + err)
            self.assertEqual((self.root / "case_name.txt").read_bytes(), before)
            self.assertFalse(list((self.base / "cache/recordprep-pi-workspaces").iterdir()))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if ready.exists():
                try:
                    os.kill(int(ready.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_settings_save_preserves_retired_case_api_values(self):
        config = {"case_name_api_url": "https://synthetic.invalid", "case_name_api_key": "SYNTHETIC",
                  "case_name_model_id": "retired", "case_name_prompt": "Old instructions", "case_name_disable_reasoning": True}
        owner = SimpleNamespace(_prompt_editors={}, _local_ocr_widgets=None, _summarize_widgets=None,
                                _agent_widgets=None, _text_source_row=None, _on_saved=None, close=Mock())
        with patch.object(ui, "_read_config", return_value=dict(config)), patch.object(ui, "_write_config") as save:
            ui.SettingsWindow._save_settings(owner)
            save.assert_called_once_with(config)

    def test_ui_routes_only_to_native_skill(self):
        owner = SimpleNamespace(_run_pi_skill_step=Mock(return_value=True), step_infer_case_row=object())
        self.assertTrue(ui.RecordPrepWindow._run_step_infer_case(owner))
        owner._run_pi_skill_step.assert_called_once_with("infer_case", owner.step_infer_case_row)
        destinations = {key for _group, _title, items in ui.SETTINGS_NAV_GROUPS for key, _label in items}
        self.assertNotIn("case-name", destinations)
        self.assertFalse(hasattr(ui.RecordPrepWindow, "_request_plain_text"))

    def test_actual_guard_extension(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable")
        env = os.environ | {"RECORDPREP_GUARD_TEST_ROOT": str(self.base / "guard")}
        result = subprocess.run([node, "tests/case_name_tools_contract.mjs"], cwd=PROJECT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
