# Motion papers and logical entries

Motion recognition, naming and Request/Reasons summaries are application-owned;
report/form naming and report topics remain profile-owned. Profile content schema
14 / API 1, bundled Dependency 1.19.0 and Criminal 1.1.0 are unchanged by this work.
See [application-owned naming](application-motion-naming.md) and
[procedural filings](procedural-filings.md). No taxonomy or profile migration occurs.

## Deterministic classification continuity (grouping schema 2)

**Organize motion papers** is an ordinary Python step after final classification
and before Build TOC. It needs no Pi executable, model, credentials, skill, VTE
terminal or provider call. The old runner command dispatches to the same Python
publisher before model/resource preflight. There is no candidate workspace or repair
pass. The row exposes the standard step controls, without a View grouping button.

Starting at an explicitly detected, named motion start, include **every following
adjacent motion-classified page** until another classification or missing numerical
page interrupts the run. Both `CT_motion` and `CT_motion_first_page` belong to the
run. A later motion, opposition, reply, different party, date or title does not split
it. A later unnamed first-page marker starts an internal component and remains included
without naming/model calls. No inferred legal relationship can override continuity.

Each explicit start still defines a physical paper: its own ID, source title (possibly
empty internally), date/date basis and exact contiguous range remain independent.
The earliest component supplies the packet's `motion:<start-page>` ID, navigation
anchor, title and date. Unknown lead dates remain unknown; organization never recovers
dates from text or borrows a later title. Source files/classifications are not rewritten.
“Unnamed motion paper” is presentation text only, never an invented source title.

Leading body fragments and unnamed starts before a usable named lead are omitted from
logical entries, with concise page/count findings. No later title is applied backward.
Service proofs, reports, exhibits, orders, blank/other classifications and missing
classifications break the run. Fragments beyond an interruption are never attached
backward. This fixes grouping, not classification or every legal attachment.

The pure `motion_pages.continuous_selection` helper validates identities, duplicate
records and complete first-page checks before returning ordered physical components,
ordered packet membership and omitted-fragment findings. The final-classification
family comes from `classification_files.final_paths`, including its interrupted-review
and incomplete-final safeguards. Historical named-only selection remains explicit and
separate; loading an old grouping never applies the new selection policy.

`artifacts/motion_groups.json` now writes schema **2**, organization contract
`recordprep-motion-organization-2`. Every selected component occurs exactly once;
members have exact adjacent, nonoverlapping ranges; adjacent selected packets cannot
remain split. The neutral filing role is **motion packet**, with `lead` / `continuation`
component roles and empty inferred party, purpose and relationship-reference fields.
The explanation states classification continuity, not a finding of substantive support.

**Selected-inventory accounting: complete** means deterministic accounting for the
selected inventory only. It is not legal relationship review, semantic certainty, or
inclusion of every motion-classified fragment.

Publication retains the organization lock, root identity, safe reads, Stop checks,
source/classification/policy/implementation/prior-output guards and unique-temp atomic
replacement. Only selected source pages enter the source fingerprint; implementation
resources include selection and shared validation, not model preferences, skill prose,
profiles or unrelated summary guidance. Unchanged schema-2 results retain bytes/mtime.
Unsafe paths, missing/unreadable selected pages, corrupt canonical stores, concurrent
runs, changed inputs, Stop and failed publication preserve prior output. Checked-zero
selection is zero-call. Unnamed-only motion fragments are reported as fragments, not
misrepresented as no motion pages.

## One contract-aware context for consumers

`motion_groups.resolve_context` selects the applicable physical inventory and groups.
TOC and boundary rebuilding use final classifications plus the saved grouping contract.
Summaries and source maps additionally require saved physical boundaries to match a
current schema-2 inventory exactly; mismatch instructs **Find boundaries → Filter
boundary entries** rather than silently dropping components.

- Build TOC emits one title/date line per packet at its lead anchor, never separate
  continuation headings.
- Find boundaries explicitly publishes original physical spans plus included unnamed
  internal components. Organization itself never overwrites boundaries. Named IDs and
  ranges remain stable. Filter boundary entries retains validated packet components,
  while still excluding unresolved standalone papers; report/form filtering is unchanged.
- Motion extraction uses exactly the members, once per work item, with no duplicate
  standalone continuation item. Hashes, quotation verification and context preflight
  follow exact member pages, including historical nonadjacent scopes.
- Source maps keep physical documents, IDs, ranges and aliases. `counts.motions` is
  physical; `counts.motion_entries` is logical. Shared validation checks packet aliases,
  exact page membership and counts against that same inventory. Runtime inputs are
  omitted from published reader context. Focus only validates descriptive metadata;
  its research method is unchanged.

