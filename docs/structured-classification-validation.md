# Local structured-classification validation — 2026-10-30

## Status: implemented, **not fully accepted**

Core classification/schema/editor/inspector work is implemented and uncommitted.
The follow-ups below record successive test/desktop evidence. The latest separately
authorized summary skill-delivery fix supersedes the former summary-delivery blocker:
all five summary launches expand correctly in installed-Pi SDK captures. See
[summary skill delivery](summary-skill-delivery.md). The subsequent separately
authorized [native/caption repair](native-skill-delivery.md) verifies those launches
too and corrects the case-name baseline test's same-profile fixture without changing
the production publication guard. The latest full suite passes (816 run, 8 skipped).
Broader original manual acceptance limits remain. Earlier sections are chronological
evidence, not current blocker status.
The original acceptance findings, before that authorization, were:

1. **Summary delivery:** actual offline installed-Pi capture proves the existing
   newline `/skill:name` command is sent literally rather than expanded. The
   inspector now flags that the skill is staged, not verified delivered. Fixing
   this would change model-visible summary instructions and needs a separately
   authorized behavior/contract decision, not a silent change in this task.
2. **Final visual acceptance/screenshots:** the last local desktop session did not
   expose window targeting (GNOME extension bus owner unavailable; Introspect denied).
   The portal screenshot returned a black image and GTK snapshot rendering returned
   no frame. Therefore final light/dark/enlarged-font and 480px **visual** acceptance
   and screenshot deliverables were **not complete at that point**. No fabricated
   screenshots or logical-allocation-only visual claims were substituted. The later
   wording follow-up successfully captures screenshots and checks the live inspector;
   this does not retroactively establish every original manual acceptance scenario.

No completion claim should hide remaining limitations. The summary repair was
subsequently authorized and verified separately; no maintained-app restart or
desktop setup change was used as a workaround.

## Scope and isolation

- Computer: local `home`; no other computer contacted or used.
- Source: RecordPrep, with narrowly necessary validator/tests/docs support in Focus.
- Focus already had uncommitted schema-6 work in `AGENTS.md`,
  `focus/profile_contract.py`, `tests/test_practice_profiles.py` and an untracked
  `.pi/` directory. Those changes are preserved. The original contract diff was
  saved privately to `/tmp/focus-contract-before.patch` before mirroring.
- Disposable root: `/tmp/recordprep-structured.SyH095` (also recorded at
  `/tmp/recordprep-structured-root`). Baseline and current source copies have the
  required final directory name `RecordPrep`; the current copy has a disposable
  `.git` for path/version-dependent tests.
- Python environments: paired explicit project/environment overrides with
  UvEnvironments' absolute `project-env` helper; RecordPrep environment at
  `<root>/env`, Focus at `<root>/focus-env`. No `.venv` or production environment
  synchronization. The test copy is refreshed with source/tests/resources, not
  private runtime files. Runs set synthetic HOME and XDG config/data/state/cache.
- GTK uses the actual production editor and inspector with temporary synthetic
  ProfileStores, no cases and no real registry. Only synthetic test processes were
  stopped. The maintained RecordPrep/Profile settings windows were not restarted,
  saved or otherwise manipulated.
- No private profile/config/history changes, real legal documents, credentials,
  live paid requests, Git commits/pushes, desktop launcher changes, XREMAP changes,
  settings deployment or other-computer actions.

## Results

