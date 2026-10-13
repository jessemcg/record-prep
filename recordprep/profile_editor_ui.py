"""Lawyer-facing typed profile settings, vendored identically by both apps."""
from __future__ import annotations

import copy
import re
import uuid
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango, GObject

from . import practice_profiles as api
from .profile_contract import ProfileError, ProfileSnapshot, RETIRED_SUMMARY_RESOURCES
from .profile_workflows import ProfileEditor
from .profile_store import BUILTIN_SPECIALTIES

SUMMARY_TITLE = "Topic-guided agentic summarization"
SUMMARY_PROGRESSION = "Each hearing / report → Topic digest + quotes → Narrative section → Hearing / report summary"
SUMMARY_EXPLANATION = (
    "Capture what matters, whether a hearing or report has a few relevant passages or is dense with important information. "
    "Topics guide selection; detail follows substance, not a word count or a quota.\n\n"
    "Stage 1 — Build digests: an agent reads each complete hearing or report, across all its pages, and captures material "
    "information by topic, with supporting source quotes. Personalize what it captures by editing the topic names "
    "and instructions below. Each topic can be brief or detailed according to its substantive importance.\n\n"
    "Stage 2 — Write narratives: after the digests are ready, a synthesis agent works hearing by hearing or report "
    "by report, weaving each hearing’s or report’s digest into a cohesive narrative section with short direct quotes. "
    "It connects developments without repeating carried-forward history; hearings and reports have separate final summaries. "
    "Topics organize the digest, not the final narrative’s headings."
)
CLASSIFICATION_PROGRESSION = "Page types → First pages → Dates & names → Table of contents → Boundaries"
CLASSIFICATION_EXPLANATION = (
    "The vision model reads page images to both classify pages and extract information, such as dates and document names. "
    "Common guidance is combined with the instructions for the current page-type, first-page or date task; "
    "document naming uses separate instructions.\n\n"
    "Reporter’s transcript (RT): Basic separates hearing dialogue from covers and indexes; Advanced marks hearing starts; "
    "Dates reads their dates. Hearing labels use those dates, not a separate name prompt.\n\n"
    "Clerk’s transcript (CT): Basic separates minute orders, reports and forms; Advanced marks minute-order and form starts; "
    "Dates reads minute-order dates. Names uses separate naming instructions to read report names and dates "
    "at the start of each continuous group of report pages, and form names on marked first pages.\n\n"
    "Each stage builds on earlier results: page types guide first-page checks, and first pages guide date and name extraction. "
    "The resulting labels help build the table of contents; later boundary stages determine each document’s page range."
)
CLASSIFICATION_PAGES = (
    ("rt", "Reporter transcript pages", "RT · Basic"),
    ("first_hearing", "Hearing first pages", "RT · Advanced"),
    ("date_hearing", "Hearing dates", "RT · Dates"),
    ("ct", "Clerk transcript pages", "CT · Basic"),
    ("first_minute", "Minute-order first pages", "CT · Advanced"),
    ("first_form", "Form first pages", "CT · Advanced"),
    ("date_minute", "Minute-order dates", "CT · Dates"),
    ("report-naming", "Report names and dates", "CT · Names"),
    ("form-naming", "Form naming instructions", "CT · Names"),
)


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


def topic_editor_text(text):
    """Unwrap prose for display only; opening a topic never rewrites its resource.

    Keep paragraph separators and structured blocks (lists, headings, code,
    quotations and explicit Markdown line breaks) verbatim. Once edited, the
    displayed text becomes the user's draft through the normal Save flow.
    """
    blocks = re.split(r"(\n[ \t]*\n)", text)
    for index in range(0, len(blocks), 2):
        lines = blocks[index].split("\n")
        structured = any(
            re.match(r"^(?:\s*(?:[-+*] |\d+[.)] |[#>`~|])| {4}|\t)", line)
            or line.endswith(("  ", "\\")) for line in lines
        )
        if not structured:
            blocks[index] = re.sub(r"(?<=\S)[ \t]*\n[ \t]*(?=\S)", " ", blocks[index])
    return "".join(blocks)


def text_editor(text, changed=None, *, label="Instructions", tall=False):
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
    scroll = Gtk.ScrolledWindow(min_content_height=360 if tall else 120,
                                max_content_height=900 if tall else 280,
                                propagate_natural_height=not tall, vexpand=tall)
    scroll.add_css_class("card")
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_child(view)
    return scroll


