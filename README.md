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
2. **Strip characters** — remove nonprinting extraction artifacts.
3. **Infer case** — write `case_name.txt`.

### Classify and organize

4. Classify RT/CT pages.
5. Add advanced first/last markers, dates, report/form names, and corrections.
6. Build/correct the TOC.
7. Find/correct hearing, report, and minute-order boundaries.

### Record context

8. **Number transcript pages** — PI writes official citation mappings and citation-series metadata.
9. **Build participant and witness index** — PI inspects appearances, express attendance or absence, unsworn colloquy, `RT_index` witness/examination pages, and actual sworn/examination evidence and writes schema-v2 `artifacts/participant_index.json`.

Counsel, non-counsel participants, and witnesses are separate hearing-scoped records. Law firms and agency abbreviations are stored as organizations rather than attorney aliases. Witness status is explicit: `verified`, `none`, `unknown`, or `conflict`; Q/A formatting alone never establishes testimony.

### Summarize

10. **Create summaries** — the configured Summarize API reads boundary-scoped source pages directly.
11. **Add links** — add hearing/minute page links.

Summary inputs are adaptive, page-aligned **ephemeral windows**. RecordPrep adds complete source pages toward a 6,000-character target, stops at six primary pages or the 12,000-character safety limit, and prefers a break before a mapped witness examination. A single oversized page remains intact. The preceding page may be sent as context-only. Every primary page is summarized exactly once; no final compression pass discards unique detail, and no window text or metadata is written to disk.

Hearing requests privately repeat validated counsel/participant/examination context under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY`. The complete hearing prompt explains that this metadata comes from the earlier participant-index stage, is supplied only for attribution, and does not replace the transcript as the factual source. The prompt asks the summarization model to identify counsel by party role, distinguish sworn testimony from unsworn colloquy, and avoid publishing rosters or standalone testimony-status statements.

RecordPrep accepts the summarization model’s paragraph without deterministic attribution validation, rejection, or model-repair requests. Summaries are nonauthoritative orientation aids; verify material facts and attribution against the source pages.

The hearing and report prompt editors contain the complete instructions actually sent as the system message; RecordPrep does not append a hidden “attribution contract.” Both prompts explain the optional preceding context page and the primary pages that must be summarized. Each page window produces one prose paragraph, and RecordPrep deterministically places one blank line between adjacent hearing or report paragraphs.

### Agent Search

12. **Create case overview** — PI writes the concise schema-v1 `artifacts/case_overview.md` orientation aid from the source summaries and participant metadata.
13. **Build source map** — publish `artifacts/source_map.json` schema v2 and update `manifest.json`.

The case overview supplies parties, procedural posture, key events, principal issues, and record scope so a Focus Agent can orient before inspecting structural metadata. It is explicitly nonauthoritative, is freshness-checked against its inputs, and cannot support a final factual claim or citation.

Source-map v2 builds document ranges directly from boundaries and `text_pages`. It includes the canonical case-overview path, official citation lookups, hearing/date ranges, counsel names/roles/aliases, witnesses/examinations, per-page context, and attribution warnings. Summary and overview paths are nonauthoritative leads; source pages remain the evidence.

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
  temp/
```

When a selected bundle is rerun, RecordPrep removes only known obsolete generated paths from retired pipelines, including legacy `_organized` summaries. It does not scan or mutate unrelated case bundles.

## PI stages

Tracked PI resources live under `.pi/`:

- `SYSTEM.md`
- `settings.json`
- `extensions/recordprep-auto-exit.ts`
- `skills/recordprep-number-transcript-pages/`
- `skills/recordprep-build-participant-index/`
- `skills/recordprep-create-case-overview/`
- `skills/recordprep-build-source-map/`
- `scripts/run_recordprep_skill.py`

Each row launches one explicitly loaded Agent Skill in PI's native VTE UI. Only the final source-map stage updates the manifest. Skills validate outputs before the pipeline advances.

## Settings

Settings include source extraction, local OCR, classification/case inference, the Summarize API/prompts, summary-window character target and maximum page count, and PI command/model selection. Retired artifact-pipeline credentials and prompts are removed when local config is loaded or saved. The obsolete paragraph-count setting is not reinterpreted as a page count; adaptive defaults apply until the new settings are saved.

Saved run-until targets migrate as follows:

- retired raw/transform stages → `create_summaries`
- retired overview stage → `create_case_overview`
- retired vector stage → `build_source_map`

## Validation

```bash
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
```

Validate each new/changed Agent Skill with the Agent Skill validator. Keep real case material, local credentials, and generated case bundles out of Git.
