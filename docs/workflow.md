# Preparation workflow

[Back to RecordPrep](../README.md) · [Installation](source-install.md) · [Practice profiles](practice-profiles.md)

This is the detailed preparation reference. Historical adoption notes describe explicit reruns, never startup migrations. Installation/settings storage alone does not require regenerating prepared work.

## Practice profiles

RecordPrep includes **General Court Record** and **California Juvenile Dependency**
preparation profiles, shipped in `recordprep/resources/practice_profiles/`. Open
the hamburger menu's profile dropdown and select one directly; the checkmark shows
the current choice. Its name appears beneath the app title. **Profile settings** opens the complete
settings in an independent, movable and maximizable window for editing and **Save**.
Report/form naming each has one instructions editor containing the approved names;
there is no separate naming mode or duplicate list editor. The approved entries also
supply Python's name validation. General starts without a practice-specific list;
add approved names there, or use Dependency's supplied list. Unnamed reports retain
provisional labels and document ranges. Unnamed forms are omitted from the Forms TOC;
their source pages and classification remain intact. Existing TOCs change only when
you explicitly run Build TOC, without needing to repeat classification or naming. A boxed category list on the left opens the selected
settings on the right: Classification and Summaries.
Participant identification is fixed application behavior, not a settings category.
The same general instructions identify hearing participants in every area of law,
using source-described roles and attorney representation instead of a role catalog. There is no General section, duplicate profile picker or default
checkbox. The selected profile is named in the header; **Create profiles** is a link
in the hamburger menu, immediately below **Profile settings**. Case naming uses one built-in, practice-neutral prompt rather
than editable profile instructions. Saved legacy caption prompts remain untouched
but no longer affect inference. Each classification prompt has its own tall editor. Structural labels are fixed
across practice areas; profiles customize recognition clues, not label names.
Task editors display their output contract and warn about unsupported label references
without blocking Save or changing historical profiles. General Court Record 1.5.0
supplies detailed, practice-neutral category definitions, continuation/date clues
and customization suggestions; add your own approved report/form names separately.
Existing personal profiles and case pins are not automatically updated.
A brief **How classification builds the record** explanation stays above every
Classification editor. Common guidance is first, followed by all reporter’s-transcript
(RT) prompts, then clerk’s-transcript (CT) prompts; small stage labels show Basic,
Advanced, Dates and Names. **Report names and dates** accurately describes the
report naming prompt. Hearing labels are dates, not separately extracted names.
Summaries has exactly three pages: **Hearing digest topics**, **Report digest topics**,
and **Minute orders**. Topics are the hearing/report personalization controls. One pinned **Topic-guided agentic
summarization** explainer and linear progression appears throughout the section:
each complete hearing/report → topic digest with quotes → narrative section →
separate hearing/report summary. It explains the two stages and substance-driven detail
without quotas. Minute orders have their own single-stage note. New content-schema-5
profiles have no additional digest/narrative instruction fields, role catalogs,
participant identification instructions or overview instructions. Historical fields remain readable but inert. Application-owned
contracts restore the pre-profile materiality and narrative method with only
specialty-neutral changes and the approved proposal-cutoff removal; see the
[reconciliation and validation limits](summary-contract-reconciliation.md).
Existing outputs remain untouched until explicitly rerun; changed contracts make
profile-bound digests and narratives regeneration-pending. At narrow widths, a categories button opens the sidebar as an overlay.
**Create profiles** creates a profile from a name and starting profile, or deletes
a personal profile with confirmation. Built-ins are protected; deletion removes
an entry from the chooser while preserving all revisions used by existing cases.
Deleting the selected application profile returns it to General; no case is rebound.
Personal edits save privately, never into
installed application files or `config.json`; the public specialties stay tracked
and useful on every fresh installation.

**Create files** never binds instructions to a bundle. New generation uses the
selected application profile, independent of historical case pins. Changing a
selection never runs models or rewrites old artifacts: explicitly rerun affected
upstream stages before later preparation when relevant instructions changed.
Missing historical instructions do not block generation; current selected guidance
must be available. See [application profiles and portable storage](application-profiles.md).

The dim header buttons are **Choose case bundle**, **Choose PDF(s)** and
**Clear current case** (trash, immediately after the plus). Clear forgets the
selection and resets displayed progress; it never deletes PDFs, bundles, case
names or generated files. Stop active work and close the TOC editor first.
With no case selected, Model settings and Profile settings remain available.
Every explicit profile choice is remembered across launches as the application
selection, whether a case is open or not. Clearing invalidates older case-bound
dialogs but preserves that selection.
Synchronized `.recordprep` metadata can retain ordinary `0755`/`0775` directory
and `0644`/`0664` file modes; ownership, link safety and concurrent-selection
checks still apply. The local accepted-profile store remains owner-only.

New runs use current application guidance and consume saved upstream files, without
requiring their historical settings or timestamps to match. Models edit private candidates; Python validates
and publishes the schema-3 source map without a model call. Prepared descriptors
remain readable without the instruction snapshot. Unknown titles/dates do not erase
short reports. Dependency naming includes the reviewed title/code catalogs and
approved “Parental” spelling correction.

Saving selected guidance advances the application selection with no separate
case-use confirmation and no regeneration. Previous Dependency customization is prepared read-only and stored
only on explicit Save or dropdown selection, never copied into public definitions.
Maintainers add public specialties using bundled data and a catalog entry, not a
separate repository or download. Focus instead uses one application-owned neutral
research method for every new question, including profile-bound bundles. It needs
no corresponding research profile and consumes preparation provenance descriptively.
Only profile_contract.py and profile_artifacts.py remain byte-identically vendored;
there is no store/workflow/editor/manager or UI/document parity requirement.
Bundle provenance remains descriptive; application settings govern new preparation.
See the [GUI guide and contract](practice-profiles.md)
and [validation evidence and limitations](practice-profiles-validation.md).

