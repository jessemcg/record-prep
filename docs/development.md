# Development and maintained runtime

Public source installs need no sibling projects. Use `scripts/recordprep-env check`, explicit `scripts/recordprep-env sync`, and `scripts/recordprep-env run python -m unittest discover -s tests`. Run write-producing tests only in disposable source/HOME/XDG/runtime copies with synthetic configuration, disabled metrics and no real credentials/model calls. Do not provision tests into a production environment. `run` never downloads or synchronizes.

The editable Hatchling package includes bundled JSON/Markdown resources. Wheels are not a replacement for a complete source deployment with tracked `.pi/`. Keep `pyproject.toml` and `uv.lock` synchronized without unrelated dependency upgrades.

The maintained workflow below is separate and retains its Home/Work-only runtime policy; that hostname restriction is not public installer policy. A dependency contract change requires an explicit maintained `project-env sync RecordPrep`, never public installer takeover.

## Machine-local runtime

Home/Work only; do not provision/use on Laptop. From the RecordPrep checkout,
provision managed Python 3.13 with the absolute helper
`/home/jesse/Dropbox/MCGLAW/config_files/scripts/PROJECTS/UvEnvironments/project-env sync RecordPrep`;
use the same helper with `run RecordPrep python -m recordprep app` to launch.
The helper verifies the selected runtime; `run` never syncs or downloads.
Same-project Python children retain sys.executable; cross-project callers select
the callee helper identity. Never use real case/config files in tests. See the
[environment policy](../../UvEnvironments/README.md) for disposable overrides.
If pdftotext imports fail after a distro Poppler upgrade, rebuild the **same locked**
package against local headers (see UvEnvironments/migration-progress.md); do not upgrade
or copy an environment from another host.

## Operational run metrics

Summary tools now emit fixed private observations for prerequisites, correction,
nonfatal feedback, candidate/coverage acceptance and publication failure, plus
bounded scratchpad/facts operations. No notes, text, ordinals or item/quote IDs
are archived; old error totals/results/shutdown/publication authority are unchanged.
Actual summary-child and native Detect Layout wrappers have installed offline-SDK
passivity tests in six collection modes. A candidate/settled child is not pipeline
success. See the [contract and per-host checklist](../../PiRunMetrics/docs/observation-contract.md).

Native Pi stages and each hearing/report extraction/synthesis or minute-order child explicitly load the optional passive sibling PiRunMetrics observer. It registers no tools, adds no context and changes no Stop/stall, content-free stdout or Python publication contracts. One settled child is not pipeline success. Skipped, deterministic and zero-model work creates no metrics.

Default archive is source-project `.run-metrics/runs/`, Git ignored and private but possibly Dropbox-synced; reports remain machine-local under XDG state. Collection requires Pi 0.87.1+ without raising existing workflow runtime minimums. Absolute root/collector overrides and `PI_RUN_METRICS_ENABLED=0` remain supported. Missing policy/collector, invalid overrides or storage failures warn and fail open, without upgrades or archive relocation. New runner sessions load the adapter; existing children are unchanged.

Use sibling **Pi Run Metrics** for readiness, reports and copy-to-PiPlanner. No model calls or automatic implementation occur there. See `../../PiRunMetrics/docs/all-app-acceptance.md`; private configuration and historical archives are never migrated by this feature.

## Architecture

<img src="../recordprep_icon.svg" alt="RecordPrep icon" width="128" align="left">

RecordPrep is a GTK4/Libadwaita desktop pipeline that converts OCR-readable legal-record PDFs into a citation-aware case bundle for Focus. It preserves original page text/images, classifies pages, finds document boundaries, numbers official transcript pages, verifies counsel and witnesses, creates detailed summaries from source pages, and publishes source-map v2 for PI Agent search.

RecordPrep creates one concise, versioned, nonauthoritative case-orientation overview. It does not create retrieval chunks, speaker-labeled transcript rewrites, embeddings, Chroma stores, vector databases, or any case-overview retrieval index.

## Application icon

The amber document dissolving into pixels represents records becoming useful data.
`recordprep_icon.svg` is the editable 128×128 vector master;
`recordprep_icon.png` is its transparent 512×512 export used by the desktop
launcher. `recordprep_icon-symbolic.svg` is the separate 16×16 monochrome companion.

## Validation

From a disposable public installation's checkout:

```bash
scripts/recordprep-env run python -m unittest discover -s tests
scripts/recordprep-env run python -m py_compile recordprep/*.py recordprep/ui/*.py tests/*.py
scripts/recordprep-env run python .pi/scripts/run_recordprep_skill.py --validate-resources
```

For a disposable maintained-workflow checkout, use the absolute `project-env`
helper with `--project /tmp/source --environment /tmp/env` before `sync RecordPrep`
or `run RecordPrep …`. Do not run these write-producing checks against the real
checkout's private settings or the production environment.

Validate each new/changed Agent Skill with the Agent Skill validator. Keep real case material, local credentials, and generated case bundles out of Git.

See [installer validation](source-install-validation.md) for public-installation evidence and limitations.
