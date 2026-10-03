"""Synthetic minute-order generation, resumability, appearance, and isolation."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recordprep import minute_summaries as minutes, summary_agents as sa
from tests.test_pi_resources import _load_runner_module, PI_DIR


def candidate(**changes):
    return {
        "artifact": "recordprep-minute-candidate", "hearing": "Review Hearing",
        "reporting": "reported", "parents": [
            {"parent": "Mother", "status": "present", "first_page_evidence": "Mother present in person."},
            {"parent": "Father", "status": "not_present", "first_page_evidence": "Counsel for father present."},
        ], "orders": "The court continued the hearing.", **changes,
    }


def fixture(base: Path, count: int = 2):
    project = base / "project/.pi"
    shutil.copytree(PI_DIR, project)
    (project.parent / "config.json").write_text(json.dumps({
        "summary_synthesize_pi_provider": "synthetic", "summary_synthesize_pi_model": "synthesis-model",
        "summary_synthesize_pi_thinking": "low", "summarize_api_key": "unused-legacy-key",
        "summarize_model_id": "unavailable-legacy-model",
    }))
    root = base / "bundle"
    (root / "text_pages").mkdir(parents=True)
    (root / "artifacts").mkdir()
    (root / "case_name.txt").write_text("Synthetic")
    boundaries = []
    for n in range(1, count + 1):
        (root / "text_pages" / f"{n:04d}.txt").write_text("Mother present in person. Counsel for father present. Continued.")
        boundaries.append({"start_page": f"{n:04d}", "end_page": f"{n:04d}", "date": f"March {n}, 2025"})
    (root / "artifacts/minutes_boundaries.json").write_text(json.dumps(boundaries))
    (root / "artifacts/transcript_page_numbers.json").write_text(json.dumps({"entries": [{"file_page": 1, "citation_label": "CT 1"}]}))
    return root, project


class MinuteSummaryTests(unittest.TestCase):
    def test_resumes_completed_orders_and_preserves_final_until_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp))
            final = sa.summary_final_path(root, "minutes")
            final.parent.mkdir()
            final.write_text("OLD MINUTES")
            hearings = sa.summary_final_path(root, "hearings")
            reports = sa.summary_final_path(root, "reports")
            hearings.write_text("OLD HEARINGS")
            reports.write_text("OLD REPORTS")
            config_before = (project.parent / "config.json").read_bytes()
            generate = mock.Mock(side_effect=[candidate(), RuntimeError("synthetic provider failure")])
            with self.assertRaises(RuntimeError):
                minutes.run_stage(root, project, generate)
            self.assertEqual(len(minutes.load_rows(root)), 1)
            self.assertEqual(final.read_text(), "OLD MINUTES")
            generate = mock.Mock(return_value=candidate())
            minutes.run_stage(root, project, generate)
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(generate.call_args.args[0].item_id, "minute:0002")
            self.assertEqual(minutes.freshness_issues(root, project), [])
            self.assertIn("Mother appeared. Father did not appear.", final.read_text())
            self.assertEqual(hearings.read_text(), "OLD HEARINGS")
            self.assertEqual(reports.read_text(), "OLD REPORTS")
            self.assertEqual((project.parent / "config.json").read_bytes(), config_before)
            # Complete reruns use zero model calls and do not invalidate editions.
            generate.reset_mock()
            with mock.patch("recordprep.summary_editions.remove_summary_edition") as remove:
                minutes.run_stage(root, project, generate)
                remove.assert_not_called()
            generate.assert_not_called()

    def test_first_page_evidence_and_unknowns(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 1)
            _, config = minutes.stage_config(project)
            item = minutes.build_items(root, config)[0]
            for evidence in ("Father present on later page.", ""):
                row = minutes.normalize_candidate(candidate(parents=[{
                    "parent": "Father", "status": "present", "first_page_evidence": evidence,
                }]), item)
                self.assertIn("Father appearance unclear.", minutes.render_paragraph(row))
                self.assertIn("first_page_appearance_unverified", row["quality_flags"])
            row = minutes.normalize_candidate(candidate(parents=[], reporting="invalid"), item)
            self.assertIn("Parent appearances unclear.", minutes.render_paragraph(row))
            self.assertIn("Reporting status unclear.", minutes.render_paragraph(row))
            self.assertIn("If only a parent's attorney is listed", config["guidance"])
            self.assertIn("first page of the minute order", config["guidance"])

    def test_complete_source_not_windowed_and_later_page_cannot_prove_presence(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp))
            (root / "artifacts/minutes_boundaries.json").write_text(json.dumps([{"start_page": "0001", "end_page": "0002"}]))
            (root / "text_pages/0002.txt").write_text("Father present on later page. " + "x" * 20000)
            item = minutes.build_items(root, minutes.stage_config(project)[1])[0]
            self.assertGreater(len(item.source), 20000)
            self.assertEqual(item.source.count("FIRST PAGE:"), 1)
            row = minutes.normalize_candidate(candidate(parents=[{"parent": "Father", "status": "present", "first_page_evidence": "Father present on later page."}]), item)
            self.assertEqual(row["parents"][0]["status"], "unclear")

    def test_fingerprints_and_ui_cache_follow_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp))
            generate = mock.Mock(return_value=candidate())
            minutes.run_stage(root, project, generate)
            self.assertTrue(minutes.stage_complete(root, project))
            with mock.patch.object(minutes, "freshness_issues", wraps=minutes.freshness_issues) as check:
                self.assertTrue(minutes.stage_complete(root, project))
                check.assert_not_called()
            (root / "text_pages/0002.txt").write_text("Mother present in person. Different order.")
            self.assertFalse(minutes.stage_complete(root, project))
            generate.reset_mock()
            minutes.run_stage(root, project, generate)
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(generate.call_args.args[0].ordinal, 2)
            config_file = project.parent / "config.json"
            config = json.loads(config_file.read_text())
            config["summary_synthesize_pi_model"] = "different-model"
            config_file.write_text(json.dumps(config))
            self.assertFalse(minutes.stage_complete(root, project))
            generate.reset_mock()
            minutes.run_stage(root, project, generate)
            self.assertEqual(generate.call_count, 2)
            # Legacy API configuration is not a generation dependency.
            config["summarize_model_id"] = "another-unavailable-model"
            config_file.write_text(json.dumps(config))
            self.assertTrue(minutes.stage_complete(root, project))

    def test_empty_boundaries_need_no_model_and_legacy_final_is_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 0)
            final = sa.summary_final_path(root, "minutes")
            final.parent.mkdir()
            final.write_text("Legacy")
            self.assertTrue(minutes.freshness_issues(root, project))
            generate = mock.Mock()
            minutes.run_stage(root, project, generate)
            generate.assert_not_called()
            self.assertEqual(minutes.freshness_issues(root, project), [])
            self.assertEqual(final.read_text(), "Minutes Summary\nSynthetic\n")

    def test_invalid_boundaries_and_missing_source_fail_before_paid_work(self):
        for boundaries in (None, [{"start_page": "0002", "end_page": "0001"}], [{"start_page": "0003", "end_page": "0003"}], [{"start_page": "0001", "end_page": "0002"}, {"start_page": "0002", "end_page": "0002"}]):
            with self.subTest(boundaries=boundaries), tempfile.TemporaryDirectory() as temp:
                root, project = fixture(Path(temp))
                (root / "artifacts/minutes_boundaries.json").write_text(json.dumps(boundaries))
                generate = mock.Mock()
                with self.assertRaises(ValueError):
                    minutes.run_stage(root, project, generate)
                generate.assert_not_called()

    def test_corrupt_checkpoint_and_invalid_candidate_preserve_final(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 1)
            minutes.run_stage(root, project, mock.Mock(return_value=candidate()))
            final = sa.summary_final_path(root, "minutes")
            before = final.read_bytes()
            (root / "text_pages/0001.txt").write_text("changed")
            with self.assertRaises(ValueError):
                minutes.run_stage(root, project, mock.Mock(return_value={}))
            self.assertEqual(final.read_bytes(), before)
            minutes.checkpoint_path(root).write_text("corrupt")
            generate = mock.Mock()
            with self.assertRaises(ValueError):
                minutes.run_stage(root, project, generate)
            generate.assert_not_called()
            self.assertEqual(final.read_bytes(), before)

    def test_shared_model_inheritance_custom_guidance_and_contract_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 1)
            settings, config = minutes.stage_config(project)
            self.assertEqual(config["model"], "synthesis-model")
            self.assertNotIn("unused-legacy-key", json.dumps(config))
            raw = {"summarize_minutes_prompt": "  Custom guidance\n", "summary_extract_pi_model": "not-this"}
            (project.parent / "config.json").write_text(json.dumps(raw))
            (project / "settings.json").write_text(json.dumps({"defaultProvider": "synthetic", "defaultModel": "project-model", "defaultThinkingLevel": "high"}))
            settings, config = minutes.stage_config(project)
            self.assertEqual(config["model"], "project-model")
            self.assertEqual(config["thinking"], "high")
            self.assertEqual(config["additional_guidance"], "  Custom guidance\n")
            before = minutes.build_items(root, config)[0].fingerprint
            with (project / "skills" / minutes.SKILL_NAME / "SKILL.md").open("a") as f:
                f.write("\nChanged contract.\n")
            self.assertNotEqual(before, minutes.build_items(root, minutes.stage_config(project)[1])[0].fingerprint)

    def test_global_defaults_participate_when_project_selection_is_unset(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 1)
            (project.parent / "config.json").write_text("{}")
            (project / "settings.json").write_text("{}")
            agent = Path(temp) / "synthetic-agent"
            agent.mkdir()
            (agent / "settings.json").write_text('{"defaultModel":"first"}')
            with mock.patch.dict("os.environ", {"PI_CODING_AGENT_DIR": str(agent)}):
                minutes.run_stage(root, project, mock.Mock(return_value=candidate()))
                self.assertTrue(minutes.stage_complete(root, project))
                (agent / "settings.json").write_text('{"defaultModel":"second"}')
                self.assertFalse(minutes.stage_complete(root, project))

    def test_stop_between_orders_and_input_change_preserve_final(self):
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp))
            final = sa.summary_final_path(root, "minutes")
            final.parent.mkdir()
            final.write_text("OLD")
            class Stopped(Exception):
                pass
            checks = mock.Mock(side_effect=[None, None, Stopped()])
            with self.assertRaises(Stopped):
                minutes.run_stage(root, project, mock.Mock(return_value=candidate()), check_stop=checks)
            self.assertEqual(len(minutes.load_rows(root)), 1)
            self.assertEqual(final.read_text(), "OLD")
            def changed(*args):
                (root / "text_pages/0002.txt").write_text("changed mid-run")
                return candidate()
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                minutes.run_stage(root, project, changed)
            self.assertEqual(final.read_text(), "OLD")
            # Lock was released on both paths.
            with sa.SummaryKindLock(root, "minutes"):
                pass

    def test_runner_staging_allowlist_and_model_flags(self):
        runner = _load_runner_module()
        with tempfile.TemporaryDirectory() as temp:
            root, project = fixture(Path(temp), 1)
            observed = {}
            def fake_run(child):
                observed["command"] = child.command
                spec = json.loads(Path(child.env_overrides["RECORDPREP_MINUTE_WORK_SPEC"]).read_text())
                observed["workspace"] = child.workspace
                observed["extensions"] = [p.name for p in (child.workspace / ".pi/extensions").iterdir()]
                self.assertIn("FIRST PAGE", spec["source"])
                Path(spec["candidate_path"]).write_text(json.dumps(candidate()))
                return 0
            with mock.patch.object(runner, "_resolve_pi_command", return_value=["synthetic-pi"]), mock.patch.object(runner, "_check_pi_version"), mock.patch("recordprep.summary_preflight.pi_runtime.available_pi_models", return_value=[]), mock.patch.object(runner._SummaryChildRunner, "run", fake_run), mock.patch.dict("os.environ", {"XDG_CACHE_HOME": str(Path(temp) / "cache")}):
                self.assertEqual(runner._run_minute_stage(root, project), 0)
            command = observed["command"]
            self.assertEqual(command[command.index("--tools") + 1], minutes.TOOLS)
            self.assertEqual(command[command.index("--model") + 1], "synthesis-model")
            self.assertEqual(command[command.index("--thinking") + 1], "low")
            self.assertIn("--no-session", command)
            self.assertIn("--no-context-files", command)
            self.assertEqual(observed["extensions"], [minutes.EXTENSION_NAME])
            self.assertFalse(observed["workspace"].exists())
            self.assertEqual(minutes.freshness_issues(root, project), [])


if __name__ == "__main__":
    unittest.main()
