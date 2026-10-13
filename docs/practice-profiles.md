# Shipped practice profiles and personal settings

RecordPrep and Focus each ship **General Court Record** and **California Juvenile
Dependency**. General is the new-case default. Dependency is a complete public
specialty, useful without anyone's private configuration. Each app owns its
instructions independently; there is no profile repository, download, sibling
package import or automatic cross-app synchronization.

## Choose, edit, save

The chosen profile name appears as a subtitle immediately below the app title,
not as a separate banner. The hamburger menu shows the profile dropdown and
**Profile settings** as compact, normal-weight, left-aligned menu items. Names
wrap in full and a check marks the current choice. Selecting a dropdown item
immediately applies that profile; there is no separate **Use profile** action or
chooser dialog. **Profile settings** edits the selected profile. Focus also offers
**Existing settings** as an explicit compatibility choice before a case's first
research session. Opening the dropdown alone does not change the case; activating
an item does. Failed or blocked selection retains the actual current choice.

Profile settings opens in an independent, non-modal window with minimize, maximize
and close controls. It can be moved/resized independently while the main app stays
usable. Active work or changing cases still blocks stale settings application.
The window uses a boxed category/subcategory list on the left and shows only the
selected settings page on the right, like Model settings. The list sits directly on
the window background, without a contrasting full-height left panel. The header
also uses Model settings' flat toolbar styling and shares the window background.
In Focus, **General → Profile and defaults** contains the profile selector,
**Create profiles** and **Use for new cases**. RecordPrep has no General section or
second profile picker/default checkbox; it edits the already-selected profile.
**Create profiles** is a hamburger-menu link immediately below **Profile settings**,
not a button at the bottom of the sidebar. Its Cancel/Create actions use flat
buttons without an extra selectable hover background. Existing new-case default
preferences are preserved by Save (saving that profile advances its revision).
The profile name remains beneath the window title; **Save** and **Cancel** stay in
the header. Switching pages preserves unsaved edits and each page's scroll position.
At narrow widths, the **Show categories** button opens the sidebar as an overlay;
selecting a subcategory closes the overlay without squeezing the editor. A built-in opens with
complete populated settings; personal settings appear in place of its baseline.
Create profiles has a **Create a profile** section asking for a name and starting
profile (General by default). Identifiers are generated internally. Create opens
an unsaved draft; only Save keeps it. Cancelling a draft saves nothing.

Its **Delete a personal profile** section lists only user-created specialties,
not built-ins (including personal edits of built-ins). Choose one and press
**Delete profile…**, then confirm. Delete removes the chooser entry, never its
accepted revision files or existing case pins. Existing cases can continue using
their saved instructions. A deleted new-case default returns to General, and a
matching pending next-case choice is cleared. No case is silently rebound and
nothing is regenerated. Reusing the name creates a new identity; old open drafts
cannot resurrect a deleted identity. Stale profile/default/case state or active
work blocks deletion without repairing private files.

RecordPrep opens at Classification. Its only main categories are **Classification**
and **Summaries**. Case Overview remains a pipeline step, not a settings category.
One fixed, practice-neutral method reads all summaries completely and supplies Focus
with central parties, record-bounded procedural posture, chronological material events,
neutral principal disputes and record scope/gaps. It preserves allegations versus
findings, uncertainty and identity-only participant metadata; it has no word/event
quotas, assumed appeal or outside legal analysis. Historical overview instructions
are ignored, not rewritten. The five-section format and nonauthoritative disclaimer
remain unchanged. Every Classification page
shows a short, display-only **How classification builds the record** explanation
above its scrolling editor, as plain text on the window background without a box,
border, shadow or contrasting panel. A wrapping, accent-colored progression reads
**Page types → First pages → Dates & names → Table of contents → Boundaries**.
The explanation describes the vision model's dual role: classifying page images
and extracting dates and document names. The progression is a display-only overview,
not clickable navigation or live progress; correction steps still run in their usual places.
Common guidance is first; reporter’s-transcript (RT)
page types → hearing starts → hearing dates come next, followed by clerk’s-transcript
(CT) page types → minute-order/form starts → minute-order dates → report names/dates
and form names. Subtitles identify RT/CT and Basic/Advanced/Dates/Names without a
new navigation level. Each task keeps its tall editor (at least 360 pixels,
expanding with the window). Report/form naming remains under Classification.

