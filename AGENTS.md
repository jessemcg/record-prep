# RecordPrep Agent Notes

## Machine-local runtime

Read ../UvEnvironments/README.md. Provision `../UvEnvironments/project-env sync RecordPrep`
(managed Python 3.13, Home/Work only; excluded on Laptop). Execute via
`../UvEnvironments/project-env run RecordPrep COMMAND`. Before uv examples below,
source `../UvEnvironments/terminal.sh RecordPrep` in a dedicated project subshell and
stop on failure; it verifies runtime and disables automatic sync/downloads. Never
inherit another project's UV_PROJECT_ENVIRONMENT/VIRTUAL_ENV. Same-project Python
children use sys.executable. All test checkouts/environments must be disposable;
private config/case bundles remain untouched.

## Practice profiles

See `docs/practice-profiles.md` and `docs/practice-profiles-validation.md` for the
shipped-specialty/personal-settings workflow, v1 API and supported content schemas,
runtime boundaries and validation limits.
The six `profile_{contract,store,artifacts,workflows,editor_ui,manager_ui}.py`
modules, shared conformance/workflow tests and docs are intentionally vendored
identically in Focus and RecordPrep. Coordinate changes; never import a sibling
app or its instructions at runtime. Bundled resources are app-owned and read-only.

Create files binds General/configured guidance only for a previously nonexistent
bundle; an explicit pending choice takes priority. Existing bundles remain legacy
or retain their accepted pin. Selection never regenerates output. Classification,
naming, boundaries, native stages, summaries and minutes share accepted snapshots,
component/source/model/upstream freshness and serialized publication. Native tools
read bounded inputs and edit private candidates only; Python owns publication and
the deterministic v3 source map. Profiles cannot add tools or weaken validators.

Keep frozen dependency fixtures and legacy readers intact. Schema-3 participants
and maps, digest format 2/row 3/metadata 5 and minute checkpoint 3 (1/2 readable) carry descriptive
provenance/catalogs, never instruction authority. Unknown names/dates must not
erase short documents. Custom category IDs may include hyphens and digits; quote
serialization must preserve their canonical IDs. Missing instructions block new
work, not browsing. Keep private configuration/cases untouched. Dependency
initialization is an allowlisted read-only candidate shared by chooser/editor,
persisted only on Save
or Use profile, never a migration script or public-resource update. Public profiles
are complete tracked specialties; personal saves use the managed private store.
RecordPrep content schemas 2/3 store task-specific classification and historical case-name
guidance. Caption inference now always uses case_name_prompt.py's fixed, neutral
prompt; profile/legacy caption text stays byte-preserved but inert. Production
caption inference/freshness lives in case_name_stage.py and uses the native Pi
runner/shared model, not a direct API. All old names stay readable but require an
explicit inference run for the schema-2 source/model/contract/output marker. Profile settings has no General page,
profile picker or default switch; Save preserves existing default semantics and
Create profiles (no ellipsis) is a hamburger-menu link below Profile settings, not a sidebar button.
Its Cancel/Create buttons use a plain action box, never FlowBoxChild hover wrappers.
Delete hides only non-built-in identities using a guarded head/default-CAS tombstone;
accepted revisions and existing case pins remain usable. A deleted default is cleared,
matching no-case pending choices are reset, and old drafts cannot resurrect it.
Classification has a pinned, display-only explainer above its editors and RT-first,
CT-second navigation with stage subtitles. Common guidance combines only with the
current page-type/first-page/date task; naming uses separate approved-name instructions.
Hearing labels are dates; report Names extracts name/date at continuous report-run starts.
Classification resource keys, prompt bytes and pipeline order remain unchanged.
Summaries has exactly Hearing digest topics, Report digest topics and Minute orders.
Content schema 3 removes the four extra summary instruction resources; old schemas
remain readable but those fields never enter prompts or component fingerprints.
Do not import legacy extra-summary settings or move their prose into the core.
The specialty-neutral fixed method preserves the pre-profile baseline documented
in docs/summary-contract-reconciliation.md; topic catalogs supply personal focus.
Header Clear current case is selection-only: preserve all case/PDF artifacts and
unrelated configuration, invalidate stale dialogs and reset pending case state.
Profile settings works with no case; explicit dropdown choices without an existing
case atomically update the private new-case default and survive restart. Selection
for an existing case must not replace that default; Clear preserves it. Case metadata tolerates synchronized 0755/0775 and 0644/0664
modes with ownership/link/world-write checks; never relax the private profile-store
validators or chmod real synchronized metadata to work around selection failures.
Model settings has one OCR page: embedded-text/local-OCR selection above local OCR
settings. Left-hand categories are direct ActionRow destinations, not expanders
with single nested pages. Keep existing persistence keys; do not restore separate Prepare pages.

