"""Compact chooser; technical maintenance operations stay outside the GUI."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from . import practice_profiles as api
from .profile_contract import ProfileError
from .profile_editor_ui import ProfileEditorWindow, button, wrapped, action_row, editable_profile, confirmation


class ProfileManagerWindow(Adw.Window):
    def __init__(self, parent, *, can_modify, preview, on_select, context_text="", allow_legacy=True,
                 selected_ref=None, customization=None, can_select=None, settings=False, case_ref=None, case_confirmed=True):
        super().__init__(transient_for=parent, modal=True, title="Choose profile", default_width=480, default_height=420)
        try:
            self.store = api.profile_store()
        except (ValueError, OSError):
            self.destroy()
            raise
        self.can_modify, self.preview, self.on_select = can_modify, preview, on_select
        self.can_select = can_select or (lambda: True)
        self.allow_legacy, self.selected_ref = allow_legacy, case_ref
        self.settings_only = settings
        self.case_confirmed = case_confirmed
        self.children_windows = []
        self._guard_id = 0
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                            margin_start=18, margin_end=18, margin_top=12, margin_bottom=18)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(Adw.HeaderBar())
        outer.append(self.body)
        self.set_content(outer)
        self.message = wrapped("", selectable=True)
        self.body.append(self.message)
        # Retained adapter surface, but no technical provenance is displayed.
        self.context_group = Adw.PreferencesGroup()
        self.body.append(self.context_group)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("boxed-list")
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=140)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.list)
        self.body.append(scroll)
        self.list.connect("row-selected", lambda *_args: self._describe_choice())
        actions = action_row()
        self.select_button = button("Use profile", self._select)
        actions.append(self.select_button)
        actions.append(button("Cancel", self.close))
        self.body.append(actions)
        self.body.append(button("Profile settings…", self._edit))
        try:
            self._refresh(selected_ref)
        except (ValueError, OSError):
            self.destroy()
            raise
        self._guard_id = GLib.timeout_add(250, self._guard)
        self.connect("close-request", self._closed)
        self.connect("destroy", self._closed)
        self._guard()
        if settings:
            self._edit()

    def _closed(self, *_args):
        if self._guard_id:
            GLib.source_remove(self._guard_id)
            self._guard_id = 0
        return False

    def _guard(self):
        allowed = self.can_modify()
        self.select_button.set_sensitive(allowed and self.can_select())
        if not allowed:
            self.message.set_text("Profile changes are unavailable while work is active or the case has changed.")
        return True

    def _refresh(self, selected=None):
        registry = self.store.read_registry()
        self.revision_heads = dict(registry["heads"])
        self.expected_default = registry["default"]
        self.candidates = list(api.profile_catalog(store=self.store))
        self.options = [None] if self.allow_legacy else []
        self.options.extend(self.candidates)
        while self.list.get_first_child() is not None:
            self.list.remove(self.list.get_first_child())
        selected_index = 0
        for index, candidate in enumerate(self.options):
            ref = candidate.snapshot.ref if candidate else None
            current = self.case_confirmed and (ref == self.selected_ref or
                      (ref is not None and self.selected_ref is not None and ref.specialty_id == self.selected_ref.specialty_id))
            name = candidate.snapshot.manifest["display_name"] if candidate else "Existing settings"
            row = Gtk.ListBoxRow()
            box = Gtk.Box(spacing=8, margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
            box.append(wrapped(name, hexpand=True))
            if current:
                box.append(Gtk.Image(icon_name="object-select-symbolic"))
                row.update_property([Gtk.AccessibleProperty.DESCRIPTION], ["Current profile"])
            row.set_child(box)
            row.update_property([Gtk.AccessibleProperty.LABEL], [name])
            self.list.append(row)
            if selected is not None and ref and ref.specialty_id == selected.specialty_id:
                selected_index = index
        self.list.select_row(self.list.get_row_at_index(selected_index))
        self._describe_choice()

    def _selected(self):
        row = self.list.get_selected_row()
        if row is None:
            raise ProfileError("choose_profile", "profiles")
        return self.options[row.get_index()]

    def _describe_choice(self):
        if not self.options or self.list.get_selected_row() is None:
            return
        candidate = self._selected()
        notice = candidate.notice if candidate else ""
        if candidate and self.selected_ref and candidate.snapshot.ref.specialty_id == self.selected_ref.specialty_id and candidate.snapshot.ref != self.selected_ref:
            notice = "This case uses earlier settings." + ("\n" + notice if notice else "")
        self.context_group.set_description(notice)

    def _select(self):
        if not self.can_modify() or not self.can_select():
            self._guard()
            return
        try:
            candidate = self._selected()
            ref = None
            if candidate:
                snapshot = candidate.snapshot
                self.preview(snapshot)
                ref = self.store.managed_save(snapshot, expected_head=self.revision_heads.get(snapshot.ref.specialty_id),
                                              expected_default=self.expected_default, personal=candidate.personal,
                                              can_modify=self.can_modify)
            self.on_select(ref)
            self.selected_ref = ref
            self.case_confirmed = True
            self.message.set_text("Profile selected. Existing summaries and answers were not regenerated.")
            self._refresh(ref)
        except (ValueError, OSError):
            self.message.set_text("The profile could not be selected. Case settings were not changed; reopen the saved settings before retrying.")

    def _edit(self):
        try:
            candidate = self._selected()
            if candidate is None:
                candidate = next(item for item in self.candidates if item.snapshot.ref.specialty_id == "general-court-record")
            notice = candidate.notice
            editor = ProfileEditorWindow(self.get_transient_for() if self.settings_only else self, editable_profile(candidate.snapshot), self.store,
                                         expected_head=self.revision_heads.get(candidate.snapshot.ref.specialty_id),
                                         can_modify=self.can_modify, preview=self.preview, on_saved=self._saved,
                                         candidates=self.candidates, notice=notice, personal=candidate.personal,
                                         expected_heads=self.revision_heads, case_ref=lambda: self.selected_ref)
            self.children_windows.append(editor)
            def closed(window):
                if window in self.children_windows:
                    self.children_windows.remove(window)
                if self.settings_only:
                    self.destroy()
            editor.connect("destroy", closed)
            editor.present()
            return editor
        except (ValueError, OSError):
            self.message.set_text("Profile settings are unavailable. Existing output remains readable.")

    def _saved(self, ref):
        self._refresh(ref)
        eligible = (self.selected_ref is not None and self.selected_ref.specialty_id == ref.specialty_id) or (
            self.case_confirmed and self.selected_ref is None and ref.specialty_id == "california-juvenile-dependency")
        if not eligible or not self.can_select():
            return
        def respond(response):
            if response != "use":
                return
            try:
                if not self.can_modify() or not self.can_select():
                    raise ProfileError("case_changed_or_active", "selection")
                self.on_select(ref)
                self.selected_ref = ref
                self.case_confirmed = True
                self._refresh(ref)
                for editor in self.children_windows:
                    editor.refresh_case_notice()
            except (ValueError, OSError):
                text = "Profile saved; case settings were not changed."
                self.message.set_text(text)
                for editor in self.children_windows:
                    editor.saved_apply_failed = True
                    editor.message.set_text(text)
        parent = self.children_windows[-1] if self.children_windows else self
        self.apply_dialog = confirmation(parent, "Use these settings for this case?",
                                         "Existing summaries and answers will not be regenerated.",
                                         (("use", "Use settings"), ("later", "Not now")), respond)
        return self.apply_dialog
