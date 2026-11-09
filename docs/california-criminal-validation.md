# California Criminal Law first-draft validation

Validated locally on **Home**, 2026-11-09. Implementation began from clean `507d93b`.
No deployment, commit, push, paid model evaluation or real-case generation was performed.
See [profile scope and explicit adoption](california-criminal-profile.md).

## Isolation

Tests/builds used a disposable tracked-source copy named `RecordPrep` under
`/tmp/recordprep-criminal-validation/`, a separately provisioned local environment,
and temporary HOME, XDG config/data/cache/state and Pi state. The normal desktop
session connection was retained for native GTK/Computer Use. Run metrics were disabled
with `PI_RUN_METRICS_ENABLED=0`. All records, images, stores and provider responses
were fictional/offline. The maintained environment was neither installed into nor
synchronized with test dependencies. Private settings and original PDFs were not
used as fixtures or migrated.

The absolute `UvEnvironments/project-env` helper selected the disposable source and
environment together for sync and execution. The first full attempt exposed harness
issues (checkout basename `source`, no temporary Git index, and an external config
override defeating tests' own project-local preferences). Those were corrected in
**the disposable harness**, not by changing application behavior or weakening tests.
Full discovery ran in the foreground with default SIGINT handling for PTY/Ctrl-C tests.

## Results

| Check | Result |
| --- | --- |
| New Criminal/containment tests | **9 passed** |
| Focused recognition, naming, report pipeline, store/reset, retirement, layout and motion suites | **131 run, 130 passed, 1 skipped** |
| Full unittest discovery | **1,017 run, 1,008 passed, 9 skipped; no failures/errors** |
| Python compilation (`recordprep`, `.pi/scripts`, `tests`) | Passed |
| Native sequential resource validator (`--validate-resources`) | Passed |
| Agent Skill validator, both changed skills | Passed |
| Wheel and sdist build | Passed; wheel built from sdist |
| Isolated installed-wheel profile acceptance and archive resource inventory | Passed for both bundled profiles, including personal customization |
| Native GTK bundled-profile acceptance | Passed for both identities |
| Existing Create profiles menu GTK acceptance | Passed with both creation bases |
| Dependency resources, recognition-v1/v2 and shared-contract immutability | Passed against HEAD; Focus shared-file parity also passed |
| Git whitespace check | Passed |

The focused skip was the existing reset viewport/frame-clock check while GNOME was
locked. No test assertion was removed to accommodate the lock. Full discovery also
retains its existing optional/environment-specific skips.

## What the fixtures prove

`tests/fixtures/criminal-documents-fictional.json` supplies **39** invented document
pages. Production Basic/Advanced/Dates/Names and TOC/boundary workers receive real
synthetic PNG attachments with **scripted** responses. This proves transport, routing,
normalization and downstream publication, not classification accuracy.

The fixture exercises sentencing and conditional preplea reports, disposition,
untitled and unfamiliar-title reports, short updates, adjacent same-title/date
memoranda and a one-page addendum. Independent victim/psychological/police material,
stationery alone and sentencing advocacy do not acquire probation names. The
independent victim attachment terminates the preceding addendum's range. Unnamed
report starts remain boundaries. The resulting eight named report ranges retain
all original source bytes and mtimes.

All twelve form families reach their naming contracts, with amended/count/proposed
source titles, unused and signed verdict sheets, a handwritten untitled jury note,
an instruction continuation and an integrated appeal/probable-cause packet. Motion,
minute, hearing-notice, service-proof, authentication and investigative exclusions
remain separate. Agent correction's captured guidance contains the same v3 CT and
first-form prompts; matched rule IDs survive its normalizer.

Fake extraction/synthesis through the actual summary runner publishes Criminal's
nine ordered categories, nulls and canonical quote IDs, then reuses unchanged work.
Scripted prose/quotes distinguish conditional recommendations, an unavailable interview,
proposed orders, disputed credits and separate financial obligations. Missing synthesis
uses the existing digest fallback rather than a new quality gate. Complete-report
source delivery includes late proposed findings/orders but not independent attachments.

Scripted resolved layout artifacts cover RT→CT→embedded preliminary→later CT,
CT-only with an embedded transcript, and standalone preliminary-hearing RT. A genuinely
separate unsupported CT→RT collection remains review-required. Embedded pages stay CT
and get no RT hearing starts in the production-worker fixture. The numbering test
preserves authored outer CT 210/211 rather than enclosed reporter/docket values and
retains authored ambiguous/missing values through current validation/normalization;
it does not pretend to perform automatic visual number selection.

Contract checks verify source-title fallback only for known rules, unchanged report-date
instructions, naming/summary prompt inspection parity, both protected built-ins,
Dependency defaults, independent Save/Reset/history/stale guards, creation bases,
no Criminal import of legacy Dependency customization, and fixed hearing/motion
methods. Existing bundle-wide tests cover the other application-owned stages.
Recognition v3 changes explicit Basic/Advanced identities for assigned and unassigned
work, not Dates/Names identities through the recognition contract. No private output
is relabeled, cleared or regenerated.

## Native desktop acceptance

`tests/acceptance_criminal_profiles.py` uses the real manager/editor and an isolated
GTK application ID (`org.synthetic.RecordPrep.CriminalAcceptance`). It selects each
profile, opens all **three editable destinations**, checks populated 1/6/12 Dependency
and 1/12/9 Criminal catalogs, compares inspected/runtime naming prompts, edits an
actual retained buffer, saves, resets through the confirmation, verifies saved history,
and confirms both creation bases and the absence of built-ins from deletion choices.
A separate run of `acceptance_new_profile_menu.py` exercised ordinary Create/Save and
its unsaved-draft guard.

Local Computer Use observed the Criminal form cards (all twelve), source-title editor,
and all nine report-topic cards in screenshots, plus the populated probation rule
through AT-SPI. Back navigation was exercised through its accessibility action.
Later GNOME window-control/screenshot access became unavailable while the session was
locked; no desktop settings were changed to work around it, and coordinate/keyboard
input without a visible state change is **not** claimed as successful navigation.
All synthetic processes were closed; no real case was opened, saved or navigated.

## Reproduction outline

Use a disposable tracked-source copy named `RecordPrep` (some existing tests infer the
owner from that basename), not the maintained checkout. Include the new uncommitted
tracked-source additions, but no private ignored files. Initialize a temporary Git
index for resource-tracking assertions; no commit is necessary.

```sh
P=/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env
# HOME/XDG/Pi state must already point to disposable local directories.
export PI_RUN_METRICS_ENABLED=0
"$P" --project /tmp/validation/RecordPrep --environment /tmp/validation/env sync RecordPrep
"$P" --project /tmp/validation/RecordPrep --environment /tmp/validation/env run RecordPrep \
  python -m unittest discover -s tests
"$P" --project /tmp/validation/RecordPrep --environment /tmp/validation/env run RecordPrep \
  python .pi/scripts/run_recordprep_skill.py --validate-resources
"$P" --project /tmp/validation/RecordPrep --environment /tmp/validation/env run RecordPrep \
  python tests/acceptance_criminal_profiles.py
```

The GUI script optionally accepts `CRIMINAL_PROFILE_HOLD=1` and
`CRIMINAL_PROFILE_PAGE=report-naming|form-naming|reports-topics` for observation; close
the synthetic parent window to finish and remove its temporary store. Validation
logs/builds remain machine-local under `/tmp/recordprep-criminal-validation/`.

## Limits

This is a bundled, editable **first draft**, supported by reviewed document structures
and mechanical regression checks. Real image-model naming/layout/citation accuracy
and generated-digest quality **have not been established**. Offline fixture answers
are authored expectations, not model-quality results. No paid semantic acceptance,
legal merits analysis, standalone investigative summary, new hearing feature,
mandatory repair pass or blocking quality validator was introduced. Later paid
semantic evaluation requires separate authorization.
