"""Schema-2 task/caption compiler and guarded production inference coverage."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from recordprep import practice_profiles as api
from recordprep.profile_contract import json_bytes, validate_contents, compile_stage_profile
from recordprep.profile_workflows import ProfileEditor
from recordprep.classification_profiles import KINDS, classifier_prompt, component
from recordprep.case_name_profiles import compile_case_name, inputs, is_current, publish_metadata
from recordprep.case_profiles import apply_case_profile
from recordprep.ui import main_window as ui


class TaskGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.base = api.validate_profile_directory(api.bundled_profile_directory("general")).draft

    def test_task_guidance_changes_only_its_runtime_prompt_and_component(self):
        groups = {"rt": "basic", "ct": "basic", "first_hearing": "advanced", "first_minute": "advanced", "first_form": "advanced",
                  "date_hearing": "dates", "date_minute": "dates"}
        for task in KINDS:
            with self.subTest(task=task):
                editor = ProfileEditor(self.base)
                marker = "Synthetic guidance only for " + task
                editor.resources["classification_tasks"][task] += "\n" + marker
                changed = editor.snapshot()
                for other in KINDS:
                    prompt = classifier_prompt(changed, other)[0]
                    self.assertEqual(marker in prompt, task == other)
                for stage in ("basic", "advanced", "dates", "names"):
                    self.assertEqual(component(changed, stage) != component(self.base, stage), stage == groups[task])
                for stage in ("participants", "hearing_extraction", "report_extraction", "minutes", "overview", "case_name"):
                    self.assertEqual(compile_stage_profile(changed, stage, core_contract=b"core").component_sha256,
                                     compile_stage_profile(self.base, stage, core_contract=b"core").component_sha256)

    def test_old_schema_bytes_compilation_and_caption_behavior_stay_unchanged(self):
        editor = ProfileEditor(self.base)
        editor.manifest["schema_version"] = 1
        for key in ("classification_tasks", "case_name"):
            editor.manifest["resources"].pop(key)
            editor.resources.pop(key)
        old = editor.snapshot()
        self.assertEqual(validate_contents(old.files, "recordprep").files, old.files)
        self.assertIsNone(compile_case_name(old))
        self.assertNotIn("TASK GUIDANCE", classifier_prompt(old, "rt")[0])
        self.assertEqual(component(old, "basic"), compile_stage_profile(old, "classification", core_contract=__import__("recordprep.classification_profiles", fromlist=["CORE"]).CORE.encode()).component_sha256)

    def test_case_name_guidance_freshness_and_production_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "case_bundle"
            root.mkdir()
            (root / "text_pages").mkdir()
            (root / "artifacts").mkdir()
            for page in range(1, 5):
                (root / "text_pages" / f"{page:04d}.txt").write_text("Smith v Jones\nSynthetic source page.")
            (root / "manifest.json").write_text('{"schema_version":1}')
            store = api.ProfileStore("recordprep", config_root=Path(temporary) / "config", data_root=Path(temporary) / "data")
            editor = ProfileEditor(self.base)
            editor.resources["case_name"] = "Synthetic caption instruction marker."
            profile = editor.snapshot()
            store.accept_profile(profile, expected_previous_digest=None)
            settings = {"api_url": "http://synthetic.invalid", "model_id": "synthetic", "api_key": "SYNTHETIC_KEY", "prompt": "Legacy prompt"}
            calls = []
            owner = SimpleNamespace(selected_pdfs=[], _resolve_case_base=lambda: root.parent, _resolve_case_root=lambda: root,
                                    _raise_if_stop_requested=lambda: None, selected_label=SimpleNamespace(set_text=lambda _text: None),
                                    _safe_update_manifest=lambda *_args: None, show_toast=lambda _text: None,
                                    step_infer_case_row=SimpleNamespace(set_sensitive=lambda _value: None),
                                    _finish_step=lambda *_args: None, _stop_status_if_idle=lambda: None, _stop_button_if_idle=lambda: None)
            def request(actual, text):
                calls.append((actual, text))
                return "Smith_v_Jones"
            owner._request_plain_text = request
            with patch.object(api, "profile_store", return_value=store), patch("recordprep.case_profiles.profile_store", return_value=store), patch.object(ui, "load_case_name_settings", return_value=settings), patch.object(ui, "save_case_context"), patch.object(ui.GLib, "idle_add", side_effect=lambda callback, *args: callback(*args)):
                apply_case_profile(root, profile.ref, expected_previous=None)
                self.assertTrue(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertIn("Synthetic caption instruction marker", calls[0][0]["prompt"])
                self.assertEqual(calls[0][1].count("Synthetic source page"), 3)
                self.assertTrue(is_current(root, profile, settings))
                before = (root / "case_name.txt").read_bytes()
                revised = ProfileEditor(profile)
                revised.resources["case_name"] += "\nChanged caption guidance."
                self.assertFalse(is_current(root, revised.snapshot(), settings))
                self.assertEqual((root / "case_name.txt").read_bytes(), before)
                # A redirected metadata directory is rejected before a request or publication.
                (root / "artifacts").rename(root / "original_artifacts")
                outside = Path(temporary) / "outside"
                outside.mkdir()
                (root / "artifacts").symlink_to(outside, target_is_directory=True)
                request_count = len(calls)
                self.assertFalse(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertEqual(len(calls), request_count)
                self.assertEqual((root / "case_name.txt").read_bytes(), before)
                self.assertEqual(list(outside.iterdir()), [])
                (root / "artifacts").unlink()
                (root / "original_artifacts").rename(root / "artifacts")
                (root / "artifacts/case_name_profile.json").unlink()
                (root / "artifacts").rmdir()
                self.assertTrue(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertTrue(is_current(root, profile, settings))
                # A changing case generation rejects synthetic response publication.
                owner._case_generation = 0
                def changing_request(actual, text):
                    owner._case_generation += 1
                    return "Other_v_Party"
                owner._request_plain_text = changing_request
                self.assertFalse(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertEqual((root / "case_name.txt").read_bytes(), before)
                # Re-evaluate the first-three-page inventory, not a captured list.
                def source_changed(actual, text):
                    (root / "text_pages/0000.txt").write_text("Synthetic newly inserted caption page.")
                    return "Other_v_Party"
                owner._request_plain_text = source_changed
                self.assertFalse(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertEqual((root / "case_name.txt").read_bytes(), before)
                def model_changed(actual, text):
                    settings["model_id"] = "synthetic-other-model"
                    return "Other_v_Party"
                owner._request_plain_text = model_changed
                self.assertFalse(ui.RecordPrepWindow._run_step_infer_case(owner))
                self.assertEqual((root / "case_name.txt").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
