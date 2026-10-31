# Profile/app ownership audit

Targeted follow-up to reviewed `67d22aed8ad97c032b7be1012f68182f7ecffb88`.
Dependency remains **1.8.0**, profile API **1**, content schema **8**. No bundled
prose, shared contract file, private configuration, accepted revision or prepared
output is migrated. Only explicit guarded Save/Reset publishes synthetic or user
drafts; opening/inspection never publishes. This is not a profile redesign.

## Ownership/dependency inventory

All generation follows application selection → frozen validated profile → effective
compatibility projection → stage-local prompt/configuration → restricted request →
Python validation/publication. Full selected-revision guards remain in force even
when an inert edit changes provenance but not an effective stage component.

| Resource/input | Editable surface | Loader/compatibility projection | Runtime consumer | Component dependency/status |
| --- | --- | --- | --- | --- |
| `classification_tasks.page_types.rt/ct` | Fixed-label recognition cards; unknown flat prose stays literal | `profile_contract`, `structured_guidance` full-resource/editable adapter and exact whole-task runtime allowlist | `classifier_prompts.classifier_document`, actual classifier request | Basic/Corrected only; active |
| `classification_tasks.first_pages` / flat start strings | Four First pages cards | Same; missing old report start uses application fallback | Same builder, independent per-report-page checking | Advanced/Corrected only; active |
| Flat `date_hearing/date_minute` | None; retained in lossless legacy-v3 draft | Historical validator; excluded from adapter recognition | Fixed `DATE_TASKS/DATE_RULES`, never these strings | No effective dependency; historical-only |
| Schema-1 missing task resource | No historical task data; explicit editing creates a draft | Neutral `PAGE_DESCRIPTIONS/FIRST_CLUES` in classifier builder | Execution and inspector share builder | Honest Basic/Advanced/Corrected change; no Common fallback |
| `naming` v4 | Stable-ID Report Names/Form Names cards | Strict resource validation; naming-only public adapters | `document_naming.compile_naming_profile` and exact-name validator | Names only; active |
| Unknown naming v1/v2 | Shared full-resource JSON compatibility editor on both destinations | Preserve catalogs/modes/global prose/v2 heading+code rules, no speculative conversion | Same compiler and validator | Names only; required compatibility |
| Naming v3 | Literal report/form instruction editors | Original approved-name parser; no split/rewrite of custom prose | Same compiler and validator | Names only; required compatibility |
| `hearings`, `reports` | Stable-ID ordered topic cards | Strict catalog validator | `summary_profiles.compile_summary`, phase builders/preflight/runner | Matching kind's extraction+synthesis only; active |
| `minutes` | Minute orders guidance | `minute_profile_text` exact historical-default resolver | Shared minute skill + `profile_guidance`; complete-order evidence | Minutes only; active |
| `classification` (Common) | None | Historical schemas 1–5 reader; omitted on explicit modern Save | None | Inert, required historical reader |
| Four extra summary resources | None | Schemas 1/2 reader; omitted on modern Save | None; never import legacy extra-summary config | Inert compatibility |
| `roles`, `participants` | None | Schemas 1–3 readers; omitted on modern Save | Fixed participant method; descriptive artifact roles remain readable | No instruction dependency; historical-only |
| `overview` | None | Schemas 1–4 reader; omitted on modern Save | Fixed overview method, actual saved summaries as source | No profile instruction dependency; historical-only |
| `case_name` and legacy caption config | None | Required schema-2–8 inert bytes / historical readers | Fixed caption builder + native runner, not stored prose | No instruction dependency; source/model/contract/output guards remain |
| `policies.attendance/report_scope` | None | Historical validator; dropped from explicit editable draft | Fixed complete-order attendance and complete-report source method | Inert compatibility |
| Legacy initialization config | No hidden settings | `profile_customization` imports active RT/CT/start/naming/minute/topic inputs only | Frozen candidate used by chooser/editor | Retired-only override creates no candidate; source config unchanged |
| Tools, source scope, routing, taxonomy, dates, publication, model selection | No profile authority | Application code/strict request and artifact validators | Classifier/native/summary runners and guarded Python publishers | Application-owned; profiles cannot expand authority |

A changed source artifact can naturally affect a downstream source dependency.
That is different from importing an unrelated profile instruction into that stage.
Publication continues checking the full selection, sources and effective model.

## Corrected legacy behavior

