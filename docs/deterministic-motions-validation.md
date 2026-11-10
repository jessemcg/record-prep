# Deterministic motion packets: validation

## Scope (2026-11-10, work computer only)

This validates Python-owned grouping schema 2 / `recordprep-motion-organization-2`.
It supersedes the current implementation described in older model-organization
reports, not their dated evidence. Schema-1 artifacts retain their existing meaning
and are not migrated when read.

A named motion start opens a packet containing every numerically adjacent
`CT_motion` / `CT_motion_first_page` page until a gap or non-motion page. Subsequent
named requests, opposition/reply, party/title/date differences and unnamed internal
starts do not split it. Physical papers retain their own IDs, ranges and metadata.
The earliest paper owns the logical ID, anchor, title and date, including unknown
dates. Classification continuity is not a finding that papers support each other or
present one legal request. Leading unnamed/body fragments remain omitted findings.
“Selected-inventory accounting” is not a representation of legal review coverage.

## Isolation and commands

Tracked source plus the intended new implementation/test files were copied into
`/tmp/motion-continuity-validation/{RecordPrep,Focus}` with disposable Git metadata.
Separate machine-local `recordprep-env` / `focus-env` environments used managed
Python 3.13.12 and the absolute UvEnvironments `project-env` helper with paired
`--project` / `--environment` overrides. HOME, XDG state and Pi state were isolated;
metrics were disabled. No production environment was synchronized. Focus's
pre-existing untracked `.pi/` was excluded.

The local `/tmp/motion-continuity-work/run` wrapper selects the disposable project,
environment and state. The principal commands were:

```sh
/tmp/motion-continuity-work/run RecordPrep python -m unittest discover -s tests -v
/tmp/motion-continuity-work/run Focus pytest -q
/tmp/motion-continuity-work/run RecordPrep python .pi/scripts/run_recordprep_skill.py --validate-resources
/tmp/motion-continuity-work/run RecordPrep python -c "import subprocess; subprocess.run(['node','scripts/collect-prompt-tools.mjs','--check'],check=True)"
```

## Automated results

- RecordPrep: **1,022 tests; 1,014 passed, 8 skipped**.
- Focus: **942 passed, 16 skipped, 11 subtests passed**; eight existing
  Adwaita deprecation warnings from settings-session tests.
- Resource validation, installed offline SDK registered-tool audit (Pi 1.5.2),
  changed skill metadata validation, Python compilation, shared-file byte parity
  and both repositories' `git diff --check`: passed.
- Both READMEs, both `profile_contract.py` files, dependency declarations and
  lockfiles remained unchanged. The dated prior motion-validation report was
  preserved verbatim and explicitly labeled historical.

Synthetic regression checks cover:

- Multiple independent/opposing titled starts in one continuous packet, unnamed
  internal starts, gaps, non-motion breaks, leading omitted fragments, zero motion
  preparation, malformed identities and duplicate/conflicting page rows.
- Earliest lead ownership, unknown dates, neutral component roles and the exact
  continuity explanation; rejection of unsupported schema/contract pairs,
  split/nonmaximal packets and invented lead metadata.
- Schema-1 nonadjacent and pre-lead membership without migration or on-read writes;
  distinct old “Review coverage” and new selected-inventory labels.
- Exact selected source/classification hashes; locks, root identity, unsafe output,
  changed inputs/policy/resources/prior output, Stop and late publication races.
  Failed replacement preserves the old artifact; abandoned unique temporary output
  is removed. An unchanged organization rerun preserves bytes and mtime.
  Model preferences and editorial guidance do not affect grouping identity.
- The common resolver across TOC, boundary rebuild/filtering, work items, digest
  reload, fixed summaries, editions and maps. Stale/missing grouping warns and uses
  named-only compatibility. Current schema 2 with missing/mismatched physical
  boundaries cannot silently publish summaries/maps.
