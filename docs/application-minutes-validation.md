# Application-owned minutes: offline validation

Validated on the current **home** computer, 2026-11-06. This is an implementation
and offline-mechanics report, **not a live-model semantic-quality evaluation**.
See [method, schema and adoption](application-minutes.md).

## Scope and isolation

Changes are confined to RecordPrep and the explicitly approved Focus mirror:
`focus/profile_contract.py`, schema tests and maintainer documentation. Focus’s
pre-existing untracked `.pi/` was excluded from validation copies and left alone.
`profile_artifacts.py`, Focus research/UI/presentation, external launcher repositories
and deployed desktop files are unchanged.

Disposable copies and independent machine-local environments were used:

- `/tmp/recordprep-fixed-minutes.YDXB95/RecordPrep` and `rp-env`
- `/tmp/recordprep-fixed-minutes.YDXB95/Focus` and `focus-env`
- isolated HOME/XDG/Pi paths beneath that directory for RecordPrep tests and GTK
- `PI_RUN_METRICS_ENABLED=0`; no selected-provider/model preference changes

Both environments were explicitly provisioned through
`/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env`
with `--project` and `--environment`. No synchronized `.venv`, production environment
sync or launch-time dependency install was used. The disposable copies have local
Git metadata because an existing resource test invokes Git.

No private configuration, profile snapshot/store, case bundle, summary, edition,
source map or other saved user artifact was migrated, rewritten or deleted.
There was no maintained-application restart, server launch, real-case generation,
paid model call, automatic regeneration, commit, push or deployment. No other
computer was inspected or used.

## Tests and exact results

### RecordPrep

Final command, through the helper with the disposable RecordPrep paths and isolated
HOME/XDG/Pi environment:

```sh
project-env --project "$B/RecordPrep" --environment "$B/rp-env" \
  run RecordPrep python -m unittest discover -s tests -v
```

`rp-verified.log`: **920 tests run in 95.239s; 912 passed, 8 skipped; OK**.
The eight skips are:

- three shared maintenance cases owned by BillingHelper, Focus, or an unsupported
  inherited-model slot, rather than this owner;
- three optional installed offline-SDK fixtures (overview, participants and quotes);
- two optional sibling PiRunMetrics integrations.

`test_application_minutes.py` now has eight focused tests. Coverage includes:

- identical application guidance, launch, skill and component under old Dependency,
  current Dependency, a distinct synthetic practice profile, missing minute
  resources and unassigned work;
- literal canaries in historical minute resources, config and unrelated profile
  guidance cannot enter minute instructions;
- normal configuration saves preserve either the exact old minute value, including
  spacing, or its absence; no default key is silently inserted;
- complete-order remote attendance, multiple parties with the same role, explicit
  absence, unresolved/invalid evidence, compact text and empty retained positions;
- application minute identity in source-map preparation provenance;
- schema-10 Save/Create/Reset projection omits minutes, while source snapshots keep
  identical bytes and mtimes;
- invalid unrelated drafts do not block or change fixed minute inspection;
- a schema-1 row retains historical parental attendance and literal prose unchanged;
  schema-2/3/4 reader coverage remains in the historical tests;
- schema-4 rows cannot be reused even with a forged current-looking fingerprint;
  schema-5 rows can be reused across accepted profile/retired-prose/unrelated-topic
  changes; malformed envelopes fail closed;
- existing cancellation, source mutation, selection-publication, partial resume,
  concurrency and final-publication guards remain covered by the complete suite.

A separate final `test_summary_skill_delivery.py` run passed **6 tests in 5.469s**.
It checks actual SDK launch plans for profile and unassigned minutes: identical
system/skill/launch/tools/extension bytes, and the preserved complete-order extension
filename. Those tests also ran in the full suite.

The minute-only external-settings golden changed after adding the explicit tool
allowlist to the component. It was recomputed and reviewed; unrelated goldens were
not updated. Earlier runs caught and resolved fixture assumptions about editable
minutes/schema 9. Three earlier PTY Ctrl-C timeouts during parallel validation did
not recur in the final standalone complete run; they were not skipped or hidden.

### Focus

`focus-final.log`: **854 passed, 16 skipped, 11 subtests passed, 8 warnings in 12.99s**.
The skips are eleven optional SDK/PiRunMetrics integration cases and five shared
maintenance cases owned by other applications or unsupported Focus slots.
Warnings are GTK/Adw and Python PTY deprecations, not contract failures.

