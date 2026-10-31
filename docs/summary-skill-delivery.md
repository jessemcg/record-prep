# Summary skill delivery — 2026-10-30

## Fixed behavior

All five summary launches now put a literal space between `/skill:name` and the
request. Pi 1.4.0's command parser stops the skill name at the first space; a newline
instead makes it look for an unknown name such as `recordprep-extract-report\nRun`
and silently passes the command through without expansion.

Correct:

```text
/skill:recordprep-extract-report Run the loaded extraction skill now for the current document.
```

`recordprep/skill_commands.py::skill_launch()` (re-exported by
`recordprep/summary_prompts.py`) supplies that separator to hearing
and report extraction, hearing and report synthesis, and minute-order summarization.
All remaining request text, intentional returns/blank lines, staged skill files,
summary guidance, custom topic prose, tool schemas, validators and rendering remain
unchanged. This is nevertheless a model-visible behavior fix: the intended skill
body now reaches the model. It is not merely a presentation change.

The initial summary-only repair covered the five summary skills, in both profile
and unassigned compatibility work; it did not change native/caption launchers.
The separately authorized [native/caption follow-up](native-skill-delivery.md) now
repairs and SDK-verifies those paths too, centralizing the command helper without
changing the already-fixed summary requests or generation identities. Neither repair
changes the production case-name publication guard, Focus, launchers, preferences
or any case bundle.

## Inspection and audit

The inspector shows **Staged skill** and **Launch message (before Pi skill
expansion)**. The staged file includes its frontmatter; Pi strips that frontmatter,
wraps the complete body in its normal `<skill ...>` block with a staged-file location
and relative-reference directory, and appends the request arguments unchanged.
The inspector is not a provider-conversation replay; subsequent source/dataset tool
results, generated exchanges and provider internals are dynamic.

`scripts/collect-prompt-tools.mjs` verifies installed-SDK expansion for every summary
skill, as well as collecting actual registered tool schemas. The packaged audit
records the tested SDK version and successful skill list; its source hashes now
also cover all five canonical skills, the profile extraction/synthesis templates,
and SYSTEM.md. Missing/malformed/unverified or stale audits still visibly mark
inspection incomplete. Opening the inspector requires no Node, model discovery,
credentials, network or persistence.

## Checkpoints and saved output

`SKILL_DELIVERY_CONTRACT = "slash-skill-space-v1"` participates in extraction,
synthesis and minute-generation identities, including unassigned work. The
unassigned extraction runtime hash additionally covers its newly delivered
canonical skill, system prompt and tool extension; profile extraction retains its
corresponding template/system/tool hash. Existing synthesis/minute skill-resource
hashes remain in force. Guidance component goldens and artifact schemas are unchanged.

Consequences:

- Saved output/checkpoints remain readable; no private file is migrated or repaired.
- Output-presence badges and Resume behavior do not change.
- Explicit summary generation cannot reuse a pre-fix checkpoint as equivalent to
  the fixed delivery method. It may regenerate extraction as well as synthesis;
  normal provider costs apply to an actual rerun.
- A failed run preserves the previous final output. New matching checkpoints still
  resume without extra calls. Current-fingerprint legacy JSONL stores retain their
  existing lossless conversion path; old delivery fingerprints do not become current
  merely through format conversion.
- No case was rerun to implement or validate this change.

## Validation

All execution used the disposable RecordPrep source/environment and synthetic
HOME/XDG under `/tmp/recordprep-structured.SyH095`, on the current computer only.
No real legal materials, credentials or paid API calls were used.

- **Actual production launch captures:** all five stages × profile/unassigned modes
  = **10** successful installed-Pi SDK captures. The test intercepts the real child
  launch before process execution, then feeds its exact staged skill, system prompt,
  extension, tool allowlist and launch request to an in-memory SDK session with a
  synthetic provider. Network entry points are forbidden. Assertions compare the
  complete final skill body, SDK wrapper and unchanged argument suffix—not just a
  marker or a hand-constructed successful prompt. Interrupted staging is cleaned.
- **Inspector parity:** five further actual SDK captures of current-draft inspection
  components match complete expansion and the registered tool definitions.
- **Negative regression:** the old newline command is captured literally, reproducing
  the original defect offline.
- **Freshness/preservation:** every summary mode changes generation identity; active
  unassigned skill edits change extraction hashes. A saved pre-fix minute checkpoint
  stays byte/mtime unchanged during freshness inspection and a failed explicit rerun;
  a successful explicit rerun makes one new call and then resumes with zero calls.
- **Focused suite:** **119 passed**. Frozen historical public-install hashes remain
  unchanged; tests normalize only the reviewed delivery/runtime-hash additions and
  independently compare complete legacy-location/external-location configurations.
- **Full suite:** **810 run — 801 passed, 8 skipped, 1 unchanged baseline failure**:
  `test_case_name_stage.CaseNameStageTests.test_profile_switch_rejects_publication`
  (`ValueError not raised`). This is the historical summary-only result. The later
  [native/caption follow-up](native-skill-delivery.md) establishes that this test
  reselected the same default profile, corrects the fixture to perform a real switch,
  and adds same-profile reselection coverage. No production publication guard changed.
- **Resources/package:** sequential resource validation, registered-tool audit,
  compileall, shared-validator parity, source/test-copy parity and whitespace checks
  pass. Offline wheel/sdist builds include the delivery code and verified audit;
  all source hashes referenced by the packaged audit match the sdist's actual files.
- **Production GTK:** bounded settings/Save/Reset/inspector acceptance passes. A separate
  synthetic production editor verifies all five summary inspector views without the
  obsolete delivery warning or private persistence. Native AT-SPI confirms the modal
  read-only inspector and empty status; a targeted portal screenshot was visually
  inspected successfully. This does not complete the broader historical manual matrix.

Evidence: `skill-delivery-initial.log`, `skill-delivery-focused.log`,
`skill-delivery-full-final.log`, `skill-delivery-gui.log`, `skill-delivery-desktop.log`,
`skill-delivery-resources.log`, `skill-delivery-package.log`, `check_skill_delivery_gui.py` and `skill-delivery-before/` under that disposable root.
The first full run exposed expected historical-fixture assumptions about unchanged
summary identities and an ad-hoc current JSONL fixture without staged-resource hashes;
those tests now account explicitly for the authorized delivery change. Original
fixtures were not rewritten. Synthetic GUI PID365934 was stopped; the maintained
application was not restarted. Changes remain uncommitted.
