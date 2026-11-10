# Dependency report naming

## Current: procedural-filing catalog (1.19.0)

JV-180 is removed from the former Form Names catalog, now **Procedural Filing Names**.
Its substantive request is classified/named as a motion under the shared function-first
rules. Five procedural-filing cards remain; the case-plan exclusion below is retained.
See [Procedural filings](procedural-filings.md).

## Case plans excluded (introduced in 1.18.0)

The agency-report naming rule excludes child welfare case plans, explicitly including
**CHILD WELFARE SERVICES CASE PLAN** and updated/amended versions. Agency authorship,
court submission, or a separate title/date does not make these qualifying reports.
The model is instructed to return an empty name and rule ID, not the fallback name.
An otherwise qualifying agency report remains eligible when it discusses or attaches
a case plan. Source pages remain intact; this naming-only exclusion prevents separate
report entries/boundaries and standalone report summaries when followed by the model.
It does not redact case-plan information from the source or from a parent report.

No classification taxonomy, form rules, summary topics or historical snapshots change.
Saved personal profiles and existing bundle output are not automatically updated:
explicitly adopt the new bundled guidance and rerun Names and affected downstream
stages to apply it. Offline tests check prompt delivery and empty-name handling, not
model classification accuracy.

## Source titles for selected agency reports (introduced in 1.13.0)

The single agency-report description remains the eligibility rule, but qualifying
reports now retain their actual cover/first-page title. **Child Welfare Agency
Report** is only the fallback when eligible but no title is discernible. Dependency
uses the general profile **Source title** naming approach; six form cards remain
fixed-name. See [source-title naming](source-title-naming.md) for the naming-v5
contract, UI, historical preservation and explicit adoption.

## Historical: single fixed category name (1.12.0, superseded)

The following records the initial implementation before source-title support.

California Juvenile Dependency **1.12.0** retains content schema **10**, naming
schema **4**, `profile_api: 1`, and existing artifact formats. Its Report Names
catalog now contains one card: `report-agency`, **Child Welfare Agency Report**.
The six Form Names cards, hearing/report summary topics, application recognition,
first-page detection, date rules and naming runtime are unchanged.

The category selects a distinct report or written update prepared by, or expressly
presented as the report of, the responsible child welfare agency for the juvenile
court's consideration. The canonical name need not appear literally on the page.
Memoranda, letters, addenda and supplemental information qualify by agency identity
and court-directed purpose, including short memoranda supplying omitted material.
No substantial narrative, recommendation, county name, title or code is mandatory.

Agency letterhead/department identification, worker or representative attribution,
court addressee/purpose, and case-specific information are supporting clues, not
mandatory fields. Evidence remains limited to the supplied first-page image. Filing,
transmitting, mentioning or attaching a document alone is insufficient. Independent
CASA, medical, psychological, school, provider and police records do not become the
agency's report through submission. Petitions, motions, notices, service proofs and
court orders keep their separate identities. Unclear attribution/purpose stays
unnamed; each distinct qualifying start retains its own range even with identical
names/dates. No extra validation gate, model pass or title-alias list was added.

The existing naming builder already permits identifying wording interpreted with
catalog descriptions rather than a mandatory prominent heading. The new description
explicitly distinguishes this canonical category from the document's literal title;
no global prompt or historical adapter change is needed. Exact output membership,
JSON normalization and the report-date sentence remain unchanged. Only the Names
component changes directly; actual changed output bytes affect downstream work.

The exact former 1.11.0 digest
`26f5ff0c018868b85966f4a54190ac4f6e6c8abc5f8351acfc348d9b5bbd79a4`
is a known bundled baseline. Accepted historical snapshots remain byte-preserved;
personal catalogs are never replaced automatically. No private settings or case
outputs are migrated. A selected personal profile requires explicit editing or
**Reset to bundled… → Reset and Save** to adopt the bundle; reset replaces all profile
guidance, including customized naming and summary topics, not only Report Names.
To preserve other guidance, replace only the report cards manually and Save.

Adoption never runs processing automatically. With complete report-start checks,
explicit **Names → Correct classification with agent**, then desired TOC/boundary/
summary work applies the new selection. If start checks are absent, run Advanced
and Dates before Names; Basic is needed only when deliberately repairing page-type
recognition. Existing completion badges and Resume remain presence-based.

Validation uses public resources, fictional data and offline providers only.
Contract and GTK checks demonstrate delivery, preservation and pipeline mechanics,
not live-model recognition accuracy. The motivating text survey was targeted, not
a prevalence study; no private case text is included in source or tests.

### Implementation validation (2026-11-06)

