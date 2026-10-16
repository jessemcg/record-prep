# Hearing readability and named-report selection — 2026-10-16

## Status and safety boundary

**Later hearing editorial follow-up:** [Hearing editorial method](hearing-editorial.md)
now strengthens orientation, integration, quotation grammar and contradiction handling,
and omits hearing capitalization announcements. The model comparisons below tested
the earlier prompts, not that follow-up. Its synthesis-only change reuses current
hearing digests; it does not reapply the extraction invalidation documented here.

**Subsequent approved change:** [Minute selection](minute-selection.md) now changes
the shared minute-writing method. Statements below about unchanged minute guidance
and reusable minute work describe this earlier hearing/report/TOC change alone;
they do not establish freshness under the subsequent minute method. No existing
private output was rewritten by either implementation.

**Implementation/isolated validation: PASS. Model-quality acceptance: NOT MET.**
The bounded comparison establishes a substantial paragraph-structure improvement,
not reliable factual attribution or complete quotation distribution. Remaining
failures are recorded below; do not describe this as fully accepted model quality.
No unattended retry/tuning loop or additional quality-enforcement pass was added.

Work ran only on the current computer, `work`. Starting tree was clean at
`72c0487c8b8c83a920a1b712ecc6bd8f00cbd4e2`. No supplied case material was read or sent
by this implementation/evaluation. No real bundle, configuration, personal profile,
accepted revision, classification, summary, edition or index was edited. No real
case refresh, maintained-environment sync, dependency/entry-point/launcher change,
cross-repository source change, other-computer access, commit or push occurred.
Focus was not opened or controlled. No old headings are hidden dynamically.

The earlier investigation's **20 named reports / 34 known-date minute-order TOC
entries / all 49 separate underlying orders** are read-only projections for the
supplied bundle, not regenerated or independently recounted results here.

## Implemented contracts

### Hearing writing and quotation selection

`summary_profiles.py` owns the full hearing quotation-distribution and readability
checklist plus a short fictional before/after regrouping example. It distinguishes
unlimited overall coverage from short focused paragraphs, splits changes in issue,
argument, attribution or ruling, integrates overlapping digests and distributes
appropriate exact quote anchors across substantive paragraphs. Extraction asks for
anchors covering materially different positions, important conditions, disputed
evidence and reasons, not merely headline rulings or generic names/dates.

The same hearing method is composed into unassigned compatibility guidance. Exact
previous built-in values remain recognized; genuine custom prose remains
byte-preserved and subordinate. Topic catalogs, report extraction, private guidance
and the canonical paraphrase-plus-evidence digest schema are unchanged. Thin hearing
skills, the profile synthesis resource and the synthesis-only tool wrapper reinforce
the protocol. The **shared extraction extension is byte-unchanged**.

No output-length cap, blocking quality validator, sentence splitting, truncation,
repair loop or new model pass was introduced. Missing suitable anchors can remain
paraphrase; quotations must not be fabricated, forced or repeated for formatting.

### Paragraph preservation

Normalize CRLF/CR, split strings at explicit blank-line delimiters, and collapse
ordinary whitespace inside each paragraph only. Single newlines remain soft wraps.
Candidate normalization, direct section rendering and deterministic digest fallbacks
share this handling. Array/word/placeholder order survives. Unknown-placeholder
fallback, all-null handling, capitalization checks and nonfatal warnings remain.

### Navigation and work-item selection

- Build TOC no longer invents provisional report labels at run starts.
- Find boundaries requires a nonempty report name at the run's start.
- Correct boundaries omits empty/unresolved actual names, regardless of an old
  synthetic `report_label`. Named one-page, missing-date and distinct same-name/date
  reports remain. The unrelated legacy one-page removal rule is not restored.
- No source page/classification is changed or deleted, no title is inferred, and
  no unnamed fragment is merged across a non-report gap.
- General without approved report names has **zero eligible report summaries**.
  No catalog is automatically changed to compensate.
- Build/Find/Correct messages give omission counts and explain that sources remain.
  Historical artifact readers continue to show old output as stored.

Correct TOC now works for both profiles and unassigned cases. It retains the first
known date inside MINUTE ORDERS in existing source order; supported long/abbreviated
US, numeric US and ISO date spellings use a conservative parsed date key. Unknown,
unresolved and invalid dates stay independent. Other sections/formatting survive.
Completion independently checks for removable dates, so Resume cannot use the
former profile bypass. Separate profile-bound same-day boundaries/summaries are
unchanged; TOC correction never touches minute checkpoints.

### Reconciliation and honest freshness

`reconcile_digest_rows` prunes absent IDs and copies retained rows with the current
contiguous work-item ordinal. IDs, labels, source/generation fingerprints, category
evidence, quote IDs/text/verification/offsets stay unchanged. Read-only checks do
not mutate the caller's historical rows. Explicit normal publication updates the
Markdown and metadata together before synthesis rereads the published dataset.

