"""Identical offline authoring transaction tests in both independent apps."""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
api = importlib.import_module(f"{PACKAGE}.practice_profiles")
contract = importlib.import_module(f"{PACKAGE}.profile_contract")
workflows = importlib.import_module(f"{PACKAGE}.profile_workflows")
store_module = importlib.import_module(f"{PACKAGE}.profile_store")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = store_module.ProfileStore(PACKAGE, config_root=self.root / "config", data_root=self.root / "data")
        self.base = api.validate_profile_directory(api.bundled_profile_directory("general")).draft

    def editor(self):
        return workflows.ProfileEditor.create(self.base, "Synthetic specialty")

    def test_cancel_and_snapshot_keep_resources_and_storage_unchanged(self):
        editor = self.editor()
        snapshot = editor.snapshot()
        self.assertNotEqual(snapshot.ref.specialty_id, self.base.ref.specialty_id)
        for name in self.base.manifest["resources"]:
            self.assertEqual(snapshot.resource(name), self.base.resource(name))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_save_export_register_identity_and_defaults_are_independent(self):
        editor = self.editor()
        destination = self.root / "created"
        ref = editor.save(self.store, destination, expected_head=None)
        self.assertEqual(self.store.load_profile_snapshot(ref), editor.snapshot())
        self.assertIsNone(self.store.read_registry()["default"])
        for path in destination.rglob("*"):
            self.assertEqual(path.stat().st_mode & 0o077, 0)
        identity = self.root / "identity.json"
        workflows.export_identity(editor.snapshot(), identity)
        counterpart = workflows.ProfileEditor.create(self.base, "ignored", identity=identity.read_bytes())
        self.assertEqual(counterpart.snapshot().ref.specialty_id, ref.specialty_id)
        # Identity supplies no instructions: this app's chosen base supplies them.
        for name in self.base.manifest["resources"]:
            self.assertEqual(counterpart.resources[name], self.base.resource(name))
        with self.assertRaises((contract.ProfileError, FileExistsError)):
            workflows.export_identity(editor.snapshot(), identity)
        with self.assertRaises(contract.ProfileError):
            editor.save(self.store, destination, expected_head=ref.content_sha256)
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(contract.ProfileError):
            workflows.export_profile(editor.snapshot(), empty)

    def test_counterpart_identity_never_translates_another_apps_resources(self):
        from test_practice_profiles import synthetic_files
        other = "recordprep" if PACKAGE == "focus" else "focus"
        other_base = contract.validate_contents(tuple(synthetic_files(other).items()), other)
        editor = self.editor()
        counterpart = workflows.ProfileEditor.create(other_base, "ignored", identity=contract.identity_descriptor(editor.snapshot()))
        other_snapshot = counterpart.snapshot()
        self.assertEqual(other_snapshot.ref.specialty_id, editor.snapshot().ref.specialty_id)
        self.assertEqual(other_snapshot.ref.application, other)
        self.assertNotEqual(other_snapshot.ref.content_sha256, editor.snapshot().ref.content_sha256)
        self.assertEqual(set(counterpart.resources), set(contract.RESOURCE_TYPES[other]))
        for name in counterpart.resources:
            self.assertEqual(counterpart.resources[name], other_base.resource(name))
        self.assertEqual(self.store.read_registry()["accepted"], [])

    def test_external_change_rejects_review_and_stale_editor(self):
        editor = self.editor()
        source = self.root / "source"
        first = editor.save(self.store, source, expected_head=None)
        review = workflows.ReviewedFolder.inspect(self.store, source)
        old_editor = workflows.ProfileEditor(review.draft, source=source)
        resource = next(name for name, kind in contract.RESOURCE_TYPES[PACKAGE].items() if kind == "md")
        path = source / review.draft.manifest["resources"][resource]
        path.write_text("Changed external guidance.\n", encoding="utf-8")
        with self.assertRaisesRegex(contract.ProfileError, "external_profile_changed"):
            review.accept(self.store)
        with self.assertRaisesRegex(contract.ProfileError, "external_profile_changed"):
            old_editor.save(self.store, self.root / "stale", expected_head=first.content_sha256)
        self.assertFalse((self.root / "stale").exists())
        self.assertEqual(self.store.read_registry()["heads"][first.specialty_id], first.content_sha256)
        current = workflows.ReviewedFolder.inspect(self.store, source)
        self.assertNotEqual(current.accept(self.store), first)

    def test_competing_acceptance_rejected_without_overwrite(self):
        editor = self.editor()
        first = editor.save(self.store, self.root / "first", expected_head=None)
        second = workflows.ProfileEditor(editor.snapshot())
        second.manifest["version"] = "2"
        second.save(self.store, self.root / "second", expected_head=first.content_sha256)
        editor.manifest["version"] = "3"
        with self.assertRaisesRegex(contract.ProfileError, "stale_profile_revision"):
            editor.save(self.store, self.root / "third", expected_head=first.content_sha256)
        self.assertFalse((self.root / "third").exists())

    def test_interrupted_export_never_accepts_or_leaves_partial_destination(self):
        editor = self.editor()
        with patch.object(workflows, "_publish_new_directory", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                editor.save(self.store, self.root / "failed", expected_head=None)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.store.read_registry()["accepted"], [])

    def test_atomic_export_refuses_racing_empty_destination(self):
        editor = self.editor()
        target = self.root / "racing"
        publish = workflows._publish_new_directory
        def race(pending, destination):
            destination.mkdir()
            publish(pending, destination)
        with patch.object(workflows, "_publish_new_directory", side_effect=race):
            with self.assertRaisesRegex(contract.ProfileError, "destination_exists"):
                workflows.export_profile(editor.snapshot(), target)
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_new_context_default_is_general_without_startup_or_read_writes(self):
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, self.base.ref)
        self.assertEqual(list(self.root.iterdir()), [])
        ref = api.accept_new_context_default(store=self.store)
        self.assertEqual(ref, self.base.ref)
        self.assertIsNone(self.store.read_registry()["default"])
        custom = self.editor().save(self.store, self.root / "custom", expected_head=None)
        self.store.set_default(custom)
        self.assertEqual(api.default_profile_candidate(store=self.store).ref, custom)
        self.assertEqual(api.accept_new_context_default(store=self.store), custom)
        self.assertEqual(self.store.load_profile_snapshot(ref).ref, self.base.ref)

    def test_new_context_default_requires_review_of_same_identity_conflict(self):
        editor = workflows.ProfileEditor(self.base)
        editor.manifest["description"] = "Explicitly accepted local revision."
        ref = editor.save(self.store, self.root / "local", expected_head=None)
        with self.assertRaisesRegex(contract.ProfileError, "review_default_revision_first"):
            api.accept_new_context_default(store=self.store)
        self.assertEqual(self.store.read_registry()["heads"][ref.specialty_id], ref.content_sha256)

    def test_missing_default_snapshot_never_substitutes_general(self):
        import shutil
        ref = self.editor().save(self.store, self.root / "custom", expected_head=None)
        self.store.set_default(ref)
        shutil.rmtree(self.store.data_root / "snapshots" / ref.content_sha256)
        with self.assertRaises(contract.ProfileError):
            api.default_profile_candidate(store=self.store)
        with self.assertRaises(contract.ProfileError):
            api.accept_new_context_default(store=self.store)
        self.assertEqual(len(self.store.read_registry()["accepted"]), 1)

    def test_explicit_registration_attaches_source_to_already_accepted_bytes(self):
        snapshot = self.editor().snapshot()
        ref = self.store.accept_profile(snapshot, expected_previous_digest=None)
        source = self.root / "registered"
        workflows.export_profile(snapshot, source)
        self.assertEqual(workflows.ReviewedFolder.inspect(self.store, source).accept(self.store), ref)
        registry = self.store.read_registry()
        self.assertEqual(len(registry["accepted"]), 1)
        self.assertEqual(registry["accepted"][0]["source"], str(source))
        self.assertEqual(self.store.load_profile_snapshot(ref), snapshot)
        self.assertIsNone(registry["default"])

    def test_export_rejects_linked_parent(self):
        (self.root / "linked").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(contract.ProfileError):
            workflows.export_profile(self.editor().snapshot(), self.root / "linked" / "escape")
        self.assertFalse((self.root / "escape").exists())
