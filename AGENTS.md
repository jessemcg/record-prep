# RecordPrep Agent Notes

## Application-owned model maintenance

`model-settings --stdin` precedes GUI/OCR/pipeline/Pi imports. Resolve only the
owner-selected absolute config location, shared Pi setting and classifier request
connection; a local-server management switch is not a different model/URL slot.
Vendored schema/store stay app-owned. Ordinary writes share CAS/locks and propagate
stale-store failures even without `raise_errors`; failed drafts never become saved
baselines. Reconcile/Retain are receipt-only, not later-edit rollback authority.
Ordinary current-user-owned settings accept primary-group-writable synchronized
0664 files; world-write, foreign-group write, wrong ownership and extra links
remain rejected. Private state and writer locks stay strict 0700/0600.
Settings writer locks live under local `$XDG_STATE_HOME/recordprep/settings-locks`
(default `~/.local/state`), keyed by the absolute settings path, never beside
synchronized settings. All GUI/CLI writers share this Store lock. Keep lock files
stable; never delete them during normal cleanup. Old adjacent writer locks are
ignored, not migrated or chmodded. Close all RecordPrep processes before upgrading
from adjacent locks. XDG state must be machine-local and identical for cooperating
processes; cross-computer use still requires single-writer synchronization. This
RecordPrep-specific leaf permission policy intentionally differs from the sibling
vendored model stores; retain it when refreshing shared code. Never chmod real
synchronized settings as a workaround. Validate with
`tests/test_model_settings_permissions.py` and the actual CLI contract suite.
Use synthetic source/HOME/state only; see SkillsMenu's package protocol-v1 reference.

## Settings interaction contract
Model and Profile settings have separate persistence boundaries. Use expandable homes and retained full-width rounded editors, not permanent sidebars. Save all draft pages without closing or changing destination; only successful persistence advances the baseline. Close offers Keep Editing / Discard Unsaved Changes, never Save-and-close. Reopening presents the application-owned draft.
Explicit Reset to bundled… → Reset and Save is the confirmed immediate-save
exception: exact validated shipped identity/resources, separate replacement draft,
production preview and existing guarded managed transaction. Never normalize the
bundle through editable_profile before reset, mutate a discarded draft before
publication, or refresh stale expectations to force it through. Retain personal
ownership/history, topic-ID objects/buffers/navigation and source bytes; suppress
edit callbacks during display installation. Undo is a new unsaved edit, not storage
rollback. See docs/bundled-reset-validation.md. Retain topic IDs, buffers/undo/selection/viewport and guarded revision/default publication. Details and validation: `docs/unified-settings-validation.md`.

## README style

Keep `README.md` minimalistic and streamlined. Add only important user-facing
information, with explanations that are short and to the point. Put detailed
technical explanations, implementation notes and validation reports in `docs/`,
not the README.

## Pi inheritance

Ship no personal `.pi/settings.json` or model/reasoning/general Pi seeds. Missing
preferences work in checkout and standalone modes and stay absent until an explicit
model/effort save; unrelated saves never create them. Keep guarded reads/writes and
the RecordPrep-specific permission policy above. Required `/skill:` expansion is
enabled only in the private stage workspace, not in persistent settings. See
`docs/pi-inheritance-validation.md` and the older-checkout preservation warning in
`docs/source-install.md`. Do not migrate or rewrite private preferences/artifacts.

## Public installation boundary

See `docs/source-install.md`. Finish RecordPrep, persist the completed receipt and
show success before offering optional Pi. Skip/cancel/failed Pi cannot invalidate
application installation. No credentials, model selection or paid verification at
install time. Public installs depend on no sibling project and set absolute
RECORDPREP_CONFIG_DIR; retain authoritative external settings and legacy checkout
compatibility without migrating private preferences or prepared artifacts. Tracked
`.pi/` remains the resource root, never the external settings directory. Preserve
personal profile registries/accepted revisions even during optional cleanup; never
recursively purge XDG RecordPrep settings. Tests use disposable source/HOME/XDG/cache/
runtime state, synthetic data and fake/offline providers, not real credentials or
paid calls. Public helpers are `scripts/recordprep-env check`, explicit `sync`, and
`run`; unittest remains the test workflow. The maintained workflow below is separate,
not a public-installation dependency or public hostname restriction.

## Machine-local runtime

Read ../UvEnvironments/README.md. Provision `../UvEnvironments/project-env sync RecordPrep`
(managed Python 3.13, Home/Work only; excluded on Laptop). Execute via
`../UvEnvironments/project-env run RecordPrep COMMAND`. Before uv examples below,
source `../UvEnvironments/terminal.sh RecordPrep` in a dedicated project subshell and
stop on failure; it verifies runtime and disables automatic sync/downloads. Never
inherit another project's UV_PROJECT_ENVIRONMENT/VIRTUAL_ENV. Same-project Python
children use sys.executable. All test checkouts/environments must be disposable;
private config/case bundles remain untouched.

## Practice profiles

Current structured settings: read `docs/structured-classification.md` and its
validation report and `docs/report-first-pages.md`. Dependency 1.8.0 uses content
schema 8, classification resource v3 and naming v4; schemas 1–7 stay readable.
Report Names/Form Names are naming-only catalogs: never inject them into page-type
or start prompts or restore CT catalog previews. Basic uses structural recognition;
report footer codes are supporting clues, not approved names or mandatory gates.
Advanced checks every CT_report page independently, including adjacent/unnamed
reports: first_report → CT_report_first_page, with explicit report_first_page yes/no
stored for every checked report page. Names requires complete checks and names
marked first pages only. All starts, including unnamed ones, terminate earlier
report ranges; orphan bodies/gaps remain source-only, never inferred starts. Keep
one-page/adjacent/repeated-name reports separate; do not restore report-gap filling.
Naming evidence/JSON/date/exact-name validation is unchanged. The Detention-only
date sentence remains deleted. Only Names depends on catalogs; report-start clue
edits affect Advanced/Corrected. Page-flow/selection identities invalidate old work
checkpoints; Dates and summary model instructions stay unchanged. Actual upstream
bytes still determine downstream workspaces. Unknown prose stays literal; explicit
editing adds the fourth task, preserving flat legacy strings and inert dates in
v3's lossless compatibility representation. Exact public adapters are read-only.
Classification has five flat destinations (RT page types, CT page
types, First pages, Report Names, Form Names); fixed-key recognition
cards and stable-ID naming cards replace monolithic prompts. Date extraction is
entirely application-owned; old date text is byte-preserved but inactive. Best fit
compares all descriptions, with no precedence, weights or preferred label. Exact
resource allowlists adapt known baseline prose; unknown custom prose stays in a
labeled compatibility editor. Only explicit Save upgrades immutable revisions.
Classification and report/form naming prompts use plain instructions, not branded
Application/Naming Contract headings or subordinate-guidance/response-key restatements.
The inspector's System message heading identifies transport, not extra model text.
Keep first-page evidence, exact-name/JSON/date validation and legacy prose intact.
Prompt inspection shares pure runtime builders, freezes unsaved drafts modally,
and reads generated hash-checked registered tool schemas without Node/model access.
Summary skill delivery uses `/skill:name request` with a literal space, never a
newline between name and request. Offline installed-Pi captures at all five actual
summary launch boundaries verify full skill expansion in profile and unassigned
modes. Preserve staged skill/guidance bytes and custom prose; delivery changes have
an explicit summary-phase fingerprint (`slash-skill-space-v1`), not private-output
migration. Unassigned extraction also hashes its now-delivered skill/system/tools.
The inspector labels staged skill versus launch-before-expansion; missing/stale
packaged audits still report incomplete inspection. See docs/summary-skill-delivery.md.
The schema-8 documentation supersedes older current-schema/RT–CT hierarchy/naming-bullet descriptions below.

