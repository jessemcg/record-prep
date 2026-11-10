# Procedural filings and standardized motion requests

Recognition-v4 classifies by procedural function, not printed format. Motions,
applications and petitions seeking substantive relief or a determination of status,
recognition or participation rights within an existing proceeding are motion papers,
including standardized requests. Oppositions, replies and separately identifiable
supporting declarations remain motion papers. The app-owned instructions do not name
practice-specific statutes or form codes.

Dependency acceptance examples include a section 388/JV-180 request to change an
order and a request for de facto-parent recognition. A civil application to modify
an injunction follows the same rule. These are examples, not runtime exceptions.

## Procedural filings

The interface now calls the former Forms category **Procedural filings**, and its
profile destination **Procedural Filing Names**. This is a bounded category, not
all papers filed with a court or all papers lacking an affirmative request. It
includes administrative/status/address filings, standardized order forms, initiating
pleadings and the existing non-motion procedural instruments: waivers, agreements,
verdict sheets, jury instructions/communications and instruments initiating appellate
review. Request wording alone does not override these functions. A substantive
application within an existing proceeding is not a procedural filing merely because
it uses a form. Orders, notices, proofs of service, reports, certificates and exhibits
retain their more specific classifications where applicable.

## Naming, grouping and compatibility

Dependency 1.19.0 removes only JV-180 (form-04) from its procedural-filing naming
catalog: five cards remain with stable IDs. JV-100 remains an initiating petition.
There was no de facto-parent request card to remove. Motion titles come from the
application-owned source-title rule, not new Dependency-specific naming cards.
The earlier 1.18.0 case-plan report exclusion remains included. Criminal 1.1.0 removes the Probable Cause Request or Certificate naming card at the
user's request; eleven procedural-filing cards remain. Structural classification of
that instrument is unchanged, but the bundled catalog no longer selects it for a
standalone named entry. An integral section of a Notice of Appeal remains part of
that notice.

Classification, first-page checks, motion naming, agent correction and organization
all recognize standardized substantive requests. A lead request and its expressly
linked declaration retain separate physical titles/ranges within one logical motion
group. Unselected documents are not silently absorbed; ambiguous support remains
visible. No deterministic code purports to decide legal function or semantic linkage.

The serialized CT_form/CT_form_first_page, form task IDs, profile forms key, editor
navigation IDs and artifact fields remain unchanged for readers. Recognition-v1/v2/v3,
historical profile resources, adapters and saved artifacts retain their original
bytes and semantics. No Focus shared schema or launcher contract changes are needed.
New recognition identity and prompt hashes invalidate explicit-stage checkpoints;
output-presence badges and Resume do not treat old output as missing.

Adoption is explicit: use current application code and adopt the new bundled naming
guidance through the application's profile settings. Existing saved personal profiles
are never overwritten. To correct existing classifications, rerun Basic and affected
downstream stages, including Advanced, Dates, Names, Agent correction, motion
organization, TOC/boundaries and dependent summaries/source map. A Names-only run
cannot reclassify a lead request. No bundle rerun is performed by this source change.

## Validation scope

Offline tests verify profile-independent instruction delivery, preserved historical
contracts, stage identity changes, current naming exclusions and synthetic standardized
requests/declarations flowing through physical boundaries into one logical group.
Synthetic rows and model proposals test plumbing, not model/image accuracy. Existing
classification, correction, grouping and summary tests cover source preservation,
invalid output and unrelated categories. No real-case processing or paid calls are
needed for this change.
