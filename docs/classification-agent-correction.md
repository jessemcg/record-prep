# Classification agent correction

**Correct classification with agent** is the last process in **Classify**, after
Classification names and before Build TOC. It uses the shared **Model settings →
Agent** Pi model/reasoning preferences, not the classifier endpoint, its reasoning
toggle or its worker count. Choose an image-capable agent model. This is another
potentially billable operation. It does not run automatically when opening a case,
changing settings or upgrading RecordPrep.

## User workflow

The pipeline is **Basic → Advanced → Dates → Names → Correct classification with
agent**. The earlier deterministic correction stage has been removed, not hidden
inside Advanced. Structural validators remain. For a complete run, set **Run through**
to the agent row, then run from Basic. You can still stop at Names for manual review.
The retired correction endpoint maps to Advanced in memory without rewriting settings.

Use the agent row's **Run** or **Run from here** to review the saved Names inputs;
it does not rerun earlier stages. Manual edits to those inputs are included. Existing
legacy final files serve as Names inputs until new-format Names files exist. No
checkpoint deletion or bundle migration is required.

New filenames (same pattern for CT):

```
RT_basic.jsonl
RT_basic_advanced.jsonl
RT_basic_advanced_dates.jsonl
RT_basic_advanced_dates_names.jsonl
RT_basic_advanced_dates_names_corrected.jsonl
```

Only the last file is the new downstream final. A successful zero-change review
still publishes it. Existing `*_basic_advanced_corrected_dates_names.jsonl` bundles
remain readable without renaming. `recordprep/classification_files.py` owns this
resolution for TOC, boundaries and participant navigation; it never mixes old and
new RT/CT families.

Python supplies a metadata-only prioritized worklist: selected-report opening/ending
neighbors and hearing/minute starts first, then potentially eligible unnamed report
starts and named forms. RT cover/index-to-body transitions and consecutive hearing
starts receive explicit evidence checks, never automatic promotion/demotion. A
recovered hearing start also needs a date check because Dates has already run.
Repeated dates are hints, never proof of duplicate orders. All minute candidates,
including undated ones, remain in this review worklist and the counterfactual
impact projection. Shared minute range enumeration adds ending-neighbor hints:
inspect separately identifiable orders/forms incorrectly absorbed as continuations.
During the existing pass, check minute identity and recover a supported proceeding
or minute-record date (including identifying top fields), also after recovering a
missed minute start. No extra mandatory pass is added. A confirmed false minute
needs its appropriate nonminute type, not merely demotion to a minute body; an
empty date alone is never grounds to guess a type.
The agent still scans every classification metadata block for additional missed
eligible documents, but uses targeted text to triage before opening images. It
avoids repeatedly rescanning all blocks and prioritizes:

- Interruptions or premature endings of named reports, including report pages that
  resemble forms, orders, tables or signature blocks.
- False hearing/minute/report/form starts, especially continuation pages mistaken
  for starts; separate adjacent documents must not be merged automatically.
- Missed eligible documents, including cases where missing starts or names conceal
  them from downstream work.
- Consequential dates/names, following current structural rules and the selected
  naming catalog. Current hearing-notice/service-proof exclusions remain in force.

An isolated unnamed document should receive no further taxonomy cleanup or manual
cleanup finding when it does not hide an eligible document or alter a selected
document's range. Unnamed starts still end previous reports. Every change and
unresolved question must identify the affected document/entry or the suspected
catalog-eligible missing identity, not merely an inconsistent label. No blanket
report-gap filling or historical-label matching. Source content is evidence, never
instructions.

Confident structural changes are independent of uncertain metadata. A clear form
misclassified as a minute-order start can be corrected and its inapplicable minute
date removed without choosing among conflicting form dates. Only a still-material
remaining question belongs in unresolved; it does not block the confident change.
This is reasoning guidance, not a deterministic visual classifier.

After accepted/impact-effective corrections, Python appends deterministic
`minute_date_unresolved` warnings to the **new** receipt for remaining undated or
invalid-date minute candidates. Each includes its complete source range and explains
omission on explicit downstream rebuilding, source availability and the distinction
between eligibility failure and misclassification. A repaired date/type removes that
candidate from these post-correction notes. Historical receipts are never changed on
load. No receipt schema or read-only View review/save workflow changes. The shared
`minute_selection.py` implementation is part of the review runtime guard.
See [minute selection](dated-minute-selection.md) and its [validation](dated-minute-selection-validation.md).

