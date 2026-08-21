---
name: recordprep-build-participant-index
description: Builds and validates hearing-scoped counsel, non-counsel participant, witness, and examination metadata from reporter-transcript indexes, appearances, attendance statements, colloquy, and sworn testimony. Use only for the RecordPrep participant-index stage.
---

# Build Participant Index

Create exactly `artifacts/participant_index.json` in `RECORDPREP_CASE_BUNDLE`. This is a private record artifact. Do not alter source pages, transcript numbering, boundaries, summaries, the manifest, or any other file.

## 1. Prepare the template and the evidence worklist

Run both helpers first:

```bash
python scripts/participant_index.py prepare "$RECORDPREP_CASE_BUNDLE"
python scripts/participant_index.py worklist "$RECORDPREP_CASE_BUNDLE"
```

`prepare` generates every hearing entry with citation mappings. `worklist` writes a **temporary, nonauthoritative evidence scope** at `$RECORDPREP_CASE_BUNDLE/temp/.participant_worklist.json` containing, per hearing:

- hearing ranges and the first/appearance pages;
- candidate `RT_index` pages scoped to the applicable reporter-transcript series;
- pages matching oath, sworn-witness, examination, attendance, absence, and appearance markers;
- citation labels and keys resolved from `artifacts/transcript_page_numbers.json`.

Read the worklist once. It is a pointer file only: **inspect the original source pages it references before making any finding**. Use its paths and citation metadata only to locate sources; evidence notes must describe the verified source page, not the worklist marker. Preserve every generated hearing entry and page/range field from the template.

## 2. Gather evidence one hearing at a time

Work strictly **one hearing at a time**, in worklist order. For each hearing:

1. Start with the worklist's first/appearance pages, then its marker pages and scoped `RT_index` pages for that hearing. Read those original pages.
2. Identify counsel by **party role**, not only name. Use these normalized role IDs where applicable: `mothers_counsel`, `fathers_counsel`, `alleged_fathers_counsel`, `presumed_fathers_counsel`, `parents_counsel`, `minors_counsel`, `county_counsel`, `tribes_counsel`, `guardian_ad_litem`, `other_counsel`, `unresolved_counsel`.
3. Identify non-counsel participants when the transcript expressly shows that they spoke, were present, appeared remotely, or were absent. Include parties, relatives, caregivers, social workers, agency representatives, judicial officers, and interpreters when supported. Do not infer a party's attendance merely because counsel appeared for that party. Routine clerks and reporters need not be listed unless they materially participate.
4. On the hearing's scoped `RT_index` pages, look for chronological witness indexes, witness names, examination type, examiner, and printed transcript page.
5. Resolve every printed transcript page through `artifacts/transcript_page_numbers.json`. Record the file page, citation label, citation key, and source text page as evidence.
6. Cross-check witness-index entries against the hearing text around each examination start. Search the hearing's own pages for sworn/oath language, `DIRECT EXAMINATION`, `CROSS-EXAMINATION`, examiner labels, and Q/A structure.
7. If the witness index is absent or unclear, investigate only the hearing's own pages for explicit swearing and examination evidence. Q/A formatting alone is never enough.
8. Use a page image only when OCR creates a material ambiguity. Record the text-page evidence either way.

Counsel aliases are hearing-scoped. An alias is an alternate personal name or transcript speaker label, such as `Matt McDonald` or `Mr. McDonald`; a law firm or agency abbreviation such as `JCA`, `CAG`, or `Clark & Le` belongs in `organization`, not `aliases`. Do not apply an attorney-role assignment from one hearing to another without evidence. Preserve names as printed and add only observed aliases. Never guess a role, identity, attendance, or speaking status.

### Bounded work rules (mandatory)

