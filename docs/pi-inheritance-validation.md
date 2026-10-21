# Pi preference inheritance — 2026-10-21

## Policy

No public or checkout personal Pi defaults are shipped. `DEFAULT_PUBLIC_PI_SETTINGS`
is removed; missing settings consistently resolve to no app override. The local
formerly tracked `.pi/settings.json` is retained byte-for-byte and precisely ignored;
only its Git index entry is removed. Tracked prompts, skills, extensions and scripts
remain. Older downstream checkouts must preserve personal selections **before**
updating: Git removal does not automatically preserve their formerly tracked file.
Existing standalone XDG settings are unaffected. No migration/path changes occur.

Reads/refresh/startup/launch do not create persistent Pi preferences. Model-only
Save stores provider/model only. An unrelated Settings Save no longer writes an
empty effort preferences file. Existing selections/unrelated keys remain; explicit
efforts still use Pi's capability behavior. Catalog index zero is not an implicit
selection. Missing, malformed, unsafe and unreadable settings are distinguished;
staging uses guarded reads, not an unchecked copy or fallback repair.

The RecordPrep-specific synchronized-file permission policy and guarded revision/
locking implementation are unchanged. Classification, OCR, profiles, prepared cases,
historical artifacts and output-presence badges are untouched. Private native and
summary workspaces enable only the required skill-command expansion; discovery does
not force it. Model/reasoning, compaction and retry otherwise inherit.

## Native compatibility review

`paths.py` participates in native stage-code hashes. Its changes are confined to
missing preference reads and private staging, not participant/overview prompts,
input composition, evidence validation, stop behavior or Python publication.
The source-owned compatibility allowlist records the new exact stage-code hashes
and the immediately preceding exact reviewed hashes. Existing model/reasoning and
consumed-source identity comparisons still apply, and changed stage code still
fails the compatibility gate. No case freshness metadata is rewritten or fabricated;
no private artifact, checkpoint or badge is altered. Existing read-only legacy
compatibility and true-invalidations tests remain required and pass.

## Validation

Home only, RTX 3090. Tests used tracked/new-source-only disposable copies and paired
UvEnvironments `/tmp` source/environment overrides, plus temporary HOME/XDG/Pi/state/
cache/runtime paths. Production private config/preferences and the untracked writer
lock remained untouched; no credentials/cases or paid inference were used.

- Full unittest suite: **724 tests, OK, 10 skipped**, including external/shared settings, runtime, permissions,
  model-settings, resources, native guards, case-name, summaries, minutes and installers.
- `test_pi_inheritance.py`: absent checkout/external preferences, explicit model-only
  persistence, malformed/symlink rejection, and ephemeral-only skill controls.
- `acceptance_pi_inheritance.py`: actual native GTK Settings with synthetic catalog,
  Computer Use inspection of fresh inheritance, unrelated Save, deliberate model
  choice, failed refresh, Save/reopen; unknown synthetic keys survive and reasoning
  remains inherited. `--auto` repeats the assertions without desktop input.
- Actual offline Pi RPC with synthetic settings/key verified live global model and
  effort changes between sessions, not copied-once defaults. No prompt was sent.
- Actual network-blocked SDK synthetic streams verified required Focus/RecordPrep
  skill bodies expand (12 skills / 12 asserted synthetic-stream invocations) despite global `enableSkillCommands: false`; global bytes remain
  unchanged. Existing native/summary fake-Pi tests retain exact tool restrictions.
- Optional Pi skip/cancel/failure, install/repair/resume receipts, shell/resource
  validation and bootstrap integrity remain covered. No installer engine or one-line
  command changes were needed. README files remain unchanged by user request.

Machine-local evidence: `/tmp/pi-defaults-start`. Initial PTY cancellation failures
were caused by running tests as background shell jobs with inherited ignored SIGINT;
rerunning with normal SIGINT disposition passed, without installer code changes.
This is not paid-model quality evaluation or clean-distro certification. Rollback
is a source revert, never private preference/artifact restoration or reset.
