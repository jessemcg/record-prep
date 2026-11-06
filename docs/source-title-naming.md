# Profile-controlled source-title naming

Dependency **1.13.0** uses naming resource **5**, with content schema **10** and
`profile_api: 1` unchanged. The application capability is practice-neutral and
available on Report Names and Form Names cards in any profile.

## Selection and display name are separate

Each naming card has a **Naming approach**:

- **Fixed name** (default): match the description and return the exact catalog name.
- **Source title**: first match the description, then return the document's own
  cover/first-page title. The card's name is the fallback only when eligibility is
  clear but the title is absent/unreadable. Unknown eligibility is not a fallback:
  it remains unnamed and does not enter selected-document TOCs/summaries.

The model preserves wording and meaningful qualifiers, joins wrapped title lines,
and does not invent a title from hearing type, case caption, agency identity,
narrative references or an attachment list. Source-title mode does not waive a
form description's heading/code requirements. No list of title aliases is needed.

Examples of profile-owned selection: child welfare agency reports in dependency;
court-appointed investigator reports in probate; custody evaluator reports in
family law; retained expert reports in civil litigation. The application contains
no specialty test. The bundled Dependency entry selects agency reports but now
returns titles such as Memorandum, Status Review Report, or Last Minute Information
for the Court. Child Welfare Agency Report is only its missing-title fallback.
Its six fixed-name form cards and report-date sentence are unchanged.

## Storage and runtime contract

Naming v5 retains `reports`/`forms` cards with stable `id`, `name`, and `guidance`.
Optional `naming_mode` is `fixed` or `source_title`; absence means fixed. Naming
v1–v4, exact historical adapters and accepted snapshots remain unchanged. Version4
rejects the new field; unknown modes/versions fail validation. Content schemas7/8
still require naming4. Explicitly selecting Source title upgrades the draft naming
resource to5; switching back does not rewrite other cards or stored revisions.

A kind with at least one source-title rule uses `name`, optional report `date`,
and `rule_id` response strings. Rule IDs match stable catalog IDs, not document
names. Mixed catalogs retain exact-name checking for fixed rules. Unknown/missing
rule IDs cannot admit arbitrary titles; valid source-rule matches accept bounded
single-line source titles. A valid source-rule match plus an explicitly empty
name selects the configured fallback. Malformed names do not silently become
fallbacks. Unresolved names retain independently usable dates. Model interpretation
of eligibility/title is not independently proven by these structural checks.

All-fixed catalogs keep their previous prompt bytes, response keys and normalized
behavior, including when stored as naming5. Naming instructions and literal rule
content enter Names fingerprints; Basic/Advanced/Dates remain unchanged. Runtime,
preview and draft/template inspection share builders. No new model pass or semantic
validation gate was added. Existing stage-local input/publication guards remain.

Names stores the actual title in `name` and the selected rule in `naming_rule_id`.
TOC, boundaries, report work items and source maps consume the stored name; separate
same-name/date starts remain separate. Agent correction follows the same rule
contract, can add/correct source titles with `naming_rule_id`, and removes that
metadata when removing a name/start. Inapplicable proposals remain advisory and do
not discard useful corrections on other pages. Historical saved rows are not
revalidated or rewritten just to add rule IDs.

Focus receives only the byte-identical shared profile validator update and
compatibility tests. Its research method and presentation are unchanged; naming
metadata never becomes research instruction authority. No launchers, dependencies,
private configuration or case files are changed.

## Adoption

Restart normally when convenient; no application was forcibly restarted. Existing
personal profiles retain their naming behavior until explicitly edited/saved.
Choose Source title for the desired card and describe eligibility, keeping its name
as the fallback. For the bundled Dependency update, Reset to bundled → Reset and
Save replaces **all profile guidance**, not only naming; edit just the report card
instead if preserving other customizations. Saving never processes a case.

With complete report-start checks, explicitly run Names → Correct classification
with agent, then desired TOC/boundary/summary work to regenerate titles. Existing
outputs and completion badges remain untouched until deliberate processing. If a
report start was missed upstream, changing naming alone cannot recover it; use
appropriate Advanced/Basic work or the classification review. New model work can
incur charges.

## Validation limits

Tests use fictional sources, temporary settings/stores, and offline scripted
providers. They establish contract delivery, eligibility-ID validation, source-title
propagation, preservation and UI behavior—not live image-model accuracy. No real
case processing, OCR, paid model calls or private profile migrations are performed.

### Completed checks (2026-11-06, current Work computer)

- RecordPrep full suite: **929 run, 921 passed, 8 skipped**. New practice-neutral
  tests cover mixed fixed/source rules for reports and forms, unknown rules,
  missing-title fallback, malformed responses, legacy fixed prompt-byte preservation,
  mode-specific freshness, preview parity and partial agent correction including
  accurate audit of removed eligibility metadata.
- Twenty-one fictional image/pipeline scenarios verify actual source-title/fallback
  propagation into Names, TOC and boundaries; unrelated sources stay preserved,
  and adjacent same-name/date memoranda retain independent ranges.
- Fatal-critical synthetic GTK acceptance: fixed/source choices for report/form
  cards, Save/Undo/Reset and inspector/runtime composition all pass. Native desktop
  screenshot confirms Source title selected on the single agency-report card in a
  separate synthetic instance. That process was closed, not the maintained app.
- Focus full suite: **860 passed, 16 skipped, 11 subtests passed**, eight existing
  deprecation warnings. Shared profile validator/artifact byte parity passes.
- Sequential resource validation, skill validation, Python compilation and diff
  whitespace checks pass. No dependency, launcher or keyboard-mapping changes.

Evidence lives in the disposable `/tmp/recordprep-agency-report.lM3snd` workspace;
source/environment and HOME/XDG are isolated. RecordPrep tests use per-test umask077
except the existing explicit0755 rejection fixture (022); Focus uses022. Early
failures were stale title-catalog expectations/historical fixture construction or
harness settings, corrected without weakening production validation. Live model
quality and private-record regeneration remain untested, not implied by these checks.
