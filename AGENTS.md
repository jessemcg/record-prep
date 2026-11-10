# RecordPrep Agent Notes

## Purpose and scope

RecordPrep prepares original OCR-readable court-record PDFs into direct-source,
citation-aware bundles for Focus. Only source pages are factual authority. Summaries,
participant metadata and the concise case overview are nonauthoritative. Do not add
retrieval copies, persistent chunks, speaker-rewritten transcripts, embeddings,
vector databases, an agent framework, subagents or runtime npm installation.
Use `python -m recordprep app`; never add a root `recordprep.py` shim.
Keep README minimal; implementation details and validation belong in `docs/`.

## Safety and development environment

- Read `../UvEnvironments/README.md`. Use its absolute `project-env` helper:
  explicit `sync RecordPrep` provisions managed Python 3.13; `run RecordPrep COMMAND`
  executes without downloads/sync. Home/Work only, never Laptop. No Dropbox `.venv`,
  inherited foreign environment or bare `uv run/sync`. Same-project children use
  `sys.executable`. Keep `pyproject.toml` and `uv.lock` synchronized.
- Tests use disposable tracked-source checkouts (basename `RecordPrep`), separate
  machine-local environments, temporary HOME/XDG/Pi state and synthetic sources.
  Use paired `--project /tmp/.../RecordPrep --environment /tmp/.../env` overrides.
  Disable metrics with `PI_RUN_METRICS_ENABLED=0`; use fake/offline providers, never
  real credentials, private configuration or client records as fixtures.
- Never rewrite, migrate, delete, normalize or chmod private config, profile stores,
  case metadata or prepared artifacts to make code/tests work. Preserve unknown
  settings, existing inert values and absent keys. Report private-file problems;
  recovery requires separately authorized copies, not fabricated freshness markers.
- Investigation, execution and GUI validation stay on this computer. No peer probes,
  remote execution or cross-computer acceptance. Respect single-writer synchronization.
- No paid generation/evaluation, real-case processing, application restart,
  deployment, commit or push is implied by source cleanup. Obtain authorization
  for publication; if shared readers change, publish compatible Focus first.
- Preserve unrelated user changes. Keep source pages and frozen historical fixtures
  intact. Offline tests establish contracts/safety, not legal accuracy or model quality.

## Current ownership and compatibility

Current content schema is **14**, profile API **1**: bundled Dependency **1.19.0**
and Criminal **1.1.0**. Profile settings has exactly three editable destinations:
**Report Names**, **Procedural Filing Names**, **Report digest topics**, grouped under Document
naming and Summaries. Hearing topics, motion naming/topics, minutes, classification,
dates, participants, caption and overview are application-owned for every assignment,
including custom, historical and unassigned contexts. Historical profile/config prose
for retired methods stays literal/readable but never supplies instructions or hashes.
Only explicit Create/Save/Reset publishes current revisions; no private migration.

- Dependency is the initial selection and new-profile base; both bundled profiles
  and available saved profiles can be bases. Criminal has 1 report rule / 11 procedural-filing
  rules / 9 report topics; Dependency has 1 / 5 / 12. Preserve shipped resource bytes
  and legal scope absent a concrete authorized change. See
  `docs/california-criminal-profile.md`, `docs/dependency-report-naming.md`.
- General Court Record is retired from selection/bases, including edited built-in
  heads. Old General defaults resolve read-only to Dependency; independent custom
  copies remain usable. Its archive and frozen recognition-v1/v2/profile resources
  are compatibility data, not dead code. Do not delete historical minute extensions
  or generic summary templates without a separate dependency review.
- Only `recordprep/profile_contract.py` and `profile_artifacts.py` are vendored
  byte-identically with Focus. Coordinate changes to those two files; no runtime
  sibling imports. Focus has one neutral research method, no profile counterpart.
- Profiles are application-wide, independent of bundles. Create files writes no
  profile pin. Old pins are inert and untouched; missing/malformed historical pins
  never block browsing or new work. Selection/Save changes no prepared output.
  Missing current instructions block new work, not browsing.
