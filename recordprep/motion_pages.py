"""Explicit motion starts only; historical runs never imply motion papers."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

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


def validated_pages(rows: Iterable[dict]) -> list[dict]:
    """Validate identities before indexing: even identical duplicates are errors."""
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid final classification page record.")
        identities = {}
        for key, value in row.items():
            normalized = re.sub(r"[^a-z0-9]+", "", str(key).lower())
            if normalized in {"filename", "pagetype"}:
                if normalized in identities and identities[normalized] != value:
                    raise ValueError("Conflicting final classification identity fields.")
                identities[normalized] = value
        name = _value(row, "filename")
        if not re.fullmatch(r"[0-9]{4,}\.txt", name) or int(Path(name).stem) < 1:
            raise ValueError("Invalid final classification page identity.")
        number = int(Path(name).stem)
        if name != f"{number:04d}.txt" or number in seen or not _page_type(row):
            raise ValueError("Duplicate/conflicting final classification page identity or missing type.")
        seen.add(number)
        result.append(row)
    motion_detection_mode(result)
    return sorted(result, key=lambda row: int(Path(_value(row, "filename")).stem))


def continuous_selection(rows: Iterable[dict], split_page: int = -1) -> tuple[list[dict], list[list[str]], list[str]]:
    """Pure maximal motion runs, beginning only at explicit named starts.

    Return physical boundaries, ordered packet IDs and omitted-fragment findings.
    Physical starts always survive internally, including empty-title continuations.
    No relationship, party, date or title comparison participates in membership.
    """
    rows = validated_pages(rows)
    motion_detection_mode(rows, required=True)
    components, packets, omitted = [], [], []
    packet = component = None
    previous = None
    for row in rows:
        number = int(Path(_value(row, "filename")).stem)
        kind = _page_type(row)
        is_motion = number > split_page and kind in MOTION_TYPES
        if not is_motion or previous != number - 1:
            packet = component = None
        if is_motion:
            start = kind == "ct_motion_first_page"
            title = _value(row, "name") or _value(row, "motionname")
            if packet is None and start and title:
                packet = []
                packets.append(packet)
            if packet is not None:
                if start:
                    date = _value(row, "date")
                    basis = row.get("date_basis", "unknown") if date else "unknown"
                    if len(title) > 1024 or not all(c.isprintable() for c in title):
                        raise ValueError("Invalid motion source title; prior output preserved.")
                    if not isinstance(basis, str) or basis not in {"filed", "document", "unknown"}:
                        raise ValueError("Invalid motion date basis; prior output preserved.")
                    component = {"start_page": f"{number:04d}", "end_page": f"{number:04d}",
                                 "motion_id": f"motion:{number:04d}", "motion_name": title,
                                 "motion_date": date, "motion_date_basis": basis,
                                 "motion_label": f"{date} - {title}" if date else title,
                                 **({"naming_rule_id": row["naming_rule_id"]} if row.get("naming_rule_id") else {})}
                    components.append(component)
                    packet.append(component["motion_id"])
                component["end_page"] = f"{number:04d}"
            else:
                omitted.append(number)
        previous = number if is_motion else None
    findings = []
    if omitted:
        ranges = []
        first = last = omitted[0]
        for number in omitted[1:]:
            if number != last + 1:
                ranges.append((first, last))
                first = number
            last = number
        ranges.append((first, last))
        # One bounded finding per fragment, no unbounded page-list messages.
        findings = [f"Omitted motion fragment: source pages {first}–{last} ({last - first + 1} pages); no usable named lead before interruption."
                    for first, last in ranges]
    return components, packets, findings


def motion_ranges(entries: Iterable[tuple[str, str, int]], split_page: int) -> list[ReportRange]:
    # Reuse the interval algorithm, never its historical run-start inference.
    mapped = ((filename, {"ct_motion": "ct_report", "ct_motion_first_page": "ct_report_first_page"}
               .get(kind.lower(), ""), number) for filename, kind, number in entries)
    return [span for span in report_ranges(mapped, split_page, modern=True) if span.start_detected]


def build_motion_boundaries(rows: Iterable[dict], split_page: int) -> list[dict]:
    rows = list(rows)
    motion_detection_mode(rows)
    by_file = {_value(row, "filename"): row for row in validated_pages(rows)}
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
