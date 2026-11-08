# Motion request-and-reasons selection follow-up

Local Home implementation on top of the existing, uncommitted focused cleanup.
This deliberately supersedes its synthesis-only motion selection scope. No commit,
push, deployment, application restart or live provider generation was performed.
The existing real bundle was not regenerated, migrated, repaired or cleared.

## Method and scope

`recordprep/motion_guidance.py` owns the fixed Request / Reasons topics and both
phase builders. The common method now applies selection before saving digest prose
**and its evidence bank**, as well as when writing the final narrative:

- State who requests what from whom and why. For opposition, state the opposed
  request, the denial/limitation/alternative sought and the reasons for resisting it.
  A reply explains its maintained/changed position and answer to the objection.
- Exclude hearing dates/times/departments, street/mailing addresses, case/court
  numbers, incident/tracking identifiers, counsel/contact particulars and caption,
  notice, service and signature boilerplate. The broad identifier-retention exception
  is gone. Source labels and metadata are navigation, not a prose checklist.
- Preserve substantive scope, conditions, alternative relief, distinct grounds,
  material counterarguments, concessions, adverse evidence and uncertainty.
  Supporting declarations/memoranda/separate statements explain the relevant ground,
  not a sequence of component summaries or a factual/procedural inventory.
- Explain an actual procedural ground or requested sanction as a contention and
  consequence, not contact/filing/service chronologies. Preserve the meaning of a
  substantive deadline/duration when itself relief or a disputed ground, not a
  routine hearing setting. Do not invent substantive grounds for boilerplate.
- Choose exact quotation anchors about relief or reasons for/against it. Preserve
  negation, attribution and qualifications; do not expand a fragment into a contrary
  proposition. No quote matcher, source-offset or page-attribution code changed.
- Both phases receive fictional motion/opposition/reply selection examples. Extraction
  is told not to save clutter for a later writer; digest prose is also the existing
  fallback final summary. Synthesis must not reintroduce excluded particulars from
  older digests, labels or evidence.

The canonical extraction and synthesis SKILLs agree with the builder; the offline
packaged prompt-tools source audit is refreshed. No new model pass, word/item/quote
quota, prose filter, content-quality gate or mandatory repair loop was added. Every
selected source page is still supplied, including boilerplate: selection changes
output, not source access. Motion/opposition/reply grouping and support membership,
exact source titles/ranges, headings, source navigation, schemas, IDs, metadata
contract, imperfect-output handling and digest fallback remain unchanged.

## Freshness and adoption

`fingerprint-comparison.txt` compares separate baseline/revised subprocesses under
identical invented model preferences, for current, historical-custom and unassigned
profiles. Motion extraction **and** synthesis fingerprints change. Hearing/report
extraction and synthesis, minutes, motion naming, participant/overview compiled
methods and both native runtime hashes are unchanged from this task's baseline.
Organization guidance and normalization are unchanged; its existing conservative
resource receipt hashes the whole `motion_guidance.py`, so that resource hash changes.
No compatibility entry or receipt was edited to hide the difference.

Adopt through explicit **Create motion summaries**, then refresh the motion edition
and dependent overview/source map as needed. This intentionally regenerates affected
motion digests as well as synthesis; old digests are not falsely relabeled current.
No private profile Save/Reset or upstream classification/boundary/hearing/report/
minute rerun is required solely for the selection method. Existing grouping remains
usable; a separately requested organization run can re-review under its ordinary
resource identity. Presence badges and Resume behavior are unchanged.

## Validation

Machine-local evidence: `/tmp/recordprep-motion-selection.ej23yncv`.
All execution used disposable source/environments through the absolute UvEnvironments
helper with paired `--project` / `--environment` overrides. HOME/XDG/Pi/TMP were
isolated, metrics disabled, and no global config override masked fixture-owned settings.
Sources and provider output in tests were entirely fictional/scripted/offline.

- `full-final.log`: **989 tests: 981 passed, 8 skipped**, 114.043 seconds,
  ordinary unittest discovery with `G_DEBUG=fatal-criticals`. Four new tests cover
  fixed selection, current/historical/unassigned launch/inspector parity, narrowly
  scoped fingerprints and complete-source/substantive-qualification/fallback mechanics.
- `motions-final.log`: **48 motion tests passed**. `focused.log`: **5 passed**.
  `delivery.log`: **6 passed**, including installed-SDK expansion at all 14 actual
  summary-child launch variants (four motion variants), with assertions on the
  complete fixed motion method in the expanded messages, not just skill filenames.
- Eight full-suite skips are the existing three owner-specific model-settings cases,
  three optional external-fixture SDK cases and two optional sibling-metrics cases.
  No test or assertion was weakened, disabled or added to the skip list. The earlier
  first full run failed only because the disposable checkout lacked Git metadata;
  initialized scratch Git repositories fixed the harness, not application code.
- The previously documented GTK viewport assertion did not fail in this ordinary
  run. This is not a claim to have fixed it or to have run the optional-fixture-enhanced
  suite. Normal GTK swapchain warnings remain nonfatal.
- Resource validation, both changed Skill validators and the offline registered-tool
  audit/check passed. Tool definitions, schemas and the delivery contract are unchanged.
  `extras.log`: compilation of **201 Python files**, all **100 wheel payload files**
  and all **242 maintained sdist payload files** matched source; generated `PKG-INFO`
  was checked separately (243 sdist members total). An extracted-wheel isolated import
  confirms both fixed motion methods. No dependency/environment declarations changed.
- `final-preservation.json`: all **405 maintained/test-copy files** match; exactly ten
  paths changed in this follow-up, preserving all unrelated earlier work. The entire
  protected editor, its four explainers/progressions, both shared contracts and their
  original source mtimes are unchanged; both contracts still match Focus. All **307
  real bundle files** retain their original bytes and mtimes. Before/after hash manifests
  pin the evidence; no real case material was copied into source, fixtures or reports.

Offline checks establish delivered instructions, data-path mechanics and preservation,
not guaranteed model editorial judgment. No live rerun of the reviewed bundle or
paid output evaluation was authorized or performed. The separately observed hearing
synthesis fidelity issue was not changed by this motion-only follow-up.
