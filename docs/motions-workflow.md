# Motions workflow (content schema 11 / profile API 1)

Dependency 1.14.0 adds separate `motion_naming` and `motions` JSON resources.
The existing `naming` formats 1–5 and all content schemas 1–10 remain readable
without mutation. Neither a code update nor opening an old assigned profile adopts
motion naming. Explicit Create/Save upgrades the draft with **empty** Motion Names;
choose/edit a motion rule or explicitly adopt/reset to the new bundle to select papers.
The unassigned compatibility path has a practice-neutral Motion Paper source-title rule.
There is no Focus preparation-profile dependency.

## Recognition and document identity

- Basic recognizes free-form motions/applications, oppositions, replies, supplemental
  briefs, points and authorities and separately titled supporting declarations.
- Standardized qualifying court request forms remain Forms. Standalone hearing
  notices, service proofs, court rulings/minute orders, neutral agency/court reports
  and separately reproduced exhibits retain their existing classifications.
  Agency-authored advocacy can be a motion; agency authorship alone is insufficient.
- Advanced runs `first_motion` on **every** CT motion page, saving
  `motion_first_page: yes/no` and `CT_motion_first_page` for positive starts.
  A running title/internal heading is not a new paper. No run-start inference,
  proximity-based family grouping or merger of repeated titles/dates is allowed.
- Names runs on explicit starts only. Source title preserves party, requested-relief,
  opposition/reply and amended/supplemental qualifiers, joining wrapped lines.
  Motion titles support 1,024 characters without silent truncation; other kinds'
  limits are unchanged. A catalog name is a fallback only for clearly eligible
  source-title papers with absent/unreadable titles. Unresolved eligibility stays unnamed.
- Date preference: filed/e-filed, then explicit document/signature date. Never use
  hearing, service, printing or merely mentioned dates. Store `date_basis` as
  `filed`, `document` or `unknown`; uncertain dates remain blank. Naming and date
  failures are independent. The extraction prompt and inspector use the same contract.
- Classification correction can change motion structure/naming; its retained raw
  candidate/read audit and advisory policy also apply. Correcting a page away from
  motion removes stale motion-specific fields.

## Selection and outputs

TOC has a canonical `MOTIONS` heading. Each named explicit start is an independent
selected paper. An unnamed start still terminates the preceding paper; unnamed
papers, orphan bodies and gaps remain searchable source, never silently appended.
Find boundaries publishes `artifacts/motion_boundaries.json` with `motion_id:
"motion:0001"` based on the zero-padded **source start page**, not ordinal position.
It retains title, date, date basis, naming rule and source range. Correct boundaries
accepts motion-only selections and preserves missing historical motion artifacts.

Create motion summaries (`create_motion_summaries`, kind `motions`) sits between
report and minute summaries. Extraction receives each paper's entire selected range
in one payload, without participant requirements. Synthesis treats motion,
opposition, reply and each supporting paper independently, distinguishes allegations,
arguments and requests from court findings, and reports outcome only when supported.
It uses existing quote/provenance validation and restricted summary tools; no new
shell/network capability or word/item target is introduced.

Final output: `summaries/motions_sum_<case>.txt` plus canonical digest/cache and final
metadata companions. A validated empty motion-boundary list publishes the standard
zero-item final and metadata with **zero model calls**. A missing boundary file is
missing preparation, not zero motions: explicit execution explains the prerequisite;
automatic Resume skips the new stage with an honest message. Find boundaries does
not manufacture an empty motion artifact from historical absence. A current Advanced
checkpoint (including its output hashes) can prove checked zero-motion coverage.
Badges/Resume remain presence-based, separate from execution-time validation.

Available motion finals join paginated PDF/page-map editions, overview inputs and
fingerprints, optional manifest keys `motion_boundaries`, `summarized_motions`,
`summarized_motions_pdf` and `summarized_motions_pages`, publication input digests and
source-map aliases/counts. A legacy bundle lacking preparation has no motion count
rather than a fabricated zero. Source maps preserve stable IDs, ranges and date basis;
Focus can navigate titles, quotes and mapped source pages without any profile.

## Offline validation and release

Use disposable source copies and machine-local environments selected with the absolute
UvEnvironments helper's explicit `--project` / `--environment`. Run full regressions,
synthetic production-worker/GTK/cross-repository acceptance, complete skill expansion,
offline registered-tool audit, wheel/sdist payload checks and byte parity for **both**
`profile_contract.py` and `profile_artifacts.py`. Tests must not read private settings
or case data or call providers. There are no dependency, entry-point, launcher,
deployment or migration changes. If publication is separately authorized, publish
compatible **Focus before RecordPrep**. See [the validation report](motions-validation.md) for actual results
and local desktop limitations; scripted model responses do not prove visual/semantic
recognition quality.