- Exact unnamed-member source access, quote provenance, physical metadata,
  per-page group aliases and complete membership; physical versus logical counts.
  Focus rejects missing/incorrect aliases, source metadata, counts, duplicate pages
  and incomplete packet page coverage while retaining historical map acceptance.
- Digest/fixed-output rollback for malformed or failed summary completion;
  organization dispatch before Pi/resource preflight, with the retired skill,
  candidate tools, staging and resource/audit entries removed.

The RecordPrep skips are three owner-specific model-setting policies, three tests
requiring the optional sibling PiRunMetrics SDK fixture, and two optional metrics
integrations. Focus skips eleven optional sibling metrics/collection-SDK tests and
five other-owner model-setting policies. These skips are not reported as passes;
no missing dependency was provisioned into a production runtime.

## Native GTK and desktop observations

Separate synthetic applications ran with `G_DEBUG=fatal-criticals` and
`GSK_RENDERER=cairo`; the maintained user applications were not restarted.

- New RecordPrep acceptance passed with `Vte=None` and no Pi runner. It exercised
  the ordinary Python step lifecycle, Stop and selection-change preservation,
  unchanged-rerun mtime, two TOC entries, physical boundary rebuilding/filtering
  retaining the unnamed continuation, two summary work items and
  digest/edition/source-map publication. The read-only grouping inspector did not
  rewrite its artifact.
- The new synthetic packet spans pages 11–15, including an unnamed physical start
  at 14; a report at 16 breaks it; 17–18 are omitted fragments; a named motion at 21
  opens a separate packet. Results: **3 physical papers / 2 logical entries**.
- Historical RecordPrep acceptance passed with saved schema-1 nonadjacent/pre-lead
  groups, two summary pages and both fixed motion inspectors without inspection
  writes.
- New Focus acceptance passed expanded sidebar entries, both summary headings,
  lead and continuation quotation links, physical unnamed context, both counts
  and no bundle writes. Historical Focus acceptance passed its separate schema-1
  synthetic bundle, wide/narrow layouts and light/dark checks. A repeated historical
  run initially exposed the old acceptance script's fixture contamination (it
  populates other synthetic summary modes). The harness now copies the producer
  bundle, asserts the producer remains unchanged, and passed twice against a fresh
  fixture. This required no Focus product-behavior change.
- Linux Computer Use observed the synthetic read-only grouping inspector showing
  complete selected-inventory accounting, two entries / three papers, the unnamed
  component and omitted-fragment findings; it also observed Focus's motion summary
  and source page 15 after quotation navigation, plus the historical Focus reader
  at supporting source page 8 with the quotation search hit. These observations
  supplement, rather than substitute for, automated provenance and read-only
  assertions.

Local logs and synthetic bundles are temporary evidence, not portable fixtures:
`/tmp/motion-continuity-validation/` contains `full-rp-final.log`,
`full-focus-final.log`, `gui-rp-final.log`, `gui-rp-old.log`,
`gui-focus-final.log` and `gui-focus-old.log`.

## Limits and deliberate adoption

No paid calls or live-model editorial acceptance were performed. Summary-pipeline
acceptance used deterministic synthetic candidate content; prompt checks and
installed offline SDK/tool-delivery audits do not prove the quality of future
Request/Reasons prose on real case materials. Focus changes are limited to shared
artifact validation, tests and motion documentation, not its research method.

No reported real bundle was regenerated, and no private settings/profile, source
text/PDF or real case manifest was changed. No user-application restart, launcher
change, deployment, commit or push was performed.

Adopting schema 2 for an existing bundle is a separate, deliberate regeneration:
run organization, rebuild TOC and physical boundaries, filter boundaries, regenerate
motion summaries and then rebuild the source map. Do not treat merely opening an
old bundle, or accepting these source changes, as that regeneration. Historical
saved artifacts remain readable as-is; missing/stale grouping uses warning-backed
compatibility rather than silently upgrading it.
