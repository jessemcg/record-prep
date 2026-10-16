# Public source installation: validation

## Scope and status

Validated locally on **2026-10-15**, on the Home desktop running Ubuntu 26.04,
x86_64. This is implementation evidence, **not clean-machine Ubuntu/Fedora or
ARM certification**. No public files were pushed and the GitHub `main` download
URL was not verified live. The README command requires publication first.

All write-producing checks used disposable source copies and environments under
`/tmp/recordprep-public.i3OBiHNq`, synthetic settings/records, isolated HOME/XDG/
cache/runtime state and disabled production metrics. Offline SDK acceptance
explicitly exercised its synthetic collection modes. No real credentials, model
selection, authentication, paid calls, OCR/model downloads or case preparation
were performed. The maintained RecordPrep environment, desktop launcher and
private preferences were not provisioned, migrated or overwritten.

## Automated evidence

| Check | Result |
| --- | --- |
| Complete stdlib unittest suite, installed offline Pi SDK available | **617 tests passed**, no skips (`full-final-display.log`) |
| Separate Desktop_Files portable-template tests | **2 passed** |
| Deterministic exported-template comparison | Passed |
| Tracked Pi resource validation | Passed |
| Bash/POSIX shell syntax | Passed |
| Source distribution and wheel built with Hatchling | Passed |
| Built archive inspection | Source includes installer/templates/tracked `.pi`; wheel includes bundled profiles/resources and new runtime modules |
| Installed command/help and environment binding | Passed, without launch-time provisioning |
| Desktop entry validation | Passed; validator emits an informational multi-category hint |
| Native capability/PDF smoke check | Passed: GLib 2.88, GTK 4.22, Libadwaita 1.9, VTE 3.91; synthetic extraction, reading and grayscale rendering |

Tests cover platform policy; ownership collisions; private receipts and locks;
interrupted source acquisition and durable uninstall; locked sync and non-provisioning
launch; repair/resume without source updates; modified files and running-process
refusal; profile/document preservation; and file-granular settings purge.
Package managers, Git publication and AI execution are fabricated in lifecycle tests.
Native package preview checks refuse unrelated removals, including bootstrap
prerequisites, and use stable-language output for parsed transactions.

Real controlling PTYs exercise Enter/Ctrl+C, optional Pi Enter/skip/EOF/cancel,
append-only colored/plain/ASCII output, piped arguments/status, and completed
receipt/success **before** the Pi offer. Synthetic Pi failures and discovery failures
leave application success intact. Failed partial public-installer, maintenance-engine
and Pi downloads are never executed; temporary downloads are cleaned up.

## Preferences and prepared-work compatibility

`tests/fixtures/public_install_baseline.json` records synthetic identities from the
pre-adapter implementation. Tests compare legacy and equivalent external settings
for native runtime/model identity, classification, hearing/report extraction and
synthesis, minute orders and case naming. Deliberately conflicting checkout
preferences cannot leak into selected public settings. Tests also exercise missing
provider-neutral defaults, private atomic saves, malformed-file preservation,
restricted-PATH Pi discovery, selected-preference staging and workspace cleanup,
and settings-based freshness invalidation.

Exact pre-adapter participant/overview fingerprints remain recognized only under
the reviewed new stage-code hashes and the unchanged effective runtime identity.
Unknown fingerprints and modified tracked resources are rejected; existing native
freshness tests continue to cover source/profile/component changes. No prepared
case metadata or artifacts were rewritten to obtain this result. Prompts, bundled
practice profiles, schemas, summary contracts and generation policy were not changed.
This demonstrates compatibility for the tested contracts, not live-model quality.

## Installed-command and desktop exercise

A separately rendered, receipt-bound public-install fixture used a real editable
managed-Python environment, the actual desktop templates/icons, command wrappers
and native checks. Locked sync installed the declared dependencies. It was launched
through its actual desktop file with `gio launch`, then observed using native Linux
screenshots and accessibility on this computer only.

- Main window and Model settings opened without credentials or Pi installed.
- The profile menu displayed General Court Record and California Juvenile Dependency.
- The real Save action stored a synthetic classification URL/model externally with
  mode `0600`. Reopening confirmed persistence; source preferences stayed unchanged.
- The Pi settings page displayed the external preferences path and high-thinking
  policy, and handled absent Pi without preventing access to settings.
- Startup diagnostics were private and under the isolated XDG state directory.
- All synthetic application windows were closed after testing.

The actual installed uninstall command was exercised with dry-run and real `/dev/tty`
consent. It removed the owned environment, managed Python/tools, commands, desktop
entry and icons, while retaining source settings, external settings, nested accepted-
profile fixtures and a synthetic case byte-for-byte. Native build cache containing
upstream sample PDFs was **retained with a document-safety warning**, not purged.
The manually constructed fixture's ownership list was corrected before this final
removal exercise; ordinary installer interrupted-ownership persistence is covered
separately by lifecycle tests. No shared packages or Pi/Node resources were removed.

## Limitations and unsuccessful checks

- No VM/container, clean Ubuntu/Fedora installation or aarch64 execution was done.
  Platform/package policy tests are not distro provisioning certification.
- Initial isolated provisioning failed because the current host lacked Cairo/
  girepository development pkg-config files. Pointing uv at wheel files alone did
  not avoid the build-isolation failure. The successful real locked sync was seeded
  with this host's cached **native build artifacts** for the same locked PyGObject,
  pycairo and pdftotext versions. The environment used for execution was provisioned
  explicitly, not copied. Native package installation was not approved or performed
  on the host. Clean-machine dependency provisioning therefore remains unverified.
- A pre-existing, ignored checkout `.venv` (dating from July 7) was inadvertently
  included in initial disposable source copies. The final audit removed those unused
  copies; all execution used the explicitly selected separate environments. The
  maintained legacy `.venv` was left untouched, not migrated or cleaned up. Final
  validation was rerun without `.venv` in the disposable source.
- An attempted stripped, display-less full-suite run crashed in an existing GTK test
  during `Adw.init()`. The successful final run used the local display with isolated
  application state. PTY fork deprecation/resource warnings do not invalidate the
  passing assertions; no claim of headless-suite certification is made.
- Optional Pi installation/removal was tested only using fabricated downloads and
  offline SDK execution, not installation of persistent Pi/Node tooling.
- No live model/provider acceptance or factual quality comparison was requested.
- Do not run the public installer over Jesse's maintained installation. Dependency
  packaging changed to editable Hatchling; updating that separate environment, if
  desired, requires an explicit maintained `project-env sync RecordPrep`.

## Follow-up: maintained Home installation

On the user's subsequent request, explicitly ran the maintained UvEnvironments
`project-env sync RecordPrep` on Home. It installed the editable RecordPrep package
without dependency upgrades; `check`, CLI help and native/PDF checks passed.
Launched the existing installed desktop entry and confirmed its visible window
runs the maintained local Python with legacy settings selection, no public
`RECORDPREP_CONFIG_DIR` override and no Python startup traceback. Existing application
and Pi preference hashes remained unchanged. The application was left open.
No public installer was run over the maintained setup, and Work was not accessed.
Work retains the same UvEnvironments contract and needs its own explicit local sync
when it receives the packaging change; no Work launch acceptance is claimed here.

See [installation/removal contracts](source-install.md) and
[development safety guidance](development.md). Temporary evidence is local and may
be cleaned up later; it is not a shared runtime or a public release artifact.
