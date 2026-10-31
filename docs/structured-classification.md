# Structured classification and prompt inspection

## Current contract

Dependency **1.8.0**, `profile_api: 1`, content schema **8** separates reusable
application instructions from editable recognition data. Classification has five
flat destinations, in organizational (not priority) order:

1. Reporter transcript page types (five existing fixed keys).
2. Clerk transcript page types (ten existing fixed keys).
3. First pages (hearing, minute order, form and report; four separate vision tasks within Advanced).
4. Report Names (16 initial stable-ID cards).
5. Form Names (six initial stable-ID cards).

Fixed page/first-page identities cannot be added, removed, reordered or renamed.
Their output keys are displayed, not editable. Naming cards can be added, renamed,
removed and reordered without changing internal IDs. Order is organizational,
never a matching priority. Empty report guidance is intentional. No new structural
category was introduced: `RT_other` already existed but lacked a description.

Report Names and Form Names are naming-only catalogs. `document_catalog.py`
projects names/descriptions without internal IDs for naming and exact-name validation.
Neither page-type nor first-page prompts receive catalogs. CT cards have structural
recognition guidance, without catalog previews or naming links. Their footer codes
remain supporting evidence, not mandatory approved-name gates. Catalog edits affect
only Names, including unsaved naming inspection.

Advanced independently checks **every CT_report page** for a report start, even for
unnamed reports and adjacent reports. Names reads name/date only on marked starts;
all starts terminate the preceding report range, whether or not the new name is
accepted. No one-page report-gap filling remains. See [report-first-page details,
cost and saved-output compatibility](report-first-pages.md).

`classification-tasks.json` version 3 contains `page_types.rt`,
`page_types.ct` and `first_pages` keyed by `first_hearing`, `first_minute`,
`first_form`, `first_report`. Exact application key sets and nonempty strings (8192 characters
maximum) are required. Mapping storage order cannot change canonical prompt order.
`naming.json` version 4 contains `reports` and `forms` arrays of exactly
`{id, name, guidance}`. IDs follow the existing identifier grammar; names are
single-line bounded canonical output strings, unique case-insensitively. Guidance
may be empty. Catalogs may be empty (no accepted output names); at most 256 cards.
Unknown fields, duplicate IDs/names, invalid Unicode, unsafe paths, file/total bounds
and existing single-link/safe-read requirements continue to fail closed.

RT/CT execution compares **all** descriptions for best supported fit. No first
match, ordered cascade, weight or preferred label is instructed or implemented.
Specific exclusions (e.g., no dialogue on a cover) remain recognition conditions.
Invalid/cross-side model labels remain errors, never Python fallbacks to `other`.
Names come solely from the same structured catalogs used by Python validation.
Unresolved names preserve source pages and do not manufacture TOC entries.

Hearing/minute dates have no editor or active profile field. The complete fixed
methods retain source locations, stamp/header/footer/page-number exclusions,
long-form U.S. dates, no weekdays, and empty-string uncertainty. Even the legacy
config loader returns these fixed methods; stored old keys are not rewritten.
First-page JSON now correctly quotes both `"yes"` and `"no"` values.

## Baseline information review

Before resource changes, public baseline bytes were frozen under
`tests/fixtures/structured_classification_baseline/`. The pre-existing
`tests/fixtures/dependency-1.6.0/` fixture is untouched. Exact allowlist inputs and
reviewed structured equivalents ship under
`recordprep/resources/profile_baselines/dependency-1.6.0/`.

The [line-by-line source-to-destination table](structured-classification-information-map.json)
accounts for all **198 nonblank original lines**, including each list item, example,
exception and qualification. It records original text and its card/application
instruction destination, authorized ordering removal, or duplicate equivalent.
It is an information-accounting aid, not a word-count or semantic-model proof.
Focused tests separately pin the original RT descriptions (with the explicit
certificate merge below), nine unchanged CT descriptions, the authorized replacement
of CT_report footer/name gating with structural recognition, three original first-page
cue sections plus the new report-start method, 16 report names and six form
heading/code pairs. The later authorized removal of the Detention date sentence and
superseded CT_report restrictions are recorded, not claimed preserved.

Explicit editorial/structural changes:

| Original | Replacement / destination | Reason |
| --- | --- | --- |
| `Decision rule (in order)` and `Else if` RT cascade | Removed cascade; all four recognition descriptions retained, plus certificate detail below | Expressly authorized removal of order/duplicates |
| RT certificate cascade: `certificate/attestation ... accuracy or preparation`; description: `Certificate of the transcript's accuracy.` | `Certificate or attestation about the transcript's accuracy or preparation.` | Merge the extra substantive attestation/preparation condition into the card, not lose it with the cascade |
| CT `Decision rules (apply in order)` and numbered prefixes | Ten fixed-key cards; report names now used only by naming | Remove priority/duplication; later authorized structural-report redesign replaces footer/name gating |
| `Parential Notification of Indian Status` heading/evidence | `Parental Notification of Indian Status` on its matching card | Correct source typo; canonical approved output name was already correct |
| `Use quotes only around the key` for first-page yes/no | Valid JSON examples with quoted key **and** value | Correct invalid JSON instruction |
| Two report-name lists and repeated form evidence lists | One catalog; each name and required heading/code retained once | Remove duplicate declarations, not evidence requirements |
| Detention Report hearing-date rule | Removed outright at explicit user request | General report-date instructions already cover report/hearing dates; no special fixed or editable exception |
| Generic report heading/date rules | `document_naming.naming_document` fixed mechanics | Reusable method; retains `unless no other report date is visible` fallback |
| Hearing-specific `particular case ... called`, ignore page numbers | `classifier_prompts.FIRST_TASKS.first_hearing` | Fixed task context retained once |
| Hearing/minute date task prose | `classifier_prompts.DATE_TASKS` and `DATE_RULES` | Full fixed methods, not shortened editable fields |

**Structural recognition, document starts and approved naming are separate.**
CT_report recognizes authored narrative/evaluative reports and continuation pages.
`CFS 6.7` and `DCFS 4216` remain supporting clues, never approved output names.
The mandatory footer/name test and `Page X of XX` disqualification are explicitly
superseded: numbering alone does not exclude a report. Report starts use fresh
opening evidence, not repeated footer/header labels or approved-name membership.
Recognizable court forms need not be among approved names to remain CT_form. The six form descriptions now state neutral
heading/code facts, including the shorter `Waiver of Rights` heading. Only the
fixed first-page naming method requires the matching heading and described code
together on that page and returns the approved canonical name. CT other examples,
minute-order authorship/dialogue exclusions, form footer/approval conditions,
and RT dialogue exclusions remain literal descriptions.

Hearing/report topic files and minute-summary guidance are byte-identical to the
frozen baseline. The classification work made no summarization method, quota, topic, routing or
artifact-format change. The separately authorized [summary skill-delivery fix](summary-skill-delivery.md)
now supplies the intended staged instructions without changing their contents.

## Runtime and compatibility

`classifier_prompts.py`, `document_naming.naming_document`, `summary_prompts.py`,
and `prompt_document.py` are GTK-independent. Execution, Save validation and
inspection share builders, not an independently rewritten prompt explanation.
User prose is concatenated literally (or serialized as JSON catalog data), never
passed through generic string formatting. JSON braces, Unicode and
`{{quote:...}}` syntax survive.

Classifier prompts use short, plain evidence/JSON instructions, without an
“Application classifier contract” heading/version or a trailing contract restatement.
RT/CT asks for the single best-supported fit across all descriptions, then presents
allowed labels and a JSON example followed by **Category Descriptions**. The verbose
ordering-policy paragraph is omitted. In the inspector, **Page image — attached
separately** explains the image attachment; that heading and placeholder are display
labels, not text sent to the model. Naming inspection uses the same attachment label;
summary skill delivery is described separately below.

Report/form extraction likewise starts with plain first-page/evidence/JSON
instructions beneath the inspector's **System message** heading. There is no
Application-owned Naming Contract banner, subordinate-guidance framing or trailing
Application Response Keys reminder. The existing first-page heading/code evidence,
report-date fallback, exact approved names and unresolved-name rules remain. Older
naming formats use the same plain generated framing without rewriting their saved
prose. That earlier wording refinement changed only Names prompts. The subsequent
report-start redesign changes page-type/first-page flow and naming selection,
not these naming extraction instructions.

