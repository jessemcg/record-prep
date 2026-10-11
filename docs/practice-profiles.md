# Practice profiles — contract v1 and implementation status

This is the initial canonical interoperability specification. RecordPrep carries
an explicitly versioned copy. The apps own their resources and storage separately;
there is no profile repository, shared runtime dependency, sibling import, or
launch-time synchronization. Common contract code and conformance fixtures are
vendored in each app and must be reviewed/tested together when changed.

## Current status: implemented, with synthetic cross-app acceptance

Implemented:

- GTK-independent strict validation and immutable in-memory drafts.
- General Court Record and California Juvenile Dependency resources inside each
  app's package, using the same format as an external specialty.
- App-owned, explicitly accepted content snapshots, a compare-and-swap revision
  registry, independent defaults, retained older revisions, and hash verification.
- Stage-specific resource selection and fingerprints that include caller-supplied
  core contract bytes. This compiler selects data, not executable instructions.
- Bounded specialty identity serialization/parsing for independent counterpart authoring.
- Read-only `profiles validate PATH --json` diagnostics in both existing CLIs.
- Synthetic conformance/security/storage tests and a frozen RecordPrep dependency
  category/role baseline. Dependency categories retain exact tracked guidance.
- Reviewed Dependency naming catalogs: 16 report names and six title/code form
  rules. General uses source-supported titles. Both RecordPrep bundled profiles
  are now version 1.1.0; naming resource schema v2 is independently versioned.
- RecordPrep's `document_naming.py` compiles a frozen profile into application-owned
  report/form response contracts and subordinate practice guidance. Its optional
  image-classifier adapter uses those exact prompts/keys, not schema inference
  from editable prose. Explicitly bound cases use it in the actual classifier
  workers, with explicit GUI selection and new-case creation bindings.
- Explicit TOC/boundary runs retain unnamed reports (including one-page reports)
  with provisional labels and review metadata; unknown first-page forms receive
  provisional TOC labels. Existing readable artifacts are not changed on opening.

- Reader-first support for source-map/participant schema 3, digest Markdown format
  2/row schema 3, digest/final metadata 5, and minute checkpoint 2. Readers use
  bounded artifact-recorded descriptors rather than installed practice guidance.
- Focus's helper reports preparation selection separately from publication/map
  provenance and emits mismatch notices. Sidecar reads are bounded and reject
  unsafe links; they cannot install/accept profiles or create a case pin.

Runtime and authoring integration:

- RecordPrep has explicit accepted case bindings and serialized publication;
  classification/naming, TOC/boundaries, summary/minute and native producers use
  pinned resources and component/source/runtime freshness. Source-map v3 is
  published deterministically by Python. CT-only scope remains explicit.
- Focus has private explicit case research choices, neutral research composition,
  literal ranking preferences, staged resources, helper/session/follow-up pins,
  and source-change rejection. First Q&A use requires explicit research choice,
  including an explicit Legacy choice, regardless of defaults or counterparts.
- Saved-answer schema 2 records instruction-free research and consumed preparation
  provenance. Old answers remain readable and visibly legacy/unassigned; recorded
  identities and different-specialty notices do not resolve current instructions.
- Byte-identical `profile_workflows.py` provides cancellable in-memory editors,
  new-folder atomic no-overwrite export, identity exchange, reviewed registration,
  and stale editor/head/external-edit rejection. Independently vendored GTK editors
  and managers expose these transactions, effective previews, ordered catalogs,
  closed policies, identity import/export and active-work guards. A failed acceptance
  may retain an unaccepted export; it never changes defaults or case selections.
- Explicit private-customization copying preserves allowlisted prose in reviewable
  drafts, excludes runtime/credential fields, and leaves original settings untouched.
  Prose itself must be reviewed for private details before sharing.
- General Court Record is the built-in new-context default. RecordPrep accepts/binds
  it only during explicit Create files for a previously nonexistent bundle, or uses
  an explicit in-memory new-case choice/configured default. Existing bundles stay
  unassigned or retain their pin. Focus proposes its default but always requires
  first-use confirmation; opening a case does not register or bind a profile.
- Native profile stages have a closed tool boundary: prepared private candidates,
  bounded input reads, no shell/canonical writes, fixed participant validation, and
  application-owned publication. Focus rechecks its pin at final-answer capture.

Civil, Dependency and a GUI-authored third specialty pass synthetic mixed RT/CT
production through the actual application publishers, then independent Focus
context/lookup/search and research-pin acceptance. Both wheels contain valid
bundled resources; the supported source deployments retain their own native Pi
resources. See [validation evidence and limitations](practice-profiles-validation.md).
Legacy prompts/settings remain effective for unassigned compatibility contexts;
explicit profiles do not layer those old prompts over profile guidance.
No private settings are migrated. Opening a case remains read-only.

