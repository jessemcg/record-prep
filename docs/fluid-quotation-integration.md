# Fluid quotation integration — current follow-up, 2026-11-10

## Delivery status

**Implementation and deterministic delivery checks pass. Paid writing-quality
acceptance is NOT met.** The small comparison demonstrates useful changes but also
material fidelity failures and unfinalized arms. A separately authorized follow-up
added synthesis-only semantic/attribution guidance and improved the targeted examples,
but did not achieve clean fidelity; see the follow-up results below. Do not describe this change as
validated improvement in legal accuracy or broad writing reliability, or adopt it
on private bundles based solely on the green offline suite. Changes are left
uncommitted and unpublished for review. No further paid runs or automatic prose
repair were introduced. Total authorized paid work is now 16 sessions / 103 admitted
provider requests / $0.17600790 SDK-reported cost, still below the original $3 ceiling.

Implementation is confined to RecordPrep. Both supplied real bundles were neither
used as fixtures nor edited/regenerated during implementation. No Focus product,
launcher, XREMAP, dependency, profile schema/catalog/version, private settings,
maintained-application restart, commit, push or deployment change is included.
README and frozen historical fixtures are unchanged.

## Display-only end-trimming — November 12

All three narrative skills now combine quote grammar, optional end-trimming and
compact capitalization instructions under **Quotation integration**. The separate
Quotation capitalization heading is removed; the five shared sections remain
byte-identical. Document-specific focus is unchanged.

`quote_selections` maps an exact used quote ID to one nonempty continuous exact
substring of its original text, in source case. Python validates whole-word edges
(including apostrophes, hyphens and combining marks) and disallows internal changes,
splicing, inserted ellipses or partial-word cuts. No semantic correctness is claimed:
for example, a literal substring can still lose a negation. Instructions explicitly
require preserving the whole sentence's meaning, conditions, qualifications and
attribution, and discourage tiny ambiguous search fragments. Restructure or paraphrase
when faithful trimming is uncertain; no automatic semantic repair or new gate.

`quote_capitalizations` remains required by instruction for every used ID, now relative
to the selected text, or the whole original if untrimmed. The explicit unchanged option
remains. The synthesis-only tool schema carries both maps; missing capitalization
feedback still runs within the same session. The original quote ID, digest evidence,
reported page/hash/offsets and extraction remain untouched. Normalization keeps only
valid used-ID selections; rendering independently revalidates them. Invalid selections
fall back to the original quote, invalid case proposals to accepted source spelling,
with nonfatal diagnostics. Last-submission-wins and historical mapless candidates
retain their previous behavior. No extra model pass is added.

TXT and PDF/page-map quotation phrases use the accepted selected display text for
Focus search. IDs do not become new evidence claims; verification still does not
certify context or attribution. Existing source matching remains case-insensitive.
Hearing/report renderer11 and motion renderer4 plus synthesis resources bind freshness;
no old summaries are silently rewritten. Explicit synthesis and editions adopt this
change. Shared active synthesis guidance no longer forbids the permitted display-only
trimming; historical built-in literals/readers remain readable. The accounts below
of capitalization-only display and unchanged HEARING_READABILITY are historical.

Validation: 100 relevant offline tests passed (no GUI/full discovery). Coverage includes
all-three skill parity and actual SDK delivery, selection/case-map transport, exact
whole-word spans, rejection/fallback, repeated substrings, unchanged evidence and
reported offsets/hashes, historical candidates, final render revalidation, TXT/PDF
quotation phrases and case-insensitive source matching. These are mechanics/search
checks, not a claim that model trimming preserves meaning. All three skill validators,
the packaged-tool audit, changed-Python compilation and diff checks passed. No paid
calls, real-bundle regeneration, private-file edits or Focus changes were performed.

## November 12 update: explicit capitalization decisions

Hearing, report and motion synthesis require checking every used quotation's
capitalization in its expanded sentence during normal drafting. Supply a
`quote_capitalizations` entry for **every used quote ID**: its complete case-adjusted
display text, or its complete original text unchanged as an explicit retain decision.
Uncertain meaningful capitalization must be explicitly retained, not omitted.
Only sections without quote placeholders may omit the map or use an empty object.

