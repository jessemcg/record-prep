# Summary backtick formatting — 2026-11-10

The report synthesis skill showed a preferred prose sentence with a backtick-wrapped
quote placeholder. The shared renderer expanded the placeholder but preserved those
backticks; edition rendering removed double quote delimiters, leaving the backticks
visible around otherwise valid searchable quotation spans.

## Fix and scope

- Report prose examples and placeholder instructions now use bare placeholders and
  explicitly disallow backticks/Markdown code formatting in narrative output.
- `render_section_paragraphs` strips model-authored backticks before existing
  double-quote-wrapper cleanup and evidence substitution. This covers single,
  repeated, escaped and unpaired backticks in prose and placeholders, including
  deterministic digest-prose fallbacks. It applies to hearings, reports and motions.
- Evidence substitution occurs **after** cleanup. A genuine backtick inside an
  original evidence-bank quotation is preserved, just like apostrophes and all other
  source punctuation. This is formatting cleanup, not authority to alter quotations.
- Digests, evidence IDs/text/offsets, source pages, headings and private files are not
  rewritten. Minute summaries use a separate pipeline and are unchanged.
- Hearing/report renderer identities advance to 9 and motion renderer to 2. The
  historical shared renderer7 name stays intact. Extraction contracts are unchanged;
  the new report skill and renderer versions affect synthesis freshness only.
- No loading-time cleanup or migration. Existing summaries/editions remain untouched;
  explicit summary regeneration adopts the fix, followed by normal edition rebuilding.
  This change does not provide a zero-model repair command for existing summaries.

## Validation

Local home desktop, disposable tracked-source checkout and dedicated environment at
`/tmp/recordprep-backticks-5jHeU9`, synthetic HOME/XDG/Pi state, metrics disabled,
no paid calls or real-case processing:

- Full unittest discovery: **1045 run, 1037 passed, 8 skipped** (existing optional
  checks). Includes actual offline SDK staging/skill-expansion checks.
- Four new regression tests cover all three shared summary kinds, wrapper variants,
  ordinary prose/fallback cleanup, evidence immutability, apostrophes, corrected
  report examples, final TXT and validated PDF/page-map generation with intact exact
  quote search phrases and no formatting backticks.
- Compileall, sequential resource validation, offline registered-tool audit and
  Agent Skill validator pass. The regenerated audit changes only the report skill
  hash; current golden skill and synthesis fingerprints are updated accordingly.
- Initial test runs caught stale audit/golden fingerprints and renderer expectations;
  these were updated to the reviewed new contract. A disposable-checkout Git init
  resolved the test that checks for tracked personal settings.

No GUI behavior, dependency, launcher/XREMAP, Focus, private configuration, existing
bundle, maintained runtime or running application changes. No commit or push.