See `docs/practice-profiles.md` and `docs/practice-profiles-validation.md` for the
shipped-specialty/personal-settings workflow, v1 API and supported content schemas,
runtime boundaries and validation limits.
Only `profile_contract.py` and `profile_artifacts.py` remain vendored byte-identically
with Focus for historical metadata/artifact compatibility. Coordinate those two;
store/workflow/editor/manager modules and UI/docs no longer require Focus parity.
Focus has one fixed neutral research method, no profiles or counterpart requirement;
preparation provenance never supplies its instructions. RecordPrep profile management,
runtime/resources/schemas/fingerprints and pipeline remain unchanged. Never import a
sibling app or its instructions at runtime. Bundled resources are app-owned and read-only.

Application profiles are independent of bundles (docs/application-profiles.md).
Every new generation uses the current application selection (California Juvenile Dependency by default),
not a case pin. Create files never writes a profile reference. Historical pins are
inert, left untouched, and never required to browse or regenerate. Selection and
Save change application settings only, never regenerate output. Saving selected
guidance advances it without a case-use confirmation. Classification, naming,
boundaries, native stages, summaries and minutes share frozen current guidance,
stage-local component/source/model checkpoints and serialized publication. Native tools
read bounded inputs and edit private candidates only; Python owns publication and
the deterministic v3 source map. Profiles cannot add tools or weaken validators.

Keep frozen dependency fixtures and legacy readers intact. Participant schema 4
(2/3 readable), schema-3 maps, digest format 2/row 3/metadata 5 and minute checkpoint 4 (1–3 readable) carry descriptive
provenance/catalogs, never instruction authority. Unknown names/dates must not
erase short documents. Custom category IDs may include hyphens and digits; quote
serialization must preserve their canonical IDs. Forms TOC lists only named forms:
empty/missing form names must not generate provisional entries. Reports likewise
require an accepted nonempty name for TOC entries and standalone summary boundaries;
Correct boundaries omits empty/unresolved names, never inferring a name from an old
synthetic report_label. Keep named one-page/missing-date and same-name/date reports.
Preserve all source pages/classifications; never merge unnamed fragments across gaps.
A profile without approved report names yields no eligible report summaries. This
approved policy replaces provisional report labels/ranges from 2303297. Historical
readers still display output as stored, without writes. Explicit Build TOC → Correct
TOC → Find boundaries → Correct boundaries applies the policy. TOC correction keeps
only the first recognized minute-order date, never collapsing unknown dates, for
profiles and unassigned cases alike; separate profile-bound order boundaries and
minute checkpoints remain intact. Derived-selection contract v4 honestly stales old
profile-era TOCs/boundaries, not classification/naming. After explicit boundary
rebuilding, unchanged RT/hearing inputs reuse participants through narrowly reviewed
runtime compatibility, not private metadata repair. Missing instructions block new
work, not browsing. Keep private configuration/cases untouched. Dependency
initialization is an allowlisted read-only candidate shared by chooser/editor,
persisted only on Save
or Use profile, never a migration script or public-resource update. Public profiles
are complete tracked specialties; personal saves use the managed private store.
RecordPrep content schemas 2/3 store task-specific classification and historical case-name
guidance. Caption inference now always uses case_name_prompt.py's fixed, neutral
prompt; profile/legacy caption text stays byte-preserved but inert. Production
caption inference/freshness lives in case_name_stage.py and uses the native Pi
runner/shared model, not a direct API. All old names stay readable but require an
explicit inference run for the schema-2 source/model/contract/output marker. Profile settings has no General page,
profile picker or default switch; Save preserves existing default semantics and
Create profiles (no ellipsis) is a hamburger-menu link below Profile settings, not a sidebar button.
Its Cancel/Create buttons use a plain action box, never FlowBoxChild hover wrappers.
Delete hides only non-built-in identities using a guarded head/default-CAS tombstone;
accepted revisions remain intact as historical data. A deleted application selection
returns to California Juvenile Dependency; old drafts cannot resurrect it. Historical pins never select guidance.
Classification has no pinned stage/context summary above About classification. Its collapsed disclosure contains the complete explanation followed by the progression line. Both About classification and About summaries expand to their full natural height in the page's ordinary scroll area, pushing editors below them; never put either explanation in its own capped scroller. Hearing/Report digest topics use retained inline expandable topic cards on their catalog page, not third-level editor destinations. Keep stable-ID buffers/undo across reorder and Save, with display-only prose unwrapping that preserves stored guidance until edited. Preserve flat RT-first, CT-second navigation with stage subtitles, followed by the combined First pages settings and separate report/form naming cards; never restore RT/CT child indentation or date editors. Keep full-width retained editors. Classification has only task-specific prompts; Common guidance is removed from the editor,
compilation and fingerprints. Schema 6 omits its resource entirely; explicit Profile settings
Save drops the old field and file rather than storing hidden text. Do not migrate private
snapshots in place. Naming uses separate approved-name instructions.
Hearing labels are dates; report Names extracts name/date only at independently
marked CT_report_first_page starts. Fully historical output without checks retains
its old run grouping when read; new Names work pauses until Advanced/Corrected/Dates
have supplied complete checks. Mixed/inconsistent report checks fail before model
work/publication. Basic taxonomy and stage order are unchanged; schema 8 adds the
new report-first-page marker/task. The
application taxonomy must preserve pre-profile structural labels including
RT_certificate and CT_certificate/CT_motion/CT_notice/CT_proof_of_service; do not
narrow it beneath the legitimate labels imported into private task guidance.
Use profile_contract.CLASSIFICATION_PAGE_TYPES (re-exported as classification_profiles.PAGE_TYPES)
for runtime prompts, validation and the editor's task contracts. Preserve those labels
through downstream stages, and continue rejecting invented/cross-side labels. Profile
editors advise on unsupported RT_/CT_/CR_ references without rejecting Save/load or
rewriting historical guidance; the token lint cannot prove semantic consistency.
General Court Record is retired from selection and starting-profile catalogs,
including saved heads of that built-in identity. California Juvenile Dependency is
the default and new-profile base; all available saved profiles remain usable as
bases. Retired General defaults resolve read-only to Dependency. Preserve General
snapshots and independent custom copies; no private migrations or deletions.
The resources/legacy_practice_profiles/general archive is compatibility-only for
old minute defaults and schema-1 editing, never a selectable public specialty.
Never auto-replace personal profiles or case pins with updated bundled resources. Contract changes participate in freshness; never migrate private guidance
or fabricate metadata to reuse incompatible checkpoints.
Summaries has exactly Hearing digest topics, Report digest topics and Minute orders.
Content schema 5 additionally removes overview instructions; the overview stage
compiles no profile resources. Profile settings has only Classification and Summaries.
Keep both overview skill paths identical in method: complete summary reads followed
by selective, short Markdown bullets, not another narrative summary. Include only
identity, latest posture and initial research leads; one fact in its best section,
major chronological turning points, neutral issue labels and material scope gaps.
Small/simple records warrant small overviews; no padding, word/event quotas or
page-count formula. Omit supporting particulars unless orientation-changing; preserve
material qualifications, identity-only participant metadata, no inferred appeal,
and the unchanged five headings/disclaimer. Use short fictional before/after examples
for each section to teach selection, not case facts or fixed section sizes. Omit evidence
inventories and routine negative checklists; preserve necessary qualifications and
claim-specific adjudication status, never blanket-label mixed matters unadjudicated.
Historical overview
prose is inert; only explicit Save publishes a current schema-6 draft. Preserve private
candidate guards and Focus's nonauthoritative orientation contract.
Content schema 4 removes role catalogs and participant instructions in addition to
schema 3's four extra summary instruction resources. Older schemas remain readable;
none of those retired fields enter any stage prompt or component fingerprint.
There is no Participants / Witnesses settings area. Participant identification uses
fixed practice-neutral instructions, source-described role labels and representation,
with no specialty catalog. Minutes use only their own order, never the participant
index or a profile role catalog. Source-map and hearing attribution consumers must
retain descriptive roles, examiner labels, attorney clients and legacy compatibility.
Do not import legacy extra-summary settings or move their prose into the core.
The specialty-neutral fixed method preserves the pre-profile baseline documented
in docs/summary-contract-reconciliation.md; topic catalogs supply personal focus.
Header Clear current case is selection-only: preserve all case/PDF artifacts and
unrelated configuration, invalidate stale dialogs and reset pending case state.
Profile settings works with or without a case; every explicit dropdown choice
atomically updates the application selection and survives restart. Clear preserves
it. Profile storage offers explicit save-to-new-folder/use-existing-folder flows;
portable registry/snapshots can synchronize, but the locator and locks stay local.
No startup migration. Keep originals and refuse overwrites, conflicts, unsafe paths
or partial synchronization. Require single-writer synchronization, never contact peers. Case metadata tolerates synchronized 0755/0775 and 0644/0664
modes with ownership/link/world-write checks. PortableProfileStore separately accepts
ordinary synchronized modes with content/ownership/link/world-write checks; private
XDG validators remain strict. Never chmod real synchronized metadata as a workaround.
Model settings has three direct destinations: OCR / Classify / Agent, initially OCR.
Agent's Shared PI settings has one PI model and one PI reasoning effort picker,
the PI command and refresh. Every PI operation (including case-name inference,
hearing/report digest extraction/synthesis and minutes) uses that shared selection.
Classification API and local OCR remain separate. Store PI selection only in the
effective PI preferences (external pi/settings.json or legacy checkout .pi/settings.json),
with global-default reasoning inheritance and PI's unsupported-level adjustment intact.
Retired summary_extract_*pi_* / summary_synthesize_*pi_* values (shared and per-kind)
are inert immediately without Save; preserve existing bytes/values, never create keys
on ordinary saves. No migration, artifact rewrite or settings-triggered regeneration.
Explicit work keeps effective-model/source/guidance checkpoint checks; unchanged
identity must remain reusable. Completion badges and Resume stay output-presence based.
Model settings has one OCR page: embedded-text/local-OCR selection above local OCR
settings. Left-hand categories are direct ActionRow destinations, not expanders
with single nested pages. Keep existing persistence keys; do not restore separate Prepare pages.

