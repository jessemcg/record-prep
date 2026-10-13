# Practice profiles: validation and limits

## Simplified minute-order summaries — 2026-10-13

Home only, same disposable checkouts/environments and synthetic HOME/XDG/records.
No private settings/profile/case changes and no live model calls.

- RecordPrep **515 tests OK, 4 skipped**, existing unclosed-file warning; Focus
  profile/shared coverage **91 passed + 40 subtests**, existing GTK CSS warning.
- New minute tests cover hearing identity, parent presence/absence on either page,
  attributed positions, findings/orders, next-hearing details and missing settings,
  fixed attendance irrespective of saved historical policies, exact old-default
  recognition without writes, custom prose preservation, schema-3 checkpoints and
  historical1/2 readability. The existing generated/resume test exercises fresh
  publication, current-output reuse and unrelated-profile-change isolation.
- Both targeted GTK suites pass with no attendance selector. Native synthetic
  Dependency settings screenshot confirms the revised instructions and the three
  Summaries entries. Historical attendance is stripped only from explicit edit
  drafts, never by modifying an accepted snapshot.
- Sequential resource validation and the generated minute skill validator pass.
  These are contract/pipeline checks, not semantic model-quality evaluation.
- New profile-bound rows use checkpoint/final metadata3 and omit reporting status;
  old rows keep their historical reader rendering. The minute core/tool changes
  make old minute generation pending until an explicit run; no outputs are rewritten
  by opening settings. Hearing/report prompts and extension are unchanged by this
  minute-specific work.

## Topic-only summaries and contract reconciliation — 2026-10-13

Current Home computer only; disposable source/environment paths under
`/tmp/classification-preview-EKHCHA`, synthetic source pages and HOME/XDG stores.
No private profiles/configuration/case outputs modified; no model or remote calls.

- RecordPrep: **508 tests OK, 4 skipped**, with the existing unclosed-file warning.
- Focus shared/profile coverage: **91 passed and 40 subtests passed**, one existing
  GTK CSS deprecation warning.
- Both apps' targeted GTK explainer/navigation and topic-wrapping checks pass under
  fatal GTK criticals. RecordPrep shows exactly Hearing digest topics, Report digest
  topics and Minute orders; the removed final explainer paragraph is absent.
- Native screenshot checked the three-entry layout and topic editor. Old-schema
  edit drafts lose the four extra fields only in memory, produce valid schema 3,
  preserve historical snapshot bytes and never write a registry on inspection.
- Shared compiler tests prove old extra-summary fields affect neither prompts nor
  component fingerprints; schema 3 rejects them. New bundled profiles physically
  omit all eight old instruction files. Legacy settings no longer import them.
- Restored-contract tests cover materiality, sparse/dense complete sources,
  multi-paragraph candidate content (existing whitespace normalization retained),
  quotations, chronology, topic-local freshness and historical compatibility.
- Native resource validation and all four generated summary-skill validators pass.
- The broader `acceptance_profile_workflows.py` resize harness is locally blocked
  before its workflows: the desktop tiles a requested 480px window to 1233px.
  `xvfb-run` is unavailable. This is not counted as a pass; targeted native GTK
  checks above and automated save/store tests supply the current evidence.

Prompt/pipeline checks are not an empirical model-quality comparison. The baseline,
intentional differences, regeneration implications and controlled A/B procedure
are documented in RecordPrep's `docs/summary-contract-reconciliation.md`.

## Simple shipped-profile acceptance — 2026-10-11

Validated on the current **Home** computer only, with disposable source copies
and managed environments under `/tmp/simple-profiles-AKJKox`, synthetic records,
and isolated HOME/XDG storage. No real case processing, private-settings migration,
production-environment provisioning, paid model calls, remote-host actions or push.
This supersedes the earlier export/registration-oriented GUI checkpoints; their
history remains in Git, not the current ordinary workflow.

### Regression and safety

- **RecordPrep: 469 tests, OK**, with the installed offline Pi SDK explicitly
  enabled and no skips. Production summary/minute/native wrappers and the existing
  resource/tool-boundary contracts are exercised. Existing content-free metrics
  warnings and an unclosed-file ResourceWarning remain; they are not hidden.
