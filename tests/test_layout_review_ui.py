"""Synthetic native GTK review tests; run with a display (or xvfb-run)."""
import tempfile
import unittest
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from recordprep.transcript_layout import (
    draft_layout_payload, finalize_layout_draft, read_resolved_layout,
    transcript_layout_path,
)
from recordprep.ui.layout_review import LayoutReviewDialog
from recordprep.ui.main_window import RecordPrepWindow


class Owner(Adw.Window):
    _try_apply_manual_layout = RecordPrepWindow._try_apply_manual_layout
    _build_transcript_split_section = RecordPrepWindow._build_transcript_split_section
    _refresh_layout_review = RecordPrepWindow._refresh_layout_review
    _show_layout_review = RecordPrepWindow._show_layout_review
    _layout_review_closed = RecordPrepWindow._layout_review_closed

    def __init__(self, root):
        super().__init__(title="Synthetic RecordPrep layout review", default_width=650)
        self.root = root
        self._pipeline_running = False
        self._rt_ct_split_mode_pending = self._rt_ct_split_pending = None
        self._rt_ct_split_dropdown = self._rt_ct_split_entry = None
        self.block = False
        self.messages = []
        self.set_content(self._build_transcript_split_section())

    def _resolve_case_root(self):
        return self.root

    def _has_layout_dependent_work(self, root):
        return self.block

    def _load_rt_ct_split(self):
        self._refresh_layout_review()

    def _refresh_step_statuses_from_artifacts(self):
        pass

    def show_toast(self, *args):
        self.messages.append(args)


def make_review(root):
    (root / "text_pages").mkdir()
    for page in range(1, 5):
        (root / "text_pages" / f"{page:04}.txt").write_text(f"Synthetic page {page}\n")
    finalize_layout_draft(root, draft_layout_payload(
        mode="split", status="needs_review", decision_source="pi-agent",
        confidence="low", method="text search", search_summary="Conflicting markers",
        warnings=["Synthetic ambiguous boundary"],
    ))


class LayoutReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        make_review(self.root)
        self.owner = Owner(self.root)
        self.addCleanup(self.owner.destroy)
        self.dialog = LayoutReviewDialog(self.owner, self.root)
        self.addCleanup(self.dialog.destroy)
        self.before = transcript_layout_path(self.root).read_bytes()

    def test_normal_ui_has_no_manual_controls_and_review_can_reopen(self):
        self.assertIsInstance(self.owner._source_row, Adw.ActionRow)
        self.assertNotIsInstance(self.owner._source_row, Adw.ExpanderRow)
        self.assertFalse(self.owner._source_row.get_activatable())
        self.owner._refresh_layout_review(present=True)
        self.assertTrue(self.owner._layout_review_button.get_visible())
        first = self.owner._layout_review_dialog
        first.close()
        self.assertIsNone(self.owner._layout_review_dialog)
        self.owner._show_layout_review()
        self.assertIsNot(first, self.owner._layout_review_dialog)
        self.owner._layout_review_dialog.close()

    def test_saved_layout_is_not_reapplied_as_a_manual_draft(self):
        self.dialog.layout.set_selected(1)
        self.dialog.page.set_text("2")
        self.dialog._apply()
        self.assertEqual(RecordPrepWindow._current_rt_ct_split_selection(self.owner), ("auto", None))
        self.assertFalse(self.owner._layout_review_button.get_visible())
        self.owner._refresh_layout_review(present=True)
        self.assertIsNone(self.owner._layout_review_dialog)

    def test_missing_and_stale_do_not_offer_manual_review(self):
        page = self.root / "text_pages/0001.txt"
        page.write_text("changed")
        self.owner._refresh_layout_review(present=True)
        self.assertFalse(self.owner._layout_review_button.get_visible())
        self.assertIsNone(self.owner._layout_review_dialog)
        transcript_layout_path(self.root).unlink()
        self.owner._refresh_layout_review(present=True)
        self.assertFalse(self.owner._layout_review_button.get_visible())

    def test_cancel_and_selection_do_not_write(self):
        self.dialog.layout.set_selected(3)
        self.dialog.close()
        self.assertEqual(transcript_layout_path(self.root).read_bytes(), self.before)
        self.assertIsNone(self.owner._rt_ct_split_mode_pending)

    def test_all_modes(self):
        for selection, mode in ((1, "split"), (2, "rt_only"), (3, "ct_only")):
            with self.subTest(mode=mode):
                transcript_layout_path(self.root).write_bytes(self.before)
                dialog = LayoutReviewDialog(self.owner, self.root)
                dialog.layout.set_selected(selection)
                dialog.page.set_text("2")
                dialog._apply()
                result = read_resolved_layout(self.root)
                self.assertEqual(result["mode"], mode)
                self.assertIsNone(self.owner._rt_ct_split_mode_pending)
                dialog.destroy()

    def test_invalid_pages_and_prepared_work_preserved(self):
        self.dialog.layout.set_selected(1)
        for value in ("", "zero", "0", "4", "9"):
            self.dialog.page.set_text(value)
            self.dialog._apply()
            self.assertEqual(transcript_layout_path(self.root).read_bytes(), self.before)
        self.owner.block = True
        self.dialog.layout.set_selected(3)
        self.dialog._apply()
        self.assertEqual(transcript_layout_path(self.root).read_bytes(), self.before)
        self.assertIsNone(self.owner._rt_ct_split_mode_pending)

    def test_stale_case_running_source_and_artifact_are_rejected(self):
        self.dialog.layout.set_selected(3)
        self.owner.root = self.root / "other"
        self.dialog._apply()
        self.owner.root = self.root
        self.owner._pipeline_running = True
        self.dialog._apply()
        self.owner._pipeline_running = False
        page = self.root / "text_pages/0001.txt"
        original = page.read_bytes()
        page.write_text("changed")
        self.dialog._apply()
        page.write_bytes(original)
        self.assertEqual(transcript_layout_path(self.root).read_bytes(), self.before)
        transcript_layout_path(self.root).write_bytes(self.before + b"\n")
        self.dialog._apply()
        self.assertIsNone(read_resolved_layout(self.root))
        self.assertIsNone(self.owner._rt_ct_split_mode_pending)


if __name__ == "__main__":
    unittest.main()
