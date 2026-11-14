# Main workspace layout

The case summary comes first, followed by the existing boxed pipeline phases,
then Activity. Phase contents, expansion/status behavior and individual-step
menus are unchanged. Settings layouts are unchanged.

The case-summary row ends with a small native flat folder icon, **Open bundle
folder** (also its tooltip and accessible name), after Review transcript layout
when that action is visible. It opens the actual `case_bundle` directory in the
default file manager, without making the summary row activatable or showing a
filesystem path. It appears only when the selected/restored bundle directory
exists, including after Create files; no selection, different-parent PDFs and
not-yet-created bundles leave no placeholder. Source-summary and pipeline-control
updates refresh availability. Browsing remains enabled during preparation and
requires no caption, valid layout, profile assignment or completed output.
Activation rechecks the directory; missing folders and launch failures receive
concise feedback, cancellation is silent, and no folder is created or substituted.

## Fixed run toolbar

Run through and Run/Resume/Stop are outside the workspace scroller in the bottom
of the existing Adw.ToolbarView. Run and Resume use native `suggested-action`
accent styling; disabled/running/resume eligibility retains the existing rules.
The selected target is width-bounded and ellipsized, with a 22-character minimum;
popup labels have a 32-character minimum to avoid one-word-per-line wrapping.
Long popup choices wrap rather than omit their text. At 650sp or narrower, the target and action buttons stack.
The workspace has a 420×420 minimum. The source/steps area scrolls vertically
when necessary without a horizontal page scrollbar. Activity is its next sibling,
outside that scroller, so scrolling steps cannot clip the terminal card's bottom.
The terminal retains its own scrolling.

## Activity

Initially only the Activity status and Show details button are visible. The
single working spinner sits beside Activity (not in the title bar), remains
visible with details collapsed while work is active, and stops/hides when idle. The same
terminal/text-view instance is retained inside a Gtk.Revealer; hiding details
never resets output, destroys the terminal, terminates a child or persists a
new preference.

Expanded Activity fills the remaining workspace height rather than requesting a
fixed 440px terminal. The terminal has a 120px usability minimum; the source/steps
scroller also has a 120px minimum and otherwise requests its natural height.
On short windows or with many phases expanded, steps scroll independently while
Activity stays visible. On tall windows, Activity receives the spare height.
The workspace's 24px bottom margin keeps the rounded card clear of the Run bar.
Output volume does not enlarge the card; output scrolls inside it.

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

### Flexible Activity follow-up — work computer, 2026-11-13

Disposable `/tmp/recordprep-flex-7jdRRD/RecordPrep` and separate environment,
isolated HOME/XDG and synthetic settings; metrics disabled. All 11 focused
`test_main_workspace_ui.py` tests passed under Xvfb, including allocation at
900×760, growth at 900×1600, 480×420 short-window scrolling, output-volume
stability and the offline VTE child lifecycle. Whitespace checks passed.
Linux Computer Use observed the actual synthetic window on the local desktop
(compositor constrained it to 479×1197): rounded terminal bottom, separate
output scrollbar and gap above the fixed Run row were visible. Previews were
closed. Real cases/settings and the user's app were untouched. No live Pi,
model processing or physical keyboard/wheel acceptance was performed.

## Bundle-folder action validation — home computer, 2026-11-14

Used disposable tracked source `/tmp/recordprep-folder-8Eaev4/RecordPrep`, a
separate machine-local Python environment through `UvEnvironments/project-env`,
isolated HOME/XDG/config/Pi state, synthetic directories and disabled metrics.
Startup configuration/resource paths and restoration were inspected before launch.

- 91 focused tests passed: 11 new `test_bundle_folder_ui.py`, 12 case-selection,
  50 main-window UI-state, 11 main-workspace and 7 layout-review tests. Launches in
  automated tests were mocked. Coverage includes restored/prospective roots,
  normal Create-files completion refresh, selection changes/Clear, running and
  interactive state, directory removal/replacement, filesystem errors, Unicode /
  spaces / `#` / `%`, success/cancellation/failure, late completion and disposal.
- Updated the layout-review owner stub for the new handler and repaired the
  existing Clear-case stub's missing Activity-toggle member. No production Clear
  or layout-review behavior was changed.
- Changed Python files compiled in the disposable copy; diff whitespace passed.
- Linux Computer Use inspected the actual synthetic RecordPrep window empty and
  selected, at 900×760 and the compositor-provided **420×720 logical pixels**.
  With both actions visible at 420px, title/subtitle wrapped vertically, actions
  remained inside the row and there was no horizontal page scrolling or new row.
  The preview forced review-action visibility; actual review lifecycle is covered
  by the separate native layout-review tests.
- Accessibility exposed **Open bundle folder**. Pointer hover styling was observed
  on the adjacent review action; Tab from it reached the folder action with the
  native focus ring. Space activated the folder action. Tooltip text is asserted
  by tests; a visible hover-tooltip popup was not separately accepted.
- Actual FileLauncher launches opened two experiment-owned Nautilus windows.
  Their location bars confirmed the exact first special-character `case_bundle`
  and the second newly selected bundle. Clear removed the folder action. Both
  owned file-manager windows and all previews were closed; pre-existing windows
  were left untouched. Synthetic sentinel SHA-256 hashes matched before/after.

No real settings/records, paid calls, pipeline processing, deployment, publication
or user-application restart was performed. Running-state independence was tested
with synthetic UI flags, not a live preparation job. These checks establish the
browsing/UI contract, not full-pipeline or model-output acceptance.
