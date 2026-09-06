# RecordPrep

<img src="recordprep_icon.png" alt="RecordPrep icon" width="128" align="left">

RecordPrep is a GTK4/Libadwaita desktop pipeline that converts OCR-readable legal-record PDFs into a citation-aware case bundle for Focus. It preserves original page text/images, classifies pages, finds document boundaries, numbers official transcript pages, verifies counsel and witnesses, creates detailed summaries from source pages, and publishes source-map v2 for PI Agent search.

RecordPrep creates one concise, versioned, nonauthoritative case-orientation overview. It does not create retrieval chunks, speaker-labeled transcript rewrites, embeddings, Chroma stores, vector databases, or any case-overview retrieval index.

## Requirements

- Python 3.13+
- GTK4, Libadwaita, and GTK4 VTE
- [uv](https://docs.astral.sh/uv/)
- PI 0.80+ and Node.js 20+ for the project-local knowledge-work stages
- `pdftotext`, PyMuPDF, and PyPDF for extraction/rendering
- An OpenAI-compatible vision endpoint for page classification and case-name inference
- An OpenAI-compatible text endpoint for source-page summaries

Install:

```bash
uv sync
```

Run:

```bash
uv run python -m recordprep app
```

## Direct-source pipeline

### Prepare

1. **Create files** — create `text_pages/NNNN.txt` and 300-DPI grayscale `image_pages/NNNN.png`; merge selected PDFs in natural order when needed.
2. **Detect transcript layout** — PI searches all extracted OCR text for structural RT/CT markers and opens only targeted page images (soft budget of 12 PNGs); it publishes the case-local schema-v1 `artifacts/transcript_layout.json` (RT-only, CT-only, or RT-then-CT with the exact boundary).
3. **Strip characters** — remove nonprinting extraction artifacts.
4. **Infer case** — write `case_name.txt`.

### Classify and organize

5. Classify RT/CT pages.
6. Add advanced first/last markers, dates, report/form names, and corrections.
7. Build/correct the TOC.
8. Find/correct hearing, report, and minute-order boundaries.

### Record context

9. **Number transcript pages** — PI writes official citation mappings and citation-series metadata.
10. **Build participant and witness index** — a deterministic helper first writes a temporary, nonauthoritative worklist containing hearing ranges, first/appearance pages, reporter-series-scoped `RT_index` pages, and oath/examination/attendance marker pages with resolved citations. PI then processes one hearing at a time, reads only original single-page sources, persists reviewed hearings incrementally, validates batches of at most five, and writes schema-v2 `artifacts/participant_index.json`. Full validation rejects the untouched template.

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
from the legacy fields after dependent work exists requires a rebuild from
Create files (RT-specific text cleanup is destructive).

Counsel, non-counsel participants, and witnesses are separate hearing-scoped records. Law firms and agency abbreviations are stored as organizations rather than attorney aliases. Witness status is explicit: `verified`, `none`, `unknown`, or `conflict`; Q/A formatting alone never establishes testimony. The participant stage never concatenates a complete transcript or multi-hundred-page range. When its bounded evidence budget cannot resolve a hearing, it preserves hearing-specific uncertainty instead of stalling.

During PI stages, RecordPrep displays the immutable bundle root used by the runner. It warns when the parent folder appears to name a different appellate case than the manifest/PDF, but never moves or renames private case data. The runner also monitors session-file progress and PI CPU state. Sustained CPU activity without session progress produces an actionable Activity/VTE warning; work continues until the user explicitly presses **Stop**. Stop terminates PI's complete process group, returns the active row to Pending, and prevents later stages from starting.

### Summarize

10. **Create hearing summaries** — a resumable two-stage PI pipeline: one fresh PI process per hearing reads the complete source pages and writes one concise salience-based digest per category (plus a small verbatim-quote bank) into the readable Markdown store `summaries/hearings_digests_<case>.md`, then one fresh PI process synthesizes the digests into a plain-prose `summaries/hearings_sum_<case>.txt`. Requires the participant index.
11. **Create report summaries** — the same two-stage PI pipeline for reports (expanded 12-category schema, extraction excludes formal proposed findings/orders, synthesis suppresses carried-forward duplication).
12. **Create minute-order summaries** — the configured Summarize API (minute-order credentials only) reads minute-order-boundary-scoped source pages directly.
13. **Build paginated summary editions** — deterministically render each summary into a fixed US-Letter PDF plus a Focus page-map sidecar under `summaries/editions/`, with page numbering restarting at 1 per category.

Hearing and report summarization runs a **two-stage PI pipeline** (`recordprep/summary_agents.py` plus `.pi/extensions/recordprep-summary-tools.ts`) built around concise category digests rather than atomized fact inventories. Stage one launches one genuinely fresh `--mode json --no-session` PI process per document: its only tools are `recordprep_get_source` (which serves that document's complete source pages in one payload — never an arbitrary path) and `recordprep_submit_extraction`, and the runtime prompt carries the complete digest contract — every category's detailed guidance, the salience priorities, and the relevance/quote content contract. Python deterministically normalizes the candidate (agent-output problems never fail the run): the runner-owned item id is injected, configured categories are reordered into canonical order, unknown ones ignored, missing or malformed ones filled with `digest: null`, and sanitized warning codes (category ids and counts only) recorded alongside the row. Quote verification stays best-effort — unmatched quotes are kept with `verified: false` — and evidence crossing the report proposal cutoff discards that category digest conservatively. Python is the sole canonical `summaries/<kind>_digests_<case>.md` publisher under an exclusive per-kind lock, together with a hash-bound metadata sidecar.

The canonical digest store is a **self-contained, versioned Markdown document** (format version 1, tracked separately from the unchanged v2 row schema): one level-two heading per document with its item id and source-page range, one level-three heading per category with its id, digest prose, an explicit `No material content.` null marker, a `#### Direct quotes` subsection whose entries carry quote id, file page, and verified status, and a `No direct quotes.` marker for empty evidence banks. Technical metadata (fingerprints, ordinals, quality flags, source offsets and page hashes, schema identifiers) lives in reserved `recordprep:digest-*` HTML comments that never duplicate digest or quote text; content is reversibly escaped so source text cannot forge headings, comments, links, or delimiters, and parsing accepts only the exact generated grammar (validated by canonical re-serialization) with sanitized line-numbered errors. Markdown for inspection, not manual editing: rerun the summary stage to regenerate it.

Interrupted runs resume at the first missing or stale row; changed boundaries, prompts, source text, models, reasoning levels, labels, or the content-contract version mark only the affected rows stale. Existing v2 `*_digests_*.jsonl` bundles migrate automatically and losslessly — with zero model calls — the next time their summary stage runs: the Markdown file is authoritative, stale rows alone are re-extracted, and the retired JSONL is removed only after the Markdown, metadata, and final summary have all published and validated. A legacy pair whose data and metadata disagree is preserved and reported for deliberate recovery. Legacy v1 `*_facts_*.jsonl` artifacts remain ignored, never converted, and are removed only after the digest pipeline publishes successfully. Stage two launches one fresh PI process per completed digest document whose dataset tool serves the overview or one document's Python-rendered Markdown block by ordinal (category ids, quote ids, pages, and verification status included; fingerprint comments omitted); the runner reloads and validates the published Markdown before synthesis, and the finish tool always emits the sections recorded so far, while Python reorders known sections, fills missing or empty ones with a deterministic digest-prose fallback, resolves known `{{quote:<id>}}` placeholders, replaces any submitted section that still references unknown quote ids with the same digest-prose fallback (a sanitized warning — the submission tool's nonfatal feedback identifies invalid ids and the allowed ones so the model can fix the section before finalizing), and flattens any generated page-link markup. Quality problems — typed quotation marks, unverified or duplicate quote use, out-of-range quote length, ellipsis or terminal punctuation inside a quotation, technical metadata in narrative, and repeated report passages — become sanitized warnings, never failures; deduplicated quality codes are stored in the optional final-metadata `quality_flags` field and shown in Activity. There are no word targets: summary length follows substantive complexity, and conciseness comes from selecting significant information and avoiding repetition. A deterministic renderer then replaces placeholders with ordinary curly-quoted text, renders plain `Date — Hearing` headings, and publishes the final text and final metadata atomically. Final summaries contain no generated `](page:NNNN)` links: Focus clicks quoted phrases into record-wide phrase searches instead, and legacy linked summaries keep working. The model never writes canonical files, and an integrity failure never replaces the prior summary. A zero-item boundary set publishes a valid header-only digest Markdown document and a title-only summary without a paid call. Model identity is resolved once per stage and matched provider-qualified on the full model id (never a basename), reusing one PI discovery result for every phase. Capacity accounting composes the components the model actually sees — system prompt, skill guidance, tool schemas (proxied by the staged extension source), the runtime prompt, the source payload or digest blocks — into a clearly labeled UTF-8-aware estimate range, never a tokenization guarantee. A known oversized individual source request fails before its paid call with the item id and actionable capacity information; the aggregate synthesis-history estimate warns and proceeds above the 80% safety margin (agent-managed incremental work, never forced batching), and unknown metadata is visibly reported as unknown while PI enforces its own limit. PI extraction is not windowed, so a model with a large context window (for example one million input tokens) handles every document in a single request. `python -m recordprep.summary_preflight --case-bundle PATH --kind both` reports counts, freshness, effective model identity/capacity, largest document payload, digest sizes, and the estimated synthesis history read-only — no paid calls, no publishing lock, no writes; missing or stale digests label the synthesis estimate extrapolated rather than measured.

The minute-order stage is unchanged: it uses the direct API path with its own credentials, windows, and prompt.

**Paginated summary editions** are built directly after the three summary stages (the retired Add-links step no longer mutates summary text). Each edition pairs `summaries/editions/<summary-stem>.pdf` with a schema-v1 `<summary-stem>.pages.json` sidecar. The PDF uses the fixed `recordprep-summary-letter-v2` layout — Letter portrait, 54-point margins, 11-point body with 1.18 line height and a 0.5em paragraph gap, `Page N of M` 9-point Times footer, numbering restarting at 1 — so it is the immutable pagination authority on every computer and printer. The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is fully deterministic: it never depends on locally installed fonts, Fontconfig, or any external font file. The denser v2 layout produced about 40% fewer pages than the previous 72-point/12-point layout on the reference bundle while passing full source-coverage validation. The sidecar layout metadata records the complete typography contract (page size, margins, font family, body size, line height, paragraph spacing, and footer template/family/size/baseline), and validation rejects any sidecar whose layout ID or fixed metrics differ — pre-v2 editions therefore show the build step as pending until they are rebuilt, and rebuilding is required once per case because pagination changes. The sidecar records per-page selectable body text (footers excluded), trusted record-page link spans with numeric targets, inclusive source-line ranges, and source/PDF SHA-256 hashes; RecordPrep verifies the pages reproduce the printable source text exactly before publishing. The `.txt` summaries remain the canonical inputs for case-overview and source-map workflows. Rerunning a summary category removes only that category's generated edition files; hash validation keeps stale editions out of Focus. The generated editions stay nonauthoritative: they never become Agent evidence or source-map search paths.

Extraction serves each document's **complete source pages in one payload** — there are no PI extraction window settings. Page-intact adaptive windows remain only where each window is a separate direct-API request: minute orders (6,000 characters/six pages by default, under the 12,000-character safety limit) and the prompt-testing sandbox, which uses built-in defaults for hearings and reports. PI extraction is not windowed: the hearing payload privately includes validated participant-index context under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` — counsel with roles and appearance, non-counsel participants with attendance/speaking/sworn status, and the witness/testimony picture (verified witnesses with mapped, cited examinations, or an explicit `Testimony: None.`) — attribution context only; every fact still needs evidence from the original hearing pages.

Report extraction still excludes the formal package of proposed or recommended advisements, findings, and orders (with associated boilerplate) offered for court adoption. The existing conservative detector recognizes only bounded structural signatures — a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order` — and the payload marks that point with an in-text scope delimiter, without deleting or rewriting any source text. Python rejects any evidence quote from pages past the cutoff, keeps actual historical orders and high-level agency recommendations eligible, and persists only fingerprints and counts — never matched proposal text.

Every non-null fact in the canonical JSONL carries at least one evidence quote with a best-effort verification flag: Python normalizes Unicode/whitespace (then case and typographic marks) and records original offsets plus the page hash when the quote is found on its declared page; quotes that cannot be located are kept as submitted and flagged `verified: false` with a sanitized count warning — never a stage failure. Facts categories with no responsive information are exactly `null`. Quote ids are canonical (`hearing:0421/court_orders_and_reasons/1/1`), and synthesis may only reference them through placeholders; the renderer, not the model, chooses the link target and quote text.

One effective-guidance contract governs every summary phase: the immutable built-in relevance, scope, schema, quote, and safety contract is always the main guidance; recognized historical built-ins — reconstructed by exact historical text from tracked history, including the retired digest built-ins with their six-quote guidance — advance to it without reattaching retired text, and genuinely custom text is preserved byte-for-byte in `config.json` and composed as explicitly subordinate additional guidance that cannot override the immutable contract. Per-category guidance prose lives in the tracked, editable files under `recordprep/resources/summary_categories/` (`hearings.md`, `reports.md`); category ids, display titles, ordering, and null semantics stay code-owned, and the loader rejects missing, duplicated, unknown, reordered, or empty sections before any paid work. Settings discloses the effective category descriptions read-only and edits only the custom additional guidance — the guidance editors no longer claim to show the complete prompt. Editing a category file makes that kind's published extraction rows regeneration-pending on the next stage run.

**Summary length** follows each document's substantive complexity; conciseness comes from selecting significant information and avoiding repetition, never from a numerical target. The retired word-target Settings controls have been removed, and any stored target values remain in `config.json` but are ignored.

### Agent Search

15. **Create case overview** — PI writes the concise schema-v1 `artifacts/case_overview.md` orientation aid from the source summaries and participant metadata.
16. **Build source map** — publish `artifacts/source_map.json` schema v2 and update `manifest.json`.

The case overview supplies parties, procedural posture, key events, principal issues, and record scope so a Focus Agent can orient before inspecting structural metadata. It is explicitly nonauthoritative, is freshness-checked against its inputs, and cannot support a final factual claim or citation.

Source-map v2 builds document ranges directly from boundaries and `text_pages`. It includes the canonical case-overview path, the resolved transcript-layout path, official citation lookups, hearing/date ranges, counsel names/roles/aliases, witnesses/examinations, per-page context, and attribution warnings. Summary and overview paths are nonauthoritative leads; source pages remain the evidence.

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
- `extensions/recordprep-summary-tools.ts`
- `skills/recordprep-detect-transcript-layout/`
- `skills/recordprep-number-transcript-pages/`
- `skills/recordprep-build-participant-index/`
- `skills/recordprep-extract-hearing/`
- `skills/recordprep-extract-report/`
- `skills/recordprep-synthesize-hearings/`
- `skills/recordprep-synthesize-reports/`
- `skills/recordprep-create-case-overview/`
- `skills/recordprep-build-source-map/`
- `scripts/run_recordprep_skill.py`

The four native VTE rows launch one explicitly loaded Agent Skill each in PI's native VTE UI. The two summary stages run headless JSON-mode children instead: one fresh `--no-session` PI process per document for extraction and one per completed JSONL for synthesis, staged with the summary extension and the phase skill only, with an exact custom-tool allowlist and no general tools. The runner captures JSON events but prints only phase, ordinal, event class, PID, elapsed/stall information, and sanitized error codes — never prompts, source text, tool arguments, or model prose. Stall monitoring tracks event activity rather than session growth; stalls warn but are never auto-killed. Stop terminates the active child's process group, escalates after the grace period, releases locks, and leaves the row Pending without starting the next item or synthesis. Each child gets a unique private cache workspace and candidate path removed in `finally`. The runner accepts a structurally valid `needs_review` layout artifact, while RecordPrep treats only a resolved, fresh artifact as step completion. Only the final source-map stage updates the manifest (including the `transcript_layout` path). Skills validate outputs before the pipeline advances.

## Settings

Settings include source extraction, local OCR, classification/case inference, the minute-order Summarize credentials and window settings (clearly labeled as minute-order-only), the soft words-per-report synthesis target (`0` disables the guidance; the ephemeral length-guidance section is attached to the report synthesis prompt), PI extraction and PI synthesis stage groups — each with an authenticated model dropdown (including `Use project PI model`) and reasoning level stored in RecordPrep `config.json` keys (`summary_extract_pi_*`/`summary_synthesize_pi_*`), never in `.pi/settings.json` — extraction guidance and synthesis guidance editors, and the PI command, model, and reasoning-level selection. The legacy shared `summarize_window_target_chars`/`summarize_window_max_pages` pair migrates to the minute-order keys and is removed on the next Settings save, together with the retired per-category PI extraction window keys (PI extraction sends each document's complete source pages and no longer uses windows). Recognized historical built-in hearing/report prompts migrate to the current extraction guidance on the next save; genuinely custom text remains byte-for-byte unchanged. Numeric entries are validated before saving, and invalid input keeps the Settings window open with an actionable message. The project default PI model and reasoning level are stored in the project `.pi/settings.json`; choosing the global default removes the project override. Each of the five native PI skill stages (layout detection, page numbering, participant index, case overview, source map) has its own model and reasoning override in `config.json` (`pi_stage_<step>_pi_*`) that is passed to that stage's PI session only; summary stage saves never call `save_project_pi_model()` or mutate `.pi/settings.json`. Retired artifact-pipeline credentials and prompts — including the old cross-case `rt_ct_split_page` key — are removed when local config is loaded or saved. The transcript expander offers automatic detection plus case-local manual overrides; a stale global value never populates a new case. The obsolete paragraph-count setting is not reinterpreted as a page count; adaptive defaults apply until the new settings are saved.

Saved run-until targets migrate as follows:

- retired raw/transform stages and the retired aggregate `create_summaries` target → `create_minute_order_summaries`
- retired overview stage → `create_case_overview`
- retired vector stage → `build_source_map`

## Validation

```bash
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
```

Validate each new/changed Agent Skill with the Agent Skill validator. Keep real case material, local credentials, and generated case bundles out of Git.
