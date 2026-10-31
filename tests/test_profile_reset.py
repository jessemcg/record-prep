"""Confirmed immediate reset, real GTK/managed stores, no private data or models."""
import copy
from dataclasses import asdict
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from recordprep import practice_profiles as api
from recordprep.profile_contract import ProfileError
from recordprep.profile_editor_ui import ProfileEditorWindow, editable_profile, topic_editor_text
from recordprep.profile_workflows import ProfileEditor
from recordprep.profile_integration import preview
from recordprep.settings_navigation import descendants
import test_unified_settings as unified
from test_unified_settings import Gtk, Adw, drain, dispose


def tree_bytes(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


class BundledIdentityTests(unittest.TestCase):
    def test_exact_identity_not_name_or_creation_base(self):
        bundle = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        self.assertIsNotNone(bundle)
        custom = ProfileEditor.create(bundle, bundle.manifest["display_name"]).snapshot()
        for app, identity in (("focus", api.DEFAULT_PROFILE_ID), (api.APPLICATION, custom.ref.specialty_id),
                              (api.APPLICATION, "general-court-record")):
            self.assertIsNone(api.bundled_profile_for_identity(app, identity))
        with patch.object(api, "profile_catalog", side_effect=AssertionError("personal lookup")):
            self.assertEqual(api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID).files, bundle.files)

    def test_future_bundle_and_corrupt_bundle(self):
        base = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        editor = ProfileEditor.create(base, "Synthetic Future Specialty")
        future = editor.snapshot()
        from recordprep.profile_contract import ValidationResult
        with patch.object(api, "BUNDLED_PROFILES", ("future",)), patch.object(api, "validate_profile_directory", return_value=ValidationResult(future, ())):
            self.assertEqual(api.bundled_profile_for_identity(api.APPLICATION, future.ref.specialty_id).files, future.files)
        with patch.object(api, "validate_profile_directory", return_value=ValidationResult(None, ())):
            with self.assertRaises(ProfileError):
                api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)


class ProfileResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not Gtk.init_check():
            raise unittest.SkipTest("GTK display unavailable")
        Adw.init()
        cls.app = Adw.Application(application_id="org.synthetic.RecordPrep.ResetTests")
        cls.app.register(None)

    setUp = unified.UnifiedSettingsTests.setUp
    profile_window = unified.UnifiedSettingsTests.profile_window

    def window(self):
        w, store = self.profile_window()
        w.preview = Mock(side_effect=lambda snapshot: preview(snapshot, Path(__file__).resolve().parents[1] / ".pi"))
        self.bundle = api.bundled_profile_for_identity(api.APPLICATION, api.DEFAULT_PROFILE_ID)
        return w, store

    def confirm(self, w):
        dialog = w._reset()
        self.assertIsNotNone(dialog)
        dialog.response("reset")
        drain()

    def test_cancel_duplicate_and_default_leave_dirty_draft_and_store_unchanged(self):
        w, store = self.window()
        w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] = ""
        before = w._state(), tree_bytes(self.root)
        dialog = w._reset()
        self.assertIs(w._reset(), dialog)
        self.assertEqual(dialog.get_default_response(), "cancel")
        self.assertEqual(dialog.get_close_response(), "cancel")
        self.assertEqual(dialog.get_response_appearance("reset"), Adw.ResponseAppearance.DESTRUCTIVE)
        for text in ("Classification and Summaries", "approved names", "topic catalogs", "unsaved profile edits", "Saves immediately", "Model settings, case files, and generated output"):
            self.assertIn(text, dialog.get_body())
        dialog.response("cancel")
        drain()
        self.assertEqual((w._state(), tree_bytes(self.root)), before)
        w.preview.assert_not_called()
        w.on_saved.assert_not_called()
        self.assertIsNone(w.reset_dialog)

    def test_invalid_dirty_draft_exact_immediate_save_selection_history_and_idempotence(self):
        w, store = self.window()
        self.assertTrue(w._save())
        old_ref = w.editor.base.ref
        w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] = "Synthetic prior revision"
        self.assertTrue(w._save())
        prior = w.editor.base.ref
        prior_files = store.load_profile_snapshot(prior).files
        w.editor.resources["naming"]["forms"][0]["name"] = ""
        w.editor.resources["hearings"][0]["guidance"] = ""
        self.confirm(w)
        self.assertEqual(w.message.get_text(), "Profile reset to bundled prompts and saved.")
        self.assertFalse(w._dirty())
        self.assertTrue(w.get_visible())
        self.assertEqual(w.editor.snapshot().files, self.bundle.files)
        self.assertEqual(store.load_profile_snapshot(w.editor.base.ref).files, self.bundle.files)
        self.assertEqual(store.load_profile_snapshot(prior).files, prior_files)
        self.assertEqual(store.load_profile_snapshot(old_ref).files, self.bundle.files)
        registry = store.read_registry()
        self.assertIn(api.DEFAULT_PROFILE_ID, registry["personal"])
        self.assertIn(api.DEFAULT_PROFILE_ID, registry["initialized"])
        self.assertIsNone(registry["default"])
        before = tree_bytes(self.root)
        self.confirm(w)
        self.assertEqual(tree_bytes(self.root), before)
        w.on_saved.assert_called_with(self.bundle.ref)
        self.assertEqual(api.profile_catalog(store=store, customization=lambda _: None)[0].snapshot.files, self.bundle.files)

    def test_default_advances_only_same_identity(self):
        for selected in (True, False):
            with self.subTest(selected=selected):
                w, store = self.window()
                w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] = "Synthetic old guidance"
                old = w.editor.snapshot()
                other = ProfileEditor.create(self.bundle, "Other synthetic profile").snapshot()
                store.managed_save(other, expected_head=None, expected_default=None, use_for_new_cases=True)
                store.managed_save(old, expected_head=None, expected_default=asdict(other.ref), use_for_new_cases=selected)
                registry = store.read_registry()
                w.expected_head = old.ref.content_sha256
                w.expected_default = registry["default"]
                self.confirm(w)
                expected = self.bundle.ref if selected else other.ref
                self.assertEqual(store.read_registry()["default"], asdict(expected))
                w.destroy()
                # Separate stores for the second iteration.
                self.root = self.root / "next"

    def test_retained_topics_buffers_undo_bindings_and_ordinary_save(self):
        w, store = self.window()
        rt_buffer = next(x for x in descendants(w.pages["rt"]) if isinstance(x, Gtk.TextView)).get_buffer()
        rt_buffer.set_text("Synthetic dirty RT")
        rt_buffer.select_range(rt_buffer.get_iter_at_offset(5), rt_buffer.get_iter_at_offset(2))
        values = w.editor.resources["hearings"]
        surviving = values[0]
        missing = values.pop(1)
        surviving["title"] = "Synthetic renamed"
        surviving["guidance"] = "Synthetic dirty topic"
        values.reverse()
        values.append({"id": "personal-only", "title": "Only personal", "guidance": "Synthetic prose"})
        # Render only the synthetic setup. Reset itself must never rebuild.
        w._render()
        w._recognition_cards['RT_cover'][0].set_expanded(True)
        rt_buffer = next(x for x in descendants(w.pages["rt"]) if isinstance(x, Gtk.TextView)).get_buffer()
        detail = "topic:hearings:" + surviving["id"]
        card = w._topic_expanders[detail]
        card.set_expanded(True)
        buffer = w._topic_editors[detail].get_child().get_buffer()
        w._select_page("hearings-topics")
        w.nav_groups["Summaries"].set_expanded(True)
        with patch.object(w, "_render", side_effect=AssertionError("rebuild")):
            self.confirm(w)
        self.assertEqual(w.editor.snapshot().files, self.bundle.files)
        self.assertIs(w.editor.resources["hearings"], values)
        self.assertIs(values[0], surviving)
        self.assertIs(w._topic_expanders[detail], card)
        self.assertTrue(card.get_expanded())
        self.assertTrue(w.nav_groups["Summaries"].get_expanded())
        self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "hearings-topics")
        self.assertIs(w._topic_editors[detail].get_child().get_buffer(), buffer)
        self.assertNotIn("topic:hearings:personal-only", w._topic_editors)
        self.assertIn("topic:hearings:" + missing["id"], w._topic_editors)
        self.assertEqual(buffer.get_text(*buffer.get_bounds(), True), topic_editor_text(values[0]["guidance"]))
        self.assertFalse(w._dirty())
        self.assertTrue(buffer.get_can_undo())
        buffer.undo()
        self.assertTrue(w._dirty())
        self.assertIn("Synthetic dirty topic", values[0]["guidance"])
        self.assertEqual(store.load_profile_snapshot(w.editor.base.ref).files, self.bundle.files)
        rt_buffer.insert_at_cursor(" subsequent synthetic edit")
        self.assertIn("subsequent synthetic edit", w.editor.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"])
        self.assertTrue(w._save())
        self.assertFalse(w._dirty())
        saved = store.load_profile_snapshot(w.editor.base.ref)
        self.assertIn("subsequent synthetic edit", saved.resource("classification_tasks")["page_types"]["rt"]["RT_cover"])
        reopened = editable_profile(saved)
        self.assertEqual(reopened.snapshot().files, saved.files)

    def test_selection_viewport_and_navigation_survive_shorter_replacement(self):
        w, _ = self.window()
        w._select_page("rt")
        drain()
        view = next(x for x in descendants(w.pages["rt"]) if isinstance(x, Gtk.TextView))
        buffer = view.get_buffer()
        buffer.set_text("Synthetic long unsaved guidance.\n" * 500)
        scroll = view.get_ancestor(Gtk.ScrolledWindow)
        drain()
        scroll.get_vadjustment().set_value(200)
        buffer.select_range(buffer.get_iter_at_offset(12000), buffer.get_iter_at_offset(10000))
        self.confirm(w)
        self.assertEqual(w.editor.snapshot().files, self.bundle.files)
        self.assertEqual(w._navigation.view.get_visible_page().get_tag(), "rt")
        self.assertIs(next(x for x in descendants(w.pages["rt"]) if isinstance(x, Gtk.TextView)), view)
        selections = w._navigation._selections["rt"]
        self.assertEqual(selections[0][1:], (buffer.get_char_count(), buffer.get_char_count()))
        adjustment = scroll.get_vadjustment()
        self.assertAlmostEqual(adjustment.get_value(), min(200, max(0, adjustment.get_upper() - adjustment.get_page_size())), delta=2)
        self.assertFalse(w._dirty())

    def test_stale_head_and_default_keep_draft_and_stale_expectations(self):
        for change in ("head", "default"):
            with self.subTest(change=change):
                w, store = self.window()
                dialog = w._reset()
                edit = ProfileEditor(self.bundle)
                if change == "head":
                    edit.resources["classification_tasks"]["page_types"]["rt"]["RT_cover"] = "Synthetic competing head"
                else:
                    edit = ProfileEditor.create(self.bundle, "Synthetic other default")
                store.managed_save(edit.snapshot(), expected_head=None, expected_default=None,
                                   use_for_new_cases=change == "default")
                before = w._state(), tree_bytes(self.root), w.expected_head, w.expected_default
                dialog.response("reset")
                drain()
                self.assertEqual((w._state(), tree_bytes(self.root), w.expected_head, w.expected_default), before)
                self.assertIn("changed elsewhere", w.message.get_text())
                w.on_saved.assert_not_called()
                w.destroy()
                self.root = self.root / "next"

    def test_bundle_changes_during_confirmation_requires_new_confirmation(self):
        w, store = self.window()
        dialog = w._reset()
        edit = ProfileEditor(self.bundle)
        edit.resources["minutes"] += " Synthetic bundle update"
        changed = edit.snapshot()
        before = w._state(), tree_bytes(self.root)
        with patch.object(api, "bundled_profile_for_identity", return_value=changed):
            dialog.response("reset")
        self.assertEqual((w._state(), tree_bytes(self.root)), before)
        self.assertIn("changed during confirmation", w.message.get_text())
        self.assertIsNone(w.reset_dialog)
        self.confirm(w)
        self.assertEqual(w.editor.snapshot().files, self.bundle.files)

    def test_case_storage_or_active_work_guard_rechecked_on_response_and_under_lock(self):
        w, store = self.window()
        # The first locked attempt may create its stable machine-local lock;
        # that is not profile publication and is intentionally never deleted.
        with store._locked():
            pass
        for label in ("case", "storage", "active work", "locked guard"):
            with self.subTest(label=label):
                dialog = w._reset()
                before = w._state(), tree_bytes(self.root)
                import itertools
                w.can_modify = Mock(side_effect=itertools.chain([True, True], itertools.repeat(False)) if label == "locked guard" else None,
                                    return_value=False)
                dialog.response("reset")
                self.assertEqual((w._state(), tree_bytes(self.root)), before)
                self.assertIn("Work is active", w.message.get_text())
                w.on_saved.assert_not_called()
                w.can_modify = lambda: True

    def test_validation_and_write_failure_preserve_invalid_draft(self):
        w, store = self.window()
        w.editor.resources["classification_tasks"]["page_types"]["ct"]["CT_cover"] = ""
        for target in ("preview", "write"):
            before = copy.deepcopy(w._state()), w.editor, w.expected_head, w.expected_default
            registry_before = store.read_registry()
            context = patch.object(w, "preview", side_effect=ValueError("synthetic validation")) if target == "preview" else patch("recordprep.profile_store._atomic_json", side_effect=OSError("synthetic publication"))
            with context:
                self.confirm(w)
            self.assertEqual((w._state(), w.editor, w.expected_head, w.expected_default), before)
            self.assertEqual(store.read_registry(), registry_before)
            self.assertIn("could not be validated or saved", w.message.get_text())
            w.on_saved.assert_not_called()

    def test_saved_but_display_or_selection_refresh_failed_is_not_rollback(self):
        for target in ("_adopt_reset", "on_saved"):
            with self.subTest(target=target):
                w, store = self.window()
                with patch.object(w, target, side_effect=RuntimeError("synthetic refresh")):
                    self.confirm(w)
                self.assertEqual(store.load_profile_snapshot(self.bundle.ref).files, self.bundle.files)
                self.assertTrue(w.saved_apply_failed)
                w._refresh_guard()
                self.assertIn("saved, refresh required", w.message.get_text())
                self.assertFalse(w.body.get_sensitive())
                self.assertFalse(w._save())
                if target == "_adopt_reset":
                    w.on_saved.assert_called_once_with(self.bundle.ref)
                w.destroy()
                self.root = self.root / "next"

    def test_older_schema_reset_preserves_historical_bytes(self):
        from test_practice_profiles import historical_snapshot
        w, store = self.window()
        old = historical_snapshot(self.bundle, 2)
        store.managed_save(old, expected_head=None, expected_default=None, use_for_new_cases=True)
        before = tree_bytes(store.data_root)
        w.editor = editable_profile(old)
        w.expected_head = old.ref.content_sha256
        w.expected_default = asdict(old.ref)
        self.confirm(w)
        self.assertEqual(w.editor.snapshot().files, self.bundle.files)
        self.assertEqual(store.read_registry()["default"], asdict(self.bundle.ref))
        self.assertEqual(store.load_profile_snapshot(old.ref).files, old.files)
        after = tree_bytes(store.data_root)
        self.assertTrue(all(after[k] == v for k, v in before.items()))

    def test_reset_does_not_write_model_settings_or_case_outputs(self):
        w, store = self.window()
        case = self.root / "case"
        case.mkdir()
        (case / "generated.txt").write_text("Synthetic existing output")
        model = self.root / "model-settings.json"
        model.write_text('{"synthetic_model":"unchanged"}')
        before = tree_bytes(case), model.read_bytes(), model.stat().st_mtime_ns
        self.confirm(w)
        self.assertEqual((tree_bytes(case), model.read_bytes(), model.stat().st_mtime_ns), before)
        self.assertEqual(store.load_profile_snapshot(self.bundle.ref).files, self.bundle.files)

    def test_keyboard_activatable_row_and_blocked_guard(self):
        w, _ = self.window()
        # ListBox rows use arrow navigation; Enter must activate the suffix
        # even when GTK focuses the row rather than tabbing into its button.
        self.assertIs(w.reset_row.get_activatable_widget(), w.reset_button)
        self.assertTrue(w.reset_row.get_activatable())
        w.reset_row.grab_focus()
        w.reset_row.activate()
        # Gtk.Button's keyboard activation includes its short press animation.
        drain()
        drain()
        self.assertIsNotNone(w.reset_dialog)
        w.reset_dialog.response("cancel")
        drain()
        w.can_modify = lambda: False
        w._refresh_guard()
        self.assertFalse(w.reset_button.is_sensitive())
        self.assertIsNone(w._reset())

    def test_future_identity_gets_same_action_and_corruption_never_writes(self):
        w, store = self.window()
        future = ProfileEditor.create(self.bundle, "Future synthetic specialty").snapshot()
        w.editor = ProfileEditor(future)
        with patch.object(api, "bundled_profile_for_identity", return_value=future):
            w._render()
            self.assertIsNotNone(w.reset_button)
            self.confirm(w)
        self.assertEqual(store.load_profile_snapshot(future.ref).files, future.files)
        before = w._state(), tree_bytes(self.root)
        with patch.object(api, "bundled_profile_for_identity", side_effect=ProfileError("invalid_bundled_profile", "profiles")):
            self.assertIsNone(w._reset())
        self.assertEqual((w._state(), tree_bytes(self.root)), before)

    def test_custom_copy_has_no_button_or_reset_target(self):
        w, store = self.window()
        w.editor = ProfileEditor.create(self.bundle, "Synthetic custom copy")
        w._render()
        self.assertIsNone(w.reset_button)
        self.assertIsNone(w._reset())
        self.assertFalse(store.registry_path.exists())


if __name__ == "__main__":
    unittest.main()