**Compatibility note:** legacy category guidance and first-page parental-attendance
rules remain available to existing unassigned bundles. Participant identification
is general for every case. Bound profiles use accepted topic catalogs and minute
guidance with fixed complete-order attendance rules, never historical role catalogs
or policies. Historical specialty prompt strings remain for exact built-in recognition
and supported readers, not as an active proposal detector or source cutoff. Opening settings/cases is read-only; only an explicit settings
save can persist legacy cleanup. The supported full application remains a source
installation containing its own `.pi/` tree. Wheels include the independent Python
package and bundled profile/category resources, not a replacement native-Pi deployment.

## Safe continuation

Step checkmarks mean **the output files exist**. Pending means the expected output
files are absent. Profile/model changes, source timestamps, metadata versions and
freshness do not change these visual completion badges. Steps that modify the
same files (such as Build/Correct TOC) share that output-presence indication.
Existing clerk-only participant skipping remains separate because that step is
not applicable. **Process text files** requires its own completion receipt,
`artifacts/text_processing.complete`, as well as text files: raw extraction alone
never proves processing ran. The receipt is published atomically only after every
page and the transcript-layout refresh succeed. Stop/failure after processing
starts leaves it pending; filling missing source pages clears an earlier receipt.
It travels with the synchronized bundle, without model/settings freshness checks.
Older bundles without this receipt show processing as pending and Resume runs it;
no receipt is inferred from downstream files or historical pipeline status.
Resume skips existing outputs too. Consumers still validate actual
required files/ranges; explicit generation protects checkpoints and in-flight inputs.

**Run through** applies to **Run**, **Resume**, and a step's **Run from here**.
The endpoint is inclusive: that step finishes, then the sequence stops before the
next step. **End of pipeline** runs through the final step. For **Run from here**,
an endpoint earlier than the starting step is rejected before any work starts;
choose that starting step, a later step, or End of pipeline instead. **Run from
here** remains an explicit rerun, unlike Resume's skip-completed-stage behavior.

During a run, a step bypassed because its artifact completion check is satisfied
shows **Already complete**, not **Skipped**. It counts toward phase completion;
a later artifact refresh may show the usual completion checkmark. **Skipped** is
reserved for actual skip paths, such as inapplicable participant indexing.

**Resume** skips completed stages and continues at the first pending stage. It
never clears the bundle. If the selected PDFs/layout require a reset, or source
pages are missing while prepared work remains, Resume stops with an explanation
before starting work. Historical settings/timestamps do not block Resume. Use a
step's Run or Run from here to regenerate existing output deliberately, under the
current application settings. That run reuses only its own matching checkpoints.

**Create files** also refuses automatic resets, including from Run and Run from
here. For an already-prepared bundle with complete source pages it is a no-op;
for changed inputs/layout, use a separate folder rather than clearing old work.
Re-selecting the same resolved manual layout preserves its bytes and fingerprints.
Changing layout after preparation is blocked before writing anything.

## Direct-source pipeline

### Prepare

1. **Create files** — create `text_pages/NNNN.txt` and 300-DPI grayscale `image_pages/NNNN.png`; merge selected PDFs in natural order when needed.
2. **Detect transcript layout** — PI searches all extracted OCR text for structural RT/CT markers and opens only targeted page images (soft budget of 12 PNGs); it publishes the case-local schema-v1 `artifacts/transcript_layout.json` (RT-only, CT-only, or RT-then-CT with the exact boundary).
3. **Strip characters** — remove nonprinting extraction artifacts.
4. **Infer case (PI)** — infer the caption from the first three text pages using the shared native-Pi model. The skill reads only private staged copies and writes a private candidate; Python validates and publishes `case_name.txt`. Unknown/ambiguous captions, Stop, failed runs or changed inputs preserve the previous name. No separate caption API settings are needed.

### Local OCR with LightOnOCR-3

Local OCR requests now send the supported `grounding` prompt with a 4096-token
completion budget. Grounding identifies layout regions, including footers and
page numbers, but does not guarantee complete transcription. Raw OCR text retains
the region markers; the existing Markdown cleanup removes marker syntax while
preserving the text following it, including transcript numbers.

This is a request-side change, not a server-command switch. Keep the LightOnOCR-3
model/projector and thinking-disabled server command in Local OCR settings.
Restart RecordPrep to load the code change. Existing extracted pages are not
rewritten automatically. To prepare changed extraction, use a separate bundle
folder; Create files never resets prepared downstream work and is a no-op for an
already-prepared bundle with complete source pages.

### Classify and organize

5. Classify RT/CT pages.
6. Add advanced first/last markers, dates, report/form names, and corrections.
7. Build/correct the TOC.
8. Find/correct hearing, report, and minute-order boundaries.

Basic classification retries malformed or unsupported profile-model page types up
to three attempts per page, using the same strict RT/CT taxonomy each time. A
persistent failure identifies the page and a content-free reason, preserves prior
published classifications, and leaves the stage pending. Retry **Classification
basic**; if the failure persists, check the classifier model and profile guidance.
Source, configuration and transport failures do not enter this model-output retry.
The profile taxonomy retains the pre-profile structural labels: reporter certificates
(`RT_certificate`), clerk certificates (`CT_certificate`), motions (`CT_motion`),
notices (`CT_notice`) and proofs of service (`CT_proof_of_service`), alongside the
cover/index/body/report/form/minute-order/other categories. Prompt and validator
share one allowlist; these labels are preserved, not coerced into reports or orders.
The corrected contract changes classification freshness; explicitly rerun Classification
basic when needed, not Create files. Private guidance and old outputs are not migrated.

