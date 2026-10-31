"""RecordPrep-owned typed profile settings and guarded explicit publication."""
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
from .settings_navigation import SettingsNavigation, install_editor_style, round_editor
from .profile_contract import ProfileError, ProfileSnapshot, RETIRED_SUMMARY_RESOURCES, RETIRED_PARTICIPANT_RESOURCES, RETIRED_OVERVIEW_RESOURCES
from .profile_workflows import ProfileEditor
from .profile_store import BUILTIN_SPECIALTIES
from .profile_contract import CLASSIFICATION_PAGE_TYPES, CLASSIFICATION_FIRST_PAGE_TYPES, classification_guidance_warning

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
    "Before classification, the “Detect transcript layout” step determines where the reporter’s transcript (RT) ends "
    "and the clerk’s transcript (CT) begins, or whether the record contains only RT or only CT pages. This effectively "
    "performs the first classification step. Here, RT pages and CT pages undergo further classification and information "
    "extraction through an image model that examines their corresponding images and returns results as JSON fields. "
    "First, the image model classifies the RT pages and CT pages into page types.\n\n"
    "For RT pages, the most important page type is the RT body page type, which contains dialogue from a given hearing. "
    "Once RT body pages are identified, the image model re-examines each one to determine whether it is the first page "
    "of a hearing. For CT pages, the most important page types are minute orders, reports, and forms. As with RT body "
    "pages, once these page types are identified, the image model re-examines each page to determine whether it is the "
    "first page of a minute order, report, or form. This allows the app to know the boundary of each hearing, "
    "minute order, report, and form.\n\n"
    "The image model also re-examines the first page of each hearing, minute order, report, and form to extract "
    "information. For each hearing and minute order, only the date is extracted. For each report, the name and date "
    "are extracted; for each form, only the name is extracted. Report and form names must match an approved name in "
    "the profile’s user-editable Report Names or Form Names list. Reports and forms without an accepted name are omitted from "
    "the table of contents, and unnamed reports are excluded from standalone report summaries. "
    "This ensures that only relevant reports and forms are identified."
)
CLASSIFICATION_PAGES = (
    ("rt", "Reporter transcript page types", "Basic"),
    ("ct", "Clerk transcript page types", "Basic"),
    ("first-pages", "First pages", "Advanced · hearing, minute order, form, report"),
    ("report-naming", "Report Names", "Names"),
    ("form-naming", "Form Names", "Names"),
)


# Home-outline membership only: follow-up tasks, not pipeline dependencies.
CLASSIFICATION_OUTLINE_GROUPS = {}  # Flat destinations, never priority.


