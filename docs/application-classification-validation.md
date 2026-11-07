# Application-owned classification: validation and limits

Historical validation report: the classification-reference menu, window and dedicated
inspector described below were removed on 2026-11-07. Classification rules and runtime
behavior are unchanged by that UI removal. See the current
[ownership and maintenance contract](application-classification.md).

## Scope and isolation

Validated on the current `home` host, 2026-10-31. This is an implementation and
offline contract/routing validation, **not an image-model accuracy evaluation**.
See [ownership/adoption](application-classification.md) and the
[read-only structural review](classification-review.md).

Evidence is machine-local under `/tmp/recordprep-neutral.6Vtzzl` (private root).
RecordPrep and Focus source copies, locked Python 3.13 environments, HOME and all
XDG directories are disposable. Execution uses UvEnvironments/project-env with
explicit `--project`/`--environment` pairs; no synchronized `.venv` or production
environment was modified. Tests use umask 022, synthetic stores/pages and fake HTTP
responses. Passive run metrics are disabled. There were no RecordPrep live model,
OCR or paid-provider calls, no OCR/model-service start, and no other-host access.

No real configuration, case, accepted profile revision, historical JSONL or saved
output was changed. The separate read-only image review did not write to the
records. Its temporary private derivatives were removed; none is in source or
packages. No entry point, dependency, launcher, keyboard mapping or packaging
layout was changed. Focus's pre-existing untracked `.pi/` remains untouched.

## Completed automated checks

| Check | Result | Evidence |
|---|---|---|
| RecordPrep full unittest discovery, final current source | 842 run; 834 passed, 8 skipped; 91.355 s | `tests-final-complete.log` |
| Focus full pytest | 840 passed, 16 skipped; 11 subtests passed; 8 warnings; 16.42 s | `focus-final.log` |
| Production GTK acceptance, fatal criticals | PASS | `gtk-final.log` |
| Sequential Pi resource validation | PASS | `resources-final.log` |
| Python compileall | PASS | `compile.log` |
| Offline wheel and sdist build | PASS | `build-final.log` |
| Package membership/byte checks and isolated installed-wheel resource smoke test | PASS | `package-final.log` |

Skips are reported, not counted as passes: optional local SDK/sibling fixtures and
existing platform/feature exclusions remain. No fixture was provisioned merely to
turn a skip into a pass. Focus warnings are pre-existing deprecations. Tests were
run sequentially for the final results; no maintained app was restarted.

Coverage includes:

- Strict bounded UTF-8 recognition loading; duplicate, unknown, missing, empty,
  wrong-identity/schema and oversized data fail with no profile fallback.
- Canonical order, 15 type definitions and four clue sets; one shared prompt
  builder for runtime/inspection/preview/fingerprints. Display-title changes are
  excluded from model text and fingerprints. Dates remain independently fixed.
- Historical profile/config recognition is inactive, including malformed drafts.
  Retired config values and their absence survive ordinary model-setting saves.
- Schema-1–8 create/save immutability, new schema-9 revisions, naming v1–v4 and
  unknown custom naming prose. The bundled Dependency is 1.9.0/profile_api 1.
- All four structural stages use private reusable unassigned checkpoints and
  `profile_ref: null` metadata. Canonical output seeds work only with matching
  effective identity. The GUI's current-output diagnostic recognizes valid nullable
  metadata; badges/Resume remain output-presence based even if resources disappear.
- Frozen in-flight request prompts; publication rejection after resource, model,
  selection, source or actual upstream changes; aborted/resumed work; prior canonical
  bytes/mtime preserved on rejection. Historical unassigned Names remains its
  separate literal compatibility path, including its refusal to overwrite recorded
  profile-naming output when no profile is selected.
- Assigned **and unassigned** fake-HTTP routing: standardized hearing notices and
  distinct service proofs never receive form-start or form-naming requests and do
  not enter Forms TOC, even with misleading historical name fields. Those fields
  are not silently cleaned. Eligible forms still receive their existing work.
- Twenty-seven authored fictional scenarios cover all Basic types and positive/
  negative starts, including appeal/hearing-notice, service/authentication and
  continuation distinctions. They test contracts/eligibility, not visual accuracy.

Earlier full runs exposed obsolete profile-ownership expectations and one unchanged
summary-explainer assertion. Tests now explicitly distinguish current application
ownership from literal historical fixtures; the summary explanation was not changed.
An initial disposable config override also gave the wrong resource root; removing
that override and giving the source copy its own `.git` fixed the harness, without
production configuration repair. Final-audit regression coverage additionally caught
and fixed the old GUI check that rejected every unassigned metadata marker.
The added GTK missing-resource check initially had a wrong scratch-variable name
and then an overly strict trailing-whitespace expectation; both were acceptance-
harness corrections only. Their failure logs are retained alongside the final pass.

## GTK and native desktop evidence

`tests/acceptance_structured_settings.py` uses the production main-window action,
reference, prompt inspector and profile editor with synthetic stores. It verifies:

- Independent menu opening with no case and unavailable profile storage.
- Nineteen searchable, selectable/wrapped definition cards and eight complete fixed
  prompts, sharing one frozen recognition object and hiding draft/template controls.
  An already-open inspector remains consistent if the resource disappears; a new
  inspector reports the explicit no-fallback error instead of substituting prose.