### Record context

9. **Number transcript pages** — PI writes official citation mappings and citation-series metadata. Python deterministically normalizes each citation label to `PREFIX N` (for example `RT 3`), never model-authored `p.`/`pp.` page notation, before participant indexing, summaries, or the source map read it.

**Transcript Page Breakdown** is the footnote-writing aid produced by **Number
transcript pages** at `artifacts/transcript_page_number_series.md`, alongside the
schema-v2 numbering JSON. Focus's existing breakdown window reads this Markdown:
a three-column **Quick reference** chart (Shorthand, Identifies, Transcript pages),
**Suggested footnotes** with one standalone, plain-text definition per exact citation
prefix, and **Review notes** only for material identification or wording issues.
Rows and definitions follow first appearance in the bundle. Page ranges are citation
pagination, not PDF positions; excerpts and disjoint ranges must remain explicit.

Definitions prefer meaningful, reliable printed volume numbers. A genuine single
"Volume 1 of 1" record is fine; repeated or inconsistent labels across distinct
sources need confirmed hearing dates or another supported distinguishing identifier.
Use the shortest unambiguous description, retaining necessary date lists in the
footnote rather than widening the chart. One citation series spanning several physical
volumes gets one definition. Prefixes are unchanged: `1RT` need not mean printed
volume 1. Filing dates, record types and case numbers are used only when supported;
uncertain scope must not become an unsupported "only contains" or completeness claim.
If identity cannot be resolved, the prefix remains with an honest inability statement,
not a fabricated paste-ready definition. Technical confidence, collisions, file-page
ranges and anomaly analysis stay in JSON, not extra Markdown audit sections. This
is instruction-and-template standardization, not a deterministic guarantee of factual
identification accuracy; verify the suggested wording against the source.

New explicit numbering runs load the updated skill for both profile-bound and
unassigned cases; no profile migration is needed. Existing JSON and Markdown remain
readable and untouched until an explicit run replaces them. Opening RecordPrep or
Focus never refreshes old breakdowns or rewrites private settings. To adopt the new
format, explicitly rerun **Number transcript pages**, then reopen the breakdown in
Focus. **Rerunning numbering is not a formatting-only refresh:** it can change the
numbering JSON and make downstream artifacts regeneration-pending under existing
freshness rules. Follow those prerequisites before explicitly rerunning affected
steps. Do not run Create files, reset a prepared bundle, or silently regenerate
existing cases just to adopt this presentation.

10. **Build participant and witness index** — a deterministic helper first writes a temporary, nonauthoritative worklist containing hearing ranges, first/appearance pages, reporter-series-scoped `RT_index` pages, and oath/examination/attendance marker pages with resolved citations. PI then processes one hearing at a time, reads only original single-page sources, persists reviewed hearings incrementally, validates batches of at most five, and writes schema-v4 `artifacts/participant_index.json` (historical v2/v3 remain readable). Full validation rejects the untouched template. When the resolved transcript layout is a **clerk's transcript only** (CT-only), the step is skipped outright — shown as `Skipped — Clerk’s transcript only` — with no PI process, no placeholder file, and no claim that indexing was performed: participant and witness attribution requires reporter's-transcript evidence, and its absence is never a finding that nobody appeared or testified. Any pre-existing participant artifact is left on disk untouched and ignored downstream. RT-only and RT + CT records always require the validated index.

Transcript layout detection runs once per new or changed bundle, never on
every launch and never as an image-classifier sweep. A high-confidence agent
result continues automatically; ambiguous or contradictory evidence publishes
a structurally valid `needs_review` artifact and pauses before any
layout-dependent mutation, with the transcript-layout controls available as a
manual override. Layouts are case-local and bound to the current page count
and input signature; a value from another case is never used. All routing
reads the validated artifact. After RecordPrep's own guarded text-only
normalization, it may atomically rebind the unchanged resolved decision to the
new text signature. Added, removed, or renamed numbered pages, changed paired
images, unguarded text changes, or a concurrently replaced artifact still
require transcript-layout detection to run again. The manifest
`rt_ct_split_mode`/`rt_ct_split_page` fields are legacy compatibility mirrors only, and the retired cross-case
`rt_ct_split_page` config value is removed during migration. Old bundles with
only legacy split fields are detection-pending; a detected result that differs
from the legacy fields after dependent work exists pauses for review. A changed
layout requires deliberate preparation in a separate folder (RT-specific text
cleanup is destructive); Create files will not erase the existing bundle.

Counsel, non-counsel participants, and witnesses are separate hearing-scoped records.
Identification is practice-neutral for both profile-bound and unassigned cases.
Record people established as present, remote or speaking and express nonappearances;
do not infer participation from a mere mention, client attendance from counsel, or
absence from an omitted name. Role labels and whom counsel represents come from
the transcript, never predefined specialty categories. Historical profile role and
participant instructions are ignored. The index still supports hearing attribution,
case overview and Focus's participant/witness navigation. Law firms and agency abbreviations are stored as organizations rather than attorney aliases. Witness status is explicit: `verified`, `none`, `unknown`, or `conflict`; Q/A formatting alone never establishes testimony. The participant stage never concatenates a complete transcript or multi-hundred-page range. When its bounded evidence budget cannot resolve a hearing, it preserves hearing-specific uncertainty instead of stalling.

