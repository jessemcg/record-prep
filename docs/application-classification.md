# Application-owned classification

This is the current recognition-v5 contract (content schema **14**, unchanged
`profile_api: 1`; Dependency **1.19.0**, Criminal **1.1.0**). It supersedes the editable-classification portions of
[structured classification](structured-classification.md), older settings reports
and schema-8 adoption notes. [Historical validation](application-classification-validation.md) and
[recognition-v5 / dated-minute validation and limits](dated-minute-selection-validation.md).

## Ownership and maintenance

Classification is application-owned, with no hamburger-menu link, reference window
or dedicated classification prompt-inspector mode. Maintain definitions, first-page
clues and fixed date rules through source changes with the coding agent, not through
end-user settings. The page image remains a separate request attachment, not text
added to the system prompt. This UI removal does not change classification prompts,
fingerprints, validation, saved output or Resume, and requires no regeneration.

Profile settings has only **Document naming** (Report Names and Procedural Filing Names)
and **Summaries** (Report digest topics). Hearing and motion topics/naming are fixed
application methods. Motion and minute instructions remain
application-owned, available in the existing summary full-prompt inspection. See [Motions](motions-workflow.md). Naming and summary
inspection still freezes the unsaved draft and offers its existing template/draft
views. Save, kept
buffers/undo/selection, guarded revision publication, unsaved-close choices and the
confirmed Reset and Save boundary are retained. Reset affects profile settings,
not application definitions, model settings or case output. About classification
retains the pipeline explanation and progression, without the extra ownership/policy
paragraph, repeated catalog-entry hint or a classification-reference link.

See [Procedural filings](procedural-filings.md) for the function-first motion/form
boundary and compatibility. Recognition-v5 adds the minute/order distinction below;
see [minute selection](dated-minute-selection.md) for explicit adoption and limits.

## Purpose, not a checklist

`recordprep/resources/classification/recognition-v5.json` is the selected packaged
recognition resource (JSON schema 1). v1/v2/v3/v4 remain byte-preserved historical resources. Definitions explain document purpose, identifying clues,
continuations/endings, and important near neighbors. Clues are not compulsory
headings, codes, signatures, layouts or a decision cascade. Best fit compares the
whole taxonomy; no practice-specific name catalog or form-code allowlist determines
a page type. Each model request sees **one image**, not unseen adjacent pages.

| JSON key | Display title / function |
|---|---|
| RT_cover | Transcript cover — identifying front matter, including listed appearances |
| RT_index | Transcript index — navigational entries and references |
| RT_body | **Hearing body** — spoken proceedings, including continuous speech without fresh labels |
| RT_certificate | Transcript certificate — distinct transcript accuracy/preparation attestation |
| RT_other | Other RT material — genuinely different or unidentifiable material, not merely a sparse continuation |
| CT_cover | Transcript cover — collection/volume/section front matter, not a substantive document caption |
| CT_index | Document index — navigation through the record, not an embedded substantive table |
| CT_minute_order | Minute order — actual clerk/court minute record of a particular proceeding, not any document reciting orders |
| CT_report | Court-directed report — authored information/assessment prepared for the court, including table/signature continuations |
| CT_form | Procedural filings — bounded non-motion procedural instruments, standardized or custom-written |
| CT_certificate | Record certificate — distinct authentication/completeness of the record or copies |
| CT_motion | Motion / application — substantive requests within an existing proceeding, including standardized forms and status/participation requests, plus recognizable support/argument |
| CT_notice | **Hearing notice** — primary purpose of notifying a party of a scheduled/continued/rescheduled hearing |
| CT_proof_of_service | Proof of service — distinct proof/dedicated page documenting delivery or attempted delivery |
| CT_other | Other CT material — remaining records/exhibits/correspondence/raw results and orders fitting no other definition |

No Basic key or first-page marker was added, removed or renamed. Advanced still
uses `first_page: yes/no` and the five existing `*_first_page` markers. It checks
all eligible report pages independently; unnamed and adjacent report starts still
end earlier ranges. JSON validation, exact-name rules, stage order and the fixed
hearing-date wording and calendar normalization are unchanged. Minute-date rules
now reuse the frozen minute definition, accept identifying top-of-page hearing
fields, and reject unrelated filing/service/print/revision/reference/future dates.
Nonminutes and missing/conflicting/unreadable minute dates yield an empty string;
no neighbor borrowing or inference to make a candidate eligible. Report naming
now permits contextual same-image header/footer identity evidence, without making
footers mandatory or allowing them to establish a start. Dependency 1.13.0 selects
agency-authored court-directed reports under one Child Welfare Agency Report card,
then extracts their own first-page titles using the practice-neutral Source title
naming approach. The category name is only the missing-title fallback. See [report naming](dependency-report-naming.md);
this catalog change never enters Basic or first-page prompts.

