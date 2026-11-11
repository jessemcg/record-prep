"""Application-owned, display-only capitalization of source quotations."""

QUOTE_CASE_GUIDANCE = """QUOTATION DISPLAY CAPITALIZATION — APPLICATION RULE
Keep {{quote:<quote_id>}} placeholders in prose; never type replacement quotations.
For a quote used in a section, optionally propose display capitalization in the
submit tool's quote_capitalizations object: exact quote id -> case-adjusted text.
All-caps, sentence-case, mixed-case and lowercase source quotations are eligible
when their sentence position warrants adjustment. Lowercase an ordinary source
sentence-initial word when embedded mid-sentence; use appropriate sentence-initial
capitalization when needed. Preserve proper names, acronyms, initials, first-person
I, legal identifiers and capitalization that carries meaning (for example, JCO,
ICWA, Webex and JV-190). When a token's proper capitalization is uncertain, retain
its source spelling rather than guess.
Change letter case ONLY: preserve every word, character position, space and
punctuation mark. Do not paraphrase, fix grammar, expand abbreviations or edit the
source quote bank. Keep the original placeholder, never type a replacement quote
or add bracketed capitalization markers. One quote id has one display spelling per
section; avoid reusing it in incompatible sentence positions. Python independently
checks proposals and falls back to the original quote on rejection. Case-only
validation proves fidelity, not meaningful capitalization. Do not add any
capitalization announcement to the published narrative.
"""

NORMALIZATION_NOTICE = "Capitalization of quotations has been normalized."


def valid_quote_capitalization(original: str, proposed: object) -> bool:
    """Only one-for-one case changes to source text are permitted.

    Characterwise comparison deliberately rejects Unicode expansions, inserted
    whitespace and typography changes. This proves case-only fidelity, not that
    a proposed proper-name or acronym capitalization is semantically correct.
    """
    return (
        isinstance(proposed, str)
        and len(original) == len(proposed)
        and all(a == b or (a.isalpha() and b.isalpha() and a.lower() == b.lower())
                for a, b in zip(original, proposed))
    )


def display_quote(original: str, proposed: object = None) -> str:
    return proposed if valid_quote_capitalization(original, proposed) else original
