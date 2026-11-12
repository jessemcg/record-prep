# Application-owned hearing topics

Hearing digest topics are now a fixed, practice-neutral application method. This
extends the application-owned motion and minute methods; it does **not** move
report topics or report/form naming out of profiles.

## Topics and ownership

- **Appearances:** a concise account of actual parties' personal or remote attendance,
  appearance only through counsel/a representative, and expressly recorded absences.
  Party status (standing to participate) must be established by the source, not inferred
  from attendance, speaking, kinship or caregiving. Exclude relatives, caregivers,
  witnesses, social workers, court staff and other nonparties unless the source
  establishes that they are parties in their own right. Omit lawyers' and representatives'
  identities, law firms, counsel appointments/substitutions, introductions, greetings
  and attendance at earlier hearings. Counsel alone proves neither personal presence
  nor absence. For entity parties, describe only their recorded representation, without
  naming the representative or implying physical presence. Use source names/roles;
  do not guess unclear party status. Silence is not proof of absence; no party-appearance
  information means a null category.
- **Evidence Considered**
- **Testimony**
- **Disputed Legal Issues**
- **Party Positions and Reasons**
- **Court Orders and Reasons**

The last five topics retain their previous bundled guidance verbatim. The existing
source-fidelity, sworn-testimony, attribution, quotation and concise-narrative rules
remain in force. No extra model pass, quality gate, quota or repair loop was added.
The serialized `parent_appearances` identifier remains stable for quote/source
compatibility; its new display title and guidance are **Appearances**, not parents.

`hearing_guidance.py` owns the current catalog. Every assigned, unassigned, custom
and historical-profile run uses it. Historical hearing topics and legacy config
prompts remain at rest but cannot affect instructions, normalization categories,
initialization, previews or generation fingerprints. Report digest topics, Report
Names and Form Names retain their editors, catalog authority and Save/Reset behavior.
The shipped `reports.json` and report/form `naming.json` are unchanged.

Profile settings no longer has a Hearing digest topics page. The existing **View
full prompts** inspector retains Hearing digest and Hearing narrative, displaying
fixed instructions without template/draft controls or unrelated invalid-draft errors.
Canonical hearing skills are identical across assigned/unassigned staging, prompt
inspection and capacity estimates. The offline installed-Pi delivery audit is updated.

## Profiles, artifacts and adoption

Dependency 1.17.0/content schema 14 omits `hearings` as well as the previously retired
resources. Schemas 1–13 remain readable. Explicit Create/Save/Reset produces the new
format through the guarded store; opening settings does not rewrite accepted data.
The legacy initialization adapter imports report topics only.

New hearing digests use the existing application-owned envelope (row schema 4,
Markdown format 3, digest/final metadata 6), now with the strict, instruction-free
`recordprep-hearing-topics-1` descriptor. Historical row2/Markdown1 and
profile-row3/Markdown2 keep their original catalog headings and quote IDs when read.
They are never relabeled as current, even if an old row has a matching hash.
Explicit generation re-extracts historical hearing rows before new synthesis. The
runner does not pre-publish an empty conversion of old hearing JSONL; the old file
stays until successful generation and the existing deliberate cleanup flow.

The mirrored Focus contract/artifact readers accept schema14 and the new hearing
ownership descriptor. Focus summary availability recognizes valid empty hearing
metadata as empty, while retaining historical/fallback reading. These changes add
no research guidance or profile-management behavior. If publication is authorized,
publish the compatible Focus reader before RecordPrep.

The party-only Appearances clarification changes the hearing extraction and synthesis
instruction fingerprints, not the ownership descriptor, schemas, topic IDs/titles or
other five topics. Explicit hearing generation therefore re-extracts digests made with
the previous broader guidance. Historical saved prose remains untouched; report, motion,
minute and participant methods are unchanged. This is prompt guidance, not a deterministic
legal-standing classifier or a guarantee of model compliance.

Restart RecordPrep to load this source change. No profile reset/save is required
to use the new hearing method. Existing output changes only after an explicit
**Create hearing summaries** run, including extraction, followed by optional summary
edition/overview/source-map refresh. Do not rerun upstream classification or boundary
work solely for this instruction change. Badges and Resume stay output-presence based.

## Party-only clarification validation — 2026-11-12

Isolated current-computer checkout/environment:
`/tmp/recordprep-party-appearances-oYAVb7/RecordPrep` and sibling `env`.
The final full discovery ran **1078 tests: 1070 passed, 8 skipped**. Focused topic,
category and skill-delivery tests passed (22 tests); compileall, sequential PI
resource validation and source diff checks passed. Added regression coverage checks
party-only scope in extraction, synthesis and prompt inspection, unchanged catalog
identity/other five topics, changed hearing instruction fingerprints versus the exact
previous guidance, and unchanged report/motion extraction fingerprints. Historical
fixtures were not rewritten. Current aggregate prompt expectations also cover the
clarification alongside the separate record-wide quotation-verification work.

An initial full run segfaulted during a GTK profile-reset test. Subsequent runs used
`GSK_RENDERER=cairo`; no native crash cause was established. The first completed run
exposed outdated prompt hash expectations in the disposable snapshot and its missing
Git metadata. Refreshing the snapshot from the current source and initializing its
local test repository resolved those failures; the final run above passed. No
production GUI/runtime workaround was added. Logs are in the temporary root.

No paid generation, real-case processing, private-settings edits, app restart,
deployment, commit or push was performed. This validates instruction delivery and
freshness contracts, not model judgment about standing or generated writing quality.

## Original ownership-transition validation (historical)

Tests use synthetic profiles, temporary stores/cases and offline/fake providers.
Coverage includes all historical profile schemas, unchanged report/motion behavior,
application-rule invalidation, inert custom hearing prose, recorded historical
headings, actual codec roundtrips, current row ownership, fixed prompt inspection,
production skill delivery, zero-output publication, source-map provenance and explicit
adoption through the fake-PI pipeline.

Final RecordPrep unittest discovery: **1011 tests, 1000 passed, 11 skipped**
(including the locked-session viewport check). Focus reader/availability conformance:
**62 passed**. Sequential PI resource validation, offline installed-SDK prompt-tool
registration/delivery audit, shared-file byte parity and both repositories' diff checks
passed. Report topic and report/form naming resources remain byte-identical.

Evidence: `/tmp/recordprep-hearing-owned-validation/`. The current desktop became
locked during validation (confirmed by GNOME ScreenSaver.GetActive). GTK constructors
and accessibility remain available, but frame callbacks stop and screenshots/window
targeting are unavailable. The viewport-restoration test now explicitly skips only
when GNOME reports a locked session; its assertions are unchanged when unlocked.
No production navigation-code changes were retained. Computer Use's scoped accessibility
tree confirmed exactly Report Names, Form Names and Report digest topics in the synthetic
settings window. Screenshot-based visual validation remains pending an unlocked session.

No real cases, private preferences or accepted profiles were rewritten. No application
restart, paid provider work, deployment, commit or push was performed. Earlier uncommitted
motion ownership work and Focus's pre-existing untracked `.pi/` were preserved.
