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
                 selected_ref=None, customization=None, can_select=None, settings=False, case_ref=None, case_confirmed=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.parent_window = parent
        self.store = api.profile_store()
        self.can_modify, self.preview, self.on_select = can_modify, preview, on_select
        self.can_select = can_select or (lambda: True)
        self.allow_legacy, self.selected_ref = allow_legacy, case_ref
        self.case_confirmed = case_confirmed
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
                                              can_modify=self.can_modify)
            self.on_select(ref)
            self.selected_ref = ref
            self.case_confirmed = True
            self.message.set_text("")
            self._refresh(ref)
            return True
        except (ValueError, OSError):
            self.message.set_text("The profile could not be selected. Case settings were not changed; reopen the saved settings before retrying.")
            return False

    def _edit(self):
        try:
            candidate = self._selected()
            if candidate is None:
                candidate = next(item for item in self.candidates if item.snapshot.ref.specialty_id == "general-court-record")
            editor = ProfileEditorWindow(self.parent_window, editable_profile(candidate.snapshot), self.store,
                                         expected_head=self.revision_heads.get(candidate.snapshot.ref.specialty_id),
                                         can_modify=self.can_modify, preview=self.preview, on_saved=self._saved,
                                         candidates=self.candidates, notice=candidate.notice, personal=candidate.personal,
                                         expected_heads=self.revision_heads, case_ref=lambda: self.selected_ref)
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
        parent = self.children_windows[-1] if self.children_windows else self.parent_window
        self.apply_dialog = confirmation(parent, "Use these settings for this case?",
                                         "Existing summaries and answers will not be regenerated.",
                                         (("use", "Use settings"), ("later", "Not now")), respond)
        return self.apply_dialog
