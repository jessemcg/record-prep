"""Read-only, file-page display classification; never used for citations/navigation."""
from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .core import RecordLayout, TocCategory


class Category(StrEnum):
    HEARING = "hearing"
    REPORT = "report"
    MOTION = "motion"
    MINUTE_ORDER = "minute_order"
    FORM = "form"
    UNKNOWN = "unknown"


PALETTE = {
    Category.HEARING: ("#3F6696", "#8EB3D8"),
    Category.REPORT: ("#2C7A70", "#79B9AA"),
    Category.MOTION: ("#A04F5F", "#E39AA8"),
    Category.MINUTE_ORDER: ("#8A6944", "#C8AC84"),
    Category.FORM: ("#78618F", "#B6A1CD"),
}
LABELS = {Category.HEARING: "Hearing", Category.REPORT: "Report", Category.MOTION: "Motion",
          Category.MINUTE_ORDER: "Minute order", Category.FORM: "Procedural filing"}
PAGE_TYPES = {
    "rt_body": Category.HEARING, "rt_body_first_page": Category.HEARING,
    "ct_report": Category.REPORT, "ct_report_first_page": Category.REPORT,
    "ct_motion": Category.MOTION, "ct_motion_first_page": Category.MOTION,
    "ct_minute_order": Category.MINUTE_ORDER,
    "ct_minute_order_first_page": Category.MINUTE_ORDER,
    "ct_form": Category.FORM, "ct_form_first_page": Category.FORM,
}
HEADINGS = {"hearings": Category.HEARING, "reports": Category.REPORT, "motions": Category.MOTION,
            "minute orders": Category.MINUTE_ORDER, "forms": Category.FORM,
            "procedural filings": Category.FORM}

# Sidebar display order: Procedural filings stays on top, then the record categories in the
# same order as the Case Tools summary strip.
SIDEBAR_CATEGORY_ORDER = {
    Category.FORM: 0,
    Category.HEARING: 1,
    Category.REPORT: 2,
    Category.MOTION: 3,
    Category.MINUTE_ORDER: 4,
}


def sidebar_category_rank(title: object) -> int:
    return SIDEBAR_CATEGORY_ORDER.get(heading_category(title), len(SIDEBAR_CATEGORY_ORDER))