Legacy category guidance and first-page parental-attendance rules apply to
unassigned compatibility contexts. Bound profiles use accepted topic catalogs and
minute guidance with fixed attendance rules; identification is general for every
case. Historical specialty text remains for exact built-in recognition and supported
readers, not an active formal-proposal detector. Do not reintroduce Dependency rules
into neutral core contracts or remove existing unassigned-case support. Run isolated unit/GTK/pipeline tests, native guard and
resource validation after changes. Keep package-data declarations covering every
bundled profile resource; source deployments must retain their own `.pi/` tree.

## Transcript Page Breakdown

Keep Number transcript pages' Markdown a footnote-writing aid: fixed Quick reference
chart, one plain-text Suggested footnote per existing citation series in first-appearance
order, and only material Review notes. Prefer meaningful, reliable printed volume
numbers; repeated/unhelpful labels fall back to confirmed hearing dates or another
supported, unambiguous identifier. Concision must not erase necessary dates or scope
qualifications. Prefixes need not be volume numbers; physical volume breaks alone
never split series. Keep schema-v2 confidence/collision/range/anomaly analysis in JSON
and definitions consistent with `definition_draft`. No private-output/config migration,
new renderer or extra model pass. Explicit numbering reruns can change JSON and stale
downstream artifacts; never advertise a formatting-only refresh or reset prepared work.
Validate instruction contracts offline; live generation evaluation needs separate approval.

## Passive run metrics
- The runner's native stages and extraction/synthesis children may explicitly load the sibling `PiRunMetrics/run-collector.ts` via `recordprep/run_metrics.py`. This is the sole passive-observer exception to tracked `.pi/` resource confinement. It adds no tools/prompts and changes no publication authority, Stop/stall behavior or content-free stdout. One settled child is not whole-pipeline success. Skips and zero-model helpers produce no runs.
- Native tags use step IDs; summary tags use the five code-owned summary skill IDs (including `recordprep-summarize-minutes`), never item IDs/case names. Default archive is this source project's Git-ignored `.run-metrics/runs/` (may Dropbox-sync). Preserve absolute root/collector overrides and `PI_RUN_METRICS_ENABLED=0`. Sibling policy probes metadata with deadlines, collects only on Pi >=0.87.1, and warns/fails open without upgrading Pi or relocating archives. Tests must never load/save real config.

## Goal

RecordPrep converts OCR-readable legal-record PDFs into direct-source, citation-aware case bundles for Focus Agent search. It may create one concise, versioned, nonauthoritative case-orientation overview, but it must not create retrieval/optimization copies, persistent chunks, speaker-labeled transcript rewrites, embeddings, or vector databases.

## Entry points and modules

