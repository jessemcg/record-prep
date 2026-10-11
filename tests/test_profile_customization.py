import copy
import tempfile
import unittest
from pathlib import Path

from recordprep.profile_customization import legacy_customization_editor, CLASSIFICATION_KEYS, SUMMARY_KEYS
from recordprep.profile_workflows import export_profile, checked_folder


class PrivateCustomizationTests(unittest.TestCase):
    def test_historical_builtins_are_not_copied_as_personal_overrides(self):
        from recordprep.summary_agents import HISTORICAL_BUILTIN_GUIDANCE
        for (kind, phase), values in HISTORICAL_BUILTIN_GUIDANCE.items():
            key = f"summarize_{kind}{'_synthesis' if phase == 'synthesize' else ''}_prompt"
            for value in values:
                with self.subTest(kind=kind, phase=phase):
                    editor = legacy_customization_editor({key:value})
                    self.assertNotIn("## Copied legacy prompt: " + key, editor.resources[SUMMARY_KEYS[key]])

    def test_allowlisted_prompts_roundtrip_without_private_runtime_fields_or_mutation(self):
        keys = [*CLASSIFICATION_KEYS, *SUMMARY_KEYS, "classify_names_report_prompt", "classify_names_form_prompt"]
        config = {key: f"\n  Synthetic private prose for {key}.\t\n\n" for key in keys}
        config.update({"api_key":"SECRET_CANARY", "model_id":"MODEL_CANARY", "api_url":"ENDPOINT_CANARY",
                       "case_root":"CASE_PATH_CANARY", "unrecognized_prompt":"UNKNOWN_CANARY",
                       "case_name_prompt":"CASE_NAME_STAYS_OUTSIDE_CANARY"})
        before = copy.deepcopy(config)
        categories = {"hearings": {"parent_appearances":"  Synthetic category prose.\n\n"}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            editor = legacy_customization_editor(config, categories=categories)
            snapshot = editor.snapshot()
            self.assertEqual(list(root.iterdir()), [])  # In-memory preview/cancel writes nothing.
            self.assertEqual(config, before)
            export_profile(snapshot, root / "private-copy")
            reloaded = checked_folder(root / "private-copy", "recordprep")
            self.assertEqual(reloaded.ref, snapshot.ref)
            self.assertNotIn(b"CANARY", b"".join(data for _, data in reloaded.files))
            for key in CLASSIFICATION_KEYS:
                self.assertIn(config[key], reloaded.resource("classification"))
            for key, resource in SUMMARY_KEYS.items():
                self.assertIn(config[key], reloaded.resource(resource))
            self.assertIn(config["classify_names_report_prompt"], reloaded.resource("naming")["report_guidance"])
            self.assertIn(config["classify_names_form_prompt"], reloaded.resource("naming")["form_guidance"])
            self.assertEqual(reloaded.resource("hearings")[0]["guidance"], categories["hearings"]["parent_appearances"])
            self.assertEqual(config, before)


if __name__ == "__main__":
    unittest.main()
