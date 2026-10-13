"""Deletion tombstones only; immutable accepted case instructions survive."""
import importlib
import json
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
api = importlib.import_module(PACKAGE + ".practice_profiles")
workflow = importlib.import_module(PACKAGE + ".profile_workflows")
store_module = importlib.import_module(PACKAGE + ".profile_store")


class ProfileDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = api.ProfileStore(PACKAGE, config_root=root / "config", data_root=root / "data")
        self.general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
        self.custom = workflow.ProfileEditor.create(self.general, "Synthetic personal profile").snapshot()
        self.store.managed_save(self.custom, expected_head=None, expected_default=None)

    def catalog(self):
        return api.profile_catalog(store=self.store, customization=lambda _snapshot: None)

    def delete(self, ref=None, default=None, **kwargs):
        self.store.delete_profile(ref or self.custom.ref, expected_default=default, **kwargs)

    def test_delete_hides_catalog_but_preserves_all_snapshot_bytes_and_refs(self):
        revised = workflow.ProfileEditor(self.custom)
        key = "research" if PACKAGE == "focus" else "classification"
        revised.resources[key] += "\nSynthetic revision.\n"
        revision = revised.snapshot()
        self.store.managed_save(revision, expected_head=self.custom.ref.content_sha256, expected_default=None)
        before = self.store.read_registry()
        snapshots = {path: path.read_bytes() for path in self.store.data_root.rglob("*") if path.is_file()}
        self.delete(revision.ref)
        after = self.store.read_registry()
        self.assertEqual(after["accepted"], before["accepted"])
        self.assertEqual(after["heads"], before["heads"])
        self.assertEqual(snapshots, {path: path.read_bytes() for path in snapshots})
        for snapshot in (self.custom, revision):
            self.assertEqual(self.store.load_profile_snapshot(snapshot.ref).files, snapshot.files)
        self.assertNotIn(self.custom.ref.specialty_id, {item.snapshot.ref.specialty_id for item in self.catalog()})

    def test_deleting_current_default_returns_to_general(self):
        self.store.set_default(self.custom.ref)
        self.delete(default=asdict(self.custom.ref))
        self.assertIsNone(self.store.read_registry()["default"])
        self.assertEqual(api.default_profile_candidate(store=self.store).ref.specialty_id, "general-court-record")

    def test_other_default_is_preserved(self):
        self.store.accept_profile(self.general, expected_previous_digest=None)
        self.store.set_default(self.general.ref)
        self.delete(default=asdict(self.general.ref))
        self.assertEqual(self.store.read_registry()["default"], asdict(self.general.ref))

    def test_builtins_even_personally_customized_are_protected(self):
        for name in api.BUNDLED_PROFILES:
            snapshot = api.validate_profile_directory(api.bundled_profile_directory(name)).draft
            self.store.managed_save(snapshot, expected_head=None, expected_default=None, personal=True)
            before = self.store.registry_path.read_bytes()
            with self.assertRaises(api.ProfileError) as error:
                self.delete(snapshot.ref)
            self.assertEqual(error.exception.issue.code, "protected_profile")
            self.assertEqual(self.store.registry_path.read_bytes(), before)

    def test_stale_head_and_default_are_rejected(self):
        for change in ("head", "default"):
            with self.subTest(change=change):
                if change == "head":
                    editor = workflow.ProfileEditor(self.custom)
                    editor.resources["research" if PACKAGE == "focus" else "classification"] += "\nNew head.\n"
                    self.store.managed_save(editor.snapshot(), expected_head=self.custom.ref.content_sha256, expected_default=None)
                else:
                    self.store.set_default(self.custom.ref)
                before = self.store.registry_path.read_bytes()
                with self.assertRaises(api.ProfileError):
                    self.delete()
                self.assertEqual(self.store.registry_path.read_bytes(), before)

    def test_work_guard_is_checked_before_and_inside_transaction(self):
        for values in ([False], [True, False]):
            checks = iter(values)
            before = self.store.registry_path.read_bytes()
            with self.assertRaises(api.ProfileError):
                self.delete(can_modify=lambda: next(checks))
            self.assertEqual(self.store.registry_path.read_bytes(), before)

    def test_deleted_identity_cannot_be_resurrected_or_made_default(self):
        self.delete()
        before = self.store.registry_path.read_bytes()
        operations = (
            lambda: self.store.managed_save(self.custom, expected_head=self.custom.ref.content_sha256, expected_default=None),
            lambda: self.store.accept_profile(self.custom, expected_previous_digest=self.custom.ref.content_sha256),
            lambda: self.store.set_default(self.custom.ref),
            self.delete,
        )
        for operation in operations:
            with self.assertRaises(api.ProfileError):
                operation()
            self.assertEqual(self.store.registry_path.read_bytes(), before)

    def test_name_can_be_reused_under_a_new_identity(self):
        self.delete()
        replacement = workflow.ProfileEditor.create(self.general, self.custom.manifest["display_name"]).snapshot()
        self.store.managed_save(replacement, expected_head=None, expected_default=None)
        self.assertNotEqual(replacement.ref.specialty_id, self.custom.ref.specialty_id)
        self.assertIn(replacement.ref, [item.snapshot.ref for item in self.catalog()])
        self.assertEqual(self.store.load_profile_snapshot(self.custom.ref).ref, self.custom.ref)

    def test_malformed_tombstones_fail_without_repair(self):
        original = self.store.read_registry()
        for deleted in (["general-court-record"], ["unknown"], [self.custom.ref.specialty_id] * 2, "bad"):
            value = dict(original, deleted=deleted)
            self.store.registry_path.write_text(json.dumps(value))
            before = self.store.registry_path.read_bytes()
            with self.assertRaises(api.ProfileError):
                self.store.read_registry()
            self.assertEqual(self.store.registry_path.read_bytes(), before)
        self.store.registry_path.write_text(json.dumps(original | {"deleted": [self.custom.ref.specialty_id], "default": asdict(self.custom.ref)}))
        with self.assertRaises(api.ProfileError):
            self.store.read_registry()

    def test_atomic_write_failure_leaves_registry_and_snapshots_intact(self):
        before = self.store.registry_path.read_bytes()
        with patch.object(store_module, "_atomic_json", side_effect=OSError("synthetic")), self.assertRaises(OSError):
            self.delete()
        self.assertEqual(self.store.registry_path.read_bytes(), before)
        self.assertEqual(self.store.load_profile_snapshot(self.custom.ref).ref, self.custom.ref)

    def test_unsafe_permissions_are_not_repaired(self):
        self.store.config_root.chmod(0o755)
        before = self.store.registry_path.read_bytes()
        with self.assertRaises(api.ProfileError):
            self.delete()
        self.assertEqual(self.store.registry_path.read_bytes(), before)
        self.assertEqual(self.store.config_root.stat().st_mode & 0o777, 0o755)


if __name__ == "__main__":
    unittest.main()
