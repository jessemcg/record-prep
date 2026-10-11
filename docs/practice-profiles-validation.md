# Practice profiles: validation checkpoints

## Reader-first compatibility checkpoint

Current Work computer only; disposable checkouts and managed environments under
`/tmp/profile-naming-ny9y30`, isolated HOME/XDG state, synthetic metadata, no model
calls or private configuration/case writes.

- Shared artifact tests validate bounded, instruction-free descriptors/provenance,
  frozen legacy roles, custom civil roles, safe evidence paths, attendance/witness
  rules, CT-only empty scope, and rejection of unsupported/future versions.
- RecordPrep tests round-trip new category digests, including zero-row documents,
  without reading current guidance. They reject mixed revisions/catalogs, retain
  legacy rendering, distinguish metadata-5 integrity from freshness, render generic
  minute appearances without parent language, and block legacy publishers from
  downgrading profile-era data.
- Focus tests exercise the actual helper script entry point with schema-3 metadata,
  report legacy-unassigned context without inferring a specialty, reject unsupported
  metadata, and distinguish selected, published, and consumed-map provenance.
  Sidecar reads reject extra fields, oversized files, and symlinks; opening alone
  creates no binding or registry. No instruction snapshot is loaded by these reads.
- Full Focus suite: **618 passed**, **38 subtests passed**. Existing two deprecation
  warnings remain. Bounded answer-switching GUI acceptance: **320 transitions,
  zero GTK criticals, expected final view and reading position, passed**.
- Full RecordPrep suite: **432 tests successful, 3 optional SDK skips** (429 pass).
  Existing unclosed-file ResourceWarning remains. Resource validation, compilation,
  common-code/test/document parity, and whitespace checks pass.
- Logs: `readers-focus-full.log`, `readers-rp-full.log`, `readers-resources.log`,
  `readers-answer-switching.log`. Optional SDK comparison was not rerun.

This is NOT end-to-end profile acceptance. Native producer/helper integration,
profile-aware classification and generation, freshness, session pinning, authoring
GUI, selection/export/counterpart flows, and controlled defaults remain incomplete.
The legacy pipeline cannot silently publish or downgrade new-profile artifacts.

## Naming integration checkpoint (historical)

Validated on the current Work computer using disposable tracked-source copies,
separate managed environments, synthetic cases, and isolated HOME/XDG state under
`/tmp/profile-naming-ny9y30`. No paid model calls, real cases, production environment
changes, or private configuration writes were used.

- Naming resource v2 validates strict title/code/output mappings, rejects unknown
  versions/fields, and retains accepted v1 snapshots without changing their refs.
  Shared profile conformance tests remain byte-identical between the applications.
- RecordPrep naming tests cover the 16 report names, six exact form rules, corrected
  Parental spelling, prominent-heading/date rules, source-title General behavior,
  exact response keys, output membership/date checks, and component/prompt hashes.
- Synthetic tests invoke the actual image-classifier adapter, TOC, boundary and
  correction methods, and existing source-map reader. Unnamed multi-page and
  one-page reports survive with review metadata; unknown first-page forms remain
  in the TOC. Repeated correction is stable. Missing-layout guards still block.
  Image evidence itself is not evaluated by these mocked classification tests.
- Full Focus suite: **604 passed**, **32 subtests passed**. Existing GTK and forkpty
  deprecation warnings remain.
- Full RecordPrep suite: **417 tests, successful, 3 optional SDK skips** (414 pass).
  An existing unclosed-file ResourceWarning was emitted. This checkpoint did not
  rerun the optional SDK comparison described in the foundation history below.
- Both RecordPrep bundled profiles pass the read-only CLI validator. The documented
  `.pi/scripts/run_recordprep_skill.py --validate-resources` command, Python
  compilation, common-code/test/document parity, and whitespace checks pass.
- A disposable Focus GUI opened the synthetic bundle and visibly rendered both
  `Untitled report — file page 1` and `Untitled report — file page 4` in its expanded
  Reports TOC, beside known report names. The fixture had no summary folder, so
  its missing-summaries warning was expected. No model session was started.
  Pointer navigation was not confirmed; this is display/read compatibility evidence,
  not a complete interactive-navigation or profile-GUI acceptance claim. The
  disposable window was closed; the user's normal application state was untouched.

Naming remains an opt-in code adapter, not an activated profile-selection flow.
The unknown-name retention fix applies to explicit legacy TOC/boundary runs too.

## Foundation checkpoint (historical)

This checkpoint covers the initial contract/storage/resources/diagnostic work,
not profile-aware generation, GUI authoring, artifact migration or model quality.
See [the contract and remaining integration work](practice-profiles.md).

All execution used disposable tracked-source copies and explicit machine-local
Python environments on the current Home computer, with synthetic data and private
temporary HOME/XDG roots. No private configuration, case bundle, model provider,
or remote computer was used for acceptance.

### Foundation results

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

The Dependency naming choice is settled and bundled from the explicitly authorized
prompt review. Arbitrary personal customization still needs explicit app-owned
export/review before activating profile-era naming for existing cases. Do not
silently change an existing case's prompts or reuse old classification checkpoints
under new profile guidance.

Reader/publisher integration, neutral pipeline behavior, application-owned prompt
composition, source/model/upstream freshness integration, profile selections,
new artifact provenance, GUI authoring/export/counterpart workflows, and all
end-to-end civil/dependency/third-specialty acceptance remain to be implemented.
Do not treat these foundation results as completion of the overall plan.
