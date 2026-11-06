"""Case-local classifier checkpoints tolerate sync modes, never unsafe paths."""
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from recordprep.classification_profiles import _work_directory
from recordprep.profile_contract import ProfileError
from recordprep.profile_store import _check_directory


class ClassificationWorkPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / ".recordprep/profile-work/basic/fingerprint"
        self.work.mkdir(parents=True)
        self.directories = [self.root / ".recordprep", self.work.parent.parent,
                            self.work.parent, self.work]

    def test_synced_checkpoints_are_reused_without_chmod_or_rewrite(self):
        checkpoint = self.work / "CT_basic.jsonl"
        checkpoint.write_text('{"file_name":"0001.txt","page_type":"CT_report"}\n')
        for mode, file_mode in ((0o700, 0o600), (0o755, 0o644), (0o775, 0o664)):
            with self.subTest(mode=oct(mode)):
                for directory in self.directories:
                    directory.chmod(mode)
                checkpoint.chmod(file_mode)
                watched = self.directories + [checkpoint]
                before = {p: (stat.S_IMODE(p.stat().st_mode), p.stat().st_mtime_ns)
                          for p in watched}
                content = checkpoint.read_bytes()
                self.assertEqual(_work_directory(self.root, "basic", "fingerprint"), self.work)
                self.assertEqual(before, {p: (stat.S_IMODE(p.stat().st_mode), p.stat().st_mtime_ns)
                                          for p in watched})
                self.assertEqual(checkpoint.read_bytes(), content)

    def test_new_checkpoint_directories_are_still_created_owner_only(self):
        created = _work_directory(self.root, "dates", "new-fingerprint")
        for directory in (created.parent, created):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_world_writable_directory_is_rejected_at_every_level(self):
        for directory in self.directories:
            with self.subTest(directory=directory.relative_to(self.root)):
                directory.chmod(0o777)
                with self.assertRaises(ProfileError) as error:
                    _work_directory(self.root, "basic", "fingerprint")
                self.assertEqual(error.exception.issue.code, "unsafe_case_profile_directory")
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o777)
                directory.chmod(0o755)

    def test_foreign_owned_directory_is_rejected_at_every_level(self):
        actual_stat = Path.stat
        for directory in self.directories:
            def foreign(path, *args, **kwargs):
                info = actual_stat(path, *args, **kwargs)
                if path == directory:
                    return SimpleNamespace(st_mode=info.st_mode, st_uid=os.getuid() + 1)
                return info
            with self.subTest(directory=directory.relative_to(self.root)), \
                    patch.object(Path, "stat", foreign), self.assertRaises(ProfileError):
                _work_directory(self.root, "basic", "fingerprint")

    def test_symlink_is_rejected_at_every_level_without_touching_target(self):
        for index, directory in reversed(list(enumerate(self.directories))):
            with self.subTest(directory=directory.relative_to(self.root)):
                target = self.root / f"redirect-{index}"
                directory.rename(target)
                directory.symlink_to(target, target_is_directory=True)
                before = target.stat().st_mtime_ns
                try:
                    with self.assertRaises((OSError, ProfileError)):
                        _work_directory(self.root, "basic", "fingerprint")
                    self.assertEqual(target.stat().st_mtime_ns, before)
                finally:
                    directory.unlink()
                    target.rename(directory)

    def test_non_directory_checkpoint_component_is_rejected(self):
        self.work.rmdir()
        self.work.write_text("not a directory\n")
        with self.assertRaises((OSError, ProfileError)):
            _work_directory(self.root, "basic", "fingerprint")
        self.assertEqual(self.work.read_text(), "not a directory\n")

    def test_private_store_directory_policy_is_not_relaxed(self):
        self.work.chmod(0o755)
        with self.assertRaises(ProfileError) as error:
            _check_directory(self.work, private=True)
        self.assertEqual(error.exception.issue.code, "store_permissions")
