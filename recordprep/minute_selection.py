"""Pure explicit-work minute selection. Historical artifact readers do not filter.

Dates establish selection eligibility, not document identity. Enumerate complete
ranges before partitioning so omitted starts still end the preceding candidate.
No source rows, stored labels or retained boundary metadata are rewritten.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

SELECTION_ID = "dated-minute-selection-1"
OMISSION_REASON = "minute_date_unresolved"
START = "ct_minute_order_first_page"
BODY = "ct_minute_order"


def recognized_date(value):
    """Return a calendar date or None, using the existing display-date formats."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+", " ", value.strip())
    cleaned = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+",
                     "", cleaned, flags=re.IGNORECASE)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


@dataclass(frozen=True)
class MinuteRange:
    start_file: str
    end_file: str
    date: object

    @property
    def source_range(self):
        return f"{self.start_file[:-4]}–{self.end_file[:-4]}"


def candidate_ranges(rows, split_page):
    """Enumerate explicit CT starts plus adjacent bodies, including undated ones.

    Reject malformed/duplicate page identities rather than treating corruption as
    an unresolved date. A leading body fragment never supplies an implicit start.
    """
    entries = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid minute-selection classification row.")
        name = row.get("file_name", row.get("filename"))
        kind = row.get("page_type", row.get("pagetype"))
        if not isinstance(name, str) or not re.fullmatch(r"[0-9]{4,}\.txt", name) or not isinstance(kind, str) or not kind.strip():
            raise ValueError("Invalid minute-selection page identity/type.")
        number = int(name[:-4])
        if number < 1 or number in seen:
            raise ValueError("Invalid/duplicate minute-selection source page.")
        seen.add(number)
        entries.append((number, name, kind.strip().lower(), row.get("date")))
    entries.sort()
    result = []
    index = 0
    while index < len(entries):
        number, name, kind, value = entries[index]
        index += 1
        if number <= split_page or kind != START:
            continue
        end = name
        last = number
        while index < len(entries):
            following, next_name, next_kind, _ = entries[index]
            if following != last + 1 or next_kind != BODY:
                break
            end, last = next_name, following
            index += 1
        result.append(MinuteRange(name, end, value))
    return result


def partition_candidates(candidates):
    eligible, omitted = [], []
    for candidate in candidates:
        (eligible if recognized_date(candidate.date) is not None else omitted).append(candidate)
    return eligible, omitted


def filter_boundaries(entries):
    """Explicit saved-boundary filtering; validate *all* structure before dates.

    Retained entries are the original objects, including all unknown metadata.
    Overlap, reversed extents and malformed ranges are errors, not omissions.
    """
    if not isinstance(entries, list):
        raise ValueError("Minute boundaries must be a list.")
    candidates = []
    spans = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid minute boundary entry.")
        pages = []
        for key, alias in (("start_page", "start"), ("end_page", "end")):
            value = entry.get(key) or entry.get(alias)
            if type(value) is int:
                value = str(value)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.txt)?", value):
                raise ValueError("Invalid minute boundary source range.")
            number = int(value.removesuffix(".txt"))
            if number < 1:
                raise ValueError("Invalid minute boundary source range.")
            pages.append(number)
        if pages[1] < pages[0]:
            raise ValueError("Reversed minute boundary source range.")
        spans.append(tuple(pages))
        candidates.append(MinuteRange(f"{pages[0]:04d}.txt", f"{pages[1]:04d}.txt", entry.get("date")))
    ordered = sorted(spans)
    if any(right[0] <= left[1] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping minute boundary source ranges.")
    kept = [entry for entry in entries if recognized_date(entry.get("date")) is not None]
    return kept, partition_candidates(candidates)[1]


def omission_messages(omitted, *, batch_size=20):
    """Bounded, source-prose-free activity messages; counts mean candidates."""
    if not omitted:
        return []
    messages = [f"{len(omitted)} minute candidates omitted: {OMISSION_REASON}. "
                "Source pages remain available; missing dates do not prove misclassification."]
    for start in range(0, len(omitted), batch_size):
        messages.append("Omitted minute source-page ranges: " + ", ".join(
            candidate.source_range for candidate in omitted[start:start+batch_size]) + ".")
    return messages


def omission_warnings(rows, split_page=-1):
    """Deterministic post-correction notes for a new receipt, never on load."""
    _, omitted = partition_candidates(candidate_ranges(rows, split_page))
    return [{"code": OMISSION_REASON, "file_name": item.start_file,
             "start_page": item.start_file[:-4], "end_page": item.end_file[:-4],
             "reason": f"Minute candidate source pages {item.source_range} have no recognized date and "
                       "will be omitted when downstream selections are rebuilt. Source pages remain "
                       "available; missing dates do not prove misclassification."} for item in omitted]