- `recordprep/cli.py`: command parser.
- `python -m recordprep app`: GTK application entry.
- `recordprep/ui/main_window.py`: Libadwaita UI, settings (one shared PI model/reasoning selection), direct-source pipeline (minute orders), and step handlers (hearing/report summary handlers are thin wrappers around `_run_pi_skill_step`).
- `recordprep/classification.py`: classification worker pool.
- `recordprep/config.py`: supported settings import surface.
- `recordprep/manifest.py`: manifest import surface.
- `recordprep/summaries.py`: summary path/link import surface.
- `recordprep/summary_editions.py`: page-matched Letter PDF editions and Focus page maps.
- `recordprep/minute_summaries.py`: single-stage direct-source PI minute summaries. Profile contract8 publishes Date — Hearing type and unbulleted Appearances / Orders / Next labels (bold in Focus), normally one or two plain-English headline outcomes; no separate party-position submission. Schema4 retains compatibility positions and complete-order evidence; old readers and unassigned first-page/reporting path stay separate.
- `recordprep/summary_agents.py`: two-stage PI summary pipeline — work items, fingerprints, canonical Markdown digest/meta publication with per-kind locks, quote span resolution, recurrence analysis, synthesis validation, and deterministic rendering.
- `recordprep/summary_categories.py`: strict loader for the tracked category-guidance resources; code-owned category ids/titles/order live here, editable guidance prose lives in `recordprep/resources/summary_categories/`.
- `recordprep/documents.py`: PDF merge, extraction, rendering, and OCR import surface.
- `recordprep/pi_runtime.py`: PI discovery/model settings, model context metadata, and summary context preflight.
- `recordprep/summary_preflight.py`: provider-qualified model identity resolution (full model id, never a basename; one discovery result reused per stage), model-visible component composition, honest UTF-8-aware estimate ranges, the capacity policy (known-oversized individual requests fail before the paid call; aggregate synthesis history warns and proceeds; unknown metadata stays visibly unknown), and the read-only `python -m recordprep.summary_preflight` diagnostic (no paid calls, no publishing lock, no writes).
- `recordprep/pi_bundle.py`: PI artifact/schema validation (including both summary PI stages).
- `.pi/`: tracked system prompt, project-local Agent Skills, sequential runner, auto-exit extension, and summary-tools extension.

Do not add a root-level `recordprep.py` shim. Use modern Libadwaita widgets and flat buttons.

## Quote display capitalization

quote_display.py owns the hearing/report synthesis display rule for all profiles and
unassigned cases. Preserve original evidence text, IDs, offsets and verification. Optional
per-section quote_capitalizations proposals map exact, used quote IDs to display text;
normalization and rendering both enforce one-for-one letter-case-only changes to all-caps
source quotations. Reject malformed, unknown, unused, mixed-case-source or wording-changing
proposals nonfatally; no automatic lower()/title() fallback and no extra model repair loop.
The rule tells the model to preserve names/acronyms/identifiers and retain uncertain token
casing; syntactic validation cannot prove semantic correctness. Newly rendered hearing
and report summaries omit capitalization announcements without changing normalization
or evidence; both kind-specific renderer identities are version8. Keep historical
candidate schemas supported and old stored output readable/untouched, not falsely current.
The synthesis-only extension wrapper reinforces one paragraph per array entry and
changes the submit schema without changing the base extraction extension/fingerprint.
Hearing contracts distinguish unlimited overall coverage from short focused paragraphs.
Open with substantive purpose or consequential result and necessary qualifications,
not roll calls/logistics. Do not preview and then repeat each party's arguments; group
shared positions while retaining different grounds/relief/reservations. Retain material
findings, burdens, evidence limitations, notice issues, conditions, review rights and
dates; omit routine inventories/recitals unless consequential. Keep conditional standard
directions conditional. Prefer meaningful anchors to stock appearances; read expanded
quotes grammatically without duplicated subjects/verbs or paraphrase-plus-quote repeats.
Never rewrite quotes or shift the speaker/actor/duty bearer. Reread conflicting digest
accounts, explain only supported changes, otherwise attribute the specific uncertainty;
counsel's account of a prior ruling is not a verified court finding. All in normal
synthesis, not a new pass. See docs/hearing-editorial.md. The hearing-only renderer8
omits the notice; the separate report follow-up now uses report renderer8 and the
canonical recordprep-synthesize-reports SKILL unchanged for profiles and unassigned
work. profile_skill_text selects that same file for staging and capacity estimates;
effective synthesis config hashes it, never the generic template for reports.
Report editorial method leads with attributed conclusion/development and necessary
qualification, short focused paragraphs, each fact once, meaningful grammatical
anchors and balanced counterevidence. No minute-style outcome cap, bullets, extra
pass, prose filter or private-profile rewrite. See docs/report-editorial.md. All
extraction/hearing/minute/native identities stay unchanged by the report follow-up.
Prior exact built-ins stay recognized, custom bytes preserved. No count quota, blocking
quality validator, repair loop or extra model pass. Apply the same hearing method to
unassigned compatibility work, retaining exact historical literals and custom bytes.
Normalize CRLF/CR and explicit blank-line breaks before collapsing soft-wrap whitespace,
including direct rendering and fallbacks; never mechanically sentence-split/truncate.
Reconciliation copies retained rows into current contiguous ordinals without changing
identity/evidence/fingerprints; freshness checks dataset identity/order as well as each
row, so shrinking a report worklist reuses extraction but must rerun synthesis. Stage both files, explicitly load only the wrapper for
synthesis, and include both in synthesis freshness/preflight/cache signatures. Existing
source/digest/private artifacts are never migrated. Test actual offline SDK schema acceptance,
source preservation, fallback, PDF quote spans, and reuse of existing extraction fingerprints.

## Native-stage freshness

Participants and overview use separate runtime fingerprints from native_freshness.py.
Fingerprint reachable local runner/validator definitions with only literal stage
branches specialized; unknown conditions retain both arms. Include the stage's
SkillStage declaration, shared safety code, model/reasoning identity and source
inputs. Do not hash the whole multi-stage runner for both stages. Stage prompts,
helper/guard resources and profile components remain independently checked.
Native and caption commands use the shared skill_commands.skill_launch builder:
literal space after /skill:name, never newline. Summary prompts re-export the same
builder without changing their established request bytes or delivery identity.
Native runtime contract 3 and caption inputs include slash-skill-space-v1; native
stage projections/caption inputs also hash the helper. All current source/component/
model/publication checks still apply. Pre-expansion identities are not equivalent.
The unchanged native_runtime_compat.json retains historical reviewed hashes only;
none has the required delivery identity. Never update its guards to bless broken
skill delivery. Future compatibility requires both the matching delivery identity
and exact reviewed current code gate. This is read-only inspection, not an artifact
migration: preserve saved bytes/mtime, badges and Resume; no automatic reruns.
Test stage isolation, actual installed-SDK body delivery/tool guards and true
invalidations. See docs/native-skill-delivery.md; earlier prerequisite-only reviews
in docs/hearing-selection-validation.md and docs/minute-selection.md are historical.

## Completion badges

Process text files is an in-place stage: raw `text_pages` presence is not its
output proof. Require `artifacts/text_processing.complete` plus text presence for
badges and Resume. Publish the receipt atomically only after all processing and
layout rebind succeed; invalidate before processing mutations or source refill.
Legacy bundles without a receipt remain pending, with no inferred/migrated marker.