- **Focus: 654 passed, 38 subtests passed**, with the two existing GTK/forkpty
  deprecation warnings. Source-installer and optional-Pi lifecycle tests remain
  part of the full suite.
- Shared conformance/workflow/managed-save tests cover independent stores,
  no-write inspection, strict files/permissions/links, complete immutable Save,
  head/default CAS, concurrent changes, interrupted publication, idempotence,
  private ownership, release behavior and a third bundled specialty. Frozen
  legacy fixtures and descriptive artifact readers remain unchanged.
- Read-only Dependency initialization preserves synthetic custom task/caption,
  naming, phase/topic, minutes/attendance and research/answer prose. Historical
  defaults are recognized, runtime/credential fields excluded, and personal
  ownership prevents repeated overlays. No actual private prose was reviewed.
- RecordPrep schema-2 task/compiler tests verify task-group and caption component
  isolation and schema-1 byte/behavior compatibility. Actual caption requests
  preserve credentials/source bounds and reject changed case generation, model,
  first-three-page inventory, or redirected metadata directory. Missing metadata
  directories are created only during successful explicit publication.
- End-user prompt testing and executable sandbox payload/request paths are absent.
  Direct-source production tests verify complete pages without a proposal delimiter,
  attribution and retained historical-default recognition. Four previously
  shadowed historical prompt tests are now independently discovered.

### Real GTK widgets and case transactions

Both `acceptance_profile_workflows.py` runs pass under `G_DEBUG=fatal-criticals`:
choose/edit/Save/reopen/new, complete fields and production compilers, long wrapping
names, topic/role/form controls, no-write cancel/discard, inline name validation,
active-work guards, preserved concurrent drafts, and separate case-use confirmation.
Save-before-switch waits for that question; failed application retains saved
success and visible draft state. Save alone and Not now do not select a case.

Settings/chooser layouts assert actual allocations at **480/640/820**. GNOME's
attached modal windows can ignore default-size changes once mapped, so the
harness remaps the same populated draft at each width rather than accepting a
stale allocation or weakening the width assertion. This is width-specific layout
coverage, not a comprehensive compositor/user-drag-resize test.

Both `acceptance_main_profile_ui.py` runs use actual main windows and synthetic
case bindings. They verify wrapping/non-ellipsized profile controls and bounds at
requested 480/640/820 sizes, then a malformed synthetic registry produces a visible
unavailable dialog without repair or an exposed partial chooser. Profile-window
cleanup is exercised. Existing MessageDialog deprecation notices remain.

Focus's bounded saved-answer switching passes **320 transitions**, zero GTK
criticals, expected final view and reading position fraction **0.5**. Native
AT-SPI inspection confirmed the populated synthetic settings/chooser and accessible
control names. Final targeted screenshot/keyboard verification was limited by the
local unavailable window-introspection backend; no desktop settings were changed.
Do not claim comprehensive screenshot-based or screen-reader acceptance.

### Independent producer/consumer and packaging

The synthetic civil General, Dependency and GUI-authored third specialty pass
RecordPrep's actual classification, boundaries, native candidate validators,
summary/minute and source-map publishers. Independent Focus helper subprocesses
consume only case artifacts and a separately authored Focus counterpart, using
context/lookup/search and research pins; case bytes stay unchanged. Responses are
synthetic, not live-model quality evidence. Consumer acceptance needs its own
fresh HOME/XDG store; reusing a previously populated test store correctly rejects
a stale expected-empty head.

Both final wheels and source archives build. Installed-copy acceptance imports
each application in isolation with `python -I`, validates every catalog resource,
checks applicable Python production compilers, rejects private-runtime archive
content, verifies no-write fresh catalogs, and performs a synthetic managed Save.
Installation uses **uv `--link-mode copy`**: default cache hardlinks are rejected
by the existing single-link resource guard. That limitation is documented, not
silently relaxed. Focus's supported source installer uses its own source tree.
Full RecordPrep native-Pi deployment still requires its owned source `.pi/` tree;
a wheel is not a native-Pi installer. Native resource validation, compilation,
vendored code/test/document parity and Git whitespace checks pass.

### Evidence and operational limits