| Check | Result |
| --- | --- |
| Unchanged baseline full suite, corrected isolated directory layout | **764 run: 755 passed, 8 skipped, 1 failure** |
| Final implementation full suite | **778 run: 769 passed, 8 skipped, 1 failure** |
| Failure in both | `test_case_name_stage.CaseNameStageTests.test_profile_switch_rejects_publication` (`ValueError not raised`) — unchanged baseline failure, not fixed here |
| Focus historical profile, schema 7, artifacts, profile-map readers | **53 passed**, plus 6 subtests |
| Pure structured classification + production GTK supplemental tests | **12 passed** (also included in full suite) |
| Actual offline Pi summary SDK request capture | Both tests pass in full suite; literal-skill defect is expected/visible, **not claimed fixed** |
| Actual classifier request capture | All nine task system messages byte-match current-draft inspection; image input retained |
| Registered prompt-tool collector | `node scripts/collect-prompt-tools.mjs --check`: **PASS**, no network |
| Bounded production GTK acceptance | **PASS**, synthetic stores: retained buffers/undo, navigation, inspectors, guarded invalid Save, successful Save/Reset |
| Final screenshot mode | **Exit 1**, explicit `No rendered GTK frame is available ... visual acceptance is incomplete`; no PNG produced |
| Shared validator | `cmp recordprep/profile_contract.py ../Focus/focus/profile_contract.py`: byte-identical |
| Python compilation | `python -m compileall -q recordprep tests .pi/scripts`: **PASS** in disposable copy |
| Build | `uv build --python <root>/env/bin/python --out-dir <root>/dist`: sdist + wheel **PASS** |
| Packaged resources | Wheel contains tool audit, public exact-adapter baseline and structured Dependency naming resource: **PASS** |
| Whitespace | `git diff --check`: **PASS** in both repositories |

An early baseline run had path/layout-related failures because the checkout ended
in `source` instead of `RecordPrep` and lacked `.git`. The corrected baseline above
is the comparison used here, not that noisy early run.

## Evidence and regression coverage

- `tests/test_structured_classification.py`: 198-line information accounting,
  original RT/CT/first-page guidance preservation, 16 report names/six form rules,
  certificate merge, footer/code/date exceptions, all-description best fit,
  canonical key order, exact-resource adapters versus custom prose, stage-local
  fingerprints, inactive legacy dates, schema/name/label validation, literal
  braces/Unicode, real classifier request parity and frozen summary identities.
- `tests/test_structured_settings_ui.py`: unmatched legacy Save/immutable history,
  mixed recognized-resource drafts, format-changing confirmed Reset retaining
  unrelated summary cards, invalid frozen inspection with no model discovery or
  store write.
- Existing GTK tests retain topic/name objects, undo/selection/focus/navigation,
  reorder/add/remove, full-width explanations, failed/stale/busy Save/Reset,
  post-publication refresh failures and settings close/switch protections.
- Existing pipeline/freshness/Resume, case-name, direct-source summary, quote,
  role, artifact and profile-store tests run in the full suite. No provider model
  quality or paid generation acceptance is asserted.
- `tests/fixtures/summary-inspection-golden.json` was generated from the unchanged
  public baseline checkout: hearing/report extraction and synthesis prompt hashes,
  component hashes, staged skill hashes, and minute guidance hash are unchanged.
  This deliberately does **not** pretend the staged skill is delivered by current Pi.
- `tests/offline_prompt_sdk.mjs` uses actual SDK skill staging, tool registration,
  allowlists and final system/user/tool capture. Auth/settings are synthetic;
  network is disabled. It captures both extraction and synthesis, including the
  wrapper's actual source, `quote_capitalizations`, active descriptions and schemas.
- `prompt-tools.json` records extension and builder/runner hashes plus installed SDK
  skill-expansion audit. Inspector hash mismatch tests produce explicit limitations,
  never silently use an apparently current independent tool description.
- Public original fixtures and Focus's existing conformance fixture remain unchanged.

Full detailed local logs remain under the disposable root:
`baseline-tests2.log`, `current-tests-final2.log`, `focus-tests.log`,
`structured-tests2.log`, `gui-final.log`, `gui-visual-final.log`, `build.log`.
The Focus command was rerun successfully after an initial typo naming a nonexistent
test file; the numeric result above is the successful run.

## Representative prompt views

`docs/prompt-examples/` contains ten literal inspector views generated **only** from
the public Dependency bundle: `rt`, `ct`, `first_hearing`, both fixed date tasks,
`report`, `form`, hearing extraction/synthesis and minutes. Runtime source/image/
context is represented by placeholders. Summary examples include the delivery
limitation and explicitly staged skill component, not a false final-message claim.
These are development review artifacts, not automatically exported user drafts.

