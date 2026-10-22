# Source installation and removal

## Publication and platform policy

Fresh installations follow `origin/main` on a named `recordprep-install` branch;
the receipt records the actual commit. The public URL in the [README](../README.md)
requires the installer files to be published to `main`. Local implementation and
validation do not establish that the live URL works. There is no release-pin manifest.
Resume/repair recheck an owned installation without fetching, resetting, cleaning,
stashing, silently updating source, or changing its lockfile.

Initial policy: mutable Ubuntu 24.04/26.04 and Fedora 43/44 or compatible derivatives,
x86_64/aarch64. Actual GLib/girepository 2.80+, GTK 4.12+, Libadwaita 1.4+, GTK4 VTE
3.91 and used APIs must pass capability checks. Poppler C++ headers/build tools are
required for `pdftotext`: `libpoppler-cpp-dev` on apt; `poppler-cpp-devel` and
`gcc-c++` on dnf, in addition to the GTK/Cairo development dependencies.
Final checks import the PDF libraries and extract/render a tiny synthetic PDF.
See [validation evidence and limitations](source-install-validation.md), not a
clean-machine Ubuntu/Fedora certification claim.

Unsupported/immutable systems stop before application changes. No repositories,
OS upgrades, SELinux changes, GPU services, CUDA, model downloads, local OCR server,
or Focus installation are included. Embedded PDF text is the default extraction
route. The public installer has no Jesse-specific hostname restriction; his separate
UvEnvironments laptop exclusion remains unchanged.

## Destinations and ownership

| Component | Default |
| --- | --- |
| Editable source | `~/RecordPrep` (`--source-dir` selects another new destination) |
| Python environment | `~/.local/share/uv/project-envs/RecordPrep` |
| App-managed Python | `~/.local/share/uv/project-python/RecordPrep` |
| Private uv when needed | `~/.local/share/recordprep/tools` |
| Application preferences | `$XDG_CONFIG_HOME/recordprep/config.json` |
| Pi model preferences | `$XDG_CONFIG_HOME/recordprep/pi/settings.json` |
| Receipt/maintenance log | `$XDG_STATE_HOME/recordprep/` |
| Durable maintenance engine | `$XDG_DATA_HOME/recordprep/installer/` |
| Disposable cache | `$XDG_CACHE_HOME/recordprep/` |
| Commands | `~/.local/bin/recordprep`, `~/.local/bin/recordprep-uninstall` |
| Desktop ID | `com.mcglaw.RecordPrep` |

Unset XDG variables use standard HOME-based `.config`, `.local/state`, `.local/share`
and `.cache` fallbacks. Runtime ownership roots are private, machine-local below
HOME, non-symlinked, nonoverlapping and not group/world writable. Foreign environments,
commands, desktop entries and icons are rejected. In particular the public installer
must not take over Jesse's maintained runtime/launchers. Do not delete private settings
to work around a collision. An existing unowned source checkout is not adopted.

## Terminal workflow

Run as the normal desktop user, not root. `sudo` is used only for separately approved
native package transactions. The normal command requires curl already installed;
install it through your distro software manager if necessary.

```sh
./install.sh --dry-run
./install.sh --source-dir "$HOME/Applications/RecordPrep source"
./install.sh --source-dir "$HOME/Applications/RecordPrep source" --resume
./install.sh --source-dir "$HOME/Applications/RecordPrep source" --repair
```

The welcome message, colored labels, Unicode/ASCII fallback and eight-stage display
match Focus. Stages are platform/destinations, proposed changes, native dependencies,
editable source, uv/Python, locked dependencies, desktop integration, final checks.
The bar counts passed stages, not elapsed time. Output is append-only and package
manager progress stays visible. Redirection, `NO_COLOR` and `TERM=dumb` produce
plain output. Prompts read `/dev/tty`, so they work through `curl | bash`.
Normal path and native-dependency approvals use **Enter to continue / Ctrl+C to cancel**.
Exceptional bootstrap prerequisites and destructive removal need explicit authorization.
No credentials, authentication transcripts, model selection or paid requests occur.

The piped bootstrap itself executes as it arrives and trusts published source.
Every subsequent installer/Pi component is downloaded completely before execution;
a failed download is never executed and temporary files are cleaned up. From a checkout,
print these alternatives without installing anything:

```sh
python3 scripts/print-install-command.py
python3 scripts/print-install-command.py --downloader wget
python3 scripts/print-install-command.py --download-first
python3 scripts/print-install-command.py --expanded
python3 scripts/print-install-command.py --inline
```

`--download-first` also fully downloads the initial bootstrap. `--inline` prints the
self-contained downloader-provisioning form; missing curl/Python prerequisites are
previewed and explicitly authorized. Bootstrap package additions are reported and
retained if a later download fails. No source viewer/pager or extra execution gate
is required on the normal path. Review [the bootstrap](../scripts/install-bootstrap.sh)
and [maintenance engine](../scripts/recordprep_maintenance.py) if desired.

## Pi is strictly last

After final application checks, setup saves a **complete** receipt and prints:

> RecordPrep is installed. Open it from your applications menu.

Only afterward does it discover Pi. Existing Pi is retained. Missing Pi offers:

> Press Enter to install Pi, or type skip to finish:

Enter runs the fully downloaded official `https://pi.dev/install.sh` in the same
terminal. Skip, EOF, Ctrl+C, discovery/download errors or Pi installer failure leave
RecordPrep complete and return installation success. Pi can be installed later.
No AI account is necessary to install/open RecordPrep; a complete preparation run
still needs configured Pi access **and a separate classification endpoint/model**.