The legacy category, role, formal-proposal and first-page parental-attendance
rules described below apply to unassigned compatibility contexts. Bound profiles
use their declared catalogs/policies instead; do not reintroduce Dependency rules
into neutral core contracts. Run isolated unit/GTK/pipeline tests, native guard and
resource validation after changes. Keep package-data declarations covering every
bundled profile resource; source deployments must retain their own `.pi/` tree.

## Passive run metrics
- The runner's native stages and extraction/synthesis children may explicitly load the sibling `PiRunMetrics/run-collector.ts` via `recordprep/run_metrics.py`. This is the sole passive-observer exception to tracked `.pi/` resource confinement. It adds no tools/prompts and changes no publication authority, Stop/stall behavior or content-free stdout. One settled child is not whole-pipeline success. Skips and zero-model helpers produce no runs.
- Native tags use step IDs; summary tags use the five code-owned summary skill IDs (including `recordprep-summarize-minutes`), never item IDs/case names. Default archive is this source project's Git-ignored `.run-metrics/runs/` (may Dropbox-sync). Preserve absolute root/collector overrides and `PI_RUN_METRICS_ENABLED=0`. Sibling policy probes metadata with deadlines, collects only on Pi >=0.87.1, and warns/fails open without upgrading Pi or relocating archives. Tests must never load/save real config.

## Goal

RecordPrep converts OCR-readable legal-record PDFs into direct-source, citation-aware case bundles for Focus Agent search. It may create one concise, versioned, nonauthoritative case-orientation overview, but it must not create retrieval/optimization copies, persistent chunks, speaker-labeled transcript rewrites, embeddings, or vector databases.

## Entry points and modules

- `recordprep/cli.py`: command parser.
- `python -m recordprep app`: GTK application entry.
- `recordprep/ui/main_window.py`: Libadwaita UI, settings (including per-PI-stage model/reasoning overrides), direct-source pipeline (minute orders), summary stage settings, and step handlers (hearing/report summary handlers are thin wrappers around `_run_pi_skill_step`).
- `recordprep/classification.py`: classification worker pool.
- `recordprep/config.py`: supported settings import surface.
- `recordprep/manifest.py`: manifest import surface.
- `recordprep/summaries.py`: summary path/link import surface.
- `recordprep/summary_editions.py`: page-matched Letter PDF editions and Focus page maps.
- `recordprep/minute_summaries.py`: single-stage direct-source PI minute summaries. Profile-bound format3: hearing identity, complete-order appearances, attributed party positions, findings/orders, next hearing; no attendance selector or reporting-status sentence. Old profile attendance fields are inert; checkpoints1/2 remain readable; unassigned legacy first-page prompt stays separate.
- `recordprep/summary_agents.py`: two-stage PI summary pipeline — work items, fingerprints, canonical Markdown digest/meta publication with per-kind locks, quote span resolution, recurrence analysis, synthesis validation, and deterministic rendering.
- `recordprep/summary_categories.py`: strict loader for the tracked category-guidance resources; code-owned category ids/titles/order live here, editable guidance prose lives in `recordprep/resources/summary_categories/`.
- `recordprep/documents.py`: PDF merge, extraction, rendering, and OCR import surface.
- `recordprep/pi_runtime.py`: PI discovery/model settings, model context metadata, and summary context preflight.
- `recordprep/summary_preflight.py`: provider-qualified model identity resolution (full model id, never a basename; one discovery result reused per stage), model-visible component composition, honest UTF-8-aware estimate ranges, the capacity policy (known-oversized individual requests fail before the paid call; aggregate synthesis history warns and proceeds; unknown metadata stays visibly unknown), and the read-only `python -m recordprep.summary_preflight` diagnostic (no paid calls, no publishing lock, no writes).
- `recordprep/pi_bundle.py`: PI artifact/schema validation (including both summary PI stages).
- `.pi/`: tracked system prompt, project-local Agent Skills, sequential runner, auto-exit extension, and summary-tools extension.