On the current Work computer, a disposable tracked-source checkout and separate
locked Python environment ran **923 tests: 915 passed, 8 skipped**. Coverage includes
21 fictional image/pipeline scenarios with scripted responses (agency memorandum,
short transmittal, unfamiliar title, letter, independent medical/provider/CASA
material, notices/service proofs, unknown attribution, adjacent same-name/date
reports and noncanonical model output). These establish routing and publication,
not image-model judgment. Historical 1.11.0 digest reconstruction, personal-profile
preservation, unchanged form-prompt/date bytes and unrelated stage identities pass.

Fatal-critical GTK acceptance passed editing/save/undo/reset in a synthetic store
and compared the full naming inspector with runtime composition. Native Computer
Use confirmed one expanded agency-report card and its description in that separate
synthetic window. The maintained app was not restarted or edited. Resource validation,
Python compilation and diff checks passed. No real profile/config/case data was
modified, and no paid model, OCR or production pipeline work was performed.

## Historical: title catalog in 1.10.0 (superseded)

The following records the prior implementation and its validation, not the current
catalog or adoption instructions.

California Juvenile Dependency **1.10.0** retains content schema **9**, naming
schema **4**, `profile_api: 1`, and the existing artifact formats. The seventeen
Report Names cards in `recordprep/resources/practice_profiles/california_dependency/naming.json`
contain the literal approved descriptions. Every description begins
“Court-directed child-welfare agency report.” Existing IDs/names are retained;
`report-17`, **Jurisdiction/Disposition Report**, follows Disposition Report.
The six form cards and title-plus-code rules are unchanged.

## Evidence and matching scope

A targeted visual review of 42 existing images found report titles in headings
and repeated footers, continuation identification tables, and report-local page
numbers different from transcript stamps. This was not a prevalence study or an
accuracy evaluation; historical labels were only candidate locators, not answers.
Only generic template findings are retained here, not source pages or case facts.

The report-naming prompt considers the report's **own visible title or identifying
wording**, together with the selected profile's descriptions. A prominent heading
is strong evidence, not mandatory. A header/footer may identify the report family
when supported by opening structure and court/report identification on the **same
supplied first-page image**. A running title, code or page number alone is not
sufficient. Conflicting heading/footer evidence is considered together with
explicitly described variants; unresolved conflicts yield an empty name. Narrative
mentions, attachment lists, hearing-type fields and directions to prepare a report
are not that report's identity. There is no heading/footer precedence cascade,
county whitelist, substring matcher or automatic alias converter.

| Approved name | Description scope / supported variants and exclusions |
|---|---|
| Detention Report | Own title in heading/footer; opening court/hearing/case fields support it, not discussion of detention. |
| Initial Hearing Report | Own title, not merely preparation for an initial hearing. |
| Jurisdiction Report | Separately titled report, not the combined report. |
| Disposition Report | Separately titled report, not the combined report. |
| Jurisdiction/Disposition Report | Own combined heading/footer and opening identification; slash spacing may vary. Return the combined canonical name. |
| Last Minute Information | Heading **Last Minute Information for the Court**; child/court/department/hearing/worker fields, Information only / Change in Recommendation boxes and DCFS 4216 support recognition but are not required. |
| Non-Detained Report | Own title; ordinary hyphenation/spacing variants, not a child's detention status. |
| Status Review Report | Own title, often repeated in footer; future hearing references do not change identity. |
| Interim Review Report | Own title; **Progress Report** heading only when the own footer says Interim Review Report and the opening context supports it. Progress or Special/Interim hearing wording alone is insufficient. |
| Review Report | Own **Review Report** or **15 Day Review Report** title; not a catch-all for specific review families or CASA Review Hearing Reports. |
| Addendum Report | Own title with fresh report-identification opening, not an Additional Information section or incidental reference. |
| Petition Report | Agency report explicitly bearing that title, not a dependency petition, allegations or discussion of a petition. |
| 366.26 WIC Report | Own title or **Continued WIC 366.26**; not a citation, hearing field or scheduling recommendation. |
| Permanent Plan Review Report | Own title, not references to a plan, future hearing or another report. |
| RPP Report | Own title/identifying footer and opening report context; not a hearing label or preparation order. |
| Selection and Implementation Report | Own title; not a hearing field or a differently titled 366.26 WIC Report. |
| Additional Information for Court | Agency update titled that way or **Additional Information to the Court**; initial child/hearing tables, Information for the Court area and CFS 6.7 are optional clues. Not an internal section or CASA Additional Information Report. |

