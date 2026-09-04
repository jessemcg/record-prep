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

10. **Create hearing summaries** — a resumable two-stage PI pipeline: one fresh PI process per hearing extracts quote-verified structured facts into `summaries/hearings_facts_<case>.jsonl`, then one fresh PI process synthesizes the whole JSONL into `summaries/hearings_sum_<case>.txt`. Requires the participant index.
11. **Create report summaries** — the same two-stage PI pipeline for reports (expanded 12-category schema, extraction excludes formal proposed findings/orders, synthesis suppresses carried-forward duplication).
12. **Create minute-order summaries** — the configured Summarize API (minute-order credentials only) reads minute-order-boundary-scoped source pages directly.
13. **Add links** — add hearing/minute page links (hearing summary only); byte-identical text is never rewritten or invalidated.
14. **Build paginated summary editions** — deterministically render each summary into a fixed US-Letter PDF plus a Focus page-map sidecar under `summaries/editions/`, with page numbering restarting at 1 per category.

Hearing and report summarization runs a **two-stage PI pipeline** (`recordprep/summary_agents.py` plus `.pi/extensions/recordprep-summary-tools.ts`). Stage one launches one genuinely fresh `--mode json --no-session` PI process per document: its only tools are `recordprep_get_source` (which serves that document's complete source pages in one payload — never an arbitrary path) and `recordprep_submit_extraction`. Python independently re-validates the structured candidate — exact category ids and order, `facts: null` semantics, page scope, and two-to-twelve-word contiguous verbatim quotes matched against the declared page — then atomically appends or replaces that document's canonical JSONL row under an exclusive per-kind lock, together with a hash-chained metadata sidecar. Interrupted runs resume at the first missing or stale row; changed boundaries, prompts, source text, models, or reasoning levels mark only the affected rows stale. Stage two launches one fresh PI process per completed JSONL whose dataset tool exposes only row metadata or one canonical row by ordinal; sections are submitted incrementally and finalized only after every row was read. Python validates exact section order, category coverage/duplicate-suppression accounting (suppression only when facts are demonstrably carried forward), `{{quote:<id>}}`-only quotation placeholders, reuse of earlier reports' evidence, and long repeated narrative passages — then a deterministic renderer replaces placeholders with trusted `["phrase"](page:NNNN)` links and publishes the final text and final metadata atomically. The model never writes canonical files, and a synthesis failure never replaces the prior summary. A zero-item boundary set publishes a valid empty JSONL and a title-only summary without a paid call. A conservative context preflight compares each complete request against 80% of the extraction model's context capacity before any paid call; PI extraction is not windowed, so a model with a large context window (for example one million input tokens) handles every document in a single request.

The minute-order stage is unchanged: it uses the direct API path with its own credentials, windows, and prompt.

**Paginated summary editions** are built after Add links so hearing pagination is never invalidated by that later text mutation. Each edition pairs `summaries/editions/<summary-stem>.pdf` with a schema-v1 `<summary-stem>.pages.json` sidecar. The PDF uses the fixed `recordprep-summary-letter-v2` layout — Letter portrait, 54-point margins, 11-point body with 1.18 line height and a 0.5em paragraph gap, `Page N of M` 9-point Times footer, numbering restarting at 1 — so it is the immutable pagination authority on every computer and printer. The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is fully deterministic: it never depends on locally installed fonts, Fontconfig, or any external font file. The denser v2 layout produced about 40% fewer pages than the previous 72-point/12-point layout on the reference bundle while passing full source-coverage validation. The sidecar layout metadata records the complete typography contract (page size, margins, font family, body size, line height, paragraph spacing, and footer template/family/size/baseline), and validation rejects any sidecar whose layout ID or fixed metrics differ — pre-v2 editions therefore show the build step as pending until they are rebuilt, and rebuilding is required once per case because pagination changes. The sidecar records per-page selectable body text (footers excluded), trusted record-page link spans with numeric targets, inclusive source-line ranges, and source/PDF SHA-256 hashes; RecordPrep verifies the pages reproduce the printable source text exactly before publishing. The `.txt` summaries remain the canonical inputs for case-overview and source-map workflows. Rerunning a summary category, or Add links on the hearing summary, removes only that category's generated edition files; hash validation keeps stale editions out of Focus. The generated editions stay nonauthoritative: they never become Agent evidence or source-map search paths.

Extraction serves each document's **complete source pages in one payload** — there are no PI extraction window settings. Page-intact adaptive windows remain only where each window is a separate direct-API request: minute orders (6,000 characters/six pages by default, under the 12,000-character safety limit) and the prompt-testing sandbox, which uses built-in defaults for hearings and reports. PI extraction is not windowed: the hearing payload privately includes validated participant-index context under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` (attribution context only; every fact still needs evidence from the original hearing pages).

Report extraction still excludes the formal package of proposed or recommended advisements, findings, and orders (with associated boilerplate) offered for court adoption. The existing conservative detector recognizes only bounded structural signatures — a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order` — and the payload marks that point with an in-text scope delimiter, without deleting or rewriting any source text. Python rejects any evidence quote from pages past the cutoff, keeps actual historical orders and high-level agency recommendations eligible, and persists only fingerprints and counts — never matched proposal text.

Every non-null fact in the canonical JSONL carries at least one verified evidence quote: a two-to-twelve-word contiguous verbatim span matched against its declared page after Unicode/whitespace normalization, with original offsets and the page hash recorded by Python. Facts categories with no responsive information are exactly `null`. Quote ids are canonical (`hearing:0421/court_orders_and_reasons/1/1`), and synthesis may only reference them through placeholders; the renderer, not the model, chooses the link target and quote text.

The hearing and report guidance editors contain the complete extraction guidance actually sent; RecordPrep does not append a hidden attribution contract. Recognized historical built-in prompts migrate to the current extraction guidance while genuinely custom text is preserved byte-for-byte and wrapped as lower-priority additional guidance. Stage-two synthesis guidance has its own editors.

**Report density** remains a soft words-per-report target (`Words per report`, default 250; `0` disables it) carried only in report synthesis guidance. It is prompt guidance about output shape only — never an API token cap, truncation rule, validator, retry, or repair pass — and RecordPrep never cuts off or mechanically rejects an answer because of it.

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

Settings include source extraction, local OCR, classification/case inference, the minute-order Summarize credentials and window settings (clearly labeled as minute-order-only), the soft words-per-report synthesis target (`0` disables the guidance; the ephemeral length-guidance section is attached to the report synthesis prompt), PI extraction and PI synthesis stage groups — each with an authenticated model dropdown (including `Use project PI model`) and reasoning level stored in RecordPrep `config.json` keys (`summary_extract_pi_*`/`summary_synthesize_pi_*`), never in `.pi/settings.json` — extraction guidance and synthesis guidance editors, and the PI command, model, and reasoning-level selection. The legacy shared `summarize_window_target_chars`/`summarize_window_max_pages` pair migrates to the minute-order keys and is removed on the next Settings save, together with the retired per-category PI extraction window keys (PI extraction sends each document's complete source pages and no longer uses windows). Recognized historical built-in hearing/report prompts migrate to the current extraction guidance on the next save; genuinely custom text remains byte-for-byte unchanged. Numeric entries are validated before saving, and invalid input keeps the Settings window open with an actionable message. The PI reasoning level is stored in the project `.pi/settings.json`; choosing the global default removes the project override; summary stage saves never call `save_project_pi_model()` or mutate `.pi/settings.json`. Retired artifact-pipeline credentials and prompts — including the old cross-case `rt_ct_split_page` key — are removed when local config is loaded or saved. The transcript expander offers automatic detection plus case-local manual overrides; a stale global value never populates a new case. The obsolete paragraph-count setting is not reinterpreted as a page count; adaptive defaults apply until the new settings are saved.

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
