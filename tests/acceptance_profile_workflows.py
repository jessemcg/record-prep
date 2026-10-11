"""Offline GTK workflow acceptance. Run with an isolated HOME/XDG and fatal-criticals.

Uses real widgets, signals, compilers, stores and publication. Only native file
picker completion is simulated with temporary local destinations; this does not
claim acceptance of the desktop portal's own file picker implementation.
"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

package = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
api = importlib.import_module(package + ".practice_profiles")
workflows = importlib.import_module(package + ".profile_workflows")
manager_ui = importlib.import_module(package + ".profile_manager_ui")
integration = importlib.import_module(package + ".profile_integration")
contract = importlib.import_module(package + ".profile_contract")
Adw.init()


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()


def click(window, label):
    widget = next(w for w in descendants(window) if isinstance(w, Gtk.Button) and w.get_label() == label)
    assert widget.get_sensitive(), label
    widget.emit("clicked")


def entry(window, title, text):
    widget = next(w for w in descendants(window) if isinstance(w, Adw.EntryRow) and w.get_title() == title)
    widget.set_text(text)


def drain():
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


def check_compact_layout(window):
    for width in (480, 640, 820):
        window.set_default_size(width, 680)
        loop = GLib.MainLoop()
        GLib.timeout_add(100, lambda: (loop.quit(), False)[1])
        loop.run()
    assert window.measure(Gtk.Orientation.HORIZONTAL, -1).minimum <= 600


class Picker:
    destination = None
    def __init__(self, **kwargs):
        pass
    def save(self, parent, cancellable, callback):
        callback(self, None)
    select_folder = open = save
    def save_finish(self, result):
        if self.destination is None:
            raise GLib.Error.new_literal(Gio.io_error_quark(), "Synthetic cancel", Gio.IOErrorEnum.CANCELLED)
        return Gio.File.new_for_path(str(self.destination))
    select_folder_finish = open_finish = save_finish


with tempfile.TemporaryDirectory(prefix="profile-gui-acceptance-") as temporary:
    root = Path(temporary)
    store = api.ProfileStore(package, config_root=root / "config", data_root=root / "data")
    parent = Adw.Window(title="Synthetic Practice Profile Acceptance", default_width=900, default_height=800)
    parent.present()
    allowed = [True]
    selected = []
    preview = integration.preview if package == "focus" else lambda snapshot: integration.preview(snapshot, Path.cwd() / ".pi")
    with patch.object(api, "profile_store", return_value=store), patch.object(Gtk, "FileDialog", Picker):
        manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: allowed[0], preview=preview,
                                                  on_select=selected.append, allow_legacy=package == "focus")
        manager.present()
        drain()
        check_compact_layout(manager)
        click(manager, "Create from General")
        editor = manager.children_windows[-1]
        check_compact_layout(editor)
        click(editor, "Cancel")
        drain()
        assert not list(root.iterdir())
        click(manager, "Create from General")
        editor = manager.children_windows[-1]
        entry(editor, "Display name", "Synthetic third specialty")
        click(editor, "Add Query terms" if package == "focus" else "Add Hearings")
        if package == "recordprep":
            click(editor, "Add Participants")
            click(editor, "Add Reports")
            role_label = next(w for w in descendants(editor) if isinstance(w, Adw.EntryRow) and w.get_text() == "New role")
            role_label.set_text("Independent expert")
            for row in list(descendants(editor)):
                if isinstance(row, Adw.EntryRow) and row.get_text() == "New category":
                    row.set_text("Specialty findings")
            click(editor, "Add Report titles")
            title_row = next(w for w in descendants(editor) if isinstance(w, Adw.EntryRow) and w.get_text() == "New term")
            title_row.set_text("Independent Expert Report")
            mode = next(w for w in descendants(editor) if isinstance(w, Adw.ComboRow) and w.get_title() == "Mode")
            mode.set_selected(1)  # Declared approved_titles, not a code-level specialty branch.
            old_guidance = editor.editor.resources["naming"]["report_guidance"]
            view = next(w for w in descendants(editor) if isinstance(w, Gtk.TextView)
                        and w.get_buffer().get_text(w.get_buffer().get_start_iter(), w.get_buffer().get_end_iter(), True) == old_guidance)
            view.get_buffer().set_text(old_guidance + "\nPreserve a synthetic expert report's source title.")
        assert editor.editor.manifest["display_name"] == "Synthetic third specialty"
        assert editor._validate() is not None
        preview_window = editor._preview()
        assert preview_window is not None
        preview_window.close()
        # Native picker cancellation must have no effects.
        Picker.destination = None
        click(editor, "Export…")
        assert not list(root.iterdir())
        Picker.destination = root / "exported"
        click(editor, "Export…")
        assert (root / "exported/profile.json").is_file()
        assert not store.read_registry()["accepted"]
        Picker.destination = root / "accepted"
        click(editor, "Save & Accept…")
        drain()
        assert len(store.read_registry()["accepted"]) == 1
        ref = manager._selected()[0].ref
        assert not selected and store.read_registry()["default"] is None
        click(manager, "Use for this case")
        click(manager, "Default for new contexts")
        assert selected == [ref]
        assert store.read_registry()["default"]["content_sha256"] == ref.content_sha256
        # Concurrent external prose edits reject the stale editor without export.
        click(manager, "Edit / Export…")
        editor = manager.children_windows[-1]
        external_manifest = root / "accepted/profile.json"
        manifest = json.loads(external_manifest.read_text())
        manifest["description"] = "Explicit external revision for synthetic acceptance."
        external_manifest.write_bytes(contract.json_bytes(manifest))
        entry(editor, "Display name", "Stale draft")
        Picker.destination = root / "must-not-exist"
        click(editor, "Save & Accept…")
        assert "external_profile_changed" in editor.message.get_text()
        assert not Picker.destination.exists()
        click(editor, "Cancel")
        click(manager, "Review external edits")
        editor = manager.children_windows[-1]
        assert "conflict/review" in editor.message.get_text()
        click(editor, "Accept reviewed folder")
        drain()
        revised = manager._selected()[0].ref
        assert revised != ref
        assert selected == [ref] and store.read_registry()["default"]["content_sha256"] == ref.content_sha256
        # Explicit folder registration reviews and accepts old exported bytes;
        # it does not rebind cases or defaults, even when changing the head.
        Picker.destination = root / "exported"
        click(manager, "Register folder…")
        click(manager.children_windows[-1], "Accept reviewed folder")
        assert manager._selected()[0].ref == ref
        # Identity-only export/import is independent of instruction resources.
        Picker.destination = root / "identity.json"
        click(manager, "Export identity…")
        identity = contract.parse_identity_descriptor(Picker.destination.read_bytes())
        assert set(identity) == {"schema_version", "specialty_id", "display_name", "description"}
        count = len(store.read_registry()["accepted"])
        click(manager, "Import identity…")
        assert "already exists locally" in manager.message.get_text()
        assert len(store.read_registry()["accepted"]) == count
        if os.environ.get("PROFILE_ACCEPT_IDENTITY"):
            identity = contract.parse_identity_descriptor(Path(os.environ["PROFILE_ACCEPT_IDENTITY"]).read_bytes())
        else:
            identity["specialty_id"] = "synthetic-counterpart"
            identity["display_name"] = "Independent synthetic counterpart"
        Picker.destination.write_bytes(contract.json_bytes(identity))
        click(manager, "Import identity…")
        editor = manager.children_windows[-1]
        assert editor.editor.manifest["specialty_id"] == identity["specialty_id"]
        entry(editor, "Version", "9.1.0")
        if package == "focus":
            click(editor, "Add Query terms")
            entry(editor, "Value", "motion")
        assert editor.editor.base.ref.application == package
        assert editor._validate() is not None
        allowed[0] = False
        manager._guard()
        editor._refresh_guard()
        assert not editor.save_button.get_sensitive() and not editor.body.get_sensitive()
        assert all(not widget.get_sensitive() for widget in manager.mutating_buttons)
        before = store.registry_path.read_bytes()
        editor._save()
        assert store.registry_path.read_bytes() == before
        allowed[0] = True
        manager._guard()
        editor._refresh_guard()
        Picker.destination = root / "counterpart-accepted"
        click(editor, "Save & Accept…")
        counterpart = manager._selected()[0]
        assert counterpart.ref.specialty_id == identity["specialty_id"]
        assert selected == [ref] and store.read_registry()["default"]["content_sha256"] == ref.content_sha256
        if os.environ.get("PROFILE_ACCEPT_OUTPUT_ROOT"):
            output = Path(os.environ["PROFILE_ACCEPT_OUTPUT_ROOT"])
            output.mkdir(mode=0o700, parents=True, exist_ok=False)
            original = store.load_profile_snapshot(ref)
            workflows.export_profile(original, output / "profile")
            workflows.export_identity(original, output / "identity.json")
            workflows.export_profile(counterpart, output / "counterpart")
        manager.close()
        parent.close()
        drain()
print("GTK PROFILE WORKFLOW ACCEPTANCE PASSED", package)
