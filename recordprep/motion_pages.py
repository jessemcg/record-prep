"""Explicit motion starts only; historical runs never imply motion papers."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .report_pages import ReportRange, _page_type, _value, report_ranges

MOTION_TYPES = frozenset({"ct_motion", "ct_motion_first_page"})
MOTION_FIRST_FIELD = "motion_first_page"


def motion_check_signature(entries: Iterable[dict]) -> list[tuple[str, str, object]]:
    return sorted(((_value(row, "filename"), _page_type(row), row.get(MOTION_FIRST_FIELD))
                   for row in entries if _page_type(row) in MOTION_TYPES),
                  key=lambda item: (item[0], item[1], str(item[2])))


def motion_detection_mode(entries: Iterable[dict], *, required: bool = False) -> bool:
    motions = [row for row in entries if _page_type(row) in MOTION_TYPES]
    modern = any(MOTION_FIRST_FIELD in row or _page_type(row) == "ct_motion_first_page"
                 for row in motions)
    if modern or required:
        for row in motions:
            expected = "yes" if _page_type(row) == "ct_motion_first_page" else "no"
            if row.get(MOTION_FIRST_FIELD) != expected:
                raise ValueError("Motion first-page checks are missing or inconsistent. Run Advanced "
                                 "classification and Dates before Names; prior output is preserved.")
    return modern


def motion_preparation_available(root: Path, rows: Iterable[dict]) -> bool:
    """Explicit per-motion flags prove nonempty coverage. Zero requires a new
    Advanced checkpoint, not an inference from historical absence of motions.
    """
    import hashlib
    import json
    rows = list(rows)
    if motion_detection_mode(rows):
        return True
    if any(_page_type(row) in MOTION_TYPES for row in rows):
        return False
    try:
        directory = root / 'classification'
        metadata = json.loads((directory / 'profile-advanced.json').read_text(encoding='utf-8'))
        outputs = metadata.get('outputs')
        return (type(metadata.get('motion_checks_version')) is int and metadata['motion_checks_version'] == 1
                and isinstance(outputs, dict) and bool(outputs)
                and all(Path(name).name == name and
                        hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
                        for name, digest in outputs.items()))
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def motion_ranges(entries: Iterable[tuple[str, str, int]], split_page: int) -> list[ReportRange]:
    # Reuse the interval algorithm, never its historical run-start inference.
    mapped = ((filename, {"ct_motion": "ct_report", "ct_motion_first_page": "ct_report_first_page"}
               .get(kind.lower(), ""), number) for filename, kind, number in entries)
    return [span for span in report_ranges(mapped, split_page, modern=True) if span.start_detected]


def build_motion_boundaries(rows: Iterable[dict], split_page: int) -> list[dict]:
    rows = list(rows)
    motion_detection_mode(rows)
    by_file = {_value(row, "filename"): row for row in rows}
    entries = sorted(((name, _page_type(row), int(Path(name).stem))
                      for name, row in by_file.items() if Path(name).stem.isdecimal()), key=lambda item: item[2])
    result = []
    for span in motion_ranges(entries, split_page):
        row = by_file[span.start_file]
        name = _value(row, "name") or _value(row, "motionname")
        if not name:
            continue
        if len(name) > 1024:
            raise ValueError("Motion title exceeds 1,024 characters; prior boundaries preserved.")
        date = _value(row, "date")
        basis = row.get("date_basis", "unknown") if date else "unknown"
        if basis not in {"filed", "document", "unknown"}:
            raise ValueError("Motion date basis is invalid; prior boundaries preserved.")
        start, end = int(Path(span.start_file).stem), int(Path(span.end_file).stem)
        result.append({"start_page": f"{start:04d}", "end_page": f"{end:04d}",
                       "motion_id": f"motion:{start:04d}", "motion_name": name,
                       "motion_date": date, "motion_date_basis": basis,
                       "motion_label": f"{date} - {name}" if date else name,
                       **({"naming_rule_id": row["naming_rule_id"]} if row.get("naming_rule_id") else {})})
    return result
