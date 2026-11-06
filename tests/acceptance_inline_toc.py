"""Real GTK inline TOC action acceptance; temporary settings/bundle, no model calls."""
import os
from pathlib import Path
import sys
import tempfile
import time

TEMP = tempfile.TemporaryDirectory(prefix="recordprep-inline-toc-")
ROOT = Path(TEMP.name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
            "XDG_CACHE_HOME", "RECORDPREP_CONFIG_DIR"):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.pop("RECORDPREP_PROFILE_DIR", None)

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk
from recordprep.ui.main_window import RecordPrepApp

app = RecordPrepApp()
app.set_application_id("org.synthetic.RecordPrepInlineToc")
errors = []


def drain():
    end = time.monotonic() + .2
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()


def check():
    try:
        window = app.get_active_window()
        window.set_title("Synthetic RecordPrep — inline TOC acceptance")
        window.set_default_size(1100, 1100)
        bundle = ROOT / "bundle"
        (bundle / "artifacts").mkdir(parents=True)
        window._resolve_case_root = lambda: bundle
        button = window._edit_toc_button
        assert button.get_label() == "Modify TOC"
        assert button.has_css_class("flat")
        assert button.get_valign() == Gtk.Align.CENTER
        assert button.is_ancestor(window.step_correct_toc_row)
        buttons = [widget for widget in descendants(window)
                   if isinstance(widget, Gtk.Button)
                   and widget.get_label() in ("Modify TOC", "Edit TOC")]
        assert buttons == [button], buttons
        window._open_phase_for_step("correct_toc")
        window._update_toc_button()
        assert button.get_visible() and not button.get_sensitive()
        toc = bundle / "artifacts/toc.txt"
        toc.write_text("Synthetic hearing — file page 1\n")
        before = (toc.read_bytes(), toc.stat().st_mtime_ns)
        window._update_toc_button()
        assert button.get_visible() and button.get_sensitive()
        window._pipeline_running = True
        window._update_toc_button()
        assert button.get_visible() and not button.get_sensitive()
        window._pipeline_running = False
        window._update_toc_button()
        button.emit("clicked")
        drain()
        editor = window._toc_editor_window
        assert editor is not None and editor.get_visible()
        buffer = editor._text_view.get_buffer()
        assert buffer.get_text(*buffer.get_bounds(), True) == toc.read_text()
        # Opening twice retains the editor and never writes the TOC.
        button.emit("clicked")
        assert window._toc_editor_window is editor
        editor.close()
        drain()
        assert window._toc_editor_window is None
        assert (toc.read_bytes(), toc.stat().st_mtime_ns) == before
        # Existing save flow still works, using fictional data only.
        button.emit("clicked")
        editor = window._toc_editor_window
        editor._text_view.get_buffer().set_text("Synthetic modified hearing — file page 2\n")
        save = next(widget for widget in descendants(editor)
                    if isinstance(widget, Gtk.Button) and widget.get_label() == "Save")
        save.emit("clicked")
        assert toc.read_text() == "Synthetic modified hearing — file page 2\n"
        editor.close()
        drain()
        assert button.get_sensitive()
        print("INLINE MODIFY TOC GTK ACCEPTANCE PASSED", flush=True)
        if os.environ.get("INLINE_TOC_ACCEPT_HOLD"):
            GLib.timeout_add_seconds(120, lambda: (app.quit(), False)[1])
        else:
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False


app.connect("activate", lambda *_: GLib.idle_add(check))
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