Python applies supported changes to separate `*_dates_names_corrected.jsonl`
finals. Names inputs retain their exact bytes and mtime. Zero-change output copies
those input bytes; an identical existing final keeps its mtime. The agent has no
direct write access to these files. Every
proposal is considered independently. Matching before-values, known same-side
page types and usable naming/date/report fields protect the source-to-output mapping;
a proposal that cannot be applied retains its original row and is saved under
Not applied, with a finding for human review. It never cancels other useful changes.
Image-read bookkeeping, adjacent-page evidence, block coverage and explanatory
formatting are **advisory**, not publication gates. An otherwise usable correction
is retained even when an image read cannot be confirmed, with an explicit review
note attached to that page. These notes are not independent visual verification.
There is no mandatory extra model pass or paid repair loop.
Python also compares selected document identities, dates, starts and extents with
each proposed edit removed from the jointly corrected result. An edit with no such
effect is not applied and is recorded in `review.not_applied`, even if the agent
claimed an impact. Necessary cooperating edits (such as two pages repairing one
gap) survive together. This projection includes all hearing/minute starts, named
reports/forms, and unnamed starts that split named reports. It is not a semantic
classifier and does not infer missing names. Structural validation cannot prove
semantic correctness or that an image was understood. Human review remains necessary.
A malformed findings list, duplicate page proposal or unusable candidate does not
stop downstream work: keep usable findings, retain originals elsewhere, and label
coverage/format limitations honestly. A wholly unreadable candidate yields unchanged
Names-based finals and a visible partial-review note, never a claim of a complete
zero-error review. Fenced JSON and PNG evidence citations are handled without
throwing away otherwise usable proposals. The raw candidate is always archived.

Ambiguities are recorded without speculative edits. A completed review can have
zero changes and/or unresolved findings. Inspect **classification/agent-review.json**
for changes, before/after field values, evidence pages and unresolved items. The
row now displays persistent correction/finding counts; **View review** opens a
read-only, selectable, scrollable findings view with unresolved items first,
with advisory evidence/coverage notes, followed by applied corrections and the
complete proposals not applied, each with a specific explanation. The row also
identifies review notes and partial coverage rather than claiming full review.
Its header identifies
the bundle. It has no save/apply action and renders model prose as plain text.
Counts refresh on case selection/reopening and stage completion. Clearing the case
removes the displayed result. Old receipts work without migration; unavailable or
malformed receipts show a safe message without changing completion badges.

New receipts also contain Python-owned `telemetry`: configured inherited agent
preferences, successful allowed-input read calls, text/image call counts and
distinct page counts, agent-process elapsed time, and elapsed time from stage entry
through publication preparation. The last measurement deliberately excludes the
final receipt/file replacements; the terminal reports total elapsed time after
publication. Direct publisher callers without a run clock record null elapsed
times, not invented durations. Pi may adjust unsupported reasoning; the recorded
preferences are not a claim of provider-confirmed effective settings. Read counts
prove successful tool responses, not comprehension or full-page coverage. No full
sessions or source text are retained as telemetry. Older receipts display timing
as unavailable. Shared reasoning preferences are not lowered or overridden.

Unresolved findings do not by themselves block downstream processing; decide
whether to inspect them first. Saved-review presentation does not hash current
source/classification files or claim later manual edits were reviewed.

## Preservation and publication

Before any replacement, exact Names inputs, prior final outputs (under
`prior-outputs/`), the previous receipt, raw `review-candidate.json`, raw
`review-reads.jsonl` bookkeeping and an audit are archived in:

```
.recordprep/classification-review/<unique-run-id>/
```

The receipt identifies that relative archive path. A rerun makes a new archive;
prior archives and manual edits are never used as hidden resume checkpoints.
A previous receipt is also preserved. These files contain case data and should
remain with the private bundle, never in source control or public test fixtures.

The original Names provenance is not rewritten to claim the classifier generated
agent corrections. The review receipt separately records actual input/output
hashes, current rules/catalog/model preferences and runtime identity. Downstream
TOC/boundary work already consumes actual final bytes, not historical Names metadata.
Explicitly rerunning any classification stage marks review required but leaves
prior finals on disk; rerun agent correction before new downstream preparation.
Rerunning the agent starts from Names, not the previous corrected final: manual
final edits can be superseded, but are archived first. Existing downstream
artifacts are not deleted or regenerated by the review. Explicitly rebuild the
TOC/boundaries and any desired downstream work after changing classification.

Badges and Resume remain presence-based, not model/freshness based. This new step
has its own completion receipt. New workflows additionally require the final files
and no `classification/review-required` marker. An explicit classifier/review run
writes that marker before work; failure or Stop leaves earlier files intact but
blocks stale final/legacy fallback. Successful publication clears it. Resume can
therefore select review after a Names rerun even with an older receipt still on disk.
These are publication-state checks, not historical model/source hash checks.
A present receipt does not certify later manual edits. Saved findings remain viewable
even while a new review is required.

