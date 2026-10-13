"""Task guidance stays isolated; historical caption resources remain inert."""
import unittest
from unittest.mock import patch

from recordprep import practice_profiles as api
from recordprep.profile_contract import validate_contents, compile_stage_profile
from recordprep.profile_workflows import ProfileEditor
from recordprep.classification_profiles import KINDS, classifier_prompt, component
from recordprep.case_name_profiles import compile_case_name
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
                for name in ("basic", "advanced", "dates", "names"):
                    self.assertEqual(component(changed, name) != component(self.base, name), name == groups[task])
                for name in ("participants", "hearing_extraction", "report_extraction", "minutes", "overview", "case_name"):
                    self.assertEqual(compile_stage_profile(changed, name, core_contract=b"core").component_sha256,
                                     compile_stage_profile(self.base, name, core_contract=b"core").component_sha256)

    def test_legacy_caption_settings_are_inert_and_not_rewritten(self):
        config = {"case_name_prompt": "Synthetic old custom prompt", "case_name_model_id": "synthetic"}
        original = dict(config)
        with patch.object(ui, "_read_config", return_value=config), patch.object(ui, "_write_config") as save:
            self.assertEqual(ui.load_case_name_settings()["prompt"], ui.DEFAULT_CASE_NAME_PROMPT)
            self.assertEqual(config, original)
            save.assert_not_called()
        editor = ProfileEditor(self.base)
        editor.resources["case_name"] = "Synthetic retired caption instructions."
        self.assertEqual(compile_case_name(editor.snapshot()), compile_case_name(self.base))

    def test_old_schema_bytes_and_classification_stay_unchanged(self):
        from test_practice_profiles import historical_snapshot
        editor = ProfileEditor(historical_snapshot(self.base, version=2))
        editor.manifest["schema_version"] = 1
        for name in ("hearing_extraction", "report_extraction", "hearing_synthesis", "report_synthesis"):
            editor.manifest["resources"][name] = name + ".md"
            editor.resources[name] = "Synthetic historical instructions."
        for key in ("classification_tasks", "case_name"):
            editor.manifest["resources"].pop(key)
            editor.resources.pop(key)
        old = editor.snapshot()
        self.assertEqual(validate_contents(old.files, "recordprep").files, old.files)
        self.assertIsNone(compile_case_name(old))
        self.assertNotIn("TASK GUIDANCE", classifier_prompt(old, "rt")[0])
        self.assertEqual(component(old, "basic"), compile_stage_profile(old, "classification", core_contract=__import__("recordprep.classification_profiles", fromlist=["CORE"]).CORE.encode()).component_sha256)


if __name__ == "__main__":
    unittest.main()
