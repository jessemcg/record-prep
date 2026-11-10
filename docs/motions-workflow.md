# Motion papers and logical entries

See [application-owned motion naming](application-motion-naming.md) for ownership,
adoption and validation details. Report/form naming remains profile-owned.

Dependency **1.19.0**, content schema **14**, retains `profile_api: 1`.
The subsequent [hearing-topic ownership](application-hearing-topics.md) change
also removes hearing topics from profile instructions; report topics stay profile-owned.
Motion naming/eligibility, exclusions, organization and summaries are application-owned
for assigned, historical, custom and unassigned work. Fixed rules preserve physical
source titles and dates, include standardized substantive requests, and exclude
neutral reports. Report Names and Procedural Filing Names remain profile-owned.
New profiles omit both `motion_naming` and `motions`; Profile settings has no Motion
Names editor. All new motion digests use the application's **Request** (`request`)
and **Reasons** (`reasons`) method.
Schemas 1–13 and naming formats 1–5 remain readable. Opening settings never migrates
private profiles or bundles. Only explicit Create/Save/Reset publishes schema 14.
Historical motion naming catalogs, topics and configuration prose stay at rest but supply no current
instructions, prompt inspection text or generation fingerprints. Report topics and the fixed minute method are unchanged by motion ownership.

## Physical recognition stays separate

Basic recognizes motions/applications, oppositions, replies, supplemental briefs,
points and authorities and separately titled supporting declarations. Standardized
requests for substantive relief or status/participation rights within an existing
proceeding are motion papers. Initiating pleadings and non-motion procedural filings
remain outside motions. See [Procedural filings](procedural-filings.md). Standalone notices, service proofs,
court rulings/minute orders, neutral agency/court reports and reproduced exhibits
keep their classifications. Advocacy can qualify regardless of author; agency
authorship alone does not establish advocacy.

Advanced checks **every** motion page, recording `motion_first_page: yes/no`.
Names uses explicit starts and source-title eligibility, preserving actual titles,
amended/supplemental distinctions and filed/document/unknown date basis. A running
heading, date, counsel, page-number restart or adjacency alone proves neither a new
paper nor a relationship. Titles retain the existing 1,024-character structural
limit without truncation; this is not a short-title quota. Unknown eligibility stays
unnamed; an eligible but unreadable title can use its catalog fallback. Names and
Dates remain independently usable. Agent classification correction retains its
existing advisory review and raw-candidate safeguards.

`artifacts/motion_boundaries.json` remains an inventory of **physical**, contiguous
papers. IDs remain `motion:<source-start-page>` (at least four digits), independent
of ordinals. Unnamed starts terminate earlier papers; gaps/orphan bodies are never
silently appended. Individual names, dates, classifications and ranges are not
rewritten to implement grouping.

## Organize motion papers

The native **Organize motion papers** stage runs after final classification and
before Build TOC, using the shared Agent model/reasoning and its own canonical
skill/restricted tool guard. Python supplies the immutable inventory and exact
staged source files. The agent proposes relationships; Python retains the lead title/date;
it cannot invent physical IDs/ranges, execute a shell or write canonical outputs.
**View grouping** is a read-only plain-text review of entries, members and findings.

`artifacts/motion_groups.json` schema 1 records the organization contract, inventory,
source/input fingerprints, model/resource identity, logical groups, findings and
honest review coverage, independently of advisory notes. For a nonempty inventory,
complete requires an explicit complete candidate and every paper accepted exactly once,
without malformed/contradictory membership, duplicate assignments or automatic fallback.
Reviewed ambiguous singletons and omitted/normalized invalid optional metadata
may have complete review coverage; that is not semantic certainty.
Missing or explicitly incomplete candidates remain incomplete. Saved historical statuses
are displayed as saved, never recalculated on viewing. The review separates components,
relationship explanations and notes, with entry/physical-paper counts.

Inventory dates/date bases can originate in image recognition. A text-only organization
run must not equate an OCR omission with an absent stamp or downgrade known filed-date
metadata. Genuine conflicting evidence belongs in an attributed advisory note.

Each group has the lead's existing ID, a separate lead-page
navigation anchor, exact ordered components, role, title, source-supported party,
purpose/date/date basis and optional relationships. Components need not be adjacent
and support can precede the lead. Never use an enclosing range as source scope.

Default to one logical entry for a lead and its continuous supporting declarations,
separate statements and memoranda. Consistent request, party and position suffice
without an express cross-reference in every component. A component title, physical
start or page-number restart does not create a separate TOC entry. Another independent
filing or a non-motion category ends the packet. Independent motions, oppositions and
replies remain **separate entries**, even back-to-back; conflicting requests, parties
or positions override continuity. Non-adjacent support requires express source linkage;
intervening unselected pages never enter the source scope. This is an agent instruction,
not a Python merge of every uninterrupted CT_motion run.

Python uses the lead's inventory source title and known date/date basis, ignoring
proposed replacement names or dates. Only an unknown lead date may be recovered from
the lead itself. Supporting names/ranges remain physical inventory, not separate TOC
entries. Historical saved titles remain as recorded until explicit organization.

Missing/invalid optional filing roles retain valid membership with an unresolved-role
finding; they no longer reject the whole group. Unknown IDs, non-string IDs, duplicate
members and invalid/nonmember leads still reject membership with specific numbered
proposal diagnostics (without echoing raw model values). Duplicate assignments across
proposals still reject all affected groups. Unlinked/ambiguous papers remain singletons;
useful independent proposals survive rejected proposals. No mandatory paid repair pass.