The naming catalogs were reviewed with Jesse's explicit authorization; he declared
these prompt fields non-sensitive and approved bundling their rules. Only the two
allowlisted naming prompts were reviewed, not other configuration fields. The
approved correction changes `Parential` to `Parental` in the new ICWA-020 output
name and matching title. Live `config.json` was not rewritten. The private
customization export/review flow is explicit and has not been run against personal settings.
These results validate application contracts, not live-model accuracy or equivalence
on private matters. No real case or personal customization was regenerated.

## Using profiles without JSON or Git

1. Open **Research** in Focus or **Preparation / New case** in RecordPrep, or
   **Practice Profiles** in Settings. The manager shows the case choice, recorded
   preparation, viewed revision and independent new-context default.
2. Choose **Create from General**, or select a bundled specialty and **Duplicate**.
   Edit its name/version, Markdown guidance and the structured fields. RecordPrep
   exposes ordered categories/roles, naming rules and closed evidence policies;
   Focus exposes research/answer guidance and literal ranking terms. Stable IDs
   are generated by the app. **Validate** checks the entire draft; **Preview**
   shows the actual compiler output, including protected application contracts.
3. **Save & Accept** writes a complete new folder and accepts that exact revision.
   **Export** writes only the folder. Neither selects a case or changes a default.
   Existing destinations are never overwritten; **Cancel** discards the draft.
   Select **Use for this case** separately. End a live research session first;
   active preparation also prevents profile changes.
4. Set **Default for new contexts** only when desired. RecordPrep binds it only
   when Create files makes a previously nonexistent bundle (an explicit pending
   choice takes priority). Focus always requires confirmation before a case's
   first Q&A, including explicit Legacy. Old contexts do not silently upgrade.
5. Use **Register folder** for an app-specific external profile. Inspect the
   reviewed name/version/hash and effective instructions before accepting.
   **Review external edits** rereads a registered source folder; stale reviews
   are rejected. Saved case pins still reference their accepted older revision.
6. To create a counterpart, **Export identity** in one app and **Import identity**
   in the other. Choose a local starting template, author that app's guidance,
   accept it and select it separately. Identity exchange contains no instructions,
   settings or case data. Existing identities are not overwritten.
7. **Copy legacy customization** is an explicit private draft, not a migration.
   Review its prose for private details and historical instruction conflicts.
   Credential/model/endpoint/path fields are excluded; RecordPrep case-name
   formatting remains an application setting. Recognized historical built-in
   summary prompts are not mislabelled as personal overrides.

Missing instructions are visibly unavailable. Restore/register the exact missing
revision or explicitly choose an alternative; General is never a silent substitute.
Changing preparation may require explicit upstream reruns and model charges, but
selection itself never processes records or relabels prior output. Old artifacts
and saved answers keep their recorded preparation/research provenance.

## Reader-first artifact contracts

`profile_artifacts.py` is vendored byte-identically in both apps. It has no
filesystem access, profile-store access, acceptance, or instruction loading.
The following metadata is descriptive, never a grant to load a profile.

- A preparation selection is exactly `{schema_version: 1, profile_ref: ProfileRef}`,
  with application `recordprep`. Its app-owned location is
  `.recordprep/practice-profile.json`; reading a case does not create it.
- Preparation provenance is exactly `{schema_version: 1, profile_ref: ProfileRef,
  components: {stage: sha256}}`. Components are a nonempty subset of RecordPrep's
  application-owned stages, with lowercase 64-character SHA-256 values. No paths,
  prompts, credentials, or extra fields are accepted. The published sidecar is
  `artifacts/practice_profile_provenance.json`.
- Structural category catalogs are ordered lists of exactly `{id, title}`; role
  catalogs have `counsel` and `participants` lists of exactly `{id, label}`. Lists
  have 1–128 unique bounded identifiers; labels are trimmed, nonblank, single-line
  strings up to 160 characters. Guidance is explicitly rejected. Role groups
  retain required `unknown` and `other` fallbacks.
- Participant schema 3 retains schema 2's hearing, attendance, witness/conflict,
  and examination structure, adding `role_catalog` and `profile_provenance` with
  a `participants` component. Roles validate against that recorded catalog;
  participant role labels must agree. Schema 2 uses frozen legacy role IDs, never
  a current profile. Native v3 evidence-path/examination safeguards are retained
  in the shared reader. Profile-bound native producers use private candidates,
  the accepted role catalog and independent application validation/publication.
