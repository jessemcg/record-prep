"""Lawyer-facing typed profile settings, vendored identically by both apps."""
from __future__ import annotations

import copy
import uuid
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango

from . import practice_profiles as api
from .profile_contract import ProfileError, ProfileSnapshot
from .profile_workflows import ProfileEditor

TOPIC_EXPLANATION = (
    "These topics tell the agent what to capture from each document. The captured information "
    "is then used to write the summary; the topics are not required headings in the final narrative."
)
POLICIES = {
    "attendance": (("explicit_complete_order", "Use explicit evidence from the complete order"),
                   ("legacy_first_page_parents", "Parents' personal appearance from the first page only")),
    "mode": (("source_title", "Use the source document's title"),
             ("approved_titles", "Use the approved titles below")),
}


def friendly(value):
    return value.replace("_", " ").replace("-", " ").capitalize()


def button(label: str, callback: Callable):
    widget = Gtk.Button(label=label)
    widget.add_css_class("flat")
    widget.connect("clicked", lambda _button: callback())
    return widget


def wrapped(text, **kwargs):
    return Gtk.Label(label=text, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0, **kwargs)


def action_row():
    return Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                       min_children_per_line=1, max_children_per_line=6, row_spacing=4, column_spacing=6)


def clear(box):
    while box.get_first_child() is not None:
        box.remove(box.get_first_child())


