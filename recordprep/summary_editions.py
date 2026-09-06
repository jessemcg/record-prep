"""Canonical page-matched Letter PDF editions and Focus page maps.

RecordPrep is the sole pagination producer. For each canonical summary text
file (for example ``summaries/hearings_sum_<case>.txt``) this module renders a
fixed US-Letter PDF under ``summaries/editions/`` plus a versioned page-map
sidecar that Focus consumes. The PDF is the immutable pagination authority;
the sidecar is derived from that exact PDF layout rather than estimated.

Invariants enforced here:

- Page body text extracted from the generated PDF, concatenated across pages
  and whitespace-normalized, equals the printable source representation (the
  source text with trusted ``[label](page:NNNN)`` links replaced by their
  labels and recognized quoted phrases rendered without their outer double
  quote delimiters). Nothing may be dropped, duplicated, or reordered. The
  canonical ``.txt`` summaries keep their quotation marks byte-for-byte; the
  delimiter removal is a presentation-only transformation applied to the
  printable representation, and the sidecar records the affected spans so
  Focus can restore its quote styling without reparsing text.
- Recognized quotations are rendered in bold through the built-in Nimbus
  Roman bold face (requested by wrapping their content in ``<b>`` while the
  CSS ``Times`` family resolves the faces). The sidecar carries each page's
  quote fragments as exact character offsets into the extracted page text
  plus the complete quote content for record-wide phrase search.
- Quote recognition is deliberately conservative: style-matched straight or
  curly double quote pairs within one source line, with content that
  survives rendering-equivalent normalization, and no partial overlap with
  a trusted link span. Unmatched or partially overlapping delimiters stay
  literal in both the PDF and the sidecar.
- Record-page link spans are exact character offsets into the extracted page
  text and are verified against their declared labels. Ambiguous or lost
  mappings fail generation instead of silently dropping a Focus link.
- All other text is HTML-escaped, so model output can never become executable
  HTML, load external resources, or alter pagination semantics.
- The layout is fixed (Letter portrait, 54pt margins, 11pt Times-family body
  rendered by PyMuPDF's built-in Nimbus Roman face, ``Page N of M`` footers).
  Footers are drawn inside the bottom margin and are excluded from page body
  text. Requesting the CSS ``Times`` family resolves to MuPDF's built-in
  Nimbus Roman, so pagination is deterministic and never depends on locally
  installed fonts, Fontconfig, or any external font file.

Progress and error messages intentionally contain only categories, page
numbers, and counts — never summary content.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import fitz

EDITIONS_DIRNAME = "editions"
PAGE_MAP_ARTIFACT = "recordprep-summary-pages"
# Schema v2 adds the required ``pages[].quotes`` quote-fragment spans that
# accompany the bold presentation of recognized quotations. Schema v1
# sidecars (layouts v1/v2, no quote spans) remain readable by Focus but are
# no longer produced or accepted by this module's validator.
PAGE_MAP_SCHEMA_VERSION = 2
SUMMARY_EDITION_KINDS: tuple[str, ...] = ("hearings", "reports", "minutes")

# Letter v3 layout: the letter-v2 typography contract plus bold quoted
# phrases rendered without their outer double quote delimiters. Body text
# uses MuPDF's built-in Times-compatible Nimbus Roman face (via the CSS
# ``Times`` family), so pagination is identical on every computer.
LAYOUT_ID = "recordprep-summary-letter-v3"
# Recorded in the sidecar layout metadata alongside the unchanged typography
# metrics so consumers know how quoted phrases are presented.
QUOTE_PRESENTATION_POLICY = {
    "policy": "bold-quoted-phrases",
    "remove_outer_double_quote_delimiters": True,
    "recognized_delimiters": ["\"", "\u201c", "\u201d"],
}
PAGE_WIDTH_PT = 612.0
PAGE_HEIGHT_PT = 792.0
MARGIN_PT = 54.0
BODY_FONT_SIZE_PT = 11.0
BODY_FONT_FAMILY = "Nimbus Roman"
_CSS_BODY_FONT_FAMILY = "Times"
BODY_LINE_HEIGHT = 1.18
PARAGRAPH_SPACING_EM = 0.5
FOOTER_FONT_SIZE_PT = 9.0
FOOTER_FONT_FAMILY = "Times"
FOOTER_BASELINE_FROM_BOTTOM_PT = 36.0
FOOTER_TEMPLATE = "Page {n} of {m}"

# RecordPrep's trusted record-page link syntax. Anything else is literal text.
RECORD_PAGE_LINK_RE = re.compile(r"\[([^\]\[\n]+)\]\(page:(\d+)\)")


def _format_pt(value: float) -> str:
    """Format a point value as a CSS length (integer points stay clean)."""
    if float(value).is_integer():
        return f"{int(value)}pt"
    return f"{value}pt"


_USER_CSS = (
    f"body{{font-family:'{_CSS_BODY_FONT_FAMILY}';"
    f"font-size:{_format_pt(BODY_FONT_SIZE_PT)};"
    f"line-height:{BODY_LINE_HEIGHT};margin:0;padding:0;}}\n"
    f"p{{margin:0 0 {PARAGRAPH_SPACING_EM}em 0;padding:0;}}"
)
_LINK_CHAR_CENTER_TOLERANCE_PT = 0.75
_MIN_LINK_RECT_WIDTH_PT = 0.5
_GEOMETRY_TOLERANCE_PT = 0.5


class SummaryEditionError(ValueError):
    """Raised when a summary edition cannot be built or validated."""


@dataclass(frozen=True)
class SummaryLinkSpan:
    """A trusted record-page link mapped into one PDF page's body text."""

    label: str
    target_page: int
    start: int
    end: int