For profile-bound participant indexing, Python conservatively normalizes new private
candidates before validation: missing optional statuses become unknown, navigation
IDs are repaired, and unsupported entries are omitted with explicit warnings rather
than invented. Supported names, roles and evidence are retained. Quality warnings
are not a reason to repeat the review. Unreviewed hearings, unsafe paths and invalid
page ranges still block publication. The model receives the validator's actual
stdout/stderr diagnostics, has only one repair opportunity (two failed validations
end the stage), and finishes immediately when full validation succeeds—even if it
requested a partial check. Partial checks must advance the count of reviewed hearings;
a repeated check without progress stops the stage and preserves prior publication.
The staged instruction file is explicitly readable, including the exact evidence-array
schema; its directory, helper scripts and arbitrary schema files remain inaccessible.
Existing indices and private settings are never rewritten by opening the app.
Participant and overview freshness now track separate stage runtime dependencies:
overview-only runner instructions do not stale a completed participant index.
Relevant stage logic, shared safety logic, source inputs, profile components and
model/reasoning changes still invalidate affected work. A narrowly reviewed compatibility
record recognizes participant output from the preceding supported runtime without
rewriting it; unknown historical runtimes are not automatically accepted.

During PI stages, RecordPrep displays the immutable bundle root used by the runner. It warns when the parent folder appears to name a different appellate case than the manifest/PDF, but never moves or renames private case data. The runner also monitors session-file progress and PI CPU state. Sustained CPU activity without session progress produces an actionable Activity/VTE warning; work continues until the user explicitly presses **Stop**. Stop terminates PI's complete process group, returns the active row to Pending, and prevents later stages from starting.

### Summarize

Hearing/report synthesis has a built-in, profile-independent rule for displaying
all-caps quotations with normal capitalization. The model proposes case-only spellings
while keeping canonical quote-ID placeholders; Python accepts only character-for-character
letter-case changes. Proper names, acronyms and identifiers must retain their appropriate
capitalization; uncertain tokens retain source casing. Missing/invalid proposals fall back
to the original quote without losing prose or causing repair loops. Mixed-case source
quotations are untouched. Source pages, digest evidence, verification offsets and quote IDs
remain original. Newly rendered hearing and report summaries do not add a
capitalization announcement; the normalization/search safeguards are unchanged. This
validates case-only fidelity, not the model's semantic judgment about proper-name spelling. PDF editions retain the displayed phrase for
case-insensitive source search. No profile edits are needed.

Existing summaries remain untouched until an explicit rerun. This synthesis/renderer change
reuses current hearing/report extraction digests; it does not require participant indexing
or source re-extraction. Rerun the desired summary stage, then rebuild its editions and the
downstream overview/source map as needed. Hearing sections lead with substantive purpose
or consequential result, then explain material arguments and reasons without repeated
synopses or routine inventories. Report sections likewise open with the main attributed
conclusion, recommendation or significant development and necessary qualification,
then supporting evidence; consolidate overlapping topics and naturally integrate exact
quotes without losing counterevidence. The canonical report SKILL is used unchanged in
profile and unassigned runs. See [hearing editorial method](hearing-editorial.md) and
[report editorial method](report-editorial.md).
Minute orders use their separate [shared selection method](minute-selection.md); this
hearing editorial change does not invalidate current minute work.

10. **Create hearing summaries** — a resumable two-stage PI pipeline: one fresh PI process per hearing reads the complete source pages and writes one concise salience-based digest per category (plus a small verbatim-quote bank) into the readable Markdown store `summaries/hearings_digests_<case>.md`, then one fresh PI process synthesizes the digests into a plain-prose `summaries/hearings_sum_<case>.txt`. Requires the participant index — except for a fresh CT-only layout with valid empty hearing boundaries, which publishes the zero-item header-only outputs without a paid call (a CT-only record with nonempty hearing boundaries is an actionable inconsistency).
11. **Create report summaries** — the same two-stage PI pipeline for reports (legacy unassigned work uses the expanded 12-category schema; bound work uses accepted topics, complete-source extraction, and synthesis that suppresses carried-forward duplication).
12. **Create minute-order summaries** — one fresh Pi process per complete minute order reads source pages directly using the shared **PI model** and **PI reasoning effort** settings. Completed orders are checkpointed for resume; no separate API credentials or digest stage.
13. **Build paginated summary editions** — deterministically render each summary into a fixed US-Letter PDF plus a Focus page-map sidecar under `summaries/editions/`, with page numbering restarting at 1 per category.