def text_editor(text, changed=None, *, label="Instructions"):
    view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, editable=changed is not None)
    view.update_property([Gtk.AccessibleProperty.LABEL], [label])
    view.set_left_margin(12)
    view.set_right_margin(12)
    view.set_top_margin(8)
    view.set_bottom_margin(8)
    buffer = view.get_buffer()
    buffer.set_text(text)
    if changed is not None:
        buffer.connect("changed", lambda source: changed(source.get_text(source.get_start_iter(), source.get_end_iter(), True)))
    scroll = Gtk.ScrolledWindow(min_content_height=120, max_content_height=280, propagate_natural_height=True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(view)
    return scroll


class ProfileSelector(Gtk.MenuButton):
    """Full-width wrapping names in both selected value and keyboard popup."""
    def __init__(self, names, changed=None):
        super().__init__(hexpand=True)
        self.names = list(names)
        self.selected = 0
        self.changed = changed
        self.label = wrapped("")
        self.label.set_hexpand(True)
        self.set_child(self.label)
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Profile"])
        self.popover = Gtk.Popover()
        scroll = Gtk.ScrolledWindow(max_content_height=380, propagate_natural_height=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for index, name in enumerate(self.names):
            item = button("", lambda index=index: self._choose(index))
            item.set_child(wrapped(name, margin_start=8, margin_end=8, margin_top=8, margin_bottom=8))
            item.update_property([Gtk.AccessibleProperty.LABEL], [name])
            rows.append(item)
        scroll.set_child(rows)
        self.popover.set_child(scroll)
        self.set_popover(self.popover)
        self.popover.connect("notify::visible", self._size_popup)
        self.set_selected(0, notify=False)

    def _size_popup(self, *_args):
        self.popover.get_child().set_size_request(max(200, self.get_width() - 24), -1)

    def _choose(self, index):
        self.popover.popdown()
        self.set_selected(index)

    def get_selected(self):
        return self.selected

    def set_selected(self, index, *, notify=True):
        if not 0 <= index < len(self.names):
            return
        self.selected = index
        self.label.set_text(self.names[index])
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Profile: " + self.names[index]])
        if notify and self.changed:
            self.changed(index)


def confirmation(parent, heading, body, responses, callback):
    dialog = Adw.MessageDialog(transient_for=parent, modal=True, heading=heading, body=body)
    for key, title in responses:
        dialog.add_response(key, title)
    dialog.set_close_response("cancel" if any(key == "cancel" for key, _ in responses) else responses[-1][0])
    dialog.set_default_response(dialog.get_close_response())
    def responded(widget, response):
        widget.destroy()
        callback(response)
    dialog.connect("response", responded)
    dialog.present()
    return dialog


def unavailable(parent):
    return confirmation(parent, "Profile settings unavailable",
                        "Saved profiles could not be verified. Existing output remains readable. No settings were changed.",
                        (("close", "Close"),), lambda _response: None)


class ProfileEditorWindow(Adw.Window):
    def __init__(self, parent, editor: ProfileEditor, store, *, expected_head,
                 can_modify, preview, on_saved, candidates=None, notice="", personal=False, expected_heads=None, case_ref=lambda: None):
        super().__init__(transient_for=parent, modal=True, title="Profile settings", default_width=820, default_height=760)
        self.editor, self.store = editor, store
        self.expected_head, self.can_modify = expected_head, can_modify
        self.preview, self.on_saved = preview, on_saved
        self.expected_heads = dict(expected_heads if expected_heads is not None else store.read_registry()["heads"])
        self.candidates = list(candidates or api.profile_catalog(store=store))
        self.personal = personal
        self.notice = notice
        self.case_ref = case_ref
        self._closing = False
        self._loading = False
        self._guard_id = 0
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        header.pack_start(button("Cancel", self.close))
        self.save_button = button("Save", self._save)
        header.pack_end(self.save_button)
        outer.append(header)
        self.message = wrapped("", margin_start=18, margin_end=18, selectable=True)
        outer.append(self.message)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                            margin_start=18, margin_end=18, margin_top=12, margin_bottom=18)
        scroll.set_child(self.body)
        outer.append(scroll)
        self.set_content(outer)
        self._render()
        self._guard_id = GLib.timeout_add(250, self._refresh_guard)
        self.connect("close-request", self._close_request)
        self.connect("destroy", self._destroyed)
        self._refresh_guard()

    def _state(self):
        return copy.deepcopy((self.editor.manifest, self.editor.resources, self.default_row.get_active()))

    def _dirty(self):
        return self._state() != self._saved_state

    def _destroyed(self, *_args):
        if self._guard_id:
            GLib.source_remove(self._guard_id)
            self._guard_id = 0

    def _close_request(self, *_args):
        if self._closing:
            self._destroyed()
            return False
        if self._dirty():
            self._unsaved(self._finish_close)
            return True
        self._destroyed()
        return False

    def _finish_close(self):
        self._closing = True
        self.close()

    def _unsaved(self, continuation):
        def respond(response):
            if response == "discard":
                continuation()
            elif response == "save" and self._save():
                def finished(*_args):
                    if not self.saved_apply_failed:
                        continuation()
                if self.saved_dialog is not None and self.saved_dialog.get_visible():
                    self.saved_dialog.connect("response", finished)
                else:
                    finished()
        self.unsaved_dialog = confirmation(self, "Save changes?", "You have unsaved profile settings.",
                                           (("save", "Save"), ("discard", "Discard"), ("cancel", "Cancel")), respond)
        return self.unsaved_dialog

    def _refresh_guard(self):
        allowed = self.can_modify()
        self.body.set_sensitive(allowed)
        self.save_button.set_sensitive(allowed)
        if not allowed:
            self.message.set_text("Settings cannot be changed while work is active or the case has changed. Your draft is kept; cancel and reopen when ready.")
        return True

    def _switch(self, index):
        if self._loading or index >= len(self.candidates):
            return
        candidate = self.candidates[index]
        if candidate.snapshot.ref == self.editor.base.ref:
            return
        previous = next((i for i, item in enumerate(self.candidates) if item.snapshot.ref == self.editor.base.ref), 0)
        self.selector.set_selected(previous, notify=False)
        def load():
            self.editor = editable_profile(candidate.snapshot)
            self.personal, self.notice = candidate.personal, candidate.notice
            self.expected_head = self.expected_heads.get(candidate.snapshot.ref.specialty_id)
            self.message.set_text("")
            self._render()
        if self._dirty():
            self._unsaved(load)
        else:
            load()

    def _render(self):
        self._loading = True
        clear(self.body)
        identity = self.editor.manifest["specialty_id"]
        names = [item.snapshot.manifest["display_name"] for item in self.candidates]
        index = next((i for i, item in enumerate(self.candidates) if item.snapshot.ref.specialty_id == identity), None)
        if index is None:
            names.append(self.editor.manifest["display_name"])
            # Draft exists only in this editor, never in the registry.
        self.selector = ProfileSelector(names, self._switch)
        self.selector.set_selected(index if index is not None else len(names) - 1, notify=False)
        self.body.append(self.selector)
        self.body.append(button("New profile…", self._new))
        if self.notice:
            self.body.append(wrapped(self.notice))
        self.case_notice = wrapped("")
        self.body.append(self.case_notice)
        self.refresh_case_notice()
        registry = self.store.read_registry()
        self.expected_default = registry["default"]
        group = self._group("")
        self.default_row = Adw.SwitchRow(title="Use for new cases")
        self.default_row.set_active(bool(registry["default"] and registry["default"]["specialty_id"] == identity)
                                   or (registry["default"] is None and identity == "general-court-record"))
        group.add(self.default_row)
        if self.store.application == "focus":
            self._guidance(self._group("Research instructions"), "research", "Research instructions")
            self._guidance(self._group("Answer-writing instructions"), "answer_guidance", "Answer-writing instructions")
            group = self._group("Search priorities", "Preferences help rank results; they never exclude any part of the record.")
            labels = {"query_terms": "Question terms", "document_terms": "Document priorities",
                      "passage_terms": "Passage priorities", "later_history_terms": "Later-history priorities"}
            for key, label in labels.items():
                self._terms(group, self.editor.resources["search"], key, label)
        else:
            self._recordprep_form()
        self._saved_state = self._state()
        self._loading = False

    def refresh_case_notice(self):
        ref = self.case_ref()
        earlier = ref is not None and ref.specialty_id == self.editor.manifest["specialty_id"] and ref != self.editor.base.ref
        self.case_notice.set_text("This case uses earlier settings. Saving does not change this case." if earlier else "")
        self.case_notice.set_visible(earlier)

    def _group(self, title, description=None):
        group = Adw.PreferencesGroup(title=title, description=description)
        self.body.append(group)
        return group

    def _guidance(self, group, resource, label, *, owner=None, key=None):
        owner = self.editor.resources if owner is None else owner
        key = resource if key is None else key
        group.add(wrapped(label, margin_top=6, margin_bottom=4))
        group.add(text_editor(owner[key], lambda text: owner.__setitem__(key, text), label=label))

    def _policy(self, group, owner, key, title):
        values = POLICIES[key]
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new([title for _, title in values]))
        row.set_selected(next(i for i, (value, _) in enumerate(values) if value == owner[key]))
        row.connect("notify::selected", lambda widget, _pspec: owner.__setitem__(key, values[widget.get_selected()][0]))
        group.add(row)

    def _terms(self, group, owner, key, label):
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        group.add(wrapped(label))
        group.add(holder)
        def render():
            clear(holder)
            for index, value in enumerate(owner[key]):
                row = Gtk.Box(spacing=4)
                entry = Gtk.Entry(text=value, hexpand=True)
                entry.update_property([Gtk.AccessibleProperty.LABEL], [label])
                entry.connect("changed", lambda widget, index=index: owner[key].__setitem__(index, widget.get_text()))
                row.append(entry)
                def remove(index=index):
                    del owner[key][index]
                    render()
                row.append(button("Remove", remove))
                holder.append(row)
            def add():
                owner[key].append("New term")
                render()
            holder.append(button("Add", add))
        render()

    def _catalog(self, group, values, *, roles=False, forms=False):
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        group.add(holder)
        def render():
            clear(holder)
            for index, value in enumerate(values):
                title_key = "name" if forms else "label" if roles else "title"
                card = Gtk.Expander()
                name = wrapped(value[title_key])
                card.set_label_widget(name)
                card.add_css_class("card")
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=12, margin_end=12, margin_top=8, margin_bottom=12)
                card.set_child(inner)
                holder.append(card)
                for key, label in (("name", "Form name"), ("title", "Required source title"), ("code", "Form code")) if forms else ((title_key, "Role name" if roles else "Topic name"),):
                    inner.append(wrapped(label))
                    entry = Gtk.Entry(text=value[key], hexpand=True)
                    entry.update_property([Gtk.AccessibleProperty.LABEL], [label])
                    def change(widget, key=key, value=value, name=name, title_key=title_key):
                        value[key] = widget.get_text()
                        if key == title_key:
                            name.set_text(value[key])
                    entry.connect("changed", change)
                    inner.append(entry)
                if not forms:
                    inner.append(text_editor(value["guidance"], lambda text, value=value: value.__setitem__("guidance", text), label="Role instructions" if roles else "Topic instructions"))
                tools = action_row()
                inner.append(tools)
                def move(offset, index=index):
                    other = index + offset
                    if 0 <= other < len(values):
                        values[index], values[other] = values[other], values[index]
                        render()
                up = button("Move up", lambda move=move: move(-1))
                up.set_sensitive(index > 0)
                tools.append(up)
                down = button("Move down", lambda move=move: move(1))
                down.set_sensitive(index < len(values) - 1)
                tools.append(down)
                if not roles or value.get("id") not in {"unknown", "other"}:
                    def remove(index=index):
                        del values[index]
                        render()
                    tools.append(button("Remove", remove))
            def add():
                values.append({"name": "New form", "title": "Source title", "code": "FORM-1"} if forms else
                              {"id": f"item-{uuid.uuid4().hex}", "label" if roles else "title": "New role" if roles else "New topic",
                               "guidance": "Capture material source-supported information."})
                render()
            holder.append(button("Add form" if forms else "Add role" if roles else "Add topic", add))
        render()

    def _recordprep_form(self):
        self._guidance(self._group("Case naming"), "case_name", "Deriving the case name")
        group = self._group("Document classification")
        self._guidance(group, "classification", "Common classification guidance")
        labels = {"rt": "Reporter transcript pages", "ct": "Clerk transcript pages", "first_hearing": "First page of a hearing",
                  "first_minute": "First page of a minute order", "first_form": "First page of a form",
                  "date_hearing": "Hearing dates", "date_minute": "Minute-order dates"}
        for task, label in labels.items():
            self._guidance(group, "classification_tasks", label, owner=self.editor.resources["classification_tasks"], key=task)
        group = self._group("Document naming")
        naming = self.editor.resources["naming"]
        review = getattr(self.editor, "review_notices", {}).get("naming")
        if review:
            group.add(wrapped(review))
        if self.notice and naming != api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft.resource("naming"):
            group.add(wrapped("Review your previous naming instructions alongside the title and form rules: custom prose does not automatically change the approved catalog."))
        self._policy(group, naming, "mode", "Naming rule")
        self._terms(group, naming, "report_titles", "Approved report titles")
        self._guidance(group, "naming", "Report naming instructions", owner=naming, key="report_guidance")
        self._catalog(group, naming["form_rules"], forms=True)
        self._guidance(group, "naming", "Form naming instructions", owner=naming, key="form_guidance")
        for kind, singular, title in (("hearings", "hearing", "Hearing summaries"), ("reports", "report", "Report summaries")):
            group = self._group(title, TOPIC_EXPLANATION)
            self._catalog(group, self.editor.resources[kind])
            self._guidance(group, singular + "_extraction", "Reviewing each document")
            self._guidance(group, singular + "_synthesis", "Writing the summary")
        group = self._group("Minute-order summaries")
        self._guidance(group, "minutes", "Writing minute-order summaries")
        self._policy(group, self.editor.resources["policies"], "attendance", "Attendance evidence")
        group = self._group("Participants and witnesses")
        for key, title in (("counsel", "Counsel roles"), ("participants", "Participant roles")):
            group.add(wrapped(title))
            self._catalog(group, self.editor.resources["roles"][key], roles=True)
        self._guidance(group, "participants", "Identifying participants and witnesses")
        self._guidance(self._group("Case overview"), "overview", "Writing the case overview")

    def _new(self):
        def open_dialog():
            dialog = Adw.Window(transient_for=self, modal=True, title="New profile", default_width=480)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=18, margin_end=18, margin_top=18, margin_bottom=18)
            box.append(wrapped("Name"))
            name = Gtk.Entry()
            name.update_property([Gtk.AccessibleProperty.LABEL], ["Name"])
            box.append(name)
            box.append(wrapped("Start with"))
            choice = ProfileSelector([item.snapshot.manifest["display_name"] for item in self.candidates])
            choice.set_selected(next(i for i, item in enumerate(self.candidates) if item.snapshot.ref.specialty_id == "general-court-record"), notify=False)
            box.append(choice)
            message = wrapped("")
            box.append(message)
            actions = action_row()
            actions.append(button("Cancel", dialog.close))
            def create():
                value = name.get_text().strip()
                if not value:
                    message.set_text("Enter a profile name.")
                    return
                if len(value) > 160:
                    message.set_text("Enter a profile name with at most 160 characters.")
                    return
                if any(item.snapshot.manifest["display_name"].strip().casefold() == value.casefold() for item in self.candidates):
                    message.set_text("A profile with this name already exists. Choose another name.")
                    return
                self.editor = ProfileEditor.create(editable_profile(self.candidates[choice.get_selected()].snapshot).snapshot(), value)
                self.expected_head, self.personal, self.notice = None, True, ""
                self.message.set_text("New profile draft. Save to keep your settings.")
                self._render()
                # A new populated draft must still trigger Save/Discard/Cancel.
                self._saved_state = None
                dialog.close()
            actions.append(button("Create", create))
            box.append(actions)
            dialog.set_content(box)
            dialog.present()
            self.new_dialog = dialog
        if self._dirty():
            self._unsaved(open_dialog)
        else:
            open_dialog()

    def _save(self):
        saved_ref = None
        self.saved_dialog = None
        self.saved_apply_failed = False
        if not self.can_modify():
            self._refresh_guard()
            return False
        try:
            draft = self.editor.snapshot()
            others = [item for item in api.profile_catalog(store=self.store) if item.snapshot.ref.specialty_id != draft.ref.specialty_id]
            if any(item.snapshot.manifest["display_name"].strip().casefold() == draft.manifest["display_name"].strip().casefold() for item in others):
                raise ProfileError("conflicting_profile_name", "name")
            personal = self.personal or draft.ref != self.editor.base.ref
            ref = self.editor.managed_save(self.store, expected_head=self.expected_head, expected_default=self.expected_default,
                                           validate=self.preview, can_modify=self.can_modify,
                                           use_for_new_cases=self.default_row.get_active(), personal=personal)
            saved_ref = ref
            self.expected_head = ref.content_sha256
            self.expected_default = self.store.read_registry()["default"]
            self.editor = ProfileEditor(self.store.load_profile_snapshot(ref))
            self._saved_state = self._state()
            self.personal = personal
            self.expected_heads = dict(self.store.read_registry()["heads"])
            self.candidates = list(api.profile_catalog(store=self.store))
            self._render()
            self.message.set_text("Profile saved.")
            self.saved_dialog = self.on_saved(ref)
            return True
        except (ProfileError, OSError, ValueError) as exc:
            if saved_ref is not None:
                self.saved_apply_failed = True
                self.message.set_text("Profile saved; case settings were not changed.")
                return True
            code = exc.issue.code if isinstance(exc, ProfileError) else "invalid_settings"
            if code in {"stale_profile_revision", "external_profile_changed"}:
                self.message.set_text("These settings changed elsewhere. Your draft is kept. Reopen the saved settings before saving again.")
            else:
                location = friendly(exc.issue.location) if isinstance(exc, ProfileError) else "Settings"
                self.message.set_text(f"{location}: check the entered settings. Nothing was selected or changed for the case.")
            return False


