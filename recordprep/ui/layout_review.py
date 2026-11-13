"""Explicit, case-bound review of ambiguous transcript detection."""
from gi.repository import Adw, Gtk

from recordprep.transcript_layout import diagnose_layout, transcript_layout_path


class LayoutReviewDialog(Adw.Window):
    def __init__(self, owner, root):
        super().__init__(title="Review transcript layout", transient_for=owner,
                         modal=True, default_width=520)
        self.owner = owner
        self.root = root
        self.original = transcript_layout_path(root).read_bytes()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=18, margin_bottom=18, margin_start=24, margin_end=24)
        box.append(Gtk.Label(label=(
            "Automatic detection could not confidently determine the layout. "
            "Check the source pages, then choose the correct arrangement. "
            "CT followed by RT or interleaved collections must be prepared separately."
        ), wrap=True, xalign=0))
        group = Adw.PreferencesGroup()
        self.layout = Adw.ComboRow(title="Transcript layout")
        self.layout.set_model(Gtk.StringList.new([
            "Choose a layout", "RT + CT", "Reporter's transcript only",
            "Clerk's transcript only",
        ]))
        group.add(self.layout)
        self.page = Adw.EntryRow(title="RT ends at page (combined PDF file page)")
        self.page.set_input_purpose(Gtk.InputPurpose.DIGITS)
        self.page.set_visible(False)
        group.add(self.page)
        self.layout.connect("notify::selected", self._selection_changed)
        box.append(group)
        self.message = Gtk.Label(wrap=True, xalign=0)
        self.message.add_css_class("error")
        box.append(self.message)
        actions = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        actions.append(cancel)
        self.apply = Gtk.Button(label="Apply layout", sensitive=False)
        self.apply.add_css_class("suggested-action")
        self.apply.connect("clicked", self._apply)
        actions.append(self.apply)
        box.append(actions)
        toolbar.set_content(box)
        self.set_content(toolbar)

    def _selection_changed(self, *_):
        selected = self.layout.get_selected()
        self.page.set_visible(selected == 1)
        self.apply.set_sensitive(selected in (1, 2, 3))
        self.message.set_text("")

    def _apply(self, *_):
        owner, root = self.owner, self.root
        try:
            current = transcript_layout_path(root).read_bytes()
        except OSError:
            current = None
        if (owner._pipeline_running or owner._resolve_case_root() != root
                or current != self.original
                or diagnose_layout(root).code != "needs_review"):
            self.message.set_text("The case or detection changed. Close this dialog and review again.")
            return
        selected = self.layout.get_selected()
        if selected not in (1, 2, 3):
            return
        raw = self.page.get_text().strip()
        if selected == 1 and (not raw.isascii() or not raw.isdigit() or int(raw) < 1):
            self.message.set_text("Enter the last RT file page, before the first CT page.")
            return
        owner._rt_ct_split_mode_pending = {1: "split", 2: "rt_only", 3: "ct_only"}[selected]
        owner._rt_ct_split_pending = int(raw) if selected == 1 else None
        try:
            accepted = owner._try_apply_manual_layout()
        finally:
            # A canceled/failed dialog must never leak a choice into a later run.
            owner._rt_ct_split_mode_pending = None
            owner._rt_ct_split_pending = None
        if not accepted:
            self.message.set_text("Layout could not be applied. Check the page range and the application's warning; prepared work is preserved.")
            return
        owner._load_rt_ct_split()
        owner._refresh_step_statuses_from_artifacts()
        self.close()
        owner.show_toast("Transcript layout updated. Use Resume to continue.")
