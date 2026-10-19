# Unified Model and Profile settings — 2026-10-19

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
