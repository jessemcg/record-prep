"""RecordPrep's ordinary synchronized settings are not private journal files.

Only disposable files are read, written or chmodded by these tests.
"""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from recordprep import _model_store as store


class SettingsPermissions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="recordprep-permissions-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        environment = patch.dict(os.environ, XDG_STATE_HOME=str(self.root / 'state'))
        environment.start()
        self.addCleanup(environment.stop)
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
        lock = store.settings_lock_path(self.path)
        store.private_dir(lock.parent)
        lock.write_bytes(b"")
        lock.chmod(0o664)
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, "unsafe_settings_lock"):
                with settings.lock():
                    self.fail("unsafe lock was accepted")
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o664)

    def test_synced_legacy_lock_is_ignored_and_unchanged(self):
        legacy = self.root / '.config.json.writer.lock'
        legacy.write_bytes(b'legacy')
        legacy.chmod(0o644)
        before = legacy.stat()
        value = store.read_ordinary(self.path)
        value['synthetic'] = 2
        store.save_ordinary(self.path, value)
        after = legacy.stat()
        self.assertEqual((before.st_ino, before.st_mode, before.st_mtime_ns),
                         (after.st_ino, after.st_mode, after.st_mtime_ns))
        self.assertEqual(legacy.read_bytes(), b'legacy')
        lock = store.settings_lock_path(self.path)
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(lock.parent.stat().st_mode), 0o700)

    def test_process_contention_and_stable_lock_after_settings_replace(self):
        child = '''from pathlib import Path
import sys
from recordprep._model_store import Store, Failure
try:
    with Store(Path(sys.argv[1])) as s, s.lock(): pass
except Failure as exc:
    print(str(exc))
'''
        with store.Store(self.path) as settings, settings.lock():
            lock = store.settings_lock_path(self.path)
            inode = lock.stat().st_ino
            settings.replace(settings.revision(), b'{"synthetic":2}\n')
            result = subprocess.run([sys.executable, '-c', child, str(self.path)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), 'settings_busy')
            other = self.root / 'other.json'
            with store.Store(other) as independent, independent.lock():
                self.assertNotEqual(store.settings_lock_path(other), lock)
        with store.Store(self.path) as settings, settings.lock():
            self.assertEqual(lock.stat().st_ino, inode)

    def test_saves_without_legacy_lock_never_create_one(self):
        draft = store.read_ordinary(self.path)
        store.save_ordinary(self.path, draft)
        self.assertFalse((self.root / '.config.json.writer.lock').exists())

    def test_conflict_and_stale_guards_still_preserve_settings(self):
        draft = store.read_ordinary(self.path)
        changed = b'{"synthetic":99}\n'
        self.path.write_bytes(changed)
        with self.assertRaisesRegex(store.Failure, 'stale_settings'):
            store.save_ordinary(self.path, draft)
        self.assertEqual(self.path.read_bytes(), changed)
        conflict = self.root / 'config (conflicted copy).json'
        conflict.write_bytes(b'{}')
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, 'sync_conflict'):
                with settings.lock(): self.fail('conflict accepted')
        self.assertEqual(self.path.read_bytes(), changed)

    def test_unsafe_local_directory_is_not_repaired(self):
        directory = store.settings_lock_path(self.path).parent
        store.private_dir(directory)
        directory.chmod(0o755)
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, 'unsafe_state_directory'):
                with settings.lock(): self.fail('unsafe directory accepted')
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)

    def test_linked_local_locks_are_rejected(self):
        lock = store.settings_lock_path(self.path)
        store.private_dir(lock.parent)
        target = self.root / 'target'
        target.write_bytes(b'')
        target.chmod(0o600)
        for symbolic in (False, True):
            with self.subTest(symbolic=symbolic):
                if symbolic: lock.symlink_to(target)
                else: os.link(target, lock)
                with store.Store(self.path) as settings:
                    with self.assertRaises(OSError):
                        with settings.lock(): self.fail('linked lock accepted')
                lock.unlink()

    def test_default_state_location_and_relative_override(self):
        with patch.dict(os.environ, HOME=str(self.root), XDG_STATE_HOME=''):
            self.assertEqual(store.settings_lock_path(self.path).parent,
                             self.root / '.local/state/recordprep/settings-locks')
        with patch.dict(os.environ, XDG_STATE_HOME='relative'):
            with store.Store(self.path) as settings:
                with self.assertRaisesRegex(store.Failure, 'unsafe_state_path'):
                    with settings.lock(): self.fail('relative state accepted')

    def test_hardlinked_settings_remain_rejected(self):
        os.link(self.path, self.root / "second-link")
        with store.Store(self.path) as settings:
            with self.assertRaisesRegex(store.Failure, "unsafe_settings_file"):
                settings.read()


if __name__ == "__main__":
    unittest.main()
