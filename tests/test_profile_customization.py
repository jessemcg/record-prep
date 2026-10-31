import copy
import tempfile
import unittest
from pathlib import Path

from recordprep import practice_profiles as api
from recordprep.profile_customization import legacy_customization_editor, initial_candidate, TASK_KEYS
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
                    self.assertEqual(editor.snapshot().files, base.files)

    def test_extra_summary_instructions_are_not_imported(self):
        base = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        config = {f"summarize_{kind}{suffix}_prompt": "REMOVED_GUIDANCE_CANARY"
                  for kind in ("hearings", "reports") for suffix in ("", "_synthesis")}
        before = dict(config)
        self.assertEqual(legacy_customization_editor(config).snapshot().files, base.files)
        self.assertEqual(config, before)

    def test_shipped_category_defaults_do_not_become_personal_overrides(self):
        from recordprep.summary_categories import load_category_descriptions
        base = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        categories = {kind: load_category_descriptions(kind) for kind in ("hearings", "reports")}
        self.assertEqual(legacy_customization_editor({}, categories=categories).snapshot().ref, base.ref)
        categories["reports"]["agency_recommendations"] = "Synthetic personal agency guidance."
        edited = legacy_customization_editor({}, categories=categories).snapshot()
        self.assertEqual(next(row["guidance"] for row in edited.resource("reports")
                              if row["id"] == "agency_recommendations"), "Synthetic personal agency guidance.")

    def test_allowlist_keeps_raw_text_by_task_and_case_name(self):
        keys = [key for key, _ in TASK_KEYS.values()] + ["case_name_prompt", "summarize_minutes_prompt", "classify_names_report_prompt", "classify_names_form_prompt"]
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
            self.assertEqual(config["case_name_prompt"], loaded.resource("case_name"))
            self.assertTrue(loaded.resource("naming")["report_guidance"].endswith(config["classify_names_report_prompt"]))
            self.assertIn("- **Detention Report**", loaded.resource("naming")["report_guidance"])
            self.assertIn("naming", editor.review_notices)
            self.assertEqual(loaded.resource("hearings")[0]["guidance"], categories["hearings"]["parent_appearances"])
            self.assertEqual(config, before)

    def test_missing_empty_historical_defaults_and_shared_precedence(self):
        base = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        config = {key: "" for key, _ in TASK_KEYS.values()}
        config.update({f"summarize_{kind}{suffix}_prompt": "" for kind in ("hearings", "reports")
                       for suffix in ("", "_synthesis")})
        config["case_name_prompt"] = ""
        self.assertEqual(legacy_customization_editor(config).snapshot().ref, base.ref)
        for task, (key, constant) in TASK_KEYS.items():
            config[key] = getattr(defaults, constant)
        self.assertEqual(legacy_customization_editor(config).snapshot().ref, base.ref)
        shared = "  Synthetic shared classifier guidance.\n"
        editor = legacy_customization_editor({"classifier_prompt": shared, "classifier_ct_prompt": ""})
        self.assertEqual(editor.resources["classification_tasks"]["rt"], shared)
        from recordprep.structured_guidance import _BASE
        import json
        self.assertEqual(editor.resources["classification_tasks"]["ct"], json.loads((_BASE/'classification-tasks.json').read_bytes())["ct"])

    def test_existing_personal_profile_and_completed_initialization_never_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = api.ProfileStore("recordprep", config_root=Path(temporary) / "config", data_root=Path(temporary) / "data")
            def resolve(base):
                return initial_candidate(base, config={"case_name_prompt": "Synthetic previous caption."}, categories={})
            first = api.profile_catalog(store=store, customization=resolve)[0]
            self.assertIn("previous", first.notice)
            ref = store.managed_save(first.snapshot, expected_head=None, expected_default=None, personal=True)
            def must_not_run(_base):
                raise AssertionError("Repeated initialization")
            # The existing Dependency customization must not be overlaid.
            result = api.profile_catalog(store=store, customization=lambda base: must_not_run(base) if base.ref.specialty_id == ref.specialty_id else None)
            self.assertEqual(result[0].snapshot.ref, ref)


if __name__ == "__main__":
    unittest.main()
