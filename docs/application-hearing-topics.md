# Application-owned hearing topics

Hearing digest topics are now a fixed, practice-neutral application method. This
extends the application-owned motion and minute methods; it does **not** move
report topics or report/form naming out of profiles.

## Topics and ownership

- **Appearances:** parties' personal, remote, counsel or representative appearances,
  with expressly recorded absences. Counsel alone does not prove a party's personal
  presence. Entity representation is described as such. Silence is not proof of
  absence; no information means a null category.
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

Restart RecordPrep to load this source change. No profile reset/save is required
to use the new hearing method. Existing output changes only after an explicit
**Create hearing summaries** run, including extraction, followed by optional summary
edition/overview/source-map refresh. Do not rerun upstream classification or boundary
work solely for this instruction change. Badges and Resume stay output-presence based.

## Local validation

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
