import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import profile_integration as ui
from recordprep.practice_profiles import bundled_profile_directory, validate_profile_directory
from recordprep.profile_contract import ProfileError


class ProfileContextTests(unittest.TestCase):
    def test_indicator_uses_application_guidance_not_historical_case_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.recordprep').mkdir()
            historical = root / '.recordprep/practice-profile.json'
            historical.write_bytes(b'Unavailable or malformed old reference')
            before = historical.read_bytes(), historical.stat().st_mtime_ns
            profile = validate_profile_directory(bundled_profile_directory('general')).draft
            title = Mock()
            window = SimpleNamespace(_title_widget=title, _resolve_case_root=lambda: root)
            with patch('recordprep.practice_profiles.default_profile_candidate', return_value=profile):
                ui.update_indicator(window)
            title.set_subtitle.assert_called_with('General Court Record')
            self.assertIn('selected application profile', ui.context_description(root))
            self.assertEqual((historical.read_bytes(), historical.stat().st_mtime_ns), before)

    def test_missing_current_application_guidance_is_not_silently_substituted(self):
        title = Mock()
        window = SimpleNamespace(_title_widget=title)
        with patch('recordprep.practice_profiles.default_profile_candidate',
                   side_effect=ProfileError('snapshot_unavailable', 'selection')):
            ui.update_indicator(window)
        title.set_subtitle.assert_called_with('Unavailable profile')