Hearing and report summarization runs a **two-stage PI pipeline** (`recordprep/summary_agents.py` plus `.pi/extensions/recordprep-summary-tools.ts`) built around concise category digests rather than atomized fact inventories. Stage one launches one genuinely fresh `--mode json --no-session` PI process per document: its only tools are `recordprep_get_source` (which serves that document's complete source pages in one payload — never an arbitrary path) and `recordprep_submit_extraction`, and the runtime prompt carries the complete digest contract — every category's detailed guidance, the salience priorities, and the relevance/quote content contract. Python deterministically normalizes the candidate (agent-output problems never fail the run): the runner-owned item id is injected, configured categories are reordered into canonical order, unknown ones ignored, missing or malformed ones filled with `digest: null`, and sanitized warning codes (category ids and counts only) recorded alongside the row. Quote verification stays best-effort — unmatched quotes are kept with `verified: false` — across the complete document; there is no proposal cutoff or cutoff-based category rejection. Python is the sole canonical `summaries/<kind>_digests_<case>.md` publisher under an exclusive per-kind lock, together with a hash-bound metadata sidecar.

The canonical digest store is a **self-contained, versioned Markdown document** (profile-bound format 2/row schema 3; legacy unassigned format 1/row schema 2): one level-two heading per document with its item id and source-page range, one level-three heading per category with its id, digest prose, an explicit `No material content.` null marker, a `#### Direct quotes` subsection whose entries carry quote id, file page, and verified status, and a `No direct quotes.` marker for empty evidence banks. Technical metadata (fingerprints, ordinals, quality flags, source offsets and page hashes, schema identifiers) lives in reserved `recordprep:digest-*` HTML comments that never duplicate digest or quote text; content is reversibly escaped so source text cannot forge headings, comments, links, or delimiters, and parsing accepts only the exact generated grammar (validated by canonical re-serialization) with sanitized line-numbered errors. Markdown for inspection, not manual editing: rerun the summary stage to regenerate it.

Interrupted runs resume at the first missing or stale row. Generation fingerprints cover every payload dependency — changed boundaries, prompts, source text, effective models or reasoning levels (including inherited project PI settings), labels, the private hearing participant context, transcript citation labels, effective topic/category-description resources, or the content-contract version mark only the affected rows stale — and duplicate stable item ids or overlapping document ranges are rejected before any paid work. Digest and final metadata use schema version 5 for profile-bound work and version 4 for legacy unassigned work, with dependency fingerprints; older schema-3 metadata stays readable but reports as regeneration-pending instead of silently counting as current. Explicit summary generation uses artifact integrity and current-generation fingerprints to reuse its own checkpoints. Badges and Resume use output presence; downstream overview/source-map work consumes saved summary text without historical freshness or metadata gates. Existing v2 `*_digests_*.jsonl` bundles migrate automatically and losslessly — with zero model calls — the next time their summary stage runs: the Markdown file is authoritative, stale rows alone are re-extracted, and the retired JSONL is removed only after the Markdown, metadata, and final summary have all published and validated. A legacy pair whose data and metadata disagree is preserved and reported for deliberate recovery. Legacy v1 `*_facts_*.jsonl` artifacts remain ignored, never converted, and are removed only after the digest pipeline publishes successfully. Stage two launches one fresh PI process per completed digest document whose dataset tool serves the overview, one document's Python-rendered Markdown block by ordinal (category ids, quote ids, pages, and verification status included; fingerprint comments omitted), or an already-submitted draft section after a context compaction (`view: "submitted_section"`); the model works incrementally — no read-everything-first requirement — with a private synthesis scratchpad (`recordprep_synthesis_scratchpad` read/replace) stored in extension-owned process-local memory that survives compaction, is never evidence, never published, and disappears when the process ends (synthesis restart resumability stays deferred); the runner reloads and validates the published Markdown before synthesis, and the finish tool emits the sections recorded so far plus sanitized coverage counts (validated by Python, republished as advisory warnings only), while Python reorders known sections, fills missing or empty ones with a deterministic digest-prose fallback, resolves known `{{quote:<id>}}` placeholders, replaces any submitted section that still references unknown quote ids with the same digest-prose fallback (a sanitized warning — the submission tool's nonfatal feedback identifies invalid ids and the allowed ones so the model can fix the section before finalizing), and flattens any generated page-link markup. Quality problems — typed quotation marks, unverified or duplicate quote use, out-of-range quote length, ellipsis or terminal punctuation inside a quotation, technical metadata in narrative, and repeated report passages — become sanitized warnings, never failures; deduplicated quality codes are stored in the optional final-metadata `quality_flags` field and shown in Activity. There are no word targets: summary length follows substantive complexity, and conciseness comes from selecting significant information and avoiding repetition. A deterministic renderer then replaces placeholders with ordinary curly-quoted text, renders plain `Date — Hearing` headings, and publishes the final text and final metadata in individually atomic writes (not a two-file transaction — hash validation detects an interrupted pair). An unchanged final text preserves the existing summary edition; only an actual text change invalidates it. Final summaries contain no generated `](page:NNNN)` links: Focus clicks quoted phrases into record-wide phrase searches instead, and legacy linked summaries keep working. The model never writes canonical files, and an integrity failure never replaces the prior summary. A zero-item boundary set publishes a valid header-only digest Markdown document and a title-only summary without a paid call. Model identity is resolved once per stage and matched provider-qualified on the full model id (never a basename), reusing one PI discovery result for every phase. Capacity accounting composes the components the model actually sees — system prompt, skill guidance, tool schemas (proxied by the staged extension source), the runtime prompt, the source payload or digest blocks — into a clearly labeled UTF-8-aware estimate range, never a tokenization guarantee. A known oversized individual source request fails before its paid call with the item id and actionable capacity information; the aggregate synthesis-history estimate warns and proceeds above the 80% safety margin (agent-managed incremental work, never forced batching), and unknown metadata is visibly reported as unknown while PI enforces its own limit. PI extraction is not windowed, so a model with a large context window (for example one million input tokens) handles every document in a single request. `python -m recordprep.summary_preflight --case-bundle PATH --kind both` reports counts, freshness, effective model identity/capacity, largest document payload, digest sizes, and the estimated synthesis history read-only — no paid calls, no publishing lock, no writes; missing or stale digests label the synthesis estimate extrapolated rather than measured.

