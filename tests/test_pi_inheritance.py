"""No shipped preferences; missing checkout/external settings are equivalent."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from recordprep import paths, pi_runtime as pi


class InheritanceTests(unittest.TestCase):
    def test_missing_and_explicit_model_only_in_both_storage_modes(self):
        for external in (False, True):
            with self.subTest(external=external), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                project = root / '.pi'
                project.mkdir()
                with patch.dict(os.environ, RECORDPREP_CONFIG_DIR=str(root / 'external') if external else ''):
                    path = paths.pi_settings_path(project)
                    self.assertEqual(paths.effective_pi_settings(project), {})
                    self.assertIsNone(pi.current_project_pi_model(path))
                    self.assertIsNone(pi.current_project_pi_thinking_level(path))
                    paths.stage_pi_settings(project, root / 'staged.json')
                    self.assertEqual(json.loads((root / 'staged.json').read_text()), {'enableSkillCommands': True})
                    self.assertFalse(path.exists())
                    pi.save_project_pi_model(pi.PiModel('synthetic', 'model', 'Model'), path)
                    self.assertEqual(json.loads(path.read_text()), {'defaultProvider': 'synthetic', 'defaultModel': 'model'})

    def test_skill_requirement_only_applies_in_workspace(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, RECORDPREP_CONFIG_DIR=''):
            root = Path(temporary)
            path = root / 'settings.json'
            path.write_text('{"enableSkillCommands":false,"unrelated":[1]}')
            original = path.read_bytes()
            paths.stage_pi_settings(root, root / 'staged.json')
            self.assertEqual(json.loads((root / 'staged.json').read_text()), {'enableSkillCommands': True, 'unrelated': [1]})
            self.assertEqual(path.read_bytes(), original)

    def test_invalid_preferences_never_fall_back_or_repair(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, RECORDPREP_CONFIG_DIR=''):
            root = Path(temporary)
            path = root / 'settings.json'
            for content in ('[]', '{bad'):
                path.write_text(content)
                with self.assertRaises((OSError, ValueError)):
                    paths.stage_pi_settings(root, root / 'staged.json')
                self.assertEqual(path.read_text(), content)
                self.assertFalse((root / 'staged.json').exists())
            path.unlink()
            path.symlink_to(root / 'missing')
            with self.assertRaises(OSError):
                paths.effective_pi_settings(root)
