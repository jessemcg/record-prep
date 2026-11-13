# Transcript layout review dialog

The normal case row retains its source/detection summary but no longer exposes
Transcript layout or RT ends at page controls. Automatic detection still owns
RT-only, CT-only and RT→CT decisions.

A fresh `needs_review` result pauses the run. Once the single step or pipeline
has stopped, RecordPrep opens **Review transcript layout**. Cancel leaves the
artifact untouched; a conditional button on the case row reopens the dialog.
Missing, malformed or stale artifacts require detection again, not manual review.

The dialog starts without a selected answer. RT + CT reveals the last RT
**combined PDF file page** entry. RT-only and CT-only need no boundary. Apply
uses the existing manual-layout validator and prepared-work guard, refreshes the
case summary/badges, and asks the user to Resume rather than restarting work.
The dialog binds to the selected case and original artifact and checks source
freshness again before applying. Failed/canceled drafts never become pending
choices for subsequent work. No settings migration or private config writes.

## Local validation — 2026-11-13

Disposable tracked-source checkout and separately provisioned environment at
`/tmp/recordprep-layout-7Ki7`, isolated HOME/XDG, synthetic pages, metrics disabled.
No model calls, real case changes, production app restart or launcher changes.

- `test_layout_review_ui.py`: 7 native GTK tests passed (all three modes,
  invalid boundaries, prepared-work guard, cancel/reopen, source/artifact/case
  changes, running guard, stale/missing gating and resolved split routing).
- `test_main_window_ui_state.py`: 50 passed.
- `test_transcript_layout.py`: 26 passed.
- `test_resume_preservation.py`: 7 passed.
- Changed Python compilation and `git diff --check` passed.
- Local Linux Computer Use observed the production dialog/case-row widgets in
  a synthetic GTK owner, including initial disabled Apply, visible choices and
  conditional review button. AT-SPI Cancel was followed by observation confirming
  the dialog closed and the review button remained. Synthetic preview closed.

The desktop preview used the actual widgets in a minimal test owner, not a full
pipeline run. Automated GTK tests exercised Apply; no live AI ambiguity run or
physical keyboard/pointer acceptance was performed. The existing running user
application was left intact. `xvfb-run` was unavailable; tests used the local
native display instead.
