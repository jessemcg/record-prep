"""Validated display-only selection and capitalization of source quotations."""

QUOTE_CASE_GUIDANCE = """QUOTATION DISPLAY — APPLICATION RULE
Keep original {{quote:<quote_id>}} placeholders and the saved evidence unchanged.
Optionally supply quote_selections: exact used quote id -> one continuous exact
substring of its original text, preserving source case. Remove only whole words
at either end to improve flow; no internal deletions, splicing, ellipses or rewriting.
Choose a useful search phrase, not a tiny ambiguous fragment. Never drop negation,
conditions, qualifications or attribution in a way that changes what the whole
sentence asserts. If faithful integration is difficult, restructure or paraphrase.
For EVERY used quote id, supply quote_capitalizations with the full selected text
(or original text if untrimmed), either case-adjusted or unchanged as an explicit
retain decision. Lowercase ordinary embedded sentence-initial words; capitalize
at sentence start. Preserve names, acronyms, initials, first-person I and meaningful
capitalization; retain source case when uncertain. Within the selected span change
letter case only, preserving every character position, space and punctuation mark.
Only quote-free sections may omit the map. Address missing-decision feedback in
the same synthesis session. No bracket markers or capitalization announcements.
Python validates selections and case changes independently and falls back on
rejection. Validation proves literal fidelity, not preserved meaning or attribution.
"""

NORMALIZATION_NOTICE = "Capitalization of quotations has been normalized."


def valid_quote_capitalization(original: str, proposed: object) -> bool:
    """Only one-for-one case changes to source text are permitted."""
    return (
        isinstance(proposed, str)
        and len(original) == len(proposed)
        and all(a == b or (a.isalpha() and b.isalpha() and a.lower() == b.lower())
                for a, b in zip(original, proposed))
    )


def valid_quote_selection(original: str, proposed: object) -> bool:
    """An exact contiguous span, never empty or cutting through a word.

    Search all occurrences: a repeated substring may have a valid boundary only
    at a later occurrence. This check cannot establish semantic faithfulness.
    Apostrophes/hyphens/combining marks remain part of words, not trim boundaries.
    """
    import unicodedata

    def word_char(char: str) -> bool:
        return char.isalnum() or char in "_'’-‐‑" or unicodedata.category(char).startswith('M')

    if not isinstance(proposed, str) or not proposed or not any(c.isalnum() for c in proposed):
        return False
    if proposed == original:
        return True
    if proposed != proposed.strip():
        return False
    start = original.find(proposed)
    while start >= 0:
        end = start + len(proposed)
        if ((start == 0 or not (word_char(original[start - 1]) and word_char(original[start])))
                and (end == len(original) or not (word_char(original[end - 1]) and word_char(original[end])))):
            return True
        start = original.find(proposed, start + 1)
    return False


def display_quote(original: str, proposed: object = None, selection: object = None) -> str:
    selected = selection if valid_quote_selection(original, selection) else original
    return proposed if valid_quote_capitalization(selected, proposed) else selected
