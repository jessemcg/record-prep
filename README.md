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

10. **Create hearing summaries** — the configured Summarize API reads hearing-boundary-scoped source pages directly and requires the participant index for attribution.
11. **Create report summaries** — the configured Summarize API reads report-boundary-scoped source pages directly, excluding formal proposed findings/orders.
12. **Create minute-order summaries** — the configured Summarize API reads minute-order-boundary-scoped source pages directly.
13. **Add links** — add hearing/minute page links (hearing summary only).
14. **Build paginated summary editions** — deterministically render each summary into a fixed US-Letter PDF plus a Focus page-map sidecar under `summaries/editions/`, with page numbering restarting at 1 per category.

The three summary stages are independently runnable rows, each with its own Run this step and Run from here actions. Each stage writes only its own output file (`summaries/hearings_sum_<case>.txt`, `summaries/reports_sum_<case>.txt`, or `summaries/minutes_sum_<case>.txt`) after all of its API windows succeed, so rerunning one category never rewrites the other two, and a stop or error leaves existing summaries untouched. Each row is Done exactly when its own summary file exists, so Resume can target a single missing category. Full pipeline runs still execute hearing, report, and minute-order generation in order before Add links.

**Paginated summary editions** are built after Add links so hearing pagination is never invalidated by that later text mutation. Each edition pairs `summaries/editions/<summary-stem>.pdf` with a schema-v1 `<summary-stem>.pages.json` sidecar. The PDF uses a fixed layout — Letter portrait, 72-point margins, 12-point serif body, `Page N of M` footer, numbering restarting at 1 — so it is the immutable pagination authority on every computer and printer. The sidecar records per-page selectable body text (footers excluded), trusted record-page link spans with numeric targets, inclusive source-line ranges, and source/PDF SHA-256 hashes; RecordPrep verifies the pages reproduce the printable source text exactly before publishing. The `.txt` summaries remain the canonical inputs for case-overview and source-map workflows. Rerunning a summary category, or Add links on the hearing summary, removes only that category's generated edition files; hash validation keeps stale editions out of Focus. The generated editions stay nonauthoritative: they never become Agent evidence or source-map search paths.

Summary inputs are adaptive, page-aligned **ephemeral windows**. RecordPrep adds complete source pages toward a 6,000-character target, stops at six primary pages or the 12,000-character safety limit, and prefers a break before a mapped witness examination. A single oversized page remains intact. The preceding page may be sent as context-only. Every primary page is summarized exactly once; no final compression pass discards unique detail, and no window text or metadata is written to disk.

Hearing requests privately repeat validated counsel/participant/examination context under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY`. The complete hearing prompt explains that this metadata comes from the earlier participant-index stage, is supplied only for attribution, and does not replace the transcript as the factual source. The prompt asks the summarization model to identify counsel by party role, distinguish sworn testimony from unsworn colloquy, and avoid publishing rosters or standalone testimony-status statements.

RecordPrep accepts the summarization model’s paragraph without deterministic attribution validation, rejection, or model-repair requests. Summaries are nonauthoritative orientation aids; verify material facts and attribution against the source pages.

Report summaries additionally exclude the formal package of proposed or recommended advisements, findings, and orders (with associated boilerplate) offered for court adoption. A conservative detector recognizes only bounded structural signatures — a `PROPOSED`/`RECOMMENDED FINDINGS AND ORDERS` title, a formal lead-in asking the court to make the following findings and orders, a split proposed-findings-then-proposed-orders template, or a proposal expressly asking the court to `find`/`order` — and marks the page with an in-text scope delimiter plus a `REPORT PROPOSAL EXCLUSION CONTEXT — FOR SCOPE ONLY` note, without deleting or rewriting any source text. When no structural marker is found, nothing is excluded and every page in the report range is summarized as before. Later windows after a marker carry a continuation note but are not automatically excluded, so a clearly separate factual attachment or embedded report is still summarized. A window with no eligible narrative returns the exact `NO_SUMMARIZABLE_REPORT_CONTENT` sentinel, which RecordPrep skips without emitting an empty report heading. The built-in report prompt asks for at least six legally significant verbatim quotes per window — each an uninterrupted two-to-five-word sequence from eligible material — whenever six suitable quotations exist, and otherwise every suitable quotation, distributed across material facts, observations, interviews, and assessments; it never permits invented, altered, insignificant, or out-of-scope quotations, and RecordPrep applies no deterministic validation or repair to the model’s paragraph. Source pages remain authoritative and unchanged throughout.

The hearing and report prompt editors contain the complete instructions actually sent as the system message; RecordPrep does not append a hidden “attribution contract.” Both prompts explain the optional preceding context page and the primary pages that must be summarized. Each page window produces one prose paragraph, and RecordPrep deterministically places one blank line between adjacent hearing or report paragraphs.

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
- `skills/recordprep-detect-transcript-layout/`
- `skills/recordprep-number-transcript-pages/`
- `skills/recordprep-build-participant-index/`
- `skills/recordprep-create-case-overview/`
- `skills/recordprep-build-source-map/`
- `scripts/run_recordprep_skill.py`

Each row launches one explicitly loaded Agent Skill in PI's native VTE UI. The runner accepts a structurally valid `needs_review` layout artifact, while RecordPrep treats only a resolved, fresh artifact as step completion. Only the final source-map stage updates the manifest (including the `transcript_layout` path). Skills validate outputs before the pipeline advances.

## Settings

Settings include source extraction, local OCR, classification/case inference, the Summarize API/prompts, summary-window character target and maximum page count, and PI command, model, and reasoning-level selection. The PI reasoning level is stored in the project `.pi/settings.json`; choosing the global default removes the project override. Retired artifact-pipeline credentials and prompts — including the old cross-case `rt_ct_split_page` key — are removed when local config is loaded or saved. The transcript expander offers automatic detection plus case-local manual overrides; a stale global value never populates a new case. The obsolete paragraph-count setting is not reinterpreted as a page count; adaptive defaults apply until the new settings are saved.

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
