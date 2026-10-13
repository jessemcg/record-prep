"""Offline real GTK choose/edit/save/new workflow and bounded wrapping checks.

Temporary storage only. No picker, repository operation or model request. Set
PROFILE_ACCEPT_HOLD=1 to inspect the synthetic settings window on this desktop.
"""
import importlib
from dataclasses import asdict
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
    widget = next(w for w in descendants(window) if isinstance(w, Gtk.Button) and
                  (w.get_label() == label or (isinstance(w.get_child(), Gtk.Label) and w.get_child().get_text() == label)))
    assert widget.get_sensitive(), label
    widget.emit("clicked")


def new_profile(manager, editor):
    if package == "recordprep":
        manager._guard()
        click(manager, "Create profiles")
    else:
        click(editor, "Create profiles")


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
        window.unrealize()
        window.unmaximize()
        window.set_size_request(*((360, 480) if hasattr(window, "stack") else (-1, -1)))
        assert window.measure(Gtk.Orientation.HORIZONTAL, -1).minimum <= 480
        window.set_default_size(width, 680)
        window.present()
        deadline = time.monotonic() + 2
        drain(.2)
        if os.environ.get("GDK_BACKEND") == "x11" and window.get_width() < width:
            # GTK's no-WM fallback counts invisible borders in the requested
            # size. Compensate, still asserting the exact content allocation.
            window.set_default_size(width + width - window.get_width(), 680)
        while abs(window.get_width() - width) > 2 and time.monotonic() < deadline:
            drain(.1)
        assert abs(window.get_width() - width) <= 2, (width, window.get_width())
    window.set_size_request(*((360, 480) if hasattr(window, "stack") else (-1, -1)))


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
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.set_content(manager)
        parent.set_content(toolbar)
        drain()
        assert len(manager.candidates) == len(api.BUNDLED_PROFILES)
        assert not list(root.iterdir())
        layout(parent)
        assert not isinstance(manager, Gtk.Window)
        # Built-in inspection is substantive, read-only and directly editable.
        manager.selector.set_selected(1 if package == "focus" else 0, notify=False)
        assert manager.settings_button.get_child().get_text() == "Profile settings"
        assert not any(isinstance(widget, Adw.PreferencesGroup) for widget in descendants(manager))
        click(manager, "Profile settings")
        editor = manager.children_windows[-1]
        assert not editor.get_modal() and editor.get_transient_for() is None
        assert editor.get_resizable()
        assert isinstance(editor.get_content(), Adw.ToolbarView)
        assert editor.get_content().get_top_bar_style() == Adw.ToolbarStyle.FLAT
        # The real-main-window acceptance covers compositor maximization.
        # This harness also runs under bare Xvfb for exact layout allocations.
        layout(editor)
        assert editor.navigation.has_css_class("boxed-list")
        assert editor.body.has_css_class("profile-settings-layout")
        first_page = "classification" if package == "recordprep" else "profile"
        assert editor.stack.get_visible_child_name() == first_page
        if package == "recordprep":
            assert not hasattr(editor, "selector")
            assert editor.default_row is None
            assert "case-name" not in editor.pages
        expected_categories = ({"Classification", "Summaries"}
                               if package == "recordprep" else {"General", "Research", "Answers", "Search priorities"})
        assert set(editor.nav_groups) == expected_categories
        # Every child row selects just its own page; navigation does not edit data.
        original_state = editor._state()
        for key, row in editor.nav_rows.items():
            row.emit("activated")
            drain(.03)
            assert editor.stack.get_visible_child_name() == key
            assert editor.pages[key].get_mapped()
            assert all(not page.get_mapped() for other, page in editor.pages.items() if other != key)
            assert editor.nav_markers[key].get_visible()
            assert sum(marker.get_visible() for marker in editor.nav_markers.values()) == 1
            assert editor._state() == original_state
        prompt_key = "ct" if package == "recordprep" else "research"
        editor.nav_rows[prompt_key].emit("activated")
        layout(editor)
        view = next(widget for widget in descendants(editor.pages[prompt_key]) if isinstance(widget, Gtk.TextView))
        prompt_scroll = view.get_ancestor(Gtk.ScrolledWindow)
        assert prompt_scroll.get_min_content_height() >= 360
        assert prompt_scroll.get_height() >= 360
        # Draft text and cursor/scroll survive navigation; only Save persists it.
        buffer = view.get_buffer()
        old_text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        buffer.set_text(old_text + "\nSynthetic navigation draft." + "\nSynthetic long prompt line." * 200)
        buffer.place_cursor(buffer.get_iter_at_offset(12))
        drain(.1)
        adjustment = prompt_scroll.get_vadjustment()
        position = (adjustment.get_upper() - adjustment.get_page_size()) / 2
        assert position > 0
        adjustment.set_value(position)
        editor.nav_rows[first_page].emit("activated")
        editor.nav_rows[prompt_key].emit("activated")
        drain(.1)
        assert "Synthetic navigation draft" in buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        assert buffer.get_iter_at_mark(buffer.get_insert()).get_offset() == 12
        assert abs(adjustment.get_value() - position) <= 1
        buffer.set_text(old_text)
        assert not editor._dirty()
        # Narrow windows use a categories overlay; selection dismisses it.
        editor.set_visible(False)
        editor.unrealize()
        editor.set_default_size(490 if os.environ.get("GDK_BACKEND") == "x11" else 480, 680)
        editor.present()
        drain(.3)
        assert editor.body.get_collapsed() and editor.sidebar_button.get_visible()
        editor.sidebar_button.set_active(True)
        assert editor.body.get_show_sidebar()
        category = "Summaries" if package == "recordprep" else "Answers"
        editor.nav_groups[category].set_expanded(True)
        assert editor.body.get_show_sidebar()
        editor.nav_rows[prompt_key].emit("activated")
        assert not editor.body.get_show_sidebar()
        layout(editor)
        editor._select_page(first_page)
        assert editor.editor.resources
        assert not hasattr(importlib.import_module(package + ".profile_editor_ui"), "POLICIES")
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
        click(manager, "Profile settings")
        editor = manager.children_windows[-1]
        resource = "research" if package == "focus" else "classification"
        editor.editor.resources[resource] += "\nSynthetic personal instructions.\n"
        click(editor, "Save")
        assert store.read_registry()["personal"]
        ref = editor.editor.base.ref
        assert not selected
        click(editor, "Cancel")
        drain()
        manager.selector._choose(manager.selector.get_selected())
        assert selected == [ref]
        click(manager, "Profile settings")
        editor = manager.children_windows[-1]
        assert "Synthetic personal instructions" in editor.editor.resources[resource]
        editor.editor.resources[resource] += "\nSynthetic revised settings.\n"
        click(editor, "Save")
        assert selected == [ref]  # Saving alone never binds the case.
        assert editor.case_notice.get_visible()
        assert "This case uses earlier settings" in editor.case_notice.get_text()
        # A pending choice is not a case pin, even when revisions differ.
        manager.has_case = False
        editor.refresh_case_notice()
        assert not editor.case_notice.get_visible() and not editor.case_notice.get_text()
        manager.has_case = True
        editor.refresh_case_notice()
        assert editor.case_notice.get_visible()
        assert manager._selected().snapshot.ref != ref
        assert not manager.message.get_visible()
        assert not any(isinstance(widget, Gtk.Label) and "This case uses earlier settings" in widget.get_text()
                       for widget in descendants(manager))
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
        new_profile(manager, editor)
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
        if package == "focus":
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
        else:
            # Saving an existing default advances it, without adding a default control.
            store.set_default(editor.editor.base.ref)
            editor.expected_default = store.read_registry()["default"]
            editor.editor.resources[resource] += "\nSynthetic default revision.\n"
            assert editor._save()
            assert store.read_registry()["default"] == asdict(editor.editor.base.ref)
            manager.apply_dialog.response("later")
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
        editor._select_page(first_page)
        new_profile(manager, editor)
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
            editor._select_page("hearings-topics")
            click(editor, "Add topic")
            topic = editor.editor.resources["hearings"][-1]
            identity = topic["id"]
            topic["title"] = "Specialty findings"
            editor.editor.resources["reports"].append({"id": "item-" + uuid.uuid4().hex, "title": "Specialty findings", "guidance": "Capture material source-supported specialty findings."})
            assert not {"roles", "participants"}.intersection(editor.editor.resources)
            assert topic["id"] == identity
            assert set(editor.editor.resources["naming"]) == {"schema_version", "report_guidance", "form_guidance"}
            labels = [w.get_text() for w in descendants(editor) if isinstance(w, Gtk.Label)]
            for removed in ("Document naming", "Naming rule", "Approved report titles", "Add form"):
                assert removed not in labels
            editor.editor.resources["naming"]["report_guidance"] += "\n- **Independent Expert Report**\n"
            from recordprep.document_naming import compile_naming_profile
            assert "Independent Expert Report" in compile_naming_profile(editor.editor.snapshot(), "report").allowed_names
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
        assert editor.message.get_text() == ""
        selected_page = editor.stack.get_visible_child_name()
        click(editor, "Save")
        assert editor.stack.get_visible_child_name() == selected_page
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
        parent.set_content(None)
        parent.close()
        drain()
print("SIMPLE GTK PROFILE WORKFLOW ACCEPTANCE PASSED", package)
