# Dated minute selection (2026-11-10)

This governs **explicit new preparation**, not historical readers or saved-output
cleanup. Recognition-v5 and `dated-minute-selection-1` improve minute/order
separation and require a recognized minute-start date for new navigation and
summary boundaries. [Validation and limits](dated-minute-selection-validation.md).

## Recognition and routing

An actual clerk/court record of a particular proceeding is CT_minute_order.
A Minute Order/minutes heading is strong evidence, not a universal requirement;
recognizable hearing identification, court personnel, appearances/proceedings and
recorded action can establish the function without every field or one layout.
Titleless genuine continuations and integral endings remain minute pages.

Separate standardized/local order or findings-and-orders templates are CT_form,
blank, proposed, signed or entered. Standalone written orders outside the
procedural-filing definition are CT_other. Dates, signatures, judicial findings/
orders language, adjacency or incorporation by reference do not make them minutes.
Recommendations inside reports remain CT_report; substantive requests/advocacy
within existing proceedings remain CT_motion; standalone hearing notifications and
distinct service proofs remain CT_notice and CT_proof_of_service. No taxonomy label
is removed. Nonselected material can still end a selected range and remains research
evidence; navigation eligibility is not legal relevance.

The first-minute check treats Basic as a hypothesis. A false separate order needs
an eventual appropriate nonminute category correction, not merely a minute body
that would merge it into a preceding record. Date extraction reuses the frozen
current minute definition and can read identifying top hearing fields. It excludes
unrelated filing/service stamps, print/revision/reference dates and future settings.
Nonminutes or missing/conflicting/unreadable relevant dates return an empty string.
Never borrow a neighbor's date or invent one to achieve eligibility. Hearing
recognition/start/date prompts and hearing-summary methods are unchanged.

## One selection contract

`recordprep/minute_selection.py` has no GTK or source I/O. On the resolved CT side:

1. Enumerate each explicit CT_minute_order_first_page followed only by numerically
   adjacent CT_minute_order bodies. No implicit start for a leading fragment.
2. Finish every candidate range **before** date eligibility. Every explicit start
   cuts the preceding candidate even if the new candidate is omitted. Gaps and
   nonminute pages end ranges; nothing bridges an omitted candidate.
3. Test the start's date, not its bodies. Accept valid long/abbreviated US dates,
   numeric US two/four-digit years and ISO, with whitespace/weekday normalization.
   Absent, blank, nonstring, placeholder and impossible dates are ineligible.
4. Keep separate same-day candidates. Only existing TOC correction deduplicates
   known same-date navigation entries. Do not rewrite stored date labels/rows.

Build TOC and Find boundaries share these ranges and eligibility in every selected,
custom, historical and unassigned context. No new minute “Date unresolved” TOC entry
is emitted. Explicit Filter boundary entries applies the same predicate to saved
minute entries, including minute-only input; retained metadata is unchanged.
Malformed/reversed/overlapping saved ranges are errors, not undated omissions.
Counts and bounded batches of source-page ranges appear in existing activity logs,
without source prose. Missing dates are an eligibility failure, **not proof of
misclassification**. Source text/images and classification rows are preserved.

Generation provenance advances from contract 5 to 6 and includes the selection ID
and implementation hash. Actual prompt bytes invalidate relevant new-work
checkpoints; old outputs/checkpoints and presence-based badges/Resume are unchanged.
Profile schema 14, shipped profile versions/catalogs and the shared Focus contracts
are unchanged. No settings, CLI, launcher or mapping change is needed.

## Correction, consumers and adoption

Agent correction sees **all** minute candidates, including undated candidates,
in worklists and impact projection. Opening/ending-neighbor hints help catch false
starts and separately identifiable orders incorrectly included as bodies. Supported
type/start/date repairs remain consequential. New receipts add deterministic
post-correction `minute_date_unresolved` notes with full ranges and rebuilding
consequences; old receipts stay literal/read-only. No second mandatory pass.

Minute summaries and source maps consume saved boundaries, with **no hidden second
filter**. Historical undated boundaries remain readable as saved. Rebuilt boundaries
naturally produce fewer minute work items/documents; all physical source pages stay
in the source map. Updating/opening a bundle changes nothing already saved.

Adoption requires a separately authorized explicit classification run through Agent
correction, then affected motion organization, TOC/correction, boundaries/filtering,
summaries, editions, overview and source map according to actual dependencies.
Shared Basic/Advanced execution may include both transcript sides despite unchanged
RT guidance; do not promise CT-only paid work without checking execution scope.
Preserve prior work until guarded replacements succeed. A date-only rebuild removes
undated candidates but cannot correct dated standalone-order look-alikes.

Unreadable genuine minute dates can be omitted; plausible dates may be wrong and
stronger prompts can still misclassify. Offline safety/contract tests do not measure
precision, recall or completeness. Live classifier evaluation needs separate approval.
