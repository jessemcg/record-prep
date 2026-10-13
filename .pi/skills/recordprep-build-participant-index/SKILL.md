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
2. Identify counsel by name and source-supported role description (`role_label`), recording whom they represent in `represents` (empty if unknown). There is no role catalog or `role_id`. Use the same general method in every area of law; do not assume party alignment, family relationships or legal status.
3. Identify all non-counsel participants established as speaking, present, remote, or expressly absent, including parties, judicial officers, interpreters, staff and other people. A person merely mentioned is not thereby a participant. Do not infer attendance from counsel representation or absence from an omitted name. An unnamed participant may have an empty name, an observed speaker label in aliases and a source-supported role description (or `Unknown`).
4. On the hearing's scoped `RT_index` pages, look for chronological witness indexes, witness names, examination type, examiner, and printed transcript page.
5. Resolve every printed transcript page through `artifacts/transcript_page_numbers.json`. Record the file page, citation label, citation key, and source text page as evidence.
6. Cross-check witness-index entries against the hearing text around each examination start. Search the hearing's own pages for sworn/oath language, `DIRECT EXAMINATION`, `CROSS-EXAMINATION`, examiner labels, and Q/A structure.
7. If the witness index is absent or unclear, investigate only the hearing's own pages for explicit swearing and examination evidence. Q/A formatting alone is never enough.
8. Use a page image only when OCR creates a material ambiguity. Record the text-page evidence either way.

Counsel aliases are hearing-scoped. An alias is an alternate personal name or transcript speaker label, such as `Alex Smith` or `Ms. Smith`; a law firm or agency abbreviation belongs in `organization`, not `aliases`. Do not apply an attorney-role assignment from one hearing to another without evidence. Preserve names as printed and add only observed aliases. Never guess a role, identity, attendance, or speaking status.

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

- `schema_version`: `4` (legacy schemas 2/3 remain readable; never generate their role catalogs)
- `source`: `record-participant-index`
- `hearings`: generated hearing list
- `warnings`: concise unresolved/conflict warnings

Each hearing must retain `id`, `date`, `start_page`, `end_page`, `start_citation_label`, `end_citation_label`, and `citation_range`, and contain:

- `counsel`: list of `{role_label, represents, name, aliases, organization, appearance_status, speaking_status, sworn_status, evidence}` where `appearance_status` is `present`, `remote`, `absent`, or `unknown`. Use short source-supported role/representation descriptions, not category IDs.
- `participants`: non-counsel participants supported by the hearing record
- `witness_status`: exactly `verified`, `none`, `unknown`, or `conflict`
- `witness_evidence`: hearing-level evidence supporting `none`, `unknown`, or a conflict
- `witnesses`: list of `{id, name, description, aliases, evidence, examinations}`
- `warnings`: list

Each participant is:

```json
{
  "id": "participant:hearing:0001:001",
  "role_label": "Interpreter",
  "name": "Alex Smith",
  "aliases": [],
  "attendance_status": "present",
  "speaking_status": "spoke",
  "sworn_status": "unsworn",
  "evidence": []
}
```

Role labels are short descriptive source data (maximum 512 characters); there are no role IDs. Attendance is `present`, `remote`, `absent`, or `unknown`; speaking is `spoke`, `did_not_speak`, or `unknown`; sworn status is `sworn`, `unsworn`, `not_applicable`, or `unknown`. The speaking/sworn statuses apply to counsel too. Lack of speech in sampled pages alone does not establish did_not_speak. Preserve mixed sworn/unsworn participation in evidence notes and examination mappings rather than inventing a single certain status.

Use `sworn_status: unsworn` for a person who addresses the court without an oath, and also retain a witness entry if that same participant later gives verified sworn testimony. Evidence must support each participant's identity/role and each non-unknown status. A role label may identify an unnamed person; do not invent a name.

Each evidence object is `{text_path, file_page, citation_label, citation_key, note}`.

Each examination is:

```json
{
  "type": "direct|cross|redirect|recross|court|continued|other",
  "examiner_name": "",
  "examiner_role_label": "",
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
