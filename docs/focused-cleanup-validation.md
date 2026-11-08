# Focused cleanup after test-bundle review

Historical validation snapshot for the first focused cleanup. The subsequent
[motion selection follow-up](motion-selection-validation.md) deliberately extends
request-and-reasons selection to **extraction and synthesis**, superseding the
synthesis-only scope and extraction-reuse statements below for new motion work.
Its separate evidence does not replace or retroactively change these results.

Implemented against `90c60c1bffe8430d934a1f4660b3211c81208d15`, on Home only.
Uncommitted implementation; no push, deployment, application restart or live generation.
All execution used fictional inputs and isolated state. The reviewed real bundle and
private settings were not opened, changed, regenerated or cleaned up by this work.

## Changes and preservation

- Schema-1 grouping separates review-coverage failures from advisory findings.
  Complete nonempty work requires explicit complete coverage, usable groups, every
  inventory paper accepted exactly once and no rejected membership/fallback work.
  Reviewed ambiguous singletons, title fallbacks, advisory notes and omitted invalid
  optional relationships need not downgrade coverage. Malformed/duplicate/missing
  work remains incomplete; independent useful groups and every physical paper survive.
- Text-only organization instructions recognize image-derived dates and prohibit
  treating absent OCR stamp text as proof of an absent stamp or a replacement date.
- The existing plain-text, read-only grouping window separates review coverage,
  pluralized counts, components, relationship explanations and notes. Historical
  statuses remain literal; viewing performs no normalization or publication.
- Pipeline subtitles/messages now include motions, preserve named one-page reports,
  describe hearing proceedings/arguments/rulings and compact minute entries, and use
  count-independent edition prerequisites. Boundary completion counts the motion
  rows removed by the **unchanged** existing filter. Layout separators use ` • `.
- Fixed minute instructions/examples distinguish express nonproduction from custody
  or counsel-only evidence, verbatim page evidence from paraphrase, and current
  continued hearings from actual future settings. They exclude other-source gap
  filling and routine production logistics, and preserve source chronology uncertainty.
  Attendance normalization/matching, complete-order scope and historical readers did
  not change. Python still verifies evidence location, not attendance semantics.
- Motion **synthesis only** opens with party, relief and target; retains identifiers
  and procedural particulars only when consequential; integrates support into its
  argument; and uses meaningful, exact quotation anchors with attribution. Request /
  Reasons, extraction, quote verification, format and digest-prose fallback are intact.
- Both overview delivery methods have identical substantive instructions for logical
  motion groups, last-ruling-dated posture and consolidated missing-outcome limits.
  Their distinct read/publication boundaries, five headings and disclaimer remain.

`recordprep/profile_editor_ui.py` is byte-identical to the pre-task snapshot, including
all four protected explanation/progression constants and the disclosure builder.
There are no shared style changes. Synthetic GTK checks verify explanation + two
newlines + progression, wrapping, initially collapsed disclosures and natural-height
expansion without an internal capped scroller.

`profile_contract.py` and `profile_artifacts.py` are unchanged and byte-identical to
Focus. No Focus source, schema, dependency, public CLI, launcher, XREMAP, membership
rule, source identity, completion badge, Resume or settings-navigation change.

## Freshness and adoption

An independent before/after subprocess comparison used identical isolated model
preferences and both assigned/unassigned paths:

| Component | Result |
|---|---|
| Hearing/report extraction and synthesis | Identical/reusable |
| Motion extraction guidance and effective configurations | Identical/reusable |
| Motion synthesis guidance/effective configurations | Changed |
| Minute fixed instructions/component/configurations | Changed |
| Organization guidance/normalizer resource hashes | Changed |
| Both overview instruction paths/components | Changed |
| Participant compiled instructions/components | Identical |

The existing conservative native runner code projection also changes both native
runtime hashes because the organization completion message lives behind a nonliteral
`organization_guard` branch in the shared runner. No participant instructions or
compatibility manifest were changed to conceal that fact. This does not trigger an
upstream run or change presence-based Resume/badges. Unrelated hearing/report summary
fingerprints remain identical.

Current regression tests verify explicit organization guidance/normalizer invalidation,
minute instruction/skill invalidation and zero-call reuse, synthesis-only invalidation,
and fixed delivery through assigned, historical/custom and unassigned paths. Existing
native tests cover overview instruction invalidation and input/read boundaries.
The packaged prompt-tools audit was regenerated offline; definitions/tools are unchanged.