- Keep historical readers/serialized IDs and recorded semantics. In particular,
  `parent_appearances` stays the hearing ID although its current title is Appearances.
  Never relabel old rows as current or bless fingerprints to reuse incompatible work.
  See `docs/practice-profiles.md`, `docs/application-profiles.md` and the specific
  ownership documents linked below for schema transitions and adoption.

## Settings, storage and installation

- Model/Profile settings have separate persistence boundaries. Use expandable homes
  and retained full-width editors, modern Libadwaita widgets and flat buttons, not
  permanent sidebars. Save all draft pages without closing/changing destination;
  only successful persistence advances the baseline. Close offers Keep Editing /
  Discard Unsaved Changes, never Save-and-close. Preserve stable IDs, buffers, undo,
  selection and viewport across reorder/Save; unwrap display prose only until edited.
- Reset to bundled… → Reset and Save is the confirmed immediate-save exception:
  exact validated shipped resources/identity, separate replacement draft, production
  preview and guarded transaction. Never normalize through editable_profile, mutate
  discarded drafts, or refresh stale expectations to force publication. Preserve
  ownership/history. Undo is a new unsaved edit, not storage rollback.
- Profile settings edits the selected profile, no General page, profile picker or
  default switch. Create profiles is a hamburger link below Profile settings; flat
  Cancel/Create actions, no FlowBoxChild wrappers. Delete hides only personal identities
  via guarded head/default CAS, retaining accepted revisions; stale drafts cannot
  resurrect them. Deleting selected personal guidance returns selection to Dependency.
- Naming/topic cards are retained inline expanders, not third-level destinations.
  About classification/summaries expand naturally in the ordinary page scroller,
  never capped scrollers. Keep the pipeline explainers/progression; no extra ownership
  paragraph, pinned stage/context header or catalog-entry hint. Fixed methods are
  inspected in existing View full prompts, ignore unrelated invalid drafts and have
  no template/draft controls. No classification menu/reference window/inspector mode.
- Clear current case is selection-only; preserve all PDFs, bundle files and unrelated
  config, invalidate stale dialogs, stop work/close TOC editor first. Profile settings
  works without a case; selection survives Clear and restart.
- Profile locators/locks stay local. Portable registry/snapshots may synchronize;
  no storage-folder menu, startup migration, peer contact, overwrite or conflict repair.
  Case metadata and PortableProfileStore tolerate synchronized 0755/0775 and 0644/0664
  with ownership/link/world-write checks; private XDG stores remain strict.
- Model settings has OCR / Classify / Agent, initially OCR. OCR combines embedded-text
  selection and local model settings, retains command editor/readiness/server/Stop.
  Classify is API-only: URL, vision model, required key, workers, disable reasoning.
  Retired local-vision flags are inert unknown data, not launch/slot/credential controls.
  Agent has one shared Pi model/reasoning selection, Pi command and refresh; no per-stage
  overrides. Save effective external `pi/settings.json` or legacy checkout preferences
  only, retaining global inheritance/unsupported-level adjustment. Retired summary
  overrides remain inert/preserved; retired native stage keys are removed only on
  explicit Settings save. No settings-triggered reruns or artifact rewrites.
- `model-settings --stdin` precedes GUI/OCR/Pi imports; use only the owner-selected
  absolute config, shared Pi and classifier request connection. App-owned vendored
  schema/store use CAS/locks; stale writes fail even without raise_errors. Failed
  drafts never become baselines; Reconcile/Retain receipts are not rollback authority.
  RecordPrep settings accept owner/primary-group 0664, not world/foreign-group write,
  wrong owner or extra links. Private state/locks are 0700/0600. Stable writer locks
  live under local `$XDG_STATE_HOME/recordprep/settings-locks`, keyed by absolute path,
  never adjacent to synced settings; do not delete locks. Old adjacent locks are ignored;
  close all processes before lock-policy upgrades. Cooperating processes need identical
  local XDG state. Preserve this RecordPrep-specific policy when refreshing vendored code.
- Ship no personal `.pi/settings.json` or general model/reasoning seeds. Missing
  preferences work and stay absent until explicit model/effort save; unrelated saves
  never create them. Enable skill expansion only in private stage workspaces.
