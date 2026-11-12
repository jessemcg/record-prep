"""Synthesis-only semantic/grammar guidance, never extraction or a prose filter."""

QUOTATION_INTEGRATION_GUIDANCE = """VERIFIED QUOTATIONS ONLY — SYNTHESIS RULE
Use direct quotations only from entries explicitly marked Verified in the digest.
Never use an Unverified quote's placeholder or copy its text as a direct quotation.
If no suitable Verified anchor exists, paraphrase the supported digest point or
choose another relevant Verified quote. Do not discard material facts merely
because their quotation is Unverified. Do not repair, relabel or independently
assume verification. Verified means Focus-style search found the wording on at
least one page somewhere in the record, not necessarily the model-reported page.
It does not certify the reported page, document, attribution or meaning. Use the
digest prose for context; a search hit elsewhere is not new evidence for an
inference. Keep verification labels out of
published prose. This rule applies to every narrative summary and every example
below; example anchors are eligible only if their actual digest entries are Verified.

EXPANDED-SENTENCE FIDELITY — SYNTHESIS ONLY
Choose the material point before choosing an anchor. The digest supplies its
meaning, actor, attribution and qualifications; an exact quote is not independent
support for a new proposition. Check BOTH grammar and meaning in the entire
expanded sentence during ordinary drafting/submission, not a separate review pass.

Fit the selected quotation to its actual grammatical form. The display-selection
rule permits faithful end-trimming; otherwise use the complete saved quote. A clause with its
own subject and finite verb is not a noun phrase: do not put it after an article,
possessive, preposition or another subject merely because it contains useful words.
Do not introduce a quotation with an equivalent complete paraphrase or repeat the
same rationale across adjacent paragraphs. Attribution may introduce a complete
statement without announcing its whole proposition again. If no natural and
faithful construction fits, retain the material point as paraphrase and use other
suitable anchors elsewhere. Do not exhaust the bank, force a review confirmation,
or change quoted words. End-trimming must preserve the complete sentence's meaning,
negation, conditions, qualifications and attribution. Quotation distribution is not a quota.

Preserve the relation between a condition and the act it qualifies. Identify exactly
WHAT may/must/must not happen, WHO acts, and WHEN/UNDER WHAT CONDITION. Do not move a
condition from reopening to closure, disclosure to withholding, or a request to an
order; do not turn until into after or not-established into disproved. Preserve
negation, alternatives and scope even when a fluent sentence would be shorter.
An anchor that fits grammatically can still state the opposite legal/factual point.

Attribute only what the digest actually attributes. Do not invent an opponent's
assertion from the fact that someone wants to test whether an event occurred. Do
not infer employment/ownership/allegiance from a supporting declaration or packet
membership. Use the person's supplied name or role rather than an unsupported
pronoun, honorific or affiliation. Report an appearance as an appearance unless the
digest says the court announced, clarified or found it; procedural metadata is not
judicial speech. Preserve the object and action: inspecting a building, reopening
the building and reopening an inspection are different propositions.

Fictional examples below assume only the stated digest facts and complete bank
entries; they are not evidence or instructions to use these ids in an actual case.

A saved finite clause is not a noun phrase — bank report:0001/assessment/1 =
'The archive reviewer attended remotely without assessing the damaged supports'.
Avoid: The report describes an {{quote:report:0001/assessment/1}}.
Prefer, with no suitable grammatical/meaningful anchor: The archive reviewer
attended remotely but did not assess the damaged supports.
Do not quote the routine attendance merely to use the anchor; choose another useful
anchor for the material engineering assessment if the bank supplies one.

Condition attaches to reopening — digest: the store should stay closed pending
ventilation repairs; bank report:0001/assessment/2 =
'only after the ventilation system has been repaired'.
Avoid: The engineer considered closure warranted {{quote:report:0001/assessment/2}}.
Prefer: The engineer recommended reopening {{quote:report:0001/assessment/2}}.
If the digest does not support reopening on that condition, paraphrase the actual
closure recommendation instead. Never infer permission solely from quote wording.

An issue is not an opponent's assertion — digest: the applicant needs records to
test whether inspections occurred; the supplied papers give no owner's assertion.
Avoid: The applicant seeks to test the owner's assertion that inspections occurred.
Prefer: The applicant seeks records to test whether inspections occurred.
Supporting declarant Sal Reed's affiliation and gender are not supplied: use Reed
or the declarant, not its custodian, the owner's employee, he or she. Do not repeat
that same testing rationale in both an opening synopsis and the declaration account.
Use only actual digest facts, relations, attributions and exact ids.
"""
