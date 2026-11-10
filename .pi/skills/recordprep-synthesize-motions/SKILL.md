---
name: recordprep-synthesize-motions
description: Write one request-and-reasons section per supplied motion packet, preserving all included filings, party attribution and distinct or opposing positions.
---

# Synthesize the motions summary

Use the fixed application-owned method supplied in the launch message. Read the
dataset overview, then digest blocks with recordprep_get_facts. Use the private
recordprep_synthesis_scratchpad to retain orientation across compaction and retrieve
submitted sections when needed. Work incrementally and submit each entry through
recordprep_submit_summary_section; finish with recordprep_finish_summary. Python
orders and publishes sections, with saved digest-prose fallback for missing output.

Produce one section per supplied packet; do not re-segment it. Classification continuity
can include independent motions, opposition and reply, different parties and dates,
and unnamed internal papers. Explain all included requests and reasons with distinct
party attribution and opposing positions within that section. Never assume a continuation
supports the lead merely because it is grouped with it. Historical entries may have
exact nonadjacent member scopes; use only their supplied evidence.

Answer only what the party requests or opposes and why, in short focused paragraphs.
Open with the filing party, practical relief and target. For an opposition open with
the opposed request and the desired denial, limitation or other result, then its
reasons for resisting the request. A reply explains the position maintained or changed
and its answer to the opposition. Preserve substantive scope, conditions and alternative
relief; do not reduce distinct grounds to a vague statement of support or opposition.

Exclude hearing dates/times/departments, street or mailing addresses, case/court
numbers, incident/tracking identifiers, counsel/firm/contact details and caption,
notice, service and signature boilerplate. Do not keep particulars merely to identify
or distinguish the filing, or reintroduce them from evidence, labels, source metadata
or an older digest. Python provides headings and source navigation separately.
Select for request and reasons; this is not a recital of everything saved in the digest.

Integrate supporting memorandum, declaration and separate-statement material only to
explain a ground, not as independent component accounts or a procedural inventory.
If timeliness, notice, informal resolution or sanctions are an actual ground or
requested relief, explain the contention and its consequence, not contact/filing/service
chronologies or compliance recitals. Preserve the meaning of a substantive deadline
or duration that is itself relief or a disputed ground, not routine calendar details.
Consolidate repetitions without flattening different positions. Preserve material
concessions, counterevidence, limitations, uncertainty and attribution. Do not grade
counsel's strategy, add independent legal analysis, manufacture an opposition from
another party's account or transform relief sought into a ruling. No external research.

Copy exact {{quote:<quote_id>}} placeholders from this entry's evidence bank,
keeping their exact wording, relationship to the digest and surrounding grammar.
Select anchors about relief or reasons for or against it, not identifiers or packaging.
Preserve exact wording, negation, attribution and qualifications. Do not use an anchor
if its expansion would reverse, overstate or contradict the supported proposition.
Do not type quotation marks, invent IDs or add page links. Quotes are anchors, not
independent proof of inferred facts. Do not repeat paraphrase-plus-quote accounts. There are
no word, paragraph, topic-fill or quotation quotas or required Request/Reasons
headings. No extra mandatory validation/repair pass. An all-null entry needs no
paragraphs; report incomplete coverage honestly and submit useful material you have.

## Selection examples

The launch message supplies fictional motion, opposition and reply examples showing
how to keep requests, grounds and consequential qualifications while dropping filing
particulars. They are not source facts, output templates or length limits. Never invent
a corresponding opposition, reply or qualification for this entry.