Final logs in `/tmp/simple-profiles-AKJKox/`:
`rp-tests-release.log`, `focus-tests-release.log`, `rp-gui-release4.log`,
`focus-gui-release4.log`, `rp-main-release2.log`, `focus-main-release2.log`,
`pipeline-release.log`, `consumer-release-clean.log`, `resources-release.log`,
`answer-switching-release.log`, final build/install logs and package archives.
Acceptance scripts are tracked in the owning repositories; temporary artifacts
are not runtime dependencies.

No private configuration/case files were rewritten, normalized, migrated or
exported. Personal customization is persisted only by explicit application Save
or Use profile; no public-resource promotion follows. Existing contexts remain
legacy or pinned. Restoring unavailable instructions and further paid/private-record
quality evaluation are separate user actions, not consequences of these tests.

## Follow-up: remove formal-proposal exclusion

The Formal proposals control, heading detectors, injected delimiter, work-item
markers and cutoff-based digest rejection are removed. Complete-document evidence
remains eligible before, within and after proposed-findings/order sections. Tests
cover heading variations, split headings, later-page and same-page quotes, and the
actual guarded summary runner publishing a verified post-heading quote in its digest
and retaining the material requested relief in final prose. Old `report_scope` bytes
remain readable and inert; editing omits the field without modifying the original
snapshot. Changing or omitting it does not change report compilation. Exact former
built-in prompts and shipped baseline hashes remain recognized; frozen fixtures are
unchanged. Report freshness explicitly distinguishes the complete-source contract.

Follow-up validation in `/tmp/simple-profiles-AKJKox/`: RecordPrep **457 tests, OK**
(`proposal-rp-tests-final.log`); Focus **655 passed + 38 subtests**, with its two
existing warnings (`proposal-focus-tests.log`). The lower RecordPrep count replaces
obsolete detector/cutoff tests with complete-source and historical-recognition tests;
source/evidence/publication guards remain tested. Both real GTK workflow acceptances
pass with fatal criticals and exact 480/640/820 allocations, explicitly checking that
no Formal proposals label or policy option exists. Scoped AT-SPI observation of the
owned synthetic editor confirms report controls and retained Attendance evidence,
without the retired control; no screenshot or broad screen-reader claim is made.
Native resources and the changed skill validate. Original unrelated RecordPrep
AGENTS/README edits, private configurations and real cases remain untouched.

## Follow-up: title subtitle and hamburger controls — 2026-10-12

Validated locally on **Work**, using disposable sources/environments at
`/tmp/profile-menu-ZDH5eg` and synthetic HOME/XDG/cases only. No paid calls,
production runtime provisioning, private configuration changes or remote actions.

- The profile banner and chooser window are removed. Actual-main-window acceptance
  checks the title subtitle, embedded hamburger controls, nested dropdown opening
  and dismissal without closing its parent, explicit selection, fresh controls on
  reopening, and malformed-store errors without repair. Browsing a dropdown alone
  leaves the case unchanged.
- Both apps pass real-desktop maximization of independent non-modal editors, with
  no transient parent. Native desktop inspection confirms title/menu layout;
  the Focus editor was also moved and resized independently to 820×760.
- Shared GTK workflows pass with fatal criticals: complete editing, Save/reopen,
  new profiles, unsaved changes, concurrent drafts, work guards and separate case
  application confirmation. Exact 480/640/820 content allocations run under Xvfb:
  independent windows recreate their surface between sizes; the no-window-manager
  fallback border is compensated rather than accepting a narrower allocation.
  These layout tests do not claim compositor drag coverage at every width.
- RecordPrep: **457 tests, OK**. Focus: **655 passed + 38 subtests**, two existing
  warnings. Installed offline Pi SDK tests are enabled. Focus answer switching:
  **320 transitions**, zero GTK criticals, correct final reading position.
- Shared UI modules/tests/docs remain byte-identical. Existing unrelated RecordPrep
  documentation changes are preserved; only the profile-navigation README paragraph
  is additionally updated for this change. Launcher and command contracts are unchanged.

### Menu polish and direct selection

