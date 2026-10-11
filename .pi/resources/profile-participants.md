---
name: recordprep-build-participant-index
description: Build hearing-scoped participant and witness metadata with the application-selected role catalog.
---

# Participant review

The application has already prepared the private candidate and private worklist
named in the runtime prompt. Read those files. Edit only that candidate, never the
published participant index. Its schema-3 role catalog, provenance and fingerprints
are application metadata: never change them or invent role IDs. Shell access and
canonical publication are not available to the model.

Review one hearing at a time from original single source pages. Start with the
worklist's appearance/first pages, reporter-index pages, oath/examination markers,
and attendance/colloquy markers. Do not concatenate a complete transcript or a long
run. Unresolved identity, attendance, speaking, sworn or witness evidence stays
explicitly unknown. Counsel representation is not personal attendance. Q/A alone is
not testimony. Organizations are not attorney aliases. Verified witnesses need cited
examinations; conflicting evidence must remain explicit.

Persist completed hearings in the candidate with the write/edit tools. Call
`recordprep_validate_candidate` with `partial: true` after batches of at most five
hearings. Remove template-review warnings only after reviewing the relevant hearing.
Finish with `recordprep_validate_candidate` with `partial: false`. Correct structural
issues in the candidate rather than changing source material or weakening metadata.
Use the runtime's frozen application contract and role guidance. Only Python
publishes the validated candidate; source pages, boundaries, numbering and manifest
are read-only to this stage.