Common guidance is combined with only the active page-type, first-page or date task,
not every task prompt. Naming has separate instructions and approved-name entries.
Advanced uses Basic’s page types to select hearing, minute-order and form start
checks; Dates uses marked hearing/minute-order first pages. Names reads a report’s
name and date at the start of each continuous group of report pages, and reads form
names from marked form first pages. Hearing TOC labels come from hearing dates—not
a separate hearing-name prompt. Correction stages retain their existing positions;
TOC and document boundaries use these classification results.

Structural page types and response keys are application-owned, shared across legal
fields. Profiles customize recognition clues, not category names. Each Basic editor
shows the supported RT or CT labels from the same definition used by the runtime
validator. Advanced returns `first_page: yes/no`; Python adds `RT_body_first_page`,
`CT_minute_order_first_page` or `CT_form_first_page`. Dates returns `date` or an empty
string. Naming uses separate approved names, not new page types. Certificates,
motions, notices and proofs of service remain recognized structural categories.

The editor warns as you type when an RT_/CT_/CR_ label reference is unsupported for
the current task. This is advisory token checking, not semantic proof: comparisons
and negations can intentionally mention other labels, and prose-only contradictions
may go undetected. Warnings do not block Save, rewrite guidance, reject historical
profiles or loosen runtime validation. Review a warning before running a case.

General Court Record 1.5.0 provides a practice-neutral starting point: definitions
of every Basic category, start/continuation clues, competing-date guidance and
instructions for adding your practice's headings, terminology and examples. Add
approved report/form names in the separate naming editors; General deliberately
ships without a specialty-specific title list. Dependency's bundled and private
instructions are untouched. Existing personal profiles and accepted case revisions
are never automatically replaced by these new General resources.

Summaries shows one pinned **Topic-guided agentic summarization** explainer above
exactly three pages: **Hearing digest topics**, **Report digest topics**, and **Minute orders**. Its linear overview is **Each hearing /
report → Topic digest + quotes → Narrative section → Hearing / report summary**.
Stage 1 reads each complete hearing or report across all its pages; after the digests
are ready, Stage 2 synthesizes hearing by hearing or report by report, producing
separate final hearing and report summaries. Relevant information may be sparse or
dense; substance determines detail, without word targets or quotas.
**Digest topics** are the hearing/report customization surface. Fixed application
instructions preserve the pre-profile materiality, adaptive-detail, quotation and
cohesive-narrative method. No additional digest or narrative instruction fields
exist in new profiles or the UI; old snapshot fields are never compiled or imported
from legacy settings. Minute orders retain their separate single-stage,
complete-order summary flow, described on their page. There is no attendance-policy
selector. California Dependency minute guidance asks for the hearing's identity,
each parent's attendance, attributed party positions, main findings/orders and the
next scheduled hearing, in that order. All pages may supply attendance evidence;
counsel alone establishes neither presence nor absence. Unclear attendance and
missing/unclear future settings remain explicit; no reporting-status sentence is
added. Exact former bundled minute prompts resolve to the new default without
rewriting private snapshots; genuinely custom minute prose remains unchanged. The shared explainer ends
with the distinction between topic-organized digests and narrative sections.
Restored contracts mark profile-bound digests and narratives regeneration-pending;
existing output stays untouched until an explicit summary run.
There is no Participants / Witnesses settings area. One fixed general identification
contract applies to every hearing, regardless of specialty. It records source-supported
names, roles/relationships, attorney representation, personal/remote attendance,
express absences, speaking, sworn testimony and examinations, with citations and
uncertainty. Role labels describe the source rather than an editable category catalog.
The index still supports hearing summaries, case overview and Focus navigation.
Minute orders use only the current order, not this index or a profile role catalog. Report naming and form naming
each have just one instructions editor. Their approved names appear once, as `- **Name**` entries in that editor;
optional matching requirements follow an em dash. The same entries supply both
the model prompt and Python's exact approved-name check. There is no naming-mode
selector, separate title list, or form-rule card editor. Editing the prompt's list
changes the approved names; prose outside those entries does not silently add names.
Dependency retains its reviewed names and form codes. General has no approved names
until you add practice-appropriate entries. Unmatched reports retain provisional
labels and their ranges; report dates can still be extracted independently. Forms
with no accepted name are omitted from the Forms TOC, without deleting their source
pages or structural classifications. An empty form name is not replaced by an
“Untitled form” entry. Existing TOCs stay unchanged until Build TOC is explicitly run.
Summary topics are expandable cards with editable names/instructions and add,
remove and reorder actions. Renaming a topic does not change its stable ID.
Topic instruction editors unwrap hard-wrapped prose to use the available width,
while preserving paragraph breaks and structured blocks such as lists. This is
initial display formatting only: opening or browsing does not change saved guidance
or mark the profile dirty. Editing a topic makes its displayed text the draft;
only the normal Save flow persists that draft.
Topics guide capture from each complete hearing or report, not required headings
in the narrative. New RecordPrep profiles use content schema 5, without the four
extra summary instruction resources, role catalogs, participant or overview instructions. Explicit editing upgrades only a draft; historical
accepted revisions are never rewritten. Focus uses the same navigation layout with **General**,
**Research**, **Answers**, and **Search priorities** categories and tall prompt editors. Priorities rank results; they never exclude parts of the record.

