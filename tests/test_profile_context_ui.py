import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import profile_integration as ui
from recordprep.practice_profiles import bundled_profile_directory, validate_profile_directory
from recordprep.profile_contract import ProfileError


class ProfileContextTests(unittest.TestCase):
    def test_missing_instructions_are_visible_without_reinterpreting_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile = validate_profile_directory(bundled_profile_directory("general")).draft
            button = Mock()
            window = SimpleNamespace(_title_widget=button, _resolve_case_root=lambda:root)
            with patch.object(ui,"read_case_profile_ref",return_value=profile.ref), patch("recordprep.practice_profiles.profile_store") as store:
                store.return_value.load_profile_snapshot.side_effect = ProfileError("snapshot_unavailable","selection")
                ui.update_indicator(window)
                button.set_subtitle.assert_called_with("Unavailable profile")
                description = ui.context_description(root)
                self.assertIn("Selected instructions unavailable", description)
                self.assertNotIn("SHA", description)
                self.assertIn("Browsing", description)
                store.return_value.load_profile_snapshot.side_effect = None
                store.return_value.load_profile_snapshot.return_value = profile
                store.return_value.read_registry.return_value = {"heads": {}, "accepted": [], "default": None}
                ui.update_indicator(window)
                button.set_subtitle.assert_called_with("General Court Record")
                self.assertEqual(list(root.iterdir()), [])
