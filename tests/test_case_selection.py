"""Synthetic case metadata permissions and non-destructive clear-selection tests."""
import json
import os
import stat
import tempfile
import threading
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import case_profiles as bindings
from recordprep import practice_profiles as api
from recordprep import profile_integration as integration
from recordprep.profile_contract import ProfileError
from recordprep.profile_store import ProfileStore
from recordprep.ui import main_window as ui


class CaseBindingPermissionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "case_bundle"
        self.root.mkdir()
        self.store = ProfileStore("recordprep", config_root=self.base / "config", data_root=self.base / "data")
        self.general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
        self.dependency = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft
        self.store.accept_profile(self.general, expected_previous_digest=None)
        self.directory = self.root / ".recordprep"
        self.directory.mkdir()
        self.selection = self.directory / "practice-profile.json"
        # A synchronized pin need not have its old snapshot in the local store.
        self.selection.write_text(json.dumps({"schema_version": 1, "profile_ref": asdict(self.dependency.ref)}))
        self.lock = self.directory / ".practice-profile.lock"
        self.lock.touch()
        context = patch("recordprep.case_profiles.profile_store", return_value=self.store)
        context.start()
        self.addCleanup(context.stop)

    def test_synced_modes_support_selection_and_publication_without_chmod(self):
        for directory_mode, file_mode in ((0o755, 0o644), (0o775, 0o664)):
            with self.subTest(directory_mode=oct(directory_mode)):
                self.directory.chmod(directory_mode)
                self.selection.chmod(file_mode)
                self.lock.chmod(file_mode)
                previous = self.store.read_registry()["default"]
                previous = api.ProfileRef.from_dict(previous) if previous else None
                before = self.selection.read_bytes()
                bindings.apply_case_profile(self.root, self.general.ref, expected_previous=previous, store=self.store)
                self.assertEqual(self.selection.read_bytes(), before)
                self.assertEqual(bindings.read_case_profile_ref(self.root), self.general.ref)
                with bindings.case_profile_publication(self.root, self.general.ref):
                    pass
                self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), directory_mode)
                self.assertEqual(stat.S_IMODE(self.lock.stat().st_mode), file_mode)

    def test_private_profile_store_stays_owner_only(self):
        self.store.config_root.chmod(0o755)
        with self.assertRaises(ProfileError) as error:
            self.store.read_registry()
        self.assertEqual(error.exception.issue.code, "store_permissions")

    def test_unsafe_case_paths_and_files_are_rejected(self):
        # Historical-reader checks remain strict, but never authorize generation.
        read = bindings.read_historical_case_profile_ref
        self.directory.chmod(0o777)
        with self.assertRaises(ProfileError):
            read(self.root)
        self.directory.chmod(0o755)
        for mode in (0o666, 0o744):
            self.selection.chmod(mode)
            with self.assertRaises(ProfileError):
                read(self.root)
        self.selection.chmod(0o644)
        alias = self.base / "alias"
        os.link(self.selection, alias)
        with self.assertRaises(ProfileError):
            read(self.root)
        alias.unlink()
        moved = self.base / "moved"
        self.selection.rename(moved)
        self.selection.symlink_to(moved)
        with self.assertRaises(ProfileError):
            read(self.root)
        self.selection.unlink()
        moved.rename(self.selection)
        self.lock.unlink()
        self.lock.symlink_to(self.selection)
        with self.assertRaises((OSError, ProfileError)):
            with bindings.case_profile_publication(self.root, self.general.ref):
                self.fail("Unsafe publication lock")
        self.assertEqual(read(self.root), self.dependency.ref)

    def test_foreign_ownership_and_redirected_metadata_are_rejected(self):
        with patch.object(bindings.os, "getuid", return_value=os.getuid() + 1), self.assertRaises(ProfileError):
            bindings.read_historical_case_profile_ref(self.root)
        actual_lstat = Path.lstat
        def foreign_file(path, *args, **kwargs):
            info = actual_lstat(path, *args, **kwargs)
            if path == self.selection:
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink, st_uid=os.getuid() + 1)
            return info
        with patch.object(Path, "lstat", foreign_file), self.assertRaises(ProfileError):
            bindings.read_historical_case_profile_ref(self.root)
        relocated = self.base / "relocated"
        self.directory.rename(relocated)
        self.directory.symlink_to(relocated, target_is_directory=True)
        with self.assertRaises(ProfileError):
            bindings.read_historical_case_profile_ref(self.root)

    def test_nonregular_and_hardlinked_locks_are_rejected(self):
        alias = self.base / "lock-alias"
        os.link(self.lock, alias)
        with self.assertRaises(ProfileError):
            with bindings.case_profile_publication(self.root, self.general.ref):
                self.fail("Hardlinked publication lock")
        alias.unlink()
        self.lock.unlink()
        os.mkfifo(self.lock)
        with self.assertRaises(ProfileError):
            with bindings.case_profile_publication(self.root, self.general.ref):
                self.fail("Nonregular publication lock")
        self.assertEqual(bindings.read_historical_case_profile_ref(self.root), self.dependency.ref)

    def test_selection_keeps_compare_and_swap_protection(self):
        bindings.apply_case_profile(self.root, self.general.ref, expected_previous=None, store=self.store)
        with self.assertRaises(ProfileError):
            bindings.apply_case_profile(self.root, self.general.ref, expected_previous=None, store=self.store)
        self.assertEqual(bindings.read_case_profile_ref(self.root), self.general.ref)
        self.assertEqual(bindings.read_historical_case_profile_ref(self.root), self.dependency.ref)