Changing profiles or closing an unsaved draft offers **Save / Discard / Cancel**.
Opening, inspecting and cancelling do not write a registry, snapshot, settings
file or case. Save needs no file picker, export, registration, technical version
entry, separate acceptance step or Git operation.

Saving does not rebind an existing case. When applicable, a separate confirmation
asks **Use these settings for this case?** with **Use settings / Not now** and
explains that existing summaries and answers will not be regenerated. An older
pin is identified inside Profile settings, not in the hamburger menu. The menu
contains no passive profile-status notices. If case application
fails after a successful save, the app reports **Profile saved; case settings
were not changed.** The saved profile is not rolled back unsafely.

With no existing case selected, RecordPrep remembers an explicit dropdown choice
in the private profile registry as the new-case default. The next launch restores
that choice, and Create files uses it for a new bundle. Save advances the remembered
revision for that specialty without a case-application confirmation or an old-case
write. Selecting a profile for an existing case does not replace this default;
existing bundles stay legacy or pinned.

RecordPrep's header has dim **Choose case bundle**, **Choose PDF(s)** and
**Clear current case** buttons, in that order. The trash button clears only the
current selection and displayed progress/activity; no PDF, bundle, case name or
generated artifact is deleted. It also drops pending layout/profile choices and
invalidates old file dialogs and case-bound profile drafts. Stop active work and
close the TOC editor before clearing; ordinary Model settings and Profile settings
remain usable without a case. Clearing drops the in-memory proposal but does not
forget the remembered new-case default or saved personal profile content.

Synchronized RecordPrep case metadata accepts ordinary owner-owned `0755`/`0775`
directories and `0644`/`0664` files, without chmod/repair. Symlinks, hardlinked or
nonregular files, foreign ownership, executable metadata files and world-writable
metadata remain rejected. Compare-and-swap and publication locking still protect
selection changes. These rules are case-specific: the accepted-profile store
continues to require owner-only directories/files. A missing pinned revision is
not silently substituted; explicitly selecting an available profile can replace
the pin without regenerating any output.

Focus proposes defaults but requires an explicit first-research choice, including
Existing settings. Active
preparation/research and changing case identities reject mutation. Selection
alone makes no model request, renames no case and regenerates nothing.

## Storage and releases

| Data | Location | Version controlled? |
| --- | --- | --- |
| Complete public specialties | `<package>/resources/practice_profiles/` | Yes |
| Evidence/citation/tool/output/publication safeguards | Application source/resources | Yes |
| Credentials, models, endpoints, workers, commands, recent cases | Existing private application settings | No |
| Personal profiles and edited built-ins | Private immutable snapshots | No |
| Current personal references, initialization and defaults | Private registry | No |
| Exact case instructions | Immutable private snapshot and existing case pin | No |

Each catalog is explicit: `practice_profiles.BUNDLED_PROFILES`. The current
catalog has one visible entry per identity, not a list of stored revisions.
An edited built-in keeps its visible name. Ordinary acceptance of bundled bytes
is not personal ownership. Exact known shipped content distinguishes historical
ordinary acceptance from real personal edits; optional registry metadata records
ownership and completed initialization only on explicit persistence.