@dataclass(frozen=True)
class SummaryQuoteSpan:
    """One page's fragment of a recognized quotation, bold in the PDF.

    ``start``/``end`` are exact character offsets into that page's extracted
    body text and ``label`` is exactly ``text[start:end]``. ``phrase`` is the
    complete quote content (without its delimiters), identical on every
    fragment of a quotation that wraps across a paper-page boundary, so a
    phrase search stays record-wide.
    """

    label: str
    phrase: str
    start: int
    end: int


@dataclass(frozen=True)
class SummaryPage:
    """One validated PDF page of a summary edition."""

    page: int
    text: str
    source_first_line: int
    source_last_line: int
    links: tuple[SummaryLinkSpan, ...] = ()
    quotes: tuple[SummaryQuoteSpan, ...] = ()


@dataclass(frozen=True)
class SummaryEdition:
    """A fully built and validated edition, ready to publish."""

    kind: str
    pdf_bytes: bytes
    page_map: dict[str, Any]
    pages: tuple[SummaryPage, ...] = field(default_factory=())


def summary_editions_dir(root_dir: Path) -> Path:
    return Path(root_dir) / "summaries" / EDITIONS_DIRNAME


def summary_edition_output_paths(source_path: Path) -> tuple[Path, Path]:
    """Return ``(pdf_path, pages_path)`` beside ``source_path``.

    ``summaries/hearings_sum_<case>.txt`` maps to
    ``summaries/editions/hearings_sum_<case>.pdf`` and
    ``summaries/editions/hearings_sum_<case>.pages.json``.
    """
    source_path = Path(source_path)
    editions_dir = source_path.parent / EDITIONS_DIRNAME
    stem = source_path.stem
    return (
        editions_dir / f"{stem}.pdf",
        editions_dir / f"{stem}.pages.json",
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _coverage_chars(text: str) -> list[tuple[str, int, int]]:
    """Content characters with their raw offsets and lengths.

    Returns ``(coverage char, raw offset, raw length)``. NFKC folds ligature
    glyphs per character (an fi/fl ligature extracts as one codepoint where
    the source has two letters, contributing two coverage characters at one
    raw offset); whitespace and format/control characters are ignored
    because the renderer may realize them as line breaks, collapses, or
    nothing at all (e.g. a long word wraps mid-word without a hyphen, which
    extraction joins with a space). Per-character normalization keeps the
    source and page streams comparable and lets every coverage character be
    traced back to its exact raw position.
    """
    chars: list[tuple[str, int, int]] = []
    for offset, char in enumerate(text):
        for normalized in unicodedata.normalize("NFKC", char):
            if normalized.isspace() or unicodedata.category(normalized) in {
                "Cc",
                "Cf",
            }:
                continue
            chars.append((normalized, offset, len(char)))
    return chars


def _coverage_stream(text: str) -> list[str]:
    """Content characters surviving rendering-equivalent normalization."""
    return [char for char, _offset, _length in _coverage_chars(text)]


def _relpath_inside_root(path: Path, root_dir: Path) -> str:
    """Return a safe POSIX path relative to ``root_dir`` or raise."""
    path = Path(path)
    root = Path(root_dir).resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SummaryEditionError(
            f"Edition path escapes the case bundle: category data withheld."
        ) from exc
    return resolved.relative_to(root).as_posix()


def _safe_bundle_relative(value: Any, root_dir: Path) -> Path:
    """Validate a sidecar path is relative and resolves inside the bundle."""
    if not isinstance(value, str) or not value.strip():
        raise SummaryEditionError("Edition path is missing or not a string.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise SummaryEditionError("Edition path must be relative and stay inside the bundle.")
    resolved = (Path(root_dir).resolve() / pure).resolve()
    root = Path(root_dir).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SummaryEditionError("Edition path escapes the case bundle.") from exc
    return resolved


# Recognized quotations are style-matched double quote pairs within one
# source line: straight quotes pair with straight quotes and curly quotes
# pair with curly quotes, mirroring Focus's display-time parser. Content
# must be nonempty; pairs whose content carries no rendering-visible
# character are left literal, as are unmatched delimiters. Nested
# quotations are not recursively stripped.
_QUOTE_PAIR_RE = re.compile(r'"([^"]+)"|“([^”]+)”')


@dataclass(frozen=True)
class _LineQuote:
    """A recognized quotation within one line's printable text.

    ``start``/``end`` delimit the quote *content* (without the outer
    delimiters) in the line's link-substituted printable text.
    """

    start: int
    end: int
    phrase: str


@dataclass(frozen=True)
class _LineAnalysis:
    printable: str
    links: tuple[tuple[int, int, int], ...]  # (start, end, target_page)
    quotes: tuple[_LineQuote, ...]


def _analyze_line(line: str) -> _LineAnalysis:
    """Analyze one source line into printable text, links, and quotes."""
    parts: list[str] = []
    links: list[tuple[int, int, int]] = []
    length = 0
    cursor = 0
    for match in RECORD_PAGE_LINK_RE.finditer(line):
        before = line[cursor : match.start()]
        parts.append(before)
        start = length + len(before)
        label = match.group(1)
        parts.append(label)
        links.append((start, start + len(label), int(match.group(2))))
        length = start + len(label)
        cursor = match.end()
    parts.append(line[cursor:])
    printable = "".join(parts)

    quotes: list[_LineQuote] = []
    for match in _QUOTE_PAIR_RE.finditer(printable):
        group = 1 if match.group(1) is not None else 2
        content_start, content_end = match.span(group)
        content = printable[content_start:content_end]
        if not _coverage_stream(content):
            continue
        extent_start = content_start - 1
        extent_end = content_end + 1
        recognized = True
        for link_start, link_end, _target in links:
            overlaps = link_start < extent_end and extent_start < link_end
            if not overlaps:
                continue
            link_inside_quote = (
                extent_start <= link_start and link_end <= content_end
            )
            quote_inside_link = (
                link_start <= extent_start and extent_end <= link_end
            )
            if not link_inside_quote and not quote_inside_link:
                recognized = False
                break
        if recognized:
            quotes.append(_LineQuote(content_start, content_end, content))
    return _LineAnalysis(printable=printable, links=tuple(links), quotes=tuple(quotes))


def _printable_line_analysis(
    line: str,
) -> tuple[str, tuple[tuple[int, int, int], ...], tuple[str, ...]]:
    """Printable form of one line: links collapse to labels and recognized
    quote delimiters are removed.

    Returns ``(transformed text, quote content spans, phrases)`` where the
    spans are ``(start, end, quote index)`` offsets into the transformed
    text and the phrases are indexed by quote index.
    """
    analysis = _analyze_line(line)
    removed = {
        position
        for quote in analysis.quotes
        for position in (quote.start - 1, quote.end)
    }
    transformed = "".join(
        char
        for index, char in enumerate(analysis.printable)
        if index not in removed
    )
    spans: list[tuple[int, int, int]] = []
    phrases: list[str] = []
    for index, quote in enumerate(analysis.quotes):
        # Each earlier quote removes exactly two positions (its delimiters),
        # plus this quote's opening delimiter, all strictly before this
        # quote's content start.
        delta = 2 * index + 1
        spans.append((quote.start - delta, quote.end - delta, index))
        phrases.append(quote.phrase)
    return transformed, tuple(spans), tuple(phrases)


def printable_source_lines(source_text: str) -> list[tuple[int, str]]:
    """Return ``(1-based source line, printable text)`` for nonblank lines.

    Trusted record-page links are replaced by their labels and recognized
    quoted phrases lose their outer double quote delimiters; that printable
    representation is exactly what the PDF body is expected to reproduce.
    The canonical ``.txt`` file is never modified.
    """
    printable: list[tuple[int, str]] = []
    for lineno, line in enumerate(source_text.splitlines(), start=1):
        transformed, _spans, _phrases = _printable_line_analysis(line)
        if transformed.strip():
            printable.append((lineno, transformed))
    return printable


def _build_html(source_text: str) -> tuple[str, dict[str, dict[str, Any]]]:
    paragraphs: list[str] = []
    registry: dict[str, dict[str, Any]] = {}
    counter = 0
    for lineno, line in enumerate(source_text.splitlines(), start=1):
        analysis = _analyze_line(line)
        if not analysis.printable.strip():
            continue
        text = analysis.printable
        # Per-position markup events. Recognized quote delimiters are skipped
        # entirely and their content is wrapped in <b>; quote recognition
        # guarantees tags nest properly (a quotation either fully contains a
        # link span or sits fully inside one), so closes always precede opens
        # at a shared boundary in the order: link close, bold close, bold
        # open, link open.
        skip: set[int] = set()
        bold_open: dict[int, bool] = {}
        bold_close: dict[int, bool] = {}
        for quote in analysis.quotes:
            skip.add(quote.start - 1)
            skip.add(quote.end)
            bold_open[quote.start] = True
            bold_close[quote.end] = True
        link_open_at: dict[int, tuple[int, int]] = {}  # start -> (target, end)
        link_close_at: dict[int, bool] = {}
        for link_start, link_end, target in analysis.links:
            link_open_at[link_start] = (target, link_end)
            link_close_at[link_end] = True

        pieces: list[str] = []
        for position in range(len(text) + 1):
            if link_close_at.get(position):
                pieces.append("</a>")
            if bold_close.get(position):
                pieces.append("</b>")
            if bold_open.get(position):
                pieces.append("<b>")
            if position in link_open_at:
                target, link_end = link_open_at[position]
                link_id = f"lnk-{counter}"
                counter += 1
                label = "".join(
                    text[index]
                    for index in range(position, link_end)
                    if index not in skip
                )
                registry[link_id] = {
                    "label": label,
                    "target": target,
                    "line": lineno,
                }
                pieces.append(f'<a href="page:{target}" id="{link_id}">')
            if position < len(text) and position not in skip:
                pieces.append(html.escape(text[position]))
        paragraphs.append(f'<p id="src-{lineno}">{"".join(pieces)}</p>')
    body = "<html><body>" + "".join(paragraphs) + "</body></html>"
    return body, registry


def _page_rect_fn() -> Any:
    def rectfn(_rect_num: int, _filled: Any) -> tuple[fitz.Rect, fitz.Rect, Any]:
        mediabox = fitz.Rect(0, 0, PAGE_WIDTH_PT, PAGE_HEIGHT_PT)
        body = fitz.Rect(
            MARGIN_PT,
            MARGIN_PT,
            PAGE_WIDTH_PT - MARGIN_PT,
            PAGE_HEIGHT_PT - MARGIN_PT,
        )
        return mediabox, body, fitz.Identity

    return rectfn


def _render_story_html(html_body: str) -> tuple[bytes, list[dict[str, Any]]]:
    css = _USER_CSS
    positions: list[dict[str, Any]] = []

    def positionfn(position: Any) -> None:
        positions.append(
            {
                "page": position.page_num,
                "id": position.id,
                "href": position.href,
                "rect": tuple(position.rect),
            }
        )

    story = fitz.Story(
        html=html_body, user_css=css, em=float(BODY_FONT_SIZE_PT)
    )
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    try:
        story.write(writer, _page_rect_fn(), positionfn=positionfn)
    finally:
        writer.close()
    return buffer.getvalue(), positions


def _page_body_text_and_chars(page: fitz.Page) -> tuple[str, list[tuple[str, tuple[float, float, float, float], int]]]:
    """Extract body text with per-character bounding boxes and offsets.

    Visual line wrapping inside a block is collapsed to single spaces while
    paragraph (block) boundaries become newlines. When the Story wraps a
    hyphenated compound at its hyphen, MuPDF renders a real, visible hyphen
    glyph but labels it ``U+00AD`` (soft hyphen) on extraction; it is
    normalized back to a plain ASCII hyphen so coverage checks, link label
    matching, and the sidecar text keep matching the source.
    """
    raw = page.get_text("rawdict")
    pieces: list[str] = []
    chars: list[tuple[str, tuple[float, float, float, float], int]] = []
    offset = 0
    first_block = True
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        if not first_block:
            pieces.append("\n")
            offset += 1
        first_block = False
        first_line = True
        for line in block.get("lines", []):
            if not first_line:
                pieces.append(" ")
                offset += 1
            first_line = False
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    glyph = char["c"]
                    if glyph == "\u00ad":
                        glyph = "-"
                    pieces.append(glyph)
                    chars.append((glyph, tuple(char["bbox"]), offset))
                    offset += len(glyph)
    return "".join(pieces), chars


def _map_links(
    positions: list[dict[str, Any]],
    registry: dict[str, dict[str, Any]],
    page_chars: dict[int, list[tuple[str, tuple[float, float, float, float], int]]],
    page_texts: dict[int, str],
) -> dict[int, list[SummaryLinkSpan]]:
    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    for position in positions:
        if not position.get("href") or not position.get("id"):
            continue
        key = (position["page"], position["id"])
        entry = grouped.setdefault(
            key, {"href": position["href"], "rects": []}
        )
        entry["rects"].append(position["rect"])

    mapped: dict[int, list[SummaryLinkSpan]] = {}
    for (page_number, link_id), entry in sorted(grouped.items()):
        info = registry.get(link_id)
        if info is None:
            raise SummaryEditionError(
                "Record-page link mapping failed: unknown layout element id."
            )
        label = str(info["label"])
        target = int(info["target"])
        if entry["href"] != f"page:{target}":
            raise SummaryEditionError(
                "Record-page link mapping failed: href target mismatch."
            )
        chars = page_chars.get(page_number, [])
        rects = entry["rects"]
        tolerance = _LINK_CHAR_CENTER_TOLERANCE_PT

        def chars_in_rect(rect: tuple[float, float, float, float]) -> list[Any]:
            rx0, ry0, rx1, ry1 = rect
            return [
                (char, bbox, offset)
                for char, bbox, offset in chars
                if rx0 - tolerance <= (bbox[0] + bbox[2]) / 2 <= rx1 + tolerance
                and ry0 - tolerance <= (bbox[1] + bbox[3]) / 2 <= ry1 + tolerance
            ]

        page_text = page_texts.get(page_number, "")

        def resolve_span(selected: list[Any]) -> tuple[int, int, str] | None:
            if not selected:
                return None
            start = min(offset for _char, _bbox, offset in selected)
            end = max(offset + len(char) for char, _bbox, offset in selected)
            window = page_text[start:end]
            if window != label:
                leading = len(window) - len(window.lstrip())
                trailing = len(window) - len(window.rstrip())
                start += leading
                end -= trailing
                window = page_text[start:end]
            if window == label:
                return (start, end, window)
            return None

        # A label can wrap across lines: MuPDF reports one rect per rendered
        # fragment plus zero-width boundary markers. Select per fragment;
        # zero-width markers select nothing useful, so skip them.
        solid_rects = [
            rect for rect in rects if rect[2] - rect[0] > _MIN_LINK_RECT_WIDTH_PT
        ]
        selected = [
            item for rect in solid_rects for item in chars_in_rect(rect)
        ]
        resolved = resolve_span(selected)
        if resolved is None:
            # Fallback: union bounding box of every reported rect.
            union = (
                min(rect[0] for rect in rects),
                min(rect[1] for rect in rects),
                max(rect[2] for rect in rects),
                max(rect[3] for rect in rects),
            )
            resolved = resolve_span(chars_in_rect(union))
        if resolved is None:
            raise SummaryEditionError(
                "Record-page link mapping failed: label did not map to exact page text."
            )
        start, end, _window = resolved
        mapped.setdefault(page_number, []).append(
            SummaryLinkSpan(label=label, target_page=target, start=start, end=end)
        )

    for spans in mapped.values():
        spans.sort(key=lambda span: (span.start, span.end))
    return mapped


def _add_footers(document: fitz.Document) -> bytes:
    total = document.page_count
    for page in document:
        label = FOOTER_TEMPLATE.format(n=page.number + 1, m=total)
        width = fitz.get_text_length(
            label, fontname="tiro", fontsize=FOOTER_FONT_SIZE_PT
        )
        page.insert_text(
            fitz.Point((PAGE_WIDTH_PT - width) / 2, PAGE_HEIGHT_PT - FOOTER_BASELINE_FROM_BOTTOM_PT),
            label,
            fontname="tiro",
            fontsize=FOOTER_FONT_SIZE_PT,
        )
    return document.tobytes()


def _align_source_detailed(
    printable: list[tuple[int, str, tuple[tuple[int, int, int], ...], tuple[str, ...]]],
    page_texts: dict[int, str],
) -> tuple[dict[int, tuple[int, int]], dict[int, list[SummaryQuoteSpan]]]:
    """Align page content to the printable source monotonically.

    Comparison is character-level after rendering-equivalent normalization
    (NFKC, whitespace-insensitive), so ligature substitution and mid-word
    line wraps do not falsely fail coverage. Alongside the per-page source
    line ranges, this derives each page's quote fragments: the recognized
    quotations' content characters are tracked through the same alignment
    and mapped back to exact raw offsets in the extracted page text, so a
    quotation wrapping across a paper-page boundary yields one fragment per
    page, each carrying the complete search phrase. Spans are never located
    by a global substring search, which would confuse repeated phrases.
    """
    source_stream: list[tuple[str, int, int | None]] = []
    phrases: list[str] = []
    for lineno, line, quote_spans, line_phrases in printable:
        base_quote_index = len(phrases)
        phrases.extend(line_phrases)
        for char, raw_offset, _raw_length in _coverage_chars(line):
            quote_index: int | None = None
            for start, end, index in quote_spans:
                if start <= raw_offset < end:
                    quote_index = base_quote_index + index
                    break
            source_stream.append((char, lineno, quote_index))

    page_stream: list[tuple[str, int]] = []
    page_cov: dict[int, list[tuple[str, int, int]]] = {}
    for page_number in sorted(page_texts):
        coverage = _coverage_chars(page_texts[page_number])
        page_cov[page_number] = coverage
        for char, _offset, _length in coverage:
            page_stream.append((char, page_number))

    if len(source_stream) != len(page_stream):
        raise SummaryEditionError(
            "Source coverage check failed: character count mismatch between "
            "source and PDF "
            f"({len(source_stream)} source, {len(page_stream)} PDF)."
        )
    for index, (source, page) in enumerate(zip(source_stream, page_stream)):
        if source[0] != page[0]:
            raise SummaryEditionError(
                "Source coverage check failed: content mismatch at character "
                f"{index + 1} on PDF page {page[1]}."
            )

    ranges: dict[int, tuple[int, int]] = {}
    quote_fragments: dict[int, list[SummaryQuoteSpan]] = {}
    cursor = 0
    consumed_lines: list[int] = []
    for page_number in sorted(page_texts):
        coverage = page_cov[page_number]
        char_count = len(coverage)

        # Group this page's coverage characters into maximal runs of equal
        # quote membership; each run maps back to raw offsets via the
        # per-character (offset, length) provenance.
        run_index: int | None = None
        run_start = 0
        for position, (_char, _offset, _length) in enumerate(coverage):
            quote_index = source_stream[cursor + position][2]
            if run_index is None or quote_index != run_index:
                if run_index is not None:
                    _append_quote_fragment(
                        quote_fragments,
                        page_number,
                        page_texts[page_number],
                        phrases,
                        coverage,
                        run_start,
                        position,
                        run_index,
                    )
                run_index = quote_index
                run_start = position
        if run_index is not None:
            _append_quote_fragment(
                quote_fragments,
                page_number,
                page_texts[page_number],
                phrases,
                coverage,
                run_start,
                char_count,
                run_index,
            )

        chunk = source_stream[cursor : cursor + char_count]
        cursor += char_count
        if chunk:
            lines = [lineno for _char, lineno, _quote in chunk]
            ranges[page_number] = (min(lines), max(lines))
            consumed_lines.extend(lines)
        else:
            if consumed_lines:
                ranges[page_number] = (consumed_lines[-1], consumed_lines[-1])
            else:
                ranges[page_number] = (0, 0)
    return ranges, quote_fragments


def _append_quote_fragment(
    quote_fragments: dict[int, list[SummaryQuoteSpan]],
    page_number: int,
    page_text: str,
    phrases: list[str],
    coverage: list[tuple[str, int, int]],
    start_position: int,
    end_position: int,
    quote_index: int,
) -> None:
    if quote_index is None or quote_index < 0 or quote_index >= len(phrases):
        return
    if end_position <= start_position:
        return
    start = coverage[start_position][1]
    end = coverage[end_position - 1][1] + coverage[end_position - 1][2]
    quote_fragments.setdefault(page_number, []).append(
        SummaryQuoteSpan(
            label=page_text[start:end],
            phrase=phrases[quote_index],
            start=start,
            end=end,
        )
    )


def _align_source_lines(
    printable: list[tuple[int, str]],
    page_texts: dict[int, str],
) -> dict[int, tuple[int, int]]:
    """Align page content to the printable source; line ranges only."""
    lines = [(lineno, line, (), ()) for lineno, line in printable]
    ranges, _fragments = _align_source_detailed(lines, page_texts)
    return ranges


def _expected_quote_spans(
    source_text: str,
    pages: Any,
) -> dict[int, list[tuple[int, int, str, str]]] | None:
    """Derive expected quote fragments from the source and sidecar texts.

    Returns ``None`` when the sidecar pages are structurally unusable (already
    reported separately) or the sidecar text does not cover the source.
    """
    printable_lines: list[
        tuple[int, str, tuple[tuple[int, int, int], ...], tuple[str, ...]]
    ] = []
    for lineno, line in enumerate(source_text.splitlines(), start=1):
        transformed, quote_spans, phrases = _printable_line_analysis(line)
        if transformed.strip():
            printable_lines.append((lineno, transformed, quote_spans, phrases))
    page_texts = {
        index + 1: entry.get("text", "")
        for index, entry in enumerate(pages)
        if isinstance(entry, dict) and isinstance(entry.get("text"), str)
    }
    if len(page_texts) != len(pages):
        return None
    try:
        _ranges, fragments = _align_source_detailed(printable_lines, page_texts)
    except SummaryEditionError:
        return None
    return {
        page_number: [
            (span.start, span.end, span.label, span.phrase)
            for span in spans
        ]
        for page_number, spans in fragments.items()
    }


def _declared_quote_spans(pages: Any) -> dict[int, list[tuple[int, int, str, str]]] | None:
    """Collect the declared per-page quote fields, or ``None`` if unusable."""
    declared: dict[int, list[tuple[int, int, str, str]]] = {}
    for index, entry in enumerate(pages):
        if not isinstance(entry, dict):
            return None
        raw_quotes = entry.get("quotes")
        if not isinstance(raw_quotes, list):
            return None
        collected: list[tuple[int, int, str, str]] = []
        for quote in raw_quotes:
            if not isinstance(quote, dict):
                return None
            start, end = quote.get("start"), quote.get("end")
            label, phrase = quote.get("label"), quote.get("phrase")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or not isinstance(label, str)
                or not isinstance(phrase, str)
            ):
                return None
            collected.append((start, end, label, phrase))
        declared[index + 1] = collected
    return declared


def build_summary_edition(
    kind: str,
    source_path: Path,
    root_dir: Path,
    source_text: str | None = None,
) -> SummaryEdition:
    """Render, extract, validate, and return one edition without publishing."""
    if kind not in SUMMARY_EDITION_KINDS:
        raise SummaryEditionError(f"Unknown summary edition category: {kind}")
    source_path = Path(source_path)
    if source_text is None:
        source_text = source_path.read_text(encoding="utf-8")

    html_body, registry = _build_html(source_text)
    base_pdf_bytes, positions = _render_story_html(html_body)
    document = fitz.open("pdf", base_pdf_bytes)
    try:
        page_texts: dict[int, str] = {}
        page_chars: dict[int, list[Any]] = {}
        for page in document:
            text, chars = _page_body_text_and_chars(page)
            page_texts[page.number + 1] = text
            page_chars[page.number + 1] = chars

        link_spans = _map_links(positions, registry, page_chars, page_texts)
        printable_lines: list[
            tuple[int, str, tuple[tuple[int, int, int], ...], tuple[str, ...]]
        ] = []
        for lineno, line in enumerate(source_text.splitlines(), start=1):
            transformed, quote_spans, phrases = _printable_line_analysis(line)
            if transformed.strip():
                printable_lines.append((lineno, transformed, quote_spans, phrases))
        line_ranges, quote_fragments = _align_source_detailed(
            printable_lines, page_texts
        )

        pages: list[SummaryPage] = []
        for page_number in sorted(page_texts):
            first_line, last_line = line_ranges.get(page_number, (0, 0))
            pages.append(
                SummaryPage(
                    page=page_number,
                    text=page_texts[page_number],
                    source_first_line=first_line,
                    source_last_line=last_line,
                    links=tuple(link_spans.get(page_number, [])),
                    quotes=tuple(quote_fragments.get(page_number, [])),
                )
            )

        final_pdf_bytes = _add_footers(document)
    finally:
        document.close()

    pdf_rel = _relpath_inside_root(
        summary_edition_output_paths(source_path)[0], root_dir
    )
    source_rel = _relpath_inside_root(source_path, root_dir)
    page_map: dict[str, Any] = {
        "artifact": PAGE_MAP_ARTIFACT,
        "schema_version": PAGE_MAP_SCHEMA_VERSION,
        "kind": kind,
        "layout": {
            "id": LAYOUT_ID,
            "page_width_pt": PAGE_WIDTH_PT,
            "page_height_pt": PAGE_HEIGHT_PT,
            "margin_pt": MARGIN_PT,
            "body_font_family": BODY_FONT_FAMILY,
            "body_font_size_pt": BODY_FONT_SIZE_PT,
            "body_line_height": BODY_LINE_HEIGHT,
            "paragraph_spacing_em": PARAGRAPH_SPACING_EM,
            "quote_presentation": QUOTE_PRESENTATION_POLICY,
            "footer": {
                "template": FOOTER_TEMPLATE,
                "font_family": FOOTER_FONT_FAMILY,
                "font_size_pt": FOOTER_FONT_SIZE_PT,
                "baseline_from_bottom_pt": FOOTER_BASELINE_FROM_BOTTOM_PT,
            },
        },
        "source": {
            "path": source_rel,
            "sha256": _sha256_bytes(source_text.encode("utf-8")),
        },
        "pdf": {
            "path": pdf_rel,
            "sha256": _sha256_bytes(final_pdf_bytes),
            "page_count": len(pages),
        },
        "pages": [
            {
                "page": page.page,
                "text": page.text,
                "source_first_line": page.source_first_line,
                "source_last_line": page.source_last_line,
                "links": [
                    {
                        "start": span.start,
                        "end": span.end,
                        "label": span.label,
                        "target_page": span.target_page,
                    }
                    for span in page.links
                ],
                "quotes": [
                    {
                        "start": span.start,
                        "end": span.end,
                        "label": span.label,
                        "phrase": span.phrase,
                    }
                    for span in page.quotes
                ],
            }
            for page in pages
        ],
    }

    edition = SummaryEdition(
        kind=kind,
        pdf_bytes=final_pdf_bytes,
        page_map=page_map,
        pages=tuple(pages),
    )
    errors = validate_edition_payload(
        edition.page_map,
        kind=kind,
        root_dir=root_dir,
        source_text=source_text,
        pdf_bytes=final_pdf_bytes,
    )
    if errors:
        raise SummaryEditionError(
            f"Summary edition validation failed for {kind}: {errors[0]}"
        )
    return edition


def validate_edition_payload(
    page_map: Any,
    *,
    kind: str,
    root_dir: Path,
    source_text: str | None = None,
    pdf_bytes: bytes | None = None,
) -> list[str]:
    """Validate a page-map payload structurally and against provided content.

    Returns a list of problems; an empty list means valid. Error strings never
    contain summary content.
    """
    errors: list[str] = []
    if not isinstance(page_map, dict):
        return ["Page map is not an object."]
    if page_map.get("artifact") != PAGE_MAP_ARTIFACT:
        errors.append("Page map artifact identifier mismatch.")
    if page_map.get("schema_version") != PAGE_MAP_SCHEMA_VERSION:
        errors.append("Page map schema version is unsupported.")
    if page_map.get("kind") != kind:
        errors.append("Page map category does not match the requested summary.")

    layout = page_map.get("layout")
    if not isinstance(layout, dict) or layout.get("id") != LAYOUT_ID:
        errors.append("Page map layout identifier mismatch.")
    else:
        for key, expected in (
            ("page_width_pt", PAGE_WIDTH_PT),
            ("page_height_pt", PAGE_HEIGHT_PT),
            ("margin_pt", MARGIN_PT),
            ("body_font_size_pt", BODY_FONT_SIZE_PT),
            ("body_line_height", BODY_LINE_HEIGHT),
            ("paragraph_spacing_em", PARAGRAPH_SPACING_EM),
        ):
            value = layout.get(key)
            if not isinstance(value, (int, float)) or abs(value - expected) > 1e-6:
                errors.append(f"Page map layout field {key} does not match the fixed layout.")
                break
        if layout.get("body_font_family") != BODY_FONT_FAMILY:
            errors.append("Page map layout field body_font_family does not match the fixed layout.")
        if layout.get("quote_presentation") != QUOTE_PRESENTATION_POLICY:
            errors.append(
                "Page map layout quote presentation policy does not match the fixed layout."
            )
        footer_layout = layout.get("footer")
        if not isinstance(footer_layout, dict):
            errors.append("Page map layout footer metadata is missing.")
        else:
            if footer_layout.get("template") != FOOTER_TEMPLATE:
                errors.append("Page map layout footer template does not match the fixed layout.")
            if footer_layout.get("font_family") != FOOTER_FONT_FAMILY:
                errors.append("Page map layout footer font family does not match the fixed layout.")
            for key, expected in (
                ("font_size_pt", FOOTER_FONT_SIZE_PT),
                ("baseline_from_bottom_pt", FOOTER_BASELINE_FROM_BOTTOM_PT),
            ):
                value = footer_layout.get(key)
                if not isinstance(value, (int, float)) or abs(value - expected) > 1e-6:
                    errors.append(
                        f"Page map layout footer field {key} does not match the fixed layout."
                    )
                    break

    source_info = page_map.get("source")
    pdf_info = page_map.get("pdf")
    if not isinstance(source_info, dict) or not isinstance(pdf_info, dict):
        errors.append("Page map source/pdf sections are missing.")
        return errors

    try:
        source_resolved = _safe_bundle_relative(source_info.get("path"), root_dir)
    except SummaryEditionError as exc:
        errors.append(str(exc))
        source_resolved = None
    try:
        pdf_resolved = _safe_bundle_relative(pdf_info.get("path"), root_dir)
    except SummaryEditionError as exc:
        errors.append(str(exc))
        pdf_resolved = None

    pages = page_map.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("Page map pages are missing or empty.")
        return errors

    expected_page_numbers = list(range(1, len(pages) + 1))
    if [entry.get("page") if isinstance(entry, dict) else None for entry in pages] != (
        expected_page_numbers
    ):
        errors.append("Page map page numbers are not consecutive starting at 1.")

    previous_last_line = 0
    for entry in pages:
        if not isinstance(entry, dict):
            errors.append("Page map page entry is not an object.")
            continue
        text = entry.get("text")
        if not isinstance(text, str):
            errors.append("Page map page text is missing.")
            continue
        first_line = entry.get("source_first_line")
        last_line = entry.get("source_last_line")
        if not isinstance(first_line, int) or not isinstance(last_line, int):
            errors.append("Page map source line range is missing.")
            continue
        if first_line < 0 or last_line < first_line:
            errors.append("Page map source line range is invalid.")
        elif first_line < previous_last_line and not (first_line == 0 and last_line == 0):
            errors.append("Page map source line ranges are not monotonic.")
        else:
            previous_last_line = last_line

        spans: list[tuple[int, int]] = []
        for link in entry.get("links", []):
            if not isinstance(link, dict):
                errors.append("Page map link entry is not an object.")
                continue
            start, end = link.get("start"), link.get("end")
            label, target = link.get("label"), link.get("target_page")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end > len(text)
                or start >= end
            ):
                errors.append("Page map link span is out of bounds.")
                continue
            if not isinstance(label, str) or text[start:end] != label:
                errors.append("Page map link span does not match its label.")
                continue
            if not isinstance(target, int) or target <= 0:
                errors.append("Page map link target is invalid.")
                continue
            spans.append((start, end))
        ordered = sorted(spans)
        for (prev_start, prev_end), (next_start, _next_end) in zip(
            ordered, ordered[1:]
        ):
            if next_start < prev_end:
                errors.append("Page map link spans overlap.")
                break

        # Schema v2 requires the quote-fragment array on every page. Quote
        # spans may overlap record-page link spans (explicit page-link
        # navigation takes precedence in Focus), but quote spans must not
        # overlap each other, and every label must be exact.
        raw_quotes = entry.get("quotes")
        if not isinstance(raw_quotes, list):
            errors.append("Page map quote spans are missing.")
            continue
        quote_spans: list[tuple[int, int]] = []
        valid_quotes: list[tuple[int, int, str, str]] = []
        for quote in raw_quotes:
            if not isinstance(quote, dict):
                errors.append("Page map quote entry is not an object.")
                continue
            start, end = quote.get("start"), quote.get("end")
            label, phrase = quote.get("label"), quote.get("phrase")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end > len(text)
                or start >= end
            ):
                errors.append("Page map quote span is out of bounds.")
                continue
            if not isinstance(label, str) or text[start:end] != label:
                errors.append("Page map quote span does not match its label.")
                continue
            if not isinstance(phrase, str) or not phrase:
                errors.append("Page map quote phrase is missing.")
                continue
            quote_spans.append((start, end))
            valid_quotes.append((start, end, label, phrase))
        ordered_quotes = sorted(quote_spans)
        for (prev_start, prev_end), (next_start, _next_end) in zip(
            ordered_quotes, ordered_quotes[1:]
        ):
            if next_start < prev_end:
                errors.append("Page map quote spans overlap.")
                break

    if source_text is not None:
        expected = _coverage_stream(
            " ".join(line for _lineno, line in printable_source_lines(source_text))
        )
        actual = _coverage_stream(
            " ".join(str(entry.get("text", "")) for entry in pages if isinstance(entry, dict))
        )
        if expected != actual:
            errors.append("Page map body text does not cover the printable source exactly.")
        # Complete mapping: every recognized quotation must appear as quote
        # spans derived from the same alignment, with identical fields.
        if not any("Page map body text does not cover" in error for error in errors):
            expected_quote_map = _expected_quote_spans(source_text, pages)
            declared_quote_map = _declared_quote_spans(pages)
            if expected_quote_map is not None and declared_quote_map is not None:
                mismatched = any(
                    expected_quote_map.get(number, [])
                    != declared_quote_map.get(number, [])
                    for number in range(1, len(pages) + 1)
                )
                if mismatched:
                    errors.append(
                        "Page map quote spans do not completely map the "
                        "recognized quotations."
                    )

    declared_source_hash = source_info.get("sha256")
    if source_text is not None:
        if not isinstance(declared_source_hash, str) or declared_source_hash.lower() != _sha256_bytes(
            source_text.encode("utf-8")
        ):
            errors.append("Page map source hash mismatch.")
    elif source_resolved is not None:
        if not source_resolved.exists():
            errors.append("Page map source text file is missing.")
        elif not isinstance(declared_source_hash, str) or declared_source_hash.lower() != _sha256_file(
            source_resolved
        ):
            errors.append("Page map source hash mismatch.")

    if pdf_bytes is not None:
        try:
            with fitz.open("pdf", pdf_bytes) as document:
                declared_count = pdf_info.get("page_count")
                if not isinstance(declared_count, int) or declared_count != (
                    document.page_count
                ):
                    errors.append("Page map page count does not match the PDF.")
                for page in document:
                    if (
                        abs(page.rect.width - PAGE_WIDTH_PT) > _GEOMETRY_TOLERANCE_PT
                        or abs(page.rect.height - PAGE_HEIGHT_PT) > _GEOMETRY_TOLERANCE_PT
                    ):
                        errors.append("PDF page geometry is not US Letter portrait.")
                        break
        except Exception:
            errors.append("Page map PDF could not be opened.")
    elif pdf_resolved is not None:
        if not pdf_resolved.exists():
            errors.append("Page map PDF file is missing.")
            declared_count = pdf_info.get("page_count")
            if not isinstance(declared_count, int) or declared_count != len(pages):
                errors.append("Page map page count does not match declared pages.")
        else:
            declared_hash = pdf_info.get("sha256")
            if not isinstance(declared_hash, str) or declared_hash.lower() != _sha256_file(
                pdf_resolved
            ):
                errors.append("Page map PDF hash mismatch.")
            try:
                with fitz.open("pdf", pdf_resolved.read_bytes()) as document:
                    declared_count = pdf_info.get("page_count")
                    if not isinstance(declared_count, int) or declared_count != (
                        document.page_count
                    ):
                        errors.append("Page map page count does not match the PDF.")
                    for page in document:
                        if (
                            abs(page.rect.width - PAGE_WIDTH_PT) > _GEOMETRY_TOLERANCE_PT
                            or abs(page.rect.height - PAGE_HEIGHT_PT) > _GEOMETRY_TOLERANCE_PT
                        ):
                            errors.append("PDF page geometry is not US Letter portrait.")
                            break
            except Exception:
                errors.append("Page map PDF could not be opened.")

    return errors