A new regression test exposed another relevant weakness: freshness checked only
retained rows' fingerprints, so a shrunken profile dataset could incorrectly take
the runner's no-model fast path. Freshness now also compares the complete ordered
`(item_id, ordinal)` dataset and metadata's expected IDs/count to current work items.
Thus valid named-report extraction is reused, but synthesis must rerun without
removed fragments' context. No freshness marker is fabricated to reuse stale text.

- Derived selection `boundary_inputs.contract_version`: **1 → 2**. Old profile-era
  TOC/boundary markers are pending; classification/naming components are unchanged.
- Hearing extraction core/skill guidance honestly stales hearing extraction.
  An isolated control/treatment fingerprint comparison confirmed unchanged report
  extraction **and report work-item generation** hashes, classification components
  and native generation components; hearing extraction and both final-synthesis
  hashes change. Final treatment prompt/config values also matched the evaluated
  treatment values exactly after implementation was finished.
- Synthesis content contract **3 → 4** and renderer **6 → 7** stale affected finals.
  Report extraction contract/resources/catalogs remain unchanged.
- Minute generation is unchanged. Same-day order boundaries and valid checkpoints
  remain reusable after explicit boundary publication.

Native runtime projection includes the boundary prerequisite. Its sole native
code dependency change is the selection contract literal **1 → 2**, not participant
or overview generation. `native_runtime_compat.json` narrowly accepts the reviewed
72c0487 stage hashes under the new exact projected-code baselines, retaining its
older reviewed entries. This is application-owned read-only compatibility, **not**
a private-artifact migration. Source/component/model/input checks still apply.
Unchanged hearing/RT inputs therefore reuse participants after boundary rebuilding;
overview input hashes still require regeneration when summaries change.

## Isolated automated and desktop validation

Disposable source/environment: `/tmp/recordprep-selection-ITRpgg/{source,env}`;
control: tracked `git archive 72c0487` under the same scratch root. Source copies
contained tracked files plus the new fictional tests/fixture only. Separate temporary
HOME/XDG/config/cache state and `PI_RUN_METRICS_ENABLED=0` were used. Provisioning and
execution used the absolute UvEnvironments `project-env` helper with explicit
`--project` and `--environment` overrides, never the maintained environment.

Results:

- Full documented unittest discovery: **626 run, 624 passed, 2 skipped**, final run 20.867 s.
  Skips are the optional sibling passive-metrics launch-policy/SDK harness, absent
  from the isolated source. No metrics collection was enabled. The installed Pi SDK
  plus a copied offline fixture exercised participant/overview/quote-display tests,
  including the actual synthesis-only wrapper schema, with fake offline responses.
- **120 Python files** compiled across application, tests and tracked `.pi` helpers.
- `.pi/scripts/run_recordprep_skill.py --validate-resources`: PASS.
- Agent Skill validator: both changed hearing skills PASS.
- Real application classification/TOC/boundary workers, publication, completion,
  cancellation and Resume predicates run against temporary synthetic state. TOC
  correction preserves retained CRLF line endings and final blank lines as well
  as unrelated sections; its successful toast reports the actual removal count.
- Profile pipeline acceptance: General (zero eligible reports) and Dependency
  (named report) PASS through participants, summaries/minutes, overview and source
  map with offline candidates. No model call occurred in these automated checks.
- Real summary runner shrink acceptance: 3 original extraction calls, then **zero
  extra extraction calls** after pruning middle report; a second synthesis receives
  only the 2 retained reports. Published ordinals, metadata and completion agree;
  a subsequent run makes no model calls. Caller-owned old rows remain unchanged.
- Actual TypeScript dataset tools: retained ordinal 2, submitted-section read,
  overview, scratchpad progress and finish diagnostics all agree on 2 documents.
- Same-day profile acceptance: one dated TOC entry, **two separate order boundaries
  and two valid checkpoints**. Further TOC correction changes neither boundary nor
  checkpoint bytes/mtime; the next minute stage reuses both without generation.
- Native tests preserve participant bytes/mtime after report-boundary rebuilding,
  including supported historical runtime compatibility. Old derived-selection
  markers are stale without staling any classification stage or writing on read.
- Embedded CRLF/blank breaks, soft wrapping, empty entries, already separated
  paragraphs, unknown IDs/fallback, missing anchors, capitalization and all-null
  cases retain their nonfatal behavior. Renderer-to-edition tests validate exact
  printable coverage and quote spans after paragraph separation.

