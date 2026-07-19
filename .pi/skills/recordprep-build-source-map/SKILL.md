---
name: recordprep-build-source-map
description: Build and validate artifacts/source_map.json for the RecordPrep case bundle named by RECORDPREP_CASE_BUNDLE after transcript numbering and both organized summaries have completed. Use only as the final Agent Refinement step.
---

# Build RecordPrep Source Map

Use `RECORDPREP_CASE_BUNDLE`. This stage must run only after the transcript-page,
hearing-summary, and report-summary skills all succeed.

Require:

- `manifest.json`
- `text_pages/NNNN.txt`
- `artifacts/transcript_page_numbers.json` using schema version 2 or newer
- `artifacts/transcript_page_number_series.md`
- the organized hearing summary
- the organized reports summary

Run from the staged project workspace:

```bash
python3 .pi/skills/recordprep-build-source-map/scripts/build_source_map.py \
  "$RECORDPREP_CASE_BUNDLE"
```

Resolve the script from the staged project `.pi` directory; do not use a global
Codex skill path.

The script is the only workflow stage allowed to update `manifest.json`. It
atomically writes `artifacts/source_map.json`, then atomically publishes:

- `files.transcript_page_numbers`
- `files.transcript_page_number_series`
- `files.organized_hearings`
- `files.organized_reports`
- `files.source_map`

Verify page counts against `text_pages`, a nonempty citation-series list when
record citations were selected, valid lookup references, and freshness relative
to every prerequisite. Report the output path, page/document/series counts, and
warnings. Fail on missing prerequisites or invalid JSON rather than producing a
non-citation-aware map.
