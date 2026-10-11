"""Declarative profile editor widgets; independent copy shipped by each app.

No raw JSON editor and no writes before explicit Save/Export. The owner supplies
its real effective-instruction compiler and active-run guard.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from .profile_contract import ProfileError, ProfileSnapshot
from .profile_store import ProfileStore
from .profile_workflows import ProfileEditor, export_profile

POLICIES = {
    "report_scope": ("include_attributed_proposals", "exclude_formal_proposals"),
    "attendance": ("explicit_complete_order", "legacy_first_page_parents"),
    "mode": ("source_title", "approved_titles"),
}


def friendly(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").capitalize()


def button(label: str, callback: Callable) -> Gtk.Button:
    widget = Gtk.Button(label=label)
    widget.add_css_class("flat")
    widget.connect("clicked", lambda _button: callback())
    return widget


def action_row() -> Gtk.FlowBox:
    """Wrap actions instead of forcing narrow/tiled dialogs below their minimum."""
    return Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                       min_children_per_line=1, max_children_per_line=6,
                       row_spacing=4, column_spacing=6)


def clear(box: Gtk.Box) -> None:
    while box.get_first_child() is not None:
        box.remove(box.get_first_child())


def text_editor(text: str, changed: Callable | None = None) -> Gtk.ScrolledWindow:
    view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, editable=changed is not None)
    view.set_left_margin(12)
    view.set_right_margin(12)
    view.set_top_margin(8)
    view.set_bottom_margin(8)
    buffer = view.get_buffer()
    buffer.set_text(text)
    if changed is not None:
        buffer.connect("changed", lambda source: changed(source.get_text(source.get_start_iter(), source.get_end_iter(), True)))
    scroll = Gtk.ScrolledWindow(min_content_height=140, max_content_height=360, propagate_natural_height=True)
    scroll.set_child(view)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    return scroll


def show_preview(parent, sections: dict[str, str]):
    window = Adw.Window(transient_for=parent, modal=True, title="Effective Instructions — Preview", default_width=820, default_height=700)
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    outer.append(Adw.HeaderBar())
    scroll = Gtk.ScrolledWindow(vexpand=True)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin_start=16, margin_end=16, margin_top=12, margin_bottom=16)
    for title, text in sections.items():
        group = Adw.PreferencesGroup(title=title)
        group.add(text_editor(text))
        body.append(group)
    scroll.set_child(body)
    outer.append(scroll)
    window.set_content(outer)
    window.present()
    return window


class ProfileEditorWindow(Adw.Window):
    def __init__(self, parent, editor: ProfileEditor, store: ProfileStore, *,
                 expected_head: str | None, can_modify: Callable[[], bool],
                 preview: Callable[[ProfileSnapshot], dict[str, str]], on_saved: Callable):
        super().__init__(transient_for=parent, modal=True, title="Edit Practice Profile",
                         default_width=820, default_height=760)
        self.editor = editor
        self.store = store
        self.expected_head = expected_head
        self.can_modify = can_modify
        self.preview = preview
        self.on_saved = on_saved
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        outer.append(header)
        header.pack_start(button("Cancel", self.close))
        self.save_button = button("Save & Accept…", self._save)
        self.export_button = button("Export…", lambda: self._save(export_only=True))
        header.pack_end(self.save_button)
        actions = action_row()
        actions.append(button("Validate", self._validate))
        actions.append(button("Preview", self._preview))
        actions.append(self.export_button)
        outer.append(actions)
        self.message = Gtk.Label(wrap=True, xalign=0, selectable=True)
        self.message.set_margin_start(16)
        self.message.set_margin_end(16)
        outer.append(self.message)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                            margin_start=18, margin_end=18, margin_top=12, margin_bottom=18)
        scroll.set_child(self.body)
        outer.append(scroll)
        self.set_content(outer)
        identity = Adw.PreferencesGroup(title="Identity", description="Saving creates a new complete folder and accepted revision. It does not select a case or change defaults.")
        self.body.append(identity)
        identity.add(Adw.ActionRow(title="Stable specialty identity", subtitle=editor.manifest["specialty_id"]))
        for key in ("display_name", "version", "description"):
            self._field(identity, editor.manifest, key, (key,))
        for name in editor.resources:
            group = Adw.PreferencesGroup(title=friendly(name))
            self.body.append(group)
            self._field(group, editor.resources, name, (name,), resource=True)
        self._guard_id = GLib.timeout_add(250, self._refresh_guard)
        self.connect("close-request", self._closed)
        self.connect("destroy", self._closed)
        self._refresh_guard()

    def _closed(self, *_args) -> bool:
        if self._guard_id:
            GLib.source_remove(self._guard_id)
            self._guard_id = 0
        return False

    def _refresh_guard(self) -> bool:
        allowed = self.can_modify()
        self.body.set_sensitive(allowed)
        self.save_button.set_sensitive(allowed)
        self.export_button.set_sensitive(allowed)
        if not allowed:
            self.message.set_text("Profile changes are unavailable while work is active or the case has changed. Cancel and reopen when ready.")
        return True

    def _field(self, group, owner, key, path: tuple[str, ...], *, resource=False) -> None:
        value = owner[key]
        title = friendly(str(key)) if not isinstance(key, int) else "Value"
        if isinstance(value, dict):
            for child in value:
                self._field(group, value, child, (*path, child))
        elif isinstance(value, list):
            holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            group.add(holder)
            self._list(holder, value, path)
        elif key in POLICIES:
            choices = POLICIES[key]
            row = Adw.ComboRow(title=title, model=Gtk.StringList.new([friendly(item) for item in choices]))
            row.set_selected(choices.index(value))
            row.connect("notify::selected", lambda widget, _pspec: owner.__setitem__(key, choices[widget.get_selected()]))
            group.add(row)
        elif key in ("id", "schema_version"):
            group.add(Adw.ActionRow(title=title, subtitle=str(value)))
        elif isinstance(value, str) and (resource or "guidance" in str(key) or key == "description"):
            if not resource:
                group.add(Adw.ActionRow(title=title))
            group.add(text_editor(value, lambda text: owner.__setitem__(key, text)))
        else:
            row = Adw.EntryRow(title=title, text=str(value))
            row.connect("changed", lambda widget: owner.__setitem__(key, widget.get_text()))
            group.add(row)

    def _list(self, holder: Gtk.Box, values: list, path: tuple[str, ...]) -> None:
        clear(holder)
        title = friendly(path[-1])
        def redraw():
            self._list(holder, values, path)
        def move(index, offset):
            other = index + offset
            if 0 <= other < len(values):
                values[index], values[other] = values[other], values[index]
                redraw()
        def remove(index):
            del values[index]
            redraw()
        for index, value in enumerate(values):
            group = Adw.PreferencesGroup(title=f"{title} {index + 1}")
            holder.append(group)
            tools = Gtk.Box(spacing=4)
            tools.append(button("Up", lambda index=index: move(index, -1)))
            tools.append(button("Down", lambda index=index: move(index, 1)))
            protected = path[0] == "roles" and isinstance(value, dict) and value.get("id") in {"unknown", "other"}
            if not protected:
                tools.append(button("Remove", lambda index=index: remove(index)))
            group.set_header_suffix(tools)
            if isinstance(value, dict):
                for key in value:
                    self._field(group, value, key, (*path, key))
            else:
                self._field(group, values, index, path)
        def add():
            if path[-1] == "form_rules":
                values.append({"name": "New form", "title": "Source title", "code": "FORM-1"})
            elif path[0] in ("roles", "hearings", "reports"):
                label = "label" if path[0] == "roles" else "title"
                values.append({"id": f"item-{uuid.uuid4().hex}", label: "New role" if label == "label" else "New category",
                               "guidance": "Record material source-supported information."})
            else:
                values.append("New term")
            redraw()
        holder.append(button(f"Add {title}", add))

    def _validate(self) -> ProfileSnapshot | None:
        try:
            snapshot = self.editor.snapshot()
            self.message.set_text(f"Valid profile · {snapshot.ref.content_sha256[:12]}. Review guidance before accepting.")
            return snapshot
        except (ProfileError, OSError) as exc:
            self.message.set_text(f"Validation failed: {exc}")
            return None

    def _preview(self) -> None:
        snapshot = self._validate()
        if snapshot is None:
            return
        try:
            sections = self.preview(snapshot)
        except (ProfileError, OSError) as exc:
            self.message.set_text(f"Preview unavailable: {exc}")
            return
        return show_preview(self, sections)

    def _save(self, *, export_only=False) -> None:
        if not self.can_modify():
            self._refresh_guard()
            return
        snapshot = self._validate()
        if snapshot is None:
            return
        dialog = Gtk.FileDialog(title="Choose a NEW profile folder name — existing destinations are refused",
                                initial_name=f"{snapshot.ref.specialty_id}-{snapshot.ref.content_sha256[:8]}")
        def chosen(source, result):
            try:
                file = source.save_finish(result)
            except GLib.Error:
                return  # Cancellation creates nothing.
            if not self.can_modify():
                self._refresh_guard()
                return
            path = file.get_path()
            if path is None:
                self.message.set_text("Choose a local folder destination.")
                return
            try:
                if self.editor.snapshot().ref != snapshot.ref:
                    raise ProfileError("editor_changed", "save")
                if export_only:
                    export_profile(snapshot, Path(path))
                    self.message.set_text("Exported. The destination app must validate and accept this folder before using it.")
                else:
                    ref = self.editor.save(self.store, Path(path), expected_head=self.expected_head)
                    self.on_saved(ref)
                    self.close()
            except (ProfileError, OSError) as exc:
                self.message.set_text(f"Save failed; no case/default changed: {exc}")
        dialog.save(self, None, chosen)
