# Application-owned classification

This is the current contract (Dependency **1.14.0**, content schema **11**, unchanged
`profile_api: 1`). It supersedes the editable-classification portions of
[structured classification](structured-classification.md), older settings reports
and schema-8 adoption notes. [Validation and limits](application-classification-validation.md).

## Ownership and reference

**App-owned Classification** opens only from the hamburger menu and works without
a case, selected profile, working profile store, model discovery or network.
It contains the full five RT definitions, ten CT definitions and five first-page
clue sets, with readable titles beside unchanged output keys. **View full prompts…**
shows the complete nine fixed task prompts: RT, CT, hearing/minute/form/report/motion
starts, and hearing/minute dates. It has search, selectable wrapped read-only text,
Copy and Close; fixed prompts have no template/current-draft switch. The page image
is a separate request attachment, not text added to the system prompt. Escape closes
the reference and prompt inspector. Opening/copying never saves or runs a model.

Profile settings has only **Document naming** (Report Names, Form Names and Motion Names)
and **Summaries** (hearing/report/motion digest topics). Minute instructions remain
application-owned, available only in full-prompt inspection. See [Motions](motions-workflow.md). Naming and summary
inspection still freezes the unsaved draft and offers its existing template/draft
views. Invalid naming does not affect application reference inspection. Save, kept
buffers/undo/selection, guarded revision publication, unsaved-close choices and the
confirmed Reset and Save boundary are retained. Reset affects profile settings,
not application definitions, model settings or case output. About classification
retains the pipeline explanation and progression, without the extra ownership/policy
paragraph, repeated catalog-entry hint or a link to App-owned Classification.

## Purpose, not a checklist

`recordprep/resources/classification/recognition-v1.json` is the single packaged
recognition resource. Definitions explain document purpose, identifying clues,
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
| CT_minute_order | Minute order — court/clerk record of proceedings and judicial action |
| CT_report | Court-directed report — authored information/assessment prepared for the court, including table/signature continuations |
| CT_form | Court form — recognizable standardized court forms, subject to the notice/service exclusions below |
| CT_certificate | Record certificate — distinct authentication/completeness of the record or copies |
| CT_motion | Motion / application — requested judicial action and recognizable support/argument |
| CT_notice | **Hearing notice** — primary purpose of notifying a party of a scheduled/continued/rescheduled hearing |
| CT_proof_of_service | Proof of service — distinct proof/dedicated page documenting delivery or attempted delivery |
| CT_other | Other CT material — remaining records/exhibits/correspondence/raw results and orders fitting no other definition |

No Basic key or first-page marker was added, removed or renamed. Advanced still
uses `first_page: yes/no` and the four existing `*_first_page` markers. It checks
all eligible report pages independently; unnamed and adjacent report starts still
end earlier ranges. JSON validation, exact-name rules, stage order and the fixed
hearing/minute date wording and date normalization are unchanged. Report naming
now permits contextual same-image header/footer identity evidence, without making
footers mandatory or allowing them to establish a start. Dependency 1.13.0 selects
agency-authored court-directed reports under one Child Welfare Agency Report card,
then extracts their own first-page titles using the practice-neutral Source title
naming approach. The category name is only the missing-title fallback. See [report naming](dependency-report-naming.md);
this catalog change never enters Basic or first-page prompts.

### Hearing notices, service proofs and other forms

A standardized hearing-notice form stays **CT_notice**. An integral service block
can remain part of its notice page. A distinct page devoted to proving service
stays **CT_proof_of_service**, including a standardized proof or a clerk's mailing
certificate in the same packet. Neither type enters form-start detection, form
naming or the Forms TOC. Old descriptive `name` fields on such pages are not an
eligibility grant and are not silently cleaned up.

A qualifying **Notice of Appeal** form remains **CT_form**: taking an appeal is not
notifying a party of a hearing. Other qualifying request/order/status/address forms
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

Basic hashes its RT/CT prompts; Advanced its four starts; Corrected both. Their
identity also includes the recognition contract and existing page-flow identity.
Dates hashes only its unchanged date prompts. Display titles do not change model
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
must explicitly run Basic and the desired downstream stages; this incurs new image
model work. Merely opening the reference, selecting/saving a profile, updating the
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
