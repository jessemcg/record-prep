# Dependency report naming

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