Actual GTK RecordPrep ran with temporary synthetic settings/profile/bundle and a
unique application ID. Its real four organizing workers and completion checks
passed. Local Computer Use screenshot/AT-SPI readback of Edit TOC showed only the
two named reports, the first known date and an independent unresolved date; all
three underlying orders remained. Activity log showed one unnamed run omitted and
one duplicate date removed. No TOC Save or private input action was used. Only the
synthetic process was stopped. No claim of physical keyboard/menu activation is made.

All five fictional model outputs also built/published/validated editions. They have
2/2/2/1/1 PDF pages respectively; TXT bytes remained unchanged and every page-map
coverage/quote-span check passed. Representative hearing/report PNG pages were
visually inspected locally. This validates rendering integrity, not model semantics.

## Bounded paid comparison

### Method and bound

Exactly **11 Pi child runs**, no retries/tuning runs, using:

- Provider `fireworks`
- Model `accounts/fireworks/models/deepseek-v4p1-flash`
- Thinking `high`
- Identical public-derived, fictional topic catalogs for both trees
- Fixture `tests/fixtures/hearing_readability.json`: two entirely fictional municipal
  hearings (sparse scheduling and dense four-party inspection/conditions), two related
  reports, and manually reviewed common hearing digests with source-exact anchors

Production `_run_extraction_child` / `_run_synthesis_child`, staged skills, runtime
contracts, restricted tools, canonicalization and deterministic rendering were used.
The driver constructed fictional work items directly; this live check is not a
claim of model-powered classification/participant identification. Offline acceptance
above exercises the full upstream/publishing paths. For report non-regression, the
unchanged report extraction method ran once per report; both synthesis contracts
received those same two digests. It was not redundantly charged for identical report
extraction. No real case text or personal profile content entered any child.

The common-digest pair isolates synthesis from extraction selection. The revised
end-to-end synthesis then used the two revised model-produced hearing digests.
Automatic Pi/provider retries were disabled in disposable settings. Before each
manual launch, the ledger enforced <12 children and a conservative cost reserve
below $5. No model substitution or provider-access failure occurred. Disposable
credential/catalog copies were private and removed after the final child; original
credentials/settings were unchanged.

| Child | Work | Seconds | Reported cost (USD) |
| --- | --- | ---: | ---: |
| 1 | Control sparse hearing extraction | 11.076 | 0.001366 |
| 2 | Control dense hearing extraction | 33.449 | 0.004016 |
| 3 | Revised sparse hearing extraction | 14.984 | 0.001521 |
| 4 | Revised dense hearing extraction | 22.308 | 0.002867 |
| 5 | Control synthesis, common reviewed digests | 74.141 | 0.009440 |
| 6 | Revised synthesis, identical common digests | 87.040 | 0.011445 |
| 7 | Revised synthesis, revised extracted digests | 76.901 | 0.010629 |
| 8 | Report 1 extraction, unchanged method | 10.319 | 0.001325 |
| 9 | Report 2 extraction, unchanged method | 19.501 | 0.002334 |
| 10 | Control report synthesis | 39.594 | 0.005509 |
| 11 | Revised report synthesis, identical digests | 46.454 | 0.005858 |

Total child elapsed: **435.767 seconds**; available per-assistant-message usage:
86,598 input, 54,126 output, 219,160 cache-read, 0 cache-write tokens; total 359,884.
Reported cost sum **$0.05630884**, not an independently audited provider invoice.
Some runner top-level events reported zero tokens despite message-level usage;
measurements use message-end usage once each, not streamed+final double-counting.
Small sample/model variability and caching prevent general latency/quality claims.

### Paragraph and quotation results

Word counts below expand quote placeholders to actual published source wording;
they are **evaluation measurements, never application limits**.

| Output | Sparse paragraphs / max words | Dense paragraphs / max words | Dense paragraphs with placeholders |
| --- | --- | --- | --- |
| Control, common reviewed digests | 1 / 57 | 5 / **282** | 5/5 |
| Revised, identical common digests | 2 / 36 | 16 / **90** | **16/16** |
| Revised, model-extracted digests | 3 / 53 | 17 / **115** | **11/17** |

The deliberately splittable fixture meets the <200-word paragraph evaluation
criterion and materially improves the oversized control block. Every substantive
paragraph in the revised common-input pair contains source-valid placeholders,
but the wrong-duty-bearer error below prevents claiming all were appropriately
attributed. No unknown-placeholder fallback or missing-section/unread diagnostic
occurred. Anchor presence is not semantic correctness; see the failures below.

Dense extraction retained positions/evidence/conditions, including reserved title
and causation, limited access, independent safety review, refrigeration, restoration,
result sharing and future directions. Quote-bank counts were control **7/7/9** and
revised **9/9/10** for positions/evidence/orders. All source locations verified.
The revised banks broadened some positions, but **did not reliably anchor all
important conditions**. Counts alone would have concealed that failure. Revised
orders lacked useful anchors for refrigeration, restoration/result-sharing and
future-directions passages, leaving those later paragraphs quote-free. Other
quote-free paragraphs followed anchors already used for earlier related points.
They are substantive, not justified connective exceptions in this fixture.

