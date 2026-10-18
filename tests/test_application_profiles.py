"""Current application-selection and portable-settings contracts, synthetic only."""
import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from recordprep import case_profiles as cases, practice_profiles as api
from recordprep.profile_contract import ProfileError
from recordprep.profile_portability import (locator_path, portable_store, save_portable_profiles,
                                            selected_directory, use_directory)
from recordprep.profile_store import ProfileStore


class ApplicationProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        env = patch.dict(os.environ, {"XDG_STATE_HOME": str(self.base / 'state'),
                                      "XDG_CONFIG_HOME": str(self.base / 'config'),
                                      "XDG_DATA_HOME": str(self.base / 'data'),
                                      "RECORDPREP_PROFILE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        self.store = api.profile_store()
        self.general = api.validate_profile_directory(api.bundled_profile_directory('general')).draft
        self.dependency = api.validate_profile_directory(api.bundled_profile_directory('california_dependency')).draft
        for profile in (self.general, self.dependency):
            self.store.accept_profile(profile, expected_previous_digest=None)
        self.store.set_default(self.dependency.ref)
        self.bundle = self.base / 'bundle'
        self.bundle.mkdir()

    def tree(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def test_missing_historical_snapshot_does_not_block_current_guidance_or_touch_bundle(self):
        directory = self.bundle / '.recordprep'
        directory.mkdir()
        ref = asdict(self.general.ref) | {'version': '9.9.9', 'content_sha256': 'a' * 64}
        (directory / 'practice-profile.json').write_text(json.dumps({'schema_version': 1, 'profile_ref': ref}))
        (self.bundle / 'old-summary.txt').write_text('Stored output remains unchanged.')
        before = self.tree(self.bundle)
        self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.dependency.ref)
        self.assertEqual(self.tree(self.bundle), before)
        self.store.set_default(self.general.ref)
        self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.general.ref)
        self.assertEqual(self.tree(self.bundle), before)

    def test_malformed_or_symlinked_historical_pin_is_not_instruction_authority(self):
        directory = self.bundle / '.recordprep'
        directory.mkdir()
        pin = directory / 'practice-profile.json'
        pin.write_text('malformed')
        self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.dependency.ref)
        pin.unlink()
        pin.symlink_to(self.base / 'missing')
        self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.dependency.ref)
        with self.assertRaises(ProfileError):
            cases.read_historical_case_profile_ref(self.bundle)

    def test_portable_save_and_explicit_selection_preserve_originals(self):
        before = self.tree(self.store.config_root), self.tree(self.store.data_root)
        destination = self.base / 'shared'
        save_portable_profiles(self.store, destination)
        self.assertIsNone(selected_directory())
        self.assertEqual((self.tree(self.store.config_root), self.tree(self.store.data_root)), before)
        self.assertEqual(set(p.name for p in destination.iterdir()), {'registry.json', 'snapshots'})
        use_directory(destination)
        self.assertEqual(api.profile_store().config_root, destination)
        self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.dependency.ref)
        self.assertFalse((destination / '.registry.lock').exists())
        self.assertTrue(locator_path().is_file())
        # Simulate another local process with empty private XDG stores; portable
        # registry+snapshots alone are sufficient. No other computer is contacted.
        with patch.dict(os.environ, {'RECORDPREP_PROFILE_DIR': str(destination),
                                     'XDG_CONFIG_HOME': str(self.base / 'empty-config'),
                                     'XDG_DATA_HOME': str(self.base / 'empty-data')}):
            self.assertEqual(cases.resolve_case_profile(self.bundle).ref, self.dependency.ref)
        self.assertEqual(list(self.bundle.iterdir()), [])

    def test_portable_modes_work_without_relaxing_private_store_or_chmod(self):
        destination = self.base / 'shared'
        save_portable_profiles(self.store, destination)
        for p in [destination, *destination.rglob('*')]:
            p.chmod(0o775 if p.is_dir() else 0o664)
        modes = {p: p.stat().st_mode for p in destination.rglob('*')}
        store = portable_store(destination)
        self.assertEqual(store.load_profile_snapshot(self.dependency.ref), self.dependency)
        self.assertEqual({p: p.stat().st_mode for p in modes}, modes)
        self.store.config_root.chmod(0o755)
        with self.assertRaises(ProfileError):
            self.store.read_registry()

    def test_portable_store_rejects_conflicts_corruption_and_partial_sync(self):
        destination = self.base / 'shared'
        save_portable_profiles(self.store, destination)
        conflict = destination / 'registry (conflicted copy).json'
        conflict.write_text('{}')
        with self.assertRaisesRegex(ProfileError, 'profile_sync_conflict'):
            use_directory(destination)
        self.assertFalse(locator_path().exists())
        conflict.unlink()
        snapshot = destination / 'snapshots' / self.dependency.ref.content_sha256
        resource = next(p for p in snapshot.rglob('*') if p.is_file() and p.name != 'profile.json')
        original = resource.read_bytes()
        resource.write_bytes(original + b' changed')
        with self.assertRaises(ProfileError):
            use_directory(destination)
        resource.unlink()
        with self.assertRaises(ProfileError):
            use_directory(destination)
        self.assertFalse(locator_path().exists())

    def test_portable_save_never_overwrites_and_rejects_stale_or_active_work(self):
        destination = self.base / 'shared'
        destination.mkdir()
        (destination / 'sentinel').write_text('keep')
        with self.assertRaisesRegex(ProfileError, 'destination_exists'):
            save_portable_profiles(self.store, destination)
        self.assertEqual((destination / 'sentinel').read_text(), 'keep')
        with self.assertRaises(ProfileError):
            save_portable_profiles(self.store, self.base / 'another', can_modify=lambda: False)
        self.assertFalse((self.base / 'another').exists())

    def test_configured_missing_store_does_not_fall_back(self):
        with patch.dict(os.environ, {'RECORDPREP_PROFILE_DIR': str(self.base / 'missing')}):
            with self.assertRaisesRegex(ProfileError, 'portable_store_unavailable'):
                api.profile_store()
        self.assertFalse((self.base / 'missing').exists())

    def test_portable_links_and_unsafe_modes_are_rejected(self):
        destination = self.base / 'shared'
        save_portable_profiles(self.store, destination)
        registry = destination / 'registry.json'
        original = registry.read_bytes()
        registry.chmod(0o666)
        with self.assertRaises(ProfileError):
            portable_store(destination).read_registry()
        registry.chmod(0o600)
        target = self.base / 'registry-copy'
        registry.rename(target)
        registry.symlink_to(target)
        with self.assertRaises(ProfileError):
            portable_store(destination).read_registry()
        self.assertEqual(target.read_bytes(), original)
