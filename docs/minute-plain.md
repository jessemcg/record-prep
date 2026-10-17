# Plain-English minute entries and unbulleted labels — 2026-10-16

Current **minute contract8**, superseding the contract6/7 presentation described in
[minute-compact.md](minute-compact.md). Approved after editorial review of the latest
supplied summary TXT, not an original-source factual audit or private profile audit.
No private facts/quotations are copied into prompts, tests, examples or this report.

## Requested result

Each entry has exactly these four adjacent lines, with **one blank line between
entries and no blank lines inside an entry**:

```text
Date — Hearing type
Appearances: Relevant personal attendance.
Orders: What the court decided, in simple, plain English.
Next: Only the next substantive hearing and date.
```

No leading dashes. Focus makes the three labels bold; canonical TXT keeps plain
prefixes rather than Markdown markers, fake quotations or clickable phrase links.

Orders normally selects one/two headline outcomes, with another when omission
would mislead. State who must do what, what was allowed/denied or what changed.
Translate form/legal language without changing the result; preserve necessary legal
terms, affected people, conditions and substantive deadlines. Setting a hearing is
not granting relief; a delay is not a dismissal; a no-contest plea is not a guilty
plea. Do not replace formal words by mechanical string substitution.

Exclude routine report receipt/preparation, filing/e-filing/portal deadlines,
clerical/service-of-paperwork/calendar mechanics, return/remote-attendance directions,
unchanged-order/statutory/standard recitals and conditional late-filing sanctions
warnings. They do not become headline outcomes merely because the form calls them
orders. An actually imposed consequential sanction or deadline essential to substantive
relief remains eligible. An administrative-only order says **No substantive orders
recorded.**, not invented substance or an inventory of logistics. Unreadable/missing
substantive results instead preserve uncertainty. Next still excludes future reports
and report-only hearings, even if earlier; never relocate that calendar into Orders.

## Scope and preservation

Shared canonical SKILL, neutral `PROFILE_MINUTE_CORE`, profile tool descriptions and
public General/Dependency focus/examples agree. Public focus supplies specialty, not
more fields. Exact preceding contract7 public prose is recognized read-only alongside
older built-ins; genuine custom bytes, private accepted revisions and case pins stay
unchanged. Attendance evidence/location rules, schema4, source pages and authority are
unchanged. No hard quota, truncation/filter, blocking prose validator or extra model pass.

`recordprep-minute-compact-labels-2` honestly identifies new profile rendering.
Explicit `compact-list-1` rendering and the default historical paragraph API remain
supported, without reformatting saved text or rewriting metadata to claim freshness.
New instructions stale minutes only, including legacy SKILL identity; first-page
legacy attendance/reporting and paragraph-format compatibility remain separate.

## Focus companion

The separate Focus repository styles exact minute line prefixes through its existing
bold entry-emphasis tag, for continuous and paginated views. The page-map/PDF text,
quote/search/link spans and schemas do not change. Focus's paginated paragraph-spacing
transformation now keeps a single newline before each minute field, retaining one
blank line before the next entry. Display and paginated search share the same mapping;
page-edge handling and other summary kinds retain their prior rules. No runtime
cross-import or new deployment/dependency/entry-point contract. PDF typography itself
is unchanged; this companion concerns Focus display. See Focus `docs/minute-labels.md`.

## Paginated PDF spacing follow-up

The PDF renderer now also preserves the source grouping: consecutive minute lines
have no extra paragraph margin; a source blank line adds one body line of space
(12.98 pt). Hearing/report rendering remains unchanged. Wrapped lines retain normal
leading, and long entries can span pages without dropping content.

MuPDF merges adjacent lines into text blocks, so minute page-map text restores source
line boundaries through monotonic normalized character alignment. Glyph offsets are
rebased before computing record-page links and quote fragments. Existing Focus v3
readers accept these sidecars without changes. The minute-only layout field
`minute_spacing: source-blank-lines-v1` makes older minute editions pending without
staling hearing/report editions or any AI generation stage.

Minute PDF editions also render the exact line prefixes **Appearances:**,
**Orders:** and **Next:** in bold, including the colon, leaving ordinary field
text plain. These labels create no quotation/search/link spans. The additional
minute-only `minute_label_emphasis: bold-field-prefixes-v1` layout policy requires
rebuilding editions created before this emphasis change. Canonical TXT is unchanged.

To apply **this PDF-only follow-up**, restart RecordPrep when convenient and run
**Build paginated summary editions**. Do not rerun minute generation for spacing alone;
there is no model call or need to change the canonical TXT. Existing private case
artifacts are untouched until the normal explicit build step runs.

Validation on Home (including bold labels): isolated unittest suite **656 run,
651 passed, 5 skipped**; 54 edition tests pass, including four new tests covering actual PDF baseline gaps,
source/sidecar grouping, wrapped and cross-page quotes/links, minute-only freshness,
and actual PDF font flags (only exact minute field prefixes become bold, without
creating quote/link spans).
A rendered fictional PDF was visually checked. No private case content is used in
fixtures or documentation. The supplied existing PDF was inspected read-only and
confirmed the former extra 5.5-point margin after individual source lines.

## Validation and applying later (original summary-generation change)

Disposable local RecordPrep/Focus sources, separate managed test environments, temporary
HOME/XDG/agent state and offline/fake providers; never production configuration/cases.
Tests cover current labels/grouping, exact historical defaults, old contract7 output
remaining byte/mtime unchanged under checks/failed first generation, explicit two-order
publication, unchanged pins/source/config/unrelated artifacts and zero calls thereafter.
Semantic model quality is not proved by those fake candidates.

Before/after `plain-minutes-{before,after}.json` prove only minute identities changed
across unassigned/General/Dependency; hearing/report extraction+synthesis and native
participant/overview runtime identities are identical. No compatibility baselines relaxed.
Reviewed external-settings minute aggregate:
`11b5a941b0d370a71c9893d413a3d839c5fe51ffb7c1715a9b185da02e2597a0`.
Evidence under `/tmp/recordprep-selection-ITRpgg/`: full-suite logs, fingerprint pair,
prior public bytes, fictional actual TXT/PDF/page map and isolated Focus preview.
Final validation: **652 tests run, 650 passed, 2 optional metrics skips**, 21.870 s;
**127 Python paths** compile; Pi resources, changed skill and whitespace checks PASS.
Focus: five new label/grouping/offset tests PASS; full pytest **665 passed, 11 skipped,
1 pre-existing README-anchor failure**, 12.19 s (both affected baseline files identical
to Focus HEAD). No installer/README test change. Synthetic 320 answer/view transitions
PASS under fatal GTK criticals, zero criticals, reading position retained. Actual Focus
preview validates six weight700 non-link labels, one blank line between entries, no
internal blank lines and unchanged fictional case bytes; visually checked through
native local Computer Use, then only that test instance was closed. No live model
writing-quality claim. Focus has 104 active Python paths compiling successfully.

No paid model call/live prose acceptance, real-case regeneration/config/pin edit,
user-app restart/interruption, maintained-environment sync, commit/push or other-computer
access. The companion Focus environment is disposable, not its maintained environment.
When ready, restart RecordPrep and Focus, explicitly regenerate affected minute summaries
(paid per-order generation, not a free reformat), then rebuild affected editions/source
map and the overview through its normal flow as needed. No hearing/report/source
extraction rerun is required solely for this change.