Missing/stale grouping warns and uses historical **named-only** physical singletons,
without inventing unnamed titles or rewriting grouping. Corrupt grouping fails closed.

## Request / Reasons summaries

Produce one summary section per supplied packet; never re-segment it. Explain the
requests and reasons of **all included filings**, keeping party attribution and distinct
or opposing positions within that section. A continuation is not presumed to support
the lead. Independent back-to-back requests intentionally can share the first headline.
Historical schema-1 groups can retain nonadjacent support, including support preceding
a lead; their exact member scope, not an enclosing interval, governs extraction.

Request/Reasons topics, source-exact best-effort quote verification, boilerplate
exclusions, all-null handling, useful extraction retention and digest-prose fallback
remain. There is no extra paid repair/review pass. Fixed motion prompts remain inspectable
for extraction and synthesis; organization has no model prompt and is absent from the
prompt picker. See [best-effort handling](summary-best-effort.md) and
[quotation policy](summary-quotation-policy.md).

New packet metadata extends existing row **4**, Markdown **3**, digest/final meta **6**
structures with the `motion packet` role and empty-title internal members. Packet-specific
lead/date/role/continuity invariants apply only to those rows. Historical roles, metadata,
headings and six-topic readers retain their recorded paths. Member metadata and updated
guidance fingerprints prevent incompatible digest reuse. Editions retain physical source
links and lead heading anchors. Existing context-capacity safeguards remain; oversized
packets fail preflight honestly, never silently split or trigger paid repair calls.

## Historical records and deliberate adoption

Schema **1** / `recordprep-motion-organization-1` retains its saved relationships,
nonadjacent/pre-lead support, historical names/dates and coverage statuses. Historical
readers keep the exact **Review coverage** terminology for those records. New maximal-continuity
rules never validate or migrate schema-1 output. Unknown version/contract pairs fail closed.

Installing code changes no private settings, profiles, source pages, classifications,
bundles or outputs. Badges and Resume remain presence-based; historical preparation
absence is not checked-zero. Existing prepared bundles can skip missing organization
on Resume with the existing adoption message. Only a successful explicit organization
publication replaces an older grouping artifact.

To adopt deliberately:

1. Run **Organize motion papers** (no model calls).
2. Rebuild/correct TOC; run **Find boundaries → Filter boundary entries** to retain
   unnamed internal components in saved physical boundaries.
3. Explicitly create motion summaries; refresh summary editions, dependent overview as
   appropriate, and source map.

Do not rerun OCR, classification, naming, hearing/report/minute summaries or participants
solely for this change. A classification defect is a separate task. This implementation
does not authorize regenerating a real bundle or making paid calls.

## Continuous-packet follow-up validation (2026-11-10)

Isolated source/environment: `/tmp/recordprep-grouping-validation/RecordPrep` and
`/tmp/recordprep-grouping-validation/env`, synthetic records, temporary HOME/XDG/Pi,
no paid calls or real-bundle changes. Full unittest discovery: 1,033 tests,
1,025 passed and 8 skipped. Regressions cover four papers/nine exact source pages,
invalid optional role retention, lead title/date ownership, specific sanitized membership
errors, adjacent independent motions, separate opposition/reply and nonadjacent support.
Prompt delivery tests check the continuity default and its exceptions; offline tests
establish application contracts, not live-model semantic accuracy.

Native grouped-motion acceptance passed under `G_DEBUG=fatal-criticals` and
`GSK_RENDERER=cairo`: real Build TOC lead anchor/title, supporting titles absent from
TOC but present in read-only grouping, three fixed inspectors, unchanged settings/bundle
bytes and mtimes during inspection. Computer Use observed the synthetic inspector.
The first default-renderer run detected shader-cache writes in its overly broad
inventory assertion; Cairo avoided that test-environment noise, without product changes.
Skill validation, sequential resources, compileall and offline registered-tool/SDK
expansion audit passed (audit refreshed with local Pi 1.5.2). Initial discovery also
caught the intentionally stale skill audit and missing Git metadata in the disposable
checkout; both were corrected before the passing full run.

For an existing bundle, explicitly rerun **Organize motion papers**, review grouping,
then rebuild TOC and regenerate motion summaries and dependent editions/overview/map.
Installing this change never rewrites old groups, physical boundaries or summaries.
No Focus/shared-schema, launcher, classification or source-text changes are required.

The preceding dated report is historical evidence for the earlier model-driven method,
not acceptance of schema 2. See [deterministic validation](deterministic-motions-validation.md)
for this implementation's actual results and limitations.

## Publication boundary

No dependencies, entry points, application IDs, launchers or XREMAP contracts change.
Both READMEs remain unchanged. Only if separately authorized, publish compatible **Focus
before RecordPrep**, in separate commits. Older readers cannot understand schema-2 groups.