- Source-map schema 3 adds `preparation_provenance`. If it includes a participant
  index, that index must be valid schema 3. An empty embedded hearing array is
  readable for CT-only scope without pretending that indexing occurred. Legacy
  map schemas 1/2 remain readable in Focus. Unknown future versions and invalid
  profile metadata fail explicitly before research tools use the map; ordinary
  text/summary browsing does not need a profile instruction snapshot.
- Digest Markdown format 2 adds a document-header `profile_metadata` containing
  exactly `category_catalog` and `profile_provenance` (with the appropriate
  extraction component). Its rows use schema 3. Parsing carries that metadata
  with each in-memory row and with the document even for zero rows; serialization
  rejects mixed catalogs/revisions. Canonical escaping/quote grammar and exact
  reserialization checks remain intact. Legacy format 1/row 2 uses frozen
  category titles/order without loading current category guidance.
- Digest metadata 5 repeats the header's `profile_metadata`, which must match;
  final metadata 5 has its own `profile_provenance` with the synthesis component.
  Both retain the existing content hashes and record Markdown format 2. Integrity
  does not imply current-generation freshness: the legacy runner deliberately
  cannot mark these profile-era artifacts current or silently downgrade them.
- Minute checkpoint 2 retains the existing row/hash wrapper and adds
  `attendance_policy`, `role_catalog`, and `profile_provenance` with a `minutes`
  component. Rows replace `parents` with `appearances` containing exactly
  `{person, role_id, status, evidence}`. Each evidence entry is `{file_page, text}`;
  explicit presence/absence requires recorded evidence. These are structural
  reader checks, not semantic proof of attendance. Generic rendering does not
  introduce parent terminology. Schema 1 remains unchanged and readable.

Focus `preparation_context.py` treats map provenance as provenance of the map
actually used by research, not the case's newly selected but unprocessed profile.
Invalid sidecars and selection/publication mismatches appear as structured notices;
no profile folder is resolved and no external instructions are accepted by this
reader. Generation and research use separately accepted local snapshots, GUI
choices and pinned preflight/freshness checks. Missing instructions block new
profile-dependent work, not reading old artifacts.

## Ownership and identity

Each profile folder targets exactly one application: `focus` or `recordprep`.
Corresponding specialties share a stable `specialty_id`, not a full content hash.
Built-ins use `general-court-record` and `california-juvenile-dependency`.

A `ProfileRef` has exactly:

```json
{
  "specialty_id": "california-juvenile-dependency",
  "application": "focus",
  "version": "1.0.0",
  "profile_api": 1,
  "content_sha256": "<64 lowercase hexadecimal characters>"
}
```

Application and content digest identify the effective resource revision. A shared
specialty ID is an association, not evidence of compatible artifacts or equivalent
instructions. Different app-specific hashes/versions are expected. Focus schema-2
answers record their own ProfileRef separately from preparation provenance;
artifact-embedded descriptors, not current Focus guidance, govern display of
prepared categories and roles.

## Manifest

Each folder has a UTF-8 `profile.json` containing exactly these keys:

```json
{
  "schema_version": 1,
  "profile_api": 1,
  "specialty_id": "my-specialty",
  "application": "focus",
  "display_name": "My Specialty",
  "description": "An independently authored research profile.",
  "version": "1.0.0",
  "required_capabilities": ["research-v1"],
  "resources": {
    "research": "research.md",
    "answer_guidance": "answer-guidance.md",
    "search": "search.json"
  }
}
```

Both version integers must be exactly 1 (booleans are not integers here).
Identifiers match `[a-z][a-z0-9_-]{0,95}`. Display names/labels/titles are at most
160 characters; descriptions at most 4096; version names at most 64. Description
may be empty. Prompt Markdown is nonempty UTF-8, and preserved byte-for-byte.
JSON duplicate keys, nonfinite constants, unknown fields, missing fields,
unsupported versions/capabilities, and invalid Unicode are rejected.

For `recordprep`, required capabilities are exactly `["preparation-v1"]` and
resources contain these required keys:

| Key | Format | Purpose |
| --- | --- | --- |
| classification | Markdown | Domain guidance, not structural response schema |
| naming | JSON | Source-title/approved-title preferences |
| roles | JSON | Separate counsel and participant catalogs |
| hearings, reports | JSON | Ordered category catalogs |
| policies | JSON | Supported scope and attendance choices |
| hearing_extraction, report_extraction | Markdown | Domain extraction relevance |
| hearing_synthesis, report_synthesis | Markdown | Domain synthesis guidance |
| minutes, participants, overview | Markdown | Stage-specific domain guidance |