The synthesis-only submission wrapper preserves the base tool's recorded candidate
and feedback, then identifies missing/empty/non-string decisions (distinct used IDs,
not placeholder occurrences). It returns advisory feedback naming missing IDs and
asking for a complete resubmission during the same synthesis session. Rejected
prerequisites are returned unchanged. No publication gate, automatic lowercasing,
separate model pass or forced repair loop is added. Existing Python validation
still rejects non-case-only text and falls back to original spelling. Explicitly
unchanged strings pass validation without creating a display override. Historical
submissions without maps remain readable and render with source capitalization.
Shared guidance, the tool description and all three skills carry this contract.

This supersedes the first instruction-only attempt, which allowed unchanged or
uncertain quotes to be omitted. A regenerated report used the new instructions but
still missed obvious embedded capitals (3 of 25 quotes adjusted), motivating
explicit coverage rather than another wording-only reminder.

Original evidence, case-only validation, uncertainty safeguards, extraction and
minutes are unchanged. Existing summaries are not edited; explicit synthesis and
edition regeneration are needed to adopt the instruction. The historical statements
below about the hearing skill's byte identity describe the earlier delivery, not
this update; `HEARING_READABILITY` itself remains unchanged.

Validation of the initial instruction-only change: isolated full discovery passed
(1,080 tests, 5 skipped), including
real offline SDK delivery of the shared rule/tool description and all three skills.
New tests cover the required instruction and sentence-initial-word display changes
across all three narrative kinds, unchanged evidence, and source-case fallback when
no map is provided. Skill validators, resource validation, compilation and the
offline packaged-tool audit passed. These checks establish delivery and mechanics,
not guaranteed model compliance; no paid calls or real-bundle regeneration occurred.

Explicit-decision follow-up validation: isolated full discovery passed (1,080 tests,
5 skipped). Actual offline SDK submissions exercised absent maps, partial coverage,
empty decisions, repeated placeholders (one missing decision per ID), explicit
unchanged strings, adjusted strings, and quote-free prose. Missing-decision feedback
is returned without losing the recorded candidate; complete resubmission retains
the display map through Python rendering. Actual staged-launch tests verify the
all-three-kinds contract. Skill validators, compilation, resources and packaged-tool
audit passed. No paid evaluation or real-bundle regeneration was performed; this
establishes feedback and delivery, not that the model will make correct decisions.

## All-three-skill alignment — November 12

Motions now use the same descriptions/title pattern, ordered subheadings and
byte-identical shared sections as hearings/reports. Only Document-specific focus
and kind metadata differ. Motion focus retains plain-English past-tense requests,
objections/replies, quotation tense preservation, no presumed ruling, and one
section per supplied packet with distinct parties/positions. The parity test now
covers all three. Eleven focused tests, skill validation and the updated packaged
audit passed; no GUI/full-suite run or real-bundle generation was performed.
Shared runtime guidance and extraction remain unchanged by this skill alignment.

## Hearing/report skill alignment — November 12

The latest hearing/report edit gives both skills matching descriptions, headings
and identical shared wording for synthesis, quote integration/capitalization, digest
reading and procedure. Only their clearly labeled Document-specific focus and
kind-specific titles/metadata differ. Shared runtime guidance, motion skills and
extraction are unchanged. A dedicated parity test protects the common sections;
17 focused tests passed. See [report editorial](report-editorial.md) for details.
The report-only simplification described next preceded this alignment.

## Report-skill simplification — November 12

The later report-only simplification removes the separate Editorial method section
and local fictional examples, placing a concise cohesive-narrative objective and
reader-time guidance in Synthesis. Repeated procedure instructions are consolidated.
Explicit capitalization decisions and the shared application fidelity examples
remain. See [report editorial](report-editorial.md). Descriptions below of the long
report skill and its local examples document the earlier implementation.

## Motion-skill simplification — November 12

The motion skill now opens its Synthesis section with a plain-English task: concisely
explain what each party asks the court to do or not do, and why. Oppositions identify
what the party objects to, why, and its desired result; replies explain the maintained
or changed position and response to objections. Unnecessary legalese, component
inventories and repeated instructions/local examples are removed. Shared application
selection/fidelity guidance remains unchanged, including its examples.