Visual checkmarks are output-presence only (`output_presence.step_outputs_present`),
not current-generation freshness. Do not make existing output Pending for changed
models, profiles, timestamps, schema versions or metadata; do not add a stale-settings
badge. Missing output is Pending. Preserve CT-only participant applicability/skip.
Resume also skips existing outputs via `_resume_step_complete`; historical profile,
model, schema and timestamp mismatches must not stop continuation or force upstream
regeneration. Keep actual input/range validation, stage-local checkpoints and
in-flight publication safeguards, plus the source-reset protection below. This
supersedes older “UI completion” and downstream-freshness requirements below. Tests must prove badge inspection reads no profile/content
and changes no bundle or private settings.

## Resume and data preservation

Downstream stages consume saved upstream files, not historical generation settings.
No classification/naming/profile-boundaries marker gate before summaries; no current
summary/participant/overview metadata gate before overview/source-map publication.
Explicit classifier/boundary work fingerprints actual input bytes for this run.
See `docs/application-profiles.md` for contracts and reviewed native compatibility.

Resume never resets/deletes an existing bundle. Selection/layout reset flags block
continuation with an explanation, not automatic Create files. Missing source pages
with prepared work (including hidden profile-work checkpoints) block extraction.
The Create files worker is the shared safety boundary for all entry paths: refuse
reset requests, and no-op for a complete already-prepared source set without
rewriting its manifest. A same-layout manual selection is a byte/mtime-preserving
no-op; differing manual layouts after preparation are refused before publication.
Keep synthetic reopen/resume, all-entry-point preservation and actual GTK safety
tests. Never silently clear existing data to get a run going; use a separate folder
for deliberately changed source/layout. Private case recovery requires separate
copies, never forging freshness metadata or rewriting the user's configuration.

## Pipeline

1. Create files.
2. Detect transcript layout (PI).
3. Strip characters.
4. Infer case (PI; first three pages, private candidate, Python-only publication).
5. Basic/advanced/corrected/date/name classification.
6. Build/correct TOC.
7. Find/correct hearing, report, and minute boundaries.
8. Number transcript pages with PI. Python then normalizes every
   `citation_label`/`citation_key` to the canonical `PREFIX N`/`PREFIX:N` form
   (never model-authored `p.`/`pp.` notation) before participant indexing,
   summaries, or the source map trust the artifact.
