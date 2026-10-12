# Shipped practice profiles and personal settings

RecordPrep and Focus each ship **General Court Record** and **California Juvenile
Dependency**. General is the new-case default. Dependency is a complete public
specialty, useful without anyone's private configuration. Each app owns its
instructions independently; there is no profile repository, download, sibling
package import or automatic cross-app synchronization.

## Choose, edit, save

The main-window preparation/research button opens a compact chooser. Names wrap
in full; a check marks the current choice. Select a profile and **Use profile**,
or open **Profile settings…**. Focus also offers **Existing settings** for an
explicit compatibility choice before a case's first research session.

Profile settings contains a full-width selector, **New profile…**, **Use for new
cases**, the substantive settings, **Save**, and **Cancel**. A built-in opens with
complete populated settings; personal settings appear in place of its baseline.
New profile asks only for a name and a starting profile (General by default).
Identifiers are generated internally. Cancelling a draft saves nothing.

RecordPrep groups case naming, document classification/naming, hearing/report/
minute summaries, participants/witnesses and case overview on one scrollable page.
Summary topics are expandable cards with editable names/instructions and add,
remove and reorder actions. Renaming a topic does not change its stable ID.
Topics guide capture from each document, not required headings in the narrative.
**Reviewing each document** and **Writing the summary** stay beside their topics.
Focus groups research instructions, answer-writing instructions and search
priorities. Priorities rank results; they never exclude parts of the record.

Changing profiles or closing an unsaved draft offers **Save / Discard / Cancel**.
Opening, inspecting and cancelling do not write a registry, snapshot, settings
file or case. Save needs no file picker, export, registration, technical version
entry, separate acceptance step or Git operation.

Saving does not rebind an existing case. When applicable, a separate confirmation
asks **Use these settings for this case?** with **Use settings / Not now** and
explains that existing summaries and answers will not be regenerated. An older
pin is identified as **This case uses earlier settings.** If case application
fails after a successful save, the app reports **Profile saved; case settings
were not changed.** The saved profile is not rolled back unsafely.

RecordPrep holds a new-case choice in memory until Create files creates a new
bundle. Existing bundles stay legacy or pinned. Focus proposes defaults but
requires an explicit first-research choice, including Existing settings. Active
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
is applicable. The chooser and editor share this resolution, so Use profile does
not bypass it. Opening does not migrate anything. First explicit Save or Use
profile persists privately and records initialization. An existing personal
profile wins and is never repeatedly overlaid.

Empty overrides inherit public guidance. Genuine prose is retained without
unnecessary stripping. Historical built-ins are recognized so retired output
instructions are not reattached as personal guidance. RecordPrep preserves
classification by task, case-name guidance, report/form guidance and known
structured naming rules, hearing/report topics and phase guidance, minutes and
effective historical attendance. Ambiguous naming prose is retained with a
focused review notice: prose does not invent approved-title/catalog rules.
Focus preserves applicable prior research/answer prose beneath current safeguards,
not tools or runtime settings. No credentials, endpoints, paths, commands or
unrelated configuration fields are copied. Never promote this private candidate
into bundled files, fixtures, logs or commits.

Legacy prompt values remain available to compatibility loaders. Ordinary Settings
no longer edits those prompts or the retired direct-API sandbox controls. It
retains production classification/case-name API settings and agentic Pi models.
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
retaining every schema-1 resource. Common classification guidance is composed
with application-owned taxonomy and only the current task's guidance. Component
fingerprints isolate basic, first-page/correction and date guidance; caption
inference uses its own compiler and source/model/output freshness marker.
Credentials, first-three-page bounds, filename validation and guarded publication
remain application-owned. Selecting a profile never renames the case.

Schema-1 snapshots remain byte-preserved and compile as before, including
historical caption behavior. Explicit editing upgrades only an in-memory draft.
Old unversioned naming catalogs remain readable; known structured title/code
rules can be retained on edit, while unresolved historical titles remain visible
in guidance with a review notice rather than invented rules.

Manifests reject unknown/missing fields, unsupported capabilities/versions,
noncanonical/traversing/executable resource paths, duplicate JSON keys, unsafe
links, oversized files and invalid Unicode. Resources are frozen and verified by
content hash. Topics/roles use stable bounded IDs; roles retain unknown/other
fallbacks; naming uses closed source/approved-title modes; scope/attendance use
only application-implemented policies. Profiles cannot weaken evidence, citations,
source scope, tools, output schema or publication safeguards.

Existing participant/source-map schema 3, digest format 2/row 3/metadata 5,
minute checkpoint 2 and saved-answer schema 2 remain descriptive reader contracts,
not instruction authority. Legacy readers and frozen fixtures remain intact.
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
