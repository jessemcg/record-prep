import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from recordprep.case_profiles import apply_case_profile
from recordprep.native_profiles import participant_freshness_issues, compile_native
from recordprep.profile_store import ProfileStore
from recordprep.transcript_layout import apply_manual_override
from test_participant_stage import _build_record_fixture, _review_hearing
from test_profile_generation import bundled, changed, seed_profile_preparation

PROJECT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class NativeProfileTests(unittest.TestCase):
    def test_actual_participant_runner_publishes_private_general_candidate(self):
        runner = load("native_profile_runner", PROJECT / ".pi/scripts/run_recordprep_skill.py")
        helper = load("native_profile_helper", PROJECT / ".pi/skills/recordprep-build-participant-index/scripts/participant_index.py")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root = _build_record_fixture(temporary, hearings=1)
            for path in (root / "text_pages").glob("*.txt"):
                path.write_text(path.read_text().replace("mother", "plaintiff").replace("minor's father", "defendant"))
            numbering = root / "artifacts/transcript_page_numbers.json"
            payload = json.loads(numbering.read_text())
            payload["entries"] = [entry for entry in payload["entries"] if entry["record_type"] == "RT"]
            numbering.write_text(json.dumps(payload))
            (root / "artifacts/transcript_page_number_series.md").write_text("# Synthetic RT series\nRT 1–8\n")
            apply_manual_override(root, mode="rt_only")
            profile = bundled("general")
            store = ProfileStore("recordprep", config_root=directory / "config", data_root=directory / "data")
            store.accept_profile(profile, expected_previous_digest=None)
            apply_case_profile(root, profile.ref, expected_previous=None, store=store)
            def child(command, *, cwd, env, **kwargs):
                self.assertIn("Private output candidate", command[-1])
                self.assertNotIn("Mother's Counsel", command[-1])
                self.assertIn("schema-3", (Path(cwd) / ".pi/skills/recordprep-build-participant-index/SKILL.md").read_text())
                self.assertEqual(command[command.index("--tools") + 1], "read,write,edit,recordprep_validate_candidate")
                self.assertTrue(any(str(argument).endswith("recordprep-profile-native-tools.ts") for argument in command))
                access = json.loads(Path(env["RECORDPREP_NATIVE_ACCESS_SPEC"]).read_text())
                self.assertEqual(access["root"], str(root))
                self.assertTrue((Path(cwd) / "participant-worklist.json").is_file())
                with patch.dict(os.environ, env, clear=True):
                    output = Path(env["RECORDPREP_PARTICIPANT_CANDIDATE"])
                    self.assertTrue(output.is_file())
                    self.assertFalse((root / "artifacts/participant_index.json").exists())
                    candidate = json.loads(output.read_text())
                    candidate["warnings"] = []
                    candidate["hearings"] = [_review_hearing(candidate["hearings"][0], 1)]
                    text = json.dumps(candidate)
                    for old, new in (("social_worker", "party"), ("Social worker", "Party"),
                                     ("mothers_counsel", "plaintiffs_counsel"), ("Mother's counsel", "Plaintiffs Counsel"),
                                     ('"mother"', '"plaintiff"'), ('"Mother"', '"Plaintiff"'),
                                     ('"father"', '"defendant"'), ('"Father"', '"Defendant"')):
                        text = text.replace(old, new)
                    output.write_text(text)
                    self.assertEqual(helper.validate(root), [])
                return SimpleNamespace(pid=os.getpid(), wait=lambda **kwargs: 0)
            with patch("recordprep.case_profiles.profile_store", return_value=store), \
                    patch.object(runner, "_pi_command", return_value=["/usr/bin/true"]), \
                    patch.object(runner, "_check_pi_version"), patch.object(runner, "StageMonitor"), \
                    patch("recordprep.run_metrics.instrument", side_effect=lambda command, env, *args: (command, env)), \
                    patch.object(runner.subprocess, "Popen", side_effect=child):
                seed_profile_preparation(root, profile, PROJECT / ".pi")
                self.assertEqual(runner._run_stage(runner.STAGES["build_participant_index"], root, PROJECT / ".pi"), 0)
                self.assertEqual(participant_freshness_issues(root, profile, PROJECT / ".pi"), [])
                topics = profile.resource("reports")
                topics[0]["guidance"] += " Unrelated report topic guidance."
                revised = changed(profile, "reports", topics)
                self.assertEqual(participant_freshness_issues(root, revised, PROJECT / ".pi"), [])
                revised = changed(profile, "participants", "Different role interpretation guidance.")
                self.assertTrue(participant_freshness_issues(root, revised, PROJECT / ".pi"))
                (root / "text_pages/0001.txt").write_text("Changed source evidence.")
                self.assertTrue(participant_freshness_issues(root, profile, PROJECT / ".pi"))

    def test_actual_native_guard_blocks_shell_canonical_writes_and_out_of_scope_reads(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable")
        sdk = Path(os.environ.get("PI_METRICS_TEST_SDK") or Path(node).resolve().parent.parent / "lib/node_modules/@earendil-works/pi-coding-agent")
        if not (sdk / "package.json").is_file():
            self.skipTest("Local optional Pi SDK unavailable; never provision during tests")
        with tempfile.TemporaryDirectory() as temporary:
            env = os.environ | {"PI_METRICS_TEST_SDK": str(sdk), "RECORDPREP_GUARD_TEST_ROOT": temporary}
            result = subprocess.run([node, str(PROJECT / "tests/native_profile_tools_contract.mjs")], cwd=PROJECT,
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Native profile boundary contract passed", result.stdout)

    def test_native_compiler_keeps_specialty_out_of_core(self):
        general, dependency = (bundled(name) for name in ("general", "california_dependency"))
        self.assertNotEqual(compile_native(general, "participants", PROJECT / ".pi")[1],
                            compile_native(dependency, "participants", PROJECT / ".pi")[1])
        from recordprep.pi_bundle import validate_case_overview_text
        text = "---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n"
        text += "> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.\n"
        for section in ("Parties and Roles", "Procedural Posture", "Key Events", "Principal Issues", "Record Scope"):
            text += f"## {section}\nUnresolved from the supplied record.\n"
        self.assertEqual(validate_case_overview_text(text, profile_mode=True), [])
        self.assertTrue(validate_case_overview_text(text))


if __name__ == "__main__":
    unittest.main()