Immutable schemas 1–7 and previous naming formats remain readable. Exact whole
resource recognition, independent of the rest of the snapshot, adapts known 1.6.0,
initial structured 1.7.0 and reviewed shared-catalog 1.7.0 classification resources
read-only to the frozen 1.8.0 resource. Original adapter inputs are unchanged.
Unknown prose is not split, fuzzily recognized or replaced with Dependency.
Explicit editing of structured v2 adds the fourth task; editing flat legacy tasks
adds `schema_version: 3` and `first_report`, preserving all original strings and
inactive dates in a lossless compatibility representation. Both new-format
resources permit manifest schema 8; mixed old naming can retain schema 6.
Runtime supplies fixed report-start clues for immutable profiles lacking that field.
Legacy ordering language is flagged and subordinate to fixed best-fit policy.
Only explicit normal Save publishes a revision. Runtime keeps the original selected
profile reference for publication guards; no replacement snapshot is published.

Navigation, successful Save and same-format Reset retain card objects, buffers,
undo/selection, expansion and viewport. Reset across formats rebuilds only the
changed classification surfaces; unrelated summary cards remain retained. Exact
bundled Reset still uses confirmed **Reset and Save**, a separate validated draft,
existing head/default/work guards, immutable history and truthful post-publication
refresh reporting. No settings action runs a stage or changes completion badges.

Historical naming v1/v2 catalogs supply their explicit names and structured evidence;
v3 supplies its explicitly declared names without guessing per-name descriptions
from monolithic prose. Unknown custom task/naming prose is retained, not cleaned up
or split. A custom old CT description may therefore still contain its own literal
list; only exact allowlisted resources are safely adapted to remove that duplication.

Effective prompt bytes plus explicit page-flow/selection identities determine
classification fingerprints. Only Names depends on naming catalogs. Report-start
clue edits affect Advanced/Corrected; historical date prose stays inert. Dates and
summary guidance bytes remain unchanged; actual upstream file hashes still determine
downstream workspaces. Basic/Advanced/Corrected and Names honestly invalidate old
explicit-run checkpoints without changing output-presence badges, Resume or saved
artifacts. Canonical unassigned Advanced/Date/Names checkpoints additionally compare
explicit report checks, so old completed rows cannot skip the new pass.
Derived-selection contract is now 4. Native compatibility retains prior reviewed
identities only under exact new stage-code guards; native prompt/evidence/model
behavior is unchanged.

## Inspector and verified summary skill delivery

Both About disclosures have **View full prompts…**. The modal, resizable read-only
inspector defaults to **Template with placeholders**; **With current draft** uses
frozen unsaved values and is labeled accordingly. Search/select/Copy work locally;
there is no model discovery, authentication, case requirement, persistence, logging
of contents or automatic export. Invalid drafts show literal values plus issues,
never silent bundled substitutions. Dates remain selectable in the inspector only.

The summary inspector includes application SYSTEM.md, actual staged skill,
complete launch instructions (including repeated per-topic guidance), active tool
names/descriptions/JSON schemas and runtime-data placeholders. Tools are generated
from **actual extension registration** with real TypeBox via
`node scripts/collect-prompt-tools.mjs`; `--check` verifies them offline. The
synthesis wrapper's added description/schema and `quote_capitalizations` are included.
The packaged resource includes source hashes. Missing/mismatched resources visibly
mark inspection incomplete/outdated. GUI inspection never needs Node or Pi.

**Summary delivery fixed in a separately authorized follow-up:** all five summary
launches now use `/skill:name request`, with a literal space instead of a newline.
Offline captures through the installed Pi SDK verify the exact complete staged
skill body plus unchanged request arguments at the production launch boundaries,
in both profile and unassigned compatibility modes. The inspector labels **Staged
skill** and **Launch message (before Pi skill expansion)** rather than claiming
the pre-expansion command is the final provider message. Staging strips/replaces
no custom guidance; Pi removes skill frontmatter and adds its normal skill wrapper.

The generated audit records the tested SDK version and successful expansion of all
five skills and hashes the tracked skill/template/system resources as well as tools
and launch code. Missing/stale audits still mark inspection incomplete. Delivery
has a distinct generation fingerprint in extraction, synthesis and minutes: explicit
reruns cannot reuse a broken-delivery checkpoint as equivalent. Saved output remains
readable and unchanged; no settings action reruns a case. See
[summary skill delivery](summary-skill-delivery.md) for scope, testing and limits.
Subsequent tool results, model-generated exchanges and provider internals are dynamic,
not fixed omitted RecordPrep instructions or replayable through this viewer.

See [local validation and limits](structured-classification-validation.md).