No saved artifact is relabeled current, migrated, silently repaired or deleted.
Adoption requires explicit organization/minute/motion-synthesis/overview work as
applicable, followed by dependent TOC, editions, overview and map refresh where needed.
No profile reset/save or hearing/report regeneration is needed solely for these edits.

## Validation evidence and limitations

Machine-local evidence root: `/tmp/recordprep-focused-cleanup.5tfrap7b`.
Disposable source and Python environment were selected with the absolute
UvEnvironments helper and paired `--project` / `--environment` overrides. HOME,
XDG, Pi and temporary state were private/isolated, metrics disabled, and providers
scripted/offline. No global `RECORDPREP_CONFIG_DIR` masked fixture-owned settings.

- `full-second.log`: **985 tests, 977 passed, 8 skipped**, 114.305 seconds,
  ordinary `python -m unittest discover -s tests -v`, `G_DEBUG=fatal-criticals`.
  Includes grouping/accounting/fallback/Stop/source/publication tests, boundary
  counts, all six layout/source-spacing combinations, minute attendance/source/
  history checks, prompt-inspector parity and actual installed-SDK summary/native
  skill-delivery tests. Fifteen tests were added to the 970-test baseline.
- `regressions-final.log`: **153 focused regression/delivery tests passed** in
  20.282 seconds on the final application/test bytes (no skips).
- `optional-sdk-verified.log`: three additional optional installed-SDK checks
  **passed**, with mixed/CT-only exact overview reads and continuation, participant
  guard settlement, and quote-display schema acceptance. Only the offline fixture
  was copied from PiRunMetrics into scratch; no sibling source/runtime was changed.
- Later whole-suite runs enabling those optional checks exposed one existing GTK
  viewport assertion in `test_selection_viewport_and_navigation_survive_shorter_replacement`
  (`2.0 != 195.0`). `viewport-baseline.log` reproduces the identical failure on the
  untouched baseline; `viewport-RecordPrep.log` does so on revised code. Ordinary
  earlier full-suite success must not be misrepresented as a clean final enhanced
  run. Neither process-local animation suppression nor Cairo eliminated this local
  failure. No protected editor/navigation code or unrelated assertion was changed
  to hide it. All other tests in those runs passed; five owner/optional-metrics skips
  remained. This is the outstanding local validation limitation.
- Initial scratch setup failures used the wrong checkout basename, nonprivate TMP
  permissions and stale prompt audit hashes. The harness and generated audit were
  corrected before `full-second.log`; no private state was used as a workaround.
- Resource validation, four changed Agent Skill validators, offline registered-tool
  audit/check, compile of 200 Python files and Git diff whitespace checks **passed**.
  Cached read-only Hatchling 1.33.0 built the wheel/sdist without dependency changes;
  all 100 wheel payload files and 133 sdist Python/resource files matched source.
- `fingerprint-comparison.txt`, protected-file/constant checks and shared-contract
  parity **passed**. Maintained/test-copy parity pins the validated bytes.
- Synthetic GTK acceptance verifies production subtitles and grouping widgets,
  unformatted literal model text, saved incomplete status, exact titles/ranges/date
  basis/lead anchor, and unchanged fixture bytes/mtime during viewing. Reviewed
  widget-rendered captures cover Classify, Organize, Summarize, grouping and protected
  disclosures. Some individual compositor snapshots were unavailable; separate bounded
  runs supplied the reviewed images. Native Computer Use independently observed the
  read-only grouping tree, but GNOME window targeting/screenshot access later became
  unavailable; no native input, setup, unlock or user-window restart was attempted.
  Only the synthetic test processes/windows were opened and closed.

Offline tests establish delivery, mechanics and preservation, **not guaranteed
live-model editorial improvement**. No paid/model evaluation was performed.

## Deliberately deferred quotation observations

The prior review's diagnostic experiment attributed eleven hearing quote warnings
to intervening transcript line-number markers. Twelve report quotes were found on
other pages, often with multiple possible matches. These are review observations,
not evidence that useful summaries should be rejected or that automatic first-match
page reassignment is safe. Quote matching, page attribution and the broader quotation/
reliability engine are unchanged. No automatic repair or extra model pass was added.