- Exact historical flat classification recognition ignores **only inactive dates**.
  It also recognizes the lossless v3 wrapper only when its report-start clue equals
  the application fallback. Every other active field/key/prose byte still matches
  exactly; no fuzzy matching, prose splitting or partial replacement of unknown task instructions. Runtime recognition is task-local: an exact complete legacy task string or RT/CT description map receives its public equivalent independently of edits to other tasks. Changing an RT/CT clue therefore cannot switch unrelated start instructions, nor can a start edit switch RT/CT recognition. Unknown task values remain wholly literal, not partially adapted. The editable full-resource adapter still requires the entire recognized active resource; it never invents a structured editor for unknown monolithic prose.
- Runtime adaptation is independent of editable format selection. Custom inactive
  date text retains a lossless compatibility draft, survives ordinary Save, and
  cannot resurrect obsolete classification ordering. Unknown active instructions
  remain literal with advisory warnings. Retired date/caption config never creates
  hidden customizations in fresh candidates; accepted historical bytes stay intact.
- Schema 1 gets explicit neutral descriptions for every supported RT/CT label,
  covers versus repeated captions, indexes versus dialogue, judicial actions versus
  requests, reports/forms/certifications/motions/notices/service documents, and
  missing first-page clues. Current schema-8 prompt bytes are unchanged.
- Unknown naming v2 now exposes its authoritative names and heading/code rules,
  not just two prose fields. v1/v2 remain complete-resource JSON escape hatches;
  v3 prose and v4 cards remain unchanged. Invalid/duplicate JSON blocks Save.
- Inspector state copies resources, retained raw JSON and issues, with a validated
  snapshot only when it represents the complete draft. Invalid naming displays
  literal raw text and an explicit incomplete/invalid warning, never the last valid
  catalog as current. Unrelated tasks can still be inspected with the limitation
  visible. Inspection has no model discovery, provider, file-write or Node path.

## Summary composition and retained compatibility

`summary_core` is the single pure core-selection builder for compiled and draft
composition. A frozen `ExtractionConfig` compiles its profile-bound contract once
and reuses its immutable prompt, category definitions and component. No global
cache of settings/drafts. Unassigned definitions still use their existing category
loader on access. Prompt sections are not deduplicated. Existing staged skills,
literal-space `/skill:` launches, tool allowlists and Python publication authority
are unchanged. Current golden prompt/component hashes and whole configuration
fingerprints must compare exactly, not be rebaselined to hide a difference.

Required compatibility retained: historical resource validators and artifact
readers; exact public-baseline adapters; unassigned execution/category resolution;
public `config.py` exports; inert fields required by existing schemas; native and
summary publication/freshness guards. Only `profile_contract.py` and
`profile_artifacts.py` are vendored byte-identically with Focus, unchanged here.

## Removed code and supported callers

Repository-wide caller inspection preceded deletion from RecordPrep-owned UI:

- Focus-only General/Research/Answers/Search editors, term-list helpers and unused
  in-window profile switching (RecordPrep edits the application selection).
- Role/form branches of the old generic catalog editor; topics and naming cards
  use the retained stable-ID editor, v1/v2 naming the complete JSON editor.
- Obsolete category/overlay navigation callbacks, outline/selected-marker/loading state,
  unmatched sidebar/explainer CSS, generic prompt-page path, unused FlowBox action helper/imports and task-instruction constants. Response-key
  metadata stays separate; useful fallback prose now has an active neutral owner.

The former `acceptance_profile_workflows.py` sidebar/Focus-shared script was stale.
Its maintained entry point now runs discoverable workflow/Reset/deletion/GTK tests.
`acceptance_classification_guidance.py` now checks five flat destinations, four
first-page cards, fixed dates and natural About disclosures in a synthetic production
editor. Historical reports retain their chronology; they do not advertise removed
widgets as current acceptance. `acceptance_structured_settings.py` remains a current
structured-card/inspector harness. The case-notice harness now edits active minute guidance and explicitly creates its synthetic second specialty instead of assuming retired General is selectable. Installed-package acceptance checks the fourth start task and active minute customization. The old case-pin/General artifact-export `acceptance_profile_pipeline.py` is explicitly retired historical evidence, with a clear nonzero retirement message; current discoverable pipeline tests replace it. Broader unrelated Model settings acceptance scripts are not claimed as validated by this profile-only pass.

## Verification

See the final validation section below for measured results and limitations.
All tests use a disposable checkout named **RecordPrep**, conventional umask 022,
locked machine-local Python environment, synthetic HOME/XDG/Pi state, disabled
metrics and no credentials. No paid calls, real cases/PDFs, other-computer testing,
dependency upgrades, system changes, private migration or automatic reruns.

