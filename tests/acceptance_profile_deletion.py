"""Edit profiles deletion: real GTK and disposable cases/profile storage only."""
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
TEMP = tempfile.TemporaryDirectory(prefix="profile-deletion-ui-")
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
workflows = importlib.import_module(package + ".profile_workflows")
manager_ui = importlib.import_module(package + ".profile_manager_ui")
Adw.init()
app = Adw.Application(application_id="org.synthetic.EditProfiles")
app.register(None)
parent = Adw.ApplicationWindow(application=app, title="Synthetic Edit profiles", default_width=700, default_height=600)
store = api.ProfileStore(package, config_root=ROOT / "config", data_root=ROOT / "data")
general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
first = workflows.ProfileEditor.create(general, "Synthetic first profile").snapshot()
second = workflows.ProfileEditor.create(general, "Synthetic second profile").snapshot()
for snapshot in (first, second):
    store.managed_save(snapshot, expected_head=None, expected_default=None)
store.set_default(first.ref)
case_pin = ROOT / "synthetic-case-pin.txt"
case_pin.write_text(second.ref.content_sha256)
pin_bytes = case_pin.read_bytes()


def drain():
    until = time.monotonic() + .2
    while time.monotonic() < until:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.01)


with patch.object(api, "profile_store", return_value=store):
    selected, deleted = [], []
    allowed = [True]
    manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: allowed[0],
        preview=lambda snapshot: None, on_select=selected.append, on_deleted=deleted.append,
        allow_legacy=False, has_case=False, selected_ref=first.ref, case_ref=first.ref)
    editor = manager._edit()
    editor._new()
    drain()
    assert editor.new_dialog.get_title() == "Create profiles"
    assert set(editor.delete_selector.names) == {"Synthetic first profile", "Synthetic second profile"}
    editor.delete_selector.set_selected(editor.delete_selector.names.index("Synthetic first profile"))
    before = store.registry_path.read_bytes()
    editor.delete_button.emit("clicked")
    drain()
    editor.delete_dialog.response("cancel")
    assert store.registry_path.read_bytes() == before and not deleted
    # A concurrent save must not allow a stale delete to win.
    updated = workflows.ProfileEditor(first)
    updated.resources["research" if package == "focus" else "classification"] += "\nSynthetic concurrent change.\n"
    revised = updated.snapshot()
    store.managed_save(revised, expected_head=first.ref.content_sha256, expected_default=store.read_registry()["default"])
    concurrent = store.registry_path.read_bytes()
    editor.delete_button.emit("clicked")
    editor.delete_dialog.response("delete")
    drain()
    assert store.registry_path.read_bytes() == concurrent and not deleted
    editor.new_dialog.close()
    editor._new()
    drain()
    editor.delete_selector.set_selected(editor.delete_selector.names.index("Synthetic first profile"))
    editor.delete_button.emit("clicked")
    editor.delete_dialog.response("delete")
    drain()
    assert deleted == [revised.ref] and not selected
    assert manager.selected_ref.specialty_id == "general-court-record"
    assert store.read_registry()["default"] is None
    assert editor.editor.manifest["specialty_id"] == "general-court-record"
    assert first.ref.specialty_id not in {item.snapshot.ref.specialty_id for item in manager.candidates}
    assert store.load_profile_snapshot(first.ref).files == first.files
    assert store.load_profile_snapshot(revised.ref).files == revised.files
    assert case_pin.read_bytes() == pin_bytes
    # A real case keeps its exact pin; deletion never invokes case selection.
    manager.has_case = True
    manager.selected_ref = second.ref
    manager._refresh(second.ref)
    other = manager._edit()
    other._new()
    drain()
    before = store.registry_path.read_bytes()
    other.delete_button.emit("clicked")
    allowed[0] = False
    other.delete_dialog.response("delete")
    assert store.registry_path.read_bytes() == before and deleted == [revised.ref]
    allowed[0] = True
    other.delete_button.emit("clicked")
    other.delete_dialog.response("delete")
    drain()
    assert manager.selected_ref == second.ref and not selected
    assert deleted == [revised.ref, second.ref]
    assert store.load_profile_snapshot(second.ref).files == second.files
    assert case_pin.read_bytes() == pin_bytes
    other._new()
    drain()
    assert other.delete_selector is None and other.delete_button is None
    assert len(manager.candidates) == len(api.BUNDLED_PROFILES)
    print(f"{package}: EDIT PROFILES DELETION GTK ACCEPTANCE PASSED", flush=True)
    if os.environ.get("EDIT_PROFILES_HOLD"):
        other.new_dialog.close()
        preview = workflows.ProfileEditor.create(general, "Synthetic preview profile").snapshot()
        store.managed_save(preview, expected_head=None, expected_default=None)
        other._new()
        drain()
        loop = GLib.MainLoop()
        other.new_dialog.connect("close-request", lambda *_args: (loop.quit(), False)[1])
        loop.run()
    other.new_dialog.close()
    other.close()
    editor.close()
parent.close()
TEMP.cleanup()
