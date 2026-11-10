# California Criminal Law — first bundled draft

RecordPrep includes **California Criminal Law 1.1.0** (`california-criminal-law`),
content schema 14 / profile API 1. It is an editable first draft for an appellate
attorney reviewing California criminal records, particularly felony conviction
and sentencing appeals. **California Juvenile Dependency remains the default**
application selection and Create profiles base. Criminal is another selectable
profile and creation base, not an automatic replacement for saved guidance.

## Scope

The profile owns only **Report Names**, **Form Names**, and **Report digest topics**.
It adds no hearing, motion, minute, participant, overview or caption method. Caption
inference remains application-owned; the required `case-name.md` is inert compatibility
text and `policies.json` is empty. No shared contract/artifact format changes, settings
migration, provider pass, summary-quality gate or automatic preparation is involved.

Every source page remains available, including unnamed reports, independent
investigative records and embedded preliminary-hearing transcripts. This draft does
not supply standalone police/interview/victim-statement digests or form summaries.

## Report Names: probation authorship and court-directed purpose

One source-title rule, `report-probation`, selects probation-agency-authored reports
and written updates for court consideration. Preplea, presentence, sentencing,
disposition, supplemental, addendum, progress, violation, restitution and postjudgment
reports are examples, not a title whitelist. Short memoranda and one-page updates
qualify without a recommendation, long narrative, form code or the word “report.”

First-page officer attribution, court identification, introductory wording and agency
identification can establish eligibility. Neither stationery nor attachment position
alone establishes authorship. Use the visible first-page title with meaningful
qualifiers; only a clearly eligible but untitled report gets **Probation Report**.
Uncertain authorship or purpose stays unnamed, not hidden behind a fallback.

Fictional examples:

| Visible document | Naming outcome when supported |
| --- | --- |
| Probation officer's court-directed PREPLEA REPORT with conditional recommendation | PREPLEA REPORT; no assumed conviction |
| Probation officer's one-page ADDENDUM | ADDENDUM, a separate report even if date/title repeats |
| Court-directed probation update with no discernible title | Probation Report with `report-probation` |
| Independent victim-completed statement on probation stationery | No probation-report name/digest |
| Police account recounted *within* probation's report | Material attributed digest content within that report |
| Independently reproduced police/interview/medical/psychological attachment | Not probation's report merely through attachment |
| Sentencing brief asking for probation | Motion work, not a neutral probation report |

Existing report-date wording and normalization are unchanged. Unnamed starts still
terminate earlier ranges. Independent attachments do not extend a named report's
summary range; matching titles/dates do not merge separate reports.

## Procedural Filing Names: eleven source-title families

Version 1.1.0 removes the Probable Cause Request or Certificate card. Its structural
classification remains unchanged; it is no longer selected for a standalone named
entry by this bundled catalog. Existing saved profiles and prepared output are not
rewritten.

All cards use source titles, preserving amended/corrected qualifiers, count identifiers
and expressly titled proposed/refused variants. No form code is required. A card's
label is a fallback only for a clearly matching, untitled document; unknown rule IDs
never authorize a fallback.

| Stable ID | Fallback label | Scope / important limit |
| --- | --- | --- |
| form-information | Information | Criminal information and amendments; not a motion to amend |
| form-complaint | Criminal Complaint | Felony/misdemeanor complaints and amendments; not civil complaints or police reports |
| form-indictment | Indictment | Indictments and amended/superseding versions; not grand-jury testimony |
| form-verdict | Verdict | Verdict/special-finding sheets, including unused/unsigned ones; naming is not proof of a returned verdict |
| form-notice-of-appeal | Notice of Appeal | Actual instrument initiating review, not a notice of its filing or transcript preparation |
| form-abstract-of-judgment | Abstract of Judgment | Determinate/indeterminate and amended/corrected abstracts with integral continuations; not minutes |
| form-jury-instructions | Jury Instructions | Submitted/proposed, given, refused/withdrawn, modified and supplemental written sets; no assumption all were given |
| form-stipulation | Written Stipulation | Distinct written agreement; not oral stipulations or advocacy seeking a ruling |
| form-jury-communication | Jury Communication | Written jury/juror questions, notes, requests and court responses, including handwritten ones; not summons/questionnaires |
| form-plea | Plea and Rights Waiver | Written plea agreements/forms and rights waivers; not withdrawal motions or oral transcripts |
| form-counsel-waiver | Waiver of Counsel | Written self-representation/counsel-waiver advisements, including Faretta; not a contested motion |

A new instruction number inside a packet, repeated title or signature ending does
not itself start a new document. An integral probable-cause section of a Notice of
Appeal packet is not automatically separate. Independently identified instruments
remain separate. These names do not create form-summary functionality.

## Nine ordered report digest topics

1. **Criminal Charges and Case Posture** — actual charge/disposition status and
   report purpose; preserve conditional preplea recommendations.
2. **Circumstances of the Defendant** — material personal history, health,
   treatment, rehabilitation and alternatives, with attributed opinions.
3. **Allegations, Interviews, and Evidence** — offense accounts and material
   evidence/discrepancies, retaining each layer of attribution and evidentiary status.
