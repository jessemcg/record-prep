# Practice-profile foundation: validation checkpoint

This checkpoint covers the initial contract/storage/resources/diagnostic work,
not profile-aware generation, GUI authoring, artifact migration or model quality.
See [the contract and remaining integration work](practice-profiles.md).

All execution used disposable tracked-source copies and explicit machine-local
Python environments on the current Home computer, with synthetic data and private
temporary HOME/XDG roots. No private configuration, case bundle, model provider,
or remote computer was used for acceptance.

## Results

- Shared new profile suite: **31 tests per application**, passing. Covers strict
  manifests, malformed JSON/Unicode, duplicate IDs, wrong applications, traversal,
  symlinks, hardlinks, executable files, FIFOs, size limits, frozen drafts, hash
  checks, private storage, stale/concurrent acceptance, interrupted publication,
  independent stores, identity descriptors, stage-scoped fingerprints, bundled
  resources, standalone package copies, and read-only CLI diagnostics.
- RecordPrep legacy baseline: **5 tests**, passing. Exact tracked category guidance
  and role IDs preserved, dependency policies present, General categories/policies
  distinct, current producer schemas unchanged.
- Focus full pytest suite: **603 passed**, with 24 passing subtests. Existing GTK
  deprecation/forkpty warnings remain.
- Focus bounded synthetic answer-switching GUI acceptance: **passed**.
- Focus wheel built in disposable storage; both bundled profile directories were
  loaded/validated from the unpacked wheel, without sibling-checkout access.
- RecordPrep normal unittest discovery: **399 tests, successful, 3 skipped**
  (396 passing; optional SDK discovery unavailable under that invocation).
- Explicitly selecting the installed local Pi SDK activates the optional offline
  tests: **398 passed, 1 failed**. The native-stage metrics passivity test
  `test_native_stage_actual_wrapper_does_not_treat_settlement_as_valid_layout`
  reports unequal normalized captures across collection variants. The same
  failure was reproduced in a separate disposable copy of unchanged RecordPrep
  `HEAD` using the same tracked PiRunMetrics harness. Its extraction/synthesis and
  minute-order SDK tests pass. This is an existing baseline issue, not claimed
  fixed or suppressed by the profile work.
- RecordPrep `--validate-resources`: **passed**. No Agent Skill changed.
- Python compilation, common-code/fixture/document parity, and Git whitespace
  checks: **passed**.

The first RecordPrep full run also lacked the sibling `sdk_acceptance` test
helper. Supplying a disposable copy of the tracked PiRunMetrics test infrastructure
resolved that import failure; no runtime dependency on a sibling profile repo was
introduced.

## Remaining acceptance gates

The bundled Dependency naming resource is provisional: tracked prompts refer to
approved title lists, but no catalog is tracked. No private lists were inferred or
read. Confirm the shipped naming choice and implement explicit customization
export/review before activating profile-era naming for existing cases.

Reader compatibility, neutral pipeline behavior, application-owned prompt
composition, source/model/upstream freshness integration, profile selections,
new artifact provenance, GUI authoring/export/counterpart workflows, and all
end-to-end civil/dependency/third-specialty acceptance remain to be implemented.
Do not treat these foundation results as completion of the overall plan.
