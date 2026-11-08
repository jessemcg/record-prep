# Longer, distinctive quotation anchors

## Policy and rationale

Hearing, report and motion-paper digest extraction, with or without a profile,
recommends **6–12 words**, **usually 8–10**. Choose the shortest natural, continuous,
verbatim phrase in that range that distinguishes the summarized substantive action,
condition, reason or disputed assertion. Prefer substantive wording to stock courtroom
language, routine appearances, generic names/dates and boilerplate; never add incidental
identifiers for uniqueness. Preserve negation, qualifications, attribution and the
quotation's declared source page. No padding, stitched fragments, ellipses, truncation,
rewriting, increased frequency or quote-per-paragraph requirement. Paraphrase when no
useful anchor exists. Useful outliers survive with sanitized advisory warnings only.

This is a practical starting range, **not a statistically established optimum**.
Unchanged Focus searches an ordered phrase with case/typography/OCR-spacing tolerance,
across the record, initially choosing the earliest match. It does not navigate using
the quotation's stored source page/offset. Length alone cannot make boilerplate unique;
extraction sees the current document, not the whole record. Repeated source passages
can still yield multiple matches. No common-word blacklist, uniqueness scan, fuzzy
matcher, gate, mandatory repair or additional paid pass has been added.

`tests/fixtures/summary_quote_navigation.json` preserves a fictional counterexample:

| Anchor | Words | Matching synthetic pages |
|---|---:|---|
| The court ordered supervised visitation | 5 | 1, 2, 3 |
| supervised visitation at the community center every Saturday | 8 | 2 |
| The court finds that notice has been given as required by law | 12 | 1, 2 |

These are controlled examples, not real-record accuracy measurements or evidence of
improved model judgment. No paid model evaluation or real-case regeneration was run.

## Implementation and compatibility

- Import-light `summary_quote_policy.py` owns recommended/preferred bounds and complete
  extraction guidance. Profile, unassigned and fixed Request/Reasons motion guidance
  use the same Python text. Extraction skills, profile template and registered tool
  descriptions reinforce it. Tool names, schemas, scope, submission and termination
  behavior are unchanged. The offline collector regenerated `prompt-tools.json`.
- `quote_convention_flags()` retains its signature, sanitized code format and normalized
  whitespace counting (apostrophes and hyphenated compounds remain single words).
  Inclusive 6–12 bounds only change advisory length diagnostics. No quote/evidence
  rewriting, clipping, rejection or repair request occurs.
- Previous active hearing/report defaults are registered as historical built-ins;
  every older literal remains intact. Known saved built-ins resolve read-only to the
  new contract without contradictory custom reattachment. Genuine custom prose remains
  byte-preserved and subordinate. No private configuration/profile/output migration.
- Extraction contract **5** and prompt/resource hashes honestly stale old extraction
  checkpoints. Current rows reuse normally. The shared extraction extension is also
  a synthesis dependency: its changed description legitimately changes all three
  dependent synthesis fingerprints. This is not a synthesis-only quote-bank upgrade.
- Artifact/profile schemas, placeholders, source verification/ambiguity handling,
  offsets/hashes/IDs, punctuation and capitalization safeguards, best-effort
  publication, synthesis instructions, renderer identities and edition formats are
  unchanged. `profile_contract.py` and `profile_artifacts.py` remain untouched; no
  Focus mirror update is needed. Minutes, upstream instruction text, presence badges
  and Resume behavior are unchanged.
- Freshness investigation found the existing conservative motion-organization
  fingerprint hashes the **whole `motion_guidance.py` module**. Although its organization
  contract/instructions are byte-identical, a separately requested organization run can
  re-review rather than reuse its previous receipt. This existing broad dependency is
  not masked or redesigned here; it never forces an organization run or rewrites groups.
  Minute, participant and overview identities are unchanged in before/after captures.

## Explicit adoption

For an existing case, explicitly run the affected **Create hearing summaries**,
**Create report summaries**, or **Create motion summaries**, including extraction
under the new policy, then **Build summary editions**. Rebuilding editions alone—or
running synthesis on an old digest—cannot lengthen its stored quotes. Refresh dependent
overview/source-map output if appropriate after new summaries. Generation may incur
normal provider costs and is not part of implementation acceptance. No profile reset,
settings save, upstream reset or automatic startup/install regeneration is required.
Historical output remains readable without being relabeled current.

## Regression and local acceptance

Validation uses disposable source/environment copies selected through the absolute
`UvEnvironments/project-env` helper with paired overrides; synthetic HOME/XDG/config/
case state, disabled metrics, fake/offline providers and no real credentials/materials.

- Full documented unittest discovery: **995 tests, 987 passed, 8 skipped**.
- Focused summary/motion/quote-display/edition/prompt/report/hearing/settings checks:
  **303 tests, 302 passed, 1 skipped**, including actual staged/expanded Pi
  launches and registered tool-description/inspector parity for all three extraction
  kinds in both assignment modes, historical/default/custom compatibility, boundary
  diagnostics at 5/6/8/10/12/13, short-quote readers/fallbacks, capitalization and
  source evidence preservation, old/current checkpoint behavior, and editions.
- Natural 6/8/12-word edition regressions cover line wrapping and a real paper-page
  split in hearing/report/motion editions. Every fragment retains the complete search
  phrase and exact display offsets; rendering/coverage validation remains authoritative.
- Before/after captures preserve all preexisting historical literal hashes and prior
  active-default hashes, plus the frozen profile extraction literal. No frozen prompt
  fixtures or historical validation reports were rewritten. The current synthetic
  `docs/prompt-examples/hearings-extract.txt` was refreshed through `inspect_prompt()`.
- Production GTK **About summaries → View full prompts…** acceptance checks all three
  extraction views, the complete policy/tool description, clean packaged audit, read-only
  text and unchanged synthetic settings/profile/case bytes/mtime. Native AT-SPI and
  screenshots show the staged range and registered tool description without warnings.
- A separately isolated **unchanged Focus** loads the newly generated synthetic digests,
  summaries and two-page editions. Its production hit-test/click-handler path searches
  the full 8-word phrase and selects source page 2; the second-page `required by law`
  fragment searches the entire 12-word quotation and returns pages 1 and 2, initially
  selecting page 1. Screenshots confirm readable links and the resulting source highlight.
  Click-handler injection establishes this end-to-end application path; physical/native
  pointer delivery was not certified (local uinput/portal/XTest attempts did not produce
  an observed GTK click). This limitation is not hidden by changing Focus or its matcher.

Reproducible inspector/fixture builder: `tests/acceptance_summary_quotes_ui.py` (optional
`QUOTE_UI_HOLD=1`). Open its generated synthetic bundle in a separately isolated Focus;
never use a real case to test this change. Resource validation, changed-skill validation,
Python compilation and the offline registered-tool `--check` complete the checks.
No maintained application restart, deployment, commit, push, provider call, private
settings/case changes or other-computer access is part of this work.

Source-aware navigation is the strongest deferred alternative: verified provenance
would need safe handling of absent, ambiguous or stale locations. Document-scoped
search or separate short display/long search context also needs a separate design.
None is implemented here.