Private roots are `$XDG_CONFIG_HOME/<application>/practice-profiles/registry.json`
and `$XDG_DATA_HOME/<application>/practice-profiles/snapshots/<digest>/` (normal
HOME defaults when unset). Files are private, content-verified and immutable to
the application. Unsafe paths, corrupt registries, unavailable snapshots and
explicitly configured missing defaults are errors, never reasons to reset or
silently substitute another profile. Browsing old output does not need its
instruction snapshot; new affected work does.

Save validates the complete draft with production compilers, checks the active
work guard, compares expected head/default state, publishes the snapshot, and
atomically updates references/ownership/initialization/default under the registry
lock. Repeated unchanged Save is idempotent. A failed publication may leave an
unauthorized orphan snapshot, never a selected profile. Concurrent changes keep
the draft and require reopening saved settings. Saving the default advances it;
clearing its preference returns to personal General, or bundled General.

A release can add a specialty without registration. Updated bundled guidance
does not overwrite personal edits, rebind case pins, rename cases or regenerate
outputs. Repository/Git changes are not instructions to refresh active cases.
Execution continues with validated frozen snapshots.

## Previous Dependency settings

The read-only resolver begins with complete shipped Dependency settings and
prepares an allowlisted in-memory personal candidate when previous customization
is applicable. The dropdown and editor share this resolution, so selecting a profile
does not bypass it. Opening does not migrate anything. First explicit Save or
dropdown selection persists privately and records initialization. An existing personal
profile wins and is never repeatedly overlaid.

Empty overrides inherit public guidance. Genuine prose is retained without
unnecessary stripping. Historical built-ins are recognized so retired output
instructions are not reattached as personal guidance. RecordPrep preserves
classification by task, historical case-name text (stored but inert), report/form guidance and known
structured naming rules, hearing/report topics and minute guidance. Extra summary
phase instructions and historical attendance choices are not imported. Ambiguous naming prose is retained with a
focused review notice: prose does not invent approved-title/catalog rules.
Focus preserves applicable prior research/answer prose beneath current safeguards,
not tools or runtime settings. No credentials, endpoints, paths, commands or
unrelated configuration fields are copied. Never promote this private candidate
into bundled files, fixtures, logs or commits.

Legacy prompt values remain available to compatibility loaders. The general
settings menu and window are now called **Model settings** in both applications,
distinct from **Profile settings**. Their existing model, credential, appearance
and machine controls remain; the rename does not change storage or action names.
Model settings no longer edits practice prompts or the retired direct-API sandbox controls. It
retains production classification API settings and agentic Pi models. RecordPrep's
Infer case uses the shared native-Pi model; its old direct-API page is removed.
End-user prompt testing, its action/window and request/payload paths are removed.
Historical recognition text remains deliberately intact for compatibility.

## Maintainer workflow for public specialties

1. Add a complete readable Markdown/JSON directory under each supporting app's
   own `resources/practice_profiles/` tree.
2. Add its directory name to that app's `BUNDLED_PROFILES` catalog.
3. Validate content, production compilers, component freshness and packaging.
4. Review and commit it as public application guidance; include it in a release.

Matching counterparts share a specialty identity, but own different instructions.
Never automatically promote a user's Save, private legacy prose or case material.
No chooser change or specialty-specific pipeline branch is needed within the
supported capability/policy contract. New capabilities still require code.
Low-level export/identity/validation helpers remain for maintenance and tests,
not lawyer-facing management controls.

## Contract and compatibility

The strict stdlib contract is vendored independently. Keep these six files
byte-identical: `profile_contract.py`, `profile_store.py`, `profile_artifacts.py`,
`profile_workflows.py`, `profile_editor_ui.py`, `profile_manager_ui.py`. Application
adapters/compilers stay independent. Shared conformance/workflow/managed-save
suites exercise both apps; do not introduce sibling runtime imports.