One section per supplied packet, distinct parties/requests/opposing positions,
material conditions and contrary evidence, administrative-detail exclusions and
source-exact Verified quotations remain protected. The explicit capitalization
section is unchanged. Only the motion synthesis skill changes behavior in this
follow-up; extraction, grouping, shared guidance, tools, renderers and hearing/report
skills are unchanged. Tests cover the central task and motion-synthesis-only freshness.

Validation: 9 focused tests passed, covering motion selection/fallback, skill-only
freshness, actual offline SDK prompt delivery, inspection and explicit capitalization
feedback/rendering. The changed skill validator, packaged prompt-tool audit and diff
checks passed. An earlier full discovery run was interrupted and is not claimed as
acceptance; completion used only relevant checks, with no further GUI/full-suite run.
No paid calls or real-bundle regeneration were performed. These tests establish
instruction delivery and mechanics, not guaranteed plain-English writing quality.

The subsequent motion-only tense clarification requires past-tense narration of
requests, objections and replies (Mother asked the court to order…), even when the
filing uses present tense. Direct quotations keep their source tense; past-tense
attribution or paraphrase provides the fit. Past tense never implies the request
was granted. Six focused motion/delivery tests and skill/audit validation passed;
no summary was regenerated.

## Editorial and display contract

Reports retain substantive selection, attribution, continuity and incremental
submission, adding explicit guidance to let a quotation carry the proposition.
Surrounding prose supplies attribution/context/transition/qualification/consequence,
not an equivalent paraphrase. Read each **entire expanded sentence**, distinguish
sentence-completing phrases from subjects with finite verbs, and avoid doubled
subjects/verbs/infinitives/modals. Complete first-person statements receive supported
attribution. Recast surrounding prose, choose another saved anchor or paraphrase;
never trim, splice, grammatically repair or reassign source wording. Colons/dashes
are allowed for nonredundant content. Keep useful quotation distribution without
quotas, an evidence-bank checklist or a goal of fewer quotations.

The canonical report skill adds fictional phrase, subject/verb, sentence-case,
first-person and unhelpful-confirmation examples. Narrative placeholders are bare
and complete. An optional capitalization map is separate from the unchanged
placeholder. Motions get a shorter version with request/reason/declaration examples,
retaining one section per supplied packet, all distinct/opposing requests and grounds,
conditions/alternatives/concessions and integrated declaration support. No new
re-segmentation, independent legal analysis or inferred support from grouping.

The hearing SKILL and `summary_profiles.HEARING_READABILITY` are byte-identical to
23948d9. Its method/examples remain the reference, not a refactoring target. Minutes
are unchanged. `motion_guidance.EDITORIAL` and motion extraction guidance are unchanged;
only the synthesis branch appends capitalization and expanded-sentence fidelity
guidance. Following the user's later instruction to fix the observed writing failures,
all three narrative kinds also receive `synthesis_fidelity.QUOTATION_INTEGRATION_GUIDANCE`.
This adds explicit semantic condition attachment, finite-clause vs noun-phrase,
nonrepetition, role/pronoun and metadata-vs-court-speech examples. The hearing skill
and HEARING_READABILITY remain byte-identical; its runtime now includes this additional
shared synthesis-only guidance, not only the earlier capitalization change.

All three narrative kinds use the same notice-free application rule:

- `quote_capitalizations` remains exact used quote ID → display spelling. All-caps,
  sentence-case, mixed-case and lowercase sources are eligible when sentence position
  warrants adjustment. Lowercase an ordinary embedded sentence-initial word or add
  appropriate sentence-initial capitalization.
- Preserve proper names, acronyms, initials, first-person **I**, legal identifiers and
  meaningful capitalization. Retain uncertain tokens' source spelling, not guesses.
- Preserve every word, character position, space and punctuation mark. Keep the
  original placeholder; no typed replacement quote, bracket markers or published
  capitalization announcements. One spelling per used ID per surviving section.
