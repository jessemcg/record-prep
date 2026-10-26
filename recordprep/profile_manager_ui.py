"""Hamburger-menu profile controls, vendored identically by both apps."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Gio, Pango

from . import practice_profiles as api
from .profile_contract import ProfileError
from .profile_editor_ui import ProfileEditorWindow, ProfileSelector, button, wrapped, editable_profile, confirmation


_menu_style_provider = None


def install_profile_menu(menu, menu_button, open_controls):
    """Refresh case-bound controls on opening; inspection never persists settings."""
    global _menu_style_provider
    if _menu_style_provider is None:
        _menu_style_provider = Gtk.CssProvider()
        _menu_style_provider.load_from_data(b"""
            button.profile-menu-item, menubutton.profile-menu-item > button {
                padding: 3px 11px;
                min-height: 26px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(menu_button.get_display(), _menu_style_provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
    item = Gio.MenuItem.new(None, None)
    item.set_attribute_value("custom", GLib.Variant("s", "practice-profiles"))
    section = Gio.Menu()
    section.append_item(item)
    menu.prepend_section(None, section)
    popover = Gtk.PopoverMenu.new_from_model(menu)
    # Keep the menu open when its nested profile selector is dismissed.
    popover.set_cascade_popdown(False)
    slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    popover.add_child(slot, "practice-profiles")
    menu_button.set_popover(popover)

    def refresh(*_args):
        if not popover.get_visible():
            return
        while slot.get_first_child() is not None:
            slot.remove(slot.get_first_child())
        controls = open_controls()
        if controls is not None:
            slot.append(controls)
    popover.connect("notify::visible", refresh)


def menu_label(text):
    label = wrapped(text)
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_weight_new(Pango.Weight.NORMAL))
    label.set_attributes(attributes)
    return label


class ProfileManagerWindow(Gtk.Box):
    """Embedded controls: historical adapter name, no separate chooser window."""
    def __init__(self, parent, *, can_modify, preview, on_select, context_text="", allow_legacy=True,
                 selected_ref=None, customization=None, can_select=None, settings=False, case_ref=None, case_confirmed=True,
                 has_case=True, on_deleted=lambda _ref: None, on_storage_changed=lambda: None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.parent_window = parent
        self.store = api.profile_store()
        self.can_modify, self.preview, self.on_select = can_modify, preview, on_select
        self.can_select = can_select or (lambda: True)
        self.allow_legacy, self.selected_ref = allow_legacy, case_ref
        self.case_confirmed = case_confirmed
        self.has_case = has_case
        self.on_deleted = on_deleted
        self.on_storage_changed = on_storage_changed
        self.children_windows = []
        self._guard_id = 0
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.append(self.body)
        self.selector_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.append(self.selector_box)
        self.message = wrapped("", selectable=True, max_width_chars=36)
        self.message.set_visible(False)
        self.message.connect("notify::label", lambda label, _spec: label.set_visible(bool(label.get_text())))
        self.body.append(self.message)
        self.settings_button = button("", self._edit)
        self.settings_button.add_css_class("profile-menu-item")
        self.settings_button.set_child(menu_label("Profile settings"))
        self.body.append(self.settings_button)
        self.new_profile_button = None
        if self.store.application == "recordprep":
            self.new_profile_button = button("", self._new)
            self.new_profile_button.add_css_class("profile-menu-item")
            self.new_profile_button.set_child(menu_label("Create profiles"))
            self.body.append(self.new_profile_button)
        self.storage_button = button("", self._storage)
        self.storage_button.add_css_class("profile-menu-item")
        self.storage_button.set_child(menu_label("Profile storage…"))
        self.body.append(self.storage_button)
        self._refresh(selected_ref)
        self.connect("map", self._mapped)
        self.connect("unmap", self._closed)
        self._guard()
        if settings:
            self._edit()

    def _mapped(self, *_args):
        if not self._guard_id:
            self._guard_id = GLib.timeout_add(250, self._guard)
        self._guard()

    def _closed(self, *_args):
        if self._guard_id:
            GLib.source_remove(self._guard_id)
            self._guard_id = 0
        return False

    def _guard(self):
        allowed = self.can_modify()
        self.selector.set_sensitive(allowed and self.can_select())
        if self.new_profile_button is not None:
            self.new_profile_button.set_sensitive(allowed)
        self.storage_button.set_sensitive(allowed)
        blocked = "Profile changes are unavailable while work is active or the case has changed."
        if not allowed:
            self.message.set_text(blocked)
        elif self.message.get_text() == blocked:
            self.message.set_text("")
        return True

    def _refresh(self, selected=None):
        registry = self.store.read_registry()
        self.revision_heads = dict(registry["heads"])
        self.expected_default = registry["default"]
        self.candidates = list(api.profile_catalog(store=self.store))
        self.options = [None] if self.allow_legacy else []
        self.options.extend(self.candidates)
        while self.selector_box.get_first_child() is not None:
            self.selector_box.remove(self.selector_box.get_first_child())
        selected_index = 0
        names = []
        for index, candidate in enumerate(self.options):
            ref = candidate.snapshot.ref if candidate else None
            current = self.case_confirmed and (ref == self.selected_ref or
                      (ref is not None and self.selected_ref is not None and ref.specialty_id == self.selected_ref.specialty_id))
            name = candidate.snapshot.manifest["display_name"] if candidate else "Existing settings"
            names.append(name + (" ✓" if current else ""))
            if selected is not None and ref and ref.specialty_id == selected.specialty_id:
                selected_index = index
        self.selector = ProfileSelector(names, self._choice_changed, menu_style=True)
        self.selector.add_css_class("profile-menu-item")
        self.selector_box.append(self.selector)
        self.selector.set_selected(selected_index, notify=False)
        self._displayed_index = selected_index
        self._guard()

    def _choice_changed(self, _index):
        previous_index = self._displayed_index
        if not self._select():
            # Failed/blocked selection must not falsely appear to be current.
            self.selector.set_selected(previous_index, notify=False)

    def _selected(self):
        if not self.options:
            raise ProfileError("choose_profile", "profiles")
        return self.options[self.selector.get_selected()]

    def _select(self):
        if not self.can_modify() or not self.can_select():
            self._guard()
            return False
        try:
            candidate = self._selected()
            ref = None
            if candidate:
                snapshot = candidate.snapshot
                self.preview(snapshot)
                ref = self.store.managed_save(snapshot, expected_head=self.revision_heads.get(snapshot.ref.specialty_id),
                                              expected_default=self.expected_default, personal=candidate.personal,
                                              # One application-wide selection, independent of bundles.
                                              use_for_new_cases=True,
                                              can_modify=self.can_modify)
            self.selected_ref = ref
            self.case_confirmed = True
            self.message.set_text("")
        except (ValueError, OSError) as exc:
            if isinstance(exc, ProfileError):
                code = exc.issue.code
                if code in {"store_permissions", "unsafe_case_profile_directory", "unsafe_case_profile_file", "unsafe_store_directory"}:
                    reason = "Profile storage or case metadata has unsafe permissions or links."
                elif code in {"unaccepted_reference", "unreadable_snapshot", "snapshot_hash_mismatch"}:
                    reason = "A required saved profile revision is unavailable or could not be verified on this computer."
                elif code in {"stale_profile_revision", "stale_case_selection", "case_changed_or_active"}:
                    reason = "The case or saved settings changed; close and reopen this menu."
                else:
                    reason = f"Profile verification failed ({code})."
            else:
                reason = "Profile storage or case metadata could not be read or written."
            self.message.set_text("The profile could not be selected. " + reason)
            return False
        failed = False
        try:
            self.on_select(ref)  # Notification only: selection is already durable.
        except (ValueError, OSError):
            failed = True
        try:
            self._refresh(ref)
        except (ValueError, OSError):
            failed = True
        if failed:
            self.message.set_text("Profile selected, but the display could not be refreshed. Close and reopen the menu.")
        return True

    def _edit(self):
        # Menu widgets may be recreated between activations. Ownership belongs
        # to the application, not to one ephemeral popover's child list.
        existing = next((window for window in self.parent_window.get_application().get_windows()
                         if isinstance(window, ProfileEditorWindow) and window.get_visible()), None)
        if existing is not None:
            popover = self.get_ancestor(Gtk.Popover)
            if popover:
                popover.popdown()
            existing.present()
            return existing
        try:
            candidate = self._selected()
            if candidate is None:
                candidate = next(item for item in self.candidates if item.snapshot.ref.specialty_id == api.DEFAULT_PROFILE_ID)
            editor = ProfileEditorWindow(self.parent_window, editable_profile(candidate.snapshot), self.store,
                                         expected_head=self.revision_heads.get(candidate.snapshot.ref.specialty_id),
                                         can_modify=self.can_modify, preview=self.preview, on_saved=self._saved,
                                         candidates=self.candidates, notice=candidate.notice, personal=candidate.personal,
                                         expected_heads=self.revision_heads,
                                         case_ref=lambda: None,
                                         on_deleted=self._deleted)
            self.children_windows.append(editor)
            def closed(window):
                if window in self.children_windows:
                    self.children_windows.remove(window)
            editor.connect("destroy", closed)
            popover = self.get_ancestor(Gtk.Popover)
            if popover:
                popover.popdown()
            editor.present()
            return editor
        except (ValueError, OSError):
            self.message.set_text("Profile settings are unavailable. Existing output remains readable.")

    def _storage(self):
        if not self.can_modify():
            return
        import os
        if os.environ.get("RECORDPREP_PROFILE_DIR"):
            self.message.set_text("Profile storage is set by RECORDPREP_PROFILE_DIR. Remove that launch override to choose a folder here.")
            return
        def choose(action):
            if action not in {"save", "use"}:
                return
            dialog = Gtk.FileDialog(title=("Choose parent folder for portable profiles" if action == "save"
                                           else "Choose existing portable profile folder"))
            def selected(dialog, result):
                try:
                    folder = dialog.select_folder_finish(result)
                    if folder is None or folder.get_path() is None:
                        return
                    from pathlib import Path
                    from .profile_portability import save_portable_profiles, use_directory
                    root = Path(folder.get_path())
                    if action == "save":
                        root /= "RecordPrep profiles"
                        save_portable_profiles(self.store, root, can_modify=self.can_modify)
                    use_directory(root, can_modify=self.can_modify)
                    self.on_storage_changed()
                    self.message.set_text("Profile storage selected. Reopen the menu; existing bundles are unchanged.")
                except GLib.Error:
                    return  # File chooser cancellation.
                except (ValueError, OSError) as exc:
                    code = exc.issue.code if isinstance(exc, ProfileError) else "storage_error"
                    self.message.set_text("Profile storage was not selected (" + code + "). Existing settings are retained.")
            dialog.select_folder(self.parent_window, None, selected)
        return confirmation(self.parent_window, "Profile storage",
                            "Profiles are separate from case bundles. Save current profiles to a new ‘RecordPrep profiles’ folder, "
                            "or use an existing portable folder. Originals are kept. For a synchronized folder, close RecordPrep "
                            "and let synchronization finish before using it on another computer. Never edit on two computers at once.",
                            (("save", "Save to new folder…"), ("use", "Use existing folder…"), ("cancel", "Cancel")), choose)

    def _new(self):
        if not self.can_modify():
            self._guard()
            return None
        # Keep an open draft and its Save/Discard guard, rather than replacing it.
        editor = next((window for window in reversed(self.children_windows) if window.get_visible()), None)
        if editor is None:
            editor = self._edit()
        else:
            popover = self.get_ancestor(Gtk.Popover)
            if popover:
                popover.popdown()
            editor.present()
        if editor is not None:
            editor._new()
        return editor

    def _deleted(self, ref):
        pending_deleted = self.selected_ref is not None and self.selected_ref.specialty_id == ref.specialty_id
        if pending_deleted:
            self.selected_ref = None
        self.on_deleted(ref)
        if pending_deleted:
            self.selected_ref = api.default_profile_candidate(store=self.store).ref
        self._refresh(self.selected_ref)
        for editor in self.children_windows:
            editor.refresh_case_notice()

    def _saved(self, ref):
        self._refresh(ref)
        eligible = (self.selected_ref is not None and self.selected_ref.specialty_id == ref.specialty_id) or (
            self.case_confirmed and self.selected_ref is None and ref.specialty_id == "california-juvenile-dependency")
        if not eligible or not self.can_select():
            return
        if eligible:
            # Saving selected guidance advances the application selection.
            # No case-use confirmation or bundle write is necessary.
            try:
                if not self.can_modify():
                    raise ProfileError("case_changed_or_active", "selection")
                self.on_select(ref)
                self.selected_ref = ref
                self._refresh(ref)
            except (ValueError, OSError):
                self.message.set_text("Profile saved; refresh the menu to see the current selection.")
            return
