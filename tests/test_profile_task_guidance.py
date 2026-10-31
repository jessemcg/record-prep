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
        groups = {"rt": "basic", "ct": "basic", "first_hearing": "advanced", "first_minute": "advanced", "first_form": "advanced", "first_report": "advanced",
                  "date_hearing": "dates", "date_minute": "dates"}
        for task in KINDS:
            with self.subTest(task=task):
                from recordprep.profile_editor_ui import editable_profile
                editor = editable_profile(self.base)
                marker = "Synthetic guidance only for " + task
                editor.resources["classification_tasks"][task] += "\n" + marker
                changed = editor.snapshot()
                for other in KINDS:
                    prompt = classifier_prompt(changed, other)[0]
                    self.assertEqual(marker in prompt, task == other and not task.startswith('date_'))
                for name in ("basic", "advanced", "dates", "names"):
                    self.assertEqual(component(changed, name) != component(self.base, name), name == groups[task] and not task.startswith('date_'))
                for name in ("participants", "hearing_extraction", "report_extraction", "minutes", "overview", "case_name"):
                    self.assertEqual(compile_stage_profile(changed, name, core_contract=b"core").component_sha256,
                                     compile_stage_profile(self.base, name, core_contract=b"core").component_sha256)

    def test_general_is_complete_neutral_and_uses_supported_labels(self):
        from recordprep.profile_contract import CLASSIFICATION_PAGE_TYPES, classification_guidance_warning
        from recordprep.document_naming import compile_naming_profile
        tasks = self.base.resource("classification_tasks")
        for kind, labels in CLASSIFICATION_PAGE_TYPES.items():
            for label in labels:
                self.assertIn(label + ":", tasks[kind])
        for kind, guidance in tasks.items():
            self.assertIn("To tailor this task", guidance)
            self.assertEqual(classification_guidance_warning(guidance, kind), "")
            for specialty in ("dependency", "juvenile", "JV-", "child-welfare"):
                self.assertNotIn(specialty.casefold(), guidance.casefold())
        for kind in ("report", "form"):
            compiled = compile_naming_profile(self.base, kind)
            # Instructions describe how to add names, without preapproving examples.
            self.assertEqual(compiled.normalize({"name": "Invented title", "date": ""}).name, "")

    def test_general_guidance_has_readable_sections_without_example_names(self):
        from recordprep.document_naming import compile_naming_profile
        self.assertNotIn("classification", self.base.manifest["resources"])
        for text in self.base.resource("classification_tasks").values():
            self.assertIn("\n\nHow to decide", text)
            self.assertIn("\n\nTo tailor this task:\n- ", text)
        naming = self.base.resource("naming")
        for kind in ("report", "form"):
            text = naming[kind + "_guidance"]
            self.assertTrue(text.startswith("Approved " + kind + " names"))
            self.assertIn("\n\nHow to decide", text)
            self.assertIn("\n\nTask and response:\n- ", text)
            # Formatting bullets must not accidentally become approved names.
            self.assertNotIn("\n- **", text)
            self.assertEqual(compile_naming_profile(self.base, kind).normalize(
                {"name": "Name", "date": ""}).name, "")
        self.assertNotIn("provisional labels", naming["report_guidance"])

    def test_guidance_warning_does_not_reject_or_rewrite_profile(self):
        from recordprep.profile_contract import classification_guidance_warning
        editor = ProfileEditor(self.base)
        editor.resources["classification_tasks"]["ct"] += " Return CT_custom_report."
        draft = editor.snapshot()
        self.assertIn("CT_custom_report", classification_guidance_warning(draft.resource("classification_tasks")["ct"], "ct"))
        self.assertEqual(validate_contents(draft.files, "recordprep").files, draft.files)
        self.assertNotIn("CT_custom_report", self.base.resource("classification_tasks")["ct"])

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
        self.assertEqual(component(old, "basic"), component(validate_contents(old.files, 'recordprep'), 'basic'))


if __name__ == "__main__":
    unittest.main()
