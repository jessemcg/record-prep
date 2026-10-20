"""RecordPrep's ordinary synchronized settings are not private journal files.

Only disposable files are read, written or chmodded by these tests.
"""
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from recordprep import _model_store as store


class SettingsPermissions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="recordprep-permissions-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "config.json"
        self.path.write_bytes(b'{"synthetic":1,"unknown":"preserve"}\n')
        self.path.chmod(0o664)
        # Some /tmp trees inherit a setgid group rather than the user's primary
        # group. Change only this disposable fixture to the intended test group.
        if self.path.stat().st_gid != os.getgid():
            os.chown(self.path, -1, os.getgid())

    def test_primary_group_writable_settings_are_read_without_repair(self):
        before = self.path.stat()
        with store.Store(self.path) as settings:
            self.assertEqual(settings.read()["bytes"], self.path.read_bytes())
        after = self.path.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns, before.st_mode),
                         (after.st_ino, after.st_mtime_ns, after.st_mode))
        self.assertEqual(stat.S_IMODE(after.st_mode), 0o664)

    def test_ordinary_save_accepts_sync_mode_and_publishes_owner_writable_file(self):
        original = store.read_ordinary(self.path)
        original["synthetic"] = 2
        store.save_ordinary(self.path, original)
        self.assertEqual(store.parse(self.path.read_bytes()), {"synthetic": 2, "unknown": "preserve"})
        mode = stat.S_IMODE(self.path.stat().st_mode)
        self.assertTrue(mode & stat.S_IWUSR)
        self.assertEqual(mode, 0o600)

    def test_world_writable_settings_remain_rejected(self):
        self.path.chmod(0o666)
        before = self.path.read_bytes()
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, "unsafe_settings_file"):
                settings.read()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o666)

    def test_write_access_for_a_different_group_remains_rejected(self):
        with patch.object(store.os, "getgid", return_value=os.getgid() + 1):
            with store.Store(self.path) as settings:
                with self.assertRaisesRegex(store.Failure, "unsafe_settings_file"):
                    settings.read()

    def test_private_state_does_not_inherit_ordinary_settings_permission_policy(self):
        with self.assertRaisesRegex(store.Failure, "unsafe_state_file"):
            store.private_read(self.path)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o664)

    def test_writer_lock_remains_private(self):
        lock = self.root / ".config.json.writer.lock"
        lock.write_bytes(b"")
        lock.chmod(0o664)
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, "unsafe_settings_lock"):
                with settings.lock():
                    self.fail("unsafe lock was accepted")
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o664)

    def test_hardlinked_settings_remain_rejected(self):
        os.link(self.path, self.root / "second-link")
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, "unsafe_settings_file"):
                settings.read()


if __name__ == "__main__":
    unittest.main()