The subsequent refinement removes **Use profile**, the extra Profile heading and
padded panel layout. Profile/settings controls are normal-weight and left-aligned
with native menu items. A dropdown activation immediately uses the guarded selection
transaction and updates the checkmark/subtitle. Simply opening it remains read-only.
The actual-main-window tests assert both labels align with the native Settings label
within one pixel, normal Pango font weight, immediate application, no Use button,
and restoration of the real current choice if selection fails. Both full suites
and GTK workflows pass again. Evidence: `*-main-polish.log`,
`*-workflows-polish.log`, `*-tests-polish.log` in the same disposable directory.
Earlier references to a separate Use profile action describe the superseded version.

### Single-source naming instructions and Model settings

RecordPrep now stores naming v3 as report/form instructions only. Approved names
are the `- **Name**` entries within those prompts; matching requirements remain
beside form names. The compiler uses those same entries for exact output membership,
without injecting a duplicate catalog. New/bundled profiles always use approved
names. General intentionally has no practice-specific list, retaining provisional
labels until approved names are supplied. Existing unversioned/v2 snapshots keep
historical behavior; editor conversion preserves their names, known heading/code
requirements and original prose without rewriting snapshot/config/case bytes.
The general menu/window is **Model settings** in both apps; action IDs, launchers,
settings storage and controls are unchanged.

Final Work-only validation in `/tmp/profile-menu-ZDH5eg`:

- RecordPrep **464 tests, OK** (`RecordPrep-tests-naming-final.log`); Focus
  **656 passed + 38 subtests**, two existing warnings (`Focus-tests-naming-final.log`).
  Includes v3 strict schema/duplicate/malformed-name rejection, prompt-edit-only
  membership/fingerprint changes, frozen v2 compatibility and mocked actual image
  requests with application-owned normalization. The exact former shipped agency
  recommendation guidance is recognized as a historical default, not copied back
  as a personal override reintroducing the retired proposal exclusion.
- Both final GTK workflow and actual-main-window acceptances pass under fatal
  criticals. They verify the removed naming controls, prompt-only editing,
  Save/reopen/new/private transactions, and actual Model settings menu/header/window
  labels without model discovery or saving settings. Synthetic native desktop
  inspection shows only report/form instruction editors, not duplicated catalogs.
- Three synthetic producer scenarios (General/civil, Dependency, GUI-authored third)
  and independent Focus consumer pass (`naming-pipeline-three.log`,
  `naming-consumer.log`). Focus's 320 answer transitions pass with zero GTK criticals.
- Four bundled CLI validations, native resources, shared module/test/document parity
  and whitespace checks pass. Wheel/sdist installed-copy acceptance passes for both
  apps (`Focus-naming-build.log`, `RecordPrep-naming-build-final.log`). RecordPrep's
  release build uses tracked source plus the new historical test fixtures; building
  from the broad development copy initially failed on ignored top-level folders
  (`prompts`, `min_test_pdfs`), not on the naming change. No production packaging
  metadata or lockfile was changed. Copy-mode installation and native-Pi source
  deployment requirements remain as documented.

All testing uses disposable stores, synthetic sources and offline model stubs;
no private settings/case rewrites, paid calls or remote-machine actions.

### Category navigation and taller profile editors

Profile settings now uses a boxed left-hand main/subcategory list and a right-hand
stack showing just the chosen page. RecordPrep has General, Classification,
Summaries, Participants / Witnesses and Case Overview; Focus has General,
Research, Answers and Search priorities. Main prompt editors are at least 360
pixels high and expand to available height. Topic/role cards retain compact inline
editors. A 700sp breakpoint changes the sidebar into a categories-button overlay.
The window remains independent/non-modal, initially 1040×800, with a 360×480
minimum. Profile/default/new controls live under General; the current profile name
is always in the header subtitle. No prompt data or persistence contract changes.

Local Work evidence remains in `/tmp/profile-menu-ZDH5eg`:

- `RecordPrep-nav-tests.log`: **464 tests, OK**; `Focus-nav-tests.log`:
  **656 passed + 38 subtests**, two existing warnings.
- Both `*-nav-workflows-final.log` and `*-nav-main.log` pass under fatal criticals.
  Every navigation row is activated and checked for a single mapped page, current
  marker and unchanged draft state. Tests verify actual tall-editor allocation,
  retained text/cursor/scroll after switching pages, active page retained after Save,
  narrow sidebar open/close behavior, old Save/Discard/Cancel and concurrency guards,
  plus populated layouts at 480/640/820. Explicit window minima avoid new Adwaita
  breakpoint sizing warnings. Existing Xvfb EGL and MessageDialog deprecation
  warnings remain; no GTK critical is suppressed.