The existing Focus suite makes conflicting ambient permission assumptions: default
umask 022 produces seven settings safety failures; a uniform 077 instead masks the
intentional broad-directory rejection fixture. Validation therefore used an
**external, temporary pytest plugin**, `/tmp/focus_minute_validation_umask.py`, to
select 077 per test except the intentional 0755 rejection test, which uses 022,
and restore the prior umask afterward. No Focus production permission checks or
unrelated tests were weakened or edited.

```sh
project-env --project "$B/Focus" --environment "$B/focus-env" run Focus python -c \
 'import sys; sys.path.insert(0,"/tmp"); import pytest; raise SystemExit(pytest.main(["-q","-rs","-p","focus_minute_validation_umask"]))'
```

New Focus tests cover schemas 1–10, original manifest/resource byte preservation,
empty compiled minute resource lists for every version, schema-10 rejection of
minute reintroduction and rejection of unknown versions. The existing schema-9
unknown-version test now rejects 11, not newly supported 10.

## Instruction identity and conservative guards

A disposable `git archive HEAD` baseline was compared with the final implementation
using both releases’ own compilers. **All 20 unrelated instruction identities match**:

- all eight non-minute profile-stage components;
- all four fixed classification task components;
- report and form naming prompt hashes;
- hearing/report extraction and synthesis components;
- participant and overview native instruction components.

All non-minute resource bytes in Dependency 1.10.0 versus 1.11.0 also match; the exact
public 1.10.0 profile is preserved as a test fixture and known baseline.

Two **native runtime safety hashes**, distinct from those instruction components,
change because their existing conservative digest includes the entire shared
`profile_contract.py`. That file intentionally changes for schema 10. This was
investigated, not concealed by relaxing validation or adding compatibility hashes.
An explicitly requested native-stage run may therefore refresh that stage; completion
badges remain output-presence based, and no participant/overview rerun is required
merely to generate new minutes. No existing artifact was relabeled as newly produced.
Baseline/final evidence is in `components-before.json` and `components-after.json`.

## GTK and Computer Use

`acceptance_application_minutes_ui.py`, run with `G_DEBUG=fatal-criticals`, passed
with synthetic in-memory settings/profile state and model/save paths forbidden:

- no editable Minute orders destination; only hearing/report digest-topic pages;
- the existing **View full prompts…** selector still offers Minute-order summary;
- its minute view hides template/draft controls and ignores invalid unrelated draft
  resources; system, canonical skill/examples, fixed launch and runtime placeholders
  remain visible;
- hearing/report views retain their template/draft mode and current draft topic
  content; switching tasks does not reset topic buffers or save a draft.

Native Linux Computer Use observed the isolated process **77934** through scoped
AT-SPI and a targeted screenshot. The inspector task selector and fixed method,
examples and runtime sections were observed. Screenshot follow-up was limited when
the GNOME window-control extension bus became unavailable; this is not a claim of
unlimited screenshot coverage. AT-SPI remained available to close only the synthetic
inspector. `ui-hold.log` confirms clean synthetic-window shutdown without Save or
model work. The maintained application and its open user state were not manipulated.

## Build, resources and source integrity

The following passed offline in the disposable environments:

- Python compilation of RecordPrep, runner/tests, and Focus/tests;
- `run_recordprep_skill.py --validate-resources`;
- canonical minute skill validation with the installed skill validator;
- `node scripts/collect-prompt-tools.mjs`, with byte-identical regenerated audit and
  independent verification of every audited source hash;
- offline wheel and sdist builds, launched by the helper’s disposable Python;
- all **94** wheel application/resource payload files byte-identical to source;
  matching sdist application payload, canonical skill/system, active tools, runner
  and audit; schema-10/version-1.11.0 manifest, no active bundled `minutes.md`, and
  no private Pi settings seed;
- byte-identical RecordPrep/Focus vendored `profile_contract.py`;
- final source-copy parity and `git diff --check` in both repositories.

Logs remain locally under the temporary validation directory; they are not part of
an installation or a portable deployment procedure. No live-model outcome quality
is asserted: offline coverage establishes fixed instruction ownership, schema and
inspection behavior, launch parity, reuse boundaries and publication safety.
