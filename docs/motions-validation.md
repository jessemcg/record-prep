# Motions — offline implementation validation

Validated on the current **work** computer only, 2026-11-06. Implementation is
uncommitted/undeployed; no publication was performed. See [workflow/adoption](motions-workflow.md).

## Isolation and results

Disposable source copies and independently provisioned machine-local environments:
`/tmp/recordprep-motions.NqinRQ/{RecordPrep,Focus,rp-env,focus-env}`. Every project run
selected the absolute UvEnvironments helper with explicit `--project` and
`--environment`; HOME/XDG were synthetic, metrics disabled, test data fictional.
Xvfb checks explicitly used `GDK_BACKEND=x11 GSK_RENDERER=cairo` (merely starting
Xvfb does not override an inherited Wayland backend).

| Check | Result / evidence |
| --- | --- |
| RecordPrep full unittest regression | **940 tests, 932 passed, 8 skipped**, 90.839 s; `rp-full-final.log` |
| Focus full pytest regression | **879 passed, 16 skipped**, 11.35 s, plus 11 passing subtests; `focus-full-final.log` |
| New motion mechanics/production workers | Included above: explicit yes/no checks on every motion page; independent motion/opposition/reply/declaration/supplemental papers; repeated titles; source-only gaps/unnamed starts; name/date cleanup; title limits/date basis; boundary correction; source-map IDs/aliases; optional manifest publication |
| Missing versus checked-zero preparation | Production Find boundaries does not manufacture old motion emptiness; Resume skips absent preparation, but runs checked empty selections. Zero-motion runner publishes matching final metadata without Pi discovery, extraction or synthesis; missing input preserves the prior final |
| Historical contracts | Schemas 1–10/naming 1–5 preserved; historical structured first-page key sets remain frozen, not widened to accept motion keys. Schema 11 strict resource/mode/duplicate/version tests in both projects |
| Summary skill delivery | Full regression expands complete motion skills in assigned/unassigned modes through the actual runner protocol, with the existing restricted tools |
| Sequential Pi resources | PASS; `resources-final.log` |
| Registered-tool audit | `node scripts/collect-prompt-tools.mjs --check`: PASS |
| Agent Skill validator | New extraction/synthesis skills, changed overview and correction skills: PASS |
| Python compilation / whitespace | Both package/test trees and runner compile; both maintained Git diffs pass `--check` |
| Shared modules | `profile_contract.py` **and** `profile_artifacts.py`: byte-identical between projects |
| Offline packaging | Cached Hatchling 1.33.0 PEP-517 backend, invoked through disposable helper-selected Python; wheel/sdist builds and full payload byte checks PASS; `build-*-final.log`, `package-check-final.log` |
| Extracted-wheel smoke | Isolated `python -I`, asserted module paths inside extracted wheels: new recognition resource, Dependency 1.14.0/schema 11, motion naming, Focus descriptors/category/discovery PASS |

Wheel application/resource payloads are **100 RecordPrep files** and **41 Focus
files**, each compared byte-for-byte with source. Sdist checks cover all included
source/documentation payloads, new motion skills and runner; no private config or
Pi settings are packaged. Wheels retain the existing source-only Pi-resource
limitation; this work does not change packaging/entry-point/dependency declarations.
Direct `uv build --offline` initially lacked index metadata in the isolated cache;
using already cached build requirements directly avoided network access or any
installation into a production environment.

## Cross-repository GTK acceptance

Producer: `tests/prepare_motion_acceptance.py`, run in RecordPrep's own disposable
environment. Consumer: Focus `tests/acceptance_motions.py --bundle <printed-path>`,
run separately in Focus's own environment. No combined/inherited project environment.

Actual producer code creates three independent motion boundaries/work items,
canonical digest rows, deterministic final text and matching metadata, a real
PDF/page-map edition and source map/manifest. Focus loads those exact outputs in a
unique synthetic application instance under `G_DEBUG=fatal-criticals`. Assertions
cover source-map Motion categories, filtered sidebar, four button/wrapper states,
direct Motions routing, actual edition identity, disappearance fallback to Agent Q&A,
and byte/mtime preservation during the read-only phase. Deliberate later fixture
changes populate all four buttons to stress wrapping. **PASS**:
`crossrepo-gtk-final.log`; rendered light/dark narrow and dark wide PNGs are under
`/tmp/focus-motions-acceptance-42uzatvn/`.

At 486 px the top mode buttons occupy two rows without clipping; at 1270 px they
fit one row. The existing paginated-summary navigation also wraps vertically at
the narrow size; it was not redesigned by this feature. Screenshot review confirms
the distinct rose source-page/sidebar treatment in both themes. These are actual
GTK-rendered Xvfb snapshots, not native desktop screenshots.

The acceptance check exposed and fixed cross-family discovery/inference when a
case-name suffix contains “Motion”, “Hearing” or “Report”. Current manifest finals
win over legacy fallback; matching zero final metadata is distinguished from
unreadable/stale metadata. Actual minute output uses **Minutes Summary** and its
own `recordprep-minute-summary` metadata; both are supported, along with the known
older Minute Orders Summary title. A real heading with null categories stays usable.

## Limits and unchanged state

Native Computer Use was attempted on this same computer. AT-SPI could see the
synthetic window, but window targeting became unavailable and the portal screenshot
was black. Native input/visual desktop acceptance is therefore **not claimed**; no
unlock, accessibility/session setup or maintained-app restart was attempted. The
synthetic process ended after its bounded hold. Xvfb runtime/snapshot acceptance and
full automated tests succeeded independently.

Scripted classification/summary responses prove mechanics and contracts, **not live
visual recognition or semantic model quality**. No provider calls, real credentials,
private case/settings writes, migrations, deployment, dependency changes, maintained
app restarts or other-computer operations occurred. Focus's pre-existing untracked
`.pi/` was excluded and left untouched. Desktop launcher/XREMAP references were
inspected read-only; existing IDs/paths/actions were unchanged and need no update.

If publication is separately authorized, publish compatible **Focus first**, then
RecordPrep. Existing bundles/profiles adopt motion work only through explicit user
actions; this validation never regenerates user output.