- `nav-pipeline-three.log` / `nav-consumer.log`: synthetic civil, Dependency and
  a third profile authored through the new GUI pass independent producer/consumer
  validation. `nav-answer-switching.log`: 320 transitions, zero GTK criticals,
  correct final reading position.
- Native screenshots of both owned synthetic editors at 1040×800 confirm the
  sidebar and spacious right-hand prompt. RecordPrep's selected text editor was
  677 logical pixels high in scoped AT-SPI inspection; unrelated pages were absent
  from that visible tree. Narrow presentation was also observed. No comprehensive
  hardware-keyboard or screen-reader interaction claim is made.

Only temporary synthetic preview windows were moved/resized/closed. Private
settings/cases and unrelated existing repository edits remain untouched.

### Synchronized selection and clear-current-case (2026-10-12)

RecordPrep now separates synchronized case-metadata permissions from owner-only
accepted-profile storage. A missing old snapshot does not prevent an explicit
choice of an available replacement. The dim header trash button clears selection,
not files. Profile settings also supports a pending choice with no case selected;
RecordPrep's General/default controls and caption prompt page remain removed.
Shared manager changes are vendored identically in Focus; its existing-case Save
confirmation and General controls remain unchanged.

Local Work evidence is in `/tmp/recordprep-general-mflas9`:

- `case-selection-final-tests.log`: **488 unittest tests, OK, 4 skipped**.
  New regressions cover normal synchronized modes, retained private-store checks,
  ownership/symlink/hardlink/nonregular/world-write rejection, stale selection,
  clear-state/preserved settings and files, busy/editor blocking, failed save,
  stale file dialogs, pending no-case choice and multi-directory PDF selections.
- `case-selection-focus-pytest.log`: **656 passed + 38 subtests**, two existing
  deprecation warnings. The narrower unittest run also passed (98 tests).
- `case-selection-ui.log` / `case-selection-preview.log`: real local GTK acceptance
  replaces an unavailable synthetic Dependency pin with General using 0755/0644
  metadata, verifies icon styling/order and busy sensitivity, clicks Clear,
  confirms all rows Pending and no selected case, saves and reads back profile content
  without a case confirmation, and verifies the old bundle is untouched.
  Scoped native screenshot/AT-SPI inspection confirms the empty selection and
  three header controls. Default-renderer swapchain warnings were avoided in
  the second preview by using Cairo; no desktop setting was changed.
- `case-selection-{rp,focus}-workflows.log`: both shared GTK workflow suites pass
  under local Xvfb, including existing Save/application/cancellation behavior.
  These are synthetic GTK checks, not a full keyboard or screen-reader audit.
- Native-resource validation, Python compilation, mirrored manager/docs parity
  and whitespace checks pass. No production provisioning, real case/configuration
  changes, chmod repair, paid calls or remote-computer actions were performed.

### No-case settings notice regression

The manager passes a case reference to the editor only when `has_case` is true;
a pending next-case profile is not a case pin. `tests/acceptance_profile_case_notice.py`
passes in both apps with disposable HOME/XDG/stores: Save and reopen without a
case show no earlier-settings warning, while a real-case earlier revision still
shows it. RecordPrep's case-selection GTK acceptance also checks the warning
stays absent after Clear, Save and reopen. Native synthetic desktop inspection
confirmed the warning is absent. Full RecordPrep unit tests pass (488, 4 skipped).
The broader window-sizing workflow could not run on this local tiled desktop
(exact 480px allocation became 1233px); `xvfb-run` is unavailable locally.
No real configuration, profile store or case was changed.

### New-profile menu and action styling

`tests/acceptance_new_profile_menu.py` passes in both apps with disposable stores:
RecordPrep exposes New profile immediately after Profile settings in the menu,
removes the sidebar button, dismisses the menu, preserves an open draft through
the Save/Discard/Cancel guard, validates names, creates an unsaved draft and saves
only explicitly. Active/stale guards disable the new link. Focus retains its
General-page entry. Cancel/Create are direct flat buttons in a Gtk.Box, with no
FlowBoxChild wrapper to add a second hover background. Scoped native AT-SPI
confirmed the menu link; a synthetic dialog screenshot with button prelight
states confirmed one hover background per button. No real app state was changed.
RecordPrep's 488 unit tests pass (4 skipped), both new-menu GTK tests and its
case-selection/no-case-notice GTK tests pass; 55 focused Focus tests pass.
The broader exact-width workflow remains subject to the local sizing limitation
noted above; no cross-computer validation was attempted.