**Minute orders** use the same shared PI model/provider/reasoning as every other PI operation. For profile-bound work, Python publishes **Date — Hearing type** followed by **Appearances / Orders / Next** labeled lines, without dashes/bullets. Focus makes the plain-text labels bold. Orders gives the actual result in simple, plain English, preserving essential legal distinctions and conditions. Routine report receipt/preparation, filing/portal deadlines, clerical/calendar mechanics and conditional late-filing sanctions warnings are excluded; administrative-only orders say **No substantive orders recorded.** Actually imposed consequential sanctions and substantive relief deadlines remain eligible. The model normally selects one or two headline outcomes with essential qualifications, not an inventory of all material detail. No separate positions narrative is requested; an objection belongs with its ruling only when essential. Next gives only the next substantive hearing type/date, excluding report-only hearings and future report filing/due dates even if earlier; do not move that report calendar into Orders. See [plain-English minute entries](minute-plain.md) (contract8; earlier compact method in [minute-compact.md](minute-compact.md)). California Juvenile Dependency focuses attendance on each parent. There is no attendance-policy selector or reporting-status sentence. Attendance evidence can come from any page of the complete order; counsel alone proves neither presence nor absence. Missing or conflicting attendance stays unclear, and the next hearing is not invented if unstated or illegible. Python verifies evidence locations (not semantic truth), renders the structured fields, and publishes checkpoint/final metadata version 4. Historical checkpoints 1–3 remain readable.
Minute orders have no participant-index or role-catalog dependency: any role description
comes from that order alone. Exact former bundled minute prompts resolve to the new default without changing stored bytes; custom minute prose is retained beneath fixed rules. Each child can only read its current order and submit a candidate. Unassigned compatibility work retains the earlier legacy prompt.

Completed orders persist in `summaries/minutes_sum_<case>.rows.json`; a matching `.meta.json` binds the final to its inputs. Resume reuses current orders and regenerates only those affected by source/boundary/citation, guidance, model/reasoning, or minute-resource changes. Stop and model/candidate failures preserve the prior final; missing/unusable candidates do not become fabricated summaries. Final text and metadata replacements are individually atomic; hash validation detects an interrupted pair and resume republishes it. Zero orders publish a title-only result without Pi. The old direct-API summary remains readable and reusable downstream. Only changed minute text invalidates its PDF edition; downstream overview/source-map work does not require current minute metadata. Hearing/report generation and its caches are unaffected by this migration.

After this general-participant update, reopen RecordPrep. For records with reporter's
transcripts, explicitly rerun **Build participant and witness index** and affected
downstream steps; profile-bound old indices are pending under the new contract.
Minute summaries likewise require an explicit rerun under their catalog-free contract.
CT-only records still skip indexing. No existing output is rewritten on opening.
There is no need to change a minute-order API model. End-user prompt testing and its sandbox controls have been removed.

**Paginated summary editions** are built directly after the three summary stages (the retired Add-links step no longer mutates summary text). Each edition pairs `summaries/editions/<summary-stem>.pdf` with a schema-v2 `<summary-stem>.pages.json` sidecar. The PDF uses the fixed `recordprep-summary-letter-v3` layout — Letter portrait, 54-point margins, 11-point body with 1.18 line height and a 0.5em paragraph gap, `Page N of M` 9-point Times footer, numbering restarting at 1 — so it is the immutable pagination authority on every computer and printer. The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is fully deterministic: it never depends on locally installed fonts, Fontconfig, or any external font file. Recognized quoted phrases render in bold through the built-in Nimbus Roman bold face and lose only their outer style-matched straight/curly double quote delimiters — a presentation-only transformation of the printable representation, recorded as a quote-presentation policy in the layout metadata. Recognition is conservative (style-matched pairs within one source line, content that survives rendering-equivalent normalization, never partially overlapping a link span), so unmatched delimiters, whitespace-only pairs, and nested quotations stay literal, and the canonical `.txt` summaries keep every quotation mark byte-for-byte. The denser v2 typography produced about 40% fewer pages than the previous 72-point/12-point layout on the reference bundle while passing full source-coverage validation. The sidecar layout metadata records the complete typography contract (page size, margins, font family, body size, line height, paragraph spacing, footer template/family/size/baseline) plus the quote-presentation policy, and validation rejects any sidecar whose schema, layout ID, fixed metrics, or policy differ and any whose required quote spans are missing, malformed, overlapping, or not a complete mapping of every recognized quotation — pre-v3 editions therefore show the build step as pending until they are rebuilt, and rebuilding is required once per case because pagination changes. The sidecar records per-page selectable body text (footers excluded), trusted record-page link spans with numeric targets, required quote-fragment spans (exact offsets with exact labels plus the complete quote content, so fragments of a quotation that wraps across a paper-page boundary stay record-wide searchable; derived from the same monotonic alignment as coverage, never by global substring search), inclusive source-line ranges, and source/PDF SHA-256 hashes; RecordPrep verifies the pages reproduce the printable source text exactly before publishing. The `.txt` summaries remain the canonical inputs for case-overview and source-map workflows. Rerunning a summary category removes only that category's generated edition files; hash validation keeps stale editions out of Focus. The generated editions stay nonauthoritative: they never become Agent evidence or source-map search paths.

Extraction serves each document's **complete source pages in one payload** — there are no PI extraction window settings. Minute orders likewise send each complete order without windowing. PI extraction is not windowed: the hearing payload privately includes validated participant-index context under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` — counsel with roles and appearance, non-counsel participants with attendance/speaking/sworn status, and the witness/testimony picture (verified witnesses with mapped, cited examinations, or an explicit `Testimony: None.`) — attribution context only; every fact still needs evidence from the original hearing pages.

Report extraction serves the complete document, including proposed-findings/order
sections and later discussion. There is no heading detector, injected delimiter or
cutoff-based quote rejection. Current guidance distinguishes requested relief and
recommendations from actual orders, omitting routine boilerplate unless consequential.
Historical proposal-exclusion text is retained solely for exact built-in recognition,
so obsolete defaults are not reattached as custom guidance; genuinely custom prose
stays byte-preserved.

Canonical Markdown categories carry a salience-based `digest` and a small evidence
quote bank, not atomized fact inventories. Categories with no material content use
`digest: null`. Python normalizes Unicode/whitespace (then case and typographic marks)
and records original offsets plus the page hash when a quote is found on its declared
page; unmatched quotes stay submitted with `verified: false` and sanitized warnings.
Quote ids are canonical (for example `hearing:0421/court_orders_and_reasons/1/1`);
synthesis uses placeholders and Python resolves their text. Historical v2 digest
JSONL remains supported through the guarded conversion described above, not as the
current synthesis store.

