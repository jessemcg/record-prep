# Native-stage and caption skill delivery — 2026-10-30

## Repair and scope

Native and caption launchers now use `/skill:name request`, with a literal space,
through `recordprep/skill_commands.py::skill_launch()`. Pi 1.4.0 separates a skill
name at the first literal space, not a newline. The previous newline commands
could pass through literally without automatically delivering the staged skill.

This covers all six canonical native skills (caption, layout detection, page
numbering, participants, overview and legacy unassigned source-map generation),
plus the profile participants/overview templates. The normal profile source-map
path remains deterministic Python; CT-only participants still skip without a
model. `summary_prompts.py` re-exports the same helper/contract, preserving the
already-fixed summary request bytes and generation identities.

Only the command separator changes model-visible delivery. Skill bodies, remaining
request text, compiled guidance, direct `CASE_NAME_PROMPT`, system
prompt, tools and validators are unchanged. Caption already received fixed
instructions directly, and native tools could sometimes reread a staged skill;
the defect is **not** proof that earlier outputs were wrong. Correct expansion
now guarantees that the full intended skill is in the first model request.

## Safety and freshness

- Existing tool allowlists and guard extensions are unchanged. Caption can read
  only its 1–3 staged first-page copies and write/edit only its private candidate.
  Profile native stages keep exact-file reads, no shell, and candidate-only writes;
  participants additionally retain the bounded validation tool. Exact staged-skill
  reread access is retained for native profiles, without authorizing its directory.
- Python remains the sole canonical publisher. Profile selection, consumed source,
  model/settings, prior caption and preparation guards remain in force. Existing
  Stop/failure/invalid-candidate behavior and private-workspace cleanup are unchanged.
- Participants/overview now use native runtime contract **3**, with the explicit
  `slash-skill-space-v1` identity. Their stage projections also hash the shared
  command helper. Caption inputs likewise include the delivery identity and helper
  hash. Schemas, saved artifact readers, badges and Resume are not migrated.
- Pre-expansion runtime hashes are **not** instruction-equivalent. The historical
  `native_runtime_compat.json` is retained unchanged, but none of its pre-delivery
  entries qualifies; do not refresh its guards to make broken delivery current.
  Any future reviewed compatibility must also have the matching delivery identity.
- Saved output stays readable and untouched. Freshness inspection is read-only;
  explicit generation may need to regenerate old native/caption work at ordinary
  provider cost. There is no automatic rerun, output rewrite or private migration.

## Offline validation

All tests use disposable source/environment selection and synthetic HOME/XDG/cases
on the current computer. No real documents, provider calls, maintained-app restart,
private settings edits, environment provisioning, commits or other-computer actions.

`tests/test_native_skill_delivery.py` intercepts **actual production child launches**
and passes their exact system/skill/extensions/tools/command into the installed
SDK's in-memory session with a synthetic provider and forbidden network:

- **10 production captures:** six canonical native paths, profile participants,
  profile overview with RT and CT-only inputs, and caption with a selected profile.
  Each asserts the complete stripped skill body, SDK wrapper/location, and literal
  remaining request suffix—not merely successful expansion of a constructed sample.
- Actual SDK extension binding and tool execution prove allowed reads/private writes
  succeed while reads of an existing unrelated synthetic file and canonical caption
  writes fail. Tool schemas/allowlists remain exact; CT-only overview does not read
  or mention participants. Intercepted/failed launches clean their workspaces and
  preserve all watched source/caption bytes.
- **Two negative captures** reproduce the old newline failure for caption and a
  generic native command. All production `/skill` construction is centralized.
- Old caption metadata remains stale with unchanged bytes/mtime; edits to the shared
  helper invalidate both native stages. Existing native/caption suites cover guarded
  publication, validator retries/failures and source/profile/model invalidation.
- Summary production/inspector SDK captures and hash-verified resource audits are
  rerun to catch regressions from centralizing the helper.

The previous full-suite caption failure was a **test-fixture error**: after default
Dependency selection became explicit, the test reselected that same profile rather
than switching profiles. It now selects two distinct accepted snapshots and proves
publication is rejected. A complementary test proves same-profile reselection is
not a change. **No production publication guard was relaxed or otherwise changed.**

Focused follow-up: **92 passed**, including native/caption guards/publication,
summary delivery/inspection SDK regressions and resource tests. Sequential resource
validation, tool audit, compileall, shared-validator byte parity, follow-up source/
test-copy parity and whitespace checks pass. Offline wheel/sdist builds contain the
new helper, native/caption changes and verified audit. All 15 audit hashes match
actual sdist members; the wheel's two applicable Python audit hashes match too.
The existing packaging contract is unchanged: `.pi` ships in the source distribution,
not the package-only wheel. All canonical skills/profile native templates in the
sdist match the tested source.

Latest full result: **816 tests, OK — 808 passed, 8 skipped**, repeated. This supersedes the
historical summary-only milestone's one failing fixture, not its recorded result.
SDK evidence establishes delivery and tool restrictions, not real-provider accuracy
or completion of the broader historical GTK manual matrix.

Evidence root: `/tmp/recordprep-structured.SyH095`; `native-skill-before/`,
`native-skill-initial.log`, `native-skill-sdk.log`, `native-skill-full-initial.log`,
`native-skill-focused.log`, `native-skill-full-final.log`, `native-skill-resources.log`
and `native-skill-package.log`. Changes remain uncommitted. Reopen RecordPrep manually
before using the updated code; no existing case has been rerun.
