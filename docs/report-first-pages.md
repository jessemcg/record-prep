# Independent report starts and naming-only catalogs

This authorized follow-up supersedes the earlier shared-CT-catalog/report-run
behavior. Dependency **1.8.0**, manifest schema **8**, classification resource **3**,
naming resource **4**, `profile_api: 1`. Focus receives the byte-identical shared
reader/validator update plus one category mapping: `CT_report_first_page` is the
existing Report category, not unknown. No new UI/category or research prompts.

## Pipeline and cost

1. **Basic:** structural CT report/form recognition, without approved-name catalogs.
   A report can be recognizable even without an approved output name. Report codes
   `CFS 6.7` / `DCFS 4216` are supporting clues, not names. The bundled report card
   no longer requires a matching footer or excludes `Page X of XX` by itself.
   Best-fit comparison and existing Basic output taxonomy remain unchanged.
2. **Advanced:** an independent `first_report` vision check on **every CT_report
   page**, just as form detection checks each form page. A positive answer produces
   `page_type: CT_report_first_page`; a negative keeps `CT_report`. Both outcomes
   persist `report_first_page: "yes"/"no"`, proving the check actually occurred.
   A repeated report name in a footer/header alone does not establish a start.
3. **Corrected/Dates:** preserve report-start markers and checks. Consecutive report
   starts are not collapsed; these can be genuine single-page/adjacent documents.
   Hearing/minute date extraction is unchanged.
4. **Names:** extract report name/date from each marked report first page and form
   name from each marked form first page. The existing evidence, exact-name, JSON,
   date and empty-name validators are unchanged. Report name/date fields inherited
   from the old run-start heuristic or continuation rows do not become accepted
   results of a new naming attempt.
5. **TOC/Boundaries:** only accepted nonempty names get report navigation or standalone
   summary work. **Every detected report start ends the previous range**, including
   an unnamed start. Gaps and other structural types also end ranges. Leading or
   post-gap report bodies without a detected start are unnamed fragments, not
   inferred starts. Source pages, images and classification rows are retained.

For N report pages and S detected starts, a fresh Advanced/Names run makes N
report-start vision calls and S naming calls (plus existing work for other types).
This is an explicit cost increase over naming only contiguous-run starts. Resuming
an identical fully checked workspace does not repeat those successful checks.
No real-provider calls were made to validate this implementation.

Examples:

| Classified report starts | Accepted names | Published report ranges |
| --- | --- | --- |
| A at 1, B at 3, next document at 5 | A only | 1–2; never 1–4 |
| A at 1, B at 3, end at 4 | B only | 3–4; B is not hidden by unnamed A |
| A at 1, B at 2 | Both, even same name/date | Two one-page ranges |
| Report bodies 1–2, A at 3 | A only | A starts at 3; bodies 1–2 remain source-only |

Basic's former one-page report-gap smoothing is removed. A form, minute order or
other separator between reports must not be converted to a report. Classifier
mistakes still need review: a missed internal start can merge material; a false
positive can split a document. Synthetic routing tests cannot prove real vision
recognition accuracy. There is no automatic inference from allowed names to hide
that uncertainty, and no fallback label or invented report title.

## Settings and prompt inspection

**First pages** has four retained cards: Hearing, Minute-order, Form and **Report**.
The new card's output identity is fixed. Its recognition clues are editable;
Save/Reset/navigation preserve retained buffers and undo using existing guards.
The five flat destinations remain unchanged.

**Report Names** / **Form Names** now supply naming only. No automatic catalog
injection, read-only catalog previews or Edit-name links remain on CT cards.
Catalog name/description edits affect **Names only**; report-start clue edits affect
Advanced and Corrected. Actual upstream bytes still affect downstream workspaces.

Runtime and inspector use the same pure `classifier_document` builder. The report
first-page task appears in Template and With current draft modes. Inspection keeps
one **System message** heading and separate image-attachment metadata, not branded
Contract framing. Report/form extraction instructions and all summary instructions
remain byte-identical to the preceding plain-naming refinement.

## Historical compatibility and explicit application

- Schemas 1–7, original naming formats, immutable snapshots and all original public
  baseline/initial adapter files remain readable and unchanged.
- Only exact complete known public resources adapt read-only. The reviewed 1.7.0
  shared-catalog input is frozen separately, and the new equivalent lives under
  `resources/profile_baselines/dependency-1.8.0/classification-v3.json`.
- Unknown custom CT/footer/name prose stays literal. Removing automatic catalog
  injection does **not** silently remove a user's own old name list/restrictions.
  Such descriptions must be reviewed/edited, or explicitly Reset to bundled, if
  the user wants the new structural recognition wording.
- Old profiles lacking `first_report` use fixed application clues at runtime.
  Explicit editing adds the new field to the draft. Flat custom task prose uses
  classification-v3's lossless compatibility representation: the original seven
  strings (including inert dates), `schema_version: 3`, and `first_report`. No
  heuristic splitting, cleanup or private snapshot rewriting occurs.
- Untouched classified output with no report checks retains historical contiguous-
  report-run reading behavior in TOC/Boundaries. Mixed/inconsistent checks fail
  before publication. This is selected from actual stored data, not guessed from
  the current profile or a stale generation marker.
- A new **Names** run with report pages requires complete report-start checks. Old
  or incomplete inputs pause before model requests with directions to run
  **Advanced → Correct classification → Dates → Names**. Rerunning only TOC or
  Boundaries does not invent starts in old classifications. Start at **Basic** too
  when applying changed structural descriptions/removing previous type smoothing.
- Profile workspaces freeze the new page-flow/selection identities. Unassigned
  canonical Advanced checkpoints reuse report rows only when explicit yes/no
  checks agree with their type. Dates/Names compare report-check signatures, so
  old completed rows cannot skip the newly checked report results.
- Derived-selection contract **4** describes new explicit-start grouping. Existing
  artifacts, completion badges, Resume and source files are not migrated. Only
  user-requested stage execution publishes replacement derived output.

Native participant/overview runtime compatibility includes preceding schema-7 code
identities under exact new code guards. Native instructions, evidence validation
and consumed-input/model hashing are unchanged. The source map and report-summary
work builders consume accepted report boundaries with their existing formats.

## Validation boundary

See [the chronological validation report](structured-classification-validation.md).
The new offline production-worker tests cover adjacent wanted/unwanted reports in
both directions, repeated names, one-page reports, forms between reports, orphan
bodies, incomplete checks, invalid responses, source retention, actual report work
items and old canonical checkpoint reuse. Shared request/inspection tests cover
all ten classifier/naming tasks, including report starts. Focus tests validate
schemas 7/8, both classification-v3 representations and historical schemas 1–6.

The unchanged case-name publication baseline failure remains unresolved. The report-
start work did not repair the separately disclosed summary-delivery defect; that
was subsequently fixed and verified in a separately authorized
[summary skill-delivery follow-up](summary-skill-delivery.md). No maintained-app restart,
private settings/case changes, commit/push or other-host validation is part of either change.