- Validation remains identical-length, **characterwise** identical character or
  alphabetic case equivalent using the existing comparison. Only the `isupper()`
  eligibility check was removed. Whole-string casefold equality is not substituted;
  Unicode expansion, typography, spacing, punctuation and wording changes are rejected.
- Candidate normalization accepts proposals only for used exact IDs in the final
  surviving section. Rendering revalidates. Rejected proposals retain source spelling
  and sanitized advisory feedback, not lost otherwise-usable prose. No automatic
  lowercase/title-case heuristics or production writing-quality gate.

Characterwise validity proves case-only fidelity, **not** correct semantic casing,
grammar, attribution or proposition. The paid trial illustrates this distinction.
The historical `NORMALIZATION_NOTICE` symbol and compatibility names remain readable;
no active guidance promises an announcement.

Data flow remains:

`source pages → extraction/digest evidence → synthesis placeholders + optional map
→ validated display substitution → canonical TXT → existing PDF/page maps → Focus`

Evidence text/IDs/source offsets/hashes/provenance are not rewritten. Edition search
phrases use accepted display spelling; unchanged Focus matches sources case-insensitively.

## Freshness and compatibility

Hearing/report renderer identities advance **9 → 10**, motion **2 → 3**. These
identities retain the prior backtick-removal behavior before evidence substitution.
Protocol/schema and the extraction extension are unchanged. Synthesis resource and
display-module hashes honestly invalidate synthesis for all three kinds, including
hearings; extraction is not deliberately invalidated.

On a baseline/candidate comparison using identical isolated settings, all **15/15
synthesis configurations changed** and all **15/15 extraction configurations stayed
identical** across unassigned, General/historical, Dependency, Criminal and historical
custom assignments. All five minute configurations, participant/overview runtime
identities, hearing readability, motion editorial block and unrelated tracked Pi/profile
resources remained identical. Classification/naming/motion organization code/resources
are not changed. Literal private/custom guidance is not migrated.

Compatible digests remain reusable during an explicit summary run. Independently
stale extraction still regenerates normally; there is no zero-extraction promise for
every historical bundle. No metadata forgery, startup migration/reset, automatic
regeneration or deterministic rewrite of old prose. Existing output remains readable
and untouched; badges/Resume stay presence-based.

## Offline and desktop validation

Current-computer-only: `home`. Isolated tracked-source copy:
`/tmp/recordprep-fluid-quotes-hRbPVP/RecordPrep`, separate locked environment
`/tmp/recordprep-fluid-quotes-hRbPVP/env`, explicit absolute
`.../UvEnvironments/project-env --project … --environment …` selection, `umask 077`,
synthetic HOME/XDG/Pi state and metrics disabled. Production environment not synced.
No case/private configuration copied into fixtures. The optional sibling offline SDK
fixture was copied machine-locally, not installed into or changed in another repository.

Validation coverage includes:

- Any-case proposals through normalization/rendering/TXT/PDF/maps for hearings,
  reports and motions; digest objects, IDs, offsets and source bytes/mtime preserved.
- Changed words/deleted negation/spaces/punctuation/typography/Unicode expansions,
  wrong types, unknown IDs and unused IDs rejected without destroying usable prose.
  Missing/malformed maps, replacement submissions, unknown-placeholder fallback and
  direct-renderer revalidation retain best-effort behavior.
- Exact report/motion skills and capitalization/tool descriptions reach actual
  staged child launches and the installed offline SDK's skill expansion/registration,
  not just test-built prompt strings. Inspection verifies all five assignment contexts.
- Existing stage/pipeline coverage passes, including compatible-digest reuse with
  synthesis-only rerun, read-only freshness inspection, failed/stopped publication
  protection, all-null documents and genuinely empty motion summaries.
- Fictional expanded-sentence assertions demonstrate grammatical construction;
  they are not live-model quality assertions or a production prose regex.
- `prompt-tools.json` regenerated with `scripts/collect-prompt-tools.mjs`; affected
  current inspection aggregates refreshed in test loaders. Frozen historical fixtures
  were not rewritten to imply current acceptance.

