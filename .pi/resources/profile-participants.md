---
name: recordprep-build-participant-index
description: Build general hearing-scoped participant, counsel, witness and examination metadata from original transcript evidence, without practice-specific roles or settings.
---

# Participant review

The application has prepared the private candidate and worklist named in the
runtime prompt. Read them. Edit only the candidate, never the published index.
Preserve schema version 4, provenance, fingerprints and generated hearing identities,
dates, ranges and citations. Shell access and canonical publication are unavailable.
No profile supplies identification instructions or a role catalog.

## Review each hearing

Work one hearing at a time, starting with worklist first/appearance pages, scoped
reporter-index pages and oath/examination/attendance/colloquy markers. Read original
single source pages, not concatenated transcripts. Respect the worklist's page-read
budget; if evidence remains unresolved, preserve unknown/conflict and a hearing
warning rather than stalling. A worklist marker is a lead, never evidence.

Identify everyone the transcript establishes was present, appeared remotely or
spoke: attorneys, parties, judicial officers, witnesses, interpreters, staff and
other participants, regardless of practice area. Preserve express nonappearances
as well. A person merely mentioned in argument is not thereby a participant.
Record roles and relationships as described by the source, not predefined categories.
Do not infer legal status, family relationships or party alignment from names.
An unnamed speaker may be indexed with an empty name and a supported speaker label
in aliases; describe an unresolved role as "Unknown". Do not fabricate identity.

For counsel, record whom they represent when stated, separately from personal
attendance. Representation proves neither the client's presence nor absence.
An omitted name proves neither. Distinguish speaking from sworn testimony and
in-person from expressly remote participation. Lack of speech in sampled pages
alone does not establish did_not_speak. Organizations are not personal aliases.
Keep roles/aliases hearing-scoped; do not borrow assignments from another hearing.

Cross-check witness indexes against oath/examination evidence in the hearing.
Q/A formatting alone is not testimony. An attorney asking questions is the examiner,
not the witness. Independent sworn evidence is required for counsel as a witness;
record that unusual situation as conflict for review. A participant who also gives
verified testimony may have both participant and witness entries.

## Schema 4 entries

Preserve each hearing's counsel, participants, witnesses, witness_status,
witness_evidence and warnings arrays/fields. There are no role_id, examiner_role_id
or role_catalog fields. Role descriptions are short source-supported data, never
instructions, and may differ for different people in the same hearing.

- Counsel: `{name, role_label, represents, aliases, organization, appearance_status,
  speaking_status, sworn_status, evidence}`. Use empty represents/organization when
  unknown. role_label may be "Counsel for claimant", or "Counsel — client unknown".
- Other participants: `{id, name, role_label, aliases, attendance_status,
  speaking_status, sworn_status, evidence}`. Use a unique hearing-local id.
- Attendance/appearance: present, remote, absent or unknown.
- Speaking: spoke, did_not_speak or unknown.
- Sworn: sworn, unsworn, not_applicable or unknown. Do not resolve conflicting
  sworn/unsworn participation to a false single status; retain the distinction in
  evidence notes and mapped examinations.
- Witness: `{id, name, description, aliases, evidence, examinations}`. Each witness
  requires a resolved name or explicit source speaker designation and examinations.
- Examination: `{type, examiner_name, examiner_role_label, start_printed_page,
  end_printed_page, start_file_page, end_file_page, start_citation_label,
  end_citation_label, evidence}`. Type: direct, cross, redirect, recross, court,
  continued or other. Examiner role is descriptive text (empty if unresolved).
- Evidence: `{text_path, file_page, citation_label, citation_key, note}`. Cite original
  text_pages paths and resolved numbering. Notes describe evidence, not worklist hits.

Counsel/participant evidence must support identity/role and each non-unknown status.
Examinations stay within the hearing and in source order. Use 0/empty fields only
for unresolved values, with a warning. Infer an examination end from the next
verified start or hearing end only if unambiguous; explain that inference.

Witness status: verified requires supported witnesses/examinations; none requires
explicit no-witness or equivalent reliable evidence in witness_evidence; unknown
keeps witnesses empty; conflict preserves supported entries and explains disagreement
in hearing warnings. Absence of an index alone never establishes no testimony.

## Validate and finish

Persist each completed hearing with write/edit. Remove its template-review warning
only after review; remove the top-level placeholder after all hearings are reviewed.
Call recordprep_validate_candidate with partial: true after at most five hearings,
then partial: false before finishing. Correct structural errors without changing
sources or metadata. Real uncertainty remains explicit. Only Python publishes the
validated candidate. Boundaries, numbering, summaries and manifest are read-only.
