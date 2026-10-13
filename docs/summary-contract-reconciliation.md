# Topic-guided summary contract reconciliation

## Preservation baseline

The behavioral baseline is RecordPrep commit `7921736`, immediately before
`2799a0d` introduced profile-driven preparation on 2026-10-11. Its complete-source
digest guidance and incremental narrative guidance are the reference, not older
windowed or quota-based prompts. No claim is made that a specific historical
user summary used this exact revision.

Current profile-bound prompts are composed in `recordprep/summary_profiles.py`.
The runner stages `.pi/resources/profile-summary-{extract,synthesize}.md`, the
shared system prompt, and the summary tool extension. The complete behavioral
instructions live in the runtime contract, not in hidden editable profile fields.

## Preserved behavior

- Each extraction agent reads one complete hearing or report, all supplied pages.
- Retain information whose omission would materially change understanding of the
  events, outcome, reasons, evidence, dispute, qualification or unresolved issue.
  Do not select only evidence supporting an already-known outcome; silence does
  not establish absence.
- Topics guide review; they do not require equal-length treatment or filled slots.
  Expand a digest for distinct material points, without word/sentence/paragraph
  quotas. Consolidate examples unless their differences, chronology, credibility
  or legal significance matter. Keep each development in its best topic once.
- Capture relevant dates and temporal qualifications. Extraction cannot assume a
  fact is covered elsewhere. Reports record current/recent developments; synthesis
  decides what is genuinely new relative to earlier reports.
- Digest prose is paraphrase; the separate evidence bank carries continuous,
  verbatim, source-page-bound quote anchors. Empty topics are exactly null.
- Write one cohesive narrative section per hearing/report. Lead with its material
  outcome, development or issue and explain reasons and evidence. Integrate topics
  into substantive paragraphs, not topic lists. Complexity determines detail.
- Weave exact quote-ID placeholders naturally into prose. Digest context controls
  meaning; quotes are not independent support for inferred propositions. Preserve
  attribution, denials, uncertainty and dates. Do not shorten stored quotations,
  invent quotes, duplicate paraphrase-plus-quote text, or leak technical metadata.
- Correct invalid quotation submissions. Work incrementally, maintain scratchpad
  orientation/progress, reread digests or submitted sections after compaction, and
  revise earlier sections when later context requires it without changing chronology.
- Reports distinguish event dates from reporting dates, preserve disputed/newly
  significant information and necessary earlier context, and avoid copied history
  and previously used evidence quotes. This is not a changes-only account.
- Existing source authority, Python publication, warning/fallback, model selection,
  no-source-windowing, direct-source and minute-order contracts remain in place.

## Intentional differences from the baseline

1. **Specialty-neutral language.** The fixed method does not mention juvenile
   dependency, parents as the only parties, or a fixed set of substantive topics.
   User topic catalogs supply the specialty focus. Hearing attribution rules still
   distinguish sworn testimony, unsworn colloquy and representation from personal
   appearance. No deleted extra-instruction prose was moved into the core contract.
2. **Topic-only customization.** Summaries contains exactly Hearing digest topics,
   Report digest topics and Minute orders. The four extra digest/narrative fields
   are absent from bundled profiles and content schema 3, and old config prompts
   are not imported into new profiles. Historical content schemas 1/2 remain
   readable, with their bytes intact, but those four fields never enter compiled
   prompts or freshness components. Explicit GUI edit/create produces a schema-3
   draft; only the application's normal Save flow can publish a new revision.
3. **Approved proposal-cutoff removal stays.** Commit `215eec5` removed the formal
   proposal delimiter. Read the whole report, retain material recommendations and
   requested relief wherever located, and distinguish proposed relief from actual
   orders. Do not restore the old heading-based exclusion.
4. **Remove the tool-description paragraph bias.** The extraction tool formerly
   illustrated its text field as “one concise synthesized digest paragraph.” It
   now explicitly allows multiple paragraphs for distinct material points, with
   no quota, consistent with the baseline's actual instructions.
5. **Explicit sparse/dense and not-changes-only wording.** These clarify the
   baseline's adaptive detail and contextual narrative rules; they do not impose
   a new substantive selection criterion.
6. **Single behavioral authority for profile-bound work.** Detailed runtime
   contracts plus thin skills replace duplicated full prose in both locations.
   Tool descriptions retain the exact protocol. Unassigned compatibility work
   retains its legacy resolver; schema-3 profiles never acquire old custom prompts.

## Freshness and preservation

Core and topic bytes are fingerprinted. Restoring digest instructions makes
profile-bound extraction regeneration-pending; changed digests and synthesis
contracts in turn stale narratives. The shared tool-extension change can also
stale legacy summary generations. Opening settings never regenerates anything.
Old digests, narratives, accepted profiles and case selections stay untouched until
an explicit application action. Reading old revisions does not rewrite them.

This change does not preserve caches by falsely claiming the generation contract
is unchanged. Do not restore old extra fields or copy private guidance into source
files to keep caches current.

## Validation and limits

Offline checks cover the restored rule families, sparse two-page and dense
three-page complete-source inputs, multi-paragraph digest preservation, removal
of all four fields from new profiles, rejection of those fields by schema 3,
old-revision readability and prompt/fingerprint isolation, category-local changes,
classification schema-3 routing, and the three-entry GTK navigation.

These checks establish behavioral prompt coverage and pipeline correctness, not
model-output quality. No real records, private profile files, or credentials are
changed by the tests, and no paid calls are part of the test suite.

A quality comparison should use the same model/provider/reasoning and identical
synthetic complete hearings/reports for both contracts. Use the pre-profile
contract with only the independently approved cutoff removal applied as the
control; hold categories and source pages constant. Evaluate extraction and
synthesis separately: retain material points and qualifications, avoid invented
facts, preserve dates/attribution, integrate quotations, and avoid repetitive
history. Include both sparse and dense inputs and a multi-report chronology with
unchanged but important facts. Run locally only. Do not infer improved prose from
unit tests, or use private cases or remote computers as an implicit requirement.