Commands: full `python -m unittest discover -s tests -v`, compileall, sequential Pi
`--validate-resources`, offline `collect-prompt-tools.mjs --check`, changed report/motion
Agent Skill validators and `git diff --check`. See final run counts in the delivery
summary. Earlier runs found stale goldens, a test assertion on a trimmed trailing
newline, and acceptance-harness setup issues (inherited external config/Pi overrides,
missing disposable Git metadata and background-shell SIGINT behavior); these were
fixed in the test setup/expectations, not by changing product behavior to pass.

`tests/acceptance_summary_quotes_ui.py` now uses the current Reports topics entry
point, checks three extraction and three synthesis inspector views, current rule/tool
agreement, clean audit/read-only text and no settings persistence. It generates all
three synthetic editions with a lowercase display proposal for a sentence-case source
quote, deliberately split across two printed pages. The RecordPrep inspector was
observed with Computer Use and closed without Save. Its opening was an application
handler invocation, not proof of a native pointer click on View full prompts.

Unchanged Focus HEAD was archived into a separate disposable source/environment.
A fatal-criticals GTK harness loaded all three actual producer editions and exercised
nine normal application-handler searches: display spelling, original case and all-caps
for each kind. Each returned the same ordered two source matches and highlight offsets;
bundle bytes/mtime stayed unchanged. Computer Use then **delivered native uinput pointer
clicks** to the page-2 quote fragment in Reports, Motions and Hearings. All three reached
the actual link handler with the complete lowercase phrase (not just the visible
fragment). A report click changed the search box from all-caps to the display spelling;
source highlights and `1 / 2` results were observed. Instrumented activations advanced
from nine scripted calls to twelve after these three native quote clicks. Only temporary
instances were closed. No maintained Focus document/settings/navigation was changed.

## First paid comparison (v1): retained findings and accounting

Frozen fictional fixture: `tests/fixtures/fluid_quotation_comparison.json`. Baseline
source is unchanged 23948d9; candidate uses the delivered source/skills/resources.
Both arms use identical canonical fictional datasets, **Fireworks
`accounts/fireworks/models/deepseek-v4p1-flash-1017`, high reasoning**, the effective
RecordPrep selection. Supported SDK ModelRuntime authentication used the existing
credential mechanism directly; no credential was copied into fixtures or repository
files. Isolated resource discovery, only the four synthesis tools, in-memory sessions,
metrics off. No extraction synthesis-repair or paid review sessions were run.

Before outputs, a factual/attribution checklist covered initial/follow-up continuity,
closure vs reopening/inspection conditions, capacity vs observed movement, west-only
certificate, limited retrieval, competing motion grounds/alternative relief/redaction,
search-not-proof-of-no-inspections, unresolved hearing ownership and ICWA/Webex/first-person
attribution. Review used fully rendered TXT, not placeholder drafts.

The disposable acceptance harness (not production) disabled automatic session retries
and compaction, capped output at 8,192 tokens in both arms and time at 180 seconds per
session, and guarded **every** provider POST including tool-loop/retry requests. First
report pair: ≤8 requests and ≤100,000 payload bytes per request. Remaining six sessions:
≤10 requests and ≤90,000 payload bytes per request. After the first candidate exhausted
its cap, no retry/replacement ninth session was made. The remaining request caps were
allocated conservatively before starting those sessions; model/reasoning/output settings
and fixtures did not change. Every request's output bound was checked before network
submission. Token price bounds were $0.30/M input and $1.20/M output (cache no more than
input); conservatively accounting input by the entire request's UTF-8 byte count gave
**$2.8471104 maximum aggregate reserved exposure**, below the $3 authorization.

| Arm | Provider requests | Final candidate | SDK-reported cost, rounded |
|---|---:|---|---:|
| Reports 1 baseline | 8 | yes | $0.015676 |
| Reports 1 candidate | 8 | **no — request cap** | $0.015272 |
| Reports 2 baseline | 7 | yes | $0.009555 |
| Reports 2 candidate | 7 | yes | $0.013677 |
| Motions baseline | 6 | yes | $0.007003 |
| Motions candidate | 6 | yes | $0.008644 |
| Hearings baseline | 5 | yes | $0.007558 |
| Hearings candidate | 6 | yes | $0.008124 |

