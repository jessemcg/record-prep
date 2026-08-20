---
name: recordprep-build-source-map
description: Build and validate direct-source artifacts/source_map.json schema v2 for the RecordPrep case bundle named by RECORDPREP_CASE_BUNDLE after transcript layout detection, transcript numbering, participant indexing, source summaries, and the concise case overview complete. Use only as the final Agent Search stage.
---

# Build RecordPrep Source Map

Use `RECORDPREP_CASE_BUNDLE`. This stage must run only after transcript layout
detection, transcript numbering, participant indexing, direct source-page
summaries, and the case-overview skill succeed.

Require:

- `manifest.json`
- `text_pages/NNNN.txt`
- `artifacts/transcript_layout.json` using schema version 1, resolved with a declared mode
- `artifacts/transcript_page_numbers.json` using schema version 2 or newer
- `artifacts/transcript_page_number_series.md`
- `artifacts/participant_index.json` using schema version 2
- hearing, report, and minute boundary JSON
- the source hearing summary
- the source reports summary
- `artifacts/case_overview.md` using case-overview schema version 1

Run from the staged project workspace:

```bash
python3 .pi/skills/recordprep-build-source-map/scripts/build_source_map.py \
  "$RECORDPREP_CASE_BUNDLE"
```

Resolve the script from the staged project `.pi` directory; do not use a global
Codex skill path.

The script is the only workflow stage allowed to update `manifest.json`. It
atomically writes `artifacts/source_map.json`, then atomically publishes:

- `files.transcript_layout`
- `files.transcript_page_numbers`
- `files.transcript_page_number_series`
- `files.participant_index`
- `files.case_overview`
- `files.summarized_hearings`
- `files.summarized_reports`
- `files.source_map`

It also upgrades the manifest to schema version 2, publishes the canonical
`artifacts/case_overview.md` path, removes legacy optimization, chunk,
vector-path, and organized-summary entries, and deletes legacy
`summaries/*_organized.txt` derivatives. The source map must build document
ranges directly from boundaries and `text_pages`, embed normalized counsel,
non-counsel participant,
witness, and examination metadata, and contain only case-root-relative paths.

Verify page counts against `text_pages`, direct document ranges, participant
page annotations, a nonempty citation-series list when record citations were
selected, valid lookup references, the resolved transcript-layout path, the
versioned nonauthoritative overview path, and freshness relative to every
prerequisite. Report the output path,
page/document/series counts, and warnings. Fail on missing prerequisites or invalid JSON rather than producing a
non-citation-aware map.
