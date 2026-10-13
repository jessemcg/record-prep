import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep.case_profiles import apply_case_profile
from recordprep.classification_profiles import ClassificationRun, STAGES, output_names, stage_issues, normalize_classifier
from recordprep.profile_store import ProfileStore
from recordprep.transcript_layout import apply_manual_override
from test_profile_generation import bundled, changed


class ClassificationProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("artifacts", "text_pages", "image_pages", "classification"):
            (self.root / name).mkdir()
        (self.root / "text_pages/0001.txt").write_text("Independent Report\nJanuary 2, 2026")
        (self.root / "image_pages/0001.png").write_bytes(b"synthetic image request payload")
        apply_manual_override(self.root, mode="ct_only")
        base = bundled("general")
        naming = base.resource("naming")
        naming["report_guidance"] += "\n- **Independent Report**\n"
        self.profile = changed(base, "naming", naming)
        self.store = ProfileStore("recordprep", config_root=self.root / "config", data_root=self.root / "data")
        self.store.accept_profile(self.profile, expected_previous_digest=None)
        apply_case_profile(self.root, self.profile.ref, expected_previous=None, store=self.store)
        self.settings = {"api_url": "https://synthetic.invalid/v1/chat/completions", "model_id": "synthetic",
                         "api_key": "NEVER-PERSIST", "disable_reasoning": True, "prompt": "legacy", "rt_prompt": "legacy", "ct_prompt": "legacy",
                         "hearing_prompt": "legacy", "minute_prompt": "legacy", "form_prompt": "legacy", "report_prompt": "legacy"}
        self.patch = patch("recordprep.case_profiles.profile_store", return_value=self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_component_checkpoints_preserve_published_outputs(self):
        for stage in STAGES:
            run = ClassificationRun.begin(self.root, stage, self.settings)
            (run.directory / output_names(stage)[1]).write_text('{"file_name":"0001.txt","page_type":"CT_report"}\n')
            run.publish(self.settings)
            self.assertEqual(stage_issues(self.root, stage, self.profile, self.settings), [])
        topics = self.profile.resource("reports")
        topics[0]["guidance"] += " Different summary topic guidance."
        unrelated = changed(self.profile, "reports", topics)
        self.assertEqual(stage_issues(self.root, "names", unrelated, self.settings), [])
        naming = changed(self.profile, "naming", self.profile.resource("naming") | {"report_guidance": "Different title guidance."})
        self.assertEqual(stage_issues(self.root, "basic", naming, self.settings), [])
        self.assertTrue(stage_issues(self.root, "names", naming, self.settings))
        run = ClassificationRun.begin(self.root, "basic", self.settings)
        canonical = self.root / "classification/CT_basic.jsonl"
        previous = canonical.read_bytes()
        (self.root / "image_pages/0001.png").write_bytes(b"changed source")
        with self.assertRaises(ValueError):
            run.publish(self.settings)
        self.assertEqual(canonical.read_bytes(), previous)
        for metadata in (self.root / "classification").glob("profile-*.json"):
            self.assertNotIn("NEVER-PERSIST", metadata.read_text())
            self.assertNotIn("synthetic.invalid", metadata.read_text())

    def _run_gui_pipeline(self, kind="report"):
        from recordprep.ui import main_window as ui
        worker = SimpleNamespace(
            _resolve_case_root=lambda: self.root, _raise_if_stop_requested=lambda: None,
            _validate_vision_settings=lambda settings: None, _classifier_worker_count=lambda settings: 1,
            _safe_update_manifest=Mock(), show_toast=Mock(), _finish_step=Mock(), _stop_status_if_idle=Mock(),
            _stop_button_if_idle=Mock(), _update_toc_button=Mock(), _extract_response_text=lambda payload: payload,
            _extract_json_payload=lambda text: text,
        )
        for name in ("step_two_row", "step_advanced_row", "step_correct_advanced_row", "step_dates_row", "step_names_row",
                     "step_six_row", "step_correct_toc_row", "step_seven_row", "step_correct_boundaries_row"):
            setattr(worker, name, Mock())
        worker._append_boundary_entry = lambda *args: ui.RecordPrepWindow._append_boundary_entry(worker, *args)
        worker._classify_image = lambda *args: ui.RecordPrepWindow._classify_image(worker, *args)
        worker._classify_image_with_page_type = lambda *args: ui.RecordPrepWindow._classify_image_with_page_type(worker, *args)
        worker._run_classifier_jobs = lambda jobs, workers: [function(*args) for function, args in jobs]
        prompts = []
        def response(request, **kwargs):
            prompt = json.loads(request.data)["messages"][0]["content"]
            prompts.append(prompt)
            if "CURRENT TASK: Classify" in prompt:
                return json.dumps({"page_type": "CT_report" if kind == "report" else "CT_minute_order"})
            if "CURRENT TASK: Is this" in prompt:
                return json.dumps({"first_page": "yes"})
            if "CURRENT TASK: Extract" in prompt:
                return json.dumps({"date": ""})
            return json.dumps({"name": "Independent Report", "date": "January 2, 2026"})
        with patch.object(ui.GLib, "idle_add"), patch.object(ui, "_post_json_with_retries", side_effect=response), \
                patch.object(ui, "load_classifier_settings", return_value=self.settings), \
                patch.object(ui, "load_advanced_classify_settings", return_value=self.settings), \
                patch.object(ui, "load_classify_dates_settings", return_value=self.settings), \
                patch.object(ui, "load_classify_names_settings", return_value=self.settings):
            for method in ("_run_step_two", "_run_step_advanced", "_run_step_correct_advanced", "_run_step_dates", "_run_step_names",
                           "_run_step_six", "_run_step_correct_toc", "_run_step_seven", "_run_step_correct_boundaries"):
                self.assertTrue(getattr(ui.RecordPrepWindow, method)(worker), method)
        self.assertEqual(len(prompts), 2 if kind == "report" else 6)
        self.assertTrue(all("legacy" not in prompt for prompt in prompts))
        entries = [json.loads(line) for line in (self.root / "classification/CT_basic_advanced_corrected_dates_names.jsonl").read_text().splitlines()]
        if kind == "report":
            self.assertEqual(entries[0]["name"], "Independent Report")
        self.assertEqual(stage_issues(self.root, "names", self.profile, self.settings), [])
        from recordprep.boundary_profiles import boundary_issues, toc_issues
        self.assertEqual(boundary_issues(self.root, self.profile, self.settings), [])
        self.assertEqual(toc_issues(self.root, self.profile, self.settings), [])
        if kind == "report":
            self.assertEqual(len(json.loads((self.root / "artifacts/report_boundaries.json").read_text())), 1)
        else:
            orders = json.loads((self.root / "artifacts/minutes_boundaries.json").read_text())
            self.assertEqual(len(orders), 2)
            self.assertTrue(all(not order["date"] for order in orders))
            self.assertEqual((self.root / "artifacts/toc.txt").read_text().count("Date unresolved"), 2)

    def test_actual_gui_worker_classification_pipeline_uses_frozen_contracts(self):
        self._run_gui_pipeline()

    def test_profile_orders_with_unknown_dates_are_not_erased_or_deduplicated(self):
        (self.root / "text_pages/0002.txt").write_text("Another distinct minute order.")
        (self.root / "image_pages/0002.png").write_bytes(b"second synthetic image payload")
        apply_manual_override(self.root, mode="ct_only")
        self._run_gui_pipeline("minutes")

    def test_structural_response_contract_cannot_be_changed_by_guidance(self):
        self.assertEqual(normalize_classifier({"page_type": "ct_report"}, "ct"), {"page_type": "CT_report"})
        with self.assertRaises(ValueError):
            normalize_classifier({"page_type": "new_executable_stage"}, "ct")
        self.assertEqual(normalize_classifier({"date": "February 30, 2026"}, "date_minute"), {"date": ""})


if __name__ == "__main__":
    unittest.main()