def normalize(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def positive_page(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        try:
            page = int(value.strip())
            return page if page > 0 else None
        except ValueError:
            pass
    return None


def heading_category(title: object) -> Category:
    return HEADINGS.get(normalize(title), Category.UNKNOWN)


def display_heading(title: str) -> str:
    """Translate only known headings; never rename source documents or stored keys."""
    return "PROC. FILINGS" if heading_category(title) == Category.FORM else title


@dataclass(frozen=True)
class Classification:
    category: Category = Category.UNKNOWN
    provenance: str = "none"
    status: str = "unknown"  # classified, unknown, or conflict
    record_type: str = ""

    @property
    def caption(self) -> str:
        label = LABELS.get(self.category, "Other" if self.record_type else "Unclassified")
        return f"{label} · {self.record_type}" if self.record_type else label


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def _page_rows(data: object, key: str) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        return []
    return [row for row in data[key] if isinstance(row, dict)]


def parse_ranges(data: object) -> tuple[tuple[int, int], ...]:
    """Dates (including report_date) deliberately play no role here."""
    spans = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        start, end = positive_page(row.get("start_page")), positive_page(row.get("end_page"))
        if start is not None and end is not None:
            spans.append((min(start, end), max(start, end)))
    return tuple(spans)


def _resolve(categories: set[Category], provenance: str, identities: set[str]) -> Classification:
    category = next(iter(categories)) if len(categories) == 1 else Category.UNKNOWN
    expected = "RT" if category == Category.HEARING else "CT" if category in PALETTE else ""
    conflict = len(categories) > 1 or len(identities) > 1 or bool(
        expected and identities and expected not in identities
    )
    identity = next(iter(identities)) if len(identities) == 1 else ""
    if conflict:
        return Classification(Category.UNKNOWN, provenance, "conflict", identity)
    return Classification(category, provenance,
                          "classified" if category != Category.UNKNOWN else "unknown", identity)


def with_toc_fallback(index: dict[int, Classification], toc: Iterable[TocCategory]) -> dict[int, Classification]:
    """Apply only accepted TOC metadata to an index without previous TOC guesses."""
    candidates: dict[int, set[Category]] = {}
    for section in toc:
        category = heading_category(section.title)
        if category == Category.UNKNOWN:
            continue
        for bookmark in section.bookmarks:
            page = positive_page(bookmark.page)
            if page in index:
                candidates.setdefault(page, set()).add(category)
    result = dict(index)
    for page, categories in candidates.items():
        base = index[page]
        if base.provenance == "none" and base.status != "conflict":
            result[page] = _resolve(categories, "toc", {base.record_type} if base.record_type else set())
    return result


def load_category_index(layout: RecordLayout, file_pages: Iterable[int],
                        toc: Iterable[TocCategory] = (), *,
                        require_nonconflicting_body: bool = False) -> dict[int, Classification]:
    pages = sorted({page for value in file_pages if (page := positive_page(value)) is not None})
    known = set(pages)
    types: list[dict[int, set[Category]]] = [{}, {}]
    identities: dict[int, set[str]] = {}
    for tier, (path, key) in enumerate(((layout.transcript_page_numbers_path, "entries"),
                                      (layout.source_map_path, "pages"))):
        data = _read_json(path)
        series = {}
        if isinstance(data, dict):
            for row in _page_rows(data, "citation_series") + _page_rows(data, "sequences"):
                series[str(row.get("series_id") or row.get("sequence_id") or "")] = row
        for row in _page_rows(data, key):
            page = positive_page(row.get("file_page"))
            if page not in known:
                continue
            values = identities.setdefault(page, set())
            series_row = series.get(str(row.get("citation_series_id") or row.get("series_id")
                                        or row.get("sequence_id") or ""), {})
            for raw in (row.get("record_type"), series_row.get("record_type")):
                identity = normalize(raw).upper()
                if identity in ("RT", "CT"):
                    values.add(identity)
            raw_type = row.get("page_type")
            if raw_type is None or (isinstance(raw_type, str) and not raw_type.strip()):
                continue
            token = normalize(raw_type)
            # Type prefixes themselves are metadata evidence, even on index/other pages.
            prefix = token.split("_", 1)[0].upper()
            if prefix in ("RT", "CT"):
                values.add(prefix)
            types[tier].setdefault(page, set()).add(PAGE_TYPES.get(token, Category.UNKNOWN))
    ranges: dict[int, set[Category]] = {}
    for category, path in ((Category.HEARING, layout.hearing_boundaries_path),
                           (Category.REPORT, layout.report_boundaries_path),
                           (Category.MOTION, layout.motion_boundaries_path),
                           (Category.MINUTE_ORDER, layout.minutes_boundaries_path)):
        for start, end in parse_ranges(_read_json(path)):
            for page in pages[bisect.bisect_left(pages, start):bisect.bisect_right(pages, end)]:
                ranges.setdefault(page, set()).add(category)
    index = {}
    for page in pages:
        category_set, provenance = set(), "none"
        for source, name in ((types[0], "transcript"), (types[1], "source_map"), (ranges, "boundary")):
            if page in source:
                category_set, provenance = source[page], name
                break
        if require_nonconflicting_body:
            # Reading requires agreement, unlike the historical sidebar's tier
            # precedence. Explicit cover/index/unknown types veto boundary guesses.
            evidence = [source[page] for source in (*types, ranges) if page in source]
            category_set = set().union(*evidence) if evidence else set()
        index[page] = _resolve(category_set, provenance, identities.get(page, set()))
    return with_toc_fallback(index, toc)