def editable_profile(snapshot):
    """Explicit edit upgrades a draft only; historical snapshot bytes stay intact."""
    editor = ProfileEditor(snapshot)
    if snapshot.ref.application == "recordprep":
        editor.resources["policies"].pop("report_scope", None)
        if snapshot.manifest["schema_version"] == 1:
            general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
            editor.manifest["schema_version"] = 2
            for name in ("classification_tasks", "case_name"):
                editor.manifest["resources"][name] = general.manifest["resources"][name]
                editor.resources[name] = general.resource(name)
        naming = editor.resources["naming"]
        if "schema_version" not in naming:
            known = api.validate_profile_directory(api.bundled_profile_directory("california_dependency")).draft.resource("naming")["form_rules"]
            rules = [copy.deepcopy(rule) for rule in known if rule["name"] in naming["form_titles"]]
            unresolved = [title for title in naming["form_titles"] if title not in {rule["name"] for rule in rules}]
            guidance = naming["guidance"]
            if unresolved:
                guidance += "\n\nPrevious approved form titles — review their source titles and codes:\n" + "\n".join(unresolved)
                editor.review_notices = {"naming": "Some historical form titles need their source title and code reviewed. The previous titles are preserved in the instructions below; no rules were invented."}
            editor.resources["naming"] = {"schema_version": 2, "mode": naming["mode"], "report_titles": naming["report_titles"],
                                          "form_rules": rules, "report_guidance": naming["guidance"], "form_guidance": guidance}
    return editor
