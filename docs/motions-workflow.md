# Motion papers and logical entries

Dependency **1.15.0**, content schema **12**, retains `profile_api: 1` and the
profile-owned `motion_naming` eligibility catalog. New profiles omit `motions`:
all new motion digests use the application's **Request** (`request`) and
**Reasons** (`reasons`) method, for assigned, historical, custom and unassigned work.
Schemas 1–11 and naming formats 1–5 remain readable. Opening settings never migrates
private profiles or bundles. Only explicit Create/Save/Reset publishes schema 12.
Historical motion topics/configuration prose stay at rest but supply no current
instructions, prompt inspection text or generation fingerprints. Hearing/report
topics and the fixed minute method are unchanged.

## Physical recognition stays separate

Basic recognizes motions/applications, oppositions, replies, supplemental briefs,
points and authorities and separately titled supporting declarations. Qualifying
standardized court request forms remain Forms. Standalone notices, service proofs,
court rulings/minute orders, neutral agency/court reports and reproduced exhibits
keep their classifications. Advocacy can qualify regardless of author; agency
authorship alone does not establish advocacy.

Advanced checks **every** motion page, recording `motion_first_page: yes/no`.
Names uses explicit starts and source-title eligibility, preserving actual titles,
amended/supplemental distinctions and filed/document/unknown date basis. A running
heading, date, counsel, page-number restart or adjacency alone proves neither a new
paper nor a relationship. Titles retain the existing 1,024-character structural
limit without truncation; this is not a short-title quota. Unknown eligibility stays
unnamed; an eligible but unreadable title can use its catalog fallback. Names and
Dates remain independently usable. Agent classification correction retains its
existing advisory review and raw-candidate safeguards.

`artifacts/motion_boundaries.json` remains an inventory of **physical**, contiguous
papers. IDs remain `motion:<source-start-page>` (at least four digits), independent
of ordinals. Unnamed starts terminate earlier papers; gaps/orphan bodies are never
silently appended. Individual names, dates, classifications and ranges are not
rewritten to implement grouping.

## Organize motion papers

The native **Organize motion papers** stage runs after final classification and
before Build TOC, using the shared Agent model/reasoning and its own canonical
skill/restricted tool guard. Python supplies the immutable inventory and exact
staged source files. The agent may propose relationships and concise entry names;
it cannot invent physical IDs/ranges, execute a shell or write canonical outputs.
**View grouping** is a read-only plain-text review of entries, members and findings.

`artifacts/motion_groups.json` schema 1 records the organization contract, inventory,
source/input fingerprints, model/resource identity, logical groups, findings and
honest coverage. Each group has the lead's existing ID, a separate lead-page
navigation anchor, exact ordered components, role, title, source-supported party,
purpose/date/date basis and optional relationships. Components need not be adjacent
and support can precede the lead. Never use an enclosing range as source scope.

A motion/application, opposition and reply remain **separate entries**, each with
its own explicitly linked support. A declaration, separate statement or memorandum
belongs with a lead only when the papers establish the relationship. Unlinked,
ambiguous or multiply assigned papers remain visible singletons with advisory notes.
Useful independent proposals survive malformed proposals; incomplete successful
output is not an all-or-nothing failure or a mandatory paid repair pass.

Short titles identify the filing/request: **Motion to compel police records**, not
“Mother to compel police records.” Keep the filing party in metadata and the opening
narrative. Preserve opposition/reply and consequential amended/supplemental qualifiers.
No regex renaming, silent truncation, word quota or numerical brevity validator.

The stage uses its own lock, private candidate, Stop handling, guarded source/model/
resource/selection/prior-output checks and atomic publication. Genuine failures,
unsafe paths, corrupt canonical stores, races or failed publication preserve prior
outputs. A successful child with unusable content yields flagged singleton coverage.
Unchanged current inputs reuse the saved result without a model call; checked zero
selection publishes an empty result without a model call.

## Summarization and navigation

Build TOC uses each current logical title and **lead anchor**, not the lowest member
page. Extraction reads exactly the selected components, integrating declaration
evidence into **Request / Reasons**, not an independent supporting-fact inventory.
The narrative answers **who wants what, and why**, distinguishing allegations,
arguments and requested relief from actual court findings; it does not infer a
later ruling or use external legal research. Motion, opposition and reply are never
collapsed into one narrative. Quote verification, hashes, overlap checks and
preflight payloads use exact member pages, excluding unrelated intervening pages.

New motion digests use Markdown format **3**, row schema **4**, digest/final metadata
schema **6**, fixed instruction-free application metadata, and exact member/anchor
metadata. Historical Markdown 1/2, row 2/3 and metadata remain readable with the
frozen historical six-topic catalog; old artifacts are never relabeled current.
Final output remains `summaries/motions_sum_<case>.txt`. Best-effort quote matching,
all-null handling, useful extraction retention and digest-prose synthesis fallback
remain authoritative: see [best-effort handling](summary-best-effort.md). There is no
mandatory repair/review pass or editorial quality gate.

Motion digest/final pairs are staged before replacement and ordinary second-file
replacement failures roll back the first, preserving prior bytes/mtime. This is not
a claim of crash-atomic multi-file transactions: canonical hashes detect interrupted
pairs. Existing Stop/source/store/publication safeguards remain separate from content
quality. Summary editions retain the fixed Letter layout and add validated heading
links to lead anchors; quote links still search physical source text.

Source-map `documents` stay physical. Current grouping adds descriptive aliases,
per-page logical context, optional `files.motion_groups`, and `counts.motion_entries`;
`counts.motions` remains the physical paper count. Published grouping omits runtime
input details. Focus reads the contracts/context without adopting preparation
instructions, changing research policy or requiring a profile.

## Historical bundles and explicit adoption

Missing grouping is supported singleton behavior. Readable stale grouping warns and
falls back to the current physical singleton inventory without rewriting the saved
artifact. Corrupt grouping is not silently treated as valid or absent. Badges and
Resume remain presence-based; changed settings alone do not trigger regeneration.
Already-prepared legacy bundles without grouping skip organization on automatic
Resume with an adoption message. Fresh pipelines include the new stage.

To adopt deliberately: run **Organize motion papers**, review grouping, then rebuild
TOC and explicitly create motion summaries. Refresh dependent editions/overview/map
as needed. No upstream source reset, private migration or automatic paid run occurs.
Historical missing motion preparation is not zero motions; explicit execution explains
the prerequisite. Checked-zero motion preparation uses zero organization, extraction
and synthesis model calls.

## Validation and publication

Use disposable checkouts/environments with isolated HOME/XDG/Pi state, synthetic
sources and offline/scripted providers. Select each callee with the absolute
UvEnvironments helper and explicit `--project` / `--environment`. Run RecordPrep's
full unittest and Focus's full pytest suites, actual SDK skill expansion and guard
checks, resources/skill/audit/package checks, shared-file parity and GTK acceptance.
Scripted results establish mechanics, not live editorial/grouping quality. See
[grouped-motion validation](grouped-motions-validation.md) for actual results.

No dependencies, entry points, launchers, deployed applications, private settings or
real bundles are changed. If publication is separately authorized, publish compatible
**Focus before RecordPrep**, in separate commits.