### Edit profiles: creation and safe deletion

The entry/dialog are now **Create profiles** (without an ellipsis), superseding
the earlier New profile and Edit profiles labels. Creation retains the explicit draft/Save flow and flat action strip.
`tests/test_profile_deletion.py` has 11 shared tests for catalog hiding, immutable
historical revision retention, default clearing/preservation, protected built-ins,
stale head/default and work guards, tombstone validation, name reuse under a new
identity, refusal to resurrect a deleted identity, permissions and failed atomic
publication. No snapshots or case pins are deleted.

`tests/acceptance_profile_deletion.py` passes in both applications: cancellation
is read-only; concurrent saves and active work block stale deletion; successful
Delete refreshes the chooser, preserves existing case refs/synthetic pin bytes and
accepted snapshots, clears only a matching next-case proposal/default, and offers
no delete targets when only built-ins remain. The menu creation and no-case notice
GTK regressions pass in both apps; RecordPrep's actual Clear workflow also passes.
Full RecordPrep unit suite: 499 tests, 4 skipped. Focus profile-focused suite:
66 passed, one existing CSS deprecation warning. Compilation and shared parity pass.
Scoped native screenshot/AT-SPI of a synthetic dialog confirmed Create and Delete
sections, personal-profile selector and Delete profile action. No real user profile,
application configuration or case was read, repaired, deleted or rewritten by tests.
The local exact-width workflow limitation remains as described above.

### Classification explanation and RT/CT order

Reviewed the production Basic/Advanced/Dates/Names handlers, `classifier_prompt`,
`compile_naming_profile` and Build TOC before writing the UI explanation. It
accurately distinguishes Common+current-task composition from separate naming
instructions, dated hearing labels (no separate hearing-name prompt), minute-order
first-page dates, report name/date extraction at continuous report-group starts
and form naming on marked first pages. No classifier/runtime contracts changed.

`tests/acceptance_classification_guidance.py` passes for both apps: RecordPrep
shows the pinned explanation on all ten Classification fields, hides it on other
categories, orders shared → RT → CT fields and labels stages, preserves exact
resource/widget binding and unsaved text/scroll position, and keeps frozen files
and the private registry untouched. Focus keeps the explanation hidden everywhere.
Native scoped screenshots/AT-SPI verified both narrow and maximized synthetic
windows, the ordered sidebar/subtitles and the pinned readable explanation.
The existing exact-width sweep limitation is not claimed to be resolved.
The explainer is an ordinary non-selectable/non-focusable label: GTK text-selection
paint must not turn it into a light panel. Acceptance checks those label properties
on first presentation, before navigation or text-editor focus can clear selection.
The RecordPrep case-selection acceptance also clicks the actual Dependency choice
button and checks the settings button and a reopened menu preserve that identity;
all choices/configuration/cases in that test remain synthetic.

RecordPrep's explicit no-existing-case selection now sets the private new-case
default in the same guarded head/default-CAS `managed_save` transaction. The
case-selection GTK acceptance launches a genuinely fresh Python/GTK process with
only the temporary HOME/XDG/configuration: no in-memory pending choice exists,
and both the main header and Profile settings restore California Juvenile
Dependency. Existing-case selection does not change the default, and previous
case metadata stays byte-preserved during the no-case choice and cold launch.
The mirrored case-notice GTK acceptance checks default revision advancement,
failed/blocked selection preservation, existing-case isolation and unchanged
Focus dropdown/default-switch semantics. RecordPrep's 499-test suite (4 skipped)
and deletion GTK regression still pass. No real preference migration was run;
a choice made before this change must be explicitly selected again to remember it.
Full RecordPrep suite remains 499 tests OK/4 skipped; Create/Delete GTK regressions
and 66 focused Focus tests pass. All data was synthetic; no model calls or real
case/profile/configuration writes occurred.
