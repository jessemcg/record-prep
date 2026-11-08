"""Import-light quotation selection policy; advisory, never an acceptance gate."""

QUOTE_MIN_WORDS = 6
QUOTE_MAX_WORDS = 12
QUOTE_PREFERRED_MIN_WORDS = 8
QUOTE_PREFERRED_MAX_WORDS = 10

EXTRACTION_QUOTE_GUIDANCE = f"""Quotes: select continuous, verbatim source quotations normally containing
{QUOTE_MIN_WORDS}–{QUOTE_MAX_WORDS} words, usually {QUOTE_PREFERRED_MIN_WORDS}–{QUOTE_PREFERRED_MAX_WORDS}. Choose the shortest natural phrase in that range
that meaningfully distinguishes the point: a substantive action, condition, reason,
or disputed assertion. Prefer distinctive substantive wording over stock courtroom
language, routine appearances, generic names/dates and boilerplate. Do not add
incidental identifiers merely to make a quotation unique. Preserve negation,
qualifications and attribution. Take each quotation from its declared original
source page, never from participant-index context. Extraction sees the current document,
not the whole record; do not claim record-wide uniqueness. Repeated source passages
can still match more than once.
Do not stitch fragments, insert ellipses, or silently clean up source wording.
Do not pad, truncate or rewrite source wording to meet the range. Never bring sentence-ending punctuation inside the final
quotation marks. If no useful anchor exists, retain the point as paraphrase rather
than forcing a quotation. There is no fixed quotation count per category, paragraph
or document, and no requirement for a quote in every paragraph. A quotation should
help locate source language, not force an extra sentence or repeat a paraphrase.
Useful out-of-range quotations remain valid exceptions: length checks are advisory
only, never a reason to discard useful summaries or request another model pass.
"""
