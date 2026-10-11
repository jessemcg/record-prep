# Practice profiles — contract v1 and implementation status

This is the initial canonical interoperability specification. RecordPrep carries
an explicitly versioned copy. The apps own their resources and storage separately;
there is no profile repository, shared runtime dependency, sibling import, or
launch-time synchronization. Common contract code and conformance fixtures are
vendored in each app and must be reviewed/tested together when changed.

## Current status: foundation, not an activated migration

Implemented:

- GTK-independent strict validation and immutable in-memory drafts.
- General Court Record and California Juvenile Dependency resources inside each
  app's package, using the same format as an external specialty.
- App-owned, explicitly accepted content snapshots, a compare-and-swap revision
  registry, independent defaults, retained older revisions, and hash verification.
- Stage-specific resource selection and fingerprints that include caller-supplied
  core contract bytes. This compiler selects data, not executable instructions.
- Bounded specialty identity serialization/parsing for future counterpart authoring.
- Read-only `profiles validate PATH --json` diagnostics in both existing CLIs.
- Synthetic conformance/security/storage tests and a frozen RecordPrep dependency
  category/role baseline. Dependency categories retain exact tracked guidance.

**Not yet implemented:** profile-aware generation or research, new artifact
readers/publishers, case selection, GUI profile management/authoring, customization
export, external-change review, complete legacy readers, or a default transition.
No profile is automatically registered or selected. Existing application behavior,
private settings and artifact formats are unchanged. The new registry APIs are
not called by application startup or existing settings-save flows.

The resource sets are preparation for integration, not a claim of model-quality
or full dependency-workflow equivalence. The existing tracked naming prompts
refer to approved title lists, but no such catalog is present in tracked source.
The bundled Dependency starter therefore uses source-supported titles and an
empty catalog; it does **not** claim to reproduce a private whitelist. Before any
real profile transition, the planned explicit customization export/review flow
must preserve private prompts and allow the user to supply reviewed title lists.
No private configuration was read to seed these resources.

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
instructions. Different app-specific hashes/versions are expected. Future Focus
answers must record their own ProfileRef separately from preparation provenance;
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
- Naming: `{mode, report_titles, form_titles, guidance}`. Mode is `source_title`
  or `approved_titles`. Title catalogs are bounded literal lists. Unknown titles
  must not remove a detected document in the future pipeline integration.
- Policies: `{report_scope, attendance}`. Report scope is
  `include_attributed_proposals` or `exclude_formal_proposals`; attendance is
  `explicit_complete_order` or `legacy_first_page_parents`. These are closed
  application-implemented choices, not algorithms supplied by a profile.
- Focus search: `{query_terms, document_terms, passage_terms, later_history_terms}`.
  Each list has 0–256 literal terms, each nonblank, trimmed, single-line, at most
  160 characters, and unique case-insensitively. They are **not** regexes and must
  never be compiled as regex syntax by future consumers. Preferences may influence
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

The compiler does not yet build model prompts. Pipeline integration must combine
these data with core fidelity/safety/tool contracts and include source, model,
upstream artifact, and policy implementation dependencies in actual freshness
checks. Tests of this API are not tests of integrated regeneration behavior.

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
revision does not advance a default pinned to an older one. No API modifies cases.

This is not yet an editable-folder save transaction. Future GUI Save must separately
validate the full draft, check the source-folder revision, safely publish resource
edits, and only then call acceptance. The acceptance API freezes reviewed bytes;
it does not write back to the source folder.

## Identity exchange and future authoring

`identity_descriptor(snapshot)` returns a strict JSON descriptor with only
`schema_version: 1`, `specialty_id`, `display_name`, and `description`.
`parse_identity_descriptor(bytes)` applies the manifest identity/size restrictions.
It is not a profile, contains no resources or paths, and is never accepted as one.

The future GUI must support Create from General/Duplicate with a fresh stable ID,
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

Still required before activation: reader-first schema integration, neutral core
prompt extraction, classification/schema-vocabulary reconciliation, unknown-title
range preservation, per-stage generation/preflight fingerprints, independent
Focus session pinning, GUI creation/counterpart/export/review, private customization
migration through application flows only, and complete synthetic producer/consumer
and actual GUI acceptance. Paid quality evaluation needs separate approval.