def classification_task_contract(task):
    if task in CLASSIFICATION_PAGE_TYPES:
        return ('Basic output: JSON with the key page_type, using exactly one of: '
                + ', '.join(CLASSIFICATION_PAGE_TYPES[task])
                + '. First-page markers are added by Advanced, not Basic. Add practice-specific headings, '
                  'document examples and distinguishing clues without renaming or adding categories.')
    if task in CLASSIFICATION_FIRST_PAGE_TYPES:
        return ('Advanced output: JSON with the key first_page and the value yes or no. '
                'The application adds ' + CLASSIFICATION_FIRST_PAGE_TYPES[task]
                + ' when the answer is yes. Do not return that label yourself. Describe how to recognize '
                  'a genuine document or hearing start, not a continuation.')
    if task in ('date_hearing', 'date_minute'):
        return ('Dates output: JSON with the key date: a long-form U.S. date, or an empty string if unresolved. '
                'Explain where the relevant date appears and which competing dates to exclude.')
    raise ValueError("Unknown classification task")


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
    buffer.set_enable_undo(True)
    buffer.set_text(text)
    if changed is not None:
        buffer.connect("changed", lambda source: changed(source.get_text(source.get_start_iter(), source.get_end_iter(), True)))
    scroll = Gtk.ScrolledWindow(vexpand=tall)
    round_editor(scroll)
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
                         title="Profile settings", default_width=900, default_height=720)
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
        self.title_widget = Adw.WindowTitle(title="Profile settings")
        install_editor_style(self)
        # Each retained destination supplies its own Back/Save header. Keep
        # global notices below it, never above the window's native controls.
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        outer.append(self.body)
        self.message = wrapped("", margin_start=18, margin_end=18, selectable=True)
        self.message.set_visible(False)
        self.message.connect("notify::label", lambda label, _spec: label.set_visible(bool(label.get_text())))
        outer.append(self.message)
        self.profile_notice = wrapped("", margin_start=18, margin_end=18)
        outer.append(self.profile_notice)
        self.case_notice = wrapped("", margin_start=18, margin_end=18)
        outer.append(self.case_notice)
        toolbar.set_content(outer)
        self.set_content(toolbar)
        self._render()
        self._guard_id = GLib.timeout_add(250, self._refresh_guard)
        self.connect("close-request", self._close_request)
        self.connect("destroy", self._destroyed)
        self._refresh_guard()

    def _state(self):
        return copy.deepcopy((self.editor.manifest, self.editor.resources,
                              self.default_row.get_active() if self.default_row is not None else None))

    def _dirty(self):
        return bool(getattr(self, '_legacy_naming_error', False)) or self._state() != self._saved_state

    def _destroyed(self, *_args):
        self._closing = True
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
        if getattr(self, "unsaved_dialog", None) is not None and self.unsaved_dialog.get_visible():
            self.unsaved_dialog.present()
            return self.unsaved_dialog
        def respond(response):
            if response == "discard":
                continuation()
        self.unsaved_dialog = confirmation(self, "Discard unsaved changes?",
            "Only changes since the last successful Save will be discarded.",
            (("keep", "Keep Editing"), ("discard", "Discard Unsaved Changes")), respond)
        self.unsaved_dialog.set_close_response("keep")
        self.unsaved_dialog.set_default_response("keep")
        return self.unsaved_dialog

    def _refresh_guard(self):
        refresh_required = getattr(self, "_reset_refresh_required", False)
        allowed = self.can_modify() and not refresh_required
        self.body.set_sensitive(allowed)
        self.save_button.set_sensitive(allowed)
        if hasattr(self, "_navigation"):
            for save in self._navigation.save_buttons.values():
                save.set_sensitive(allowed)
        blocked = "Settings cannot be changed while work is active or the case has changed. Your draft is kept; cancel and reopen when ready."
        if refresh_required:
            self.message.set_text("Profile reset saved, refresh required. Close and reopen Profile settings and the profile menu before editing again.")
        elif not allowed:
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
        if hasattr(self, "_navigation"):
            self._navigation.headers["home"].set_title_widget(None)
        clear(self.body)
        self._navigation = SettingsNavigation(self._save, lambda: self._closing)
        self._navigation.headers["home"].set_title_widget(self.title_widget)
        self.save_button = self._navigation.save_buttons["home"]
        self._topic_editors = {}
        self._topic_expanders = {}
        self._topic_refreshers = {}
        self._guidance_bindings = []
        self._recognition_cards = {}
        self._recognition_pages = {}
        self._page_bodies = {}
        self._legacy_naming_buffer = None
        self._legacy_naming_error = False
        self._installing = False
        self.reset_dialog = None
        self.reset_button = None
        self.navigation = self._navigation.home_list
        self.body.append(self._navigation.view)
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
            self._bundled_action()
        self._nav_updating = False
        self._navigation.finish()
        self._active_page = "home"
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
                                   or (registry["default"] is None and identity == api.DEFAULT_PROFILE_ID))
        group.add(self.default_row)

    def refresh_case_notice(self):
        self.case_notice.set_text("New preparation uses the selected application profile. Existing output is not regenerated by Save.")
        self.case_notice.set_visible(True)

    def _page(self, category, key, title):
        if category not in self.nav_groups:
            row = self._navigation.add_category(category)
            row.set_title_lines(2)
            self.nav_groups[category] = row
        row = Adw.ActionRow(title=title, activatable=True)
        row.add_css_class("profile-destination")
        row.set_title_lines(2)
        marker = Gtk.Image(icon_name="go-next-symbolic")
        row.add_suffix(marker)
        row.connect("activated", lambda _row: self._select_page(key))
        self.nav_groups[category].add_row(row)
        self.nav_rows[key], self.nav_markers[key], self.page_groups[key] = row, marker, category
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True,
                       margin_start=12, margin_end=12, margin_top=12, margin_bottom=12)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(body)
        self._navigation.add_page(key, title, scroll, prompt=category == "Classification" or key == "minutes")
        self.pages[key] = scroll
        self._page_bodies[key] = body
        self._page_body = body
        self._building_page = key

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
        self._navigation.open(key, self.nav_rows.get(key))

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
        self._page_body.remove(group)
        page_key = self._building_page
        scroll = self.pages[page_key]
        category = self.page_groups[page_key]
        if category != "Summaries":
            scroll.set_child(None)
            self._navigation.pages[page_key].get_child().set_content(self._page_body)
            self.pages[page_key] = self._page_body
        self._explanation(self._page_body, category,
            classification_task_contract(key) if resource == "classification_tasks" else group.get_description())
        warning = None
        if resource == "classification_tasks":
            warning = wrapped("", margin_bottom=4)
            warning.add_css_class("warning")
            self._page_body.append(warning)
        def update(text):
            if warning is not None:
                message = classification_guidance_warning(text, key)
                warning.set_text(message)
                warning.set_visible(bool(message))
        def change(text):
            if not self._installing:
                owner[key] = text
                update(text)
        update(owner[key])
        editor = text_editor(owner[key], change, label=label, tall=True)
        self._guidance_bindings.append((owner, key, editor.get_child().get_buffer(), update))
        if category == "Summaries":
            # The complete disclosure pushes this editor down in the page scroll.
            editor.set_min_content_height(240)
        self._page_body.append(editor)

    def _explanation(self, box, category, task=None):
        classification = category == "Classification"
        if not classification:
            box.append(wrapped("Summaries · topic digests → narrative sections"))
        expander = Gtk.Expander(label="About classification" if classification else "About summaries", expanded=False)
        explanation = (CLASSIFICATION_EXPLANATION if classification else
                       SUMMARY_TITLE + "\n" + SUMMARY_PROGRESSION + "\n\n" + SUMMARY_EXPLANATION)
        if task:
            explanation += "\n\n" + task
        if classification:
            explanation += "\n\n" + CLASSIFICATION_PROGRESSION
        label = wrapped(explanation, margin_top=6, margin_bottom=6)
        disclosure = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inspect = button("View full prompts…", lambda: self._inspect_prompts(category))
        inspect.set_halign(Gtk.Align.START)
        disclosure.append(inspect)
        disclosure.append(label)
        expander.set_child(disclosure)
        box.append(expander)

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
        if not roles and not forms:
            return self._topic_catalog(group, values)
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

    def _topic_catalog(self, group, values, *, kind=None):
        kind = kind or ("hearings" if values is self.editor.resources["hearings"] else "reports")
        naming = kind in {"naming-reports", "naming-forms"}
        title_key = "name" if naming else "title"
        noun = "Report" if kind == "naming-reports" else "Form" if naming else "Topic"
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        group.add(holder)
        # Retain each inline disclosure/editor by stable ID across reorder/add/remove.
        cards = {}
        def render(refresh=False):
            visible = self._navigation.view.get_visible_page()
            retained_page = visible.get_tag() if visible is not None and cards and not refresh else None
            if retained_page is not None:
                self._navigation._capture(retained_page)
            clear(holder)
            live_ids = {value["id"] for value in values}
            for identity in set(cards) - live_ids:
                cards.pop(identity)
                detail = f"topic:{kind}:{identity}"
                self._topic_editors.pop(detail, None)
                self._topic_expanders.pop(detail, None)
            for value in values:
                identity = value["id"]
                detail = f"topic:{kind}:{identity}"
                if identity not in cards:
                    card = Gtk.Expander()
                    name = wrapped(value[title_key], margin_top=10, margin_bottom=10,
                                   margin_start=10, margin_end=10)
                    card.set_label_widget(name)
                    card.add_css_class("card")
                    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                                    margin_top=8, margin_bottom=12, margin_start=12, margin_end=12)
                    card.set_child(inner)
                    inner.append(wrapped(noun + " name"))
                    entry = Gtk.Entry(text=value[title_key], hexpand=True)
                    entry.update_property([Gtk.AccessibleProperty.LABEL], [noun + " name"])
                    def rename(widget, value=value, name=name):
                        if not self._installing:
                            value[title_key] = widget.get_text()
                            name.set_text(value[title_key] or noun + " instructions")
                    entry.connect("changed", rename)
                    inner.append(entry)
                    def change_topic(text, value=value):
                        if not self._installing:
                            value["guidance"] = text
                    if naming:inner.append(wrapped("Description (optional)"))
                    editor = text_editor(topic_editor_text(value["guidance"]), change_topic, label=noun + " description" if naming else noun + " description / matching instructions")
                    editor.set_min_content_height(120)
                    editor.set_max_content_height(300)
                    editor.set_propagate_natural_height(True)
                    inner.append(editor)
                    self._topic_editors[detail] = editor
                    self._topic_expanders[detail] = card
                    tools = Gtk.Box(spacing=6)
                    inner.append(tools)
                    def move(delta, value=value):
                        index = next(i for i, item in enumerate(values) if item is value)
                        other = index + delta
                        if 0 <= other < len(values):
                            values[index], values[other] = values[other], values[index]
                            render()
                    up = button("Move up", lambda move=move: move(-1))
                    down = button("Move down", lambda move=move: move(1))
                    tools.append(up)
                    tools.append(down)
                    def remove(value=value, identity=identity, detail=detail):
                        values.remove(value)
                        cards.pop(identity)
                        self._topic_editors.pop(detail)
                        self._topic_expanders.pop(detail)
                        render()
                    tools.append(button("Remove", remove))
                    cards[identity] = (card, up, down, entry, editor, name)
                card, up, down, entry, editor, name = cards[identity]
                if refresh:
                    entry.set_text(value[title_key])
                    name.set_text(value[title_key])
                    self._replace_buffer(editor.get_child().get_buffer(), topic_editor_text(value["guidance"]))
                up.set_sensitive(value is not values[0])
                down.set_sensitive(value is not values[-1])
                holder.append(card)
            def add():
                values.append({"id": f"item-{uuid.uuid4().hex}", title_key: "New " + noun.lower(),
                               "guidance": "" if naming else "Capture material source-supported information."})
                render()
            holder.append(button("Add " + noun.lower(), add))
            if retained_page is not None:
                self._navigation._restore(retained_page)
        self._topic_refreshers[kind] = render
        render()

    def _inspect_prompts(self, category):
        from .prompt_inspector_ui import PromptInspector
        self.prompt_inspector = PromptInspector(self, category, self._active_page, self.editor)
        self.prompt_inspector.present()

    def _fixed_cards(self, owner, keys, *, read_only=False):
        titles = {"first_hearing": "Hearing first page", "first_minute": "Minute-order first page",
                  "first_form": "Form first page", "first_report": "Report first page", "RT_body": "Hearing dialogue"}
        for key in keys:
            card = Gtk.Expander()
            title = titles.get(key, friendly(key.removeprefix("RT_").removeprefix("CT_")))
            card.set_label_widget(wrapped(title, margin_start=10, margin_end=10, margin_top=10, margin_bottom=10))
            card.add_css_class("card")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                            margin_start=12, margin_end=12, margin_top=8, margin_bottom=12)
            output = CLASSIFICATION_FIRST_PAGE_TYPES.get(key, key)
            label = wrapped("Output key: " + output, selectable=True)
            label.add_css_class("dim-label")
            inner.append(label)
            warning = wrapped("")
            warning.add_css_class("warning")
            inner.append(warning)
            def update(text, warning=warning, key=key):
                from .structured_guidance import legacy_policy_warning
                message = classification_guidance_warning(text, key) or legacy_policy_warning(text)
                warning.set_text(message)
                warning.set_visible(bool(message))
            def change(text, owner=owner, key=key, update=update):
                if not self._installing:
                    owner[key] = text
                    update(text)
            editor = text_editor(topic_editor_text(owner[key]), None if read_only else change, label=title + " recognition description")
            editor.set_min_content_height(120)
            editor.set_max_content_height(420)
            editor.set_propagate_natural_height(True)
            update(owner[key])
            if not read_only:self._guidance_bindings.append((owner, key, editor.get_child().get_buffer(), update))
            inner.append(editor)
            card.set_child(inner)
            self._page_body.append(card)
            self._recognition_cards[key] = (card, editor)
            self._recognition_pages[key] = self._building_page

    def _legacy_naming(self, naming):
        import json
        self._page_body.append(wrapped("Historical naming catalog (JSON compatibility editor). Unrecognized prose is not split or replaced. Preserve the original catalog format."))
        def change(text):
            if not self._installing:
                try:
                    value = json.loads(text)
                    if isinstance(value, dict):
                        naming.clear()
                        naming.update(value)
                        self._legacy_naming_error = False
                    else:
                        self._legacy_naming_error = True
                except ValueError:
                    self._legacy_naming_error = True
        scroll = text_editor(json.dumps(naming, ensure_ascii=False, indent=2), change,
                             label="Legacy naming JSON", tall=True)
        view = scroll.get_child()
        if self._legacy_naming_buffer is None:
            self._legacy_naming_buffer = view.get_buffer()
        else:
            view.set_buffer(self._legacy_naming_buffer)
        self._page_body.append(scroll)

    def _classification_contents(self, key, title):
        tasks = self.editor.resources["classification_tasks"]
        naming = self.editor.resources["naming"]
        self._explanation(self._page_body, "Classification")
        if key in ("rt", "ct") and "page_types" in tasks:
            self._fixed_cards(tasks["page_types"][key], CLASSIFICATION_PAGE_TYPES[key])
        elif key == "first-pages":
            owner = tasks.get("first_pages", tasks)
            if owner is tasks:
                self._page_body.append(wrapped("Legacy compatibility guidance — retained without splitting. Date extraction is application-owned."))
            self._fixed_cards(owner, (task for task in CLASSIFICATION_FIRST_PAGE_TYPES if task in owner))
            if "first_report" not in owner:
                from .classifier_prompts import REPORT_FIRST_CLUES
                self._page_body.append(wrapped("Report first-page detection uses the application's default clues for this older profile."))
                self._fixed_cards({"first_report": REPORT_FIRST_CLUES}, ("first_report",), read_only=True)
        elif key.endswith("-naming") and naming.get("schema_version") == 4:
            plural = key.removesuffix("-naming") + "s"
            self._page_body.append(wrapped("Enter each approved name and optional recognition description once. "
                                           "This catalog is used only to name marked first pages, not to classify page types or detect document starts."))
            self._topic_catalog(self._group(title), naming[plural], kind="naming-" + plural)
        else:
            self._page_body.append(wrapped("Legacy compatibility editor — original prose is preserved. Best-fit application policy overrides any ordering language. Reset to bundled explicitly replaces all guidance with structured settings."))
            if key in ("rt", "ct"):
                self._fixed_cards(tasks, (key,))
            else:
                field = key.removesuffix("-naming") + "_guidance"
                if field in naming:
                    self._fixed_cards(naming, (field,))
                else:
                    self._legacy_naming(naming)

    def _recordprep_form(self):
        for key, title, stage in CLASSIFICATION_PAGES:
            self._page("Classification", key, title)
            self.nav_rows[key].set_subtitle(stage)
            self._classification_contents(key, title)
        for kind, title in (("hearings", "Hearing"), ("reports", "Report")):
            self._page("Summaries", kind + "-topics", title + " digest topics")
            self._explanation(self._page_body, "Summaries")
            self._catalog(self._group(title + " digest topics"), self.editor.resources[kind])
            self.nav_rows[kind + "-topics"].set_subtitle("1 · Build digest")
        self._page("Summaries", "minutes", "Minute orders")
        group = self._group("Minute orders", "One agent summarizes each complete minute order directly, without a topic-digest stage.")
        self._guidance(group, "minutes", "Writing minute-order summaries")

    def _bundled_action(self):
        try:
            target = api.bundled_profile_for_identity(self.editor.base.ref.application, self.editor.manifest["specialty_id"])
        except (ValueError, OSError):
            self.message.set_text("Bundled prompts could not be verified. Reopen Profile settings after restoring the installed resources.")
            return
        if target is None:
            return
        row = Adw.ActionRow(title="Bundled prompts", subtitle="Restore and save all guidance for this profile.")
        row.set_title_lines(2)
        row.set_subtitle_lines(0)
        self.reset_button = button("Reset to bundled…", self._reset)
        self.reset_button.set_valign(Gtk.Align.CENTER)
        row.add_suffix(self.reset_button)
        row.set_activatable_widget(self.reset_button)
        self.reset_row = row
        self._navigation.home_list.append(row)

    def _reset(self):
        if self.reset_dialog is not None:
            self.reset_dialog.present()
            return self.reset_dialog
        if not self.can_modify() or getattr(self, "_reset_refresh_required", False):
            self._refresh_guard()
            return None
        try:
            target = api.bundled_profile_for_identity(self.editor.base.ref.application, self.editor.manifest["specialty_id"])
            if target is None:
                raise ProfileError("missing_bundled_profile", "profiles")
        except (ValueError, OSError):
            self.message.set_text("Bundled prompts are unavailable or corrupt. Restore the installed resources and reopen Profile settings; your draft is kept.")
            return None
        # Freeze the target and the editor's CAS expectations, not a later head.
        expected_head, expected_default = self.expected_head, copy.deepcopy(self.expected_default)
        use_default = self.default_row.get_active() if self.default_row is not None else None
        def respond(response):
            self.reset_dialog = None
            if response == "reset" and not self._closing:
                self._reset_to(target, expected_head, expected_default, use_default)
        self.reset_dialog = confirmation(self, "Reset to bundled prompts?",
            f'For “{target.manifest["display_name"]}”, replace all Classification and Summaries guidance, '
            'including approved names, topic catalogs, and unsaved profile edits. Saves immediately. '
            'Model settings, case files, and generated output do not change.',
            (("cancel", "Cancel"), ("reset", "Reset and Save")), respond)
        self.reset_dialog.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)
        return self.reset_dialog

    def _reset_to(self, target, expected_head, expected_default, use_default=None):
        saved_ref = None
        self.saved_apply_failed = False
        self.saved_dialog = None
        try:
            def guarded():
                if not self.can_modify() or self._closing:
                    raise ProfileError("work_active_or_case_changed", "reset")
                current = api.bundled_profile_for_identity(target.ref.application, target.ref.specialty_id)
                if current is None or current.files != target.files:
                    raise ProfileError("bundled_profile_changed", "reset")
                return True
            guarded()
            # Do not compile or mutate the discarded draft, even when invalid.
            replacement = ProfileEditor(target)
            ref = replacement.managed_save(self.store, expected_head=expected_head,
                expected_default=expected_default, validate=self.preview, can_modify=guarded,
                use_for_new_cases=use_default, personal=True)
            saved_ref = ref
            try:
                accepted = self.store.load_profile_snapshot(ref)
                registry = self.store.read_registry()
                self._adopt_reset(accepted)
                self.expected_head = ref.content_sha256
                self.expected_default = registry["default"]
                self.expected_heads = dict(registry["heads"])
                self.personal, self.notice = True, ""
                self.profile_notice.set_text("")
                self.profile_notice.set_visible(False)
                self.candidates = list(api.profile_catalog(store=self.store))
                self._saved_state = self._state()
                self.message.set_text("Profile reset to bundled prompts and saved.")
            finally:
                # Publication already succeeded: notify the selection owner even
                # if retained-widget refresh fails. Never claim a rollback.
                self.saved_dialog = self.on_saved(ref)
            return True
        except Exception as exc:
            if saved_ref is not None:
                self.saved_apply_failed = True
                self.message.set_text("Profile reset saved, refresh required. Close and reopen Profile settings and the profile menu before editing again.")
                # Partial display installation is not a safe subsequent draft.
                self._reset_refresh_required = True
                self._refresh_guard()
                return True
            code = exc.issue.code if isinstance(exc, ProfileError) else "invalid_settings"
            if code == "bundled_profile_changed":
                text = "Bundled prompts changed during confirmation. Your draft is kept; choose Reset to bundled again to review the new target."
            elif code in {"stale_profile_revision", "external_profile_changed", "deleted_profile"}:
                text = "Saved profile or default changed elsewhere. Your draft is kept; close and reopen the saved settings before resetting."
            elif code == "work_active_or_case_changed":
                text = "Work is active, or the case or profile storage changed. Your draft is kept; stop work and reopen Profile settings before resetting."
            else:
                text = "Reset could not be validated or saved. Your draft and selection are kept. Check installed resources and profile storage, then reopen Profile settings."
            self.message.set_text(text)
            return False

    @staticmethod
    def _replace_buffer(buffer, text):
        if buffer.get_text(*buffer.get_bounds(), True) == text:
            return
        insert = buffer.get_iter_at_mark(buffer.get_insert()).get_offset()
        bound = buffer.get_iter_at_mark(buffer.get_selection_bound()).get_offset()
        buffer.begin_user_action()
        try:
            buffer.delete(*buffer.get_bounds())
            buffer.insert(buffer.get_start_iter(), text)
        finally:
            buffer.end_user_action()
        size = buffer.get_char_count()
        buffer.select_range(buffer.get_iter_at_offset(min(insert, size)), buffer.get_iter_at_offset(min(bound, size)))

    def _adopt_reset(self, snapshot):
        """Install exact saved values through retained containers and stable IDs."""
        visible = self._navigation.view.get_visible_page().get_tag()
        self._navigation._capture(visible)
        resources = self.editor.resources
        rebuild = set()
        for resource, pages in (("classification_tasks", ("rt", "ct", "first-pages")),
                                ("naming", ("report-naming", "form-naming"))):
            old, new = resources[resource], snapshot.resource(resource)
            if (old.get("schema_version"), "page_types" in old) != (new.get("schema_version"), "page_types" in new):
                rebuild.update(pages)
        retired_buffers = set()
        for key, page in list(self._recognition_pages.items()):
            if page in rebuild:
                retired_buffers.add(self._recognition_cards.pop(key)[1].get_child().get_buffer())
                self._recognition_pages.pop(key)
        self._guidance_bindings[:] = [binding for binding in self._guidance_bindings if binding[2] not in retired_buffers]
        self._installing = True
        self._legacy_naming_error = False
        try:
            def retain(old, new):
                if isinstance(old, dict) and isinstance(new, dict):
                    for key in set(old) - set(new):
                        del old[key]
                    for key, value in new.items():
                        old[key] = retain(old.get(key), value)
                    return old
                if isinstance(old, list) and isinstance(new, list):
                    by_id = {item.get("id"): item for item in old if isinstance(item, dict)}
                    old[:] = [retain(by_id.get(item.get("id")), item) if isinstance(item, dict) else item for item in new]
                    return old
                return new
            for name in snapshot.manifest["resources"]:
                value = snapshot.resource(name)
                if name in self._topic_refreshers:
                    values = resources[name]
                    retained = {item["id"]: item for item in values}
                    ordered = []
                    for topic in value:
                        item = retained.get(topic["id"], {})
                        item.clear()
                        item.update(topic)
                        ordered.append(item)
                    values[:] = ordered
                elif isinstance(value, dict) and isinstance(resources.get(name), dict):
                    retain(resources[name], value)
                else:
                    resources[name] = value
            for name in set(resources) - set(snapshot.manifest["resources"]):
                del resources[name]
            self.editor = ProfileEditor(snapshot)
            self.editor.resources = resources
            self.title_widget.set_subtitle(snapshot.manifest["display_name"])
            self.title_widget.set_tooltip_text(snapshot.manifest["display_name"])
            for key, title, _stage in CLASSIFICATION_PAGES:
                if key in rebuild:
                    self._page_body = self._page_bodies[key]
                    self._building_page = key
                    clear(self._page_body)
                    self._navigation._focus.pop(key, None)
                    self._classification_contents(key, title)
            for owner, key, buffer, update in self._guidance_bindings:
                self._replace_buffer(buffer, owner[key])
                update(owner[key])
            for render in self._topic_refreshers.values():
                render(refresh=True)
            # Clamp cached offsets too: hidden pages may contain shorter text now.
            live_buffers = {binding[2] for binding in self._guidance_bindings}
            live_buffers.update(scroll.get_child().get_buffer() for scroll in self._topic_editors.values())
            for key, selections in self._navigation._selections.items():
                self._navigation._selections[key] = [
                    (buffer, min(insert, buffer.get_char_count()), min(bound, buffer.get_char_count()))
                    for buffer, insert, bound in selections if buffer in live_buffers]
            self._navigation._restore(visible)
        finally:
            self._installing = False

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
            choice.set_selected(next(i for i, item in enumerate(candidates) if item.snapshot.ref.specialty_id == api.DEFAULT_PROFILE_ID), notify=False)
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
                                candidate = next(item for item in self.candidates if item.snapshot.ref.specialty_id == api.DEFAULT_PROFILE_ID)
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
        if not self.can_modify() or getattr(self, "_reset_refresh_required", False):
            self._refresh_guard()
            return False
        try:
            if getattr(self, "_legacy_naming_error", False):
                raise ProfileError("invalid_json", "naming")
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
            # Rebind publication identity without rebuilding widgets. The retained
            # draft containers become the new editor's containers, so every existing
            # callback targets the current editor, not an abandoned resource tree.
            resources = self.editor.resources
            self.editor = ProfileEditor(self.store.load_profile_snapshot(ref))
            self.editor.resources = resources
            self._saved_state = self._state()
            self.personal = personal
            self.expected_heads = dict(self.store.read_registry()["heads"])
            self.candidates = list(api.profile_catalog(store=self.store))
            self.message.set_text("Profile saved.")
            self.saved_dialog = self.on_saved(ref)
            return True
        except Exception as exc:
            if saved_ref is not None:
                self.saved_apply_failed = True
                self.message.set_text("Profile saved; reopen the menu to refresh the current selection.")
                return True
            code = exc.issue.code if isinstance(exc, ProfileError) else "invalid_settings"
            if code in {"stale_profile_revision", "external_profile_changed"}:
                self.message.set_text("These settings changed elsewhere. Your draft is kept. Reopen the saved settings before saving again.")
            else:
                location = friendly(exc.issue.location) if isinstance(exc, ProfileError) else "Settings"
                self.message.set_text(f"{location}: check the entered settings. The selected profile and existing output are unchanged.")
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
        editor.manifest["schema_version"] = 6
        from .structured_guidance import structured_resources
        tasks, naming, structured = structured_resources(editor.resources)
        editor.resources["classification_tasks"] = tasks
        editor.resources["naming"] = naming
        if structured:
            editor.manifest["schema_version"] = 8
        editor.manifest["resources"].pop("classification", None)
        editor.resources.pop("classification", None)
        for name in RETIRED_SUMMARY_RESOURCES | RETIRED_PARTICIPANT_RESOURCES | RETIRED_OVERVIEW_RESOURCES:
            editor.manifest["resources"].pop(name, None)
            editor.resources.pop(name, None)
        # Unknown legacy resources retain their exact format and prose. Only the
        # structured resource pair above becomes a schema-8 draft.
    return editor