- Public install finishes/persists receipt/shows success before optional Pi. Skip,
  cancel or failed Pi cannot invalidate installation. No install-time credentials,
  model selection or paid verification. Standalone installs need no sibling project;
  use absolute RECORDPREP_CONFIG_DIR while tracked `.pi/` stays the resource root.
  Never recursively purge XDG settings or personal profile revisions on uninstall.
  Public runtime helper: `scripts/recordprep-env check`, explicit `sync`, `run`.
  See `docs/source-install.md`, `docs/pi-inheritance-validation.md`,
  `docs/unified-settings-validation.md`, `docs/bundled-reset-validation.md` and
  `tests/test_model_settings_permissions.py` / CLI contract tests.

## Pipeline and source preservation

Create files → Detect transcript layout → Strip characters → Infer case → Basic /
Advanced / Dates / Names / Agent correction → Organize motion papers → Build/correct
TOC → Find/correct boundaries → Number transcript pages → Participants → independent
hearing/report/motion/minute summary stages → deterministic summary editions → concise
case overview → deterministic source map. See `docs/workflow.md`.

- Extract physical page text with `pdftotext(physical=True)` into `text_pages/NNNN.txt`;
  render grayscale 300-DPI images with PyMuPDF. Preserve every physical page identity.
- Resume never resets/deletes bundles. Layout/selection reset flags block with an
  explanation. Missing source pages with prepared work, including hidden checkpoints,
  block extraction. Create files is the shared safety boundary: refuse resets; complete
  prepared inputs are a byte/mtime-preserving no-op. Same manual layout is a no-op;
  differing layouts after preparation are refused. Never clear data to get work going.
- Layout artifact is case-local/schema1, bound to current input identity/page count.
  OCR-first with targeted images (soft budget 12), no full image sweep. Ambiguity
  publishes needs_review and pauses. Only guarded text-only normalization can rebind
  an unchanged resolved layout; changed pages/images or uncontrolled text require
  detection. Manifest split fields are legacy mirrors, not routing authority.
- Caption uses fixed neutral `case_name_prompt.py`, native Pi/shared model and private
  candidate, first three source pages only. Python checks selection/source/resources/
  model/prior output before atomic publication. Invalid/unknown/Stop preserves old name.
  Retired caption API/config/profile prose stays inert; no automatic bundle renaming.
- Recognition-v4 owns the taxonomy and five start checks, including bounded custom
  procedural instruments, not all pleadings/exhibits. Embedded transcripts stay in outer
  CT (normally CT_other), never reopening RT. RT_body/CT_notice display as Hearing body/
  Hearing notice without key changes. Preserve certificate/motion/notice/service labels;
  use CLASSIFICATION_PAGE_TYPES, rejecting invented/cross-side labels. Hearing notices
  and service proofs are not Forms; qualifying Notice of Appeal forms remain Forms.
- Substantive requests within an existing proceeding are motion papers even on standardized forms, including status/participation requests. Non-motion procedural filings retain legacy CT_form/form IDs; initiating pleadings and administrative updates are not motions merely for requesting relief. Recognition-v1/v2/v3 remain historical resources.
- Report/form catalogs are naming-only; no page/start injection or CT catalog previews.
  Basic uses structural recognition. Advanced checks every report page independently;
  Names requires complete first-page checks and reads marked starts only. All starts,
  even unnamed, terminate previous ranges. Never fill report gaps or infer starts/names
  from synthetic labels. Unresolved names stay empty; only accepted names yield TOC/
  standalone report boundaries. Preserve named one-page/missing-date/repeated reports.
  Historical unchecked output keeps its old grouping when read, not when regenerated.
- Naming5 fixed/source_title is per card and kind; absent mode means fixed. Dynamic
  matches require rule_id, propagated as naming_rule_id. Empty source title with a valid
  rule uses its name; unknown eligibility does not. Best-fit descriptions, no precedence,
  weights or mandatory footer/code evidence. Preserve actual visible titles downstream,
  all-fixed/form prompt bytes, historical adapters and unknown custom naming prose.
