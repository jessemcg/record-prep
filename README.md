# RecordPrep

RecordPrep is a GTK4/Libadwaita desktop pipeline that converts OCR-readable legal-record PDFs into a citation-aware case bundle for Focus. It preserves original page text/images, classifies pages, finds document boundaries, numbers official transcript pages, verifies counsel and witnesses, creates detailed summaries from source pages, and publishes source-map v2 for PI Agent search.

RecordPrep does not create retrieval chunks, speaker-labeled transcript rewrites, embeddings, Chroma stores, vector databases, or a case-overview retrieval artifact.

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
12. **Organize hearing summary** — PI preserves every unique summary-window sentence without adding an appearance roster or testimony-status boilerplate.
13. **Organize report summary** — PI organizes sourced report-summary sentences without rewriting them.

Summary inputs are bounded **ephemeral windows** (default: 15 primary source pages, with an additional input-size cap). The preceding page may be sent as context-only. Every primary window is summarized independently; no final compression pass discards unique detail, and no window text or metadata is written to disk.

Hearing requests privately repeat validated counsel/participant/examination context. Summary prose uses that metadata only for accurate attribution: it identifies counsel by party role when describing a material act, reserves “testified” for mapped witnesses within verified examinations, and describes unsworn colloquy as stated/answered/confirmed/advised. It does not publish a counsel/participant roster or a standalone statement about whether testimony occurred. Known-bad attribution causes retry and then a specific step failure rather than publication.

### Agent Search

14. **Build source map** — publish `artifacts/source_map.json` schema v2 and update `manifest.json`.

Source-map v2 builds document ranges directly from boundaries and `text_pages`. It includes official citation lookups, hearing/date ranges, counsel names/roles/aliases, witnesses/examinations, per-page context, and attribution warnings. Summary paths are nonauthoritative leads; source pages remain the evidence.

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
    source_map.json
  summaries/
    hearings_sum_<case>.txt
    hearings_sum_<case>_organized.txt
    reports_sum_<case>.txt
    reports_sum_<case>_organized.txt
    minutes_sum_<case>.txt
  temp/
```

When a selected bundle is rerun, RecordPrep removes only known obsolete generated paths from the retired artifact pipeline. It does not scan or mutate unrelated case bundles.

## PI stages

Tracked PI resources live under `.pi/`:

- `SYSTEM.md`
- `settings.json`
- `extensions/recordprep-auto-exit.ts`
- `skills/recordprep-number-transcript-pages/`
- `skills/recordprep-build-participant-index/`
- `skills/recordprep-organize-hearing-summary/`
- `skills/recordprep-organize-report-summary/`
- `skills/recordprep-build-source-map/`
- `scripts/run_recordprep_skill.py`

Each row launches one explicitly loaded Agent Skill in PI's native VTE UI. Only the final source-map stage updates the manifest. Skills validate outputs before the pipeline advances.

## Settings

Settings include source extraction, local OCR, classification/case inference, the Summarize API/prompts, 15-page summary-window preference, and PI command/model selection. Retired artifact-pipeline credentials and prompts are removed when local config is loaded or saved. The old summary paragraph-count preference migrates to `summarize_window_pages`.

Saved run-until targets migrate as follows:

- retired raw/transform stages → `create_summaries`
- retired overview/vector stages → `build_source_map`

## Validation

```bash
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
```

Validate each new/changed Agent Skill with the Agent Skill validator. Keep real case material, local credentials, and generated case bundles out of Git.