Coverage includes schemas 1–8; naming v1–v4; exact public baselines; unknown active
prose; mixed formats; retired-only initialization; draft/raw invalid/repair/undo,
shared buffers/navigation, guarded Save/Reset/Close and immutable revisions;
stage-local summary/classification mutations; golden/request parity and installed
Pi SDK delivery; pipeline/reuse/Stop/presence/Resume preservation.

Offline composition/isolation/delivery/publication checks cannot establish model
classification accuracy or narrative quality for real legal records. Paid synthetic
comparisons remain a separately authorized follow-up.

### Local results — 2026-10-31 (`home`)

Evidence: `/tmp/recordprep-ownership.8yMChi/` (disposable, not application data).
The supplied planner directory was no longer present; these are fresh local results.

| Check | Result |
| --- | --- |
| Full isolated unittest suite, final source | **828 run: 820 passed, 8 skipped**, 98.718 s (`full-authoritative.log`) |
| All five actual summary launch boundaries, profile and unassigned, installed Pi SDK | **8 tests passed**, including ten actual launch captures and negative newline delivery checks (`summary-sdk-authoritative.log`) |
| Current prompts/configurations/components/fingerprints/launch text before vs after | **Byte-identical** JSON snapshot, SHA-256 `8492c48a628e6a8db479f0bb029245fcd7c1a5c62020e18cca1a14cee74c15b2`; includes all current classifier prompts/components and both summary modes (`summary-before-final.json`, `summary-after-authoritative.json`) |
| Frozen extraction configuration repeated access | **One compile**, including 100 repeated fingerprint/definition reads; unassigned loader behavior retained |
| Workflow/Reset/deletion/retained GTK acceptance entry point | **56 tests passed** (`acceptance-workflows.log`) |
| Current Classification/Summaries harness | **PASS** for current, unknown v2 and invalid raw scenarios; case-notice and structured-card harnesses also **PASS** |
| Sequential resource validation / registered-tool audit | **PASS**; no audited input changed, so the packaged audit was not regenerated |
| Python compilation / whitespace | **PASS**, disposable files only |
| Offline wheel + sdist / source-resource byte parity / isolated installed-package customization | **PASS**; 118 tracked production/Pi files checked; ownership document included; no private config/runtime payload |
| Shared contract/artifact files vs Focus | **Byte-identical**, Focus unchanged |

The eight full-suite skips are three owner-specific model-settings exclusions,
three optional native/quote SDK checks requiring the absent sibling PiRunMetrics
fixture, and two optional sibling metrics checks. Supplying the installed SDK path
alone does not supply that fixture: a separate 12-test native/quote probe passed
nine and skipped the same three. No fixture was provisioned. The RecordPrep-owned
actual summary SDK captures above do run; they are not among those skips.

The authoritative run also covers adjacent/unnamed/one-page report boundaries,
empty catalogs/worklists, summary checkpoint reuse, Stop/publication guards,
output-presence badges and Resume preservation. Golden fixtures were not replaced.
Historical snapshot read/open/inspection tests assert byte **and mtime** preservation;
only explicit synthetic Save/Reset publishes revisions.

Native desktop observation used only separate synthetic production-editor PIDs.
Rendered screenshots and accessibility state confirmed current recognition/four-start
cards; all three Summary destinations; the v2 full-resource editor shared across
Report/Form Names; current-draft inspection; literal invalid JSON with its explicit
warning; Save failure/success; and Close's Keep Editing/Discard dialog. Narrow and
normal widths, light/dark appearance and enlarged text were observed across these
states. Programmatic navigation/style setup was followed by actual rendered-window
observation, not counted as visual proof by itself. This is a bounded matrix, not
every page × size × theme × font combination and not completion of all older visual
acceptance matrices. No maintained app restart, real settings edit or case rerun.
Reopen the maintained application manually to use the updated source.

Intermediate harness corrections are recorded rather than hidden: the initial
archive lacked a Git index; a background launcher inherited ignored SIGINT and
broke PTY Ctrl-C tests; derived cache fields initially changed `asdict` serialization
and were removed from that surface; one added request fixture initially omitted
its required inactive `prompt` key. A concurrent GTK test attempt exited with a
segfault; subsequent GUI acceptance and the final full run were sequential and
passed. None of these justified production permission/configuration changes or
new golden hashes. The additional legacy active-clue regression first failed
(`active-legacy-before.log`), then passed with exact whole-task runtime recognition.
Corrected legacy effective prompts may stale explicit-run checkpoints honestly;
current summary identities, saved output, output-presence badges and Resume remain
unchanged. No hashes were fabricated to bless incompatible work.