Do not add a root-level `recordprep.py` shim. Use modern Libadwaita widgets and flat buttons.

## Pipeline

1. Create files.
2. Detect transcript layout (PI).
3. Strip characters.
4. Infer case (PI; first three pages, private candidate, Python-only publication).
5. Basic/advanced/corrected/date/name classification.
6. Build/correct TOC.
7. Find/correct hearing, report, and minute boundaries.
8. Number transcript pages with PI. Python then normalizes every
   `citation_label`/`citation_key` to the canonical `PREFIX N`/`PREFIX:N` form
   (never model-authored `p.`/`pp.` notation) before participant indexing,
   summaries, or the source map trust the artifact.
9. Build `artifacts/participant_index.json` schema v2 with PI from appearances, express attendance/absence, unsworn colloquy, RT witness indexes, and sworn/examination evidence. A fresh, resolved CT-only layout (read through `transcript_layout.is_ct_only`, the single applicability predicate) skips this step entirely: the UI and `.pi/scripts/run_recordprep_skill.py` return a successful `Skipped — Clerk’s transcript only` no-op before any VTE/PI launch, pre-existing participant artifacts are ignored on disk and excluded from downstream freshness inputs, and the overview/source-map participant requirement is waived. Missing, malformed, stale, or needs-review layouts never authorize the exemption; RT-only and mixed records keep full participant validation and attribution.
10. Create summaries in three independently runnable stages. Hearing and report stages run the resumable two-stage PI pipeline (`recordprep/summary_agents.py` + `.pi/extensions/recordprep-summary-tools.ts`): stage one launches one fresh `--mode json --no-session` PI process per document whose only tools are `recordprep_get_source` (the document's complete source pages in one payload, with the full digest contract in the runtime prompt) and `recordprep_submit_extraction`; Python deterministically normalizes the candidate — agent-output problems are never fatal — injecting the runner-owned item id, reordering configured categories, ignoring unknown ones, filling missing or malformed categories with `digest: null`, and flagging sanitized warning codes (category ids and counts only) in the row metadata, while best-effort verifying each quote against its declared page (normalization, then case/typography; unmatched quotes are kept as submitted with `verified: false` rather than rejected) and discarding any category digest whose evidence crosses the report proposal cutoff. Python is the sole canonical digest Markdown/metadata publisher under an exclusive per-kind lock (stable `.hearings_facts.lock` path) with atomic replace and a final newline. Stage two launches one fresh PI process per completed digest Markdown document — reloaded and validated from disk before synthesis, never the pre-publication in-memory rows — with dataset-only tools serving one Python-rendered Markdown block per document, a synthesis-only scratchpad tool (`recordprep_synthesis_scratchpad` read/replace, stored in extension-owned process-local memory separate from conversation history so notes survive context compaction; notes are orientation aids, never evidence, never published or logged, and they disappear when the process ends — synthesis restart resumability is explicitly deferred), and a `view: "submitted_section"` read for already-submitted drafts after compaction; the model works incrementally — overview and scratchpad first, then documents in boundary order or agent-chosen logical groups, submitting each section as it completes it and replacing its scratchpad notes, with revisions by resubmitting the same item id that never move later developments into earlier event chronology — and always emits the sections it has; Python validates the candidate's private coverage diagnostics (well-typed unread/missing counts only), reorders known sections, drops unknown ones, fills missing or empty sections with a deterministic prose fallback from the category digests, resolves known quote placeholders, replaces any submitted section that still references unknown quote ids with the same digest-prose fallback (a sanitized warning — never silent in-sentence deletion of quoted wording), and flattens any generated page-link markup, then a deterministic renderer publishes the final plain-text summary (ordinary curly-quoted quotations, plain `Date — Hearing` headings, no generated `](page:NNNN)` markup) plus final metadata atomically. Quality problems — typed quotation marks, unverified or duplicate quote use, out-of-range quote length, ellipsis or terminal punctuation inside a quotation, technical metadata in narrative, and repeated report passages — are sanitized warnings, never failures. Item IDs are stable by kind and start page; duplicate stable ids and overlapping document ranges are rejected before any paid work. Generation fingerprints cover every payload dependency — end pages, labels, source text, the effective guidance and category-description text, the effective provider/model/thinking (override or inherited project PI settings), the private participant context, transcript citation labels, and the proposal delimiter position — so any of those changes mark only the affected rows regeneration-pending. Digest and final metadata use schema version 4 with explicit dependency/fingerprint fields; schema-3 metadata stays readable but its freshness is unproven, so those artifacts report as regeneration-pending rather than current. Artifact integrity validation (structural consistency) is separate from current-generation freshness (`summary_stage_freshness_issues`), and stage completion plus downstream prerequisites (case overview, source map) require both; the UI uses a reusable stage-input snapshot cached by an invalidation signature (settings, resources, boundaries, source pages, published artifacts) so completion predicates never rescan the record repeatedly. Each stage writes only its own final summary file (`hearings_sum_<case>.txt` / `reports_sum_<case>.txt`) and completes independently; hearing extraction requires the validated participant index, while report extraction does not. For a fresh CT-only layout with a valid empty hearing-boundary array, hearing extraction builds zero work items without loading participants and the existing zero-item publishing flow applies with no model calls; CT-only with nonempty hearing boundaries fails with an actionable layout/boundary inconsistency, and transcript-layout changes are watched in hearing-summary freshness/cache signatures so a layout decision cannot reuse a stale exemption. A zero-item boundary set publishes a valid header-only digest Markdown document and a title-only summary without a paid call. Existing v2 `*_digests_*.jsonl` bundles migrate losslessly, with zero model calls, when their summary stage next runs under its lock: Markdown is authoritative once present, only missing or stale rows re-extract, and the retired JSONL is removed only after the Markdown, metadata, and final summary have published and validated; a legacy pair whose data and metadata disagree is preserved and reported. Legacy v1 `*_facts_*.jsonl` artifacts are ignored (never converted) and removed only after the digest pipeline publishes successfully; the minute-order stage uses the single-stage PI path described below and writes only its own minute summary/checkpoint/metadata.
11. Build page-matched summary editions deterministically: directly after the three summary stages (the retired Add-links step was removed), render each summary into a fixed US-Letter PDF and a schema-v2 page-map sidecar under `summaries/editions/`. The PDF is the immutable pagination authority under the fixed `recordprep-summary-letter-v3` layout (Letter portrait, 54-point margins, 11-point body, 1.18 line height, 0.5em paragraph spacing, `Page N of M` 9-point Times footer, numbering restarting at 1 per category). Recognized quoted phrases render in bold through the built-in Nimbus Roman bold face and lose only their outer style-matched straight/curly double quote delimiters — a presentation-only transformation of the printable representation; the canonical `.txt` summaries keep every quotation mark byte-for-byte, and summary generation, digests, prompts, and extraction fingerprints are untouched. Recognition is conservative: style-matched double quote pairs within one source line whose content survives rendering-equivalent normalization and that never partially overlap a trusted link span; unmatched delimiters, whitespace-only pairs, and nested quotations stay literal, and the recorded quote-presentation policy in the layout metadata makes the transformation explicit. The sidecar records per-page selectable body text, trusted record-page link spans and targets, required quote-fragment spans (exact offsets into the page text, exact labels, and the complete quote content for record-wide phrase search on fragments that wrap across a paper-page boundary, derived from the same monotonic rendering-normalized alignment as coverage and never by global substring search), inclusive source-line ranges, and source/PDF hashes; generation verifies normalized page text reproduces the printable source exactly and fails rather than dropping a link, a bold span, or text. The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is deterministic and never depends on locally installed fonts, Fontconfig, or any external font file. The sidecar layout metadata records the complete typography contract plus the quote-presentation policy, and validation rejects any sidecar whose schema, layout ID, fixed metrics, or policy differ, requires well-formed nonoverlapping quote spans that completely map every recognized quotation, and tolerates quote spans overlapping link spans (explicit page-link navigation wins in Focus), so pre-v3/v2 editions show the build step as pending until rebuilt (old editions remain untouched until a successful rebuild). Build and validate all three candidates before replacing any edition, publish PDF then sidecar atomically, and invalidate only the rerun category's edition after a summary text change. Editions are never Agent evidence or source-map search paths. RecordPrep/`summary_editions.py` owns this logic, re-exported through `recordprep/summaries.py`.
12. Create the concise nonauthoritative `artifacts/case_overview.md` orientation aid.
13. Build source-map v2 last.

Transcript layout detection runs immediately after Create files, once per new
or changed bundle, and publishes `artifacts/transcript_layout.json` schema v1.
It searches OCR text first and opens only targeted page images (soft budget of
12 PNGs per detection), never a full image sweep. A high-confidence agent
result continues automatically; ambiguity publishes a structurally valid
`needs_review` artifact and pauses before any layout-dependent mutation.
Layouts are case-local, bound to the current page count and input signature;
a value from another case is never used. RecordPrep may atomically rebind an
unchanged, resolved decision after its own guarded text-only normalization.
It must rerun detection when numbered page identity or paired images change,
or when text changes outside that controlled pass. All downstream routing
reads the validated artifact; the manifest `rt_ct_split_mode`/`rt_ct_split_page` fields
are legacy compatibility mirrors only. The retired `rt_ct_split_page` config
key is removed during config migration.

The participant index is hearing-scoped and separates counsel, non-counsel participants, and witnesses. Its helper publishes a temporary, nonauthoritative worklist under `temp/` that scopes first/appearance pages, RT-index pages, and oath/examination/attendance markers without copying source-page text. The agent processes one hearing at a time, reads single source pages, persists completed hearings incrementally, and uses partial validation after batches of at most five hearings. It must never concatenate the complete RT or a multi-hundred-page run. Full validation rejects the unreviewed template placeholder. Law firms/agencies are organizations, not attorney aliases. Q/A alone is not testimony. Unknown/conflicting identity, attendance, witness, or counsel evidence must remain explicit rather than guessed.

Profile-bound minute orders use PROFILE_MINUTE_CORE plus topic-independent minute
guidance: hearing identity, source-supported appearances, attributed party positions,
main findings/orders and next hearing. Attendance is fixed to complete-order evidence;
no presence/absence inference from counsel alone or missing names. There is no policy
selector; old policy fields are inert and exact former bundled prose resolves to the
new default without private writes. Checkpoint/final metadata3 has positions and
next_hearing instead of reporting status; historical1/2 readers preserve old output.
The following legacy minute prompt applies only to unassigned compatibility work.

Minute orders run one fresh, restricted PI child per complete boundary-scoped order using the shared **PI synthesis** model/provider/reasoning overrides, or inherited project settings. There is no digest stage, no direct API credential dependency, and no source windowing. Preserve the immutable minute prompt: hearing name, reported/not reported, each parent's personal appearance from the FIRST PAGE only (attorney-only listings mean not present), and concise actual orders. Custom `summarize_minutes_prompt` guidance stays intact and is subordinate. The dedicated `.pi/skills/recordprep-summarize-minutes/` skill and `.pi/extensions/recordprep-minute-tools.ts` expose only source-read and candidate-submit tools; Python validates affirmative first-page quote locations, marks unverified attendance unclear with sanitized warnings, and renders the paragraph. Location verification is not semantic proof of attendance. Ambiguous evidence stays unclear. Unusable/missing candidates preserve the prior final rather than inventing a summary. Python owns `minutes_sum_<case>.rows.json` checkpoints and `.meta.json`, uses the per-kind lock and atomic writes, and fingerprints source, boundaries, labels/citations, guidance, model/reasoning and dedicated resources. Resume regenerates only missing/stale orders; completed checkpoints need no Pi call. Legacy direct-API text remains untouched but pending until regenerated. UI completion and overview/source-map prerequisites require current metadata. Only changed minute text invalidates its edition. Stop/stall, private workspace cleanup, model capacity preflight, and content-free logs reuse the summary runner. Do not alter the hearing/report extension merely to add minute tools, since its hash is a hearing/report synthesis dependency.

Summary extraction and minute summarization serve each document's complete source pages in one payload — neither is windowed. End-user prompt testing and its direct-API request/payload paths are removed. Ordinary Settings edits production credentials/models/machine settings, never legacy prompt prose or inert sandbox keys. There are no output word targets: summary length follows each document's substantive complexity, and conciseness comes from selecting significant information and avoiding repetition — never from a numerical limit. The retired `summarize_hearings_target_words` / `summarize_reports_target_words` keys (and the legacy `summarize_reports_window_target_words`) remain stored but are inert: nothing reads them, the Settings-save flow preserves any existing values untouched, and new configurations never create them.

A formal package of proposed/recommended advisements, findings, orders, and associated boilerplate offered for court adoption is out of summary scope. A conservative, ephemeral detector recognizes only bounded structural signatures (a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order`); it never fires on a generic recommendation heading, a change-in-recommendation note, a substantive treatment/assessment recommendation, a singular assessment-order request, or narrative references to orders the court already made. Actual historical orders and a high-level agency recommendation stated apart from the formal template remain distinguishable and in scope. Detection is carried only as a non-sensitive page/offset/line/kind marker; matched text is never logged or persisted. Report extraction inserts the scope delimiter at the marker in the source payload and Python rejects evidence quotes from pages past the cutoff; marker-page quotes are verified against the eligible prefix only, so a quotation at/after the delimiter, crossing it, or unverifiable from the prefix cannot survive by matching excluded text (conservative category fallback and warnings retained).

Canonical digest rows carry trusted Python-injected metadata (schema version 2, kind, stable item id by kind and start page, ordinal, label, page range, source and generation fingerprints, sanitized `quality_flags`) and categories in exact configured order: hearings use `parent_appearances`, `evidence_considered`, `testimony`, `disputed_legal_issues`, `party_positions_and_reasons`, `court_orders_and_reasons`; reports use the expanded twelve-category schema ending in `placement_and_caregiver_adoption_approval`. The canonical store for those rows is the versioned Markdown document `summaries/<kind>_digests_<case>.md` (Markdown format version 1, independent of the v2 row schema): a document title with a generated-artifact notice, one level-two heading per document (label, item id, source-page range), one level-three heading per category (readable name, category id), digest prose, an explicit `No material content.` null marker, a `#### Direct quotes` subsection carrying each quote's id, file page, and verified status, and a `No direct quotes.` marker for a non-null digest with an empty evidence bank. Reserved `recordprep:digest-*` HTML comments carry fingerprints, ordinals, quality flags, source offsets/hashes, and schema identifiers — never digest or quote text; content is reversibly escaped so source text cannot create headings, comments, links, or delimiters; parsing accepts only the generated grammar, validates reconstructed rows against canonical re-serialization, and rejects duplicates, malformed structure, metadata disagreement, unsupported versions, and truncation with sanitized location-based errors. The Markdown file is for inspection, not manual editing. Each category canonicalizes to exactly one `digest`: `null` when the source has no material orientation-worthy content, or `{text, evidence}` holding one concise salience-based synthesis (representative examples, not an inventory; a development lives in its best category once) plus a small bank of short verbatim quotes — continuous two-to-five-word source phrases, preferably distinctive three-to-five-word anchors, chosen for important points with no fixed count. Quotes are checked against the declared page after Unicode/whitespace normalization, with Python recording the original offsets, canonical quote id, and page hash when the quote is found. Ambiguous matches keep the first occurrence, and unmatched quotes are flagged `verified: false` and kept: quote fidelity is never a pipeline failure. Stage one records developments described as current/recent by a report; stage two determines what is genuinely new. Recurrence analysis is retained for diagnostics and prompt tuning only. All agent-output handling is nonfatal: only source/model execution failures, generated-store corruption, rendering integrity failures, or atomic publication failures may stop a run rather than publish corrupt data, and they preserve the prior final summary. All-null documents keep their required document heading with no sentinel paragraph; unusable extraction is distinguished from genuinely empty categories through private warnings only.

One effective-guidance contract governs both summary phases (`resolve_phase_guidance`): the immutable relevance, scope, schema, quote, and safety contract is always the main guidance; previously shipped built-ins — including the retired digest built-ins with length and six-quote guidance — are recognized by exact historical text reconstructed from tracked history and advance to the current contract without reattaching retired text, while custom prompts remain byte-for-byte unchanged in configuration and are composed as lower-priority additional guidance that cannot override the immutable contract. Per-category guidance prose is loaded and frozen per stage from the tracked resources under `recordprep/resources/summary_categories/` (ids, display titles, ordering, and null semantics stay code-owned; the strict loader rejects missing, duplicated, unknown, reordered, or empty sections with actionable errors before any paid work), and the effective description text is part of each row's extraction fingerprint, so editing one kind's file stales only that kind's rows. Do not reinterpret the retired paragraph-count setting as a page count. Profile settings uses digest topic cards and minute-order guidance, never separate hearing/report review or writing instruction fields. Save writes a private customization, never the tracked bundled/category files; legacy prose stays available to compatibility loaders without duplicate ordinary-settings editors. The hearing source payload includes validated participant-index context privately under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` — counsel, participants, and the witness/testimony picture (verified witnesses with mapped, cited examinations, or explicit `Testimony: None.`) — as attribution context only; every submitted fact still requires evidence from original hearing pages. Summaries are nonauthoritative; source pages remain the factual authority.

The case overview is a schema-versioned orientation aid derived from source summaries and, when participant indexing applies to the resolved layout, participant metadata; a CT-only overview uses the report/minute summaries and the valid empty hearing summary and identifies the absence of reporter-transcript attribution in Record Scope. It is never authoritative evidence and must be regenerated when those inputs change (the participant artifact and the transcript layout are overview freshness inputs).

Source-map v2 uses original `text_pages`, boundaries, transcript citation metadata, participants, examinations, warnings, the case-overview path, and summary paths. For CT-only records the final publisher uses an empty in-memory participant structure (`hearings: []`), omits `paths.participant_index` and `manifest.files.participant_index` (a CT-only published participant path is rejected), records the explicit unavailable-attribution scope warning, and keeps schema v2 unchanged; RT-only/mixed maps publish the normal validated participant data and canonical path. Only source pages are authoritative evidence.

## PI rules

- Keep every RecordPrep PI resource under tracked `.pi/`.
- Invoke one explicit skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Native VTE stages stage `.pi/SYSTEM.md`, one skill, and only `extensions/recordprep-auto-exit.ts` into a private workspace. Summary stages stage `.pi/SYSTEM.md`, the phase skill, and only `extensions/recordprep-summary-tools.ts` (or `extensions/recordprep-minute-tools.ts` for minute orders), with `--mode json --no-session --approve`, an exact custom-tool allowlist, optional runner-owned `--provider`/`--model`/`--thinking` overrides, and a unique private cache workspace and candidate path removed in `finally`.
- Preserve PI's native interactive VTE UI for the native stages.
- Infer case uses recordprep-infer-case and its dedicated case-name-tools guard:
  read only up to three staged text pages, write/edit only the private candidate,
  no shell or canonical file access. Python checks case identity/selection, source
  inventory/bytes, shared model preferences, contract resources and prior output
  before atomic publication. Unknown/invalid/missing candidates and Stop preserve
  the old name. Model settings no longer exposes a caption API; retired credentials
  and prompts stay inert/untouched. Keep the separate native profile guard unchanged.
- Validate each stage after PI exits; summary children publish only after Python-side validation of the candidate.
- The runner monitors session-file growth and child CPU state for native stages and JSON-event activity for summary children. Summary children are consumed through timed non-blocking polling, so a silently hanging child still triggers a visible stalled-stage warning and Stop stays responsive; a stall never kills PI automatically — the user must press Stop. Each summary child reports sanitized aggregate telemetry (elapsed time, supplied usage numbers with authoritative final-message usage replacing streamed totals, peak reported context, compaction count, tool-call count) — never model text, tool arguments/results, scratchpad notes, or provider error bodies.
- Stop signals the runner, terminates the active child's complete process group, escalates to SIGKILL only when SIGTERM fails, releases locks, restores the row to Pending, and prevents the next child or downstream stages from starting.
- PI launch logs the immutable bundle root. RecordPrep warns when a parent folder's apparent appellate case number conflicts with manifest/PDF identity, but never moves or renames private case data. Summary child output never contains prompts, source text, tool arguments/results, model prose, or digest facts — only phase, ordinal/count, event class, PID, elapsed/stall information, and sanitized error codes. Synthesis children receive structured, nonfatal correction feedback from the section-submission tool (invalid quote ids with the allowed ids, advisory typed-quotation-mark and zero-placeholder notes); the feedback stays inside the private model/tool exchange, and public logs carry sanitized codes and counts only.
- Harden executable resolution before any `--version` or agent spawn: never attempt a nonexistent configured path; rediscover only for `pi` or a known legacy default location and fail early with the discovered alternative for an arbitrary missing custom command. The summary-resource minimum is PI 0.85 while Node 20+ stays a documentation-level dependency; never hard-code an absolute installer path.
- The six native PI stages share one project model and reasoning level from `.pi/settings.json`; there are no per-stage overrides. The retired `pi_stage_<step>_pi_*` config keys are ignored on read and removed only by an explicit Settings save.
- The transcript-layout skill writes only `artifacts/transcript_layout.json`; the runner accepts a structurally valid `needs_review` artifact, while RecordPrep treats only a resolved, fresh artifact as step completion. Direct participant-stage invocation of the runner exits 0 with the explicit skip reason for a CT-only record before any PI executable/version check or workspace creation.
- Transcript numbering, participant, and summary stages must not update `manifest.json`.
- The case-overview skill writes only `artifacts/case_overview.md`.
- The final source-map skill is the single manifest publisher and also publishes the `transcript_layout` path.
- Do not add an agent framework, subagent abstraction, or runtime npm install.

## Source extraction

- Use `pdftotext` with `physical=True` for `text_pages/0001.txt`, etc.
- Render grayscale 300-DPI `image_pages/0001.png`, etc., with PyMuPDF.
- Preserve source page identity and never place private case content in tests or commits.

## Development commands

```bash
uv run python -m recordprep app
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
uv run python -m recordprep.summary_preflight --case-bundle PATH --kind both
```

Use the Agent Skill validator for every changed skill. Keep `pyproject.toml` and tracked `uv.lock` synchronized. GTK4 VTE, PI 0.85+ (0.80+ for the native stages), and Node 20+ are system/runtime dependencies.
