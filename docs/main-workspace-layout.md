# Main workspace layout

The case summary comes first, followed by the existing boxed pipeline phases,
then Activity. Phase contents, expansion/status behavior and individual-step
menus are unchanged. Settings layouts are unchanged.

## Fixed run toolbar

Run through and Run/Resume/Stop are outside the workspace scroller in the bottom
of the existing Adw.ToolbarView. Run and Resume use native `suggested-action`
accent styling; disabled/running/resume eligibility retains the existing rules.
The selected target is width-bounded and ellipsized, with a 22-character minimum;
popup labels have a 32-character minimum to avoid one-word-per-line wrapping.
Long popup choices wrap rather than omit their text. At 650sp or narrower, the target and action buttons stack.
The workspace has a 420×420 minimum and scrolls vertically without a horizontal
page scrollbar. The terminal retains its own scrolling.

## Activity

Initially only the Activity status and Show details button are visible. The
single working spinner sits beside Activity (not in the title bar), remains
visible with details collapsed while work is active, and stops/hides when idle. The same
terminal/text-view instance is retained inside a Gtk.Revealer; hiding details
never resets output, destroys the terminal, terminates a child or persists a
new preference.

- Starting a step reveals details; warnings/errors also reveal them.
- Native Pi startup reveals details and brings the terminal into view/focus.
- Attempts to collapse details while a native Pi child is active are refused.
- Completion/child exit leaves details available; there is no automatic collapse
  that would hide errors or results. Clear current case collapses the cleared view.
- Existing status messages, Stop, resume/pause rules and terminal child lifecycle
  are unchanged. No automatic pipeline restart or model calls are added.

## Local validation — 2026-11-13

On the home computer, disposable source/environment under
`/tmp/recordprep-layout-7Ki7`, isolated HOME/XDG, synthetic settings/pages and
metrics disabled:

- `test_main_workspace_ui.py`: 6 native GTK tests passed. Includes a real VTE
  child running a temporary offline Python fixture (not Pi/model processing),
  successful exit, automatic reveal and retained details after exit; also layout,
  accents, start/error/interactive disclosure, Clear and running control states.
- `test_main_window_ui_state.py`: 50 passed.
- `test_layout_review_ui.py`: 7 passed, retaining the preceding review-dialog work.
- Changed Python compilation and whitespace checks passed.
- Linux Computer Use inspected an actual synthetic RecordPrepWindow on the local
  portrait display, then at 900×760 and 480×720 logical window sizes. Confirmed
  compact idle Activity, steps above it, accent Run, fixed footer and narrow
  two-row footer. AT-SPI Show details changed to Hide details and expanded the
  content. Preview Run was replaced with a no-op; no pipeline was launched.

All synthetic preview processes were stopped; the user's running application,
private settings and real case files were untouched. No paid/model calls,
launcher/dependency changes or deployment. Native tests used the local display
because xvfb-run was unavailable. Physical keyboard/wheel acceptance, live Pi
processing and a full pipeline run were not performed. Tests establish layout
and lifecycle behavior, not model-output quality.
