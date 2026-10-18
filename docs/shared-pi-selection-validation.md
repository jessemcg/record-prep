# Shared PI selection validation

Implemented and validated on Home, 2026-10-18. No paid generation was performed.

## Behavior

- Model settings has direct OCR / Classify / Agent destinations and initially
  opens OCR. Agent retains the authorized-model picker, provider-qualified full
  model identity, reasoning/global-default behavior, command and refresh.
- Hearing/report extraction and synthesis, minutes, and native PI operations use
  the same effective PI preferences. Summary phase dictionaries retain empty
  provider/model/thinking fields for existing consumers. Generic identity and
  command helpers remain available; production supplies no retired overrides.
- Shared and hearing/report-specific legacy summary overrides are immediately
  inert, without Save. Settings preserves existing values and custom prose;
  ordinary/new saves never create retired model/reasoning keys.
- No changes to classification/OCR configuration, pipeline summary entries,
  profile summary guidance, prompts, tools, resources, schemas, output-presence
  badges, Resume, locking, Stop, or publication guards.
- Explicit runs still fingerprint effective identity/source/guidance. Ignoring
  a former conflicting override correctly changes identity; matching effective
  identity does not add artificial invalidation. Existing legacy explicit
  hearing/report runs still reuse extraction but execute synthesis; this change
  does not add synthesis checkpointing.

## Isolation and results

Disposable tracked-source snapshot: `/tmp/recordprep-shared-pi-rFbVKo/source`.
Provisioned its separate `/tmp/recordprep-shared-pi-rFbVKo/env` with the maintained
`UvEnvironments/project-env --project ... --environment ... sync RecordPrep` helper.
Execution used the same paired overrides and a wrapper selecting disposable
HOME/XDG config/data/cache/runtime and PI agent settings, metrics disabled,
synthetic preferences and fake providers. No private config, credentials, case
bundle or write-through link was copied. The local display socket was addressed
by absolute path so app runtime storage could remain disposable.

- Full unittest suite: **677 run, 675 passed, 2 optional skips**
  (`tests-final-native.log`). The baseline no-optional-SDK run was also green:
  677 run, 672 passed, 5 optional skips.
- Offline installed-SDK native acceptance: both participant and overview tests
  passed (also included in final full suite). Only the reviewed network-forbidden
  `PiRunMetrics/tests/app_sdk_fixture.mjs` was copied into the disposable parent;
  no sibling production environment or configuration was used or modified.
- `compileall` of application, tests and `.pi/scripts`: passed.
- Runner `--validate-resources`: passed.
- OCR GTK acceptance: passed, including direct navigation, extraction source,
  local OCR Save/reopen, and classification-page navigation.
- Shared PI GTK acceptance: passed, including long-label factory, exactly one
  picker pair, refresh, Save/reopen, Cancel byte preservation, preserved retired
  values/custom prose/unrelated preferences, new config without retired keys,
  discovery failure and unavailable-current-model behavior.
- Linux Computer Use doctor reported no blockers. Scoped AT-SPI/screenshot
  observation of experiment PID 386348 verified the three destinations, shared
  explanation and picker pair, distinguishable model choices in the popup and
  native refresh. Closed only that experiment window. The maintained app and its
  open Model settings dialog were not interacted with or restarted.
- `git diff --check`: passed.

New/updated offline coverage verifies conflicting retired shared/per-kind values,
external and legacy preference paths, unchanged effective identity/config hashes,
retired-only edits/removal with no fingerprint change, shared model/reasoning
changes, byte-preserved guidance, preflight capacity identity, staged preferences
and child command flags for hearing/report extraction/synthesis and minutes.
Actual fake-executable summary runs confirm extraction reuse and unchanged digest
and summary bytes after retired-key changes. Frozen historical fixtures remain
unchanged; the external-settings test normalizes only explicitly asserted identity
differences when checking the historical content/resource hashes.

No artifact migration, private settings write, dependency declaration change,
launcher change, Focus-shared module edit, other-repository edit or other-computer
access was needed. Offline checks establish propagation and safety behavior, not
provider output quality. Restart the maintained app when convenient to load the
new UI; historical outputs remain untouched.
