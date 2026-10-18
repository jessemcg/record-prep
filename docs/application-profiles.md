# Application profiles, independent case bundles

RecordPrep uses the profile selected in its hamburger menu for **new preparation
and explicit regeneration**, whether a bundle is new or already exists. The name
beneath the app title identifies that application-wide choice. Changing or saving
it never rewrites a case selection, source page, summary, or other prepared output.
Clearing or opening a case does not change the selected profile.

Historical `.recordprep/practice-profile.json` files are left untouched. They are
not consulted for instructions, selection, freshness, or publication authorization.
An absent historical snapshot, an older profile version, or a malformed historical
pin cannot make the current profile unavailable. New bundles get no such pin.
Profile version labels remain internal compatibility metadata, not bundle requirements.

## Save and resume

**Profile settings → Save** saves application guidance. Saving the selected
profile advances the application's selected revision immediately, with no separate
“Use these settings for this case?” confirmation. Save does not run any models.
Choosing a different profile also changes the application selection for future
runs and survives restart, regardless of which case is open.

Generated artifacts continue recording descriptive profile provenance and actual
component/source/model/tool fingerprints. Those fingerprints prove whether a
checkpoint can be reused; they do not require its historical instructions to be
installed. Opening old output does not regenerate it. **Resume skips existing
outputs** and fills missing ones. **Run/Run from here** explicitly runs the requested
stage, using its current instructions/model and its own reusable checkpoints.

Saved upstream files are inputs, not settings-dependent permissions. Summaries use
existing boundaries and source pages (plus supported participant data for hearings)
without requiring classification markers, a current naming profile, or matching
filesystem timestamps. Classification stages consume the preceding saved files;
Find boundaries and Build TOC consume saved naming output. Overview/source-map work
uses saved summaries and preparation, without demanding old generation metadata or
rebuilding those stages. Missing/unreadable required files and invalid source ranges
still fail; changing upstream guidance does not itself invalidate saved preparation.
New provenance describes the publisher's active settings, not a claim that every
saved upstream file was regenerated under those settings.

Each run freezes its guidance. Local publication is serialized against changes to
the selected settings, including a profile-storage switch. A changed selection or
changed input prevents stale work from replacing published output. Profile
selection/Save still cannot weaken citation, source, tool or publication safeguards.

The historical `require_current_boundaries` entry point remains a compatibility
no-op: each consumer validates its actual inputs instead. Explicit boundary/TOC
publication fingerprints actual classification bytes (input contract 3); classifier
runs fingerprint actual preceding output bytes (input contract 2), not its old
markers. Timestamp differences alone do not invalidate unchanged classifier bytes.
Summary checkpoints still track the requested summary's inputs/guidance/model, so
an explicit rerun with changed summary instructions actually regenerates affected
rows, rather than merely labeling old rows current. Content changes during a run
still prevent publication over the prior final.

Native-runtime compatibility remains narrowly code/model-gated. The reviewed
saved-preparation change alters prerequisite checks, not participant/overview model
prompts; participant consumed-input hashes are unchanged. Overview hashing now uses
actual summary text, not historical summary metadata. A changed input hash is still
not accepted by runtime compatibility, and no historical markers are rewritten.

## Portable profile settings

Use **Profile storage…** in the hamburger menu:

- **Save to new folder…**: choose a parent folder. RecordPrep writes a new
  `RecordPrep profiles` directory and selects it for subsequent use. An existing
  destination is never overwritten or merged. Current profiles, personal edits,
  and the selected instructions are saved; original private stores remain intact.
- **Use existing folder…**: choose an already prepared portable directory.
  RecordPrep validates it before selecting it. It does not copy it into a local
  snapshot store, alter case bundles, or reset unavailable settings.

The portable directory contains `registry.json` and immutable, content-verified
`snapshots/`. It contains no credentials, model/runtime settings, recent-case
paths, or per-machine locks. It can live in a synchronized folder **outside case
bundles**. RecordPrep does not contact other computers or manage synchronization.

**Use one writer at a time:** close RecordPrep and let synchronization finish
before opening the shared profile folder on another computer. Local file locks
cannot serialize writers across machines. Conflicted registry copies, partial
snapshot synchronization, unsafe links/ownership/modes, or corrupt content are
reported, never automatically merged or repaired. Ordinary synchronized 0755/0775
directory and 0644/0664 file modes are accepted only by the explicit portable
store; the original private XDG store retains its owner-only validation. New
files are still created privately. Choose a private parent folder if profiles
contain confidential guidance; synchronization is not encryption.

The folder choice is machine-local at
`$XDG_STATE_HOME/recordprep/profile-storage.json` (default
`~/.local/state/recordprep/profile-storage.json`). Locks also live in that local
state directory. An optional absolute `RECORDPREP_PROFILE_DIR` launch override
selects an **existing** portable store and takes precedence; while set, change
that override rather than using the folder chooser. A missing configured folder
is an error, not permission to fall back silently to different instructions.
Existing private stores remain the default until an explicit storage action;
there is no launch-time migration or relocation of personal instructions.

## Validation boundary

`tests/test_application_profiles.py` covers absent/malformed historical pins,
application selection, portable export/selection, byte/mtime preservation,
no-overwrite, unsafe paths, sync conflicts, incomplete snapshots and private-store
permission isolation. The current profile generation/classification/minute/native
suites exercise actual runners and checkpoint reuse with synthetic models.
`tests/acceptance_application_profiles.py` exercises real GTK selection, Save,
case independence, storage switching and stale-editor protection.

Frozen unassigned-generation fixtures explicitly inject their legacy resolver
only inside tests (`tests/legacy_profile_fixtures.py`); production has no hidden
legacy-mode switch. Historical artifact readers remain unchanged. No private
case/profile migration or live model run is part of acceptance.