## Classifier wording follow-up — 2026-10-30

User-requested simplification removes the numbered Application classifier contract
heading, tool/subordination framing, verbose category-ordering paragraph, extra
JSON-format restatement and trailing controlling-contract reminder. Short plain
visible-evidence/uncertainty/JSON instructions remain. RT/CT still compares all
category descriptions for the single best-supported fit; **Category Descriptions**
now appears immediately above them. The inspector labels image attachments
**Page image — attached separately**, including compatibility naming views. The
heading and explanatory placeholder are not added to actual model messages.

- Focused structured/GTK tests: **13 passed**.
- Latest full isolated suite: **779 run — 770 passed, 8 skipped, 1 unchanged baseline
  failure** (`test_profile_switch_rejects_publication`). One pipeline mock initially
  depended on capitalized `Classify ONE`; it now identifies the generated output-key
  declaration. The actual classifier/request-parity tests still run all nine tasks.
- Sequential resource validator, offline tool-audit check, compilation and whitespace
  checks pass. No shared validator/schema, profile data or summary behavior change.
- Effective Basic/Advanced/Corrected/Dates fingerprints change with their new prompt
  bytes. Names and all hearing/report summary component identities are unchanged.
  The three summary example views are byte-identical to before this follow-up;
  frozen minute/summary golden tests still pass.
- Desktop targeting/rendering subsequently became available without setup changes.
  The live synthetic inspector was opened through native pointer actions; its
  screenshot and accessibility text show the plain instructions, descriptions
  heading, absence of the removed text and explicit image-attachment label.
- Synthetic GTK screenshot mode now succeeds: ten actual rendered windows covering
  480px light/dark editors, enlarged font, naming/first-page cards and inspectors.
  Representative home, dark RT, enlarged-font and narrow classifier-inspector images
  were visually reviewed. Files: `docs/screenshots/structured-classification/`.
  The harness's home screenshot now explicitly returns to its home destination.
  These focused checks do not claim every broader original keyboard/selection/scroll
  acceptance scenario or fix the separate summary-delivery defect.
- Public prompt examples were regenerated; no maintained-app restart, private profile/
  config write, model call, commit/push or other-computer action occurred.

Local follow-up logs: `prompt-wording-focused.log`, `prompt-wording-full-final.log`,
`prompt-wording-resources.log`, `prompt-wording-screenshots-final.log` under the same
disposable root. `prompt-wording-before/` records pre-change prompts/fingerprints for
comparison; no private data was copied. Synthetic GUI processes were stopped.

## Shared Report Names / Form Names follow-up — 2026-10-30

Implemented the explicitly approved refinement without adding destinations:

- Settings labels are **Report Names** and **Form Names**, with canonical name and
  optional recognition description. All initial report descriptions are empty;
  the Detention-only date sentence is removed, not relocated into fixed code.
- `document_catalog.py` supplies the same name/description data to CT_report,
  CT_form and later naming. Internal IDs are not model inputs. CT cards contain
  page-recognition/footer guidance, live read-only catalog previews and links to
  the one editable catalog, not stored second lists.
- CT uses catalogs as recognition clues, including continuation pages. Prominent
  first-page heading and same-first-page heading/code requirements remain only in
  naming instructions. Six form descriptions contain neutral heading/code facts.
  Recognizable unnamed forms remain CT_form; names must still validate later.
- Report footer-only matching, `CFS 6.7`, `DCFS 4216`, negative condition and
  `Page X of XX` exclusion remain. The codes are not approved report names.
- Catalog name/description edits now stale Basic, Corrected and Names for explicit
  runs; RT prompts, Advanced and hearing/minute Dates remain independent. No
  completion badge, Resume, output or private snapshot is changed automatically.