### Actual minutes versus separate orders

A prominent Minute Order/minutes heading is strong evidence, not compulsory.
A recognizable hearing-record structure combining hearing identification, court
personnel, appearances/proceedings and recorded action can suffice without every
field or a particular county layout. Genuine continuations and integral endings
need not repeat the heading/date. Separate findings-and-orders templates and local
standardized order forms stay CT_form whether blank, proposed, signed or entered.
Standalone written orders outside that procedural-filing definition stay CT_other.
Dates/signatures, the court finds/orders language, adjacency or incorporation by
reference do not turn those documents into minutes. Incidental quotation in a
report, brief, index or service proof is not minute identity.

The first-minute task treats Basic as a hypothesis and requires an actual fresh
minute opening, not repeated headers, continuation findings or internal signature/
service sections. Answering no cannot repair a false underlying type: Agent
correction must change confirmed false minutes to their appropriate nonminute type,
not simply minute bodies that merge into a preceding range. Missing dates alone
never prove a type error. [New minute selections](dated-minute-selection.md) omit undated
candidates with counts/ranges while preserving every source and classification row.

### Bounded procedural instruments, including custom-written documents

CT_form includes criminal charging pleadings, plea/rights/counsel-waiver instruments,
verdict/special-finding sheets, written jury instructions/sets, written stipulations,
jury/juror communications and court responses, appellate notices/probable-cause
instruments and abstracts, whether standardized, custom-written or handwritten.
Other qualifying standardized forms remain eligible. No form code is mandatory.
Unused/unsigned verdicts are still documents, not evidence that a verdict was returned;
submitted instructions do not establish that they were given. Repeated titles,
new instruction numbers inside a packet and signature endings do not alone start a
new instrument. An integral probable-cause section of an appeal packet is not
automatically separate; independently identified instruments remain separate.

This is universal application recognition, not a Criminal-catalog lookup. It does
not redefine all pleadings/correspondence/exhibits as forms: motion advocacy, neutral
reports, investigative records, hearing notices, service proofs, actual minutes and
record-authentication certificates keep their own categories. A motion to amend an
information remains CT_motion; the amended information itself is CT_form. A distinct
written agreement is a stipulation, not advocacy merely because it is free-form.
See the [Criminal first draft](california-criminal-profile.md) for naming-only scope.

### Embedded transcripts stay inside the outer CT collection

Layout detection uses outer covers/indexes, clerk certification, pagination and
neighbors, not hearing dates or the word preliminary alone. An established CT
collection may enclose preliminary-hearing/interview transcripts, reporter covers,
certificates, internal indexes and Q/A pages. Those remain CT-side, normally CT_other,
without RT hearing starts; their front matter is not the outer CT cover/index.
CT-only stays CT-only despite verbatim proceedings. Standalone RT of a preliminary
hearing stays RT. Conflicting outer evidence, an uncertain boundary or genuinely
separate CT→RT/interleaved collections still require review; never swallow a distinct
RT volume based on an incidental CT reference. Preserve every source page. Numbering
uses supported outer CT citation pagination, not enclosed reporter or docket overlays;
unresolved values remain ambiguous/missing, not invented. No layout/schema/parser
heuristic or hearing-summary method is added.

### Hearing notices, service proofs and other forms

A standardized hearing-notice form stays **CT_notice**. An integral service block
can remain part of its notice page. A distinct page devoted to proving service
stays **CT_proof_of_service**, including a standardized proof or a clerk's mailing
certificate in the same packet. Neither type enters form-start detection, form
naming or the Forms TOC. Old descriptive `name` fields on such pages are not an
eligibility grant and are not silently cleaned up.

