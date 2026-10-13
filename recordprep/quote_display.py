"""Application-owned, display-only capitalization of source quotations."""

QUOTE_CASE_GUIDANCE = """QUOTATION DISPLAY CAPITALIZATION — APPLICATION RULE
Keep {{quote:<quote_id>}} placeholders in prose; never type replacement quotations.
For each all-caps quote used in a section, propose normal display capitalization
in the submit tool's optional quote_capitalizations object: exact quote id ->
case-adjusted text. Use lowercase for an embedded fragment, or sentence case when
it begins a sentence. Preserve proper names, acronyms, initials, legal identifiers,
and meaningful capitalization (for example, JCO, ICWA, Webex and JV-190).
Change letter case ONLY: preserve every word, character, space and punctuation.
Do not paraphrase, fix grammar, expand abbreviations or edit the source quote bank.
Leave already mixed/lowercase quotations unchanged. If a name or acronym's casing
is uncertain, retain that token's source capitalization rather than guess. One
quote id has one display spelling per section; avoid reusing it in incompatible
sentence positions. Python independently checks proposals and falls back to the
original quote on rejection. Do not add an editorial note yourself: Python adds
one normalization notice only when case-adjusted quotations are actually used.
"""

NORMALIZATION_NOTICE = "Capitalization of quotations has been normalized."


def valid_quote_capitalization(original: str, proposed: object) -> bool:
    """Only one-for-one case changes to all-caps source text are permitted.

    Characterwise comparison deliberately rejects Unicode expansions, inserted
    whitespace and typography changes. This proves case-only fidelity, not that
    a proposed proper-name or acronym capitalization is semantically correct.
    """
    return (
        isinstance(proposed, str)
        and original.isupper()
        and len(original) == len(proposed)
        and all(a == b or (a.isalpha() and b.isalpha() and a.lower() == b.lower())
                for a, b in zip(original, proposed))
    )


def display_quote(original: str, proposed: object = None) -> str:
    return proposed if valid_quote_capitalization(original, proposed) else original