Total **8 sessions / 53 admitted provider requests / $0.08550798 SDK-reported cost**.
These are SDK usage figures, not an independently reconciled invoice. A guard-rejected
continuation in the unfinalized report arm is not an admitted/billable provider request.
All seven completed finals were rendered and their editions validated. Every accepted
candidate map passed case-only checks; all source/dataset bytes/mtime were unchanged.
The baseline Reports 2 proposed sentence-case normalization which the baseline correctly
rejected under its old all-caps-only rule. Candidate maps were accepted without flags.

### Fully rendered sentence review

- **Report improvement:** baseline embeds `that “The eastern support remained unstable
  after the repair”`; candidate correctly embeds `that “the eastern support remained
  unstable after the repair”`. Candidate also lowercases the follow-up no-movement
  sentence and gives the complete `“I cannot certify the structure as safe”` statement
  supported attribution. Initial/follow-up chronology, the west-only certificate,
  incomplete testing, limited retrieval and recommendation-not-order distinction remain.
- **Report failure (material):** candidate says Vale *“framed the closure as warranted
  ‘only after a joint inspection of both supports’”*. The digest calls for closure
  pending inspection, not closure warranted only afterward. This misattaches the exact
  anchor and reverses its condition despite valid evidence spelling. Both baseline and
  candidate also force the finite quote `ICWA reviewer joined by Webex without assessing
  structural safety` after `an`, an awkward/dangling construction. Candidate leaves the
  embedded source capital in `but “The new certificate …”`. No clean grammar/fidelity
  acceptance or complete two-repeat report comparison can be claimed.
- **Motion improvement:** baseline has the clear doubled subject `In reply, the claimant
  “The claimant will accept redaction …”`. Candidate uses the complete quoted subject
  directly, keeps one request-and-reasons section with opposing positions/alternative
  redaction/access, and accepts `“the gaps do not establish …”` after `that`. No new
  external legal research, missing declaration inventory or conversion to a ruling.
- **Motion limitations:** both retain the unhelpful archive-review confirmation, and
  candidate repeats the missing-entry/testing rationale in adjacent paragraphs. Candidate
  adds the *owner's assertion* that inspections occurred where this fixture only says
  the claimant wants to test whether they occurred; that attribution is not established.
  Calling Chen *its custodian* also risks an unsupported affiliation. Thus improvement
  on the doubled subject does not establish clean attribution throughout.
- **Hearing improvement:** existing short issue/result-focused paragraphs, notice/engineer
  conditions, unresolved ownership, load-capacity qualification and attributed first-person
  statement survive; the embedded `The eastern support …` receives the intended lowercase
  proposal without changing `ICWA`, `Jo Lin`, `Webex` or `I` in quotations.
- **Hearing limitations:** candidate says *reopen the inspection generally* rather than
  reopen the site, and assigns Jo Lin *she* without supplied gender evidence. Both arms
  embellish court attribution of the reviewer description. The editorial resource bytes
  were protected, but the small live sample does not prove unchanged factual fidelity.

No additional doubled modal was observed in the completed candidates; that is not a
statistical claim. No tested accepted capitalization map changed words, negation,
proper-name/acronym/I spelling, punctuation or evidence provenance. The failures arise
in surrounding prose/selection/attribution and are deliberately **not** hidden by a
production repair system, blocking quality validator, rewritten source quote or extra
paid pass. **Quality acceptance fails** because material regressions remain, even though
targeted integration and display mechanics improved. The original eight-session allowance was exhausted, not its dollar ceiling. The user
subsequently explicitly requested more paid calls and fixes, authorizing the follow-up
below. The failed findings above are retained rather than relabeled as passing.

Machine-local receipts/fully rendered synthetic outputs and harnesses remain under
`/tmp/recordprep-fluid-quotes-hRbPVP/paid`, with `ledger.json` and per-completed-arm
`render-receipt.json`; these paths are evidence, not application runtime dependencies.
Do not use their synthetic metadata to bless any real bundle.

## Authorized follow-up: v1 versus shared-fidelity guidance (v2)

