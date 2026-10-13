# Practice-profile maintainer contract

See [the ordinary profile workflow](practice-profiles.md) and
[validation/limits](practice-profiles-validation.md). This reference describes the
independently vendored API, not additional end-user management steps.

## Identity and manifest

A profile targets exactly one application. Corresponding specialties may share a
`specialty_id`, never instructions or full content hashes. Built-ins use
`general-court-record` and `california-juvenile-dependency`.

A ProfileRef has exactly `specialty_id`, `application`, `version`, `profile_api`
(equal to 1), and `content_sha256` (64 lowercase hexadecimal characters).
An identity descriptor has exactly `schema_version: 1`, `specialty_id`,
`display_name`, and `description`. It contains no instructions, paths or runtime
settings and cannot authorize acceptance or instruction loading.

`profile.json` has exactly `schema_version`, `profile_api`, `specialty_id`,
`application`, `display_name`, `description`, `version`, `required_capabilities`,
and `resources`. Booleans are not accepted as version integers. Identifiers match
`[a-z][a-z0-9_-]{0,95}`. Names/labels/titles are at most 160 characters,
descriptions 4096, version strings 64. Description may be empty. Guidance is
nonempty UTF-8 and is preserved byte-for-byte.

Focus content schema 1 requires capability `research-v1` and `research`,
`answer_guidance` (Markdown), and `search` (JSON). RecordPrep requires
`preparation-v1` and:

| Resource | Format |
| --- | --- |
| classification | Markdown |
| naming, roles, hearings, reports, policies | JSON |
| hearing_extraction, report_extraction | Markdown |
| hearing_synthesis, report_synthesis | Markdown |
| minutes, participants, overview | Markdown |
| classification_tasks (content schema 2) | JSON |
| case_name (content schema 2) | Markdown |

RecordPrep schema 1 retains its old required resources/compilation. Schema 2 adds
exact task keys `rt`, `ct`, `first_hearing`, `first_minute`, `first_form`,
`date_hearing`, `date_minute`. Only the current task is composed beneath the
application's protected classification contract. Caption inference uses its own
resource/component; schema-1 caption behavior is unchanged. Editing an old draft
may upgrade it, but never rewrites the accepted snapshot.

## Structured resources

Every object rejects unknown fields, duplicate keys and nonfinite numbers.

- Categories: ordered arrays of `{id, title, guidance}`, 1–128 unique entries.
- Roles: `{counsel: [...], participants: [...]}` of `{id, label, guidance}`,
  1–128 entries per group, with required `unknown` and `other` fallbacks.
  Entry guidance is nonempty and at most 8192 characters.
- Naming v3: `{schema_version: 3, report_guidance, form_guidance}`. The instructions
  are the only stored source of approved names. Each line `- **Name**` (optionally
  followed by ` — matching requirements`) declares one approved output name.
  At most 256 entries per prompt, unique case-insensitively, at most 160 characters
  each; malformed bold entries, duplicate names and unknown fields are rejected.
  Empty catalogs intentionally accept no names. Python derives exact membership
  from these same prompt entries; no second catalog is injected into the request.
  Form heading/code interpretation remains model work, not something membership
  validation proves. Schema/first-page/evidence/date/publication guards remain
  application-owned. Opening an old profile converts only the editor draft; an
  explicit save publishes a new revision, never a rewrite of historical bytes.
- Legacy naming v2: `{schema_version: 2, mode, report_titles, form_rules,
  report_guidance, form_guidance}`. Mode is `source_title` or `approved_titles`.
  Each of 0–256 form rules has exactly `{name, title, code}`, with names/codes
  unique case-insensitively. v2 approved forms require both title and code on the
  supplied first page. The unversioned `{mode, report_titles, form_titles,
  guidance}` shape remains readable without inventing code requirements.
- Policies: `{attendance}`, either `explicit_complete_order` or
  `legacy_first_page_parents`. For byte-preserving compatibility, old snapshots
  may also contain `report_scope`, validated as `include_attributed_proposals`
  or `exclude_formal_proposals` but never compiled or executed. The editor omits
  this retired field from new saved revisions, never from inspected snapshots.
  There is no heading-based report source cutoff.
- Focus search: `{query_terms, document_terms, passage_terms, later_history_terms}`,
  each 0–256 unique literal terms, at most 160 characters each. Never compile
  these as regexes or use them to filter source eligibility.

Profiles cannot declare tools, commands, models, endpoints, credentials or
executable stages. Output/evidence/citation/source/publication contracts stay in
application code. Names and topics are not mandatory narrative headings.

## Files, hashing and compilation

Manifest and individual resources are bounded to 256 KiB, at most 256 referenced
files and 2 MiB total. Relative paths have at most eight components and 240
characters. Reject absolute/traversing/noncanonical paths, backslashes, wrong
extensions, reused paths and manifest self-references. Undeclared files are not
loaded. Descriptor-relative `O_NOFOLLOW` reads reject symlinks, hardlinks,
nonregular or executable files, bound reads, check changes and reread inputs.
No discovery scans or downloads are authorized by validation.

Full SHA-256 begins with `court-record-profile-v1\0`. Sort files by relative path;
append each UTF-8 path length as four big-endian bytes, its path, content length
as eight big-endian bytes, then exact content. The manifest participates.
Snapshots freeze `(path, bytes)` pairs; parsed JSON accessors return copies.
Acceptance revalidates contents and the claimed hash. Owner edits to stored
snapshots cause verification failure, not automatic revision acceptance.