Source PDFs/text/images, earlier classifications, private config/profiles, manifest,
TOCs, boundaries and summaries are never edited by this stage. Inputs, source
inventory/bytes, layout, rules, shared agent preferences and prior receipt are
rechecked before publication under the existing case-profile publication lock.
Changed inputs, Stop and unsafe/unwritable publication preserve prior canonical
outputs. Ordinary write failures roll back from exact captured bytes. Candidate
quality and evidence bookkeeping do not trigger this rollback or discard a review.
If an agent exits abnormally but leaves a candidate, usable proposals still publish
with a partial-review note. An agent failure without any candidate still reports
an execution failure; there is no review result to recover.
On Stop or a hard publication failure, the runner attempts to preserve only the
candidate and read bookkeeping in a private machine-local
`~/.cache/recordprep-pi-workspaces/review-attempt.<id>/` directory (or the effective
XDG cache root). It prints that location; no full session is retained. This is for
manual inspection, not a Pi resume session or an automatic cross-run checkpoint.

Multi-file replacement is not an atomic filesystem transaction. A durable
`.recordprep/classification-review-pending.json` marker identifies the recovery
archive before replacements begin and is removed only after commit or successful
rollback. If interrupted by a crash, the UI refuses new pipeline work and the
review refuses a new run until the archived originals/current files are inspected
and recovered deliberately. Do not simply remove this marker and trust mixed files.
A rollback failure intentionally leaves the marker. No startup repair/migration.

## Implementation and limits

- `recordprep/classification_files.py`: canonical filenames, legacy compatibility,
  review-required/publication readiness and shared downstream resolution.
- `recordprep/classification_review.py`: source/contract snapshots, 80-row metadata
  blocks and prioritized worklists, selected-document impact filtering, per-proposal
  applicability and advisory review notes, telemetry, read-only result formatting, backups, rollback and
  receipt publication.
- `.pi/skills/recordprep-correct-classification/SKILL.md`: fixed impact-focused method.
- `.pi/extensions/recordprep-classification-review-tools.ts`: exact read allowlist,
  private candidate-only writes, successful-read journal, no shell or other tools.
- The established native runner owns the interactive VTE session, shared model
  settings, Stop/process-group termination, stall monitoring and workspace cleanup.
- No new framework, dependencies, profile schema, Focus contract, classifier model call,
  launcher or keyboard mapping. No stage-specific model overrides.
- The agent is instructed to read and report every metadata block, but incomplete
  coverage is a visible limitation, not a reason to discard useful work or stop
  downstream processing. Even complete read bookkeeping is not proof of exhaustive
  semantic review. Large records use bounded reads and Pi compaction.
- Historical fully unmarked report files remain unmarked. The reviewer refuses
  mixed/inconsistent report checks rather than silently migrating a bundle.
- Without a selected naming catalog, existing names can be preserved/removed, but
  new nonempty names are unresolved/manual work rather than invented titles.
- Explicit review runs start fresh. Minimal candidates/read bookkeeping survive
  Stop/hard failure when safe to retain; full sessions are cleaned. Successful
  publication archives the raw candidate, including unused/malformed findings.
  Cross-run incremental review/checkpoint reuse is not implemented.

## Knowledge-work result policy (2026-11-05)

This supersedes historical strict-output acceptance descriptions in the validation
history below. Deliver useful results, not all-or-nothing model-output validation.
Evidence/coverage limitations are review notes; inapplicable individual patches
retain their originals and their proposals without cancelling usable corrections.
Only source/selection changes, Stop, unsafe access or inability to publish safely
remain hard failures. No new submit/validation tool, mandatory model retry, extra
paid pass, private bundle repair or settings migration is introduced.

Acceptance for this policy: **906 tests, 898 passed and 8 skipped** (93.298s),
including 20 new best-effort scenarios and the updated review tests. A separate
fatal-critical GTK acceptance opened View review and verified advisory notes,
partial-review counts, retained unapplied proposals, read-only text and unchanged
receipt bytes/mtime; local accessibility/screenshot observation confirmed the view.
Resource/skill checks, offline registered-tool audit, compile and offline wheel/sdist
build passed. Evidence: `/tmp/recordprep-advisory-review.iq0lmV/` (`full-final.log`,
`gtk-notes-final.log`, `resources-final.log`, `skill-final.log`, `tools-final.log`,
`build-final.log`, `dist-final/`). All cases/providers were fictional/offline; no
real case processing, settings writes, paid rerun or maintained-app restart occurred.
The previous failed run's already-deleted workspace was not recovered.

