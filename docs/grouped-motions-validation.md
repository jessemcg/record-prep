# Grouped-motion validation

## Scope and environment

Implemented locally on Home only. Validation uses disposable checkouts under
`/tmp/recordprep-grouped-motions.sao7ds93`, explicit UvEnvironments `--project` /
`--environment` selection for each callee, isolated HOME/XDG/Pi preferences, disabled
metrics and synthetic sources. No real bundles/settings, credentials, paid provider
calls, production restarts/deployment, dependencies, launchers or other computers.
Existing summary-resilience changes are retained, not replaced by quality gates.
Changes remain uncommitted; publication was not performed.

## Automated checks

- **RecordPrep:** full unittest discovery, **969 tests**, **961 passed / 8 skipped**,
  105.174 seconds (`rp-full-verified.log`).
- **Focus:** full pytest, **892 passed / 16 skipped**, plus **11 passing subtests**,
  13.12 seconds (`focus-full-verified.log`).
- New grouping suite has **22 tests**, including subcases: four physical papers /
  nine pages → one entry; exact nonadjacent/pre-lead components; separate motion,
  opposition and reply support; malformed/duplicate partial proposals; singleton
  coverage; source/Stop/publication failures; locks; unsafe paths; corrupt stores;
  stale fallback; zero calls; unchanged reuse; historical Resume adoption; title
  fallback without an editorial length gate; fixed guidance despite legacy canaries;
  schema-12 ownership; long page IDs; Markdown3/row4/metadata6 round trips; digest and
  final second-file rollback with original bytes/mtime; and bounded impossible ranges.
- A fake-Pi native runner executes one organization child and reuses unchanged output
  without another call. A fake-Pi summary runner executes one grouped extraction and
  one synthesis, then reuses both. These exercise real orchestration/publication.
- Actual installed Pi SDK expands the real organization skill/launch, serves a staged
  source read, blocks canonical reads, permits the private candidate write and blocks
  canonical writes. The actual TypeScript guard also rejects shell/other tools,
  traversal, unstaged files, symlinks, hardlinks and invalid access specs. No network
  or model provider is used. Existing full SDK summary delivery/schema tests pass.
- Focus schema-12 tests preserve historical schema 11, reject reintroduced topics,
  validate physical/logical membership and descriptive aliases/counts, reject corrupt
  descriptors and read schema-6 empty/nonempty finals without writes. Pure metadata
  validation does not expand enormous page ranges.
- Resource validation, changed skill validators, offline registered-tool audit,
  compilation, shared-contract byte parity, source/test-copy parity and diff checks
  pass. Historical six-topic motion data remains available to old readers.

## Real application mechanics and desktop observation

`prepare_motion_acceptance.py --grouped` produces original synthetic files through
RecordPrep's actual boundary/digest/final/edition/source-map builders. Five physical
papers form three entries; the motion's lead is page 5, with support on 1–2 and 7–8,
excluding the intervening opposition on 3–4. The reply remains separate on 9–10.
Physical documents, aliases, exact member context, manifest coverage and counts are
validated by both applications.

`acceptance_grouped_motions_ui.py` checks actual RecordPrep widgets and the actual
Build TOC worker, read-only View grouping, retained Motion Names plus only two editable
summary-topic pages, and all three fixed motion prompt inspectors. A malformed
unrelated naming draft neither blocks nor contaminates those views. Inspection does
not save settings or rewrite the bundle. Local GTK snapshots cover grouping and fixed
prompts. Native Linux Computer Use observed the synthetic prompt window, captured it,
and opened its task selector, showing organization/digest/narrative choices. The
bounded synthetic process closed itself; a later click was refused after it exited,
so no action reached another application.

Focus's actual GTK acceptance, with fatal criticals enabled, loads that producer's
edition, finds the heading link to lead page **5** rather than supporting page **1**,
activates it, searches the supporting-paper quotation on physical page **8**, and
preserves that page's physical document identity plus logical context. It also checks
summary visibility, direct routing, unavailable-final fallback and read-only reload.
Rendered light/dark narrow and wide snapshots passed and were reviewed
(`/tmp/focus-motions-acceptance-4l_wwywe`). New grouping did not redesign pagination
controls or change the fixed Letter layout.

Earlier desktop/frame availability was temporarily incomplete: a viewport test also
failed on untouched HEAD, and early snapshot attempts returned no rendered node.
The final full suites passed unchanged, and later GTK/native observation succeeded.
Do not interpret those intermediate infrastructure failures as waived regressions.

## Packaging and boundaries

Offline wheel/sdist builds use the cached Hatchling backend through each disposable
callee environment. Every payload file is compared byte-for-byte with the checkout;
new Python modules, bundled schema-12 profile, audit, native guard/skill and updated
summary skills are covered. Payloads: RecordPrep **101 wheel / 241 sdist** files;
Focus **41 wheel / 214 sdist** files. The retired bundled `motions.json` is absent. Source
installations retain `.pi` in the sdist; a wheel alone is not a new standalone Pi
resource deployment contract. Both shared modules remain byte-identical with Focus.

These checks establish data flow, permissions, compatibility, rendering/navigation
and best-effort failure handling. **They do not establish live-model relationship,
editorial brevity or legal-summary quality.** There was no live semantic acceptance,
external legal research or real-case rerun. Adoption is explicit as documented in
[motions workflow](motions-workflow.md). If publication is separately authorized,
compatible Focus must precede RecordPrep, in separate commits.