class ProfileSelector(Gtk.MenuButton):
    """Full-width wrapping names in both selected value and keyboard popup."""
    def __init__(self, names, changed=None, *, menu_style=False):
        super().__init__(hexpand=True)
        self.names = list(names)
        self.selected = 0
        self.changed = changed
        self.label = wrapped("")
        attributes = Pango.AttrList()
        if menu_style:
            self.add_css_class("flat")
            attributes.insert(Pango.attr_weight_new(Pango.Weight.NORMAL))
            self.label.set_attributes(attributes)
        self.label.set_hexpand(True)
        self.label.set_max_width_chars(36)
        selected_box = Gtk.Box(spacing=8)
        selected_box.append(self.label)
        selected_box.append(Gtk.Image(icon_name="pan-down-symbolic"))
        self.set_child(selected_box)
        self.update_property([Gtk.AccessibleProperty.LABEL], ["Profile"])
        self.popover = Gtk.Popover()
        scroll = Gtk.ScrolledWindow(max_content_height=380, propagate_natural_height=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0 if menu_style else 4)
        for index, name in enumerate(self.names):
            item = button("", lambda index=index: self._choose(index))
            margin = 0 if menu_style else 8
            label = wrapped(name, max_width_chars=36, margin_start=margin, margin_end=margin,
                            margin_top=margin, margin_bottom=margin)
            if menu_style:
                item.add_css_class("profile-menu-item")
                label.set_attributes(attributes)
            item.set_child(label)
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
    _navigation_style = None

    def __init__(self, parent, editor: ProfileEditor, store, *, expected_head,
                 can_modify, preview, on_saved, candidates=None, notice="", personal=False, expected_heads=None, case_ref=lambda: None, on_deleted=lambda _ref: None):
        # No transient relationship: GNOME attaches transient dialogs to their parent.
        super().__init__(application=parent.get_application(), modal=False, resizable=True,
                         title="Profile settings", default_width=1040, default_height=800,
                         width_request=360, height_request=480)
        if ProfileEditorWindow._navigation_style is None:
            provider = Gtk.CssProvider()
            provider.load_from_data(b"""
                /* Match Model settings: the boxed list sits on the window
                   background, not a contrasting full-height sidebar panel.
                   Narrow overlay panes retain their opaque native styling. */
                .profile-settings-layout > .sidebar-pane {
                    background: transparent;
                    color: inherit;
                    box-shadow: none;
                }
                /* Keep the explanation as plain text on the window surface,
                   not a contrasting content-pane or label panel. */
                .profile-settings-layout > .content-pane,
                .profile-settings-content,
                .profile-classification-explainer,
                .profile-classification-explainer > label {
                    background: transparent;
                    border: none;
                    box-shadow: none;
                }
                .profile-navigation row.profile-destination { min-height: 40px; }
                .profile-navigation row.profile-destination > box {
                    min-height: 40px;
                    padding-top: 0;
                    padding-bottom: 0;
                }
            """)
            Gtk.StyleContext.add_provider_for_display(self.get_display(), provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            ProfileEditorWindow._navigation_style = provider
        self.editor, self.store = editor, store
        self.expected_head, self.can_modify = expected_head, can_modify
        self.preview, self.on_saved = preview, on_saved
        self.expected_heads = dict(expected_heads if expected_heads is not None else store.read_registry()["heads"])
        self.candidates = list(candidates or api.profile_catalog(store=store))
        self.personal = personal
        self.notice = notice
        self.case_ref = case_ref
        self.on_deleted = on_deleted
        self._closing = False
        self._loading = False
        self._guard_id = 0
        self._active_page = "profile"
        self._nav_updating = False
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_decoration_layout(":minimize,maximize,close")
        self.title_widget = Adw.WindowTitle(title="Profile settings")
        header.set_title_widget(self.title_widget)
        self.sidebar_button = Gtk.ToggleButton(icon_name="sidebar-show-symbolic", tooltip_text="Show categories")
        self.sidebar_button.add_css_class("flat")
        header.pack_start(self.sidebar_button)
        header.pack_start(button("Cancel", self.close))
        self.save_button = button("Save", self._save)
        header.pack_end(self.save_button)
        toolbar.add_top_bar(header)
        self.message = wrapped("", margin_start=18, margin_end=18, selectable=True)
        self.message.set_visible(False)
        self.message.connect("notify::label", lambda label, _spec: label.set_visible(bool(label.get_text())))
        outer.append(self.message)
        self.profile_notice = wrapped("", margin_start=18, margin_end=18)
        outer.append(self.profile_notice)
        self.case_notice = wrapped("", margin_start=18, margin_end=18)
        outer.append(self.case_notice)
        self.body = Adw.OverlaySplitView(vexpand=True, min_sidebar_width=220, max_sidebar_width=260,
                                         sidebar_width_fraction=.26)
        self.body.add_css_class("profile-settings-layout")
        self.body.bind_property("show-sidebar", self.sidebar_button, "active",
                                GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.body.bind_property("collapsed", self.sidebar_button, "visible", GObject.BindingFlags.SYNC_CREATE)
        outer.append(self.body)
        toolbar.set_content(outer)
        self.set_content(toolbar)
        breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 700sp"))
        breakpoint.add_setter(self.body, "collapsed", True)
        breakpoint.add_setter(self.body, "show-sidebar", False)
        self.add_breakpoint(breakpoint)
        self._render()
        self._guard_id = GLib.timeout_add(250, self._refresh_guard)
        self.connect("close-request", self._close_request)
        self.connect("destroy", self._destroyed)
        self._refresh_guard()

    def _state(self):
        return copy.deepcopy((self.editor.manifest, self.editor.resources,
                              self.default_row.get_active() if self.default_row is not None else None))

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
        blocked = "Settings cannot be changed while work is active or the case has changed. Your draft is kept; cancel and reopen when ready."
        if not allowed:
            self.message.set_text(blocked)
        elif self.message.get_text() == blocked:
            self.message.set_text("")
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
        self._nav_updating = True
        self.pages = {}
        self.nav_groups = {}
        self.nav_rows = {}
        self.nav_markers = {}
        self.page_groups = {}
        self.stack = Gtk.Stack(hexpand=True, vexpand=True, hhomogeneous=False, vhomogeneous=False)
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.add_css_class("profile-settings-content")
        self.classification_explainer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
            margin_start=18, margin_end=18, margin_top=12, visible=False)
        self.classification_explainer.add_css_class("profile-classification-explainer")
        explanation_title = wrapped("How classification builds the record")
        explanation_title.add_css_class("heading")
        self.classification_explainer.append(explanation_title)
        progression = wrapped(CLASSIFICATION_PROGRESSION)
        progression.add_css_class("accent")
        progression.add_css_class("heading")
        self.classification_explainer.append(progression)
        # A selectable label can receive focus/selection, painting persistent
        # inactive-selection rectangles after focus moves.
        # This is explanation text, not an editor or a focus/selection target.
        self.classification_explainer.append(wrapped(CLASSIFICATION_EXPLANATION))
        content.append(self.classification_explainer)
        self.summary_explainer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
            margin_start=18, margin_end=18, margin_top=12, visible=False)
        self.summary_explainer.add_css_class("profile-classification-explainer")
        summary_title = wrapped(SUMMARY_TITLE)
        summary_title.add_css_class("heading")
        self.summary_explainer.append(summary_title)
        summary_progression = wrapped(SUMMARY_PROGRESSION)
        summary_progression.add_css_class("accent")
        summary_progression.add_css_class("heading")
        self.summary_explainer.append(summary_progression)
        self.summary_explainer.append(wrapped(SUMMARY_EXPLANATION))
        content.append(self.summary_explainer)
        content.append(self.stack)
        self.body.set_content(content)
        self.navigation = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, valign=Gtk.Align.START,
                                      margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
        self.navigation.add_css_class("boxed-list")
        self.navigation.add_css_class("profile-navigation")
        sidebar = Gtk.ScrolledWindow(vexpand=True)
        sidebar.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar.set_child(self.navigation)
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.append(sidebar)
        self.body.set_sidebar(sidebar_box)
        self.title_widget.set_subtitle(self.editor.manifest["display_name"])
        self.title_widget.set_tooltip_text(self.editor.manifest["display_name"])
        self.profile_notice.set_text(self.notice)
        self.profile_notice.set_visible(bool(self.notice))
        self.refresh_case_notice()
        self.expected_default = self.store.read_registry()["default"]
        self.default_row = None
        if self.store.application == "focus":
            self._general_form()
            self._prompt_page("Research", "research", "Research instructions", "research")
            self._prompt_page("Answers", "answer", "Answer-writing instructions", "answer_guidance")
            labels = {"query_terms": "Question terms", "document_terms": "Document priorities",
                      "passage_terms": "Passage priorities", "later_history_terms": "Later-history priorities"}
            for key, label in labels.items():
                self._page("Search priorities", key, label)
                group = self._group(label, "Preferences help rank results; they never exclude any part of the record.")
                self._terms(group, self.editor.resources["search"], key, label)
        else:
            self._recordprep_form()
        self._nav_updating = False
        self._select_page(self._active_page if self._active_page in self.pages else next(iter(self.pages)))
        self._saved_state = self._state()
        self._loading = False

    def _general_form(self):
        self._page("General", "profile", "Profile and defaults")
        identity = self.editor.manifest["specialty_id"]
        names = [item.snapshot.manifest["display_name"] for item in self.candidates]
        index = next((i for i, item in enumerate(self.candidates) if item.snapshot.ref.specialty_id == identity), None)
        if index is None:
            names.append(self.editor.manifest["display_name"])
            # Draft exists only in this editor, never in the registry.
        self.selector = ProfileSelector(names, self._switch)
        self.selector.set_selected(index if index is not None else len(names) - 1, notify=False)
        group = self._group("Profile and defaults")
        group.add(self.selector)
        group.add(button("Create profiles", self._new))
        registry = self.store.read_registry()
        self.expected_default = registry["default"]
        self.default_row = Adw.SwitchRow(title="Use for new cases")
        self.default_row.set_active(bool(registry["default"] and registry["default"]["specialty_id"] == identity)
                                   or (registry["default"] is None and identity == "general-court-record"))
        group.add(self.default_row)

    def refresh_case_notice(self):
        ref = self.case_ref()
        earlier = ref is not None and ref.specialty_id == self.editor.manifest["specialty_id"] and ref != self.editor.base.ref
        self.case_notice.set_text("This case uses earlier settings. Saving does not change this case." if earlier else "")
        self.case_notice.set_visible(earlier)

    def _page(self, category, key, title):
        if category not in self.nav_groups:
            row = Adw.ExpanderRow(title=category)
            row.set_title_lines(2)
            row.connect("notify::expanded", self._category_expanded, category)
            self.navigation.append(row)
            self.nav_groups[category] = row
        row = Adw.ActionRow(title=title, activatable=True)
        row.add_css_class("profile-destination")
        row.set_title_lines(2)
        marker = Gtk.Image(icon_name="object-select-symbolic", visible=False)
        row.add_suffix(marker)
        row.connect("activated", lambda _row: self._select_page(key))
        self.nav_groups[category].add_row(row)
        self.nav_rows[key], self.nav_markers[key], self.page_groups[key] = row, marker, category
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18, vexpand=True,
                       margin_start=18, margin_end=18, margin_top=18, margin_bottom=18)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(body)
        self.stack.add_named(scroll, key)
        self.pages[key] = scroll
        self._page_body = body

    def _category_expanded(self, row, _spec, category):
        if self._nav_updating or not row.get_expanded():
            return
        key = self._active_page if self.page_groups.get(self._active_page) == category else next(
            key for key, value in self.page_groups.items() if value == category)
        # Expanding a category reveals its children; choosing a child dismisses
        # the narrow-window overlay, not merely expanding its parent.
        self._select_page(key, dismiss_sidebar=False)

    def _select_page(self, key, *, dismiss_sidebar=True):
        if key not in self.pages:
            return
        self._active_page = key
        self.stack.set_visible_child_name(key)
        self.classification_explainer.set_visible(self.store.application == "recordprep"
                                                 and self.page_groups[key] == "Classification")
        self.summary_explainer.set_visible(self.store.application == "recordprep"
                                          and self.page_groups[key] == "Summaries")
        self._nav_updating = True
        for category, row in self.nav_groups.items():
            row.set_expanded(category == self.page_groups[key])
        self._nav_updating = False
        for name, marker in self.nav_markers.items():
            marker.set_visible(name == key)
            self.nav_rows[name].update_property([Gtk.AccessibleProperty.DESCRIPTION],
                                                ["Current settings page" if name == key else ""])
        if dismiss_sidebar and self.body.get_collapsed():
            self.body.set_show_sidebar(False)

    def _prompt_page(self, category, key, title, resource, *, owner=None, field=None):
        self._page(category, key, title)
        self._guidance(self._group(title), resource, title, owner=owner, key=field)

    def _group(self, title, description=None):
        group = Adw.PreferencesGroup(title=title, description=description)
        self._page_body.append(group)
        return group

    def _guidance(self, group, resource, label, *, owner=None, key=None):
        owner = self.editor.resources if owner is None else owner
        key = resource if key is None else key
        if group.get_title() != label:
            group.add(wrapped(label, margin_top=6, margin_bottom=4))
        group.set_vexpand(True)
        group.add(text_editor(owner[key], lambda text: owner.__setitem__(key, text), label=label, tall=True))

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
                    displayed = value["guidance"] if roles else topic_editor_text(value["guidance"])
                    inner.append(text_editor(displayed, lambda text, value=value: value.__setitem__("guidance", text), label="Role instructions" if roles else "Topic instructions"))
                # Avoid FlowBoxChild's second hover background around the
                # flat buttons, as in the Create profiles action row.
                tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
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
        self._prompt_page("Classification", "classification", "Common guidance", "classification")
        self.nav_rows["classification"].set_subtitle("Shared · Basic / Advanced / Dates")
        for key, title, stage in CLASSIFICATION_PAGES:
            if key.endswith("-naming"):
                kind = key.removesuffix("-naming")
                self._prompt_page("Classification", key, title, "naming",
                                  owner=self.editor.resources["naming"], field=kind + "_guidance")
            else:
                self._prompt_page("Classification", key, title, "classification_tasks",
                                  owner=self.editor.resources["classification_tasks"], field=key)
            self.nav_rows[key].set_subtitle(stage)
        for kind, title in (("hearings", "Hearing"), ("reports", "Report")):
            self._page("Summaries", kind + "-topics", title + " digest topics")
            self._catalog(self._group(title + " digest topics"), self.editor.resources[kind])
            self.nav_rows[kind + "-topics"].set_subtitle("1 · Build digest")
        self._page("Summaries", "minutes", "Minute orders")
        group = self._group("Minute orders", "One agent summarizes each complete minute order directly, without a topic-digest stage.")
        self._guidance(group, "minutes", "Writing minute-order summaries")
        self._prompt_page("Participants / Witnesses", "participants", "Identification instructions", "participants")
        for key, title in (("counsel", "Counsel roles"), ("participants", "Participant roles")):
            self._page("Participants / Witnesses", key + "-roles", title)
            self._catalog(self._group(title), self.editor.resources["roles"][key], roles=True)
        self._prompt_page("Case Overview", "overview", "Overview instructions", "overview")

    def _new(self):
        if not self.can_modify():
            self._refresh_guard()
            return
        def open_dialog():
            if not self.can_modify():
                self._refresh_guard()
                return
            try:
                candidates = list(api.profile_catalog(store=self.store))
                registry = self.store.read_registry()
            except (ValueError, OSError):
                self.message.set_text("Profiles could not be verified. No settings were changed.")
                return
            dialog = Adw.Window(transient_for=self, modal=True, title="Create profiles", default_width=480)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=18, margin_end=18, margin_top=18, margin_bottom=18)
            heading = wrapped("Create profiles")
            heading.add_css_class("title-2")
            box.append(heading)
            box.append(wrapped("Create a profile"))
            box.append(wrapped("Name"))
            name = Gtk.Entry()
            name.update_property([Gtk.AccessibleProperty.LABEL], ["Name"])
            box.append(name)
            box.append(wrapped("Start with"))
            choice = ProfileSelector([item.snapshot.manifest["display_name"] for item in candidates])
            choice.set_selected(next(i for i, item in enumerate(candidates) if item.snapshot.ref.specialty_id == "general-court-record"), notify=False)
            box.append(choice)
            message = wrapped("")
            box.append(message)
            # FlowBoxChild adds its own hover background around flat buttons.
            # This is an action strip, not a selectable flow of items.
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                              halign=Gtk.Align.END)
            actions.append(button("Cancel", dialog.close))
            def create():
                if not self.can_modify():
                    message.set_text("The case changed or work is active. Close and reopen Create profiles.")
                    return
                value = name.get_text().strip()
                if not value:
                    message.set_text("Enter a profile name.")
                    return
                if len(value) > 160:
                    message.set_text("Enter a profile name with at most 160 characters.")
                    return
                if any(item.snapshot.manifest["display_name"].strip().casefold() == value.casefold() for item in candidates):
                    message.set_text("A profile with this name already exists. Choose another name.")
                    return
                self.editor = ProfileEditor.create(editable_profile(candidates[choice.get_selected()].snapshot).snapshot(), value)
                self.expected_head, self.personal, self.notice = None, True, ""
                self.message.set_text("New profile draft. Save to keep your settings.")
                self._render()
                # A new populated draft must still trigger Save/Discard/Cancel.
                self._saved_state = None
                dialog.close()
            actions.append(button("Create", create))
            box.append(actions)
            box.append(Gtk.Separator())
            box.append(wrapped("Delete a personal profile"))
            box.append(wrapped("Remove it from the chooser. Existing cases and saved revisions are kept. Built-in profiles cannot be deleted."))
            deletable = sorted((item for item in candidates if item.snapshot.ref.specialty_id not in BUILTIN_SPECIALTIES),
                               key=lambda item: item.snapshot.manifest["display_name"].casefold())
            self.delete_selector = None
            self.delete_button = None
            if deletable:
                selector = ProfileSelector([item.snapshot.manifest["display_name"] for item in deletable])
                selector.set_selected(next((index for index, item in enumerate(deletable)
                    if item.snapshot.ref.specialty_id == self.editor.manifest["specialty_id"]), 0), notify=False)
                self.delete_selector = selector
                box.append(selector)
                def delete():
                    if not self.can_modify():
                        message.set_text("The case changed or work is active. Close and reopen Create profiles.")
                        return
                    target = deletable[selector.get_selected()].snapshot
                    def respond(response):
                        if response != "delete":
                            return
                        try:
                            self.store.delete_profile(target.ref, expected_default=registry["default"],
                                                      can_modify=self.can_modify)
                        except (ValueError, OSError):
                            message.set_text("Profile could not be deleted. The profile or case may have changed; close and reopen Create profiles.")
                            return
                        # Deletion is committed. Never re-save/resurrect this identity
                        # from the editor, and never rebind an existing case.
                        dialog.close()
                        self.message.set_text("Profile deleted from the chooser. Existing cases are unchanged.")
                        try:
                            self.on_deleted(target.ref)
                            self.candidates = list(api.profile_catalog(store=self.store))
                            updated = self.store.read_registry()
                            self.expected_heads = dict(updated["heads"])
                            if self.editor.manifest["specialty_id"] == target.ref.specialty_id:
                                candidate = next(item for item in self.candidates if item.snapshot.ref.specialty_id == "general-court-record")
                                self.editor = editable_profile(candidate.snapshot)
                                self.expected_head = updated["heads"].get(candidate.snapshot.ref.specialty_id)
                                self.personal, self.notice = candidate.personal, candidate.notice
                                self._render()
                            else:
                                self.expected_default = updated["default"]
                        except (ValueError, OSError):
                            self.message.set_text("Profile deleted, but the settings or menu could not be refreshed. Close and reopen Profile settings.")
                    default_note = " It will no longer be the default for new cases." if registry["default"] and registry["default"]["specialty_id"] == target.ref.specialty_id else ""
                    self.delete_dialog = confirmation(dialog, "Delete profile?",
                        f'“{target.manifest["display_name"]}” will be removed from the chooser. Existing cases and saved revisions are kept.' + default_note,
                        (("delete", "Delete profile"), ("cancel", "Cancel")), respond)
                self.delete_button = button("Delete profile…", delete)
                self.delete_button.set_halign(Gtk.Align.END)
                box.append(self.delete_button)
            else:
                box.append(wrapped("No personal profiles to delete."))
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
                                           use_for_new_cases=self.default_row.get_active() if self.default_row is not None else None,
                                           personal=personal)
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
        editor.resources["policies"].pop("attendance", None)
        from .minute_summaries import minute_profile_text
        editor.resources["minutes"] = minute_profile_text(snapshot)
        if snapshot.manifest["schema_version"] == 1:
            general = api.validate_profile_directory(api.bundled_profile_directory("general")).draft
            editor.manifest["schema_version"] = 2
            for name in ("classification_tasks", "case_name"):
                editor.manifest["resources"][name] = general.manifest["resources"][name]
                editor.resources[name] = general.resource(name)
        editor.manifest["schema_version"] = 3
        for name in RETIRED_SUMMARY_RESOURCES:
            editor.manifest["resources"].pop(name, None)
            editor.resources.pop(name, None)
        from .document_naming import editable_naming
        editor.resources["naming"] = editable_naming(editor.resources["naming"])
    return editor
