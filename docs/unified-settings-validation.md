# Unified Model and Profile settings — 2026-10-19

## Confirmed bundled reset — 2026-10-28

**Reset to bundled… → Reset and Save** is the deliberate immediate-save exception
to the ordinary draft/Save contract. It replaces every profile resource from an
exact validated shipped counterpart, after confirmation, through the existing
production preview and managed transaction. Cancel/default/close changes nothing;
invalid discarded drafts are never compiled. Personal ownership, immutable history,
selection/default guards, retained topic IDs/buffers/undo/navigation and callback
bindings remain. Reset does not change Model settings or generated output.
See [implementation, tests and limits](bundled-reset-validation.md) for this
follow-up; historical validation below remains scoped to its original versions.

Pi inheritance follow-up (2026-10-21): see [validation](pi-inheritance-validation.md)
for missing checkout/external preferences and current isolated native Model settings
acceptance. Historical Profile settings evidence below is unchanged.

## Summaries inline-editor follow-up — 2026-10-19

The latest follow-up supersedes the older third-level topic-editor and bounded
**About summaries** descriptions below. The Classification outline is preserved.

- About summaries now contains the complete wrapping explanation directly, with
  no nested scroller or height cap. Hearing topics, Report topics and Minute orders
  use the page's ordinary vertical scrolling; expanding the explanation pushes
  editors below it. About classification retains its existing bounded behavior.
- Hearing/Report topic catalogs have inline expandable cards containing Topic name,
  Topic instructions and Move up / Move down / Remove. Multiple topics can be open
  together. There is no Edit instructions navigation button and no `topic:*`
  NavigationPage: the stack is just home → digest catalog.
- Cards and buffers are retained by stable ID across collapse, page switches,
  reorder, additions and successful Save. Topic titles update their disclosure
  labels. The normal Save/Close/revision guard and no-regeneration contracts remain.
- Topic text uses the existing display-only prose unwrapping: incidental single
  newlines become spaces; paragraph breaks, lists, headings, code and explicit
  Markdown breaks remain. Opening/expanding a topic, or saving an otherwise
  unedited profile, does not rewrite stored guidance. Editing publishes the visible
  draft only through the normal Save flow. Topic text boxes remain locally
  scrollable for long instructions (120px minimum, 300px natural-height cap);
  this does not cap or scroll the About explanation.

### Latest validation

Disposable source `/tmp/recordprep-summaries`, explicitly provisioned environment
`/tmp/recordprep-summaries-env`, synthetic HOME/XDG under
`/tmp/recordprep-summaries-state` and temporary profile stores, on work only.
Startup/config paths were reviewed; no real private config, profile, case bundle,
model call, maintained-app restart or other computer was used by the harness.

- Full suite: **692 run, 684 passed, 7 skipped, 1 existing README-heading failure**,
  the same `test_readme_public_surface` failure reproduced on baseline in the
  outline follow-up. README remains unchanged.
- Final native GTK unified-settings tests: **10 passed**, with
  `G_DEBUG=fatal-criticals` and Cairo. Updated topic-wrapping GTK acceptance passed.
  Coverage includes both catalogs, no third-level destinations, complete explanation
  widgets, literal source preservation on open/Save, paragraph/structured text
  preservation, original bindings, retained buffer/undo/expanded state on reorder,
  topic rename/add/remove, callback rebinding after Save, Save failures and Close.
- Xvfb/Cairo: **36 page/size/theme/font combinations** across Hearing topics,
  Report topics and Minute orders at requested 900×720, 520×620 and 469×620,
  light/dark and Sans 11/16. Complete expanded explanations measured above the old
  140px cap; no ellipsized explanation or horizontal page scrolling. Minute editor
  placement is below the full explanation, reachable by ordinary page scrolling.
  Inspected expanded/collapsed topic cards and the lower minute editor.
- Native Wayland preview identified separately as PID **1241148**, window
  **394828687**, title **RecordPrep summaries synthetic**. Computer Use readiness
  had no blockers and exact focus was verified. Delivered Enter expanded About
  summaries, showing its complete text; an explicit coordinate pointer click opened
  Party Appearances inline without changing page. Delivered Tab visibly focused
  the topic disclosure and Enter collapsed it. Each action was re-observed; no
  programmatic activation is counted as native input. Owned preview exited.
- Compile, sequential PI resource validation, whitespace and tested-source byte
  identity checks passed. No persistence/schema/resource/pipeline/launcher changes.

[Inline Hearing topic](settings-previews/summaries-hearing-inline-520-light.png) ·
[Enlarged Report topic](settings-previews/summaries-report-inline-469-large-dark.png) ·
[Full About summaries in page flow](settings-previews/summaries-about-520-light.png)