class ClearCaseTests(unittest.TestCase):
    def owner(self):
        return SimpleNamespace(_pipeline_running=False, _pi_terminal_active=False, _toc_editor_window=None,
                               _case_generation=7, selected_pdfs=[Path("/synthetic.pdf")],
                               _pending_preparation_profile=(Path("/old"), object()), _rt_ct_split_pending=42,
                               _rt_ct_split_mode_pending="split", _bundle_reset_required=True,
                               _active_bundle_root="/old", _bundle_identity_warning_roots={"/old"},
                               _active_step_id="infer_case", _run_completion_message="old", _run_pause_message="old",
                               _pi_terminal_sequence_started=True, _stop_event=threading.Event(),
                               selected_label=Mock(), _load_rt_ct_split=Mock(), _update_source_summary=Mock(),
                               _source_row=Mock(), _reset_step_statuses=Mock(), _stop_status=Mock(),
                               _set_activity_status_text=Mock(), _log_buffer=Mock(), _activity_terminal=Mock(), show_toast=Mock())

    def test_clear_forgets_selection_but_preserves_files_and_other_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bundle = base / "case_bundle"
            bundle.mkdir()
            (bundle / "case_name.txt").write_text("Synthetic_case")
            pdf = base / "synthetic.pdf"
            pdf.write_bytes(b"synthetic PDF sentinel")
            config = base / "config.json"
            data = {"case_name": "Synthetic_case", "case_root_dir": str(base), "selected_pdfs": [str(pdf)],
                    "classifier_api_key": "SYNTHETIC", "case_name_prompt": "Old private prompt", "unrelated": [1, 2],
                    "rt_ct_split_page": 77}
            config.write_text(json.dumps(data))
            before = {path: path.read_bytes() for path in (pdf, bundle / "case_name.txt")}
            owner = self.owner()
            with patch.object(ui, "CONFIG_FILE", config):
                ui.RecordPrepWindow.on_clear_case(owner, None)
                self.assertEqual(ui.load_case_context(), ("", None))
                self.assertEqual(ui.load_selected_pdfs(), [])
                self.assertIsNone(ui.RecordPrepWindow._resolve_case_root(owner))
            saved = json.loads(config.read_text())
            expected = data | {"case_name": "", "case_root_dir": "", "selected_pdfs": []}
            self.assertEqual(saved, expected)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertEqual(owner._case_generation, 8)
            self.assertIsNone(owner._pending_preparation_profile)
            self.assertIsNone(owner._rt_ct_split_pending)
            self.assertFalse(owner._bundle_reset_required)
            owner._reset_step_statuses.assert_called_once()
            owner._activity_terminal.reset.assert_called_once_with(True, True)

    def test_clear_blocks_active_work_and_open_toc_editor(self):
        for key in ("_pipeline_running", "_pi_terminal_active", "_toc_editor_window"):
            owner = self.owner()
            setattr(owner, key, True)
            with patch.object(ui, "clear_case_context") as clear:
                ui.RecordPrepWindow.on_clear_case(owner, None)
                clear.assert_not_called()
            self.assertEqual(owner._case_generation, 7)
            self.assertTrue(owner.selected_pdfs)

    def test_failed_clear_keeps_selection_and_corrupt_settings(self):
        owner = self.owner()
        with patch.object(ui, "clear_case_context", side_effect=OSError("synthetic")):
            ui.RecordPrepWindow.on_clear_case(owner, None)
        self.assertEqual(owner._case_generation, 7)
        self.assertTrue(owner.selected_pdfs)
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.json"
            config.write_bytes(b"broken json")
            with patch.object(ui, "CONFIG_FILE", config), self.assertRaises(ValueError):
                ui.clear_case_context()
            self.assertEqual(config.read_bytes(), b"broken json")

    def test_old_file_dialog_callbacks_cannot_restore_cleared_case(self):
        owner = self.owner()
        dialog = Mock()
        ui.RecordPrepWindow._on_files_chosen(owner, dialog, None, generation=6)
        ui.RecordPrepWindow._on_case_bundle_chosen(owner, dialog, None, generation=6)
        dialog.open_multiple_finish.assert_not_called()
        dialog.select_folder_finish.assert_not_called()
        self.assertEqual(owner._case_generation, 7)

    def test_pdf_selection_scopes_pending_choice_and_handles_multiple_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for selection_kind in ("new", "existing", "multiple-directories"):
                with self.subTest(selection_kind=selection_kind):
                    base = root / selection_kind
                    base.mkdir()
                    if selection_kind == "existing":
                        (base / "case_bundle").mkdir()
                    paths = [base / "first.pdf"]
                    if selection_kind == "multiple-directories":
                        paths.append(root / "second.pdf")
                    files = ui.Gio.ListStore.new(ui.Gio.File)
                    for path in paths:
                        files.append(ui.Gio.File.new_for_path(str(path)))
                    dialog = Mock()
                    dialog.open_multiple_finish.return_value = files
                    owner = self.owner()
                    owner.selected_pdfs = []
                    ref = object()
                    owner._pending_preparation_profile = (None, ref)
                    owner._update_toc_button = Mock()
                    owner._refresh_step_statuses_from_artifacts = Mock()
                    with patch.object(ui, "save_selected_pdfs"), patch.object(ui, "_bundle_inputs_changed", return_value=False):
                        ui.RecordPrepWindow._on_files_chosen(owner, dialog, None, generation=7)
                    self.assertEqual(owner._case_generation, 8)
                    self.assertEqual(owner.selected_pdfs, paths)
                    expected = (base / "case_bundle", ref) if selection_kind == "new" else None
                    self.assertEqual(owner._pending_preparation_profile, expected)

    def test_selection_callback_never_binds_case_and_drafts_expire_on_clear(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProfileStore("recordprep", config_root=root / "config", data_root=root / "data")
            owner = SimpleNamespace(_resolve_case_root=lambda: None, _pipeline_running=False, _case_generation=0)
            captured = {}
            def manager(*args, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace()
            general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
            with patch("recordprep.profile_manager_ui.ProfileManagerWindow", side_effect=manager), \
                    patch.object(api, "profile_store", return_value=store), \
                    patch.object(api, "default_profile_candidate", return_value=general), \
                    patch.object(integration, "update_indicator"):
                integration.open_manager(owner, Path.cwd() / ".pi")
                self.assertFalse(captured["has_case"])
                captured["on_select"](general.ref)
                self.assertIsNone(integration.pending_profile(owner, None))
                self.assertIsNone(integration.pending_profile(owner, root / "new/case_bundle"))
                self.assertFalse(list(root.iterdir()))
                captured["on_deleted"](SimpleNamespace(specialty_id="unrelated-profile"))
                self.assertIsNone(integration.pending_profile(owner, None))
                captured["on_deleted"](general.ref)
                self.assertIsNone(integration.pending_profile(owner, None))
                captured["on_select"](general.ref)
                owner._case_generation += 1
                self.assertFalse(captured["can_modify"]())
                captured["on_deleted"](general.ref)
                self.assertIsNone(integration.pending_profile(owner, None))
                with self.assertRaises(ProfileError):
                    captured["on_select"](general.ref)


if __name__ == "__main__":
    unittest.main()