The user's subsequent instruction was **“Conduct more paid calls and fix the writing
problems”**. Implementation added the synthesis-only shared fidelity rule described
above and concise report/motion skill reinforcement. No new tool, model stage,
extraction instruction, prose repair, deterministic rewriter or blocking writing-quality
validator. No per-kind method/renderer version beyond the already unreleased 10/10/3.
Current source/skill and registered-tool hashes were refreshed honestly. The hearing
skill/readability block, shared motion EDITORIAL and extraction remain protected.

The follow-up retained the same frozen fixture, effective model/high reasoning,
8,192-token experimental output bound, auth isolation, time bound and pre-output factual
checklist. Baseline was a frozen source snapshot of v1, **not 23948d9**; candidate is v2.
Both report repetitions use identical fictional input, as do the motion/hearing pairs.
No failed arm was replaced by a ninth additional session.

An initial follow-up baseline did not finalize after six admitted requests under the
60,000-byte request guard (12-request allowance). Its synthetic final was not recovered
or treated as a complete comparison. Subsequent seven sessions were each allowed at
most 16 requests and 150,000 request bytes, still 8,192 output tokens and 180 seconds.
Those limits are acceptance-harness-only and the same for both remaining arms. This
avoided the earlier guard preventing ordinary dataset/tool-loop completion; observed
largest payload was 70,088 bytes, not a production requirement or prompt quota.

Budget accounting retained the **original $3 aggregate ceiling**, not another $3.
Every admitted first-round request had settled with token usage. Repricing all prior
cached input at full input price gave a conservative $0.18402150 prior spend bound.
For each follow-up session, the guard reserved at most $0.87728640 before starting;
a completed reservation was released only when every admitted request had settled
with usage, repriced at full input price. Unknown/partial sessions would retain their
whole worst-case reservation. Before every new session, past exposure plus the new
worst-case reservation had to remain below $3. Network retries and tool loops still
counted against the per-session request allowance; no automatic session retries.

| Follow-up arm | Provider requests | Final candidate | SDK-reported cost |
|---|---:|---|---:|
| Reports 1 v1 baseline | 6 | no | $0.012808272 |
| Reports 1 v2 candidate | 8 | yes | $0.010444440 |
| Reports 2 v1 baseline | 8 | yes | $0.014506176 |
| Reports 2 v2 candidate | 7 | yes | $0.016272204 |
| Motions v1 baseline | 6 | yes | $0.009751272 |
| Motions v2 candidate | 5 | yes | $0.009939384 |
| Hearings v1 baseline | 5 | yes | $0.008298948 |
| Hearings v2 candidate | 5 | yes | $0.008479224 |

Follow-up **8 sessions / 50 requests / $0.09049992 reported cost**. Across both rounds:
**16 sessions / 103 requests / $0.17600790 reported cost**; conservative full-input
repricing of all settled usage is **$0.36537330**. This is usage accounting, not an
independent provider invoice. No additional paid calls followed these eight sessions.
Seven more completed finals passed normalization/evidence-preservation and edition
validation with no capitalization-rejection flags. Baseline/candidate input rows and
model/reasoning settings matched; source/dataset bytes/mtime were preserved.

### What the follow-up fixed and what it did not

Fully rendered outputs were reviewed against the same factual checklist, including the
unpaired first report candidate. No automatic output cleanup was applied.

- **Condition attachment improved:** both v2 report candidates keep closure pending
  inspection. Neither repeats the v1 inversion that closure was warranted only after
  inspection. The new shared example makes that precise distinction.
- **Clause/noun construction improved:** neither v2 report candidate forces the complete
  ICWA-reviewer clause after `an`. One paraphrases that incidental consultation; the
  other supplies `the` before a complete clause under `the report notes that …`.
- **Grammar/capitalization:** no doubled subject/verb/modal or dangling finite quote
  was identified in the completed v2 candidates. Both correctly embed the eastern-
  support sentence in lowercase. The second report candidate also embeds the western-
  certificate sentence and no-movement sentence in lowercase. Proper quotation names,
  ICWA/Webex and first-person I remain intact. Complete first-person assessments keep
  attribution. This is observed sample behavior, not a general guarantee.