### Manual factual/attribution review — remaining failures

1. **Wrong duty bearer, revised common-input output:** it says the *city* “must mark
   the cable”; the source/digest requires the **utility** to do so. Exact source
   wording with a valid ID did not prevent a materially wrong actor.
2. **Revised common-input integration:** examples include paraphrase followed by
   the same prohibition again (“without ... powered excavation; No powered
   excavation ...”), and a duplicated “state the reason / stating the reason in
   writing” construction. Several anchors are grammatically awkward, including
   “independent engineer should resolve” without a completed object.
3. **Revised end-to-end output:** **six substantive dense paragraphs have no quote**,
   including refrigeration and restoration/result-sharing. Upstream selection plus
   synthesis distribution remains unreliable despite the improved instructions.
4. End-to-end synthesis assigns unsupported gendered pronouns to counsel; fictional
   source/digests supply names/roles but not those genders. The sparse extraction
   also generates low-value absence/evidence narration and repeats the scheduling
   reason across categories. This falls short of attribution/no-inference and
   integrate-once goals.
5. Several model-selected anchors contain 6–7 words rather than the existing 2–5
   guidance. They remain source-exact and publish with advisory length warnings,
   as intended. Reviewed common anchors ending in “a.m.” trigger existing terminal-
   punctuation warnings. No blocking validator or quote alteration was introduced.

Reports retain the January 20 event date, later report dates, February route/cable
preparations and aborted test, and distinguish the proposed March 9 date from an
order. Both outputs use 3 paragraphs per report, with maximums control **76/104**
versus revised **49/108** words. No material chronology/paragraph-structure regression
was found in this small pair. Both still have awkward quote integration/redundant
history; revised “continued to recommends inspection” illustrates that grammar is
not established by quote-validity tests. This is limited non-regression evidence,
not a clean global writing-quality acceptance.

**Overall: mixed result / quality acceptance not met.** Paragraph structure improved;
factual fidelity and end-to-end quotation coverage failed the approved criteria.
Testing stopped after the planned 11 runs. The remaining budget was not used to tune
until green. No automatic real-case refresh is recommended or performed.

Machine-local evidence remains under `/tmp/recordprep-selection-ITRpgg/`: paid
ledger/logs, reviewed common rows, submitted sections, rendered fictional TXT,
`reviewed-stats.json`, edition PDFs/maps/PNGs, GTK readback and test logs. These paths
are disposable, not product runtime data. They contain no exported credentials.

## Subsequent explicit application sequence (not run on the real bundle)

After Jesse decides to proceed, and subject to the quality limitations above:

1. **Build TOC → Correct TOC → Find boundaries → Correct boundaries.** Deterministic,
   no paid regeneration. Reuse valid classification/naming. This selects named
   reports and fixes navigation, never deletes original pages or combines orders.
2. **Create hearing summaries.** Changed hearing extraction guidance requires paid
   regeneration of affected hearing digests, then paid hearing synthesis. This is
   not a renderer-only refresh. Unchanged hearing/RT/citation inputs should reuse
   current participants after boundary rebuilding; rerun participants only if
   independently stale, not merely because reports were omitted.
3. **Create report summaries.** Prune omitted fragments through the normal stage.
   Unchanged named reports reuse valid extraction fingerprints; paid report
   synthesis must rerun for the reduced dataset and changed final contract. Any
   independently stale/missing report digest still requires paid extraction.
4. **Minute-order summaries:** for this organizing-only change, unchanged guidance,
   boundaries/model/source reused existing checkpoints without paid calls. The
   subsequently approved [shared minute selection method](minute-selection.md)
   now stales old minute work and requires explicit paid regeneration per affected
   order. Keep every separate same-day order. TOC deduplication alone is still not
   a reason to regenerate them.
5. **Build summary editions.** Deterministic/no paid calls for current summary TXT;
   hearing/report changes stale their editions. Unchanged minute text/edition can
   remain current. Python verifies complete coverage and quotation spans.
6. **Create case overview**, then **Build source map**. Overview needs paid
   regeneration when summaries change. Profile-bound source-map publication is
   deterministic/no paid call and must reflect the current boundaries/summaries.
   There is no need to rerun source extraction, classification, naming or transcript
   numbering solely for these selection/presentation changes.

Stop, failed child execution or an unusable/unpublished candidate preserves prior
final summaries. Publication remains individually atomic per file, not a multi-file
transaction; normal integrity/freshness checks detect interrupted pairs. No manual
bundle cleanup, metadata repair, private guidance migration or schema migration is
part of this change.
