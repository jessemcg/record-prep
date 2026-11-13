"""Native main-workspace checks; use a disposable checkout and isolated HOME/XDG."""
import tempfile
import threading
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk
from recordprep.ui import main_window as ui


def drain():
    until = time.monotonic() + 0.15
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.005)


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Adw.Application(application_id="org.synthetic.RecordPrepWorkspaceTests")
        cls.app.register(None)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        config = Path(self.temp.name) / "settings.json"
        config.write_text("{}")
        patcher = patch.object(ui, "CONFIG_FILE", config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.window = ui.RecordPrepWindow(self.app)
        self.addCleanup(self.window.destroy)

    def test_steps_precede_compact_activity_and_footer_is_fixed(self):
        win = self.window
        self.assertIs(win.step_list.get_next_sibling(), win._activity_section)
        self.assertFalse(win._activity_details.get_reveal_child())
        self.assertEqual(win._activity_details_toggle.get_label(), "Show details")
        self.assertFalse(win._run_footer.is_ancestor(win._workspace_scroller))
        self.assertTrue(win.run_all_button.has_css_class("suggested-action"))
        self.assertTrue(win.resume_button.has_css_class("suggested-action"))

    def test_work_errors_and_interactive_terminal_reveal_details(self):
        win = self.window
        win._start_step(win.step_one_row)
        self.assertTrue(win._activity_details.get_reveal_child())
        win._activity_details_toggle.set_active(False)
        win._append_log_message("Synthetic error", "ERROR")
        self.assertTrue(win._activity_details.get_reveal_child())
        win._activity_details_toggle.set_active(False)
        win._pi_terminal_active = True
        win._reveal_activity()
        win._activity_details_toggle.set_active(False)
        self.assertTrue(win._activity_details.get_reveal_child())
        win._pi_terminal_active = False
        win._activity_details_toggle.set_active(False)
        self.assertFalse(win._activity_details.get_reveal_child())

    def test_offline_terminal_child_reveals_and_preserves_output_on_exit(self):
        win = self.window
        if ui.Vte is None:
            self.skipTest("GTK4 VTE unavailable")
        runner = Path(self.temp.name) / "fake_runner.py"
        runner.write_text("import time\nprint('Synthetic terminal output', flush=True)\ntime.sleep(0.3)\n")
        win.present()
        drain()
        done = threading.Event()
        with patch.object(ui, "PI_SKILL_RUNNER", runner):
            win._spawn_pi_skill_terminal(Path(self.temp.name), [sys.executable],
                                        "detect_transcript_layout", "Synthetic detection", done)
            self.assertTrue(win._activity_details.get_reveal_child())
            until = time.monotonic() + 5
            while not done.is_set() and time.monotonic() < until:
                drain()
        self.assertTrue(done.is_set())
        self.assertIsNone(win._pi_terminal_spawn_error)
        self.assertEqual(win._pi_terminal_exit_status, 0)
        self.assertFalse(win._pi_terminal_active)
        self.assertTrue(win._activity_details.get_reveal_child())

    def test_spinner_lives_in_activity_and_only_shows_while_working(self):
        win = self.window
        header = win._activity_section.get_first_child()
        self.assertIs(win.status_spinner.get_parent(), header)
        self.assertIs(header.get_first_child(), win.status_spinner)
        self.assertFalse(win.status_spinner.get_visible())
        win._set_status("Synthetic work", True)
        self.assertTrue(win.status_spinner.get_visible())
        self.assertTrue(win.status_spinner.get_spinning())
        self.assertFalse(win._activity_details.get_reveal_child())
        win._set_status(ui.APPLICATION_NAME, False)
        self.assertFalse(win.status_spinner.get_visible())
        self.assertFalse(win.status_spinner.get_spinning())

    def test_clear_collapses_details(self):
        win = self.window
        win._reveal_activity()
        win.on_clear_case(None)
        self.assertFalse(win._activity_details.get_reveal_child())

    def test_run_controls_keep_their_running_state(self):
        win = self.window
        win.selected_pdfs = [Path(self.temp.name) / "synthetic.pdf"]
        win._sync_pipeline_controls()
        self.assertTrue(win.run_all_button.get_sensitive())
        win._pipeline_running = True
        win._sync_pipeline_controls()
        self.assertFalse(win.run_all_button.get_visible())
        self.assertTrue(win.stop_button.get_visible())
        self.assertFalse(win._run_until_dropdown.get_sensitive())

    def test_run_target_labels_have_readable_minimum_widths(self):
        dropdown = self.window._run_until_dropdown
        for factory, width in ((dropdown.get_factory(), 22),
                               (dropdown.get_list_factory(), 32)):
            item = Gtk.ListItem()
            factory.emit("setup", item)
            self.assertEqual(item.get_child().get_width_chars(), width)
            minimum, natural, *_ = item.get_child().measure(Gtk.Orientation.HORIZONTAL, -1)
            self.assertGreater(minimum, 100)
            self.assertGreaterEqual(natural, minimum)

    def test_responsive_footer(self):
        win = self.window
        win.set_default_size(900, 760)
        win.present()
        drain()
        # Native compositors may tile/maximize windows; assert at actual allocation.
        expected = Gtk.Orientation.VERTICAL if win.get_width() <= 650 else Gtk.Orientation.HORIZONTAL
        self.assertEqual(win._run_footer.get_orientation(), expected)
        self.assertGreater(win._run_footer.get_height(), 0)


if __name__ == "__main__":
    unittest.main()