One effective-guidance contract governs every summary phase: the immutable built-in relevance, scope, schema, quote, and safety contract is always the main guidance; recognized historical built-ins — reconstructed by exact historical text from tracked history, including the retired digest built-ins with their six-quote guidance — advance to it without reattaching retired text, and genuinely custom text is preserved byte-for-byte in `config.json` and composed as explicitly subordinate additional guidance that cannot override the immutable contract. Per-category guidance prose lives in the tracked, editable files under `recordprep/resources/summary_categories/` (`hearings.md`, `reports.md`); category ids, display titles, ordering, and null semantics stay code-owned, and the loader rejects missing, duplicated, unknown, reordered, or empty sections before any paid work. Profile settings exposes hearing/report topics and minute-order guidance; identification is application-owned. Personal Save never changes tracked category or bundled files. Historical unassigned output retains its compatibility readers; new work uses validated application settings and component-local freshness.

**Summary length** follows each document's substantive complexity; conciseness comes from selecting significant information and avoiding repetition, never from a numerical target. The retired word-target Settings controls have been removed, and any stored target values remain in `config.json` but are ignored.

For CT-only records the hearing summary stage runs its existing zero-item flow: with a valid empty hearing-boundary array it publishes the header-only hearing digest and title-only summary without a paid call and without loading participants. A CT-only record with nonempty hearing boundaries is an actionable layout/boundary inconsistency rather than something to summarize unattributed. A transcript-layout change is watched in hearing-summary freshness, so a later layout decision never reuses a stale CT-only exemption.

### Agent Search

15. **Create case overview** — PI writes the concise schema-v1 `artifacts/case_overview.md` orientation aid from the source summaries and, when participant indexing applies to the resolved layout, participant metadata. For CT-only records the overview is built from the report and minute-order summaries and the valid empty hearing summary, and its Record Scope explicitly identifies the absence of reporter-transcript attribution; attendance, sworn testimony, or the absence of participants is never inferred from the missing indexing.
16. **Build source map** — publish `artifacts/source_map.json` schema v2 and update `manifest.json`.

The case overview is fixed, practice-neutral application behavior, not a profile
setting. Read every summary completely (continue after truncation), but publish a
compact starting map in short Markdown bullets, not a narrative summary of summaries.
Include only what helps Focus identify the case, understand the latest recorded posture,
or decide what to inspect next. State each fact in its best section once: central
parties, latest operative result, major chronological turning points, neutral issue
labels/research leads, and material record scope/gaps. Supporting detail stays in the
summaries and source record; omit routine appearance rosters, contact attempts and
incidental dates unless central to orientation. Small/simple records warrant small
overviews, without heading filler, word targets or mechanical page-count scaling.
Short fictional before/after examples demonstrate the intended detail level for each
section: name/role, operative result, dated landmark, research lead and consolidated
coverage limitation. They are not case facts or output quotas. Avoid paragraph-length
bullets, evidence inventories and routine negative checklists. Attribute each issue's
status separately, never label a mixture of allegations and sustained matters as
collectively unadjudicated. Preserve qualifications needed to avoid misleading compression. Participant metadata
is only for identity, roles and representation, never substantive facts.
Distinguish allegations, positions, evidence and actual rulings; do not assume an
appeal, infer nonoccurrence from silence, use outside knowledge or predict outcomes.
Keep it concise without word caps or event quotas. The five-section format/disclaimer
is unchanged for Focus. Profile-bound work retains private candidate validation and
Python-only publication. Old profile overview prose is readable but inert; existing
overviews remain untouched until explicit regeneration. To adopt the compact method,
rerun **Create case overview**, then **Build source map**, with current upstream inputs;
this instruction change does not require regenerating participants or summaries.
The pipeline step remains.
Profile-bound overview generation receives an explicit manifest of exact allowed input
paths, including all three canonical summaries. It does not discover filenames by
listing directories or guessing paths. The access guard remains restrictive; a failure
to read a listed required input must stop the stage rather than trigger substitute-file
searches. Profile-bound Build source map is a deterministic Python publication step,
not an AI stage, so it does not use that model access guard. It validates actual
inputs and preserves prior publication if they change during work; it does not
require old preparation to match current settings. See [application profiles](application-profiles.md).

The case overview supplies parties, procedural posture, key events, principal issues, and record scope so a Focus Agent can orient before inspecting structural metadata. It is explicitly nonauthoritative and cannot support a final factual claim or citation. An explicit rerun uses the saved inputs; historical settings and timestamp differences are not downstream prerequisites.

Source-map v2 builds document ranges directly from boundaries and `text_pages`. It includes the canonical case-overview path, the resolved transcript-layout path, official citation lookups, hearing/date ranges, counsel names/roles/aliases, witnesses/examinations, per-page context, and attribution warnings. For CT-only records the participant prerequisite does not apply: the map carries an empty participant structure with a zero indexed-participant count, an explicit unavailable-attribution scope warning, and no `paths.participant_index` or `files.participant_index` reference (a dangling path is rejected), while RT-only and mixed records keep publishing the validated participant data and canonical path. Summary and overview paths are nonauthoritative leads; source pages remain the evidence.

## Case bundle layout