- Read at most one page file per `read` call (`text_pages/NNNN.txt`). **Never concatenate the complete RT, a complete hearing, or any multi-hundred-page run into one tool call.**
- Use `grep`, `find`, and `ls` over targeted page sets to locate evidence; do not load whole directories into context.
- Stay within the worklist's per-hearing page budget (at most 12 page reads per hearing, including the first/appearance pages).
- Prefer hearing-scoped pages. The worklist's scoped index pages and explicitly noted cross-references are the only sanctioned out-of-range sources.
- If the budget is exhausted or evidence stays ambiguous, record explicit `unknown` or `conflict` status with the evidence gathered so far and a hearing-specific warning. **Never stall while trying to eliminate uncertainty**; the record stays the authority and uncertainty stays explicit.

## 3. Persist incrementally and validate in bounded batches

- After completing each hearing, update `artifacts/participant_index.json` so every generated hearing entry is preserved and this hearing's `counsel`, `participants`, `witness_status`, `witness_evidence`, `witnesses`, and `warnings` reflect your findings.
- Remove the placeholder warning exactly as you review each hearing, from that hearing and from the top-level `warnings` list once the last hearing is done.
- After each batch of **up to 5 hearings**, and before finishing, validate the work persisted so far:

```bash
python scripts/participant_index.py validate --partial "$RECORDPREP_CASE_BUNDLE"
```

`--partial` fully validates every reviewed hearing while allowing not-yet-reviewed hearings to keep the placeholder. Fix every error before continuing to the next batch.

## 4. Populate the schema

Top level:

- `schema_version`: `2`
- `source`: `record-participant-index`
- `hearings`: generated hearing list
- `warnings`: concise unresolved/conflict warnings

Each hearing must retain `id`, `date`, `start_page`, `end_page`, `start_citation_label`, `end_citation_label`, and `citation_range`, and contain:

- `counsel`: list of `{role_id, role_label, name, aliases, organization, appearance_status, evidence}` where `appearance_status` is `present`, `remote`, or `unknown`
- `participants`: non-counsel participants supported by the hearing record
- `witness_status`: exactly `verified`, `none`, `unknown`, or `conflict`
- `witness_evidence`: hearing-level evidence supporting `none`, `unknown`, or a conflict
- `witnesses`: list of `{id, name, description, aliases, evidence, examinations}`
- `warnings`: list

Each participant is:

```json
{
  "id": "participant:hearing:0001:001",
  "role_id": "relative",
  "role_label": "Maternal great-aunt",
  "name": "Janette McKinley",
  "aliases": [],
  "attendance_status": "present",
  "speaking_status": "spoke",
  "sworn_status": "unsworn",
  "evidence": []
}
```

Allowed participant role IDs are `mother`, `father`, `alleged_father`, `presumed_father`, `minor`, `relative`, `caregiver`, `social_worker`, `agency_representative`, `judicial_officer`, `interpreter`, `audience_member`, `other_participant`, and `unresolved_participant`. Attendance is `present`, `remote`, `absent`, or `unknown`; speaking is `spoke`, `did_not_speak`, or `unknown`; sworn status is `sworn`, `unsworn`, `not_applicable`, or `unknown`.

Use `sworn_status: unsworn` for a person who addresses the court without an oath, and also retain a witness entry if that same participant later gives verified sworn testimony. Evidence must support each participant's identity/role and each non-unknown status. A role label may identify an unnamed person; do not invent a name.

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

An attorney who asks questions is the examiner, not the witness. Do not list counsel as a witness unless independent, explicit sworn-witness evidence establishes that unusual fact; flag it as a conflict for human review. An unsworn speaker remains a participant, not a witness.

## 5. Validate and clean up

Run the final full validation:

```bash
python scripts/participant_index.py validate "$RECORDPREP_CASE_BUNDLE"
```

Full validation **rejects the prepared template**: every hearing must be reviewed, or explicitly declared `unknown`/`conflict` with hearing-specific evidence and warnings. Fix every error. Warnings representing genuine record uncertainty may remain, but must also appear in the affected hearing. Finish only after full validation succeeds, then remove the temporary worklist:

```bash
python scripts/participant_index.py cleanup "$RECORDPREP_CASE_BUNDLE"
```
