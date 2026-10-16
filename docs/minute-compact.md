# Compact minute entries — 2026-10-16

Historical contract6/7 implementation and validation. The later
[plain-English / unbulleted-label follow-up](minute-plain.md) is current contract8;
its Orders label, bold Focus presentation and administrative exclusions supersede
the Main rulings/bullet presentation and routine-report example below.

## Approval and reason for the second change

The first [minute selection change](minute-selection.md) did not achieve the intended
brevity on the user's subsequent summary review. Passing checkpoint, tool and staging
tests did not establish prose quality. The user approved a narrower selection method,
short examples and aligned specialty focus, then specifically chose **hearing type
beside the date**, not a separate Hearing bullet. The user then narrowed Next to only
the next substantive hearing date, with no future reports (contract7 follow-up below).
Only summary-level editorial review
was performed; no factual audit against original orders or private pinned-profile
inspection was performed. Private facts/examples were not copied into resources/tests.

## Method and publication at contract6/7

The shared visible `recordprep-summarize-minutes/SKILL.md`, `PROFILE_MINUTE_CORE`,
profile submission tool and bundled General/California Dependency minute guidance agree:

- Read the complete order, but normally select **one or two headline outcomes**,
  not all material detail, every finding, service referral or implementation direction.
- Group related outcomes; add another only if omission would mislead about disposition.
  Preserve the qualifications necessary to state a selected outcome accurately.
- No separate party-position narrative. Include an objection only when essential to
  understand a selected ruling. Setting a motion for hearing is not granting relief.
- Submit a short hearing type, not the date, case caption, birth date or court location.
- Keep relevant appearances compact. Do not create an Unknown person or staff roster.
- Next gives only the next substantive hearing type/date. Exclude report-only hearings,
  report filing/due dates and other future report dates even when earlier. Do not move
  that report calendar into Main rulings. Omit later settings, times and notice mechanics.
- Fictional short routine/significant examples demonstrate selection and scale.
  No word limit, hard item cutoff, mechanical truncation, quality-blocking gate,
  additional model pass or tuning/repair loop.

Python, not the model, now publishes profile entries as:

```text
May 7, 2030 — Motion to compel
- Appearances: Applicant present; Respondent's appearance unclear.
- Main rulings: Disclosure ordered by May 21, subject to the protective order; unrestricted disclosure denied.
- Next: Review June 4.
```

This example is fictional. Appearance labels use a source-supported role when unique
within the submitted relevant people; repeated or unresolved roles retain individual
names instead of collapsing them. An entirely unidentified, unevidenced Unknown/unclear
placeholder is not a person to display; no established appearances prints **Not
established.** Named uncertainty remains explicit. The source/evidence data is retained.
No content-based shortening is performed by the renderer.

Core method and formatting stay specialty-neutral. Dependency focus supplies custody,
services, rights/plan, relevant parents and meaningful dependency settings as selection
priorities, not an exhaustive checklist. General does not acquire parental rules.

## Pinned guidance and compatibility

Changing public resource files alone does not update accepted personal revisions or
case pins. The existing read-only exact-built-in recognition now also recognizes both
preceding broad paragraph defaults and compact defaults that allowed future report dates.
Those **exact** old built-ins resolve
to the current public specialty focus at composition/preview time, without saving,
rebinding or migrating a private profile. The older exact predecessors remain recognized.
Custom/near-matching instructions remain byte-identical and compose subordinate to the
shared method. This does not claim any particular case's actual private text was audited.
Cached completion also watches the public default minute focus/manifest when exact-built-in
resolution uses them; changing that effective focus cannot leave a warmed status cache
claiming the old output is current. Watching uses file stats, not repeated source scans.

New tool submissions omit `positions`; a missing field is no longer a quality warning.
Schema-4 checkpoint rows still store compatibility `positions` (normally empty), so
historical row readers, integrity validation and publication schemas do not change.
If a candidate nonetheless supplies positions, its content is retained, including in
Main rulings rather than silently discarded. Historical paragraph rendering remains the
default for historical/direct callers; current profile stages explicitly select the
versioned compact renderer. Unassigned compatibility retains its legacy output and
first-page parental/reporting runtime; those rules are not universalized.

Attendance still requires explicit personal-attendance evidence anywhere in this
complete order. Counsel representation and missing names establish neither presence
nor absence. Python verifies locations, not semantic attribution. All evidence checks,
source-only tools, stop/locking/publication rules and uncertainty behavior are retained.
Separate same-day orders and checkpoints are not merged by this presentation change.

## Freshness and scope

Profile minute content contract **5 → 6 → 7** (7 narrows Next to the next substantive
hearing date only), with unchanged explicit presentation identity
`recordprep-minute-compact-list-1`. Changed core, skill, tool and effective specialty
guidance are fingerprinted. Checkpoint/final metadata remain schema **4**. Previous
minute generation is honestly pending; stale checks never reformat old files, forge
metadata, delete checkpoints or truncate retained content. A failed first candidate
preserves old output/checkpoint/metadata bytes and timestamps. Explicit successful
regeneration produces the new layout; unchanged subsequent runs reuse current rows.