Afterward open Pi and use `/login`, then select an available model in RecordPrep's
**Model settings**. Pi authentication does not supply the classification endpoint's
credentials. AI use may incur provider charges and send text/images to configured
providers; review confidentiality terms and verify generated work against the record.
Pi credentials/sessions stay in Pi's global store, never a bundle or app preferences.
Discovery recognizes PATH, `PI_CODING_AGENT_DIR/bin/pi`, managed Pi Node locations,
and supported legacy locations even with a restricted desktop PATH.

## Preferences and prepared work

Public commands/helpers set absolute `RECORDPREP_CONFIG_DIR`; that selection is
authoritative and does not merge checkout-local personal settings. Without it,
existing checkout `config.json` and `.pi/settings.json` remain supported, including
explicit test/staging roots. Startup never migrates, overwrites or deletes them.
Missing Pi preferences in either mode mean no app override: inherit live user Pi
settings/native behavior, with no shipped model, reasoning or general preferences.
Startup, reads, refresh and unrelated saves never create Pi preferences. Explicit
model-only saves do not add reasoning. Existing standalone XDG preferences are
unaffected. Before updating an older Git checkout, preserve any personal selection
from the formerly tracked `.pi/settings.json` outside the checkout, then restore it
to that ignored path if desired. Git removal can delete a downstream checkout's
unmodified tracked file; it does not automatically preserve every user's copy.
No automatic settings migration or reset is performed.
Private workflow workspaces enable skill commands for required `/skill:` expansion;
this is a workflow requirement, not a persistent preference default.
Explicit Model settings saves create private atomic files;
malformed existing settings are not silently repaired/replaced. Public startup logs
live in private XDG state, not the legacy shared `/tmp/recordprep_startup.log`.

Settings saves use private, machine-local locks in
`$XDG_STATE_HOME/recordprep/settings-locks` (default
`~/.local/state/recordprep/settings-locks`), for both GUI and model-maintenance
commands. Keep XDG state outside synchronized folders and use the same state
location for all RecordPrep processes. Settings themselves may remain synchronized.
Close all RecordPrep processes before updating from versions with adjacent
`.writer.lock` files, then relaunch; old adjacent locks are ignored and left
untouched. Do not delete active local lock files. Locking coordinates this computer
only: shared settings still require single-writer use and completed synchronization
before switching computers. No settings or case-file migration is required.

`RECORDPREP_PI_PROJECT_DIR` selects **tracked resources**, not a settings-only directory.
Prompts, skills, extensions and runner stay under the installed checkout's `.pi/`.
The selected effective preferences are privately staged beside those resources for
native/summary children and isolated model discovery. Global auth, allowlists, Stop,
publication authority and workspace cleanup are unchanged. Profile registries and
accepted snapshot locations are unchanged; historical bundle-local naming fallbacks
are not current application settings.

Equivalent legacy/external settings retain model/guidance identities. Exact reviewed
pre-adapter native fingerprints are supported only under the new reviewed stage-code
hash and unchanged source, model, resources and profile components. Unknown hashes or
real input/preference changes still stale affected work. No case metadata/artifacts
are rewritten and no regeneration is required merely to change settings storage.

## Launch and development

Launch goes directly through the verified editable environment, never launch-time
`uv sync`, dependency/Python downloads or Git updates. Public launchers disable
optional run metrics; the maintained workflow is unchanged. Users need RecordPrep
alone, not Desktop_Files, UvEnvironments, XREMAP or Focus to install it.
Desktop templates are deterministically exported from Desktop_Files at development
time; end users receive their copies here and the existing RecordPrep icon assets.
No maintained local entry is replaced or deployed by template export.

```sh
cd "$HOME/RecordPrep"
git status --short
scripts/recordprep-env check
scripts/recordprep-env run recordprep
# Explicit dependency provisioning only when intended:
scripts/recordprep-env sync
```

Use disposable source/runtime/HOME/XDG copies for write-producing tests:
`python -m unittest discover -s tests`, Python/shell syntax checks and
`python .pi/scripts/run_recordprep_skill.py --validate-resources` through their
verified environment. There is no additional test-framework dependency.
See [development](development.md) for Jesse's distinct maintained workflow.

## Removal

Close RecordPrep and its children yourself; removal never kills running applications.

```sh
recordprep-uninstall --dry-run
recordprep-uninstall
recordprep-uninstall --purge --dry-run
recordprep-uninstall --purge
# Only if separately desired, with independent confirmations:
recordprep-uninstall --purge --cleanup-packages --cleanup-pi
```

Normal removal deletes owned commands, desktop entry/icons, environment, app-managed
Python/tools and disposable cache. Cache containing protected document/profile
structures (including upstream sample PDFs) is retained with a warning rather than
guessed safe to delete. Removal retains source, application settings, personal
profiles/accepted revisions, case documents, Pi and shared packages. Ownership hashes,
private receipts, locking and durable early maintenance allow safe partial-install
recovery. Modified/foreign files, unsafe links/paths or malformed receipts cause refusal,
not forced replacement. Interrupted installs retain their changes for resume/removal.

Optional purge independently confirms installer-created source and maintenance
resources by exact path, reports all Git changes/ignored additions/branches/local
commits, and refuses source deletion containing user records, PDFs/documents or
personal profile stores. Settings cleanup confirms **only individual application
preference files** under an installer-owned settings directory. It never recursively
deletes the XDG RecordPrep directory; all personal registries/revisions and unfamiliar
files remain, including nested ones. Pre-existing settings are retained.

Shared package cleanup is separately requested/consented, bounded to introduced
packages and previewed; unrelated removals are refused, never `autoremove`.
Introduced Pi cleanup uses its official uninstaller; existing Pi is retained.
Introduced Node needs separate exact-path consent and no active shared Node process.
Pi credentials/sessions remain. Shared tools may now serve unrelated apps.

**No removal mode deletes case bundles, source documents or personal profiles.**
