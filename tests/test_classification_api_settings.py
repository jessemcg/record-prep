"""API-only classification, synthetic settings; retired data is never authority."""
import copy
import unittest
from unittest.mock import patch

from recordprep.ui import main_window as ui
from recordprep.config import save_classifier_settings


class ClassificationApiSettingsTests(unittest.TestCase):
    def test_loaders_and_saves_ignore_and_preserve_unknown_legacy_values(self):
        for legacy in (None, False, True, "true"):
            with self.subTest(legacy=legacy):
                config = {"unknown": ["preserve"], "classifier_api_url": "https://synthetic.invalid",
                          "classifier_model_id": "synthetic", "classifier_api_key": "synthetic-key"}
                if legacy is not None:
                    config.update(classifier_local_vision_enabled=legacy,
                                  classifier_local_vision_start_command="NEVER EXECUTE {legacy}")
                before = copy.deepcopy(config)
                with patch.object(ui, "_read_config", side_effect=lambda: copy.deepcopy(config)), \
                     patch.object(ui, "_write_config") as write:
                    for loader in (ui.load_classifier_settings, ui.load_advanced_classify_settings,
                                   ui.load_classify_dates_settings, ui.load_classify_names_settings):
                        settings = loader()
                        self.assertNotIn("local_vision_enabled", settings)
                        self.assertNotIn("local_vision_start_command", settings)
                        self.assertEqual(settings["api_key"], "synthetic-key")
                    write.assert_not_called()
                    save_classifier_settings("https://new.invalid", "new", "new-key", "inert", "inert", True, "3")
                    saved = write.call_args.args[0]
                    self.assertEqual(saved["classifier_workers"], 3)
                    self.assertEqual(saved["unknown"], before["unknown"])
                    self.assertNotIn("classifier_rt_prompt", saved)
                    for key in ("classifier_local_vision_enabled", "classifier_local_vision_start_command"):
                        if key in before:
                            self.assertEqual(saved[key], before[key])
                            self.assertIs(type(saved[key]), type(before[key]))
                        else:
                            self.assertNotIn(key, saved)

    def test_api_url_model_and_key_required_regardless_of_legacy_flags(self):
        for legacy in (None, False, True, "true"):
            settings = dict(api_url="https://synthetic.invalid", model_id="synthetic", api_key="synthetic-key")
            if legacy is not None:
                settings.update(local_vision_enabled=legacy, local_vision_start_command="NEVER EXECUTE",
                                classifier_local_vision_enabled=legacy)
            ui.RecordPrepWindow._validate_vision_settings(None, settings)
            for key in ("api_url", "model_id", "api_key"):
                for missing in (None, "", "   "):
                    with self.subTest(legacy=legacy, key=key, missing=missing):
                        with self.assertRaises(ValueError) as caught:
                            ui.RecordPrepWindow._validate_vision_settings(None, dict(settings, **{key: missing}))
                        message = str(caught.exception)
                        self.assertIn("vision API", message)
                        self.assertIn("Model settings", message)
                        self.assertNotIn("local", message.lower())
                        self.assertNotIn("server", message.lower())
