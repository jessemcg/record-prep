"""Pinned classifier explainer and RT→CT navigation; synthetic GTK only."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
package = "focus" if (HERE / "focus").is_dir() else "recordprep"
TEMP = tempfile.TemporaryDirectory(prefix="classification-guidance-")
ROOT = Path(TEMP.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

api = importlib.import_module(package + ".practice_profiles")
manager_ui = importlib.import_module(package + ".profile_manager_ui")
editor_ui = importlib.import_module(package + ".profile_editor_ui")
Adw.init()
app = Adw.Application(application_id="org.synthetic.ClassificationGuidance")
app.register(None)
parent = Adw.ApplicationWindow(application=app, title="Synthetic classification guidance")
store = api.ProfileStore(package, config_root=ROOT / "config", data_root=ROOT / "data")


def drain():
    until = time.monotonic() + .2
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()


with patch.object(api, "profile_store", return_value=store):
    manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: True,
        preview=lambda snapshot: None, on_select=lambda ref: None, allow_legacy=False, has_case=False)
    editor = manager._edit()
    drain()
    labels = [item for item in descendants(editor.classification_explainer) if isinstance(item, Gtk.Label)]
    assert len(labels) == 2
    assert all(not item.get_selectable() and not item.get_focusable() for item in labels)
    # Observe first presentation, before switching pages/editors clears the
    # automatic selection that previously disguised itself as panel styling.
    if os.environ.get("CLASSIFICATION_GUIDANCE_HOLD") == "initial":
        loop = GLib.MainLoop()
        editor.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    before = editor._state()
    original_files = editor.editor.base.files
    if package == "recordprep":
        expected = ["classification", "rt", "first_hearing", "date_hearing", "ct", "first_minute",
                    "first_form", "date_minute", "report-naming", "form-naming"]
        assert [key for key in editor.pages if editor.page_groups[key] == "Classification"] == expected
        assert editor.nav_rows["classification"].get_subtitle() == "Shared · Basic / Advanced / Dates"
        assert [editor.nav_rows[key].get_subtitle() for key in expected[1:]] == [
            "RT · Basic", "RT · Advanced", "RT · Dates", "CT · Basic", "CT · Advanced",
            "CT · Advanced", "CT · Dates", "CT · Names", "CT · Names"]
        assert editor.nav_rows["report-naming"].get_title() == "Report names and dates"
        assert editor.classification_explainer.has_css_class("profile-classification-explainer")
        assert editor.classification_explainer.get_parent().has_css_class("profile-settings-content")
        assert not editor.classification_explainer.has_css_class("card")
        assert not editor.classification_explainer.has_css_class("boxed-list")
        assert editor.classification_explainer.get_ancestor(Gtk.ScrolledWindow) is None
        assert editor.classification_explainer.get_parent() is editor.stack.get_parent()
        for key in expected:
            editor.nav_rows[key].emit("activated")
            drain()
            assert editor.classification_explainer.get_visible()
            view = next(item for item in descendants(editor.pages[key]) if isinstance(item, Gtk.TextView))
            buffer = view.get_buffer()
            value = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
            resource = (editor.editor.resources["classification"] if key == "classification" else
                editor.editor.resources["naming"][key.removesuffix("-naming") + "_guidance"] if key.endswith("-naming") else
                editor.editor.resources["classification_tasks"][key])
            assert value == resource
            valid, explanation_bounds = editor.classification_explainer.compute_bounds(editor)
            valid_page, page_bounds = editor.pages[key].compute_bounds(editor)
            assert valid and valid_page and explanation_bounds.get_y() + explanation_bounds.get_height() <= page_bounds.get_y()
        # Moving fields does not cross-wire their owners or discard unsaved text.
        editor._select_page("date_hearing")
        view = next(item for item in descendants(editor.pages["date_hearing"]) if isinstance(item, Gtk.TextView))
        buffer = view.get_buffer()
        original = editor.editor.resources["classification_tasks"]["date_hearing"]
        buffer.set_text(original + "\nSynthetic date-only draft." * 400)
        drain()
        scroll = view.get_ancestor(Gtk.ScrolledWindow)
        adjustment = scroll.get_vadjustment()
        position = (adjustment.get_upper() - adjustment.get_page_size()) / 2
        assert position > 0
        adjustment.set_value(position)
        assert editor.classification_explainer.get_visible()
        editor._select_page("date_minute")
        assert editor.editor.resources["classification_tasks"]["date_minute"] == before[1]["classification_tasks"]["date_minute"]
        editor._select_page("date_hearing")
        assert editor.editor.resources["classification_tasks"]["date_hearing"].endswith("Synthetic date-only draft.")
        drain()
        assert abs(adjustment.get_value() - position) <= 1
        assert editor.classification_explainer.get_visible()
        buffer.set_text(original)
        assert editor._state() == before and not editor._dirty()
    for key in editor.pages:
        editor._select_page(key)
        assert editor.classification_explainer.get_visible() == (package == "recordprep" and editor.page_groups[key] == "Classification")
    assert editor._state() == before and editor.editor.base.files == original_files
    assert not store.registry_path.exists()
    print(f"{package}: CLASSIFICATION GUIDANCE GTK ACCEPTANCE PASSED", flush=True)
    if os.environ.get("CLASSIFICATION_GUIDANCE_HOLD"):
        editor._select_page("ct" if package == "recordprep" else "research")
        loop = GLib.MainLoop()
        editor.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    editor.close()
parent.close()
TEMP.cleanup()