`compile_stage_profile(snapshot, stage, core_contract=...)` selects code-owned
resource dependencies. Markdown remains exact; structured content is canonical
JSON. Component hashes include application, stage and caller-supplied core bytes,
not unrelated display metadata or the whole-profile digest. Classification task
groups and caption guidance are isolated. Report extraction selects topics and
extraction guidance, not policies; minutes selects only attendance. Report runtime
freshness includes `complete-document-no-cutoff-v1`, so old cutoff-era extraction
requires explicit rerunning rather than being silently reused or regenerated.
Runtime freshness additionally binds source,
model, upstream artifacts and validators. Application compilers own exact response
keys, approved-name membership, date validation and publication.

## Private storage and managed Save

Default roots are `$XDG_CONFIG_HOME/<application>/practice-profiles/registry.json`
and `$XDG_DATA_HOME/<application>/practice-profiles/snapshots/<digest>/`, with
normal HOME defaults. Relative overrides fail. Directories/files are private
0700/0600. Inspection, validation, catalog and snapshot reads create nothing.
Unsafe permissions/paths or corrupt registries fail; no automatic repair.

The registry retains accepted references, heads, optional source references,
default, and optional personal/initialized/deleted identity lists. Older metadata remains
readable without inspection-time rewriting. Exact known shipped hashes identify
ordinary public acceptance; unknown private content is not replaced speculatively.

`ProfileStore.managed_save` validates the complete draft/production compilers,
checks the work guard, compares expected head/default under lock, publishes and
fsyncs immutable bytes, then atomically commits registry references and private
ownership/initialization/default metadata. It is idempotent for unchanged Save.
An interrupted write may leave an unauthorized orphan, never a selected revision.
Capacity is bounded to 256 accepted revisions; no automatic pruning. Saving the
current default advances it; explicitly clearing it returns to personal or public
General. Missing configured defaults are errors, not fallback permission.

`ProfileStore.delete_profile(ref, expected_default=..., can_modify=...)` hides a
user-created specialty using an optional `deleted` identity list, under the same
private lock and atomic publication rules. It checks the exact accepted head,
expected default and work/case guard before commit; built-in identities are
protected even if personally customized. Deleting the configured new-case default
clears it to General. Heads, accepted references, ownership metadata and immutable
snapshot bytes remain intact: historical pins still authorize their exact saved
instructions, while catalog discovery excludes deleted identities. Managed Save,
accept_profile and set_default reject a tombstoned identity rather than resurrecting
it from a stale editor. Deleted names can be reused with a new generated identity.
The user-facing adapter clears only matching no-case pending proposals, never an
existing case pin. There is no garbage collection, automatic migration or launch-time
write; deletion happens only after explicit confirmation.

Low-level `accept_profile`, explicit folder export/review and identity helpers
remain for maintainers/tests. Their acceptance/default semantics are distinct
from managed Save; they are not ordinary GUI controls. Neither storage API
silently selects a case. The separate explicit case transaction uses its own
CAS/root/work guards. Saved success survives failed case application.

## Instruction-free artifact contracts

`profile_artifacts.py` has no filesystem/store/acceptance access. Recorded
provenance describes output; it cannot resolve or authorize current instructions.

- Selection: `{schema_version: 1, profile_ref}`, app `recordprep`, at
  `.recordprep/practice-profile.json`; reading creates no selection.
- Provenance: `{schema_version: 1, profile_ref, components: {stage: sha256}}`,
  with a nonempty subset of code-owned stages, at
  `artifacts/practice_profile_provenance.json`. No paths/prose/extra fields.
- Category descriptors: ordered `{id, title}` lists. Role descriptors:
  `{counsel: [...], participants: [...]}` of `{id, label}`, including fallbacks.
  Bounds/uniqueness apply; instruction guidance is forbidden.
- Participant schema 3 retains schema 2's attendance, witnesses, conflicts and
  examination safeguards, adds role catalog/provenance, and checks role/label
  agreement against recorded descriptors. Legacy schema 2 uses frozen roles.
- Source-map schema 3 adds preparation provenance and requires schema-3 embedded
  participants when present. CT-only empty arrays do not claim indexing occurred.
  Map schemas 1/2 remain readable; unsupported future versions fail explicitly.
- Digest Markdown format 2/row 3 records category catalog/provenance in the header;
  metadata 5 must agree. Mixed revisions/catalogs and broken escaping/quote grammar
  fail. Legacy format 1/row 2 uses frozen categories, not current instructions.
- Minute checkpoint 2 records policy/catalog/provenance, with appearance rows
  `{person, role_id, status, evidence}` and `{file_page, text}` evidence. Explicit
  presence/absence needs evidence. Location checks are not semantic proof.
  Legacy checkpoint 1 remains readable.
- Saved-answer schema 2 records research separately from consumed preparation.
  Older answers remain readable. Different specialty identities are notices,
  not automatic structural incompatibility or instructions to refresh output.

Only separately accepted, validated local snapshots authorize new work. Missing
instructions block affected new work, not ordinary browsing of existing output.
Focus reports selection separately from the map provenance actually consumed.
Source pages remain factual authority; summaries/overviews remain orientation aids.
