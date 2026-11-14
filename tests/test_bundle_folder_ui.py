"""Native folder-action tests; run only in an isolated disposable checkout."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk
from recordprep.ui import main_window as ui


class BundleFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(application_id="org.synthetic.RecordPrepFolderTests")
        cls.app.register(None)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = self.base / "settings.json"
        self.config.write_text("{}")
        patcher = patch.object(ui, "CONFIG_FILE", self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.win = ui.RecordPrepWindow(self.app)
        self.addCleanup(self.win.destroy)
        feedback = patch.object(self.win, "show_toast")
        self.feedback = feedback.start()
        self.addCleanup(feedback.stop)
        launch = patch.object(ui.Gtk.FileLauncher, "new")
        self.launch = launch.start()
        self.addCleanup(launch.stop)
        self.launcher = self.launch.return_value

    def bundle(self, name="Synthetic case"):
        root = self.base / name / "case_bundle"
        root.mkdir(parents=True)
        (root / "sentinel.txt").write_text("Synthetic only\n")
        return root

    def select(self, root):
        # The real resolver derives case_bundle from a selected PDF's parent.
        self.win.selected_pdfs = [root.parent / "Synthetic.pdf"]
        self.win._update_source_summary()

    def activate(self):
        self.win._bundle_folder_button.emit("clicked")

    def assert_destination(self, root):
        self.assertEqual(self.launch.call_args.args[0].get_path(), str(root))
        self.assertIs(self.launcher.launch.call_args.args[0], self.win)

    def test_empty_and_existing_bundle_presentation(self):
        button = self.win._bundle_folder_button
        self.assertFalse(button.get_visible())
        self.select(self.bundle())
        self.assertTrue(button.get_visible())
        self.assertEqual(button.get_icon_name(), "folder-open-symbolic")
        self.assertTrue(button.has_css_class("flat"))
        self.assertEqual(button.get_valign(), Gtk.Align.CENTER)
        self.assertEqual(button.get_tooltip_text(), "Open bundle folder")
        self.assertFalse(self.win._source_row.get_activatable())
        self.activate()
        self.assert_destination(self.win._resolve_case_root())

    def test_restored_context_without_prepared_metadata(self):
        root = self.bundle()
        self.config.write_text(ui.json.dumps({"case_root_dir": str(root.parent)}))
        self.win.destroy()
        self.win = ui.RecordPrepWindow(self.app)
        self.addCleanup(self.win.destroy)
        self.assertEqual(self.win._resolve_case_root(), root)
        self.assertTrue(self.win._bundle_folder_button.get_visible())
        self.assertFalse((root / "case_name.txt").exists())

    def test_prospective_created_and_different_parent_pdfs(self):
        root = self.base / "new" / "case_bundle"
        self.select(root)
        self.assertFalse(self.win._bundle_folder_button.get_visible())
        root.mkdir(parents=True)
        # Create files already queues _load_rt_ct_split on the main thread.
        self.win._load_rt_ct_split()
        self.assertTrue(self.win._bundle_folder_button.get_visible())
        self.win.selected_pdfs.append(self.base / "other" / "other.pdf")
        self.win._sync_pipeline_controls()
        self.assertFalse(self.win._bundle_folder_button.get_visible())
        self.activate()
        self.launch.assert_not_called()

    def test_switch_and_clear_do_not_launch_stale_selection(self):
        first, second = self.bundle("one"), self.bundle("two")
        self.select(first)
        self.select(second)
        self.activate()
        self.assert_destination(second)
        self.launch.reset_mock()
        self.win.on_clear_case(None)
        self.assertFalse(self.win._bundle_folder_button.get_visible())
        self.activate()
        self.launch.assert_not_called()

    def test_running_and_interactive_leave_browsing_enabled(self):
        self.select(self.bundle())
        for running, interactive in ((True, False), (False, True), (True, True)):
            self.win._pipeline_running = running
            self.win._pi_terminal_active = interactive
            self.win._sync_pipeline_controls()
            self.assertTrue(self.win._bundle_folder_button.get_sensitive())
            self.assertFalse(self.win.file_button.get_sensitive())
            self.assertFalse(self.win.case_bundle_button.get_sensitive())
            self.assertFalse(self.win._layout_review_button.get_sensitive())
            self.activate()
        self.win._pipeline_running = self.win._pi_terminal_active = False

    def test_deleted_or_replaced_directory_is_not_recreated(self):
        for replacement in (False, True):
            root = self.bundle(str(replacement))
            self.select(root)
            (root / "sentinel.txt").unlink()
            root.rmdir()
            if replacement:
                root.write_text("not a directory")
            self.activate()
            self.launch.assert_not_called()
            self.assertFalse(self.win._bundle_folder_button.get_visible())
            self.feedback.assert_called_with("The bundle folder is no longer available.")
            self.assertEqual(root.is_file(), replacement)

    def test_filesystem_errors_hide_action(self):
        self.select(self.bundle())
        with patch.object(Path, "is_dir", side_effect=PermissionError("private path")):
            self.win._refresh_bundle_folder()
            self.assertFalse(self.win._bundle_folder_button.get_visible())
            self.activate()
        self.launch.assert_not_called()

    def test_special_path_and_async_results_preserve_state_and_contents(self):
        root = self.bundle("Spaces é 日本 # 100%")
        self.select(root)
        sentinel = root / "sentinel.txt"
        before = hashlib.sha256(sentinel.read_bytes()).digest()
        selected = list(self.win.selected_pdfs)
        errors = [None,
                  GLib.Error.new_literal(Gio.io_error_quark(), "private path", Gio.IOErrorEnum.CANCELLED),
                  GLib.Error.new_literal(Gtk.dialog_error_quark(), "private path", Gtk.DialogError.DISMISSED),
                  GLib.Error.new_literal(Gtk.dialog_error_quark(), "private path", Gtk.DialogError.CANCELLED),
                  GLib.Error.new_literal(Gio.io_error_quark(), "private path", Gio.IOErrorEnum.FAILED)]
        for error in errors:
            self.feedback.reset_mock()
            self.activate()
            self.assert_destination(root)
            callback = self.launcher.launch.call_args.args[2]
            self.launcher.launch_finish.side_effect = error
            callback(self.launcher, Mock())
            if error is errors[-1]:
                self.feedback.assert_called_once_with("Could not open the bundle folder.")
            else:
                self.feedback.assert_not_called()
            self.assertEqual(self.win.selected_pdfs, selected)
            self.assertFalse(self.win._pipeline_running)
            self.assertEqual(hashlib.sha256(sentinel.read_bytes()).digest(), before)

    def test_late_completion_does_not_restore_selection_and_disposed_owner_is_silent(self):
        self.select(self.bundle("old"))
        self.activate()
        callback = self.launcher.launch.call_args.args[2]
        new = self.bundle("new")
        self.select(new)
        callback(self.launcher, Mock())
        self.assertEqual(self.win._resolve_case_root(), new)
        self.win.destroy()
        self.launcher.launch_finish.side_effect = GLib.Error.new_literal(
            Gio.io_error_quark(), "private path", Gio.IOErrorEnum.FAILED)
        callback(self.launcher, Mock())
        self.launcher.launch_finish.assert_called()
        self.feedback.assert_not_called()

    def test_synchronous_launch_error_is_sanitized(self):
        self.select(self.bundle())
        self.launcher.launch.side_effect = GLib.Error.new_literal(
            Gio.io_error_quark(), "private path", Gio.IOErrorEnum.FAILED)
        self.activate()
        self.feedback.assert_called_once_with("Could not open the bundle folder.")

    def test_row_with_both_actions_fits_420_pixels(self):
        # Native minimum measurement is independent of compositor width policies;
        # full-window 420px allocation is also checked in desktop acceptance.
        row = self.win._source_row
        row.set_title("A long synthetic case title that should wrap naturally")
        self.win._layout_review_button.set_visible(True)
        self.win._bundle_folder_button.set_visible(True)
        minimum, *_ = row.measure(Gtk.Orientation.HORIZONTAL, -1)
        self.assertLessEqual(minimum, 420)
        self.assertIs(self.win._layout_review_button.get_next_sibling(),
                      self.win._bundle_folder_button)


if __name__ == "__main__":
    unittest.main()
