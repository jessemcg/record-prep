"""Standalone, offline, read-only reference. Never resolves a profile or case."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from .profile_contract import CLASSIFICATION_FIRST_PAGE_TYPES
from .recognition_contract import TITLES, load_recognition
from .profile_editor_ui import button, wrapped

OWNERSHIP = (
    "These rules belong to RecordPrep and apply to every profile. Viewing them does not alter saved output. "
    "Report Names, Form Names, Motion Names and summary topics remain profile settings; minute guidance is application-owned. "
    "Each classifier request receives one page image, not adjacent-page context."
)
SAVED_OUTPUT = (
    "Existing classifications, Forms TOCs and other prepared output remain unchanged. To apply these rules to an "
    "existing bundle, explicitly run Basic and the desired downstream stages. This requires new image-model work; "
    "newly classified hearing notices and service proofs will no longer be named forms. Resume still skips saved output."
)


class ClassificationReference(Adw.Window):
    def __init__(self, parent):
        super().__init__(application=parent.get_application(), title="App-owned Classification",
                         default_width=850, default_height=720, resizable=True)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.pack_start(button("Close", self.close))
        header.pack_end(button("View full prompts…", self._prompts))
        toolbar.add_top_bar(header)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_start=16, margin_end=16, margin_top=12, margin_bottom=16)
        body.append(wrapped(OWNERSHIP, selectable=True))
        body.append(wrapped(SAVED_OUTPUT, selectable=True))
        self.search = Gtk.SearchEntry(placeholder_text="Find definitions or output keys")
        body.append(self.search)
        self.cards = {}
        self.contract = None
        try:
            contract = self.contract = load_recognition()
            groups = [("Reporter transcript (RT)", entries) for side, entries in contract.page_types if side == "rt"]
            groups += [("Clerk transcript (CT)", entries) for side, entries in contract.page_types if side == "ct"]
            groups += [("First pages — five independent tasks", contract.first_pages)]
            for title, entries in groups:
                heading = wrapped(title)
                heading.add_css_class("title-3")
                body.append(heading)
                for key, text in entries:
                    marker = CLASSIFICATION_FIRST_PAGE_TYPES.get(key, key)
                    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                   margin_top=4, margin_bottom=4)
                    card.add_css_class("card")
                    label = wrapped(TITLES[key] + " — " + marker, selectable=True,
                                    margin_start=12, margin_end=12, margin_top=12)
                    label.add_css_class("heading")
                    card.append(label)
                    definition = wrapped(text, selectable=True, margin_start=12, margin_end=12, margin_bottom=12)
                    card.append(definition)
                    body.append(card)
                    self.cards[key] = (card, (TITLES[key] + " " + key + " " + marker + " " + text).casefold())
        except ValueError as exc:
            body.append(wrapped(str(exc), selectable=True))
        self.search.connect("search-changed", self._find)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(body)
        toolbar.set_content(scroll)
        self.set_content(toolbar)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)

    def _key(self, _controller, key, _code, _state):
        if key == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _find(self, *_args):
        query = self.search.get_text().casefold()
        for card, text in self.cards.values():
            card.set_visible(query in text)

    def _prompts(self):
        from .prompt_inspector_ui import PromptInspector
        self.prompt_inspector = PromptInspector(self, "Application classification", contract=self.contract)
        self.prompt_inspector.present()