The stage uses its own lock, private candidate, Stop handling, guarded source/model/
resource/selection/prior-output checks and atomic publication. Genuine failures,
unsafe paths, corrupt canonical stores, races or failed publication preserve prior
outputs. A successful child with unusable content yields flagged singleton coverage.
Unchanged current inputs reuse the saved result without a model call; checked zero
selection publishes an empty result without a model call.

## Summarization and navigation

Build TOC uses each current logical title and **lead anchor**, not the lowest member
page. Extraction reads exactly the selected components, integrating declaration
evidence into **Request / Reasons**, not an independent supporting-fact inventory.
The narrative answers **who wants what, and why**, distinguishing allegations,
arguments and requested relief from actual court findings; it does not infer a
later ruling or use external legal research. **Both extraction and synthesis** select
only what the filing party requests or opposes and its reasons. Opposition entries
explain the opposed request, the result sought instead and the grounds for resisting
it; replies explain the position maintained or changed and the answer to the objection.
Substantive scope, conditions, alternatives and consequential qualifications remain.

Digest prose, its quotation bank and final narrative exclude hearing dates/times/
departments, street/mailing addresses, case/court numbers, incident/tracking identifiers,
counsel/contact details and caption/notice/service/signature boilerplate. No general
"needed to distinguish the filing" exception remains. Navigation metadata stays intact
and Python still supplies headings. Supporting papers explain grounds, not a sequence
of component accounts or a factual/procedural inventory. A contested timing, notice,
informal-resolution or sanctions ground is explained as a contention and consequence,
not a chronology of contacts or compliance recitals. A substantive deadline/duration
that is itself relief or a disputed ground is not routine hearing-calendar information.
Quotes anchor relief or reasons for/against it, retaining wording, negation, attribution
and qualifications. Selection starts in extraction because digest prose is also the
fallback final summary. Synthesis must not reintroduce excluded particulars from older
digests, labels or metadata. Fictional motion/opposition/reply examples teach selection,
not source facts or length limits. See [selection validation](motion-selection-validation.md).
Motion, opposition and reply are never collapsed into one narrative.
Quote verification, hashes, overlap checks and
preflight payloads use exact member pages, excluding unrelated intervening pages.

New motion digests use Markdown format **3**, row schema **4**, digest/final metadata
schema **6**, fixed instruction-free application metadata, and exact member/anchor
metadata. Historical Markdown 1/2, row 2/3 and metadata remain readable with the
frozen historical six-topic catalog; old artifacts are never relabeled current.
Final output remains `summaries/motions_sum_<case>.txt`. Best-effort quote matching,
all-null handling, useful extraction retention and digest-prose synthesis fallback
remain authoritative: see [best-effort handling](summary-best-effort.md). There is no
mandatory repair/review pass or editorial quality gate.

Motion digest/final pairs are staged before replacement and ordinary second-file
replacement failures roll back the first, preserving prior bytes/mtime. This is not
a claim of crash-atomic multi-file transactions: canonical hashes detect interrupted
pairs. Existing Stop/source/store/publication safeguards remain separate from content
quality. Summary editions retain the fixed Letter layout and add validated heading
links to lead anchors; quote links still search physical source text.

Source-map `documents` stay physical. Current grouping adds descriptive aliases,
per-page logical context, optional `files.motion_groups`, and `counts.motion_entries`;
`counts.motions` remains the physical paper count. Published grouping omits runtime
input details. Focus reads the contracts/context without adopting preparation
instructions, changing research policy or requiring a profile.

## Historical bundles and explicit adoption

Missing grouping is supported singleton behavior. Readable stale grouping warns and
falls back to the current physical singleton inventory without rewriting the saved
artifact. Corrupt grouping is not silently treated as valid or absent. Badges and
Resume remain presence-based; changed settings alone do not trigger regeneration.
Already-prepared legacy bundles without grouping skip organization on automatic
Resume with an adoption message. Fresh pipelines include the new stage.

To adopt deliberately: run **Organize motion papers**, review grouping, then rebuild
TOC and explicitly create motion summaries. Refresh dependent editions/overview/map
as needed. No upstream source reset, private migration or automatic paid run occurs.
Historical missing motion preparation is not zero motions; explicit execution explains
the prerequisite. Checked-zero motion preparation uses zero organization, extraction
and synthesis model calls.

For the request-and-reasons selection follow-up, explicitly **Create motion summaries**
to adopt the new extraction and synthesis instructions. Existing digest fingerprints
are intentionally not reused as current selection; no saved artifact is cleared,
rewritten or relabeled by installing the change. No profile reset/save or hearing,
report, minute, classification or boundary rerun is needed solely for it. Refresh the
motion edition and dependent overview/source map after new output as appropriate.
The organization method and membership rules are unchanged; its existing conservative
resource identity nevertheless hashes the whole `motion_guidance.py` module, so a
separately requested organization run may re-review rather than reuse its old receipt.
That does not force organization or alter saved groups, presence badges or Resume.

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

## Validation and publication

Use disposable checkouts/environments with isolated HOME/XDG/Pi state, synthetic
sources and offline/scripted providers. Select each callee with the absolute
UvEnvironments helper and explicit `--project` / `--environment`. Run RecordPrep's
full unittest and Focus's full pytest suites, actual SDK skill expansion and guard
checks, resources/skill/audit/package checks, shared-file parity and GTK acceptance.
Scripted results establish mechanics, not live editorial/grouping quality. See
[grouped-motion validation](grouped-motions-validation.md) for actual results.

No dependencies, entry points, launchers, deployed applications, private settings or
real bundles are changed. If publication is separately authorized, publish compatible
**Focus before RecordPrep**, in separate commits.
