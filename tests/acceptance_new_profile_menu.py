"""New-profile entry/actions: real GTK, temporary storage, no model calls."""
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
TEMP = tempfile.TemporaryDirectory(prefix="new-profile-menu-")
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
Adw.init()
app = Adw.Application(application_id="org.synthetic.NewProfileMenu")
app.register(None)
parent = Adw.ApplicationWindow(application=app, title="Synthetic New profile menu", default_width=600, default_height=400)
store = api.ProfileStore(package, config_root=ROOT / "config", data_root=ROOT / "data")


def drain():
    until = time.monotonic() + .3
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


def click(widget, label):
    target = next(item for item in descendants(widget) if isinstance(item, Gtk.Button)
        and (item.get_label() == label or (isinstance(item.get_child(), Gtk.Label) and item.get_child().get_text() == label)))
    assert target.get_sensitive()
    target.emit("clicked")
    drain()


def actions(dialog):
    buttons = [item for item in descendants(dialog) if isinstance(item, Gtk.Button) and item.get_label() in ("Cancel", "Create")]
    assert [item.get_label() for item in buttons] == ["Cancel", "Create"]
    assert all(item.has_css_class("flat") and isinstance(item.get_parent(), Gtk.Box) for item in buttons)
    assert buttons[0].get_parent() is buttons[1].get_parent()
    assert not any(isinstance(item, (Gtk.FlowBox, Gtk.FlowBoxChild)) for item in descendants(dialog))
    return buttons


with patch.object(api, "profile_store", return_value=store):
    allowed = [True]
    menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.pack_end(menu_button)
    toolbar.add_top_bar(header)
    toolbar.set_content(Gtk.Label(label="Synthetic menu acceptance"))
    parent.set_content(toolbar)
    menu = Gtk.Popover()
    menu_button.set_popover(menu)
    manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: allowed[0],
        preview=lambda snapshot: None, on_select=lambda ref: None, allow_legacy=False, has_case=False)
    menu.set_child(manager)
    parent.present()
    drain()
    menu_button.popup()
    drain()
    assert menu.get_visible()
    assert not store.registry_path.exists()
    if os.environ.get("NEW_PROFILE_MENU_HOLD") == "menu":
        print("SYNTHETIC NEW PROFILE MENU READY", flush=True)
        loop = GLib.MainLoop()
        parent.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    if package == "recordprep":
        assert manager.new_profile_button.get_child().get_text() == "Create profiles"
        assert manager.new_profile_button.get_prev_sibling() is manager.settings_button
        click(manager, "Create profiles")
        assert not menu.get_visible()
        editor = manager.children_windows[-1]
        assert not any(isinstance(item, Gtk.Button) and item.get_label() == "New profile…" for item in descendants(editor))
    else:
        assert manager.new_profile_button is None
        editor = manager._edit()
        click(editor, "Create profiles")
    dialog = editor.new_dialog
    actions(dialog)
    click(dialog, "Cancel")
    assert not store.registry_path.exists()
    resource = "research" if package == "focus" else "classification"
    editor.editor.resources[resource] += "\nSynthetic unsaved menu draft.\n"
    if package == "recordprep":
        menu_button.popup()
        drain()
        click(manager, "Create profiles")
        assert len(manager.children_windows) == 1  # Reuse, don't discard an open draft.
    else:
        click(editor, "Create profiles")
    editor.unsaved_dialog.response("cancel")
    assert "Synthetic unsaved menu draft" in editor.editor.resources[resource]
    # An explicit discard opens the new-profile dialog, but never writes storage.
    editor._new()
    editor.unsaved_dialog.response("discard")
    drain()
    dialog = editor.new_dialog
    actions(dialog)
    before_create = editor._state()
    click(dialog, "Create")
    assert editor._state() == before_create  # Name validation never replaces a draft.
    name = next(item for item in descendants(dialog) if isinstance(item, Gtk.Entry))
    name.set_text("Synthetic menu specialty")
    click(dialog, "Create")
    assert editor.editor.manifest["display_name"] == "Synthetic menu specialty"
    assert editor._dirty() and not store.registry_path.exists()
    assert editor._save()
    drain()
    assert api.profile_store().load_profile_snapshot(editor.editor.base.ref).manifest["display_name"] == "Synthetic menu specialty"
    allowed[0] = False
    manager._guard()
    if package == "recordprep":
        assert not manager.new_profile_button.get_sensitive()
        assert manager._new() is None
    allowed[0] = True
    print(f"{package}: NEW PROFILE MENU GTK ACCEPTANCE PASSED", flush=True)
    if os.environ.get("NEW_PROFILE_MENU_HOLD") == "dialog":
        editor._new()
        drain()
        # Exercise each button's own hover paint, with no wrapper to paint too.
        for item in actions(editor.new_dialog):
            item.set_state_flags(Gtk.StateFlags.PRELIGHT, False)
        loop = GLib.MainLoop()
        editor.new_dialog.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    editor.close()
parent.close()
TEMP.cleanup()