Local runners, logs and renders: `/tmp/recordprep-summaries-preview.py`,
`/tmp/recordprep-summaries-*.log`, `/tmp/recordprep-summaries-previews/`.
Preliminary preview checks caught undersized text when disabling the topic editor's
own scrollbar; the final inline editors retain their ordinary scrolling/minimum
height instead. All final results above use the corrected code. The user then
authorized committing this follow-up together with the Classification outline and
pushing the pending RecordPrep commits. No private rewrite or maintained-app restart
is included.

## Classification outline follow-up — 2026-10-19

Classification's expanded home now shows Common guidance followed by two shallow
RT/CT groups. Reporter transcript pages and Clerk transcript pages remain ordinary
Basic editor destinations. Their seven follow-up destinations have a **24 logical-pixel
start margin**, with no end margin; dates and naming are peers, not nested sequential
steps. Membership is presentation-only, keyed explicitly in `profile_editor_ui.py`.
The existing order, titles, stage subtitles, boxed-list surface and suffix arrows
remain. All children stay visible while Classification is expanded. Summaries,
Model settings, retained full-width pages and the flat prompt chooser are unchanged.
No shared navigation hook, private-widget styling, pipeline/resource change,
persistence change, schema bump, migration or output regeneration was introduced.

### Follow-up validation

All execution was local on **work**, using a tracked-source copy at
`/tmp/recordprep-outline`, explicitly provisioned `/tmp/recordprep-outline-env`,
synthetic HOME/XDG state under `/tmp/recordprep-outline-state` and temporary profile
stores. Test config/store setup and startup paths were inspected before execution.
No real configuration, profile store, bundle or maintained application was loaded,
saved or restarted by the test harness; no model requests or other-host actions.

- **Structure/navigation:** new GTK tests check precisely seven insets, zero inset
  on Common/Basic/Summaries and Model rows, unchanged chooser order, all ten
  Classification destinations and their original resource bindings, and Back to
  the still-expanded outline. RT and CT buffers, text and undo survive switching
  and Save; undo after Save creates a dirty draft and Keep Editing retains it.
  Existing tests cover revision guards, failed Save, retained selections/viewports,
  reopening and Close/Discard.
- **Full unittest suite:** **691 run, 683 passed, 7 skipped, 1 pre-existing failure**.
  Unchanged HEAD in the same disposable environment: **689 run, 681 passed,
  7 skipped, the same failure**. `test_readme_public_surface` expects the icon
  immediately after the README heading, but the previously added settings note
  precedes it. README was not changed for this task.
- **Native GTK focused suite:** **9 passed**, final source, with
  `G_DEBUG=fatal-criticals` and Cairo rendering. Compile checks and sequential PI
  resource validation passed; whitespace and tested-source identity checks passed.
- **Layout:** Xvfb/Cairo renders at requested 900×720, 520×620 and 469×620,
  light/dark, Sans 11/16 (12 combinations), plus RTL. X11 decorations consume
  10px of requested width; editor widths were 866/486/435px respectively, still
  full-width within the normal 12px content margins. All Classification arrows
  aligned, all row targets were at least 54px high, no title/subtitle ellipsization
  was found, and both outline top and bottom were inspected. Narrow/enlarged homes
  scroll vertically to reach the CT naming rows, not horizontally. A global RTL
  preview verified the inset moves to the logical start (right), with the opposite
  edge aligned. Whole-row margins leave a modest recessed start edge/separator,
  not disconnected boxes; no brittle internal-label selectors were needed.
- **Delivered native input:** desktop diagnostics passed before interaction.
  Separately identified synthetic windows (owned PIDs 1205482 and 1214329; exact
  window IDs 394828589/394828606) were observed with Computer Use. Real Tab/Enter
  opened Reporter transcript pages; Alt+Left returned to its focused outline row.
  An explicit coordinate pointer click opened Minute-order first pages. On the
  final synthetic window, programmatic focus initially selected Hearing first
  pages, then **delivered Tab** visibly moved its focus border to Hearing dates;
  **delivered Enter** opened Hearing dates. Re-observation confirmed each result.
  These are native input checks, not claims based on `emit("activated")`. Native
  narrow layout was also observed at a compositor-assigned 479px width. Owned
  preview processes exited; the user's open application/documents were untouched.

[Complete outline](settings-previews/classification-outline-520-dark.png) ·
[469px enlarged lower outline](settings-previews/classification-outline-469-large-dark-bottom.png) ·
[469px enlarged editor](settings-previews/classification-outline-469-large-dark-editor.png)