Only minute guidance/publication changes in this follow-up. Hearing/report extraction
and synthesis, classification/naming, participants and native runtime methods remain
unchanged. Public profile content identity changes, but unrelated stage components do
not. The earlier hearing/editorial/organizing changes retain their independent effects.
No native compatibility-baseline relaxation is needed for this follow-up.

## Validation

Work-only, disposable source/environment under `/tmp/recordprep-selection-ITRpgg`,
absolute UvEnvironments helper with explicit project/environment overrides, temporary
HOME/XDG/agent state and metrics disabled. Tests use fictional candidates and no model
calls. Initial compact-layout evidence (contract6; hearing-date-only follow-up below):

- **644 tests run: 642 passed, 2 optional passive-metrics checks skipped**, 21.332 s.
- **125 working-tree Python paths** compile under the disposable managed interpreter;
  sequential Pi resource and changed-skill validators PASS; `git diff --check` PASS.
- New tests cover the header/three-bullet layout, unique versus repeated appearance
  roles, unresolved placeholders, retained long outcomes/compatibility positions,
  historical paragraph callers, all exact predecessor built-ins and untouched custom
  guidance, unrelated profile component isolation and cached public-focus dependencies.
- General and California Dependency synthetic old-contract prose stays byte/mtime
  unchanged under current stale checks and a failed first candidate. Explicit generation
  runs once per each of two separate same-date orders and publishes compact entries;
  the next unchanged run makes zero generation calls. Private pins/config remain intact.
- Existing actual runner/child workspace staging tests verify the canonical skill and
  current focus in both profiles. Real TypeScript minute tools verify no positions
  submission field, source-before-submit, current descriptions and session termination.
- Before/after fingerprints (`compact-before.json`, `compact-after.json`) prove only
  minutes changed for unassigned, General and Dependency; both hearing/report extraction
  and synthesis identities and native participant/overview runtime identities are equal.
- Synthetic TXT/PDF/page-map validation PASS with exact source coverage; a persisted
  one-page compact edition and PNG were visually reviewed under `compact-preview/`.
  Its source bytes remain unchanged by edition publication.

Artifacts/logs: `/tmp/recordprep-selection-ITRpgg/compact-final.log`, the fingerprint
JSON pair, `compact-baseline/` (public pre-change data only) and `compact-preview/`.
The exact preceding public resource bytes were separately checked against the recognition
map. Initial compact-layout external-settings minute aggregate was
`3e06907bc9fc04202a5077d98a94482fea21245371e8c7057d0d8ae380b37c47`;
extraction/synthesis aggregates and native compatibility baselines are unchanged.

These are implementation and rendering checks, **not live-model writing-quality
acceptance**. The deterministic layout is verified; actual model selection/accuracy
still needs human review when explicitly generated. No maintained-environment sync,
private configuration/profile/case rewrite, real-case generation, Focus interaction,
other-computer access, dependency/launcher/entry-point change, commit or push.

## Hearing-date-only follow-up — contract7 (now superseded by contract8)

The user no longer wants future reports in Next. Shared skill, core, submission
schema descriptions and both public specialty guides now request only the next
substantive hearing type/date. Report-only hearings and report filing/due dates are
excluded even if earlier; they are not relocated into Main rulings. Existing main
outcome selection and necessary qualifications remain unchanged. No text-filtering
regex, destructive shortening, extra generation pass or new validator was added.

The former exact compact public defaults (including their report-date guidance)
also resolve read-only to the new defaults. Their original public bytes were saved
and checked against the recognition map; private/custom instructions remain intact.
Content contract **6 → 7** honestly stales affected prior rows, while renderer identity
and schema4 stay unchanged. Stale checks preserve existing report-date prose; only
explicit generation replaces it.

Final isolated suite: **646 run, 644 passed, 2 optional checks skipped**, 21.643 s.
Two added tests verify the policy across shared/profile/tool guidance and simulate
contract6 output with earlier report dates: stale checks preserve bytes/mtime, explicit
fake generation publishes only the substantive hearing, then current runs need zero
calls. This is offline protocol evidence, not live-model selection acceptance.
All 125 Python paths compile; resource/skill/whitespace validators pass.

`next-hearing-before.json` / `next-hearing-after.json` prove only minute identities
changed across unassigned/General/Dependency; all hearing/report extraction+synthesis
and native runtime identities remain equal. New reviewed external-settings minute
aggregate: `b060de2685d9ef8ffdf77aa4386eb42ae31513f24d67939291157f74565ab1ef`.
Evidence: `/tmp/recordprep-selection-ITRpgg/next-hearing-final.log`, fingerprint pair
and `next-hearing-baseline/` (public guidance only). No paid calls, real-case/private
writes, maintained sync, restart/test interruption, commit or push.

## Applying later — not performed

Restart RecordPrep after the user's current hearing test is finished. Explicitly run
**Create minute-order summaries** when ready: this is paid per affected order, not a
free reformat of existing prose. No reclassification, renaming, participant, hearing
or report rerun is required solely for this change. Rebuild affected editions and the
source map deterministically; regenerate the affected overview through its normal paid
flow. Existing readable summaries remain until normal publication succeeds.
