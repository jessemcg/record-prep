import copy
import tempfile
import unittest
from pathlib import Path

from recordprep import practice_profiles as api
from recordprep.profile_customization import legacy_customization_editor, initial_candidate, TASK_KEYS, SUMMARY_KEYS
from recordprep.profile_workflows import export_profile, checked_folder
from recordprep.ui import main_window as defaults


class PrivateCustomizationTests(unittest.TestCase):
    def test_historical_builtins_are_not_copied_as_personal_overrides(self):
        from recordprep.summary_agents import HISTORICAL_BUILTIN_GUIDANCE
        base = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        for (kind, phase), values in HISTORICAL_BUILTIN_GUIDANCE.items():
            key = f"summarize_{kind}{'_synthesis' if phase == 'synthesize' else ''}_prompt"
            for value in values:
                with self.subTest(kind=kind, phase=phase):
                    editor = legacy_customization_editor({key: value})
                    self.assertEqual(editor.resources[SUMMARY_KEYS[key]], base.resource(SUMMARY_KEYS[key]))

    def test_allowlist_keeps_raw_text_by_task_and_case_name(self):
        keys = [key for key, _ in TASK_KEYS.values()] + list(SUMMARY_KEYS) + ["case_name_prompt", "summarize_minutes_prompt", "classify_names_report_prompt", "classify_names_form_prompt"]
        config = {key: f"\n  Synthetic personal prose for {key}.\t\n\n" for key in keys}
        config.update({"api_key": "SECRET_CANARY", "model_id": "MODEL_CANARY", "api_url": "ENDPOINT_CANARY",
                       "case_root": "CASE_PATH_CANARY", "unrecognized_prompt": "UNKNOWN_CANARY"})
        before = copy.deepcopy(config)
        categories = {"hearings": {"parent_appearances": "  Synthetic category prose.\n\n"}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            editor = legacy_customization_editor(config, categories=categories)
            snapshot = editor.snapshot()
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(config, before)
            export_profile(snapshot, root / "personal")
            loaded = checked_folder(root / "personal", "recordprep")
            self.assertNotIn(b"CANARY", b"".join(data for _, data in loaded.files))
            for task, (key, _) in TASK_KEYS.items():
                self.assertEqual(config[key], loaded.resource("classification_tasks")[task])
                for other_task, text in loaded.resource("classification_tasks").items():
                    if task != other_task:
                        self.assertNotIn(config[key], text)
            for key, resource in SUMMARY_KEYS.items():
                self.assertEqual(config[key], loaded.resource(resource))
            self.assertEqual(config["case_name_prompt"], loaded.resource("case_name"))
            self.assertEqual(config["classify_names_report_prompt"], loaded.resource("naming")["report_guidance"])
            self.assertIn("naming", editor.review_notices)
            self.assertEqual(loaded.resource("hearings")[0]["guidance"], categories["hearings"]["parent_appearances"])
            self.assertEqual(config, before)

    def test_missing_empty_historical_defaults_and_shared_precedence(self):
        base = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        config = {key: "" for key, _ in TASK_KEYS.values()}
        config.update({key: "" for key in SUMMARY_KEYS})
        config["case_name_prompt"] = ""
        self.assertEqual(legacy_customization_editor(config).snapshot().ref, base.ref)
        for task, (key, constant) in TASK_KEYS.items():
            config[key] = getattr(defaults, constant)
        self.assertEqual(legacy_customization_editor(config).snapshot().ref, base.ref)
        shared = "  Synthetic shared classifier guidance.\n"
        editor = legacy_customization_editor({"classifier_prompt": shared, "classifier_ct_prompt": ""})
        self.assertEqual(editor.resources["classification_tasks"]["rt"], shared)
        self.assertEqual(editor.resources["classification_tasks"]["ct"], base.resource("classification_tasks")["ct"])

    def test_existing_personal_profile_and_completed_initialization_never_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = api.ProfileStore("recordprep", config_root=Path(temporary) / "config", data_root=Path(temporary) / "data")
            def resolve(base):
                return initial_candidate(base, config={"case_name_prompt": "Synthetic previous caption."}, categories={})
            first = api.profile_catalog(store=store, customization=resolve)[1]
            self.assertIn("previous", first.notice)
            ref = store.managed_save(first.snapshot, expected_head=None, expected_default=None, personal=True)
            def must_not_run(_base):
                raise AssertionError("Repeated initialization")
            # General remains eligible; only assert that Dependency is not overlaid.
            result = api.profile_catalog(store=store, customization=lambda base: must_not_run(base) if base.ref.specialty_id == ref.specialty_id else None)
            self.assertEqual(result[1].snapshot.ref, ref)


if __name__ == "__main__":
    unittest.main()
