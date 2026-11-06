# API-only classification removal

Classification retains the existing configurable vision API transport and requires
URL, model ID and API key. No host/provider allowlist was added to the runtime.
The app-owned maintenance protocol retains its existing direct-transport
compatibility checks and protocol-v1 classification slot identity/output shape.
Shared Pi inheritance, permissions, CAS and locking are unchanged.

Removed the local switch/command editor, loader fields/save arguments, process
ownership/logging/readiness/shutdown and pipeline lifecycle tracking. Single-step
case/layout preflight remains; pipeline vision-stage preflight is independent of
retired settings and occurs after Resume's completed-output skip. Agent correction
remains outside the vision-stage set. OCR retains shared server/readiness/output
helpers, command editor, lifecycle and Stop handling.

`classifier_local_vision_enabled` and `classifier_local_vision_start_command` are
unknown inert values. Existing values survive ordinary settings saves unchanged;
fresh settings omit them. Former local-mode users explicitly configure their API
connection; no endpoint is guessed/replaced. Existing outputs remain usable, with
no classification schema/fingerprint migration or removal-only rerun requirement.
Basic → Advanced → Dates → Names → Agent correction and useful-results/advisory
review are unchanged; no prompts, model request payloads or artifact formats changed.

## Isolated validation (2026-11-06, home)

Disposable tracked-source copy at `/tmp/recordprep-api-only.TsnkZC/RecordPrep`,
separate environment at `/tmp/recordprep-api-only.TsnkZC/env`, temporary HOME and
XDG settings/data/cache/state, synthetic Pi preferences and offline providers only.
Provisioned through UvEnvironments/project-env with explicit project/environment.
The machine lacks Cairo development pkg-config metadata; seeding the temporary uv
cache with already-built matching local Cairo/GObject wheel cache entries allowed
locked provisioning without changing dependencies or production environments.

- Complete documented unittest suite: 912 tests, 904 passed, 8 skipped: three
  sibling-owner-specific maintenance cases, three tests requiring an installed
  offline Pi SDK fixture, and two optional sibling PiRunMetrics harness/policy
  checks. No SDK or sibling fixture was provisioned into the disposable HOME.
- Regressions cover absent/false/true/string legacy flags, all four loaders,
  unknown-value preservation, fresh saves, API-only required-field errors, actual
  CLI inventory/credential blockers/read-only bytes and mtime, GTK Save/reopen and
  failed-save drafts, single-step/pipeline success/failure/Stop/Run from here/Resume,
  plus existing OCR lifecycle/bundle restart, requests/checkpoints and agent review.
- Compilation and sequential resource validation pass. Production-code search
  finds no retired local-vision keys, lifecycle names or user-facing controls.
- Linux Computer Use inspected a uniquely identified synthetic settings instance
  with mocked discovery and no case. Classify exposes the five retained controls;
  OCR controls and the sole command editor work; Agent selection/navigation remain.
  API fields and OCR command save/reopen; a native UI model-field edit and Save
  succeed without closing. Server launch/probe/stop mocks remain uncalled.
  Only the synthetic instance was closed; maintained RecordPrep was left running.
- `git diff --check` passes. No private settings/preferences, case files, outputs,
  metadata/checkpoints, dependencies, launchers or sibling repositories changed.

The first suite attempt had harness-only failures from a global external-config
override interfering with tests' own synthetic project selection, and missing Git
metadata in the copy. Removing that override and initializing disposable Git
metadata resolved them without changing production behavior or those tests.
No paid calls or live semantic-quality/performance evaluation were performed.

Reopen RecordPrep normally to load the changes; do not restart an active session
or rerun classification solely because local server management was removed.