9. Build `artifacts/participant_index.json` schema v4 with PI from appearances, express attendance/absence, unsworn colloquy, RT witness indexes, and sworn/examination evidence. A fresh, resolved CT-only layout (read through `transcript_layout.is_ct_only`, the single applicability predicate) skips this step entirely: the UI and `.pi/scripts/run_recordprep_skill.py` return a successful `Skipped — Clerk’s transcript only` no-op before any VTE/PI launch, pre-existing participant artifacts are ignored on disk and excluded from downstream freshness inputs, and the overview/source-map participant requirement is waived. Missing, malformed, stale, or needs-review layouts never authorize the exemption; RT-only and mixed records keep full participant validation and attribution.
10. Create summaries in three independently runnable stages. Hearing and report stages run the resumable two-stage PI pipeline (`recordprep/summary_agents.py` + `.pi/extensions/recordprep-summary-tools.ts`): stage one launches one fresh `--mode json --no-session` PI process per document whose only tools are `recordprep_get_source` (the document's complete source pages in one payload, with the full digest contract in the runtime prompt) and `recordprep_submit_extraction`; Python deterministically normalizes the candidate — agent-output problems are never fatal — injecting the runner-owned item id, reordering configured categories, ignoring unknown ones, filling missing or malformed categories with `digest: null`, and flagging sanitized warning codes (category ids and counts only) in the row metadata, while best-effort verifying each quote against its declared page (normalization, then case/typography; unmatched quotes are kept as submitted with `verified: false` rather than rejected) across the complete document, without proposal-cutoff rejection. Python is the sole canonical digest Markdown/metadata publisher under an exclusive per-kind lock (stable `.hearings_facts.lock` path) with atomic replace and a final newline. Stage two launches one fresh PI process per completed digest Markdown document — reloaded and validated from disk before synthesis, never the pre-publication in-memory rows — with dataset-only tools serving one Python-rendered Markdown block per document, a synthesis-only scratchpad tool (`recordprep_synthesis_scratchpad` read/replace, stored in extension-owned process-local memory separate from conversation history so notes survive context compaction; notes are orientation aids, never evidence, never published or logged, and they disappear when the process ends — synthesis restart resumability is explicitly deferred), and a `view: "submitted_section"` read for already-submitted drafts after compaction; the model works incrementally — overview and scratchpad first, then documents in boundary order or agent-chosen logical groups, submitting each section as it completes it and replacing its scratchpad notes, with revisions by resubmitting the same item id that never move later developments into earlier event chronology — and always emits the sections it has; Python validates the candidate's private coverage diagnostics (well-typed unread/missing counts only), reorders known sections, drops unknown ones, fills missing or empty sections with a deterministic prose fallback from the category digests, resolves known quote placeholders, replaces any submitted section that still references unknown quote ids with the same digest-prose fallback (a sanitized warning — never silent in-sentence deletion of quoted wording), and flattens any generated page-link markup, then a deterministic renderer publishes the final plain-text summary (ordinary curly-quoted quotations, plain `Date — Hearing` headings, no generated `](page:NNNN)` markup) plus final metadata atomically. Quality problems — typed quotation marks, unverified or duplicate quote use, out-of-range quote length, ellipsis or terminal punctuation inside a quotation, technical metadata in narrative, and repeated report passages — are sanitized warnings, never failures. Item IDs are stable by kind and start page; duplicate stable ids and overlapping document ranges are rejected before any paid work. Generation fingerprints cover every payload dependency — end pages, labels, source text, the effective guidance and category-description text, the effective provider/model/thinking (inherited shared PI settings), the private participant context, transcript citation labels, and the complete-source contract — so any of those changes mark only the affected rows regeneration-pending. Digest and final metadata use schema version 5 for profile-bound work and version 4 for legacy unassigned work with explicit dependency/fingerprint fields; schema-3 metadata stays readable but its freshness is unproven, so those artifacts report as regeneration-pending rather than current. Artifact integrity validation (structural consistency) is separate from current-generation freshness (`summary_stage_freshness_issues`), and explicit summary generation uses both for its own checkpoint reuse; downstream overview/source-map work consumes saved text without historical freshness requirements; the UI uses a reusable stage-input snapshot cached by an invalidation signature (settings, resources, boundaries, source pages, published artifacts) so completion predicates never rescan the record repeatedly. Each stage writes only its own final summary file (`hearings_sum_<case>.txt` / `reports_sum_<case>.txt`) and completes independently; hearing extraction requires the validated participant index, while report extraction does not. For a fresh CT-only layout with a valid empty hearing-boundary array, hearing extraction builds zero work items without loading participants and the existing zero-item publishing flow applies with no model calls; CT-only with nonempty hearing boundaries fails with an actionable layout/boundary inconsistency, and transcript-layout changes are watched in hearing-summary freshness/cache signatures so a layout decision cannot reuse a stale exemption. A zero-item boundary set publishes a valid header-only digest Markdown document and a title-only summary without a paid call. Existing v2 `*_digests_*.jsonl` bundles migrate losslessly, with zero model calls, when their summary stage next runs under its lock: Markdown is authoritative once present, only missing or stale rows re-extract, and the retired JSONL is removed only after the Markdown, metadata, and final summary have published and validated; a legacy pair whose data and metadata disagree is preserved and reported. Legacy v1 `*_facts_*.jsonl` artifacts are ignored (never converted) and removed only after the digest pipeline publishes successfully; the minute-order stage uses the single-stage PI path described below and writes only its own minute summary/checkpoint/metadata.
11. Build page-matched summary editions deterministically: directly after the three summary stages (the retired Add-links step was removed), render each summary into a fixed US-Letter PDF and a schema-v2 page-map sidecar under `summaries/editions/`. The PDF is the immutable pagination authority under the fixed `recordprep-summary-letter-v3` layout (Letter portrait, 54-point margins, 11-point body, 1.18 line height, 0.5em paragraph spacing, `Page N of M` 9-point Times footer, numbering restarting at 1 per category). Recognized quoted phrases render in bold through the built-in Nimbus Roman bold face and lose only their outer style-matched straight/curly double quote delimiters — a presentation-only transformation of the printable representation; the canonical `.txt` summaries keep every quotation mark byte-for-byte, and summary generation, digests, prompts, and extraction fingerprints are untouched. Recognition is conservative: style-matched double quote pairs within one source line whose content survives rendering-equivalent normalization and that never partially overlap a trusted link span; unmatched delimiters, whitespace-only pairs, and nested quotations stay literal, and the recorded quote-presentation policy in the layout metadata makes the transformation explicit. The sidecar records per-page selectable body text, trusted record-page link spans and targets, required quote-fragment spans (exact offsets into the page text, exact labels, and the complete quote content for record-wide phrase search on fragments that wrap across a paper-page boundary, derived from the same monotonic rendering-normalized alignment as coverage and never by global substring search), inclusive source-line ranges, and source/PDF hashes; generation verifies normalized page text reproduces the printable source exactly and fails rather than dropping a link, a bold span, or text. The body renders with PyMuPDF's built-in Times-compatible Nimbus Roman face, requested through the CSS `Times` family, so pagination is deterministic and never depends on locally installed fonts, Fontconfig, or any external font file. The sidecar layout metadata records the complete typography contract plus the quote-presentation policy, and validation rejects any sidecar whose schema, layout ID, fixed metrics, or policy differ, requires well-formed nonoverlapping quote spans that completely map every recognized quotation, and tolerates quote spans overlapping link spans (explicit page-link navigation wins in Focus), so pre-v3/v2 editions show the build step as pending until rebuilt (old editions remain untouched until a successful rebuild). Build and validate all three candidates before replacing any edition, publish PDF then sidecar atomically, and invalidate only the rerun category's edition after a summary text change. Editions are never Agent evidence or source-map search paths. RecordPrep/`summary_editions.py` owns this logic, re-exported through `recordprep/summaries.py`.
12. Create the concise nonauthoritative `artifacts/case_overview.md` orientation aid.
13. Build source-map v2 last.

Transcript layout detection runs immediately after Create files, once per new
or changed bundle, and publishes `artifacts/transcript_layout.json` schema v1.
It searches OCR text first and opens only targeted page images (soft budget of
12 PNGs per detection), never a full image sweep. A high-confidence agent
result continues automatically; ambiguity publishes a structurally valid
`needs_review` artifact and pauses before any layout-dependent mutation.
Layouts are case-local, bound to the current page count and input signature;
a value from another case is never used. RecordPrep may atomically rebind an
unchanged, resolved decision after its own guarded text-only normalization.
It must rerun detection when numbered page identity or paired images change,
or when text changes outside that controlled pass. All downstream routing
reads the validated artifact; the manifest `rt_ct_split_mode`/`rt_ct_split_page` fields
are legacy compatibility mirrors only. The retired `rt_ct_split_page` config
key is removed during config migration.

Profile-bound participant generation uses participant_candidates.py to normalize NEW
private schema-4 candidates only, never historical/published artifacts or private
settings. Missing optional statuses become unknown; unsupported entries are omitted
with explicit quality warnings, not invented. Keep reader validators unchanged and
retain template-review, unsafe-path and examination-range failures. The native guard
must return both helper stdout and stderr, stop after two failed validation attempts,
and terminate model work on full success, including successful full validation during
a partial request. Helper-owned reviewed/total/complete progress prevents repeated
partial checks without review progress; those also write the failure marker. Explicitly
allow read of the staged SKILL.md for both native profile stages, never its directory,
helper scripts or arbitrary schema files. Test real SDK instruction reads and termination,
not just fixtures which preconstruct a valid candidate. A private exhaustion marker prevents later
publication. Stop still prevents publication; do not turn unreviewed templates into
completed empty hearings. Test normalization, helper CLI, actual extension and runner.

The participant index is hearing-scoped and separates counsel, non-counsel participants, and witnesses. Its helper publishes a temporary, nonauthoritative worklist under `temp/` that scopes first/appearance pages, RT-index pages, and oath/examination/attendance markers without copying source-page text. The agent processes one hearing at a time, reads single source pages, persists completed hearings incrementally, and uses partial validation after batches of at most five hearings. It must never concatenate the complete RT or a multi-hundred-page run. Full validation rejects the unreviewed template placeholder. Law firms/agencies are organizations, not attorney aliases. Q/A alone is not testimony. Unknown/conflicting identity, attendance, witness, or counsel evidence must remain explicit rather than guessed.

All minute runs stage the same specialty-neutral recordprep-summarize-minutes SKILL
unchanged; never substitute another hidden skill for profiles. The alternate
resources/profile-minutes.md is retired. Shared selection normally chooses one or two
headline outcomes, not every material detail or a miniature order. Preserve the
qualifications needed for those outcomes; another outcome only when omission would
mislead about disposition. New profile submissions omit positions; an essential
objection belongs with its ruling. Python publishes Date — Hearing type followed by
only Appearances / Orders / Next labeled lines, with no dashes. Focus's minute-only
label emphasis renders these plain-text prefixes bold, never as quote/search links.
Keep exactly one blank line between entries and no blank lines inside each entry;
Focus paginated display/search must preserve that grouping too. Minute PDF editions
use zero paragraph margin within adjacent source lines and one body-line-height gap
at source blank lines. Their v3 layout metadata additionally requires
`minute_spacing: source-blank-lines-v1`; older minute editions require only a
deterministic edition rebuild, not model regeneration. Restore page-map source
breaks via monotonic coverage alignment before rebasing link/quote offsets;
MuPDF merges tightly spaced lines into blocks. Minute PDF field prefixes
Appearances: / Orders: / Next: are bold (colon included), not quote/link spans;
`minute_label_emphasis: bold-field-prefixes-v1` separately stales older editions.
Hearing/report spacing and emphasis are unchanged.
Orders uses simple, plain English, keeping necessary legal distinctions/conditions.
Exclude routine report receipt/preparation, filing/portal deadlines, clerical/calendar
mechanics and conditional late-filing sanctions warnings. An actually imposed
consequential sanction or substantive relief deadline is different. For administrative-only
orders use 'No substantive orders recorded.', not filler or an invented ruling.
Next contains only the next substantive
hearing type/date; exclude report-only hearings and future report filing/due dates,
even if earlier. Do not move the report calendar into Orders. No hard item/word quota, truncation,
blocking quality gate, extra pass or private-output migration.
Profiles supply specialty terminology, relevant participants and emphasis, subordinate
to shared selection/safety; never hard-code juvenile/parent rules into the neutral
method. PROFILE_MINUTE_CORE defines the structured response and complete-order
attendance evidence; counsel alone and missing names establish neither presence nor
absence. There is no policy selector; old policy fields are inert and exact former
bundled prose resolves to the new default without private writes (including the
preceding broad paragraph and compact-with-report-date defaults; never fuzzy-match
custom prose). Contract8 and
recordprep-minute-compact-labels-2 honestly stale former minute generation. Preserve
explicit compact-list-1 rendering and historical paragraph callers; do not silently
reformat saved summaries. See docs/minute-plain.md for current language/presentation
and the narrow Focus consumer dependency.
Historical checkpoints/readers/rendering stay unchanged; explicit reruns incur paid
per-order work, then reuse current rows. See docs/minute-compact.md (current) and
docs/minute-selection.md (first attempt). Checkpoint/final metadata4 retains positions and
next_hearing instead of reporting status, source-described appearance roles and no
catalog/policy metadata; historical1/2/3 readers preserve old output.
The following legacy minute prompt applies only to unassigned compatibility work.

Minute orders run one fresh, restricted PI child per complete boundary-scoped order using the shared **PI model** and reasoning preferences. There is no digest stage, no direct API credential dependency, and no source windowing. Preserve the immutable minute prompt: hearing name, reported/not reported, each parent's personal appearance from the FIRST PAGE only (attorney-only listings mean not present), and concise actual orders. Custom `summarize_minutes_prompt` guidance stays intact and is subordinate. The dedicated `.pi/skills/recordprep-summarize-minutes/` skill and `.pi/extensions/recordprep-minute-tools.ts` expose only source-read and candidate-submit tools; Python validates affirmative first-page quote locations, marks unverified attendance unclear with sanitized warnings, and renders the paragraph. Location verification is not semantic proof of attendance. Ambiguous evidence stays unclear. Unusable/missing candidates preserve the prior final rather than inventing a summary. Python owns `minutes_sum_<case>.rows.json` checkpoints and `.meta.json`, uses the per-kind lock and atomic writes, and fingerprints source, boundaries, labels/citations, guidance, model/reasoning and dedicated resources. Resume regenerates only missing/stale orders; completed checkpoints need no Pi call. Legacy direct-API text remains untouched but pending until regenerated. UI completion/Resume use output presence; overview/source-map prerequisites use saved text, not current minute metadata. Only changed minute text invalidates its edition. Stop/stall, private workspace cleanup, model capacity preflight, and content-free logs reuse the summary runner. Do not alter the hearing/report extension merely to add minute tools, since its hash is a hearing/report synthesis dependency.

Summary extraction and minute summarization serve each document's complete source pages in one payload — neither is windowed. End-user prompt testing and its direct-API request/payload paths are removed. Ordinary Settings edits production credentials/models/machine settings, never legacy prompt prose or inert sandbox keys. There are no output word targets: summary length follows each document's substantive complexity, and conciseness comes from selecting significant information and avoiding repetition — never from a numerical limit. The retired `summarize_hearings_target_words` / `summarize_reports_target_words` keys (and the legacy `summarize_reports_window_target_words`) remain stored but are inert: nothing reads them, the Settings-save flow preserves any existing values untouched, and new configurations never create them.

Report extraction serves the complete document, including proposed-findings/order
sections and later discussion. There is no detector, injected cutoff delimiter or
cutoff-based quote rejection. Current guidance distinguishes requested relief and
recommendations from actual orders and omits routine boilerplate unless consequential.
Keep historical specialty prompt strings and exact-text recognition: they prevent
obsolete built-ins from being reattached as personal instructions while preserving
genuinely custom prose byte-for-byte. They are compatibility data, not an active
source filter. Markdown digests are the current synthesis input; historical v2
JSONL conversion remains guarded and supported, not a current fact-inventory path.

Canonical digest rows carry trusted Python-injected metadata (profile-bound row schema 3, legacy unassigned row schema 2, kind, stable item id by kind and start page, ordinal, label, page range, source and generation fingerprints, sanitized `quality_flags`) and categories in exact configured order. Bound profiles use their accepted topics; legacy unassigned hearings use `parent_appearances`, `evidence_considered`, `testimony`, `disputed_legal_issues`, `party_positions_and_reasons`, `court_orders_and_reasons`; reports use the expanded twelve-category schema ending in `placement_and_caregiver_adoption_approval`. The canonical store for those rows is the versioned Markdown document `summaries/<kind>_digests_<case>.md` (profile-bound format 2, legacy unassigned format 1, independent of the row schema): a document title with a generated-artifact notice, one level-two heading per document (label, item id, source-page range), one level-three heading per category (readable name, category id), digest prose, an explicit `No material content.` null marker, a `#### Direct quotes` subsection carrying each quote's id, file page, and verified status, and a `No direct quotes.` marker for a non-null digest with an empty evidence bank. Reserved `recordprep:digest-*` HTML comments carry fingerprints, ordinals, quality flags, source offsets/hashes, and schema identifiers — never digest or quote text; content is reversibly escaped so source text cannot create headings, comments, links, or delimiters; parsing accepts only the generated grammar, validates reconstructed rows against canonical re-serialization, and rejects duplicates, malformed structure, metadata disagreement, unsupported versions, and truncation with sanitized location-based errors. The Markdown file is for inspection, not manual editing. Each category canonicalizes to exactly one `digest`: `null` when the source has no material orientation-worthy content, or `{text, evidence}` holding one concise salience-based synthesis (representative examples, not an inventory; a development lives in its best category once) plus a small bank of short verbatim quotes — continuous two-to-five-word source phrases, preferably distinctive three-to-five-word anchors, chosen for important points with no fixed count. Quotes are checked against the declared page after Unicode/whitespace normalization, with Python recording the original offsets, canonical quote id, and page hash when the quote is found. Ambiguous matches keep the first occurrence, and unmatched quotes are flagged `verified: false` and kept: quote fidelity is never a pipeline failure. Stage one records developments described as current/recent by a report; stage two determines what is genuinely new. Recurrence analysis is retained for diagnostics and prompt tuning only. All agent-output handling is nonfatal: only source/model execution failures, generated-store corruption, rendering integrity failures, or atomic publication failures may stop a run rather than publish corrupt data, and they preserve the prior final summary. All-null documents keep their required document heading with no sentinel paragraph; unusable extraction is distinguished from genuinely empty categories through private warnings only.

One effective-guidance contract governs both summary phases (`resolve_phase_guidance`): the immutable relevance, scope, schema, quote, and safety contract is always the main guidance; previously shipped built-ins — including the retired digest built-ins with length and six-quote guidance — are recognized by exact historical text reconstructed from tracked history and advance to the current contract without reattaching retired text, while custom prompts remain byte-for-byte unchanged in configuration and are composed as lower-priority additional guidance that cannot override the immutable contract. Per-category guidance prose is loaded and frozen per stage from the tracked resources under `recordprep/resources/summary_categories/` (ids, display titles, ordering, and null semantics stay code-owned; the strict loader rejects missing, duplicated, unknown, reordered, or empty sections with actionable errors before any paid work), and the effective description text is part of each row's extraction fingerprint, so editing one kind's file stales only that kind's rows. Do not reinterpret the retired paragraph-count setting as a page count. Profile settings uses digest topic cards and minute-order guidance, never separate hearing/report review or writing instruction fields. Save writes a private customization, never the tracked bundled/category files; legacy prose stays available to compatibility loaders without duplicate ordinary-settings editors. The hearing source payload includes validated participant-index context privately under `PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY` — counsel, participants, and the witness/testimony picture (verified witnesses with mapped, cited examinations, or explicit `Testimony: None.`) — as attribution context only; every submitted fact still requires evidence from original hearing pages. Summaries are nonauthoritative; source pages remain the factual authority.

The case overview is a schema-versioned orientation aid derived from source summaries and, when participant indexing applies to the resolved layout, participant metadata; a CT-only overview uses the report/minute summaries and the valid empty hearing summary and identifies the absence of reporter-transcript attribution in Record Scope. It is never authoritative evidence. An explicit overview rerun uses current input text, participant data and layout; their historical generation settings do not block downstream reuse.

Source-map v2 uses original `text_pages`, boundaries, transcript citation metadata, participants, examinations, warnings, the case-overview path, and summary paths. For CT-only records the final publisher uses an empty in-memory participant structure (`hearings: []`), omits `paths.participant_index` and `manifest.files.participant_index` (a CT-only published participant path is rejected), records the explicit unavailable-attribution scope warning, and keeps schema v2 unchanged; RT-only/mixed maps publish the normal validated participant data and canonical path. Only source pages are authoritative evidence.

## PI rules

- Keep every RecordPrep PI resource under tracked `.pi/`.
- Invoke one explicit skill per UI row with `.pi/scripts/run_recordprep_skill.py`.
- Native VTE stages stage `.pi/SYSTEM.md`, one skill, and the applicable auto-exit, case-name-tools or native-profile-tools guard into a private workspace. Summary stages stage `.pi/SYSTEM.md`, the phase skill, and `extensions/recordprep-summary-tools.ts` (plus the explicitly loaded synthesis-only `extensions/recordprep-summary-synthesis-tools.ts` wrapper for synthesis, or the separate `extensions/recordprep-minute-tools.ts` for minute orders), with `--mode json --no-session --approve`, an exact custom-tool allowlist, optional runner-owned `--provider`/`--model`/`--thinking` overrides, and a unique private cache workspace and candidate path removed in `finally`.
- Preserve PI's native interactive VTE UI for the native stages.
- Infer case uses recordprep-infer-case and its dedicated case-name-tools guard:
  read only up to three staged text pages, write/edit only the private candidate,
  no shell or canonical file access. Python checks case identity/selection, source
  inventory/bytes, shared model preferences, contract resources and prior output
  before atomic publication. Unknown/invalid/missing candidates and Stop preserve
  the old name. Model settings no longer exposes a caption API; retired credentials
  and prompts stay inert/untouched. Keep the separate native profile guard unchanged.
- Validate each stage after PI exits; summary children publish only after Python-side validation of the candidate.
- The runner monitors session-file growth and child CPU state for native stages and JSON-event activity for summary children. Summary children are consumed through timed non-blocking polling, so a silently hanging child still triggers a visible stalled-stage warning and Stop stays responsive; a stall never kills PI automatically — the user must press Stop. Each summary child reports sanitized aggregate telemetry (elapsed time, supplied usage numbers with authoritative final-message usage replacing streamed totals, peak reported context, compaction count, tool-call count) — never model text, tool arguments/results, scratchpad notes, or provider error bodies.
- Stop signals the runner, terminates the active child's complete process group, escalates to SIGKILL only when SIGTERM fails, releases locks, restores the row to Pending, and prevents the next child or downstream stages from starting.
- PI launch logs the immutable bundle root. RecordPrep warns when a parent folder's apparent appellate case number conflicts with manifest/PDF identity, but never moves or renames private case data. Summary child output never contains prompts, source text, tool arguments/results, model prose, or digest facts — only phase, ordinal/count, event class, PID, elapsed/stall information, and sanitized error codes. Synthesis children receive structured, nonfatal correction feedback from the section-submission tool (invalid quote ids with the allowed ids, advisory typed-quotation-mark and zero-placeholder notes); the feedback stays inside the private model/tool exchange, and public logs carry sanitized codes and counts only.
- Harden executable resolution before any `--version` or agent spawn: never attempt a nonexistent configured path; rediscover only for `pi` or a known legacy default location and fail early with the discovered alternative for an arbitrary missing custom command. The summary-resource minimum is PI 0.85 while Node 20+ stays a documentation-level dependency; never hard-code an absolute installer path.
- All PI operations share one model and reasoning selection from the effective PI preferences file; there are no per-stage summary or native overrides. The retired `pi_stage_<step>_pi_*` config keys are ignored on read and removed only by an explicit Settings save.
- The transcript-layout skill writes only `artifacts/transcript_layout.json`; the runner accepts a structurally valid `needs_review` artifact, while RecordPrep treats only a resolved, fresh artifact as step completion. Direct participant-stage invocation of the runner exits 0 with the explicit skip reason for a CT-only record before any PI executable/version check or workspace creation.
- Transcript numbering, participant, and summary stages must not update `manifest.json`.
- Profile-bound overview receives an explicit APPLICATION INPUT MANIFEST containing
  the same exact absolute paths as its read allowlist: three canonical summaries,
  layout, staged skill, and participants only when applicable. No directory discovery,
  guessed names, case_name.txt or manifest.json reads. Python publishes only the private
  overview candidate. Test actual SDK reads/offset continuation and the runner's mixed
  and CT-only manifests, plus deterministic source-map publication and failure preservation.
- The unassigned case-overview skill writes only `artifacts/case_overview.md`.
- The final source-map skill is the single manifest publisher and also publishes the `transcript_layout` path.
- Do not add an agent framework, subagent abstraction, or runtime npm install.

## Source extraction

- Use `pdftotext` with `physical=True` for `text_pages/0001.txt`, etc.
- Render grayscale 300-DPI `image_pages/0001.png`, etc., with PyMuPDF.
- Preserve source page identity and never place private case content in tests or commits.

## Development commands

```bash
uv run python -m recordprep app
uv run python -m unittest discover -s tests
uv run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
python3 .pi/scripts/run_recordprep_skill.py --validate-resources
uv run python -m recordprep.summary_preflight --case-bundle PATH --kind both
```

Use the Agent Skill validator for every changed skill. Keep `pyproject.toml` and tracked `uv.lock` synchronized. GTK4 VTE, PI 0.85+ (0.80+ for the native stages), and Node 20+ are system/runtime dependencies.