An actual **Notice of Appeal** remains **CT_form**, even when custom-written:
taking an appeal is not notifying a party of a hearing. A notice merely announcing
its filing or transcript preparation does not itself initiate appellate review. Other qualifying request/order/status/address forms
also remain forms. A clerk's distinct record-authentication certificate is different
from a mailing certificate; an integral minute-order attestation/mailing ending need
not detach into either. Court-directed reports are distinguished from underlying
operational records, raw logs/results and separately reproduced exhibits. A motion's
requested relief or a report's recommendation is not an actual judicial minute order.

See [read-only review and authored examples](classification-review.md). These rules
are generalized from structural distinctions, not private case facts or historical
labels treated as ground truth.

## Builders, contracts and freshness

`recognition_contract.load_recognition` reads bounded strict UTF-8 JSON, rejects
duplicates/unknown or missing keys, unsupported schema/identity, empty or oversized
text, and freezes canonical-order tuples. Missing or invalid installation resources
fail explicitly before model work, with **no profile/config fallback**.

`classifier_document` is shared by runtime, preview, inspection and fingerprints.
A stage freezes its recognition contract once and attaches that same object plus
an explicit task identity to every worker request. Legacy `classifier_*` and
`advanced_classify_*` prompt values and schema-1–8 `classification_tasks` data are
inert, even if custom. Ordinary Model settings saves preserve existing retired
values/absence; they never recreate those keys. Legacy initialization imports no
classification/start/date/caption prose. Naming catalogs, summary topics and minute
guidance keep their existing profile ownership and compatibility formats.

Basic hashes its RT/CT prompts; Advanced its five starts; Corrected both. Their
identity also includes the recognition contract and existing page-flow identity.
Dates hashes its actual date prompts: hearing bytes are unchanged; minute bytes
change with the new rules and frozen minute definition. Display titles do not change model
bytes/freshness. Catalog changes affect Names, not Basic or start detection; source
or actual upstream-file changes still invalidate the dependent run honestly.

Structural runs, **including unassigned runs**, stage privately under
`.recordprep/profile-work/`. Canonical rows are checkpoint inputs only when their
metadata matches the effective contract/model/source/upstream identity. Old output
is never deleted to force new work. Publication verifies complete page retention,
current selection (including null), current resource/prompt/model identity, source
inventory and actual upstream bytes, using the existing serialized publication
boundary. Stop/error leaves old canonical output and private resumable work intact.
Checkpoint directories are case-local, not private XDG profile storage: existing
owner-controlled 0755/0775 synchronized modes are accepted without changing modes
or saved checkpoints. New directories still start at 0700. Ownership, no-symlink
ancestor traversal and no-world-write checks remain enforced at every checkpoint
level; machine-local profile stores retain their stricter owner-only policy.
Unassigned legacy naming remains its separate compatibility path.

## Historical data and explicit work

Schemas **1–8** and stored bytes remain readable. Schema 9 omits the
`classification_tasks` manifest entry/file and continues to support naming v1–v4;
unknown naming prose is not guessed into cards. Explicit create/save projects a
**new** schema-9 draft/revision. Existing accepted revisions, real configuration,
case pins and historical JSONL are never migrated, repaired or overwritten by this
change. `profile_contract.py` is mirrored byte-identically in Focus; Focus gains no
classification UI/runtime or profile instruction authority. `profile_artifacts.py`
and all existing artifact formats remain unchanged.

Badges and Resume remain **output-presence based**. Existing classifications and
TOCs remain as saved. To adopt the new definitions for an existing bundle, the user
must explicitly run **Basic → Advanced → Dates → Names → Agent correction** and
rebuild affected downstream outputs; this incurs new image-model work. A wrong outer
layout requires a separate safe bundle/recovery workflow, never a forced protected
split change or reset of the original. Merely selecting/saving a profile, updating the
application, or resuming does not reclassify, remove historical named forms or
rebuild a TOC. No automatic regeneration or saved-output cleanup is performed.

That Basic adoption advice concerns changed **structural definitions**, not report
catalog edits. For the 1.10.0 report-card update, saved personal profiles explicitly
adopt desired cards in Profile settings and Save; updating the bundle never replaces
them. Reset to bundled resets **all** profile guidance, including custom summary
topics. With complete report-start checks, explicitly run Names and desired downstream
TOC/boundary/summary stages. Without them, run Advanced → Corrected → Dates → Names
first. Basic is only for deliberate upstream reclassification. Model reruns can
incur charges; presence-based badges/Resume do not automatically rerun anything.
