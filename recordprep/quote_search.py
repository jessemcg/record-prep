"""Focus-compatible phrase-search verification, without a Focus runtime dependency.

The normalization and regex builders mirror Focus focus/core.py's Find/link
search contract. Keep conformance tests in sync when either implementation changes.
This is search compatibility, not proof of attribution, meaning or uniqueness.
This module matches one page at a time; record_quote_search owns the record-wide
inventory and scan. Source text is never rewritten.
"""
from __future__ import annotations

import re
import unicodedata

from .focus_transcript_reading import search_layout, search_projection

QUOTE_SEARCH_CONTRACT = "focus-phrase-search-2"
TRANSCRIPT_SEARCH_CONTRACT = "focus-transcript-search-1"
MAX_BREAKS = 2
MAX_INTERWORD_NUMERIC_INSERTS = 1
MAX_INTERWORD_NUMERIC_DIGITS = 8
NORMALIZE_REPLACEMENTS = {
    "\u2019": "'", "\u2018": "'", "\u201C": '"', "\u201D": '"',
    "\u2013": "-", "\u2014": "-", "\u00A0": " ",
    "\u00B7": " ", "\u2022": " ",
    # Match Focus: a gutter bar separates words; it never joins their letters.
    "|": " ",
}


def normalize_quotes_dashes(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for src, dst in NORMALIZE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def normalize_text_for_search(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalize_quotes_dashes(text)


def preprocess_phrase(phrase: str) -> str:
    return normalize_quotes_dashes(phrase)


def build_word_pattern(word: str) -> str:
    parts: list[str] = []
    length = len(word)
    for i, ch in enumerate(word):
        if ch == "-":
            parts.append(r"\-(?:[ ]*\n[ ]*)?")
        elif ch in ("'", '"'):
            parts.append(r"['\"]")
        else:
            parts.append(re.escape(ch))
        if ch.isalnum() and i + 1 < length and word[i + 1].isalnum():
            parts.append(r"(?:[ ]+)?")
    return "".join(parts)


def build_pattern(phrase: str, max_breaks: int = MAX_BREAKS) -> str:
    words = [w for w in re.split(r"\s+", phrase) if w]
    words = [build_word_pattern(w) for w in words]
    newline_alts = []
    for count in range(1, max_breaks + 1):
        newline_alts.append(r"(?:[ \t]*\n)" * count + r"[ \t]*")
    alts = [r"(?:[ \t]+)"] + newline_alts
    sep_base = "(?:" + ("|".join(alts) if alts else r"(?:[ \t]+)") + ")"
    numeric_bridge = (
        rf"(?:\d{{1,{MAX_INTERWORD_NUMERIC_DIGITS}}}[ \t]*)"
        rf"{{0,{MAX_INTERWORD_NUMERIC_INSERTS}}}"
    )
    optional_quotes = r"['\"]*"
    sep = optional_quotes + sep_base + numeric_bridge + optional_quotes
    return r"(?x)" + sep.join(words)


def prepare_search_page(page_text: str, *, transcript: bool = False) -> str:
    """Focus's search-only gutter projection, then its core normalization.

    Callers opt in only for pages classified as hearing transcripts, independently
    of the kind of document whose quote is being verified. Detection is bounded and conservative; ordinary lists, tables, ambiguous
    columns and oversized pages retain Focus's original-text fallback. Never
    use render_readable: display reflow is not the text Focus actually searches.
    """
    layout = search_layout(page_text) if transcript else None
    projection, _ = search_projection(page_text, layout=layout) if layout else (page_text, None)
    return normalize_text_for_search(projection)


def quote_matches_focus_search(
    quote: str, page_text: str, *, transcript: bool = False,
    prepared_page: str | None = None,
) -> bool:
    """Use the same projection, phrase preparation, flags and normalization as Find.

    Numeric bridges deliberately accept numbers, not just proven line numbers:
    matching Focus is not a semantic assertion that an intervening number is inert.
    prepared_page lets extraction reuse a page projection within one document;
    it must be produced by prepare_search_page with the same eligibility.
    """
    phrase = preprocess_phrase(quote.strip())
    if not phrase.strip():
        return False
    pattern = re.compile(build_pattern(phrase, MAX_BREAKS), re.IGNORECASE | re.DOTALL)
    searchable = (prepare_search_page(page_text, transcript=transcript)
                  if prepared_page is None else prepared_page)
    return pattern.search(searchable) is not None