The actual filenames are explicit relative manifest paths, not discovery patterns.
Profiles cannot name executable stages, tools, commands, endpoints, models, or
credentials. Undeclared files are never loaded. An executable reference is rejected;
there is no package installation or network retrieval.

### Structured declarations

All JSON objects reject unknown fields; catalogs reject duplicate IDs.

- Categories: ordered array of `{id, title, guidance}`, 1–128 entries.
- Roles: `{counsel: [...], participants: [...]}`; each is an ordered array of
  `{id, label, guidance}`, 1–128 entries. Each catalog requires `unknown` and `other`.
  Legacy dependency IDs remain available in addition to those explicit fallbacks.
  Guidance is nonempty and at most 8192 characters per entry.
- Naming schema v2: `{schema_version: 2, mode, report_titles, form_rules,
  report_guidance, form_guidance}`. Mode is `source_title` or `approved_titles`.
  Report titles are bounded literal lists. Each of 0–256 form rules has exactly
  `{name, title, code}`: canonical output name, required matching title, and
  required form code. Names and codes are unique case-insensitively; values are
  nonblank trimmed single-line strings up to 160 characters. Both title and code
  must appear on the same supplied first page under v2 approved-title mode.
  Guidance fields are separate editable prose (up to 8192 characters each) rather
  than a second copy of the catalogs. The compiler renders a single effective
  prompt from the declarations. Source-title mode does not require a form code.
  The older unversioned `{mode, report_titles, form_titles, guidance}` shape remains
  readable/compilable as v1 without inventing code requirements or changing its
  content digest. Unsupported naming versions fail clearly; no automatic snapshot
  migration occurs.
- Policies: `{report_scope, attendance}`. Report scope is
  `include_attributed_proposals` or `exclude_formal_proposals`; attendance is
  `explicit_complete_order` or `legacy_first_page_parents`. These are closed
  application-implemented choices, not algorithms supplied by a profile.
- Focus search: `{query_terms, document_terms, passage_terms, later_history_terms}`.
  Each list has 0–256 literal terms, each nonblank, trimmed, single-line, at most
  160 characters, and unique case-insensitively. They are **not** regexes and must
  never be compiled as regex syntax by consumers. Preferences may influence
  ranking, not scope or eligibility. The General profile has empty specialty lists;
  core lexical/date/document ranking remains an application responsibility.

## Paths and size limits

Manifest and each resource: at most 256 KiB. At most 256 referenced files, with
manifest plus resources at most 2 MiB. Relative paths have at most eight components
and 240 characters; absolute paths, traversal, backslashes, noncanonical paths,
wrong extensions, reused resource paths, and manifest self-references fail.

Descriptor-relative `O_NOFOLLOW` reads reject symlink resources/directories,
nonregular files (including FIFOs), hardlinks, and executable-mode resources.
Reads are bounded, check file changes during reading, and reread declared inputs
before returning the frozen draft. No case folder or current directory is scanned
for profiles. Explicit validation does not authorize execution or acceptance.

## Hashing, compilation, and immutability

Full content SHA-256 starts with `court-record-profile-v1\0`. Files are sorted by
relative path. For each file append the UTF-8 path byte length as a four-byte
big-endian integer, its path bytes, content byte length as an eight-byte big-endian
integer, and exact content bytes. The manifest participates, including application
identity, so versions/display labels/formatting also change full provenance.

`ProfileSnapshot` contains a frozen ProfileRef and a tuple of `(path, bytes)`.
Parsed JSON accessors return copies. It has no live reference to the original
folder. Acceptance revalidates the draft and its claimed hash. On disk, accepted
snapshots are application-immutable, not an OS-level immutable-file guarantee:
the owner can edit files, but hash validation rejects altered snapshots rather
than silently authorizing a new revision.

`compile_stage_profile(snapshot, stage, core_contract=...)` selects only code-owned
resource dependencies. It returns frozen resource bytes and a component digest.
Markdown remains exact; structured declarations use deterministic sorted JSON.
The component digest includes application, stage, and nonempty caller-supplied
core bytes, but not unrelated display metadata or the whole-profile digest.
Report extraction includes only the `report_scope` policy; minutes includes only
`attendance`, so an attendance change does not stale report extraction.

The generic compiler selects resources; RecordPrep's naming-specific compiler now
builds exact prompts for both preview and the optional image-classifier adapter.
It records both a naming component fingerprint (core + complete naming resource)
and the exact prompt hash. Python fixes the response keys, requires exact approved
output-name membership, rejects malformed values, and validates calendar dates.
Unresolved names remain empty; a provisional display label is a separate pipeline
responsibility. Membership validation does not prove that a heading/code was
actually visible on the image: evidence interpretation still depends on the model.

