import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_native_profiles import load
from test_participant_stage import _transcript_entries


class ProfilePublicationTests(unittest.TestCase):
    def test_ct_only_full_preparation_publishes_v3_without_map_model_or_cleanup(self):
        from test_classification_profiles import ClassificationProfileTests
        fixture = ClassificationProfileTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root, profile = fixture.root, fixture.profile
        (root / "manifest.json").write_text(json.dumps({"schema_version": 2, "files": {}}))
        fixture._run_gui_pipeline()
        source = Path(__file__).resolve().parents[1]
        project = root / "application"
        shutil.copytree(source / ".pi", project / ".pi")
        (project / "config.json").write_text(json.dumps({
            "classifier_api_url": fixture.settings["api_url"], "classifier_model_id": fixture.settings["model_id"],
            "classifier_disable_reasoning": fixture.settings["disable_reasoning"],
        }))
        entry = _transcript_entries(range(1, 2))[0]
        entry.update(record_type="CT", page_type="CT_report", citation_series_id="ct-1", citation_prefix="CT",
                     citation_label="CT 1", citation_key="CT:1")
        (root / "artifacts/transcript_page_numbers.json").write_text(json.dumps({
            "schema_version": 2, "entries": [entry], "citation_series": [{"series_id": "ct-1", "citation_prefix": "CT"}], "anomalies": []}))
        (root / "artifacts/transcript_page_number_series.md").write_text("# CT series\nCT 1\n")
        runner = load("profile_publication_runner", project / ".pi/scripts/run_recordprep_skill.py")
        from recordprep import minute_summaries as minutes
        from recordprep.pi_bundle import validate_prepare_bundle_outputs
        from recordprep.publication_profiles import publication_issues
        with patch.object(runner, "_resolve_pi_command", return_value=["synthetic-pi"]), \
                patch.object(runner, "_check_pi_version"), \
                patch("recordprep.summary_preflight.pi_runtime.available_pi_models", return_value=[]), \
                patch.object(runner, "_stage_capacity", return_value=None), patch.object(runner, "_report_capacity"), \
                patch.object(runner, "_run_extraction_child", return_value={"categories": []}), \
                patch.object(runner, "_run_synthesis_child", return_value=([], [])):
            for kind, singular in (("hearings", "hearing"), ("reports", "report")):
                stage = runner.SkillStage(f"create_{singular}_summaries", f"Create {kind} summaries", f"recordprep-extract-{singular}", "")
                self.assertEqual(runner._run_summary_stage(stage, root, project / ".pi"), 0)
        minutes.run_stage(root, project / ".pi", lambda *args: self.fail("No minute documents should call a model."))
        overview = "---\nartifact: recordprep-case-overview\nschema_version: 1\nstatus: nonauthoritative-orientation\n---\n# Case Overview\n"
        overview += "> Orientation aid only. Verify every factual claim against mapped source pages before relying on or citing it.\n"
        for section in ("Parties and Roles", "Procedural Posture", "Key Events", "Principal Issues", "Record Scope"):
            overview += f"## {section}\nThe synthetic record supplies a report; other matters remain unresolved.\n"
        def child(command, *, cwd, **kwargs):
            self.assertIn("Private output candidate", command[-1])
            self.assertIn("never evidence", command[-1])
            (Path(cwd) / "overview-candidate.md").write_text(overview)
            return SimpleNamespace(pid=os.getpid(), wait=lambda **kwargs: 0)
        with patch.object(runner, "_pi_command", return_value=["/usr/bin/true"]), \
                patch.object(runner, "_check_pi_version"), patch.object(runner, "StageMonitor"), \
                patch("recordprep.run_metrics.instrument", side_effect=lambda command, env, *args: (command, env)), \
                patch.object(runner.subprocess, "Popen", side_effect=child):
            self.assertEqual(runner._run_stage(runner.STAGES["create_case_overview"], root, project / ".pi"), 0)
        legacy = root / "summaries/synthetic_organized.txt"
        legacy.write_text("Preserve legacy output.")
        with patch.object(runner, "_pi_command", side_effect=AssertionError("Source-map publication must not launch a model.")):
            self.assertEqual(runner._run_stage(runner.STAGES["build_source_map"], root, project / ".pi"), 0)
        self.assertTrue(legacy.exists())
        self.assertEqual(validate_prepare_bundle_outputs(root, project_dir=project / ".pi"), [])
        self.assertEqual(publication_issues(root, profile, project / ".pi"), [])
        payload = json.loads((root / "artifacts/source_map.json").read_text())
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["counts"]["reports"], 1)
        self.assertNotIn("participant_index", payload["paths"])
        self.assertNotIn("participants", payload["preparation_provenance"]["components"])
        self.assertEqual(payload["participant_index"]["applicability"], "not_applicable_ct_only")
        self.assertEqual(payload["participant_index"]["hearings"], [])
        self.assertEqual(payload["preparation_provenance"], json.loads((root / "artifacts/practice_profile_provenance.json").read_text()))
        (root / "artifacts/toc.txt").write_text("Changed outside publication.")
        self.assertTrue(publication_issues(root, profile, project / ".pi"))


if __name__ == "__main__":
    unittest.main()