- Exact initial structured 1.7.0 resources are frozen as additional read-only
  adapter inputs. Customized prose is retained literally, without heuristic
  splitting or removing user-specific instructions. Original historical fixtures
  remain unchanged. The 198-clause map explicitly records the authorized deletion
  and relocation of duplicate CT report-name data to the one catalog.

Validation on this computer with the same disposable source/environments:

| Check | Latest result |
| --- | --- |
| Focused classification/catalog/naming/production GTK suites | **70 passed** |
| Final full RecordPrep suite | **787 run: 778 passed, 8 skipped, 1 unchanged baseline case-name failure** |
| Focus historical/schema-7/artifact/map readers | **53 passed**, 6 subtests |
| Actual request versus draft inspection | All nine classifier/naming tasks pass, including shared edited descriptions in CT and naming messages |
| Production GTK workflows | **PASS**: live previews/links, retained CT buffers, explicit Save and confirmed Reset, optional descriptions, both new labels; bounded acceptance prints PASS before screenshot failure |
| Fresh visual capture | **Unavailable**: window-control backend denied/unavailable, and screenshot harness reports no rendered GTK frame; no new screenshot published |
| Resource validator, offline registered-tool audit, compilation | **PASS** |
| Offline sdist/wheel build | **PASS**; new catalog module and both initial-structured adapter JSON files are packaged |
| Shared contract / whitespace | Byte-identical RecordPrep/Focus contracts; both diff checks pass |

A first full run was backgrounded and inherited ignored SIGINT, causing three
installer Ctrl+C PTY timeout subtests. Two foreground full reruns clear those
additional failures; no installer/test implementation was changed for them. The
remaining failure is the same pre-existing case-name publication test.

Native AT-SPI observation of the isolated synthetic editor confirms the two labels.
Targeted screenshots/input cannot be verified in the current desktop session, so
no maintained application or desktop setup was modified to bypass that limitation.
Earlier screenshots under `screenshots/structured-classification/` remain historical
wording-follow-up evidence, not screenshots of these latest catalog changes. The
broader original manual acceptance matrix and summary-delivery issue remain open.
All synthetic GUI processes from this continuation were stopped.

Public classification/naming examples were regenerated. The three summary example
files and frozen summary component/prompt identities remain unchanged. No paid
calls, real documents, private configuration/profile writes, maintained-app restart,
commit/push, launcher/XREMAP changes or other-computer actions occurred.

Latest logs under the disposable root: `catalog-focused2.log`,
`catalog-full-final2.log`, `catalog-focus-final.log`, `catalog-resources.log`,
`catalog-tools.log`, `catalog-build.log`, `catalog-screenshots.log`.

## Plain report/form extraction wording — 2026-10-30

At the user's request, Report Names and Form Names extraction now uses the same
plain framing as the other classifiers. Removed the Application-owned Naming
Contract banner, subordinate-guidance language, Task/Output prefixes and repeated
Application Response Keys footer. The inspector still has one **System message**
heading followed by actual model instructions, plus separate image-attachment
metadata. No System message heading is inserted into the model text itself.

First-page source scope, visible-evidence/uncertainty, exact approved names,
report-date formatting/fallback, prominent form headings and same-first-page
heading/code requirements remain. Python JSON/name/date checks are unchanged.
Generated framing is simplified for naming v1–v4; saved custom prose, including
literal braces/Unicode and any user-authored contract terminology, is not rewritten.
Shared catalog data, CT page recognition, all other classifier prompts and summary
instructions/delivery remain unchanged.

- **72 focused tests PASS**, including both current/template inspection modes,
  legacy naming versions, literal preservation, stage-local dependencies and actual
  request/current-draft inspection parity for all nine tasks.
- Final full suite: **789 run — 780 passed, 8 skipped, 1 unchanged baseline failure**
  (`test_case_name_stage.test_profile_switch_rejects_publication`).
- Before/after comparison confirms only Names fingerprints change. Both naming
  examples refreshed; all eight other public example files are byte-identical.
