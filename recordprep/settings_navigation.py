"""Application-local retained settings navigation (Libadwaita >= 1.4).

Presentation only: no settings I/O, discovery, or sibling-project imports.
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango


def descendants(widget):
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()


def round_editor(scroller):
    scroller.add_css_class("settings-prompt-editor")
    scroller.set_overflow(Gtk.Overflow.HIDDEN)


def install_editor_style(window):
    provider = Gtk.CssProvider()
    provider.load_from_data(b"""
      scrolledwindow.settings-prompt-editor {
        border-radius: 12px; background-color: @view_bg_color;
      }
      scrolledwindow.settings-prompt-editor textview,
      scrolledwindow.settings-prompt-editor textview text,
      scrolledwindow.settings-prompt-editor textview border {
        background-color: transparent; background-image: none; box-shadow: none;
      }
    """)
    Gtk.StyleContext.add_provider_for_display(window.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    window._settings_editor_css = provider


class SettingsNavigation:
    def __init__(self, save, is_closed):
        self._save = save
        self._is_closed = is_closed
        self.view = Adw.NavigationView()
        self.pages = {}
        self.parents = {}
        self.save_buttons = {}
        self.headers = {}
        self._positions = {}
        self._selections = {}
        self._focus = {}
        self._origin = None
        self._generation = 0
        self._choosers = {}
        self._prompt_keys = []
        self._syncing = False
        self.home_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.home_list.add_css_class("boxed-list")
        self.home_list.set_valign(Gtk.Align.START)
        for edge in ("top", "bottom", "start", "end"):
            getattr(self.home_list, "set_margin_" + edge)(18)
        self.home_scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.home_scroller.set_child(self.home_list)
        self.add_page("home", "Settings", self.home_scroller)

    def add_category(self, title):
        row = Adw.ExpanderRow(title=title)
        row.set_expanded(False)
        self.home_list.append(row)
        return row

    def add_destination(self, category, key, title, content, *, prompt=False):
        row = Adw.ActionRow(title=title, activatable=True, use_markup=False)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda *_: self.open(key, row))
        category.add_row(row)
        self.add_page(key, title, content, prompt=prompt)
        return row

    def add_page(self, key, title, content, *, prompt=False):
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.headers[key] = header
        if prompt:
            chooser = Gtk.DropDown()
            chooser.set_tooltip_text("Switch prompt")
            chooser.update_property([Gtk.AccessibleProperty.LABEL], ["Switch prompt"])
            factory = Gtk.SignalListItemFactory()
            def setup(_factory, item):
                item.set_child(Gtk.Label(ellipsize=Pango.EllipsizeMode.END, max_width_chars=18))
            def bind(_factory, item):
                label = item.get_child()
                label.set_label(item.get_item().get_string())
                label.set_tooltip_text(label.get_label())
            factory.connect("setup", setup)
            factory.connect("bind", bind)
            chooser.set_factory(factory)
            menu_factory = Gtk.SignalListItemFactory()
            def menu_setup(_factory, item):
                label = Gtk.Label(xalign=0, wrap=True, width_chars=18, max_width_chars=28)
                label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                item.set_child(label)
            menu_factory.connect("setup", menu_setup)
            menu_factory.connect("bind", bind)
            chooser.set_list_factory(menu_factory)
            chooser.connect("notify::selected", self._switch_prompt)
            self._choosers[key] = chooser
            self._prompt_keys.append(key)
            header.set_title_widget(chooser)
        else:
            header.set_title_widget(Adw.WindowTitle(title=title))
        button = Gtk.Button(label="Save")
        button.add_css_class("flat")
        button.connect("clicked", lambda *_: self._save())
        self.save_buttons[key] = button
        header.pack_end(button)
        toolbar.add_top_bar(header)
        toolbar.set_content(content)
        page = Adw.NavigationPage(child=toolbar, title=title, tag=key)
        page.connect("hiding", lambda *_: self._capture(key))
        page.connect("shown", lambda *_: self._restore(key))
        self.pages[key] = page
        self.view.add(page)
        return page

    def finish(self):
        self._syncing = True
        for key, chooser in self._choosers.items():
            chooser.set_model(Gtk.StringList.new([self.pages[k].get_title() for k in self._prompt_keys]))
            chooser.set_selected(self._prompt_keys.index(key))
        self._syncing = False

    def _switch_prompt(self, chooser, _param):
        if self._syncing:
            return
        selected = int(chooser.get_selected())
        if 0 <= selected < len(self._prompt_keys):
            self.open(self._prompt_keys[selected])

    def open(self, key, origin=None):
        if self._is_closed() or self.view.get_visible_page() is self.pages[key]:
            return
        current = self.view.get_visible_page()
        if current is not None:
            self._capture(current.get_tag())
        if origin is not None:
            self._origin = origin
            self._focus["home"] = origin
        self._generation += 1
        if key in self._choosers:
            self._syncing = True
            self._choosers[key].set_selected(self._prompt_keys.index(key))
            self._syncing = False
        parent = self.parents.get(key)
        chain = [self.pages["home"]]
        if parent:
            chain.append(self.pages[parent])
        chain.append(self.pages[key])
        self.view.replace(chain)

    def remove_page(self, key):
        self._generation += 1
        if self.view.get_visible_page() is self.pages[key]:
            self.view.pop_to_tag(self.parents.get(key, "home"))
        page = self.pages.pop(key)
        self.view.remove(page)
        self.save_buttons.pop(key, None)
        self.headers.pop(key, None)
        self._choosers.pop(key, None)
        if key in self._prompt_keys:
            self._prompt_keys.remove(key)
        self.parents.pop(key, None)
        self._positions.pop(key, None)
        self._selections.pop(key, None)
        self._focus.pop(key, None)
        self.finish()

    def _capture(self, key):
        page = self.pages[key]
        self._positions[key] = [(w, w.get_vadjustment().get_value())
                                for w in descendants(page) if isinstance(w, Gtk.ScrolledWindow)]
        self._selections[key] = [(w.get_buffer(), w.get_buffer().get_iter_at_mark(w.get_buffer().get_insert()).get_offset(),
                                  w.get_buffer().get_iter_at_mark(w.get_buffer().get_selection_bound()).get_offset())
                                 for w in descendants(page) if isinstance(w, Gtk.TextView)]
        root = page.get_root()
        focus = root.get_focus() if isinstance(root, Gtk.Window) else None
        if key == "home" and self._origin is not None:
            self._focus[key] = self._origin
        elif focus is not None and focus.is_ancestor(page):
            self._focus[key] = focus

    def _restore(self, key):
        self._generation += 1
        generation = self._generation
        def restore():
            page = self.pages.get(key)
            if (self._is_closed() or generation != self._generation or page is None
                    or page.get_root() is None or self.view.get_visible_page() is not page):
                return GLib.SOURCE_REMOVE
            focus = self._focus.get(key)
            if focus is not None:
                focus.grab_focus()
            for buffer, insert, bound in self._selections.get(key, []):
                buffer.select_range(buffer.get_iter_at_offset(insert), buffer.get_iter_at_offset(bound))
            for widget, value in self._positions.get(key, []):
                widget.get_vadjustment().set_value(value)
            return GLib.SOURCE_REMOVE
        def after_layout(widget, clock):
            GLib.idle_add(restore)
            return GLib.SOURCE_REMOVE
        self.pages[key].add_tick_callback(after_layout)


def close_settings_before_parent(application):
    """Both Model and Profile settings must accept closure before teardown."""
    for window in list(application.get_windows()):
        if isinstance(getattr(window, "_navigation", None), SettingsNavigation):
            window.close()
            if window.get_visible():
                window.present()
                return True
    return False


class SettingsSession:
    """Literal baseline and a close veto; Save never continues a close request."""
    def __init__(self, window, snapshot, immediate_note=""):
        self.window = window
        self.snapshot = snapshot
        self.baseline = snapshot()
        self.closed = False
        self._discard = False
        self.dialog = None
        self.immediate_note = immediate_note

    def accept(self):
        self.baseline = self.snapshot()

    def close_request(self, *_):
        if not self._discard and self.snapshot() != self.baseline:
            if self.dialog is None:
                dialog = Adw.MessageDialog(transient_for=self.window, heading="Discard unsaved changes?",
                    body="Only changes since the last successful Save will be discarded." + self.immediate_note)
                dialog.add_response("keep", "Keep Editing")
                dialog.add_response("discard", "Discard Unsaved Changes")
                dialog.set_default_response("keep")
                dialog.set_close_response("keep")
                dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
                def response(_dialog, choice):
                    self.dialog = None
                    if choice == "discard":
                        self._discard = True
                        self.window.close()
                dialog.connect("response", response)
                self.dialog = dialog
            self.dialog.present()
            return True
        self.closed = True
        return False
