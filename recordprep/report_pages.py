"""Explicit report starts and range separation; no model, store or source writes."""
from __future__ import annotations

from dataclasses import dataclass
import re
from collections.abc import Iterable

REPORT_TYPES = frozenset({'ct_report', 'ct_report_first_page'})
REPORT_FIRST_FIELD = 'report_first_page'


def _value(entry: dict, key: str) -> str:
    values = {re.sub(r'[^a-z0-9]+', '', str(key).lower()): value for key, value in entry.items()}
    value = values.get(key, '')
    return value.strip() if isinstance(value, str) else ''


def _page_type(entry: dict) -> str:
    return _value(entry, 'pagetype').lower()


def report_check_signature(entries: Iterable[dict]) -> list[tuple[str, str, object]]:
    """Resume only a checkpoint carrying the same explicit report checks.

    Profile-era workspaces already freeze all inputs. This additionally prevents
    old canonical checkpoints in unassigned cases skipping the new report pass.
    """
    return sorted(((_value(entry, 'filename'), _page_type(entry), entry.get(REPORT_FIRST_FIELD))
                   for entry in entries if _page_type(entry) in REPORT_TYPES), key=lambda item: (item[0], item[1], str(item[2])))


def report_detection_mode(entries: Iterable[dict], *, required: bool = False) -> bool:
    """Validate complete yes/no checks, or identify untouched historical output.

    Positive markers alone cannot prove continuation pages were checked. New work
    records both outcomes so a partial/old checkpoint never silently counts as a
    negative check. Historical fully unmarked output remains consumable as stored.
    Explicit Names requires the new checks; downstream reading does not migrate it.
    """
    reports = [entry for entry in entries if _page_type(entry) in REPORT_TYPES]
    modern = any(REPORT_FIRST_FIELD in entry or _page_type(entry) == 'ct_report_first_page'
                 for entry in reports)
    if modern or required:
        for entry in reports:
            expected = 'yes' if _page_type(entry) == 'ct_report_first_page' else 'no'
            if entry.get(REPORT_FIRST_FIELD) != expected:
                raise ValueError('Report first-page checks are missing or inconsistent. Run Advanced classification, '
                                 'Correct classification, and Dates before Names; prior output is preserved.')
    return modern


@dataclass(frozen=True)
class ReportRange:
    start_file: str
    end_file: str
    start_detected: bool


def report_ranges(entries: Iterable[tuple[str, str, int]], split_page: int, *, modern: bool) -> list[ReportRange]:
    """Separate adjacent reports before applying names, never across gaps/types.

    Undetected leading/fragment pages are retained as unnamed ranges for omission
    diagnostics, never attached across a gap to a previously accepted report.
    Old saved classifications without checks keep their historical run semantics.
    """
    result = []
    start = end = None
    previous = None
    detected = False
    for filename, kind, number in entries:
        kind = kind.lower()
        is_report = number > split_page and kind in REPORT_TYPES
        fresh_start = modern and kind == 'ct_report_first_page'
        if start is not None and (not is_report or previous != number - 1 or fresh_start):
            result.append(ReportRange(start, end, detected))
            start = end = None
        if is_report:
            if start is None:
                start = filename
                detected = fresh_start or not modern
            end = filename
            previous = number
        else:
            previous = None
    if start is not None:
        result.append(ReportRange(start, end, detected))
    return result