- Agent correction follows Names using shared Pi, not classifier workers. Read bounded
  sources; write private patches only. Apply proposals independently with valid before
  values/taxonomy/name/date mappings. Image evidence/adjacency/coverage/formatting are
  advisory, not gates. Structural counterfactual checks suppress no-effect edits but
  retain cooperating gap repairs/unnamed starts and consequential type changes.
  Publish separate corrected finals and review provenance, preserving Names inputs.
  Mark review required before work; crash marker blocks continuation pending deliberate
  recovery, no silent fallback. Retain useful safe candidates after abnormal exit, not
  full sessions. Review unresolved first, plain text only, read-only counts/no apply.
  See `docs/classification-agent-correction.md` and `docs/classification-review.md`.
- Motion flow: immutable physical inventory → restricted candidate → independent Python
  normalization → locked guarded atomic grouping → existing consumers. Lead ID/anchor,
  exact member spans (even preceding/nonadjacent support), separate motion/opposition/
  reply; ambiguous support stays singleton. Preserve known filed dates. Optional model
  metadata is advisory, not a coverage/quality gate. Stale grouping warns/singletons;
  corrupt stores and Stop/source/model/race/publication failures preserve prior output.
  Resume skips historical missing preparation honestly; explicit work hashes resources.
  Source-map physical documents/counts remain physical; groups/aliases are reader context.
  See `docs/motions-workflow.md`, `docs/application-motion-naming.md`.
- TOC correction retains first known minute date, never collapses unknown dates. Actual
  ranges/inputs still govern explicit work; narrowly reviewed compatibility may reuse
  unchanged participant work after boundary rebuilding, never metadata repair.
- Transcript numbering normalizes citations to PREFIX N / PREFIX:N, never p./pp.
  Breakdown Markdown is a footnote aid: fixed quick chart, one suggested footnote per
  citation series in first-appearance order and material review notes. Prefer reliable
  printed volumes, otherwise supported hearing dates/identifiers. Physical volumes alone
  never split series. Preserve schema2 confidence/collision/range/anomaly JSON.

## Summaries and native knowledge work

- Usefulness, not perfection: imperfect model content/coverage/quotes and missing or
  malformed successful-child output are advisory. Retain usable work, use saved digest
  fallback, flag unusable extraction honestly and continue other documents. No mandatory
  paid repair pass, all-or-nothing quality gate, quota, prose filter or regex renaming.
  Stop, execution/source failure, changed inputs, corrupt stores, unsafe paths, rendering
  integrity and publication failures remain separate safeguards preserving prior finals.
  See `docs/summary-best-effort.md`.
- Fixed hearings cover Appearances (express absence/personal vs representative attendance,
  never absence from silence) plus the other five established topics. Current rows4 /
  Markdown3 / meta6 have application authority; historical rows2/3 / Markdown1/2 retain
  recorded headings/catalogs. Explicit generation re-extracts incompatible rows.
  See `docs/application-hearing-topics.md`.
- Hearing quotation integration and fictional examples must remain: let quotes carry
  propositions, not repeat a complete paraphrase; mentally expand placeholders, preserve
  grammar/speaker/duty bearer, attribute complete spoken statements, omit unhelpful
  confirmations without seeking fewer quotes. Purpose/result first, short focused
  paragraphs, arguments once, consequential qualifications and unresolved conflicts.
  No extra review pass. Preserve exact active hearing skill/runtime bytes unless a prompt
  change is requested. See `docs/hearing-editorial.md` and `docs/report-editorial.md`.
- Extraction serves each complete document once, no windows/proposal cutoff. Advisory
  quotes are continuous source-exact 6–12 words, usually 8–10, shortest useful anchors;
  no padding/stitching/truncation/quote quotas. Preserve provenance/negation/attribution;
  useful outliers and unverified matches remain with sanitized warnings. Reports include
  all later/proposed sections but distinguish requests/recommendations from orders.
  See `docs/summary-quotation-policy.md`, `docs/summary-contract-reconciliation.md`.
- Python owns IDs/category order, digest Markdown/meta and final text publication under
  per-kind locks. Normalize categories nonfatally; all-null documents keep headings.
  Reject duplicate IDs/overlapping ranges before paid work. Digest codec must round-trip
  all supported kinds, category IDs (including hyphens/digits), quote IDs and escaped text;
  generated-store corruption is not defective model work. Markdown is authoritative.
  Historical v2 JSONL conversion is guarded/lossless/zero-call on explicit stage work;
  delete retired stores only after complete validated publication, never on disagreement.