def validate_summary_edition_files(
    kind: str,
    source_path: Path,
    root_dir: Path,
) -> list[str]:
    """Validate the published edition on disk against the current source."""
    source_path = Path(source_path)
    pdf_path, pages_path = summary_edition_output_paths(source_path)
    if not source_path.exists():
        return ["Source summary text file is missing."]
    if not pdf_path.exists() or not pages_path.exists():
        return ["Summary edition files are missing."]
    try:
        page_map = json.loads(pages_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["Page map sidecar is not valid JSON."]
    try:
        source_text = source_path.read_text(encoding="utf-8")
    except OSError:
        return ["Source summary text file could not be read."]
    return validate_edition_payload(
        page_map,
        kind=kind,
        root_dir=root_dir,
        source_text=source_text,
    )


def summary_edition_is_complete(
    kind: str,
    source_path: Path,
    root_dir: Path,
) -> bool:
    try:
        return not validate_summary_edition_files(kind, source_path, root_dir)
    except OSError:
        return False


def publish_summary_edition(edition: SummaryEdition, source_path: Path) -> None:
    """Atomically publish PDF then JSON sidecar via same-directory temp files."""
    pdf_path, pages_path = summary_edition_output_paths(source_path)
    editions_dir = pdf_path.parent
    editions_dir.mkdir(parents=True, exist_ok=True)
    pdf_tmp = pages_tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=editions_dir, suffix=".pdf", delete=False
        ) as handle:
            handle.write(edition.pdf_bytes)
            pdf_tmp = Path(handle.name)
        with tempfile.NamedTemporaryFile(
            dir=editions_dir, suffix=".json", delete=False
        ) as handle:
            handle.write(
                json.dumps(edition.page_map, indent=2, ensure_ascii=False).encode(
                    "utf-8"
                )
            )
            pages_tmp = Path(handle.name)
        os.replace(pdf_tmp, pdf_path)
        pdf_tmp = None
        os.replace(pages_tmp, pages_path)
        pages_tmp = None
    finally:
        for leftover in (pdf_tmp, pages_tmp):
            if leftover is not None:
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass


def remove_summary_edition(source_path: Path) -> None:
    """Remove one category's generated edition files, if present."""
    pdf_path, pages_path = summary_edition_output_paths(source_path)
    for path in (pdf_path, pages_path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