4. **Prior Record and Supervision** — convictions versus arrests, pending/dismissed
   charges, adjudications, supervision and custody conduct.
5. **Victim Impact** — harm, safety, nonfinancial consequences and expressed
   preferences, not assumptions based on nonresponse.
6. **Sentencing Recommendation and Supporting Reasons** — attributed recommendations,
   eligibility, aggravation/mitigation and contrary considerations; proposals are not orders.
7. **Custody and Credits** — stated periods/figures/disputes; no recalculation or
   silent reconciliation of proposed versus awarded credits.
8. **Restitution and Financial Obligations** — distinguish losses, restitution,
   fines/fees, payment issues and requested/recommended/ordered/deferred status.
9. **Disputed Issues and Information Limits** — material objections, missing or
   outdated sources and consequential inconsistencies, without appellate merits analysis.

These are source-bounded review guidance, not a mandatory checklist. Use existing
null behavior when no material content responds. Give each development its best
topic once; retain enough context without repeating the entire offense account.
Read the **complete** report, including late recommendations and proposed findings/orders.
Preserve the report-date perspective. Existing quotation, synthesis and best-effort
rules remain in force: no quotas, cutoff detector, compulsory repair pass or blocking
summary-quality gate. Do not calculate the lawful sentence or “correct” historical
recommendations by applying current law.

## Universal recognition and embedded transcripts

The application selects `recognition-v3.json` (recognition JSON schema 1). Historical
v1/v2 bytes are retained. `CT_form` now includes the bounded procedural-instrument
families above whether standardized or custom-written/handwritten, for **every**
profile and unassigned work. It does not redefine all pleadings/correspondence/exhibits
as forms. Hearing notices, distinct service proofs, record-authentication certificates,
actual minutes, neutral reports, investigative records and motion advocacy retain
their existing categories. Basic, Advanced and agent correction share the same resource;
profile catalogs never determine structural type or start detection.

Layout detection identifies the **outer collection** using covers, indexes, clerk
certification, pagination and neighbors. Once CT is reliably established, enclosed
preliminary hearings, interview transcripts, reporter covers/certificates, internal
indexes and Q/A do not reopen RT. They normally remain `CT_other`, without RT hearing
starts. CT-only can contain verbatim proceedings; standalone RT of a preliminary
hearing remains RT. A genuinely separate CT→RT/interleaved collection, conflicting
outer evidence or uncertain boundary still requires review. No page deletion or text
stripping is authorized. Enclosed reporter pagination and federal docket overlays
are not the outer CT citation sequence; unsupported numbers stay ambiguous/missing.

## Reviewed structures and legal context

Planning reviewed embedded text and selected images in three supplied numbered record
folders and a standalone probation report, not every page as a complete legal review.
No private source text/images are shipped as fixtures. Notable limitations:

- The standalone report is a juvenile delinquency disposition report, not an adult
  sentencing report. Its structural examples do not supply adult placement rules.
- One sample combines RT/CT files with differing case captions; individual formats
  are supplemental examples, not a verified unified case.
- Another sample's index lists an absent second CT volume. Index entries do not
  establish that those documents were inspected or that the record is complete.
- PDF file pages, official CT/RT pages, internal document pages and federal docket
  overlays are distinct numbering systems.

[Rule 8.320(b)](https://courts.ca.gov/cms/rules/index/eight/rule8_320) supports the
criminal-appellate document families and places certain preliminary-examination
transcripts in CT (notably (b)(13)(B)). “Ignore the preliminary hearing” means ignore
its transcript-like appearance for the outer split decision, not omit it or conclude
it cannot belong to the normal record.
[Rule 4.411.5](https://courts.ca.gov/cms/rules/index/four/rule4_411_5) informs attention
to status, sources, history, eligibility, recommendation reasons, credits and finances.
These are drafting context, not instructions to manufacture missing content or apply
current sentencing law to historical facts.

## Explicit adoption and validation limits

Select **California Criminal Law** explicitly. Its personal Save/Reset target and
protected built-in identity are separate from Dependency's. Create profiles can copy
either profile. Save retains immutable history and ordinary stale-write guards;
selection/Save/Reset never starts preparation. Existing personal settings and legacy
Dependency customizations are not imported into Criminal or migrated.

For correctly routed/classified existing bundles with complete starts, explicitly
rerun **Names** and necessary downstream work. To adopt custom-instrument recognition,
explicitly run **Basic → Advanced → Dates → Names → Agent correction**, then rebuild
the affected downstream outputs. This deliberately changes Basic/Advanced generation
identities across profiles, not existing output on disk. Incorrect outer layouts
need a separate safe bundle/recovery workflow; never force a protected split change
or reset the original. Completion badges and Resume remain presence-based.

Fictional offline tests cover contracts, scripted image-request routing, distinct
starts/attachments, source preservation, nine-topic/null/quote codecs and fake-provider
summary publication/reuse. They do **not** establish real image-model naming accuracy,
layout judgment, citation selection accuracy or generated-digest quality. Any later
paid semantic evaluation needs separate authorization and is not an ordinary pipeline
repair/validation pass. See [implementation validation](california-criminal-validation.md).
