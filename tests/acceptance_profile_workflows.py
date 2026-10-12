"""Offline real GTK choose/edit/save/new workflow and bounded wrapping checks.

Temporary storage only. No picker, repository operation or model request. Set
PROFILE_ACCEPT_HOLD=1 to inspect the synthetic settings window on this desktop.
"""
import importlib
import json
import uuid
import os
import tempfile
import time
import sys
from pathlib import Path
from unittest.mock import patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

package = "focus" if (Path(__file__).resolve().parents[1] / "focus").is_dir() else "recordprep"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
api = importlib.import_module(package + ".practice_profiles")
manager_ui = importlib.import_module(package + ".profile_manager_ui")
integration = importlib.import_module(package + ".profile_integration")
workflows = importlib.import_module(package + ".profile_workflows")
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


def drain(seconds=.12):
    until = time.monotonic() + seconds
    context = GLib.MainContext.default()
    while time.monotonic() < until:
        while context.pending():
            context.iteration(False)
        time.sleep(.005)


def layout(window):
    for width in (480, 640, 820):
        # GNOME attached modal windows can ignore default-size changes after mapping.
        # Remap the same populated draft; assert actual allocations at every width.
        window.set_visible(False)
        drain(.1)
        window.unmaximize()
        window.set_default_size(width, 680)
        window.present()
        deadline = time.monotonic() + 2
        drain(.2)
        while abs(window.get_width() - width) > 2 and time.monotonic() < deadline:
            drain(.1)
        assert window.measure(Gtk.Orientation.HORIZONTAL, -1).minimum <= 480, window.measure(Gtk.Orientation.HORIZONTAL, -1)
        assert abs(window.get_width() - width) <= 2, (width, window.get_width())