No distinctive opening template was confirmed for Initial Hearing, standalone
Jurisdiction/Disposition, Non-Detained, Petition, Permanent Plan Review, RPP, or
literal Selection and Implementation titles. Their descriptions remain conservative:
no invented codes, acronym expansions, legal-content tests or extra aliases.
Missing/cropped footers never disqualify otherwise clear report identity.
Differently titled CASA reports remain structurally preserved but unnamed unless
separately added to the selected catalog.

## Pipeline and compatibility

1. **Basic** recognizes court-directed reports structurally, without a name catalog.
2. **Advanced/Corrected** independently check all report pages for starts, including
   adjacent, one-page and unnamed reports. A repeated footer cannot prove a start.
3. **Names** requires complete start checks and names only marked starts using the
   selected profile's catalog. Descriptions cannot repair a missed start.
4. TOC/boundaries/summaries accept named reports under existing rules. Every start,
   including an unnamed one, terminates the preceding range. Source pages remain
   preserved; unnamed fragments are not merged across gaps or turned into summaries.

Only Names identities change directly; Basic/Advanced/Corrected/Dates, recognition-v1,
report-date wording (including footer-date fallback), form prompts and summary
instructions are unchanged. Actual changed upstream bytes can still invalidate
dependent work. Rendered prompt hashes capture the naming rule change without
bumping the shared naming contract version. Exact canonical output names remain
required: Progress Report itself is not an approved output name.

The exact prior 1.9.0 digest
`f67e0a93bb226ea682988f54b9555c5705f3d42a952631a3327091aa5561a620`
is a known baseline, so ordinary acceptance is not mistaken for personalization.
Historical snapshots, frozen catalogs and exact adapters retain their old names,
descriptions and bytes. Unknown custom naming prose remains literal. Saved personal
profiles are not automatically replaced; no private migration/configuration repair,
output regeneration, completion-badge change or historical cleanup occurs.

## Explicit adoption

Updating the bundle does not change existing output or overwrite a saved personal
profile. Personal profiles can explicitly adopt the desired report-card changes in
**Profile settings**, then **Save**. **Reset to bundled… resets all profile guidance**,
including summary topics and minute guidance, not only report descriptions; do not
use it casually when other guidance is customized.

For an existing case with complete report-start checks, explicitly run **Names**,
then the desired downstream TOC/boundary/summary work. If checks are missing, first
run **Advanced → Corrected → Dates → Names**. Basic is needed only when deliberately
reclassifying upstream page types, not just for description changes. Reruns can
incur provider charges. Badges and Resume remain output-presence based; opening,
selecting, saving or updating never triggers an automatic rerun.

## Validation limits

Offline tests cover literal composition, exact-name/date validation, historical
ownership and stage-local identities. Newly authored fictional scenarios and fake
HTTP responses exercise actual request routing, start-only naming, source retention,
range separation and publication. They do **not** show that an image model recognizes
those scenarios. Isolated synthetic Profile settings/inspection and packaging checks
validate presentation and resource delivery, not semantic accuracy. These changes
are evidence-informed and mechanically validated; any improvement in classifier
accuracy requires a separately authorized model evaluation.

### Implementation checks (2026-11-05, current home computer only)

A tracked-source copy at `/tmp/recordprep-report-naming.kWw5U9/RecordPrep` used an
explicit project-env source/environment pair, locked Python 3.13 and temporary
HOME/XDG/config/cache/state. No private profile/case/configuration was copied.
Full unittest discovery: **848 run, 840 passed, 8 skipped**. Compilation, sequential
native-resource validation, fatal-critical synthetic GTK acceptance, offline
wheel/sdist build and all **30** packaged resource byte comparisons passed.
A copy-mode installed-wheel smoke test independently loaded the 1.10.0 profile and
compiled/validated report naming from an empty directory. Diff whitespace and
maintained/copy byte-parity checks passed. Evidence logs remain under the temporary
root, not in the package.

The frozen prompt-tool audit expects Pi SDK 1.4.0; it was provisioned offline in a
temporary nested-layout installation instead of changing the packaged audit or the
installed 1.5.0 SDK. Initial checkout-name/SDK-layout harness errors and obsolete
prompt assertions were corrected before the passing full run. Eight optional or
platform exclusions remain skips, not claimed passes.

Production Profile settings widgets showed all descriptions and the combined card;
full-prompt inspection matched runtime composition. Visual checks used synthetic
widget captures and a native desktop capture of that separate synthetic window.
Text wrapped normally at the actual **1226×1197** settings size; requested narrow
sizes were not honored by this desktop, so narrow-layout acceptance is not claimed.
The prompt inspector was **700×760**. The temporary process was terminated; no
maintained application was restarted, and no real Save/Reset, OCR, model request,
private-profile update, case regeneration, launcher/Focus change or deployment was
performed. Live semantic evaluation remains separate.