Runtime compilers combine profiles with application-owned fidelity/safety/tool
contracts. Freshness includes source bytes, relevant models, upstream artifacts,
policy implementations and validators. Component and integrated runner tests cover
stage-local reuse, zero-call unchanged resumes and preservation of prior finals on
failure. No paid regeneration is triggered by selection, acceptance or opening.

## Explicit accepted storage

Default roots, selected by each app independently:

- `$XDG_CONFIG_HOME/<application>/practice-profiles/registry.json`
- `$XDG_DATA_HOME/<application>/practice-profiles/snapshots/<digest>/`

Unset XDG roots use `~/.config` and `~/.local/share`. Relative overrides fail.
Neither legacy source-root `config.json` nor the other app's store is used.
Construction, validation, registry reads and snapshot loads do not create files.
Directories must be private (`0700`); files are published private (`0600`). Unsafe
permissions, symlinks or corrupt registries cause errors, never automatic repair.

`ProfileStore.accept_profile(draft, expected_previous_digest=..., source_path=...)`
uses a private per-store lock and compares the accepted head for the specialty.
A stale editor loses the comparison and must review/reload. A new specialty uses
`None`. Publication writes and fsyncs a complete snapshot in a private staging
directory, renames it, then atomically commits the registry. On failure, an orphan
snapshot may remain but is not authorized; no prior snapshot/default is replaced.
The registry retains accepted references plus optional private source locations,
current heads and an optional default. There is a bounded 256-revision registry;
capacity errors are explicit, with no automatic pruning.

`load_profile_snapshot(ref)` requires a local accepted reference and revalidates
snapshot hashes and permissions. A reference in a case cannot install instructions.
`set_default(ref)` is explicit and affects only this app's default. Accepting a new
revision does not advance a default pinned to an older one. The store API does not modify cases.

The GUI Save transaction separately validates the complete draft, checks the source
folder and accepted head, atomically publishes a new complete folder without
replacement, and only then accepts the reviewed bytes. It never writes back to an
existing source folder. Cancellation writes nothing; stale review requires reopening.
Explicit re-registration can attach a source folder to an already accepted revision.

## Identity exchange and authoring

`identity_descriptor(snapshot)` returns a strict JSON descriptor with only
`schema_version: 1`, `specialty_id`, `display_name`, and `description`.
`parse_identity_descriptor(bytes)` applies the manifest identity/size restrictions.
It is not a profile, contains no resources or paths, and is never accepted as one.

The GUI supports Create from General/Duplicate with a fresh stable ID,
full app-specific editors, validation/preview, safe new-folder export, registration
and explicit selection. Bundled profiles are read-only. Identity import retains
the specialty ID while creating the other app's independent guidance from a local
template. Existing-ID conflicts need explicit review, not overwrites. Neither
app should imply that the other half exists merely because an identity was shared.

## Validation and development

Read-only diagnostic (no GTK, settings writes, model calls or acceptance):

```sh
focus profiles validate /explicit/profile/folder --json
python -m recordprep profiles validate /explicit/profile/folder --json
```

Return 0 for valid, 1 for invalid. JSON includes `valid`, sanitized `{code, location}`
issues, and optional `profile_ref`; never prompt text or source paths. Local runtime
users should invoke these through the maintained project environment helper.

`tests/test_practice_profiles.py` is identical in both repos and uses synthetic
profiles and temporary stores. `tests/fixtures/practice_profiles/conformance-v1.json`
pins hashes for the same app-specific synthetic inputs. RecordPrep additionally
has `test_profile_legacy_baseline.py` and `legacy-dependency-v1.json`, preserving
tracked category IDs/titles/guidance, roles, and current summary schema versions.
Update tests to point to explicit frozen legacy readers when producers advance;
do not replace legacy fixture contents merely to make new behavior pass.

`tests/acceptance_profile_workflows.py` exercises real GTK widgets, signals,
compilers and storage with synthetic data; only native file-picker completion is
simulated. This is separate from the ordinary offline suite. Run in an isolated
HOME/XDG environment with `G_DEBUG=fatal-criticals`. Its optional output variables
export GUI-authored synthetic profiles/identity for the separate RecordPrep
`acceptance_profile_pipeline.py` and Focus `acceptance_profile_consumer.py` scripts.
Only synthetic case artifacts and an identity descriptor cross app boundaries;
no sibling runtime imports or preparation instructions are required by Focus.
Passing these checks is not a claim of model quality. Paid quality evaluation
needs separate approval.