```text
case_bundle/
  manifest.json
  case_name.txt
  text_pages/
  image_pages/
  classification/
  artifacts/
    toc.txt
    transcript_layout.json
    hearing_boundaries.json
    report_boundaries.json
    minutes_boundaries.json
    transcript_page_numbers.json
    transcript_page_number_series.md
    participant_index.json
    case_overview.md
    source_map.json
  summaries/
    hearings_sum_<case>.txt
    reports_sum_<case>.txt
    minutes_sum_<case>.txt
    editions/
      hearings_sum_<case>.pdf
      hearings_sum_<case>.pages.json
      reports_sum_<case>.pdf
      reports_sum_<case>.pages.json
      minutes_sum_<case>.pdf
      minutes_sum_<case>.pages.json
  temp/
```

When a selected bundle is rerun, RecordPrep removes only known obsolete generated paths from retired pipelines, including legacy `_organized` summaries. It does not scan or mutate unrelated case bundles.

## PI stages

Tracked PI resources live under `.pi/`:

- `SYSTEM.md`
- `settings.json`
- `extensions/recordprep-auto-exit.ts`
- `extensions/recordprep-case-name-tools.ts`
- `extensions/recordprep-profile-native-tools.ts`
- `extensions/recordprep-profile-minute-tools.ts`
- `extensions/recordprep-summary-tools.ts`
- `extensions/recordprep-summary-synthesis-tools.ts`
- `extensions/recordprep-minute-tools.ts`
- `skills/recordprep-detect-transcript-layout/`
- `skills/recordprep-infer-case/`
- `skills/recordprep-number-transcript-pages/`
- `skills/recordprep-build-participant-index/`
- `skills/recordprep-extract-hearing/`
- `skills/recordprep-extract-report/`
- `skills/recordprep-synthesize-hearings/`
- `skills/recordprep-synthesize-reports/`
- `skills/recordprep-summarize-minutes/`
- `skills/recordprep-create-case-overview/`
- `skills/recordprep-build-source-map/`
- `scripts/run_recordprep_skill.py`

The native VTE rows launch one explicitly loaded Agent Skill each in PI's native VTE UI. The two summary stages run headless JSON-mode children instead: one fresh `--no-session` PI process per document for extraction and one per completed Markdown digest document for synthesis, staged with the phase skill and summary tools (synthesis explicitly loads the synthesis-only wrapper), with an exact custom-tool allowlist and no general tools. The runner captures JSON events but prints only phase, ordinal, event class, PID, elapsed/stall information, and sanitized error codes — never prompts, source text, tool arguments, or model prose. Stall monitoring tracks event activity rather than session growth; stalls warn but are never auto-killed. Stop terminates the active child's process group, escalates after the grace period, releases locks, and leaves the row Pending without starting the next item or synthesis. Each child gets a unique private cache workspace and candidate path removed in `finally`. The runner accepts a structurally valid `needs_review` layout artifact, while RecordPrep treats only a resolved, fresh artifact as step completion. Only the final source-map stage updates the manifest (including the `transcript_layout` path). Skills validate outputs before the pipeline advances.

## Model settings

The general settings menu and window are labeled **Model settings**, distinct from
**Profile settings**. Clicking a left-hand category immediately shows its settings;
there are no nested subcategories or navigation dropdowns. Model settings opens on **OCR**, a single page with the embedded-text/local-OCR source selector at the top and local OCR server, model, worker, slot and advanced start-command settings below. These replace the former Prepare → Create files / Local OCR pages; existing saved values are unchanged. Its three direct destinations are **OCR / Classify / Agent**. Agent contains **Shared PI settings**: one **PI model** picker, one **PI reasoning effort** picker, the PI command and model refresh. The selection applies to every PI preparation operation, including case-name inference, hearing/report digest extraction and synthesis, and minute-order summaries. Classification API credentials/workers and local OCR remain separate. Practice instructions belong on the single Profile settings page, including task-specific classification. Case naming uses application-owned instructions. Legacy `summary_extract_*pi_*` and `summary_synthesize_*pi_*` model/provider/reasoning values, including hearing/report-specific variants, are inert immediately: ordinary saves preserve existing values unchanged and never create them. The removed sandbox API/window keys and legacy prompt values are not edited or rewritten by the ordinary Settings UI; historical guidance recognition remains available to compatibility loaders. Personal profile Save leaves `config.json` and bundled files unchanged. Numeric entries are validated before saving. The shared PI model and reasoning effort are stored in the effective Pi preferences file (external `pi/settings.json` for public launches; checkout `.pi/settings.json` for legacy launches); choosing global-default reasoning removes the project reasoning override. There are no per-stage overrides or separate summary model page. PI retains global-default reasoning inheritance and adjusts unsupported reasoning levels. Saving changes no prepared output or completion badge; Resume skips existing outputs. Explicit generation still checks its own effective model/source/guidance checkpoints. Retired artifact-pipeline credentials and prompts — including the old cross-case `rt_ct_split_page` key and the per-stage `pi_stage_<step>_pi_*` overrides — are ignored on read and removed only by an explicit Settings save. The transcript expander offers automatic detection plus case-local manual overrides; a stale global value never populates a new case. Retired paragraph-count and sandbox window settings are not reinterpreted by the production pipeline or ordinary Settings UI.

**Infer case migration:** restart RecordPrep to load the new skill and remove the old
Infer Case Name settings page. Retired `case_name_api_*`, `case_name_model_id`,
`case_name_disable_reasoning` and prompt values are inert and left untouched.
Existing case names are not changed on opening. They may show inference pending
until an explicit run creates the new source/model/contract-bound freshness marker.
No model has unrestricted file access for caption inference; classification is the
only remaining direct cloud-model request path (local OCR is separate).

Saved run-until targets migrate as follows:

- retired raw/transform stages and the retired aggregate `create_summaries` target → `create_minute_order_summaries`
- retired overview stage → `create_case_overview`
- retired vector stage → `build_source_map`
