"""Independent app-owned profile management; no sibling discovery or imports."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from . import practice_profiles as api
from .profile_contract import ProfileError, ProfileRef, parse_identity_descriptor, read_file_at
from .profile_editor_ui import ProfileEditorWindow, action_row, button, show_preview
from .profile_workflows import ProfileEditor, ReviewedFolder, export_identity


class ProfileManagerWindow(Adw.Window):
    def __init__(self, parent, *, can_modify, preview, on_select, context_text="", allow_legacy=True, selected_ref=None, customization=None, can_select=None):
        super().__init__(transient_for=parent, modal=True, title="Practice Profiles", default_width=820, default_height=680)
        self.store = api.profile_store()
        self.can_modify = can_modify
        self.preview = preview
        self.on_select = on_select
        self.allow_legacy = allow_legacy
        self.customization = customization
        self.can_select = can_select or (lambda: True)
        self.options = []
        self.revision_heads = {}
        self.children_windows = []
        self.mutating_buttons = []
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(Adw.HeaderBar())
        self.message = Gtk.Label(wrap=True, xalign=0, selectable=True, margin_start=18, margin_end=18, margin_top=8, margin_bottom=8)
        outer.append(self.message)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin_start=18, margin_end=18, margin_top=12, margin_bottom=18)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self.body)
        outer.append(scroll)
        self.set_content(outer)
        group = Adw.PreferencesGroup(title="Preparation and research", description=context_text or "Each app owns its guidance, revisions and defaults. Matching specialty identities do not imply identical instructions.")
        self.body.append(group)
        self.context_group = group
        self.choice = Adw.ComboRow(title="Profile / accepted revision")
        group.add(self.choice)
        self.revision_details = Gtk.Label(wrap=True, xalign=0, selectable=True)
        self.revision_details.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        group.add(self.revision_details)
        self.choice.connect("notify::selected", lambda *_args: self._describe_choice())
        self.default_row = Adw.ActionRow(title="Default for new contexts")
        group.add(self.default_row)
        actions = action_row()
        self.body.append(actions)
        self.select_button = self._action(actions, "Use for this case", self._select)
        self._action(actions, "Default for new contexts", self._default)
        self._action(actions, "Preview", self._preview, mutating=False)
        group = Adw.PreferencesGroup(title="Author profiles", description="Bundled resources and accepted snapshots are never overwritten. Edit saves a new complete folder/revision; existing case selections stay pinned.")
        self.body.append(group)
        actions = action_row()
        group.add(actions)
        self._action(actions, "Create from General", self._create)
        self._action(actions, "Duplicate", lambda: self._create(duplicate=True))
        self._action(actions, "Edit / Export…", self._edit)
        self._action(actions, "Register folder…", self._register)
        self._action(actions, "Review external edits", self._review_external)
        if customization is not None:
            group = Adw.PreferencesGroup(title="Private customization", description="Copy allowlisted legacy prose into a reviewable draft. No settings, case selections or defaults are changed. Credential/runtime fields are not copied; review prose for private details.")
            self.body.append(group)
            actions = action_row()
            group.add(actions)
            self._action(actions, "Copy legacy customization…", self._copy_customization)
        group = Adw.PreferencesGroup(title="Corresponding specialty in the other app", description="Identity exchange contains no instructions, paths or case data. The other app must independently author, accept and select its own profile.")
        self.body.append(group)
        actions = action_row()
        group.add(actions)
        self._action(actions, "Export identity…", self._export_identity)
        self._action(actions, "Import identity…", self._import_identity)
        self._refresh(selected_ref)
        self._guard_id = GLib.timeout_add(250, self._guard)
        self.connect("close-request", self._closed)
        self.connect("destroy", self._closed)
        self._guard()

    def _action(self, box, label, callback, *, mutating=True):
        widget = button(label, lambda: self._invoke(callback, mutating=mutating))
        box.append(widget)
        if mutating:
            self.mutating_buttons.append(widget)
        return widget

    def _invoke(self, callback, *, mutating=True):
        if mutating and not self.can_modify():
            self._guard()
            return
        try:
            callback()
        except (ValueError, OSError) as exc:
            self.message.set_text(f"Profile operation unavailable: {exc}. Check the current selection before retrying; an accepted/exported revision may remain.")

    def _closed(self, *_args):
        if self._guard_id:
            GLib.source_remove(self._guard_id)
            self._guard_id = 0
        return False

    def _guard(self):
        allowed = self.can_modify()
        for widget in self.mutating_buttons:
            widget.set_sensitive(allowed)
        self.select_button.set_sensitive(allowed and self.can_select())
        if not allowed:
            self.message.set_text("Profile changes are disabled while work is active or the case has changed. Reopen when ready.")
        return True

    def _refresh(self, selected=None):
        registry = self.store.read_registry()
        self.revision_heads = dict(registry["heads"])
        self.options = []
        labels = []
        if self.allow_legacy:
            self.options.append((None, None, False))
            labels.append("Legacy / unassigned — existing compatibility guidance")
        bundled = {}
        for name in api.BUNDLED_PROFILES:
            result = api.validate_profile_directory(api.bundled_profile_directory(name))
            if result.draft is None:
                raise ProfileError("invalid_bundled_profile", "profiles")
            snapshot = result.draft
            bundled[snapshot.ref.content_sha256] = snapshot
            self.options.append((snapshot, None, True))
            labels.append(f"Bundled · {snapshot.manifest['display_name']} · {snapshot.ref.version} · {snapshot.ref.content_sha256[:8]}")
        for entry in registry["accepted"]:
            ref = ProfileRef.from_dict(entry["ref"])
            if ref.content_sha256 in bundled:
                # Preserve a reviewed external source for the matching revision.
                if entry["source"]:
                    for index, (snapshot, source, shipped) in enumerate(self.options):
                        if snapshot is not None and snapshot.ref == ref:
                            self.options[index] = (snapshot, Path(entry["source"]), shipped)
                continue
            try:
                snapshot = self.store.load_profile_snapshot(ref)
            except (ProfileError, OSError):
                self.options.append((ref, None, False))
                labels.append(f"Unavailable · {ref.specialty_id} · {ref.version} · {ref.content_sha256[:8]}")
                continue
            self.options.append((snapshot, Path(entry["source"]) if entry["source"] else None, False))
            labels.append(f"Accepted · {snapshot.manifest['display_name']} · {ref.version} · {ref.content_sha256[:8]}")
        self.choice.set_model(Gtk.StringList.new(labels))
        if selected is not None:
            for index, (snapshot, _source, _shipped) in enumerate(self.options):
                ref = snapshot if isinstance(snapshot, ProfileRef) else (snapshot.ref if snapshot else None)
                if ref == selected:
                    self.choice.set_selected(index)
                    break
        self._describe_choice()
        default = registry["default"]
        self.default_row.set_subtitle("General Court Record (built-in default; existing contexts unchanged)" if default is None else f"{default['specialty_id']} · {default['version']} · {default['content_sha256'][:8]}")

    def _describe_choice(self):
        index = self.choice.get_selected()
        if not 0 <= index < len(self.options):
            self.revision_details.set_text("")
            return
        snapshot, _source, shipped = self.options[index]
        if snapshot is None:
            text = "Viewed choice: Legacy compatibility. Use for this case explicitly confirms it."
        else:
            unavailable = isinstance(snapshot, ProfileRef)
            ref = snapshot if unavailable else snapshot.ref
            name = ref.specialty_id if unavailable else snapshot.manifest["display_name"]
            origin = "Unavailable" if unavailable else ("Bundled, read-only" if shipped else "Accepted")
            text = f"Viewed revision — {origin}: {name} · {ref.version}\n{ref.specialty_id}\nSHA-256: {ref.content_sha256}"
        self.revision_details.set_text(text)

    def _selected(self):
        index = self.choice.get_selected()
        if not 0 <= index < len(self.options):
            raise ProfileError("choose_profile", "profiles")
        if isinstance(self.options[index][0], ProfileRef):
            raise ProfileError("snapshot_unavailable_choose_explicit_alternative", "profiles")
        return self.options[index]

    def _accept_selected(self):
        snapshot, source, _shipped = self._selected()
        if snapshot is None:
            return None
        # This explicit button action accepts shipped bytes if necessary; it
        # never adopts unreviewed bytes from an external source folder.
        if not any(entry["ref"] == asdict(snapshot.ref) for entry in self.store.read_registry()["accepted"]):
            self.store.accept_profile(snapshot, expected_previous_digest=self.revision_heads.get(snapshot.ref.specialty_id))
        self.store.load_profile_snapshot(snapshot.ref)
        return snapshot.ref

    def _select(self):
        if not self.can_select():
            raise ProfileError("select_case_first", "selection")
        ref = self._accept_selected()
        notice = self.on_select(ref)
        self.message.set_text(notice or "Explicit case choice saved. Existing outputs/answers were not regenerated or relabeled.")
        self._refresh(ref)

    def _default(self):
        ref = self._accept_selected()
        if ref is None:
            raise ProfileError("choose_profile_for_default", "profiles")
        self.store.set_default(ref)
        self._refresh(ref)
        self.message.set_text("Default changed for this app only. Existing case/session choices are unchanged.")

    def _open_editor(self, editor, expected):
        window = ProfileEditorWindow(self, editor, self.store, expected_head=expected,
                                     can_modify=self.can_modify, preview=self.preview, on_saved=self._saved)
        self.children_windows.append(window)
        window.connect("close-request", lambda widget: self._forget(widget))
        window.present()
        return window

    def _forget(self, window):
        if window in self.children_windows:
            self.children_windows.remove(window)
        return False

    def _saved(self, ref):
        self._refresh(ref)
        self.message.set_text("Accepted new revision. Use for this case or choose a default explicitly; neither happened automatically.")

    def _copy_customization(self):
        editor, notice = self.customization()
        window = self._open_editor(editor, None)
        window.body.prepend(Gtk.Label(label=notice, wrap=True, xalign=0, selectable=True))

    def _create(self, *, duplicate=False, identity=None):
        base = self._selected()[0] if duplicate else api.validate_profile_directory(api.bundled_profile_directory("general")).draft
        if base is None:
            raise ProfileError("choose_profile_to_duplicate", "profiles")
        editor = ProfileEditor.create(base, "New specialty", identity=identity)
        current = self.store.read_registry()["heads"].get(editor.manifest["specialty_id"])
        if current is not None:
            ref = next(ProfileRef.from_dict(entry["ref"]) for entry in self.store.read_registry()["accepted"] if entry["ref"]["content_sha256"] == current)
            self._refresh(ref)
            self.message.set_text("This specialty already exists locally. Use it or explicitly edit/review its revision; identity import did not overwrite it.")
            return
        self._open_editor(editor, None)

    def _edit(self):
        snapshot, source, shipped = self._selected()
        if snapshot is None:
            raise ProfileError("choose_profile_to_edit", "profiles")
        if shipped:
            self.message.set_text("Bundled profiles are read-only. Duplicate creates a new specialty in your chosen folder.")
            return
        editor = ProfileEditor(snapshot, source=source)
        self._open_editor(editor, self.revision_heads.get(snapshot.ref.specialty_id))

    def _preview(self):
        snapshot = self._selected()[0]
        if snapshot is None:
            self.message.set_text("Legacy compatibility uses existing guidance, not an assigned practice profile.")
            return
        window = show_preview(self, self.preview(snapshot))
        self.children_windows.append(window)
        window.connect("close-request", lambda widget: self._forget(widget))

    def _review(self, source):
        review = ReviewedFolder.inspect(self.store, source)
        # The full editor displays every field and the effective preview before
        # acceptance. Save creates a new complete folder, preserving the external
        # folder; direct acceptance is a separate explicit button below.
        window = self._open_editor(ProfileEditor(review.draft, source=source), review.expected_head)
        if review.expected_head is None:
            window.message.set_text("Review this new specialty before accepting. No case or default will be selected.")
        elif review.expected_head == review.draft.ref.content_sha256:
            window.message.set_text("These bytes are already accepted. Accept explicitly registers this external source folder for later change review.")
        else:
            window.message.set_text(f"Revision conflict/review: accepted {review.expected_head[:12]} → proposed {review.draft.ref.content_sha256[:12]}. Existing pinned cases keep their old revision.")
        accept = button("Accept reviewed folder", lambda: accept_review())
        window.body.prepend(accept)
        def accept_review():
            if not self.can_modify():
                return
            try:
                if window.editor.snapshot().ref != review.draft.ref:
                    raise ProfileError("edited_draft_requires_save", "review")
                ref = review.accept(self.store)
                self._saved(ref)
                window.close()
            except (ProfileError, OSError) as exc:
                window.message.set_text(f"Review must be repeated: {exc}")

    def _register(self):
        dialog = Gtk.FileDialog(title="Register an application-specific profile folder")
        def chosen(source, result):
            try:
                file = source.select_folder_finish(result)
            except GLib.Error:
                return
            if file.get_path():
                self._invoke(lambda: self._review(Path(file.get_path())))
        dialog.select_folder(self, None, chosen)

    def _review_external(self):
        _snapshot, source, _shipped = self._selected()
        if source is None:
            raise ProfileError("no_registered_external_folder", "review")
        self._review(source)

    def _export_identity(self):
        snapshot = self._selected()[0]
        if snapshot is None:
            raise ProfileError("choose_profile", "identity")
        dialog = Gtk.FileDialog(title="Export specialty identity only — new file", initial_name=f"{snapshot.ref.specialty_id}.identity.json")
        def chosen(source, result):
            try:
                file = source.save_finish(result)
            except GLib.Error:
                return
            if file.get_path():
                self._invoke(lambda: export_identity(snapshot, Path(file.get_path())))
        dialog.save(self, None, chosen)

    def _import_identity(self):
        dialog = Gtk.FileDialog(title="Import specialty identity — guidance is authored independently")
        def chosen(source, result):
            try:
                file = source.open_finish(result)
            except GLib.Error:
                return
            def load():
                path = file.get_path()
                if path is None:
                    raise ProfileError("local_file_required", "identity")
                path = Path(path)
                from .profile_store import _check_directory
                _check_directory(path.parent)
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    data = read_file_at(fd, path.name)
                finally:
                    os.close(fd)
                parse_identity_descriptor(data)
                # The selected local profile is an explicit starting point; if
                # legacy is highlighted, use this app's General resources.
                self._create(duplicate=self._selected()[0] is not None, identity=data)
            self._invoke(load)
        dialog.open(self, None, chosen)
