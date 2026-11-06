"""Actual GTK View review with advisory limitations; synthetic data/settings only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="recordprep-review-notes-ui-")
ROOT = Path(TEMP.name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
            "XDG_CACHE_HOME", "RECORDPREP_CONFIG_DIR"):
    directory = ROOT / key.lower()
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ.pop("RECORDPREP_PROFILE_DIR", None)

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib
from recordprep.ui import main_window as ui
from recordprep import classification_review as review

bundle = ROOT / "Synthetic_bundle"
(bundle / "classification").mkdir(parents=True)
value = {"schema_version": 1, "archive": ".recordprep/classification-review/synthetic",
         "review": {"changes": [{"file_name": "0012.txt", "before": {"page_type": "CT_other"},
                                 "after": {"page_type": "CT_report"}, "evidence": ["0012.txt"],
                                 "reason": "The synthetic page continues the preceding named report."}],
                    "unresolved": [{"file_name": "0014.txt", "reason": "Check the synthetic date if material."}],
                    "warnings": [{"code": "image_evidence_unconfirmed", "file_name": "0012.txt",
                                  "reason": "The image read was not confirmed in the journal. The useful correction was retained; check the source if material."},
                                 {"code": "partial_coverage", "reason": "Only part of the synthetic record was reviewed. Useful findings were retained."}],
                    "coverage": {"complete": False},
                    "not_applied": [{"change": {"file_name": "0014.txt", "before": {"date": "wrong date"},
                                                "after": {"date": "January 2, 2025"}},
                                     "reason": "Before-values did not match; original retained on this page."}]}}
receipt = bundle / review.RECEIPT
receipt.write_text(json.dumps(value))
before = receipt.read_bytes(), receipt.stat().st_mtime_ns
app = ui.RecordPrepApp()
app.set_application_id("org.synthetic.RecordPrepReviewNotes")
errors = []


def drain():
    end = time.monotonic() + .2
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def check():
    try:
        owner = app.get_active_window()
        owner.set_title("Synthetic RecordPrep — advisory review acceptance")
        owner._resolve_case_root = lambda: bundle
        owner._refresh_classification_review_result()
        owner._open_phase_for_step("correct_classification_agent")
        assert owner.step_classification_agent_row.get_subtitle() == "1 page corrected · 1 finding needs review · 2 review notes · partial review"
        dialogs = []
        real = ui.ClassificationReviewWindow
        def open_dialog(*args):
            dialog = real(*args)
            dialogs.append(dialog)
            return dialog
        with patch.object(ui, "ClassificationReviewWindow", side_effect=open_dialog):
            owner._classification_review_button.emit("clicked")
        drain()
        dialog = dialogs[0]
        dialog.set_title("Synthetic advisory classification review")
        assert dialog.get_visible()
        assert not dialog.text_view.get_editable()
        buffer = dialog.text_view.get_buffer()
        text = buffer.get_text(*buffer.get_bounds(), True)
        for expected in ("REVIEW NOTES / LIMITATIONS", "Useful corrections were retained", "partial review",
                         "APPLIED CORRECTIONS", "NOT APPLIED: 1", '"date": "wrong date"'):
            assert expected in text, expected
        assert text.index("REVIEW NOTES / LIMITATIONS") < text.index("APPLIED CORRECTIONS")
        assert (receipt.read_bytes(), receipt.stat().st_mtime_ns) == before
        print("ADVISORY CLASSIFICATION REVIEW GTK ACCEPTANCE PASSED", flush=True)
        if os.environ.get("REVIEW_NOTES_ACCEPT_HOLD"):
            GLib.timeout_add_seconds(120, lambda: (dialog.close(), app.quit(), False)[2])
        else:
            dialog.close()
            app.quit()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        errors.append(exc)
        app.quit()
    return False


app.connect("activate", lambda *_: GLib.idle_add(check))
app.run([])
TEMP.cleanup()
if errors:
    raise SystemExit(1)
