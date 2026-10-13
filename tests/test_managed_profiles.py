"""Offline managed-save/catalog release and failure conformance in both apps."""
import importlib
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

PACKAGE = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
api = importlib.import_module(PACKAGE + ".practice_profiles")
contract = importlib.import_module(PACKAGE + ".profile_contract")
workflows = importlib.import_module(PACKAGE + ".profile_workflows")
store_module = importlib.import_module(PACKAGE + ".profile_store")


class ManagedProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = api.ProfileStore(PACKAGE, config_root=self.root / "config", data_root=self.root / "data")
        self.base = api.validate_profile_directory(api.bundled_profile_directory("general")).draft

    def catalog(self, **kwargs):
        return api.profile_catalog(store=self.store, customization=kwargs.get("customization", lambda _base: None))

    def save(self, snapshot, **kwargs):
        registry = self.store.read_registry()
        return self.store.managed_save(snapshot, expected_head=registry["heads"].get(snapshot.ref.specialty_id),
                                       expected_default=registry["default"], **kwargs)

    def edit(self, snapshot=None):
        editor = workflows.ProfileEditor(snapshot or self.base)
        resource = "research" if PACKAGE == "focus" else "overview"
        editor.resources[resource] += "\nSynthetic substantive guidance.\n"
        return editor.snapshot()

    def test_fresh_catalog_and_inspection_have_no_side_effects(self):
        catalog = self.catalog()
        self.assertEqual([item.snapshot.manifest["display_name"] for item in catalog],
                         ["General Court Record", "California Juvenile Dependency"])
        for item in catalog:
            self.assertFalse(item.personal)
            for resource in item.snapshot.manifest["resources"]:
                if resource == "policies":
                    self.assertEqual(item.snapshot.resource(resource), {})
                else:
                    self.assertTrue(item.snapshot.resource(resource))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_direct_save_unchanged_idempotence_default_advance_and_clear(self):
        first = self.save(self.base, personal=False, use_for_new_cases=True)
        unchanged = self.store.registry_path.read_bytes()
        mtime = self.store.registry_path.stat().st_mtime_ns
        self.assertEqual(self.save(self.base, personal=False, use_for_new_cases=True), first)
        self.assertEqual(self.store.registry_path.read_bytes(), unchanged)
        self.assertEqual(self.store.registry_path.stat().st_mtime_ns, mtime)
        revised = self.edit()
        second = self.save(revised, personal=True)
        registry = self.store.read_registry()
        self.assertEqual(registry["default"], asdict(second))
        self.assertEqual(registry["personal"], [second.specialty_id])
        self.assertEqual(self.catalog()[0].snapshot.ref, second)
        self.save(revised, personal=True, use_for_new_cases=False)
        self.assertIsNone(self.store.read_registry()["default"])
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, second)
        self.assertEqual(self.store.load_profile_snapshot(first).files, self.base.files)

    def test_invalid_active_concurrent_and_publication_failure_leave_references(self):
        original = self.save(self.base, personal=False)
        before = self.store.registry_path.read_bytes()
        changed = self.edit()
        with self.assertRaisesRegex(contract.ProfileError, "work_active"):
            self.store.managed_save(changed, expected_head=original.content_sha256, expected_default=None, can_modify=lambda: False)
        with self.assertRaisesRegex(contract.ProfileError, "stale_profile"):
            self.store.managed_save(changed, expected_head=None, expected_default=None)
        with patch.object(self.store, "_publish_snapshot", side_effect=OSError("synthetic publication failure")):
            with self.assertRaises(OSError):
                self.save(changed)
        bad = workflows.ProfileEditor(self.base)
        bad.resources["research" if PACKAGE == "focus" else "overview"] = ""
        with self.assertRaises(contract.ProfileError):
            bad.managed_save(self.store, expected_head=original.content_sha256, expected_default=None,
                             validate=lambda _draft: None, can_modify=lambda: True)
        self.assertEqual(self.store.registry_path.read_bytes(), before)

    def test_compiler_failure_and_mid_publication_guard_do_not_authorize(self):
        editor = workflows.ProfileEditor(self.edit())
        with self.assertRaises(ValueError):
            editor.managed_save(self.store, expected_head=None, expected_default=None,
                                validate=lambda _draft: (_ for _ in ()).throw(ValueError("synthetic compiler failure")),
                                can_modify=lambda: True)
        self.assertEqual(list(self.root.iterdir()), [])
        allowed = [True]
        publish = self.store._publish_snapshot
        def change(draft):
            publish(draft)
            allowed[0] = False
        with patch.object(self.store, "_publish_snapshot", side_effect=change):
            with self.assertRaises(contract.ProfileError):
                self.save(editor.snapshot(), can_modify=lambda: allowed[0])
        self.assertEqual(self.store.read_registry()["accepted"], [])

    def test_default_cas_and_unavailable_default_are_errors(self):
        ref = self.save(self.base, personal=False, use_for_new_cases=True)
        with self.assertRaisesRegex(contract.ProfileError, "stale_profile"):
            self.store.managed_save(self.edit(), expected_head=ref.content_sha256, expected_default=None)
        import shutil
        shutil.rmtree(self.store.data_root / "snapshots" / ref.content_sha256)
        with self.assertRaises(contract.ProfileError):
            api.default_profile_candidate(store=self.store)

    def test_release_update_does_not_overwrite_personal_or_case_snapshots(self):
        self.save(self.base, personal=False)
        updated = self.edit()
        # Shipped baseline update wins over ordinary acceptance, not private ownership.
        catalog = workflows.current_catalog(self.store, [updated], known_baselines=[self.base.ref.content_sha256])
        self.assertEqual(catalog[0].snapshot.ref, updated.ref)
        personal = self.edit(updated)
        self.save(personal, personal=True)
        catalog = workflows.current_catalog(self.store, [updated], known_baselines=[self.base.ref.content_sha256])
        self.assertEqual(catalog[0].snapshot.ref, personal.ref)
        self.assertEqual(self.store.load_profile_snapshot(self.base.ref).files, self.base.files)

    def test_third_public_specialty_needs_only_data_and_catalog_entry(self):
        editor = workflows.ProfileEditor.create(self.base, "Synthetic public third specialty")
        snapshot = editor.snapshot()
        source = self.root / "public-third"
        workflows.export_profile(snapshot, source)
        original = api.bundled_profile_directory
        def directory(name):
            return source if name == "third" else original(name)
        with patch.object(api, "BUNDLED_PROFILES", (*api.BUNDLED_PROFILES, "third")), patch.object(api, "bundled_profile_directory", side_effect=directory):
            catalog = self.catalog()
            self.assertEqual(len(catalog), 3)
            third = catalog[-1].snapshot
            self.assertEqual(third.ref, snapshot.ref)
            for stage in contract.STAGE_RESOURCES[PACKAGE]:
                self.assertTrue(contract.compile_stage_profile(third, stage, core_contract=b"synthetic core").component_sha256)
            ref = self.save(third, personal=False)
            self.assertEqual(self.catalog()[-1].snapshot.ref, ref)
            edited = self.edit(third)
            self.save(edited, personal=True)
            self.assertEqual(self.catalog()[-1].snapshot.ref, edited.ref)

    def test_old_registry_read_does_not_rewrite_and_name_collision_is_rejected(self):
        self.store.accept_profile(self.base, expected_previous_digest=None)
        before = self.store.registry_path.read_bytes()
        self.catalog()
        self.assertEqual(self.store.registry_path.read_bytes(), before)
        self.assertNotIn("personal", self.store.read_registry())
        editor = workflows.ProfileEditor.create(self.base, self.base.manifest["display_name"])
        with self.assertRaisesRegex(contract.ProfileError, "conflicting_profile_name"):
            self.save(editor.snapshot())
        self.assertEqual(self.store.registry_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