- Synthesis consumes reloaded canonical digests through dataset-only tools, incrementally
  submits sections with private process-local scratchpad and submitted-section rereads
  after compaction. Notes are not evidence and never published/logged; restart resumability
  is deferred. Keep chronology; unknown quote IDs use digest fallback, not silent deletion.
  Deterministic rendering preserves plain text/quote anchors, no generated page-link markup.
- Quote display permits exact used-ID case-only proposals for all-caps source quotes,
  preserving evidence/offsets. Reject invalid/wording-changing proposals nonfatally; no
  automatic lower/title fallback. No capitalization announcements. Preserve renderer8,
  synthesis-only wrapper isolation, paragraph breaks and current contiguous ordinals;
  dataset order/identity changes require synthesis, even with reusable extraction.
- New minutes use canonical neutral SKILL and unconditional complete-order
  recordprep-profile-minute-tools.ts, contract9/envelope5, compact-labels-2. No profile,
  config, participant index, role catalog or historical parental first-page policy.
  Date — Hearing type, adjacent unbulleted Appearances / Orders / Next, blank line
  between entries. Normally 1–2 plain-English headline outcomes, necessary conditions,
  no hard cap. No routine filing/calendar recitals; administrative-only orders say
  'No substantive orders recorded.' Next is substantive hearing/date, not report due
  dates. Attendance can use any order page; counsel/missing names/custody alone prove
  neither attendance nor absence. Evidence-location checks do not prove semantics.
  Preserve old checkpoints/positions/compact-list/paragraph readers exactly, not relabeled
  as contract9. See `docs/application-minutes.md`, `docs/minute-plain.md`,
  `docs/minute-compact.md`; earlier selection reports are historical evidence.
- Participants are hearing-scoped: counsel, non-counsel, witnesses, source-described roles,
  representation, express attendance and sworn/examination evidence. Q/A alone is not
  testimony; firms are organizations, not aliases. Work one hearing at a time, single
  pages, batches ≤5 for partial validation, no concatenated RT. Normalize NEW schema4
  candidates only, omit unsupported entries with warnings; keep historical readers.
  Reject unreviewed templates, unsafe paths and invalid examination ranges. Native helper
  owns progress, two-failure exhaustion and full-success termination (even in partial
  requests); stage SKILL file is readable, not arbitrary helpers/directories. Test real SDK.
- Only fresh resolved `transcript_layout.is_ct_only` authorizes participant skip, before
  Pi/workspace launch. Ignore pre-existing participant artifacts and waive downstream
  attribution inputs; empty hearing boundaries yield zero-call hearing output. Nonempty
  hearing boundaries fail honestly. Missing/stale/review layouts grant no exemption.
  Source maps use empty in-memory hearings and omit participant paths for CT-only.
- Overview reads all saved summaries completely, plus applicable identity-only participant
  context; five unchanged sections/disclaimer, selective short bullets, latest bounded
  posture, major chronology, neutral issues/scope gaps, no assumed appeal, quotas or
  copied evidence inventory. Profile-bound native reads exactly the APPLICATION INPUT
  MANIFEST (summaries/layout/skill/participants if applicable), no discovery, manifest or
  case_name.txt. Publish private candidate only. Source map is deterministic Python;
  original text, not editions/summaries, is research evidence.
- Editions are page-matched Letter PDFs + maps, fixed recordprep-summary-letter-v3 /
  schema2 (Times-compatible Nimbus Roman, no local font dependency). Preserve all text,
  trusted link/quote spans and source/PDF hashes via monotonic alignment. Recognized
  double quotes become bold only in print; canonical TXT stays byte-identical. Validate
  all candidates before replacing, PDF then map atomically. Minute source-blank-lines-v1
  spacing and bold-field-prefixes-v1 are separate policies, never quote links. No model
  regeneration for edition-only changes. See `recordprep/summary_editions.py` tests.

## Pi delivery, freshness and output presence

