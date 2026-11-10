# Dated minute selection — implementation validation (2026-11-10)

## Scope and result

Implemented in RecordPrep only, on **Home**. Recognition-v5 distinguishes actual
proceeding minute records from separately identifiable orders/templates without a
literal-heading gate or county allowlist. `dated-minute-selection-1` constructs
complete ranges before requiring recognized start dates for explicit TOC/boundary
preparation and saved-boundary filtering. Agent correction retains every candidate
before filtering and publishes post-correction omission notes in new receipts.
See [behavior and adoption](dated-minute-selection.md).

No real bundle was regenerated or used as a fixture. No private settings/profile,
source/classification, case metadata or prepared output was changed. No live
classifier/agent/OCR call, maintained-app restart, deployment, commit or push.
These offline checks establish deterministic contracts and preservation, **not
model precision/recall, legal relevance or completeness**. A date-only rebuild
cannot repair dated standalone-order look-alikes. Unreadable genuine minutes can
still be omitted; plausible dates can still be wrong.

## Isolation and commands

Disposable tracked-source checkout: `/tmp/recordprep-dated-minutes-validation/RecordPrep`.
Independent managed Python **3.13.12** environment: the sibling `env/`.
Temporary HOME/XDG/Pi state: sibling `isolation/`; metrics disabled.
Provisioned once using the absolute UvEnvironments helper's explicit paired
`--project` / `--environment` overrides and `sync RecordPrep`; no production-env
sync, Dropbox runtime or dependency/lockfile changes. The temporary checkout has
its own Git index for tests that inspect shipped-file tracking.

All application execution/tests used the helper's `run RecordPrep`, with no
launch-time downloads. The local `run` wrapper preserves those overrides and
sets umask 077 and isolated state. Commands included:

```text
python -m unittest discover -s tests -v
python -m compileall -q recordprep tests
python .pi/scripts/run_recordprep_skill.py --validate-resources
python tests/acceptance_dated_minute_selection.py
python -c 'import subprocess; subprocess.run(["node", "scripts/collect-prompt-tools.mjs", "--check"], check=True)'
```

The last command uses the helper-selected Python to invoke the existing system
Node executable; Node is not an installed Python-environment entry point. Agent
Skill validation used the installed skill-creator validator with available distro
Python/PyYAML against the disposable skill, without adding a project dependency.

## Acceptance evidence

| Check | Result |
|---|---|
| Full unittest discovery, final source | **1,041 run: 1,033 passed, 8 skipped**, 106.722 seconds |
| Historical recognition-v1–v4 bytes | Frozen SHA-256 regression checks pass; maintained resources unchanged |
| Prompt isolation | RT definitions, hearing start/date and unrelated first-page prompts unchanged; frozen pre-change hearing-date render hash passes |
| New recognition/date guidance | Runtime/inspection shared builder, frozen minute definition in date task, settings-canary isolation and stage-byte invalidation tests pass |
| Fictional scenarios | 12 newly authored labeled/unlabeled minutes, top date, titleless continuation, blank/datestamped/signed templates, separate orders, references, notice/service cases; authored expectations only, not fake-model accuracy claims |
| Selection | Supported calendar formats, whitespace/weekdays, absent/blank/nonstring/placeholder/impossible dates; adjacent starts, leading fragments, numerical gaps, omitted middle ranges, same-day preservation pass |
| Pipeline | Production TOC/Find/Filter methods share eligibility across selected/custom/historical/unassigned resolved contexts; minute-only saved artifact is processed; corrupt saved structure preserves output |
| Sources/downstream | Text/images and classification input bytes/mtimes preserved; rebuilt boundary/work-item/map-document counts agree; every physical page remains in map inventory |
| All-undated work | Empty new minute selection and zero minute-generation calls pass |
| Historical readers | Saved undated minute boundaries remain readable by minute work-item and source-map readers without writes/hidden filtering |
| Agent correction | Undated candidates remain in worklist/impact projection; ending hints, supported date/type repair, missed-start-plus-date recovery, helper guard, and post-correction-only notes pass; old receipt reading stays nonmutating |
| Safeguards | Existing classification/review source/input/Stop/publication guards plus new selection-resource identity and Stop/prior-output preservation tests pass |
| Native GTK | Fatal-critical synthetic production UI acceptance **PASS**, repeated after final code changes |
| Resource validation / offline registered-tool audit | **PASS** |
| Agent Skill validator / compilation / whitespace | **PASS** |
| Final maintained/tested byte parity | **21 intended paths identical**; **19 protected/historical paths** match HEAD; pre-change/new prompt byte-isolation audit passes |

The eight skips are three owner-specific settings tests, three tests requiring an
optional installed offline SDK fixture, and two optional sibling PiRunMetrics
checks. They are not failures or live-model acceptance. Full discovery includes
affected classification, review, naming, motion organization/continuity, hearing,
minute summaries/editions, source-map and publication tests. The changed review
extension's offline guard test also passed.

### GTK and Computer Use

`tests/acceptance_dated_minute_selection.py` creates six fictional source pages and
four explicit minute candidates, two dated and two unresolved. It uses the actual
review publisher (offline zero-change candidate), then production Build TOC, Find
boundaries and Filter boundary entries. It asserts two retained separate same-day
minute boundaries, two reported omission ranges, complete source/input byte+mtime
preservation, unchanged receipt on view, and two new read-only review notes.

Computer Use observed both source ranges (`0003–0004`, `0006–0006`), the omission
count/reason and evidence-preservation explanation in Activity, and both saved
notes in the existing read-only View review. No settings/save/apply controls were
added. A targeted review screenshot was partially off-screen because of desktop
tiling; the accessibility tree exposed complete note text, and a separate main
window screenshot showed complete activity output. Synthetic processes exited;
no maintained application or user's documents were closed/restarted.

Initial acceptance-harness iterations exposed a deprecated VTE text getter's GI
attributes assertion, an unregistered transient window lookup, and an expectation
that the view displayed warning codes rather than their reasons. Only the new
acceptance harness was adjusted: supported `get_text_format`, constructor capture,
and separate receipt-code/view-reason assertions. Final fatal-critical execution
passes without those errors. Earlier full-suite failures were obsolete expectations
that minute-date fingerprints stayed unchanged and a missing disposable Git index;
tests/index were corrected, not production/private metadata or historical resources.

## Compatibility and limits

TOC/boundary generation contract is **6** with minute-selection ID and helper hash
in guarded inputs. Profile schema **14**, bundled profile versions/catalogs,
`profile_contract.py`, `profile_artifacts.py`, README, CLI/dependencies/launchers and
Focus remain unchanged. Recognition-v1–v4 and historical validation reports are
preserved. Badges and Resume remain output-presence based; loading existing bundles
prunes nothing. Actual changed prompt bytes invalidate only appropriate explicit
new-work checkpoints; no freshness fabrication or checkpoint deletion.

A future real adoption run needs separate authorization through classification /
Agent correction and affected downstream organization, TOC, boundaries/filtering,
summaries, editions, overview and map. Do not infer CT-only paid execution from
unchanged RT prompts: shared Basic/Advanced can process both sides.

Machine-local logs: `/tmp/recordprep-dated-minutes-validation/logs/`, notably
`full-final.log`, `gtk-final.log`, `gtk-fourth.log`, `tools-final.log`, `resources.log`
and `skill.log`, plus `final-audit.log`. Temporary files contain fictional test data only. No live semantic
recognition benchmark was performed or claimed.