- Resource validator, offline registered-tool audit, compilation, whitespace and
  byte-identical shared-contract checks PASS. No additional Focus code changes.
- A fresh isolated production inspector displayed and checked both report and form
  text. Scoped native AT-SPI and an actual portal screenshot visually confirm the
  Form Names view starts with System message and plain instructions, without the
  contract banner. A rendered-widget PNG is retained privately at
  `<root>/naming-wording-form-inspector.png`. No desktop setup changes were made;
  this focused successful capture does not establish the full original GUI matrix.
- No paid request, real document, private settings/profile write, maintained-app
  restart, commit/push or other-computer work. The synthetic inspector was stopped.

Logs: `naming-wording-focused.log`, `naming-wording-full.log`,
`naming-wording-resources.log`, `naming-wording-gui.log` under the same disposable
root. Pre-change source/example hashes/fingerprints: `naming-wording-before/`.

## Authorized independent report starts (2026-10-30, latest)

The later user approval supersedes the shared-CT-catalog design above. Implemented
Dependency **1.8.0**, manifest schema **8**, classification resource **3**, naming
**4**. See [report starts, cost and compatibility](report-first-pages.md).

- Basic now uses structural report/form recognition with no automatic catalogs.
  Bundled CT_report no longer requires approved footer names or disqualifies
  `Page X of XX`; report codes remain supporting clues. One-page report-gap
  smoothing is removed. Other structural category descriptions are unchanged.
- First pages gains the fourth retained **Report first page** card. Advanced checks
  every report page and persists positive/negative checks; Names uses only explicit
  starts. All report starts, including unnamed starts, break preceding ranges.
  Unnamed/orphan ranges remain source-only; accepted report boundaries feed the
  existing summary work builder without adjacent unwanted material.
- Original schemas/readers/fixtures stay intact. Known complete public resources
  adapt read-only to frozen 1.8.0 tasks. Unknown old CT/name restrictions remain
  literal. Explicit editing adds the fourth task, preserving whole legacy strings
  and inert dates in v3's compatibility representation. No private migration.
- New Names runs pause before requests when report checks are incomplete. Old
  unmarked output remains consumable as stored by TOC/Boundaries. Canonical
  unassigned checkpoints cannot skip new checks or reuse old run-start names.
- Catalog edits now affect **Names only**; report-start clue edits affect
  Advanced/Corrected. Explicit page-flow/selection identities protect workspaces;
  derived selection is contract 4. Dates and naming/summary instruction bytes are
  unchanged by this follow-up.
- Focus's shared validator remains byte-identical. One additional read-only mapping
  recognizes `CT_report_first_page` as the existing Report category for category
  display/reading, not unknown. No new Focus UI/category or research prompt/tool.
  All pre-existing unrelated Focus work remains intact.

Validation on **home**, disposable source/environments and synthetic HOME/XDG only:

| Check | Result |
| --- | --- |
| New report-start acceptance tests | **11 passed**, including production workers/offline HTTP, adjacent wanted/unwanted and repeated-name reports, one-page reports, form separators, orphan bodies, source retention, strict naming, summary work ranges, bad checks/responses and canonical checkpoint reuse |
| Full RecordPrep suite, two foreground runs | **800 run: 791 passed, 8 skipped, 1 unchanged baseline failure**, `test_case_name_stage.CaseNameStageTests.test_profile_switch_rejects_publication` (`ValueError not raised`) |
| Actual classifier/naming request ↔ current-draft inspection | All **10 tasks** covered, including report starts; actual image attachment retained; no catalog leakage into CT/start prompts |
| Focus profile/schema/category/reading tests | **182 passed, 6 subtests passed**; profile/schema subset alone **64 passed, 6 subtests passed** |
| Resource validator / offline registered-tool audit | **PASS**; unrelated summary delivery limitation remains disclosed |
| Compile / both diff checks / shared contract `cmp` | **PASS** |
| Offline final sdist + wheel | **PASS** using the explicit machine-local uv cache, no network or environment provisioning; new report module, schema-8 bundle and both new adapter JSON inputs included |
| Public prompt examples | CT updated, report-start example added; other **nine byte-identical**, including both naming and all three summary examples |
| Bounded production GTK Save/failed Save/Reset/navigation/undo/inspection harness | **PASS**, synthetic stores only |

