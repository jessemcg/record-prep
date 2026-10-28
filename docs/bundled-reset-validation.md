# Confirmed bundled reset and Dependency restoration — 2026-10-28

## Current scope

Jesse requested keeping **Reset to bundled…** but reverting the editorial changes
to California Juvenile Dependency. The bundle is again the **exact pre-edit 1.6.0
snapshot**, including original wording, formatting, examples and catalogs. This is
not a second rewrite or a selective cleanup. Content schema 6, naming schema 3 and
profile API 1 remain, as do the previously committed General/Common retirement and
reviewed-baseline promotion.

Exact restored bundle digest:
`9009fbc8300ec42b0eec7786960e162956a8b6152a6315a3c8a185e0b5987c17`.
All shipped resource bytes and manifest match pre-edit Git HEAD. The three files
changed by the withdrawn editorial pass (`classification-tasks.json`, `naming.json`
and `profile.json`) also match public-only `tests/fixtures/dependency-1.6.0/`
byte-for-byte. The editorial-only legacy-initialization adaptation and added
baseline entry were reverted; the shipped-identity lookup/reset implementation
and its 17 tests remain. Earlier 1.6.1 clarity/31%-shorter claims do not describe
the maintained bundle. Exact restoration intentionally retains the old examples
and any ambiguities or duplicated prose; no silent fixes are included.

## Reset persistence contract

**Reset to bundled… → Reset and Save** is the explicit immediate-save exception
to the ordinary draft/Save contract. Availability uses validated shipped application
and specialty identity, not the personal catalog, display name or creation base.
Retired General and independent custom copies have no target; future shipped
specialties use the same path. Corruption/duplicate identities fail closed.

Confirmation freezes the target and existing head/default expectations. Cancel is
the default/close response. Reset validates a separate exact-bundle `ProfileEditor`
through production preview and the existing managed transaction, with work/case/
storage and bundle checks before and during locked publication. An invalid discarded
draft is not compiled or mutated before publication. Exact manifest/resources,
explicit personal ownership, initialization and normal default semantics are kept;
prior immutable revisions remain. Repeating an unchanged reset does not rewrite the
registry or create another revision. No automatic tracking of later bundle updates.

After publication, retained resource containers, stable-ID topic objects/cards and
text buffers are updated without rebuilding navigation. Display-only topic prose
unwrapping cannot change saved source bytes. Surviving buffers retain undo, valid
selections/viewports and subsequent Save bindings; undo is a new unsaved edit, not
storage rollback. A display or selection-callback failure after publication reports
**saved, refresh required** and disables editing until reopened.

## Isolated automated validation after restoration

All test execution used disposable source/environment and synthetic HOME, XDG,
config, cache and profile stores on the current work computer. No real private
configuration, cases or credentials were used by the test harness, and no model
execution or paid calls occurred. Environments were selected explicitly with
UvEnvironments overrides, never synchronized into the production environment.

- Source: `/tmp/recordprep-reset.ll2key-suite/RecordPrep`.
- Environment: `/tmp/recordprep-reset.ll2key-env`.
- Synthetic state: `/tmp/recordprep-restore-state`.
- Previously verified untouched baseline:
  `/tmp/recordprep-reset-baseline/RecordPrep`, separate environment.
- Xvfb/private D-Bus, `GSK_RENDERER=cairo`, `G_DEBUG=fatal-criticals`.

Results with the restored bundle:

- **Full suite: 764 run, 755 passed, 8 skipped, 1 pre-existing failure**:
  `test_case_name_stage.CaseNameStageTests.test_profile_switch_rejects_publication`
  expects `ValueError`, which is not raised. The same failure was reproduced on
  untouched baseline (746 run, 737 passed, 8 skipped). No fix or expectation
  weakening was included in this task.
- **Focused suite: 102 passed** across `test_classification_contract`,
  `test_classification_profiles`, `test_dependency_bundled_guidance`,
  `test_document_naming`, `test_managed_profiles`, `test_profile_reset`,
  `test_profile_task_guidance`, `test_profile_workflows`,
  `test_task_only_classification` and `test_unified_settings`.
- Sequential PI resource validation and Git whitespace checks pass.
  Public resource hash pins were restored. A dedicated regression test checks the
  exact pre-editorial bundle digest and fixture bytes, not new editorial criteria.

`test_profile_reset.py` retains 17 tests: exact/future/custom/retired identities,
confirmation/cancel, clean/dirty/invalid drafts, exact immediate persistence,
default/selection/history, byte/mtime-idempotence, older schemas, stale head/default,
changed bundle, response and locked guards, preview/write failure, post-publication
refresh failure, stable topic/buffer/undo/navigation/viewport state, subsequent
ordinary Save/reopen and synthetic model/case-output sentinels. The reset row's
keyboard-activatable suffix is tested through GTK row activation, including its
button animation; this is not a claim of delivered native keyboard input.

Logs: `/tmp/recordprep-restore-full.log`,
`/tmp/recordprep-restore-focused.log`. Rerun tests only in disposable source with
synthetic state; maintained personal configuration must not be a fixture.
See [settings validation](unified-settings-validation.md) and
[source-install isolation guidance](source-install.md).

## Native GUI evidence and limits

The initial implementation was inspected in a separately identified synthetic
instance. AT-SPI activation exercised Cancel and Reset and Save, and saved readback
matched the then-installed bundle. Home, confirmation and first-hearing editor were
inspected at normal 900×720 and narrow compositor-assigned 479×720 widths, including
Sans 16. Injected native keyboard/pointer events did not register reliably. Full
delivered native keyboard navigation is **not validated**; GTK activation tests
and observed AT-SPI actions are distinct evidence. No desktop/input configuration
was changed to work around this limitation.

The original explicit personal reset to 1.6.1 preserved existing historical files
and Model settings. That revision remains historical. After restoration, the idle
maintained application was closed normally and relaunched through its existing
launcher because its menu was not opening reliably. No case or unrelated draft was
open. Its original narrow geometry was restored by the normal launch.

The maintained GUI then completed **Profile settings → Reset to bundled… → Reset
and Save**. The confirmation was observed with Cancel focused by default, followed
by the visible **Profile reset to bundled prompts and saved.** success message.
Read-only verification confirms the selected personal snapshot equals the complete
restored 1.6.0 bundle and exact digest above, with personal/initialized status kept.
All 33 previously stored snapshot files remain byte- and mtime-identical; application
configuration and Pi preferences remain byte-identical. Normal application
close/startup changed only the application configuration mtime. The machine-local
hash/mtime receipt is `/tmp/recordprep-restore-integrity.json`; no private contents
were copied into public fixtures. Profile settings was left open showing success.
No direct private-JSON writer, historical migration/deletion, case selection,
classification, model call or case regeneration was used.

No sibling repository, dependency, launcher, shared-contract or other-computer
change. No commit or push was performed. Tests validate reset mechanics and exact
restoration, not live LLM classification accuracy.
