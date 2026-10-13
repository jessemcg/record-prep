"""Combined OCR settings page: real GTK, disposable settings, no server/model calls."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
TEMP = tempfile.TemporaryDirectory(prefix="recordprep-ocr-settings-")
ROOT = Path(TEMP.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk
from recordprep.ui import main_window as ui

Adw.init()
app = Adw.Application(application_id="org.synthetic.RecordPrepOCRSettings")
app.register(None)


def drain():
    until = time.monotonic() + 0.3
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


with patch.object(ui, "CONFIG_FILE", ROOT / "config.json"), \
        patch.object(ui.SettingsWindow, "_load_pi_models"), \
        patch.object(ui, "current_project_pi_model", return_value=None), \
        patch.object(ui, "current_project_pi_thinking_level", return_value=None), \
        patch.object(ui, "resolve_pi_agent_argv", return_value=["synthetic-pi"]), \
        patch.object(ui, "save_project_pi_model"), \
        patch.object(ui, "save_project_pi_thinking_level"), \
        patch.object(ui, "_generate_text_files_with_local_ocr") as ocr:
    window = ui.SettingsWindow(app)
    window.present()
    drain()
    assert set(window._settings_destination_labels) == {"ocr", "classify-basic", "summarize", "pi"}
    assert window._settings_group_rows["ocr"].get_title() == "OCR"
    assert window._prompt_stack.get_visible_child_name() == "ocr"
    assert len(window._settings_group_rows) == 4
    for group_id, title, destinations in ui.SETTINGS_NAV_GROUPS:
        nav_row = window._settings_group_rows[group_id]
        assert isinstance(nav_row, Adw.ActionRow) and not isinstance(nav_row, Adw.ExpanderRow)
        assert nav_row.get_parent() is window._prompt_list
        assert nav_row.get_title() == title and not nav_row.get_subtitle()
        nav_row.emit("activated")
        drain()
        key = destinations[0][0]
        assert window._prompt_stack.get_visible_child_name() == key
        assert window._active_settings_key == key
        assert all(marker.get_visible() == (destination == key)
                   for destination, marker in window._settings_destination_markers.items())
    window._settings_group_rows["ocr"].emit("activated")
    drain()
    page = window._prompt_stack.get_visible_child()
    row = window._text_source_row
    widgets = window._local_ocr_widgets
    assert row.get_ancestor(Gtk.ScrolledWindow) is page
    assert widgets.server_url_row.get_ancestor(Gtk.ScrolledWindow) is page
    valid_source, source_bounds = row.compute_bounds(page)
    valid_server, server_bounds = widgets.server_url_row.compute_bounds(page)
    assert valid_source and valid_server and source_bounds.get_y() < server_bounds.get_y()
    row.set_selected(window._text_source_values.index(ui.TEXT_SOURCE_LOCAL_OCR))
    widgets.server_url_row.set_text("http://localhost:12345/v1/chat/completions")
    widgets.model_row.set_text("synthetic-ocr-model")
    widgets.workers_row.set_text("3")
    widgets.slots_row.set_text("2")
    widgets.start_command_buffer.set_text("synthetic-ocr --slots {slots}")
    window._settings_group_rows["classify"].emit("activated")
    window._settings_group_rows["ocr"].emit("activated")
    assert widgets.model_row.get_text() == "synthetic-ocr-model"
    window._save_settings()
    assert ui.load_text_source_setting() == ui.TEXT_SOURCE_LOCAL_OCR
    saved = ui.load_local_ocr_settings()
    assert saved["model_id"] == "synthetic-ocr-model"
    assert str(saved["workers"]) == "3" and str(saved["slots"]) == "2"
    assert saved["server_url"] == "http://localhost:12345/v1/chat/completions"
    assert saved["start_command"] == "synthetic-ocr --slots {slots}"
    window = ui.SettingsWindow(app)
    assert window._text_source_values[window._text_source_row.get_selected()] == ui.TEXT_SOURCE_LOCAL_OCR
    assert window._local_ocr_widgets.model_row.get_text() == "synthetic-ocr-model"
    window._text_source_row.set_selected(window._text_source_values.index(ui.TEXT_SOURCE_EMBEDDED))
    window._save_settings()
    assert ui.load_text_source_setting() == ui.TEXT_SOURCE_EMBEDDED
    assert ui.load_local_ocr_settings() == saved
    ocr.assert_not_called()
    print("COMBINED OCR SETTINGS GTK ACCEPTANCE PASSED", flush=True)
    if os.environ.get("OCR_SETTINGS_HOLD"):
        window = ui.SettingsWindow(app)
        window.set_title("Synthetic RecordPrep — combined OCR settings")
        window.present()
        loop = GLib.MainLoop()
        window.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
TEMP.cleanup()
