# TOC editing during downstream work

## Behavior

Modify TOC now depends on the file's presence and the active step, not the
whole-pipeline running flag. Status transitions refresh both the inline action
and an already-open editor's Save button. Opening/saving is allowed during
boundary, numbering, participant, summary, edition and overview work. It pauses
during Build TOC, Correct TOC and Build source map, then resumes when those steps
finish (including failure/stop returning them to Pending).

The first two steps write `artifacts/toc.txt`; profile-aware source-map publication
also reads/hashes it and checks for changed inputs before publishing. Boundaries
are built independently from final classifications, and summaries consume their
boundary/source inputs rather than TOC text. No dependency/fingerprint contracts,
badges, Resume rules or saved artifacts were changed.

Save rechecks the active-step permission even for a programmatic click. It also
compares current file bytes with the editor's last loaded/saved bytes, preventing
an old buffer from overwriting a later pipeline rebuild. A conflict retains the
buffer and file, with instructions to copy desired draft edits and reopen. Opening
and closing without Save remains byte/mtime-preserving.

## Validation — 2026-11-06, Work only

Disposable source/environment: `/tmp/recordprep-live-toc.lhRDKo/{RecordPrep,env}`.
Provisioned explicitly with UvEnvironments/project-env; no production dependency,
private configuration, case, profile or Pi-preference changes.

- UI-state suite: **49 passed**.
- Full offline unittest suite: **922 tests, 914 passed, 8 skipped**, 86.364s.
- Real GTK acceptance under `G_DEBUG=fatal-criticals`: passed. Exercises missing
  file, Build/Correct transitions, opening/reopening and saving during simulated
  report-summary work, already-open Save exclusion during all three protected
  steps, direct signal guards, changed-file conflict and reopen/save recovery.
- Native Computer Use on synthetic PID 146762 confirmed enabled Modify TOC while
  the activity showed Create report summaries running; invoked the action and
  observed the editor's fictional contents and enabled Save (screenshot/AT-SPI).
  Only the synthetic process was closed; the maintained app and open editor were
  left untouched. No model calls or actual pipeline generation.
- Packaged resource validation, Python compilation and `git diff --check`: passed.

The first broad test attempt exposed validation-wrapper issues: a global external
config override bypassed tests' synthetic project settings, an archive lacked Git
metadata, and umask 077 masked a negative fixture's requested unsafe 0755 mode.
The final run used an initialized disposable repository, isolated HOME/XDG with no
external-config override, and a validation-only per-test umask (077 normally, 022
for that existing negative-permissions fixture). No production or tracked test
permission policy was weakened. Logs and wrapper are under the temporary directory.

Restart RecordPrep normally when convenient to load the change. No regeneration
is required. No launcher, CLI, XREMAP, sibling repository or remote-computer changes.