`profile_api` remains 1. Focus content schema remains 1. RecordPrep content
schema 2 adds `classification_tasks` (strict JSON keys `rt`, `ct`, `first_hearing`,
`first_minute`, `first_form`, `date_hearing`, `date_minute`) and `case_name` text,
retaining every schema-1 resource. Schema 3 keeps those task fields but removes
the four extra summary instruction resources. Schema 4 additionally removes roles
and participant instructions; historical schemas 1–3 remain readable, and all these
retired fields are inert in every stage's prompts and component fingerprints.
Schema 5 additionally removes overview instructions. Overview compilation selects
no profile resources; it follows the application method and runtime summary inputs.
Schemas 1–4 remain readable with historical overview prose inert. Common classification guidance is composed
with application-owned taxonomy and only the current task's guidance. Component
fingerprints isolate basic, first-page/correction and date guidance; caption
inference uses one application-owned, practice-neutral prompt and its own
source/model/output freshness marker. The native `recordprep-infer-case` skill
reads only private copies of the first three pages and writes only a candidate;
Python validates and publishes it with unchanged-input/selection checks. No
separate caption model or credential settings remain. Stored case-name guidance and legacy
`case_name_prompt` overrides are ignored, not rewritten. There is no case-name
prompt editor; caption inference preserves source names, initials/anonymization
and caption forms without assuming a specialty.
Credentials, first-three-page bounds, filename validation and guarded publication
remain application-owned. Selecting a profile never renames the case.

Schema-1 snapshots remain byte-preserved. Explicit caption inference uses the
same built-in prompt and shared native-Pi model for every case. Caption freshness
now requires the schema-2 marker bound to the source/model/contract/output;
existing names remain readable but may show pending until explicitly rerun.
Opening a case never renames it or migrates its data.
The retired report-scope field is an explicit exception: it remains readable but
no longer controls extraction. Explicit editing upgrades only an in-memory draft.
Old unversioned and v2 naming catalogs remain readable with their historical
runtime behavior and immutable bytes. Explicit editing folds their names, known
heading/code requirements and original prose into v3 naming instructions. Save or
selecting a new bundled revision is deliberate; existing case pins are not rewritten.
Prior private naming prose is preserved for review alongside the approved entries;
no model or heuristic invents a new allowlist from arbitrary prose.

Manifests reject unknown/missing fields, unsupported capabilities/versions,
noncanonical/traversing/executable resource paths, duplicate JSON keys, unsafe
links, oversized files and invalid Unicode. Resources are frozen and verified by
content hash. Topics use stable bounded IDs; historical role catalogs retain their
reader validation only. New participant metadata uses source-described role labels,
not specialty IDs. Naming retains historical source/approved-title modes; profile-bound attendance
uses a fixed complete-order source-evidence rule, not a selectable policy. There is no Formal proposals switch or heading-
based report cutoff. Complete reports remain available for material recommendations,
requested relief and later discussion; guidance distinguishes proposals from actual
orders and omits routine boilerplate unless consequential. Quote/citation checks and
publication guards remain. Old `report_scope` and `attendance` fields are accepted but ignored and
omitted from an edited draft on explicit Save; inspection does not rewrite snapshots,
private configuration or cases. Existing outputs are not regenerated automatically;
report freshness requires explicit rerunning under the new complete-source contract.
Profiles cannot weaken evidence, citations, source scope, tools, output schema or
publication safeguards.

New participant schema 4 (with 2/3 compatibility), source-map schema 3,
digest format 2/row 3/metadata 5, minute checkpoint 4 (with 1–3 compatibility)
and saved-answer schema 2 remain descriptive reader contracts,
not instruction authority. Legacy readers and frozen fixtures remain intact.
Old private snapshots and generated output are never rewritten on inspection.
The changed participant/minute contracts make affected profile-bound work pending
until explicitly rerun; historical role edits alone no longer change stage components.
Prepared provenance and research choices remain separate; different specialties
are not intrinsically structural incompatibility. Source pages remain authority.

Read-only diagnostics: `focus profiles validate PATH --json` and
`python -m recordprep profiles validate PATH --json`. Invalid content returns a
sanitized structural issue, not prompt text. Source archives/wheels must include
all catalog directories and their resources. Full RecordPrep native-Pi deployment
still uses its own source `.pi/` tree; a Python wheel is not a native-Pi installer.

For direct wheel installation with uv, use **`--link-mode copy`**. uv's default
cache hardlinks fail the resource validator's single-link safety check. Do not
relax the validator or modify cache/installed resources to work around this.
The supported source installation reads its own regular tracked resource files.

The [maintainer contract reference](practice-profile-contract.md) records manifest,
hash, size, storage and instruction-free artifact details.

See [validation and limits](practice-profiles-validation.md). Use disposable
source/environment overrides through UvEnvironments, synthetic records and isolated
HOME/XDG locations. Never test against real private configuration or case files.