Focused native desktop evidence: scoped AT-SPI verified all four first-page cards,
editable report clues/output identity and the revised naming-only explanation.
Native accessibility actions opened About → Full prompts and confirmed the modal,
read-only inspector. A rendered GTK widget capture from the separate synthetic
production editor shows the new report card at 540×820 in dark mode:
[first-pages.png](screenshots/report-first-pages/first-pages.png). This is a real
GTK renderer capture, not a successful portal/window-target screenshot. Targeted
Computer Use focus/capture remained unavailable because the window backend could
not resolve this session; no setup was changed. The full screenshot-matrix harness
passed assertions but then failed explicitly with `No rendered GTK frame is
available in this desktop session`; no blank/reused matrix images were published.
The broader original manual keyboard/selection/scroll/light-dark matrix is still
not exhaustively established. Synthetic process PID320835 was stopped; no maintained
RecordPrep window was restarted or modified.

Native compatibility guards were reviewed for the shared-validator-only code
projection change: participants `9f1317b0aa02927dd1e0b5eab0d4847b79e16c933c9f88ae9bcdf6f8732615c9`,
overview `48e108ad2579a0397331c155e6d96777af0b21cd119b4b9126ba2871493335da`.
Previous guarded schema-7 identities join the prior allowlist; no private metadata
repair or native prompt/evidence/model relaxation occurs.

No real legal documents, paid model calls, private settings/profile/case writes,
maintained environment provisioning, commit/push, launcher/XREMAP changes or
other-computer actions. The case-name baseline failure and summary skill-delivery
blocker remain unresolved; full original acceptance must not be claimed complete.

Evidence under `/tmp/recordprep-structured.SyH095`: `report-start-focused.log`,
`report-start-full2.log`, `report-start-full-final.log`, `report-start-focus-final.log`,
`report-start-resources.log`, `report-start-package-final.log`, `report-start-gui.log`,
`report-start-desktop.log`, `report-start-screenshots.log`, and `report-start-before/`.
Earlier build attempts used an unavailable executable/cache through the helper;
the final offline build explicitly selected the already-populated local cache.

## Prompt source-width wrap cleanup

Removed only unintended mid-sentence hard wraps from fixed classifier/date and
report/form naming prose, report-start clues, and the bundled CT_other description.
Deliberate sentence returns, blank lines, bullets, category-heading breaks and JSON
formatting remain. There is no generic prompt reflow: custom descriptions and legacy
guidance remain literal, including chosen hard returns, Unicode and brace tokens.
Summary instructions and the separate summary skill-delivery limitation are unchanged.

The previous public classification-v3.json stays frozen. Full-resource exact
recognition now also accepts that reviewed input and returns
`dependency-1.8.0/classification-v3-unwrapped.json`, matching the bundled resource.
Any custom change disables that adaptation; no saved profile is rewritten. Resource
versions and schema remain unchanged. Word order/content are identical; generated
prompt fingerprints still reflect the actual changed whitespace for explicit work.

Disposable validation: 114 focused tests pass, including four new whitespace/literal
preservation tests and actual-request/current-draft parity for all ten vision tasks.
Full suite: **804 run, 795 passed, 8 skipped, the same one baseline failure** in
`test_case_name_stage.CaseNameStageTests.test_profile_switch_rejects_publication`.
The eight refreshed classification/naming examples differ only in whitespace; the
three existing summary examples are byte-identical. Resource validation, offline
registered-tool audit, source/test-copy parity, shared-validator parity and whitespace
checks pass. Offline wheel/sdist builds include the new exact-adapter resource
(`prompt-linebreaks-package-membership.log`); the first membership scan also tried
uv's non-archive lock file, then the archive-filtered scan passed.
Evidence: `/tmp/recordprep-structured.SyH095/prompt-linebreaks-{focused,full,resources}.log`
and `prompt-linebreaks-before/`. No maintained application restart, private settings
writes, case reruns, paid calls, commit or cross-repository changes in this follow-up.