- Search selection and Copy-button payload through a controlled clipboard stub;
  this does not claim a system-clipboard or keyboard-delivery test.
- Document naming/Summaries only; naming save/undo/selection/buffers/reset retained,
  summary/naming draft inspection, invalid naming-save refusal and fixed inspection
  unaffected by an invalid naming draft. Close/Escape handlers are present.
- Process-local light/dark/font overrides only, not persistent desktop settings.

Nine public/synthetic GTK widget snapshots were generated and visually inspected in
`gtk-images-3/`: reference light 850×760, narrow 480×760, dark 480×760, enlarged-font
**596×760**, naming home 850×760, report names 480×760, form names 480×760, summary
topics 850×760 and fixed prompts 700×760. Text wraps, editors retain full width and
content remains vertically scrollable. The enlarged-font request was 480 px but GTK
expanded the natural minimum width to 596 px; it is **not** evidence of a 480-px
large-font layout. Screenshots are widget renders, not desktop captures.

Native computer-use/AT-SPI observation on a separate synthetic interactive instance
confirmed the independent reference/settings windows. Setting search to `CT_notice`
filtered cards; invoking View full prompts opened the read-only inspector/task
chooser; native `window.close` removed it. That temporary process was terminated.
No maintained case window was used.

**Desktop limitation:** this GNOME Wayland session has no available WindowControl
D-Bus owner, and GNOME Shell GetWindows returns AccessDenied. Native targeted focus,
keyboard injection, window resizing and desktop screenshots could not be validated.
Do not equate direct callback/control tests with real keyboard acceptance. Initial
widget-capture attempts also failed with “No rendered GTK frame”; the successful
bounded run used fresh reference windows and remapped targets. Neither failure is
hidden by claiming broad manual acceptance.

## Packaging, parity and preservation

Hatchling built the unchanged 0.1.0 application wheel/sdist offline from the disposable
source. Both contain byte-identical recognition JSON and the schema-9/Dependency-1.9.0
manifest, without the removed current bundled classification-tasks resource. The
sdist includes current ownership/review/validation docs and new minute/form prompt
examples. The wheel was installed offline with no dependencies and `--link-mode copy`
into a separate scratch target; isolated `python -I` from an empty directory imports that installed
package, loads all definitions, builds all eight prompts and validates the bundled
profile without a sibling source/profile store. This is a resource/import smoke
check, not a claim that the pre-existing wheel layout includes the source-only Pi
installation workflow. The first smoke attempt used uv's default hardlinks and was
rejected by the existing profile reader's single-link safety check. The successful
copy-mode installation preserves that validator; no permissions or link checks were
weakened, and the failed attempt's log remains available.

The shared `profile_contract.py` is byte-identical in RecordPrep and Focus;
`profile_artifacts.py` is unchanged and remains byte-identical. Historical baselines
and bundled naming/topics/minute resources are unchanged. Both date prompt examples
are byte-identical to HEAD; naming and summary examples were not regenerated. Diff,
changed-source byte parity, public-only additions and resource/audit checks were
reviewed separately. No private review derivative, credential or case identifier is
part of this change.

## Adoption and remaining limits

Saved records continue to be read as stored. Opening, selection, Save or Reset does
not reclassify them, repair labels or refresh metadata. Adoption requires an explicit
Basic run followed by the desired downstream stages; new image work uses the new
application rules and can incur the configured provider's charges. Dates have no
direct recognition-content invalidation, but actual changed upstream bytes still
change downstream checkpoints. No live semantic-quality result is claimed here.

Publication is coordinated across separate repository commits: Focus's schema-9
metadata compatibility precedes RecordPrep's producer change. Reopen RecordPrep
manually to use the new application code; no maintained app restart or existing
preparation rerun was performed during this validation.

## UI follow-up: simpler classification explanation

At the user's request, the window and sole hamburger-menu entry are now named
**App-owned Classification**. The internal action ID is unchanged. Both naming
pages retain the original pipeline explanation/progression and naming prompt
inspection, without the added ownership/notice-policy paragraph, the repeated
“Enter each approved name…” catalog hint or a link to the application reference.
The unused profile-editor reference launcher was removed as well.

The isolated full RecordPrep suite passed again: **842 run, 834 passed, 8 skipped,
91.898 s** (`tests-app-owned.log`). Updated regression assertions cover both naming
pages and the exact window title. Fatal-critical production GTK acceptance passed
(`gtk-app-owned.log`), including menu-action opening and invalid-draft independence.
Current expanded-explainer and renamed-window widget renders were visually reviewed
in `gtk-app-owned/`; actual dimensions were 1233×2192 under the current desktop
layout, not the requested narrow sizes. GDK logged nonfatal swapchain warnings.
Native AT-SPI also exposed the new window title. Window queries were available
during this follow-up, but an attempted targeted desktop capture did not show the
intended synthetic window and was excluded from visual evidence. No native keyboard
or precise resize claim is added. The temporary interactive process was terminated;
no maintained app, case, configuration, model prompt, classification resource,
fingerprint or Focus code was changed by this UI-only follow-up.
