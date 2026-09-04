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
  labels). Nothing may be dropped, duplicated, or reordered.
- Record-page link spans are exact character offsets into the extracted page
  text and are verified against their declared labels. Ambiguous or lost
  mappings fail generation instead of silently dropping a Focus link.
- All other text is HTML-escaped, so model output can never become executable
  HTML, load external resources, or alter pagination semantics.
- The layout is fixed (Letter portrait, 72pt margins, 12pt serif body). Page
  ``N of M`` footers are drawn inside the bottom margin and are excluded from
  page body text.

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
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import fitz

EDITIONS_DIRNAME = "editions"
PAGE_MAP_ARTIFACT = "recordprep-summary-pages"
PAGE_MAP_SCHEMA_VERSION = 1
SUMMARY_EDITION_KINDS: tuple[str, ...] = ("hearings", "reports", "minutes")

LAYOUT_ID = "recordprep-summary-letter-v1"
PAGE_WIDTH_PT = 612.0
PAGE_HEIGHT_PT = 792.0
MARGIN_PT = 72.0
BODY_FONT_SIZE_PT = 12.0
BODY_FONT_FAMILY = "serif"
FOOTER_FONT_SIZE_PT = 9.0
FOOTER_BASELINE_FROM_BOTTOM_PT = 36.0
FOOTER_TEMPLATE = "Page {n} of {m}"

# RecordPrep's trusted record-page link syntax. Anything else is literal text.
RECORD_PAGE_LINK_RE = re.compile(r"\[([^\]\[\n]+)\]\(page:(\d+)\)")

_USER_CSS = "body{font-family:serif;}"
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
class SummaryPage:
    """One validated PDF page of a summary edition."""

    page: int
    text: str
    source_first_line: int
    source_last_line: int
    links: tuple[SummaryLinkSpan, ...] = ()


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


def printable_source_lines(source_text: str) -> list[tuple[int, str]]:
    """Return ``(1-based source line, printable text)`` for nonblank lines.

    Trusted record-page links are replaced by their labels; that printable
    representation is exactly what the PDF body is expected to reproduce.
    """
    printable: list[tuple[int, str]] = []
    for lineno, line in enumerate(source_text.splitlines(), start=1):
        clean = RECORD_PAGE_LINK_RE.sub(lambda match: match.group(1), line)
        if clean.strip():
            printable.append((lineno, clean))
    return printable


def _build_html(source_text: str) -> tuple[str, dict[str, dict[str, Any]]]:
    paragraphs: list[str] = []
    registry: dict[str, dict[str, Any]] = {}
    counter = 0
    for lineno, line in enumerate(source_text.splitlines(), start=1):
        clean = RECORD_PAGE_LINK_RE.sub(lambda match: match.group(1), line)
        if not clean.strip():
            continue
        pieces: list[str] = []
        cursor = 0
        for match in RECORD_PAGE_LINK_RE.finditer(line):
            label = match.group(1)
            target = int(match.group(2))
            link_id = f"lnk-{counter}"
            registry[link_id] = {"label": label, "target": target, "line": lineno}
            pieces.append(html.escape(line[cursor : match.start()]))
            pieces.append(
                f'<a href="page:{target}" id="{link_id}">{html.escape(label)}</a>'
            )
            cursor = match.end()
            counter += 1
        pieces.append(html.escape(line[cursor:]))
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


def _render_story_html(
    html_body: str,
) -> tuple[bytes, list[dict[str, Any]]]:
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

    story = fitz.Story(html=html_body, user_css=_USER_CSS, em=int(BODY_FONT_SIZE_PT))
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
    paragraph (block) boundaries become newlines.
    """
    raw = page.get_text("rawdict")
    pieces: list[str] = []
    chars: list[tuple[str, tuple[float, float, float, float], int]] = []
    first_block = True
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        if not first_block:
            pieces.append("\n")
        first_block = False
        first_line = True
        for line in block.get("lines", []):
            if not first_line:
                pieces.append(" ")
            first_line = False
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    offset = sum(len(piece) for piece in pieces)
                    pieces.append(char["c"])
                    chars.append((char["c"], tuple(char["bbox"]), offset))
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
        x = (PAGE_WIDTH_PT - width) / 2
        y = PAGE_HEIGHT_PT - FOOTER_BASELINE_FROM_BOTTOM_PT
        page.insert_text(
            fitz.Point(x, y),
            label,
            fontname="tiro",
            fontsize=FOOTER_FONT_SIZE_PT,
        )
    return document.tobytes()


def _align_source_lines(
    printable: list[tuple[int, str]],
    page_texts: dict[int, str],
) -> dict[int, tuple[int, int]]:
    """Align page tokens to the printable source token stream monotonically."""
    source_tokens: list[tuple[str, int]] = []
    for lineno, line in printable:
        for token in line.split():
            source_tokens.append((token, lineno))

    page_tokens: list[tuple[str, int]] = []
    for page_number in sorted(page_texts):
        for token in page_texts[page_number].split():
            page_tokens.append((token, page_number))

    if len(source_tokens) != len(page_tokens):
        raise SummaryEditionError(
            "Source coverage check failed: token count mismatch between source and PDF."
        )
    for index, (source, page) in enumerate(zip(source_tokens, page_tokens)):
        if source[0] != page[0]:
            raise SummaryEditionError(
                "Source coverage check failed: content mismatch at token "
                f"{index + 1} on PDF page {page[1]}."
            )

    ranges: dict[int, tuple[int, int]] = {}
    cursor = 0
    consumed_lines: list[int] = []
    for page_number in sorted(page_texts):
        token_count = len(page_texts[page_number].split())
        chunk = source_tokens[cursor : cursor + token_count]
        cursor += token_count
        if chunk:
            lines = [lineno for _token, lineno in chunk]
            ranges[page_number] = (min(lines), max(lines))
            consumed_lines.extend(lines)
        else:
            if consumed_lines:
                ranges[page_number] = (consumed_lines[-1], consumed_lines[-1])
            else:
                ranges[page_number] = (0, 0)
    return ranges


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
        printable = printable_source_lines(source_text)
        line_ranges = _align_source_lines(printable, page_texts)

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
            "footer": FOOTER_TEMPLATE,
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
        ):
            value = layout.get(key)
            if not isinstance(value, (int, float)) or abs(value - expected) > 1e-6:
                errors.append(f"Page map layout field {key} does not match the fixed layout.")
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

    if source_text is not None:
        expected = _normalize_text(
            " ".join(line for _lineno, line in printable_source_lines(source_text))
        )
        actual = _normalize_text(
            " ".join(str(entry.get("text", "")) for entry in pages if isinstance(entry, dict))
        )
        if expected != actual:
            errors.append("Page map body text does not cover the printable source exactly.")

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
