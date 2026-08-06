---
name: recordprep-build-participant-index
description: Builds and validates hearing-scoped counsel, witness, and examination metadata from reporter-transcript indexes, appearances, and sworn testimony. Use only for the RecordPrep participant-index stage.
---

# Build Participant Index

Create exactly `artifacts/participant_index.json` in `RECORDPREP_CASE_BUNDLE`. This is a private record artifact. Do not alter source pages, transcript numbering, boundaries, summaries, or any other file.

## 1. Prepare the template

Run:

```bash
python scripts/participant_index.py prepare "$RECORDPREP_CASE_BUNDLE"
```

Read the generated template. It contains every hearing, citation mappings, and candidate `RT_index` pages. Preserve every hearing entry and all generated page/range fields.

## 2. Gather evidence conservatively

For each hearing:

1. Read nearby appearance pages and identify counsel by **party role**, not only name. Use these normalized role IDs where applicable: `mothers_counsel`, `fathers_counsel`, `alleged_fathers_counsel`, `presumed_fathers_counsel`, `parents_counsel`, `minors_counsel`, `county_counsel`, `tribes_counsel`, `guardian_ad_litem`, `other_counsel`, `unresolved_counsel`.
2. Read relevant `RT_index` pages. Look for chronological witness indexes, witness names, examination type, examiner, and printed transcript page.
3. Resolve every printed transcript page through `artifacts/transcript_page_numbers.json`. Record the file page, citation label, citation key, and source text page as evidence.
4. Cross-check witness-index entries against the hearing text around each examination start. Search for sworn/oath language, `DIRECT EXAMINATION`, `CROSS-EXAMINATION`, examiner labels, and Q/A structure.
5. If the witness index is absent or unclear, search the actual hearing for explicit swearing and examination evidence. Q/A formatting alone is never enough.
6. Use a page image only when OCR creates a material ambiguity. Record the text-page evidence either way.

Counsel aliases are hearing-scoped. Do not apply an attorney-role assignment from one hearing to another without evidence. Preserve names as printed and add only observed aliases. Never guess a role.

## 3. Populate the schema

Top level:

- `schema_version`: `1`
- `source`: `record-participant-index`
- `hearings`: generated hearing list
- `warnings`: concise unresolved/conflict warnings

Each hearing must retain `id`, `date`, `start_page`, `end_page`, `start_citation_label`, `end_citation_label`, and `citation_range`, and contain:

- `counsel`: list of `{role_id, role_label, name, aliases, evidence}`
- `witness_status`: exactly `verified`, `none`, `unknown`, or `conflict`
- `witness_evidence`: hearing-level evidence supporting `none`, `unknown`, or a conflict
- `witnesses`: list of `{id, name, description, aliases, evidence, examinations}`
- `warnings`: list

Each evidence object is `{text_path, file_page, citation_label, citation_key, note}`.

Each examination is:

```json
{
  "type": "direct|cross|redirect|recross|court|continued|other",
  "examiner_name": "",
  "examiner_role_id": "",
  "start_printed_page": 0,
  "end_printed_page": 0,
  "start_file_page": 0,
  "end_file_page": 0,
  "start_citation_label": "",
  "end_citation_label": "",
  "evidence": []
}
```

Use `0` and empty strings only when a value genuinely cannot be resolved, and add a warning. Examination ranges must remain inside the hearing. Infer an end from the next verified examination start or hearing end only when that inference is unambiguous, and say so in evidence notes.

Set status as follows:

- `none`: an explicit no-witness index (or equivalent reliable evidence) and no contrary sworn-examination evidence. Put that evidence in `witness_evidence`; `none` without evidence is invalid.
- `verified`: a usable witness index or explicit sworn/examination evidence supports every listed witness.
- `unknown`: testimony cannot be established. Keep `witnesses` empty.
- `conflict`: index and transcript evidence materially disagree. Preserve the supported entries and explain the conflict.

An attorney who asks questions is the examiner, not the witness. Do not list counsel as a witness unless independent, explicit sworn-witness evidence establishes that unusual fact; flag it as a conflict for human review.

## 4. Validate

Run:

```bash
python scripts/participant_index.py validate "$RECORDPREP_CASE_BUNDLE"
```

Fix every error. Warnings representing genuine record uncertainty may remain, but must also appear in the affected hearing. Finish only after validation succeeds.
