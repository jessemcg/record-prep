"""Read-only modal audit; its draft snapshot cannot silently become stale."""
from __future__ import annotations
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from .profile_editor_ui import wrapped, button
from .prompt_inspection import CLASSIFICATION_TASKS, SUMMARY_TASKS, inspect_prompt
from .paths import resource_root


class PromptInspector(Adw.Window):
    def __init__(self, parent, category, page, draft):
        super().__init__(transient_for=parent, modal=True, resizable=True,
                         title="Full prompts — RecordPrep-controlled instructions", default_width=850, default_height=720)
        self.draft = draft
        self.resources = draft.resources
        self.snapshot = draft.snapshot
        validation = "\n".join(draft.issues)
        self.tasks = CLASSIFICATION_TASKS if category == "Classification" else SUMMARY_TASKS
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.pack_end(button("Copy", self._copy))
        toolbar.add_top_bar(header)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                          margin_start=12, margin_end=12, margin_top=8, margin_bottom=12, vexpand=True)
        content.append(wrapped("RecordPrep-controlled instruction components and delivery audit, with runtime-data placeholders. Not a live conversation replay or provider internals."))
        self.selector = Gtk.DropDown.new_from_strings([title for _, title in self.tasks])
        self.selector.set_enable_search(True)
        content.append(self.selector)
        self.mode = Gtk.DropDown.new_from_strings(["Template with placeholders", "With current draft"])
        content.append(self.mode)
        self.mode_note = wrapped("Current draft includes unsaved editor values, frozen while this inspector is open.")
        self.mode_note.set_visible(False)
        content.append(self.mode_note)
        self.status = wrapped(validation, selectable=True)
        self.validation = validation
        content.append(self.status)
        self.search = Gtk.SearchEntry(placeholder_text="Find in displayed prompts")
        self.search.connect("search-changed", self._find)
        self.search.connect("activate", self._find)
        content.append(self.search)
        self.text = Gtk.TextView(editable=False, cursor_visible=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                 left_margin=10, right_margin=10, top_margin=10, bottom_margin=10)
        self.text.update_property([Gtk.AccessibleProperty.LABEL], ["Read-only full prompts"])
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.text)
        content.append(scroll)
        toolbar.set_content(content)
        outer.append(toolbar)
        self.set_content(outer)
        selected = {"first-pages": "first_hearing", "report-naming": "report", "form-naming": "form",
                    "hearings-topics": "hearings-extract", "reports-topics": "reports-extract"}.get(page, page)
        self.selector.set_selected(next((i for i, (key, _) in enumerate(self.tasks) if key == selected), 0))
        self.selector.connect("notify::selected", self._refresh)
        self.mode.connect("notify::selected", self._refresh)
        self._refresh()

    def _refresh(self, *_args):
        self.mode_note.set_visible(self.mode.get_selected() == 1)
        try:
            result = inspect_prompt(self.resources, self.tasks[self.selector.get_selected()][0], resource_root(),
                                    template=self.mode.get_selected() == 0, draft=self.draft)
            self.text.get_buffer().set_text(result.display_text())
            self.status.set_text("\n".join(result.issues))
        except (ValueError, OSError, KeyError, TypeError):
            self.status.set_text("\n".join(filter(None, [self.validation,
                "Incomplete inspection: this draft or an installed resource is malformed. No bundled values have been substituted."])))
            import json
            self.text.get_buffer().set_text(json.dumps(self.resources, ensure_ascii=False, indent=2)
                + "\n\n" + "\n\n".join(name + " (literal raw draft)\n" + text for name, text in self.draft.raw_resources))

    def _copy(self):
        buffer = self.text.get_buffer()
        self.get_clipboard().set(buffer.get_text(*buffer.get_bounds(), True))

    def _find(self, *_args):
        query = self.search.get_text()
        if not query:
            return
        buffer = self.text.get_buffer()
        start = buffer.get_iter_at_mark(buffer.get_insert())
        match = start.forward_search(query, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
        if match is None:
            match = buffer.get_start_iter().forward_search(query, Gtk.TextSearchFlags.CASE_INSENSITIVE, None)
        if match:
            buffer.select_range(*match)
            self.text.scroll_to_iter(match[0], 0.1, False, 0, 0)
