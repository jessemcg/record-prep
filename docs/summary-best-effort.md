# Best-effort summary output

Knowledge work should remain useful when imperfect. A model's formatting, coverage
or quote-matching problem is not an all-or-nothing publication gate, and does not
require another paid repair/validation pass.

## Motion failure fixed (2026-11-07)

The extraction normalizer correctly generated `motion:0098/requested_relief/1`, but
the Markdown serializer accepted only `hearing:` and `report:` quote IDs. The
heading parser had the same omission, so merely widening the quote expression
would have failed again when synthesis reloaded the published digest. This was
RecordPrep rejecting its own output, not a model-quality problem.

Both expressions now derive their supported prefixes from `SUMMARY_ITEM_PREFIXES`.
The numeric portion permits four or more digits, matching Python's minimum-width
page formatting. Canonical source/metadata round trips remain checked; no schemas,
prompts, extraction fingerprints, profile resources or historical output are migrated.

## Advisory handling

Applies to hearing, report and motion summary children:

- Existing extraction normalization retains useful digest prose, injects the
  runner's identity/quote IDs, ignores unknown categories, fills missing categories
  and retains unmatched in-range quotations as unverified. It never requires every
  category or quotation to be perfect before continuing other documents.
- After a **successful** child exit, missing, invalid-JSON/invalid-UTF-8 or non-object
  candidates produce sanitized warnings instead of stopping the stage. Unusable
  extraction becomes an honestly flagged all-null row; it does not invent findings
  or cancel other papers. Unavailable synthesis uses the saved category digests.
- A string-valued synthesis paragraph field is preserved as one paragraph. Null,
  numeric and other malformed paragraph fields use digest fallback, without
  discarding usable sections for other papers. Existing unknown-quote fallback
  preserves the digest rather than silently deleting quoted words from a sentence.
- Synthesis candidate and coverage warning codes are retained in final metadata as
  well as reported in the terminal. Extraction all-null warnings remain in row
  metadata. These are review information, not failure gates or semantic proof.
- No extra model call, retry loop, prose filter, content quota or quality gate is
  added. A completely unusable extraction cannot supply a substantive summary;
  its heading and private warning remain while useful papers are published.

Stop, genuine child execution/source failures, unreadable filesystem state,
changed inputs, damaged generated stores and unsafe publication remain separate
safeguards. They are not editorial-perfection tests. Existing execution-failure,
Stop and preservation regressions remain unchanged.

Retry **Create motion summaries** on an existing bundle. No source reset, profile
adoption, upstream rerun, private-output rewrite or settings migration is needed
for this fix. Any saved compatible extraction checkpoints remain reusable.

## Validation

Current home computer only; disposable source/environment:
`/tmp/recordprep-useful-summaries.FquKfl/{RecordPrep,env}`. Explicit absolute
UvEnvironments helper selection, synthetic HOME/XDG, metrics disabled, fictional
case data and fake/offline providers. No real case/settings reads or writes, paid
calls, maintained-app restart, deployment, other-computer actions or commits.

- Reproduced the exact quote-ID failure before the fix (`before.log`).
- Full unittest regression: **947 run, 939 passed, 8 skipped**, 101.123 s
  (`full-final.log`). The first disposable run had one test-harness error because
  the archive lacked `.git`; initializing only that temporary repository resolved
  the Git-inspection prerequisite without changing application code.
- New regression file `tests/test_motion_summary_resilience.py`: four independent
  nonempty motion papers, canonical quotes, complete final headings, disk reload,
  profile/unassigned round trips, unverified quotes, unknown/missing categories,
  malformed paragraph fields, missing/malformed/non-object child output, digest
  fallback, persisted warnings and exactly four extraction calls plus one synthesis
  (no repair call). All summary kinds also round-trip IDs beyond four digits.
- Existing Markdown escaping/round-trip test now covers **every** summary kind.
- Sequential resources, Python compilation and offline registered-tool audit PASS.
  The packaged audit updates only its runner source hash; tool definitions and
  model instructions are unchanged.

These tests establish mechanics and continuation, not live semantic model quality.
No GUI, entry-point, dependency, desktop launcher, XREMAP, shared Focus-module or
consumer-contract changes are involved.
