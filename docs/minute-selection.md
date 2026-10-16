# Brief minute-order summaries — 2026-10-16 (first attempt)

**Historical report:** this initial contract5 change passed protocol tests but did
not achieve the user's intended brevity on subsequent minute-summary review. It is
superseded by [compact minute entries, contract6](minute-compact.md): normally one
or two headline outcomes, Date — Hearing type plus three bullets, no separate
positions submission, short examples and aligned bundled specialty focus. Statements
below about unchanged public guidance/candidate fields describe this first attempt,
not the later implementation. Neither test suite establishes live writing quality.

## Purpose and scope

Keep the profile architecture: the application owns a shared, specialty-neutral
selection/safety method; profiles supply specialty terminology, relevant people
and emphasis. Do not replace it with dependency-specific parental/reporting rules.

The earlier visible `recordprep-summarize-minutes/SKILL.md` described the unassigned
compatibility path, while profile runs silently substituted `profile-minutes.md`
and broader runtime guidance. That combination asked for appearances, positions,
findings/orders and future settings, encouraging a field-by-field narrative despite
saying “concise.” This implementation addresses that instruction mismatch. It does
not assert that every excessive sentence in a particular private output was traced;
no real case was inspected or regenerated in this follow-up.

## One shared selection method

`.pi/skills/recordprep-summarize-minutes/SKILL.md` is now neutral and stages unchanged
in both paths. The alternate `.pi/resources/profile-minutes.md` is removed, along
with its staging override, preflight override and presence requirement. The skill
is visible at the same path used for instruction loading and fingerprinting.

The shared method says:

- Read the entire order, but select rather than reproduce its contents.
- Give a brief account of consequential actual rulings, not a miniature hearing
  narrative or inventory of findings, checked boxes, requests or procedural events.
- Group related rulings and keep each point once. Preserve conditions, deadlines,
  qualifications and unresolved issues when omission would change material effect.
- Omit routine recitals, standard/form findings, document inventories, notice/service
  mechanics and history unless consequential. Prefer plain paraphrase to long quotes.
- Keep profile-relevant appearances compact rather than listing every attorney or
  court employee. Keep the next setting compact, with purpose/other dates only when
  consequential.
- Include recorded positions only to explain the result or a material unresolved
  dispute. `positions` may be empty even when nonessential requests were recorded.
- Use a short fictional neutral before/after example to demonstrate selection, not
  a numerical target. No word/sentence/item quota, mechanical truncation, blocking
  quality validator, extra generation pass or repair loop is introduced.

`PROFILE_MINUTE_CORE` now treats schema fields as containers rather than a coverage
checklist and explicitly makes specialty focus subordinate to shared selection and
fidelity. The profile tool descriptions agree with that method instead of requesting
complete narratives in all fields. Bundled and private profile resource bytes are
not rewritten. Existing custom focus still composes into the runtime prompt.

## Preserved behavior

- Profile attendance remains based on explicit evidence anywhere in the complete
  order, including expressly recorded remote attendance. Counsel alone and missing
  names establish neither personal presence nor absence. Uncertainty stays explicit.
- No participant-index lookup or role catalog is added. The current order remains
  the only evidence source; tool allowlists, source-before-submit, evidence location
  checks, Stop, locking, canonical publication and checkpointing are unchanged.
- Reporting status is still omitted for profiles. Unassigned compatibility keeps
  its existing runtime-specific first-page parental/reporting rules; these do not
  become application-wide rules.
- Candidate fields, schema-4 checkpoints, old readers, appearance rendering and
  next-hearing uncertainty conventions are unchanged. No new output schema or
  automatic cleanup/migration. Historical paragraphs render as stored, not shortened
  on read. A renderer test deliberately retains long submitted text in full.

## Freshness and existing work

Profile minute content contract **4 → 5**; checkpoint schema remains **4**. Profile
fingerprints now include the canonical skill instead of the removed alternate,
plus the changed core/tool guidance. Unassigned fingerprints change with the same
canonical skill. This honestly marks former minute generation pending, without
writing/deleting existing output or private metadata.

Removing the obsolete resource-presence requirement also changes the native runner's
projected runtime hash. Reviewed AST comparison against the pre-change runner proved
that for **both participants and overview**, the entire projected runner differs
only by removal of `Constant(value='profile-minutes.md')` from that resource list.
No native generation instructions, tools, validation or inputs changed.
`native_runtime_compat.json` narrowly updates the exact reviewed baselines and accepts
the preceding hashes read-only. Existing source/component/model/input checks remain;
this is not a blanket exemption or a private-artifact rewrite. New exact baselines:

- Participants: `fadf15e91ba9bedb7f66fc064a541fbc144c538af5170176e482755b03fa6379`
- Overview: `2ae778b48b76c46fa6db0e7201c0d5d26d974b1d7915d03a674e6cc20fdae851`

Unchanged participants and hearing/report digests/finals are not made stale by this
minute-writing change. An overview/source map must still reflect regenerated minute
summaries through their normal prerequisite/input checks. Earlier hearing/report
changes have their separate freshness effects; see hearing-selection-validation.md.

## Isolated verification

Work-only; disposable source/environment under `/tmp/recordprep-selection-ITRpgg`,
using the absolute UvEnvironments helper with explicit project/environment overrides,
temporary HOME/XDG/agent state and `PI_RUN_METRICS_ENABLED=0`. No maintained environment
sync, new production dependency, private configuration, accepted profile, case bundle,
Focus, launcher/entry-point change, other repository or other computer was involved.

- Full suite: **632 tests run, 630 passed, 2 optional passive-metrics checks skipped**,
  20.892 seconds. Installed SDK offline tests enabled; no credentials/model calls.
- **121 Python files** compiled; Pi resource validation and changed-skill validator PASS.
- Actual minute runner, real workspace staging, model/tool flags and publication tested
  for **General and California Dependency**, with offline candidate-producing children.
  Staged skill bytes exactly match the visible canonical file; each profile's actual
  guidance is still in the runtime prompt. Restricted tools and workspace cleanup pass.
- Real TypeScript minute tools exercised under Node with a synthetic host: source read
  required, narrow capability list, unchanged candidate fields, submission termination
  and new selective description pass. Existing fixed attendance and historical reader
  tests pass, as do native compatibility gates and isolation tests.
- Synthetic previous-method output remains byte/mtime unchanged under stale checks and
  a failed explicit run. Successful explicit regeneration updates it; a subsequent
  current run needs zero child generation calls. Empty positions remain valid and
  necessary qualifications survive rendering without deterministic truncation.

These are implementation/protocol checks with offline responses, **not a live-model
writing-quality comparison or a guarantee that a chosen model will be sufficiently
brief**. This follow-up makes no paid calls and does not extend the earlier bounded
hearing/report experiment. Source instruction consistency is verified; actual writing
still needs human review against the order when explicitly generated.

## Applying later (not performed)

Restart RecordPrep to load the changed code, then explicitly run **Create minute-order
summaries** when ready. Existing source/classification/boundaries/participant work does
not need regeneration solely for this change. Former minute rows require paid
per-order regeneration under the new method; subsequent unchanged runs reuse them.
Do not delete old checkpoints or edit their metadata to force this.

After successful generation, rebuild affected summary editions deterministically,
regenerate the affected overview (paid), and rebuild the source map deterministically.
Prior readable output remains until normal publication succeeds. No automatic real-case
refresh, commit or push was performed.