- Tracked `.pi/` owns resources; native VTE launches one explicit skill via
  `.pi/scripts/run_recordprep_skill.py`. Preserve native interactive UI. Summary children
  use JSON/no-session/approve, exact custom-tool allowlists and unique private workspaces
  cleaned in finally. Stage only system/skill/required guards; synthesis explicitly loads
  its separate wrapper, minutes their own extension. Models never publish canonical files.
- `/skill:name request` uses a literal space, never newline. Runtime/inspector/preflight
  use identical staged guidance/skills and hash-checked registered schemas. Preserve
  `slash-skill-space-v1` fingerprints and actual offline SDK launch-boundary tests.
  Missing/stale packaged audit reports incomplete inspection; regenerate only for audited
  source changes. See `docs/summary-skill-delivery.md`, `docs/native-skill-delivery.md`.
- Native participant/overview fingerprints hash reachable stage-specialized definitions,
  shared safety/model/source and declaration/resources, not entire multi-stage runners.
  Keep native_runtime_compat.json historical; never bless broken pre-expansion identities.
- Resolve executable safely before version/spawn: only rediscover `pi`/known legacy default;
  fail with alternative for missing custom path. Pi summary minimum 0.85/native 0.80,
  Node20+, GTK4/VTE required. Never hard-code installer paths.
- Stop terminates active child process group (SIGKILL only after failed SIGTERM), releases
  locks and blocks publication/next stages. Nonblocking summary polling and native
  session-growth/CPU monitoring show stalls without automatically killing the child.
  Logs contain stage/count/event/PID/timing/usage and sanitized codes, never prompts,
  source text, provider bodies, arguments/results, model prose or scratchpad. Effective
  provider settings stay distinct from configured preferences; no full-session retention.
- Capacity preflight fails known-oversized individual requests before paid calls;
  aggregate synthesis history warns/proceeds, unknown capacity stays unknown. Diagnostic
  `python -m recordprep.summary_preflight` is read-only/no calls/no publication lock.
- Explicit generation uses actual stage-local inputs/components/model/checkpoints and
  guarded serialized publication. Downstream stages consume saved upstream files, not
  old generation settings; no upstream freshness gate on summaries/overview/source map.
  Never delete output or fabricate metadata to force or avoid work.
- Badges and Resume are output-presence only (`output_presence.step_outputs_present`,
  `_resume_step_complete`). No profile/content reads or private writes in badge inspection;
  changed models/resources/schemas/timestamps do not make existing output Pending. Missing
  output is Pending. Text processing specifically requires text plus atomically published
  `artifacts/text_processing.complete`, invalidated before mutation/refill/layout rebind;
  legacy bundles without receipt are pending, never auto-migrated.
- Numbering, participants and summary stages never modify manifest.json. Final source-map
  publication owns manifest paths, including transcript_layout. Preserve immutable bundle
  root logs and warnings for apparent parent-case-number conflicts; never move private data.
- Sole resource-confinement exception: passive `PiRunMetrics/run-collector.ts` via
  `recordprep/run_metrics.py`. No tools/prompts/publication authority; fail-open policy,
  Pi≥0.87.1, no upgrades. Step/skill tags only, never case/item names; zero-model/skips
  produce no runs. Keep archive/collector overrides and content-free telemetry.

## Validation commands

Use the absolute project-env helper with disposable source/environment overrides:

```text
.../UvEnvironments/project-env --project /tmp/.../RecordPrep --environment /tmp/.../env run RecordPrep python -m unittest discover -s tests -v
.../UvEnvironments/project-env --project /tmp/.../RecordPrep --environment /tmp/.../env run RecordPrep python -m compileall -q recordprep tests
.../UvEnvironments/project-env --project /tmp/.../RecordPrep --environment /tmp/.../env run RecordPrep python .pi/scripts/run_recordprep_skill.py --validate-resources
```

Run affected unit/pipeline/native-guard tests, full discovery and resource/audit checks;
validate changed skills with the Agent Skill validator. Keep package data complete,
including historical resources and standalone `.pi/`. Use synthetic isolated GTK
acceptance for UI parity, preserve the running user's state and report desktop limits.
Dated validation reports remain historical; do not rewrite them to imply HEAD acceptance.