## Authorized summary skill-delivery repair

The user explicitly authorized fixing the previously disclosed summary-loading
issue. `summary_prompts.skill_launch()` now uses `/skill:name request` with a
literal space. All five production summary entry points share it. Staged skills,
guidance/custom prose, tools and output schemas are unchanged, but the intended
skill body is now actually expanded into the model request. Extraction, synthesis
and minutes have explicit delivery fingerprints; unassigned extraction now hashes
its active skill/system/tool resources too. No saved output/profile is rewritten.
The inspector labels the staged file and pre-expansion launch truthfully; its
refreshed hash-checked audit verifies expansion instead of showing the old blocker.

Installed-Pi offline captures verify exact full skill expansion at **10 actual
production launch boundaries** (five tasks, both modes), plus all five current-draft
inspection requests. The old newline failure is reproduced as a negative test.
Focused **119 pass**; full **810 run: 801 pass, 8 skip, the same one case-name
publication baseline failure**. Historical fixture files and summary guidance goldens
remain unchanged; tests explicitly account for the authorized generation-identity
additions. Bounded production GTK acceptance and all five summary-inspector views
pass, with AT-SPI/read-only modal/empty-status evidence and one successful targeted
portal screenshot. Broader historical manual acceptance is not implied.

Full scope, checkpoint/cost implications, evidence and the separate native-launch
audit limitation: [summary skill delivery](summary-skill-delivery.md). No private
settings/cases, real legal documents, paid calls, maintained-app restart, environment
provisioning, Focus/native launch changes, commit/push or other-host actions.

## Authorized native/caption skill-delivery follow-up

The user separately authorized the native/caption repair. All command construction
now uses `skill_commands.skill_launch`; the summary API re-exports it without
changing its already-fixed requests/identities. Ten actual production-boundary
installed-SDK captures verify full native/caption expansion, with two old-newline
negative captures. Actual SDK tool calls under the unchanged native/caption guards
prove allowed private operations and blocked unrelated reads/canonical caption writes.
Native runtime contract 3 and caption signatures carry the delivery identity/helper
hash; old runtime allowlist entries are retained as historical data, not blessed as
instruction-equivalent. No saved output/private settings/cases are rewritten or rerun.

Focused **92 pass**; latest full **816 run, OK, 8 skip**, repeated. The old caption
failure was its same-profile reselection fixture, not a production guard defect:
the corrected test actually switches between distinct accepted profiles and rejects
publication; a complementary same-profile test succeeds. Production publication
code is unchanged. Resource/audit/compile/parity/diff and offline wheel/sdist code/
audit membership checks pass. Earlier GTK limitations remain, and no new model
quality claims are made. See [native/caption delivery](native-skill-delivery.md).

## Reproduction (same computer only)

Use the absolute UvEnvironments helper with paired disposable `--project` and
`--environment` overrides to provision locked RecordPrep/Focus dependencies. Never
sync test dependencies into the maintained environments. Then from the disposable
RecordPrep checkout:

```sh
# Set HOME and XDG_* to new synthetic directories; use the disposable Python.
PYTHONPATH=. <root>/env/bin/python -m unittest discover -s tests
PYTHONPATH=. <root>/env/bin/python tests/acceptance_structured_settings.py
# Actual desktop required, output directory must not already exist:
PYTHONPATH=. <root>/env/bin/python tests/acceptance_structured_settings.py \
  --screenshots <new-local-directory>
node scripts/collect-prompt-tools.mjs --check
```

The interactive harness uses `--interactive` and remains synthetic. Do not launch
or restart the maintained RecordPrep application for these checks. Screenshot mode
fails explicitly rather than claiming a blank/unrendered frame is acceptance.
Do not require, probe or propose validation on another computer.