- **Report continuity mostly retained:** new certificate, incomplete testing, unchanged
  bounded recommendation, proposed limited retrieval, notice/engineer condition and
  owner's opposition to continued closure remain. Recommendations are expressly not
  orders. The second v2 report candidate no longer says that whether to close the wing
  had ceased to be a live question while also recounting that dispute.
- **Report fidelity still fails:** the second v2 report candidate adds `so entry for an
  inspection would not have moved those records out of the owner's hands`. The digest
  only says the owner will retain the logs; it does not establish that consequence of
  entry. The first v2 candidate also omits the explicit contrary contention that the
  owner's maintenance logs showed repairs complete. Thus a condition/grammar improvement
  cannot be called clean fidelity or a complete two-repeat acceptance.
- **Motion focus improved:** the v2 candidate groups the practical request and opposition,
  gives the supporting declaration in the claimant's ground, then explains opposition
  and reply. It avoids the invented owner's assertion, guessed declarant affiliation
  and gender, retains negation (unlocated entries are not proof of no inspections),
  conditional access, privilege limitation, health redaction and reply acceptance. No
  doubled subject or independent legal research. It still quotes the routine archive-
  review confirmation; the desired selection improvement is not reliable. The requested
  redacted-entry alternative is conveyed in the reply concession rather than explicitly
  listed as alternative relief in the opener, so this is not a model-compliance guarantee.
- **Hearing fidelity still fails:** the v1 baseline says `reopen the eastern support`
  and invents `she`. The v2 candidate avoids that wrong object, preserves the purpose/
  result, conditional retrieval, unresolved ownership and capacity qualification, but
  again says the court `recorded` the appearance and `identif[ied] her` as the ICWA
  reviewer. Neither the gender nor the court-attribution is supplied. Those are exactly
  the failures the shared guidance warns against; presence in the prompt did not prove
  compliance. The method resources remain unchanged, but successful semantic acceptance
  cannot be claimed from this sample.

**Conclusion: useful targeted writing fixes, but overall writing-quality acceptance
remains NOT MET.** There are still substantive omissions/inferences and unsupported
attribution. The implementation is retained for review, not claimed ready for private
adoption. No additional tuning is hidden after the tested v2 source, no automatic
repair pass, and no more paid calls beyond the declared follow-up limit. Another
iteration or different model needs a new explicit user direction and bounded budget.

Follow-up machine-local receipts/outputs: `/tmp/recordprep-fluid-quotes-hRbPVP/paid-followup`;
its `ledger.json`, per-completed-arm `render-receipt.json` and fully rendered synthetic
TXT/PDF/maps are separate from the first round. `round1/` preserves the v1 source only,
not a runtime or private settings copy.

Final v2 offline discovery: **1,052 tests, 1,047 passed, 5 skipped** (three owner-specific
model slots and two optional metrics/sibling cases). Actual offline quote-map, participant
and overview SDK fixtures run rather than skip after the machine-local fixture copy.
The actual staged-launch SDK test checks the shared fidelity rule as well as capitalization
and registered tool descriptions. Current prompt-inspector acceptance includes the
fidelity rule in all three syntheses and excludes it from all three extractions. Compile,
resources, audit, changed Agent Skills and diff checks pass. The original 15/15 synthesis-
change / 15/15 extraction-unchanged comparison still holds, including protected minute,
participant/overview, hearing and motion editorial identities.

## Later adoption — explicit user action only

No adoption is performed by these edits, and the failed quality acceptance should be
reviewed before using the new synthesis method on real material. If the user later
chooses to adopt it:

1. Explicitly run the desired hearing/report/motion summary stage under the updated
   application. Reuse compatible canonical digests normally; let independently stale
   extraction follow its normal regeneration rules.
2. Rebuild affected summary editions through the normal stage/workflow, and review
   fully rendered narrative against original sources and attribution/conditions.
3. Refresh dependent overview/source-map output as appropriate through normal workflows.

Edition rebuilding alone faithfully renders saved TXT; it cannot fix old synthesis
grammar or capitalization. No direct real-bundle rewrite, freshness repair, reset,
startup migration or metadata relabeling is authorized by this follow-up.
