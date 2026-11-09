# Application-owned motion naming

Current writers use schema 14 / API 1 (Dependency 1.17.0 / Criminal 1.0.0).
[Hearing topics](application-hearing-topics.md) are fixed too; Report Names,
Form Names and Report digest topics remain profile-owned. The schema-13 transition
and dated validation below are historical evidence, not a description of current writers.

Motion rules are universal, not an area-of-law preference. Recognition, physical
source naming and dates, eligibility/exclusions, grouping and Request/Reasons
summaries are application-owned. Qualifying standardized request forms remain
Forms even when they request relief. Neutral reports remain Reports.

**Report Names and Form Names remain profile-owned.** Their catalogs, descriptions,
fixed/source-title options, editors, Save/Reset behavior and naming JSON are unchanged.
Report digest topics remain profile-owned; hearing topics do not.

`document_naming.compile_motion_naming` now uses `motion_guidance`'s fixed neutral
catalog for every assignment, ignoring historical motion catalogs and identity.
Runtime classification, correction, boundary validation and full-prompt inspection
share this compiler. Fixed inspection ignores invalid unsaved profile drafts and
has no draft/template controls. Motion Names is removed from the settings editor;
no new menu or reference window was added.

The Dependency 1.16.0/content schema 13 transition omitted `motion_naming` as well
as `motions`. Schemas 1–13 remain readable; historical motion resources are inert.
Explicit Create/Save/Reset now produces schema 14 through the existing guarded workflow.
Opening settings does not rewrite any accepted snapshot. The legacy report/form
customization adapter retains the current envelope rather than downgrading it.
The byte-identical profile contract in Focus accepts the new format without adding
research instructions or profile management. Its historical artifact contract is
unchanged. Publish the compatible consumer first if publication is authorized.

## Adoption

Restart RecordPrep to load the new code. No profile Save/Reset is required to use
the fixed motion method. Existing output, private preferences and accepted profile
revisions are not migrated or regenerated. Explicit motion naming/processing uses
the fixed rules; rebuild dependent preparation only when deliberately adopting new
output. Completion badges and Resume remain presence-based.

## Local validation (2026-11-08, home desktop)

- Full RecordPrep unittest discovery: **1002 tests, 992 passed, 10 skipped**.
- Focus reader/schema conformance: **35 passed**.
- New regression coverage: custom/empty/schema-11/schema-12 catalogs cannot affect
  motion prompts, normalization rules or Names fingerprints; fixed inspection
  ignores invalid drafts; current projection omits the retired field without
  changing historical bytes; report/form edits still affect their own prompts
  and Names freshness, but never motion naming.
- GTK tests cover retained report/form editing, Save/Reset and the fixed motion
  inspector. A separate synthetic desktop window was observed with Computer Use:
  Document naming contains exactly Report Names and Form Names, with both digest
  topic destinations retained. The temporary profile store remained unsaved.
- Sequential PI resource validation, shared-file byte parity and diff checks passed.
  Bundled report/form `naming.json` is byte-identical to the pre-change version.
- Initial development run exposed stale-schema assumptions, which were corrected.
  Three PTY Ctrl-C tests also timed out under background shell execution; the final
  foreground full-suite run passed, without changing terminal tests or behavior.

Evidence logs: `/tmp/recordprep-motion-owned-validation/`. No paid provider work,
real-case processing, private-settings writes, application restart, deployment,
commit or push was performed. Focus's pre-existing untracked `.pi/` was preserved.