with tempfile.TemporaryDirectory(prefix="simple-profile-gui-") as temporary:
    root = Path(temporary)
    store = api.ProfileStore(package, config_root=root / "config", data_root=root / "data")
    parent = Adw.Window(title="Synthetic Practice Profile Acceptance", default_width=820, default_height=760)
    parent.present()
    allowed = [True]
    selected = []
    preview = integration.preview if package == "focus" else lambda snapshot: integration.preview(snapshot, Path.cwd() / ".pi")
    with patch.object(api, "profile_store", return_value=store):
        manager = manager_ui.ProfileManagerWindow(parent, can_modify=lambda: allowed[0], preview=preview,
                                                  on_select=selected.append, allow_legacy=package == "focus")
        manager.present()
        drain()
        assert len(manager.candidates) == len(api.BUNDLED_PROFILES)
        assert not list(root.iterdir())
        layout(manager)
        # Built-in inspection is substantive, read-only and directly editable.
        manager.list.select_row(manager.list.get_row_at_index(1 if package == "focus" else 0))
        click(manager, "Profile settings…")
        editor = manager.children_windows[-1]
        layout(editor)
        assert editor.editor.resources
        assert "report_scope" not in importlib.import_module(package + ".profile_editor_ui").POLICIES
        assert not any(isinstance(item, Gtk.Label) and item.get_text() == "Formal proposals"
                       for item in descendants(editor))
        if package == "recordprep":
            assert "report_scope" not in editor.editor.resources["policies"]
            # An old saved value is readable, but editing drops it only in memory.
            legacy = workflows.ProfileEditor(editor.editor.base)
            legacy.resources["policies"]["report_scope"] = "exclude_formal_proposals"
            historical = legacy.snapshot()
            old_files = historical.files
            draft = importlib.import_module(package + ".profile_editor_ui").editable_profile(historical)
            assert "report_scope" not in draft.resources["policies"]
            assert historical.files == old_files
            assert historical.resource("policies")["report_scope"] == "exclude_formal_proposals"
            assert preview(draft.snapshot())
        click(editor, "Cancel")
        drain()
        assert not list(root.iterdir())
        click(manager, "Profile settings…")
        editor = manager.children_windows[-1]
        resource = "research" if package == "focus" else "case_name"
        editor.editor.resources[resource] += "\nSynthetic personal instructions.\n"
        click(editor, "Save")
        assert store.read_registry()["personal"]
        ref = editor.editor.base.ref
        assert not selected
        click(editor, "Cancel")
        drain()
        click(manager, "Use profile")
        assert selected == [ref]
        click(manager, "Profile settings…")
        editor = manager.children_windows[-1]
        assert "Synthetic personal instructions" in editor.editor.resources[resource]
        editor.editor.resources[resource] += "\nSynthetic revised settings.\n"
        click(editor, "Save")
        assert selected == [ref]  # Saving alone never binds the case.
        manager.apply_dialog.response("later")
        assert selected == [ref]
        # Explicit application is guarded again after successful persistence.
        click(editor, "Save")
        allowed[0] = False
        manager.apply_dialog.response("use")
        assert selected == [ref]
        assert editor.message.get_text() == "Profile saved; case settings were not changed."
        allowed[0] = True
        editor._refresh_guard()
        before_cancel = store.registry_path.read_bytes()
        click(editor, "New profile…")
        cancelled = editor.new_dialog
        next(item for item in descendants(cancelled) if isinstance(item, Gtk.Entry)).set_text("Synthetic cancelled draft")
        click(cancelled, "Create")
        click(editor, "Cancel")
        editor.unsaved_dialog.response("cancel")
        assert store.registry_path.read_bytes() == before_cancel
        click(editor, "Cancel")
        editor.unsaved_dialog.response("discard")
        assert store.registry_path.read_bytes() == before_cancel
        editor = manager._edit()
        drain()
        editor.editor.resources[resource] += "\nSynthetic unsaved switch instruction.\n"
        editor.selector._choose(1)
        editor.unsaved_dialog.response("cancel")
        assert "Synthetic unsaved switch instruction" in editor.editor.resources[resource]
        editor.selector._choose(1)
        editor.unsaved_dialog.response("save")
        # Resolve the explicit case question before changing the viewed draft.
        assert editor.editor.manifest["specialty_id"] == "general-court-record"
        manager.apply_dialog.response("later")
        assert editor.editor.manifest["specialty_id"] == "california-juvenile-dependency"
        assert selected == [ref]
        editor.selector._choose(0)
        editor.editor.resources[resource] += "\nSynthetic draft preserved after a concurrent save.\n"
        competing = workflows.ProfileEditor(editor.editor.base)
        competing.resources[resource] += "\nSynthetic competing save.\n"
        competing.managed_save(store, expected_head=editor.expected_head, expected_default=editor.expected_default,
                              can_modify=lambda: True, validate=preview, use_for_new_cases=False, personal=True)
        concurrent_bytes = store.registry_path.read_bytes()
        assert not editor._save()
        assert "preserved after a concurrent save" in editor.editor.resources[resource]
        assert store.registry_path.read_bytes() == concurrent_bytes
        click(editor, "Cancel")
        editor.unsaved_dialog.response("discard")
        manager._refresh()
        editor = manager._edit()
        drain()
        click(editor, "New profile…")
        dialog = editor.new_dialog
        name = next(w for w in descendants(dialog) if isinstance(w, Gtk.Entry))
        click(dialog, "Create")
        assert "Enter" in next(w for w in descendants(dialog) if isinstance(w, Gtk.Label) and "Enter" in w.get_text()).get_text()
        long_name = "Synthetic third specialty for complex multi-party court proceedings and complete record research"
        name.set_text(long_name)
        click(dialog, "Create")
        drain()
        assert editor.editor.manifest["display_name"] == long_name
        assert len(store.read_registry()["heads"]) == 1
        layout(editor)
        if package == "recordprep":
            click(editor, "Add topic")
            topic = editor.editor.resources["hearings"][-1]
            identity = topic["id"]
            topic["title"] = "Specialty findings"
            editor.editor.resources["reports"].append({"id": "item-" + uuid.uuid4().hex, "title": "Specialty findings", "guidance": "Capture material source-supported specialty findings."})
            editor.editor.resources["roles"]["participants"].append({"id": "item-" + uuid.uuid4().hex, "label": "Independent expert", "guidance": "Identify the expert only from explicit source evidence."})
            assert topic["id"] == identity
            editor.editor.resources["naming"]["mode"] = "approved_titles"
            editor.editor.resources["naming"]["report_titles"].append("Independent Expert Report")
        else:
            editor.editor.resources["search"]["query_terms"].append("motion")
            if os.environ.get("PROFILE_ACCEPT_IDENTITY"):
                # Maintainer-authored counterpart metadata, not an end-user import.
                descriptor = json.loads(Path(os.environ["PROFILE_ACCEPT_IDENTITY"]).read_text())
                editor.editor.manifest["specialty_id"] = descriptor["specialty_id"]
        assert preview(editor.editor.snapshot())
        allowed[0] = False
        before = store.registry_path.read_bytes()
        assert not editor._save()
        assert store.registry_path.read_bytes() == before
        allowed[0] = True
        editor._refresh_guard()
        click(editor, "Save")
        new_ref = editor.editor.base.ref
        assert new_ref.specialty_id != ref.specialty_id
        assert len(store.read_registry()["heads"]) == 2
        assert selected == [ref]
        count = len(store.read_registry()["accepted"])
        before = store.registry_path.read_bytes()
        click(editor, "Save")
        assert len(store.read_registry()["accepted"]) == count
        assert store.registry_path.read_bytes() == before
        if os.environ.get("PROFILE_ACCEPT_OUTPUT_ROOT"):
            output = Path(os.environ["PROFILE_ACCEPT_OUTPUT_ROOT"])
            output.mkdir(mode=0o700, parents=True, exist_ok=False)
            workflows.export_profile(store.load_profile_snapshot(new_ref), output / "profile")
            workflows.export_identity(store.load_profile_snapshot(new_ref), output / "identity.json")
        if os.environ.get("PROFILE_ACCEPT_HOLD"):
            editor.set_default_size(480, 680)
            GLib.MainLoop().run()
        editor._closing = True
        editor.close()
        manager.close()
        parent.close()
        drain()
print("SIMPLE GTK PROFILE WORKFLOW ACCEPTANCE PASSED", package)