Follow-up logs and preview runner/images remain at `/tmp/recordprep-outline-*.log`,
`/tmp/recordprep-outline-layout.py` and `/tmp/recordprep-outline-layout/`.
Preliminary harness runs collided with the still-running synthetic application's
D-Bus ID and crashed on constructing a remote ApplicationWindow; serializing owned
windows resolved this. An over-specified external-config override also conflicted
with tests' own synthetic legacy config paths; removing it inside disposable HOME
resolved those failures. Neither required production changes. Broadway without a
browser did not allocate preview rows, so layout acceptance used Xvfb and native
Wayland instead. No outstanding native-input limitation for this outline change;
the older report below describes its own earlier validation limitations. Changes
were subsequently authorized for commit and push together with the Summaries
follow-up above; no launcher or cross-project change.

Publication: the user subsequently authorized a separate local commit of these changes. No push or maintained-app restart is included; the native-input limitation below remains unresolved. The no-commit statements describe the validation run.

## Two independent sessions

**Model settings** keeps OCR/Classify/Agent inline in one expandable boxed list. Local OCR and vision start commands open retained, full-width rounded editors with Back and a compact chooser. Profile settings is explicitly a separate transaction. Hidden worker/slot counts and the Pi command are validated before the first write. Failed independent writes retain drafts and report possible partial persistence; Save never closes.

**Profile settings** keeps Classification/Summaries and RT-first/CT-second stage subtitles. A short pinned context summary precedes a collapsed, bounded About classification/About summaries disclosure containing the full existing explanation and task guidance. Guidance and topic instructions have retained full-height rounded, labelled, undo-enabled editors. Topic catalogs retain naming/reordering/removal, addressed by stable IDs rather than positions or names.

Successful Profile Save rebinds the accepted revision while retaining resource containers, buffers, callbacks and navigation; it does not rerender editors. Revision/default conflict checks and active-work guards remain. Publication followed by a display-refresh failure reports “Profile saved” truthfully. No Save regenerates output. Reopening Profile settings finds the application-owned draft even if its menu widget was recreated.

Both windows use independent Close actions with **Keep Editing / Discard Unsaved Changes**, never Save-and-close. Dirty settings veto main-window teardown before servers/jobs are stopped.

## Local validation

Disposable source/environment, synthetic HOME/XDG/Pi state, fabricated machine config and temporary managed profile stores only. Explicit paired UvEnvironments overrides selected RecordPrep. No real bundle/config, service, OCR/model inference, paid request or maintained runtime was used.

- Full unittest suite: **689 run, 682 passed, 7 skipped**.
- Model/Profile/session subset: **9 passed**, with `G_DEBUG=fatal-criticals`.
- Actual visible Save controls; hidden-page validation; failed and repeated saves; unknown/retired machine values; unavailable/pending model retention and stale callbacks; literal Unicode/placeholder text, captured selection, undo capability and viewport restoration; multiple accepted profile revisions and callback rebinding; native catalog rename/move/remove/add; application-owned reopen; failed publication versus saved-but-refresh-failed feedback; dirty Keep/Discard and parent ownership.
- Synthetic teardown drains dialog/clipboard responses before destroying a Wayland surface. The initial immediate-destroy test harness crashed in GTK's Wayland seat callback; draining owned surfaces resolved the native rerun. Inactive Wayland primary selection also clears in a minimal ordinary Gtk.TextView; active Broadway selection restoration passed.
- GTK/Broadway previews: 900×720, 520×620, 469×620, light/dark and enlarged fonts. At 520×620 both command editors were at least **496×505**; all **24** built-in profile instruction destinations were **496×458**. Rounded-edge pixel checks passed. Expanded explanations remained bounded, including at enlarged font size.

[Model home](settings-previews/settings-home-520-dark.png) · [Command editor](settings-previews/settings-520-dark.png) · [Profile home](settings-previews/profile-home-520-dark.png) · [Profile editor](settings-previews/profile-520-dark.png) · [469px profile editor](settings-previews/profile-469-dark.png) · [Large-font expanded explanation](settings-previews/profile-large-explained-469-dark.png)

## Limits and artifacts

The real GNOME desktop was locked during final observation. Broadway screenshots establish layout/rendering, not native Wayland keyboard/pointer acceptance. Unlocked native traversal, focus, selection and viewport delivery remain to check; no other computer is part of acceptance.

Synthetic sources/environment/logs remain under `/tmp/gtk-rollout-20261019/RecordPrep`; see `final-full-result.log`, `final-focused.log`, `settings-all-preview.log` and `profile-all-preview.log`. The root holds bounded `preview.py` and foreground `test.sh` runners. Background-shell SIGINT inheritance caused preliminary unrelated installer Ctrl-C timeouts; foreground full-suite execution passed. No commit/push, maintained-app restart, launcher change, private-file migration, output regeneration or other-host action was performed.