## Validation

Use isolated HOME/XDG/config and a disposable source checkout/environment. Tests
contain newly authored fictional scenarios and fake/offline model execution only.
No private record contents, page-linked examples or corrected files are fixtures.
Local acceptance on 2026-11-05, isolated checkout/environment at
`/tmp/recordprep-agent-review.OB5FxG`:

- Full unittest suite: 860 run, 852 passed, 8 skipped (84.391 seconds).
- Twelve new offline tests: continuity/false starts, exact no-change preservation,
  archive/audit, unsupported proposals and fields, evidence/coverage/staleness,
  rollback/pending marker, symlinks, native runner/shared settings, stale dates,
  unapproved names, unresolved-only completion, mixed RT/CT and RT-only preservation,
  pipeline placement, and actual extension/SDK read execution without network.
- Native resource validation, compileall, offline wheel/sdist build, wheel module
  and sdist extension/skill inclusion, and diff whitespace checks passed.
- Separate synthetic native GTK instance with fatal criticals: six Classify rows,
  new row after Names/before Organize, activity terminal and Pending badge verified
  with assertions, accessibility tree and targeted screenshot. No case selected.
  Temporary process exited; maintained application was not restarted.
- No live provider/OCR call, real bundle processing, private configuration/profile
  change, checkpoint reset, launcher/mapping change, commit, push or deployment.

No live model-quality, accuracy, cost or performance claim is implied by these
checks. Targeted images were synthetic; real-record semantic acceptance remains a
separate, potentially billable review run.

### Impact-prioritization and results-view follow-up (2026-11-05)

- Full isolated suite: **869 run, 861 passed, 8 skipped**, 84.476 seconds.
  Twenty-one classification-review tests now include priority ordering, no-impact
  proposal suppression with exact byte/mtime preservation, cooperating gap fixes,
  protective unnamed boundaries, newly recovered eligible documents, historical
  name aliases, independent type/date correction, read-call/unique-page telemetry,
  old/malformed receipts, case-clear presentation, and read-only view/caret-at-top.
- The first background full-suite invocation failed three unrelated PTY Ctrl+C
  checks (background signal inheritance); foreground reruns passed. No installer
  code or tests were changed to accommodate it.
- Native GTK acceptance in a separate synthetic app: clicked **View review**,
  verified persistent counts, read-only AT-SPI state, unresolved-before-corrections,
  telemetry and archive details, and a readable targeted screenshot. Fatal GTK
  criticals enabled; transient Vulkan swapchain warnings occurred during window
  presentation, not application criticals. The maintained app was untouched.
- Skill validator, native resource validation, offline registered-tool audit,
  compileall, offline wheel/sdist build, and diff whitespace checks passed.
- Evidence: `/tmp/recordprep-agent-review.OB5FxG/tweaks-full3.log`,
  `gtk-tweaks.log`, `tweaks-build.log`, and the disposable `tweaks-dist/` artifacts.
  Tests/GUI use synthetic data only. No case files or private settings were
  modified, no agent rerun/live provider calls, no commit or push.

The new prioritization is intended to reduce low-value work; its live speed and
semantic quality have not yet been benchmarked. Old receipts are displayed as
recorded, not retroactively filtered or furnished with invented timing.

### One correction stage and separate finals (2026-11-05)

- Full isolated suite: **877 run, 869 passed, 8 skipped**, 84.492 seconds.
- Added resolver coverage for legacy/new families, mixed/RT-only/CT-only inputs,
  incomplete outputs, required-review and pending-publication states, and legacy
  generic participant navigation. No automatic renaming or fallback after failure.
- Added evidence-backed RT start/date recovery, non-mutating adjacency hints,
  zero-change separate publication with identical-final mtime preservation, and
  rollback of manually edited prior finals while keeping review required.
- Existing synthetic pipeline/native-consumer tests now explicitly publish an
  offline zero-change agent result before downstream work. No real model calls.
- Separate fatal-critical GTK process: five Classify stages in order; retired row
  and Run-through endpoint absent; dropdown initialization makes no settings-save
  calls. Verified through assertions, AT-SPI and targeted screenshot, then closed.
- Native resource/skill validation, registered-tool audit, compileall, offline
  wheel+sdist build and changed module/resource byte parity passed. Source and
  disposable test checkout matched. No Focus, launcher or XREMAP changes needed.
- Evidence: `/tmp/recordprep-agent-review.OB5FxG/rename-full4.log`,
  `gtk-rename.log`, `rename-build.log`, and `rename-dist/`.
- No private bundle/settings changes, automatic migration, maintained-app restart,
  paid agent rerun, commit or push.
