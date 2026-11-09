# Targeted recent-change cleanup — 2026-11-09

Scope: reviewed HEAD `7ce9652`, implemented locally on the work computer. This is
contract/runtime cleanup, not a certification of generated legal accuracy or an
application-wide defect review.

## Confirmed changes

- Optional motion-date recovery accepts strings only before calendar parsing.
  Missing/null/numeric/Boolean/list/object/invalid-string/impossible-calendar values
  retain the original lead date/basis and yield a fixed advisory finding when
  recovery was attempted. Known filed dates are never overwritten. Membership,
  anchors, independent proposals and review-coverage accounting remain intact.
- Behavioral tests exercise normalization **and guarded organization publication**,
  including unknown dates, document-to-filed upgrades, leap dates, mixed groups,
  immutable inventories/source bytes and honestly incomplete coverage. Existing
  Stop, changed-source, corrupt-store, unsafe-path and publication-failure tests pass.
- Current hearing synthesis expectations now reflect the reviewed quotation
  integration bytes, without changing frozen fixtures or weakening external/checkout
  identity parity and unrelated-stage checks. Existing hearing editorial tests retain
  proposition-carrying quotations, examples and stage-isolation assertions.
- README installation testing checks the title, intended icon and accessible text,
  not incidental pixel width. Installer/uninstaller public-surface checks remain.
  README itself is unchanged.
- Summary composition now returns fixed hearing/motion methods before report setup,
  with a direct report path and no empty defaults/dead motion metadata branch.
  Public signatures, schemas and instruction contracts are unchanged.
- Current user/maintainer guidance names schema 14 / API 1, Dependency 1.17.0 and
  Criminal 1.0.0, and the three editable destinations: Report Names, Form Names,
  Report digest topics. AGENTS.md replaces overlapping historical overrides with
  current invariants and detailed-document links. Dated validation results remain
  historical; schema-transition descriptions are explicitly qualified.

## Validation

Disposable tracked source: `/tmp/recordprep-cleanup-9qsYFV/RecordPrep`; separate
Python 3.13 environment, HOME/XDG/Pi state, synthetic records/offline providers and
run metrics disabled. The checkout basename and local Git index are retained for
repository-aware tests. No production environment provisioning was used.

| Check | Result |
| --- | --- |
| Baseline full discovery | 1,018 run; five expected failure reports across four methods; eight skips |
| Final full discovery | **1,020 run; 1,012 passed; eight skipped; no failures/errors** |
| Motion grouping module | 28 passed, including new publication/date matrix |
| External settings module | 8 passed |
| Summary before/after matrix | Byte-identical prompts, draft guidance, inspector text, skills, catalogs, metadata, provenance and fingerprints |
| Native resource validator / Python compilation / whitespace | Passed |
| Packaged prompt-tool audit (`--check`) | Passed; no regeneration or audit-file change |
| Synthetic native GTK bundled-profile harness | Passed for both bundles, three destinations, fixed hearing/motion/minute inspection, naming parity, Save/Reset/history |

The equivalence matrix covers Dependency, Criminal, a synthetic custom report profile,
retired General, synthetic historical schemas 1–10/13/14, and unassigned runtime
configuration, across hearing/report/motion extraction and synthesis. Both bundled
resource inventories/hashes are unchanged. GTK acceptance confirms Dependency is
initial/default creation base and both bundles remain available; it uses temporary
stores only, never the user's profile. Existing compatibility/ownership/Criminal/
prompt-inspection/public-installation tests also pass in full discovery.

All eight skips are explicit:

- Three shared model-settings tests belong to other owners or an unsupported
  inherited model slot (BillingHelper medium default, Focus first-load seeding,
  inherited model-slot round trip).
- Three optional installed-offline-SDK fixtures are unavailable in this isolated
  checkout (overview native, participant native, quote-display SDK).
- Two optional sibling PiRunMetrics checks are unavailable (launch-policy behavior
  and its SDK harness). Run collection remains disabled.

Initial Computer Use attempts were blocked by local binary/catalog mismatch
(0.7.49 versus 0.7.48). A later user-requested retry succeeded after the tool became
available; no desktop setup was changed by this review. Screenshots and accessibility
observation of the isolated Criminal editor confirmed Report Names (Probation Report),
Form Names (twelve cards) and Report digest topics (nine cards), with only those three
editable destinations. About summaries expands naturally and describes fixed hearing,
motion and minute methods. The actual full-prompts window displayed Hearing narrative,
Motion narrative and Minute-order summary with the expected canonical staged skills
and no template/current-draft selector for those fixed methods. Read-only prompt text
and search were present. Desktop input initially navigated/opened the inspector;
because focus was shifting, a disposable-only harness callback selected the three
fixed inspection modes before screenshot observation. Both bundled profiles still
passed the native GTK harness (with nonfatal GDK swapchain warnings); visual follow-up
covered Criminal specifically, not an exhaustive UI review. All synthetic windows
were closed afterward; the user's running RecordPrep/settings/case remained untouched.

Evidence: `/tmp/recordprep-cleanup-9qsYFV/validation/`, including
`baseline-full.log`, `final-full.log`, `motion-tests.log`, `external.log`,
`before-expanded.json`, `after-expanded.json`, `resources.log`, `compile.log`,
`audit.log`, and `gtk.log`. The successful desktop follow-up also has
`gtk-observation.log`, `gtk-topics-observation.log` and `gtk-fixed-observation.log`;
screenshot/accessibility evidence is in the associated Pi tool-call history. These
contain synthetic state only.

## Preservation and limits

No hearing skill/editorial instruction changes, profile-resource changes, frozen
fixture edits, shared Focus contract edits, dependencies, CLI/interfaces, launcher
changes, migrations or schema bumps. No real-case generation, paid evaluation,
private settings/artifact modification, running-app restart, deployment, commit or
push. The normalizer's existing conservative implementation fingerprint changes;
an explicitly requested organization run can re-review inputs. Old fingerprints
were not blessed and presence-based badges/Resume were not altered.

Offline tests do not establish recognition quality, legal/editorial completeness,
quote usefulness or accuracy on real records. Active hearing instruction duplication
and substantive Criminal-profile evaluation remain deferred, as requested.
