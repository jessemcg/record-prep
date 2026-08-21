#!/usr/bin/env python3
"""Prepare, scope, and validate RecordPrep participant_index.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUSES = {"verified", "none", "unknown", "conflict"}
ROLE_IDS = {
    "mothers_counsel", "fathers_counsel", "alleged_fathers_counsel",
    "presumed_fathers_counsel", "parents_counsel", "minors_counsel",
    "county_counsel", "tribes_counsel", "guardian_ad_litem",
    "other_counsel", "unresolved_counsel",
}
EXAM_TYPES = {"direct", "cross", "redirect", "recross", "court", "continued", "other"}
PARTICIPANT_ROLE_IDS = {
    "mother", "father", "alleged_father", "presumed_father", "minor",
    "relative", "caregiver", "social_worker", "agency_representative",
    "judicial_officer", "interpreter", "audience_member",
    "other_participant", "unresolved_participant",
}
ATTENDANCE_STATUSES = {"present", "remote", "absent", "unknown"}
SPEAKING_STATUSES = {"spoke", "did_not_speak", "unknown"}
SWORN_STATUSES = {"sworn", "unsworn", "not_applicable", "unknown"}

TEMPLATE_WARNING = "Participant review has not been completed."

WORKLIST_RELATIVE = Path("temp") / ".participant_worklist.json"

MARKER_PATTERNS: list[tuple[str, str]] = [
    (
        "oath",
        r"\boath\b|\bswear\b|\bsworn\b|\baffirm\b|\baffirmed\b|"
        r"\bsolemnly\s+promise\b|\bdo\s+you\s+solemnly\b",
    ),
    (
        "examination",
        r"\bDIRECT\s+EXAMINATION\b|\bCROSS-EXAMINATION\b|"
        r"\bREDIRECT\s+EXAMINATION\b|\bRECROSS-EXAMINATION\b|"
        r"\bEXAMINATION\s+(?:BY|CONTINUED)\b",
    ),
    (
        "counsel",
        r"\battorneys?\s+for\b|\bcounsel\s+for\b|\bby\s+counsel\b|"
        r"\bappointed\s+counsel\b",
    ),
    (
        "attendance",
        r"\bappeared\b|\bappearance\b|\bpresent\s+in\s+court\b|"
        r"\bappear\w*\s+(?:by|through)\s+counsel\b|\bon\s+behalf\s+of\b",
    ),
    (
        "absence",
        r"\bfailed\s+to\s+appear\b|\babsent\b|\bnot\s+present\b|"
        r"\bwaiv\w*\s+appearance\b",
    ),
]
MARKER_PRIORITY = {
    "oath": 0,
    "examination": 1,
    "counsel": 2,
    "attendance": 3,
    "absence": 3,
}

WORKLIST_LIMITS = {
    "pages_per_read": 1,
    "first_pages_per_hearing": 3,
    "marker_pages_per_hearing": 12,
    "page_read_budget_per_hearing": 12,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def page_number(value: Any) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else 0


def citation_range(start: str, end: str) -> str:
    if not start:
        return ""
    return start if not end or end == start else f"{start}-{end}"


def classification_rows(root: Path) -> list[dict[str, Any]]:
    candidates = [
        root / "classification" / "RT_basic_advanced_corrected_dates_names.jsonl",
        root / "classification" / "CT_basic_advanced_corrected_dates_names.jsonl",
        root / "classification" / "final.jsonl",
        root / "classification" / "final_classification.jsonl",
        root / "classification" / "combined.jsonl",
    ]
    rows: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        if rows:
            break
    return rows


def transcript_entries(root: Path) -> list[dict[str, Any]]:
    transcript = read_json(root / "artifacts" / "transcript_page_numbers.json")
    entries = transcript.get("entries") if isinstance(transcript, dict) else None
    if not isinstance(entries, list):
        raise ValueError("Transcript numbering entries are required.")
    return [item for item in entries if isinstance(item, dict)]


def hearing_boundaries(root: Path) -> list[dict[str, Any]]:
    boundaries = read_json(root / "artifacts" / "hearing_boundaries.json")
    if not isinstance(boundaries, list):
        raise ValueError("Hearing boundaries are required.")
    return [item for item in boundaries if isinstance(item, dict)]


def load_required_context(root: Path) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    entries = transcript_entries(root)
    by_file_page: dict[int, dict[str, Any]] = {}
    for item in entries:
        number = page_number(item.get("file_page") or item.get("file_name"))
        if number:
            by_file_page[number] = item
    return hearing_boundaries(root), by_file_page


def prepare(root: Path) -> Path:
    root = root.resolve(strict=False)
    artifacts = root / "artifacts"
    boundaries, by_file_page = load_required_context(root)

    hearings: list[dict[str, Any]] = []
    for index, item in enumerate(boundaries, start=1):
        start = page_number(item.get("start_page"))
        end = page_number(item.get("end_page"))
        start_entry = by_file_page.get(start, {})
        end_entry = by_file_page.get(end, {})
        date = str(item.get("date") or item.get("hearing_date") or "").strip()
        hearings.append({
            "id": str(item.get("id") or f"hearing:{index:04d}"),
            "date": date,
            "start_page": start,
            "end_page": end,
            "start_citation_label": str(start_entry.get("citation_label") or ""),
            "end_citation_label": str(end_entry.get("citation_label") or ""),
            "citation_range": citation_range(
                str(start_entry.get("citation_label") or ""),
                str(end_entry.get("citation_label") or ""),
            ),
            "counsel": [],
            "participants": [],
            "witness_status": "unknown",
            "witness_evidence": [],
            "witnesses": [],
            "warnings": [TEMPLATE_WARNING],
        })

    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "record-participant-index",
        "hearings": hearings,
        "warnings": [TEMPLATE_WARNING],
    }
    output = artifacts / "participant_index.json"
    write_json(output, payload)
    return output


def scoped_index_pages(root: Path, by_file_page: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """RT_index-classified pages that belong to a reporter-transcript series."""
    index_pages: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in classification_rows(root):
        page_type = str(
            row.get("page_type") or row.get("classification") or row.get("type") or ""
        )
        if page_type.casefold() != "rt_index":
            continue
        number = page_number(row.get("file_page") or row.get("page") or row.get("file_name"))
        if not number or number in seen:
            continue
        seen.add(number)
        entry = by_file_page.get(number)
        if entry is None or str(entry.get("record_type") or "").casefold() != "rt":
            continue
        index_pages.append({
            "text_path": f"text_pages/{number:04d}.txt",
            "file_page": number,
            "citation_label": str(entry.get("citation_label") or ""),
            "citation_key": str(entry.get("citation_key") or ""),
        })
    index_pages.sort(key=lambda item: item["file_page"])
    return index_pages


def _page_markers(text: str) -> list[str]:
    found: list[str] = []
    for marker_name, pattern in MARKER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            found.append(marker_name)
    return found


def worklist(root: Path) -> Path:
    root = root.resolve(strict=False)
    boundaries, by_file_page = load_required_context(root)

    ranges: list[tuple[int, int, str]] = []
    for index, item in enumerate(boundaries, start=1):
        start = page_number(item.get("start_page"))
        end = page_number(item.get("end_page"))
        if not start or end < start:
            continue
        hearing_id = str(item.get("id") or f"hearing:{index:04d}")
        ranges.append((start, end, hearing_id))

    index_pages = scoped_index_pages(root, by_file_page)

    def citation_for(number: int) -> tuple[str, str]:
        entry = by_file_page.get(number, {})
        return (
            str(entry.get("citation_label") or ""),
            str(entry.get("citation_key") or ""),
        )

    def citation_page(number: int) -> dict[str, Any]:
        label, key = citation_for(number)
        return {
            "file_page": number,
            "citation_label": label,
            "citation_key": key,
            "text_path": f"text_pages/{number:04d}.txt",
        }

    # Scan only pages inside hearing ranges. Each text page is read once.
    markers_by_page: dict[int, tuple[int, list[str]]] = {}
    scanned: set[int] = set()
    for start, end, _hearing_id in ranges:
        for number in range(start, end + 1):
            if number in scanned:
                continue
            scanned.add(number)
            try:
                text = (root / "text_pages" / f"{number:04d}.txt").read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                continue
            markers = _page_markers(text)
            if not markers:
                continue
            priority = min(MARKER_PRIORITY[name] for name in markers)
            markers_by_page[number] = (priority, markers)

    in_range = {
        number
        for start, end, _hearing_id in ranges
        for number in range(start, end + 1)
    }

    hearing_entries: list[dict[str, Any]] = []
    for start, end, hearing_id in ranges:
        first_pages = [
            citation_page(number)
            for number in range(start, min(start + WORKLIST_LIMITS["first_pages_per_hearing"], end + 1))
        ]
        chosen_markers = sorted(
            (number for number in range(start, end + 1) if number in markers_by_page),
            key=lambda number: (markers_by_page[number][0], number),
        )[: WORKLIST_LIMITS["marker_pages_per_hearing"]]
        marker_pages = [
            {
                **citation_page(number),
                "markers": list(markers_by_page[number][1]),
            }
            for number in chosen_markers
        ]
        hearing_index_pages = [
            {**page}
            for page in index_pages
            if start <= page["file_page"] <= end
        ]
        hearing_entries.append({
            "id": hearing_id,
            "start_page": start,
            "end_page": end,
            "start_citation_label": str(by_file_page.get(start, {}).get("citation_label") or ""),
            "end_citation_label": str(by_file_page.get(end, {}).get("citation_label") or ""),
            "citation_range": citation_range(
                str(by_file_page.get(start, {}).get("citation_label") or ""),
                str(by_file_page.get(end, {}).get("citation_label") or ""),
            ),
            "first_pages": first_pages,
            "index_pages": hearing_index_pages,
            "marker_pages": marker_pages,
        })

    outside = [
        {**page}
        for page in index_pages
        if page["file_page"] not in in_range
    ]

    payload = {
        "artifact": "recordprep-participant-worklist",
        "schema_version": 1,
        "temporary": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "record-participant-index",
        "limits": dict(WORKLIST_LIMITS),
        "hearings": hearing_entries,
        "index_pages_outside_hearings": outside,
        "note": (
            "Nonauthoritative evidence scoping only. Inspect the original source "
            "pages referenced here before making any finding; this file never "
            "substitutes for record text and must be deleted when the stage finishes."
        ),
    }
    output = root / WORKLIST_RELATIVE
    write_json(output, payload)
    return output


def cleanup(root: Path) -> Path:
    root = root.resolve(strict=False)
    output = root / WORKLIST_RELATIVE
    output.unlink(missing_ok=True)
    return output


def _validate_evidence(value: Any, label: str, issues: list[str]) -> None:
    if not isinstance(value, list):
        issues.append(f"{label}.evidence must be a list.")
        return
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            issues.append(f"{label}.evidence[{index}] must be an object.")
            continue
        path = str(item.get("text_path") or "")
        if path and (Path(path).is_absolute() or ".." in Path(path).parts):
            issues.append(f"{label}.evidence[{index}] has an unsafe text_path.")


def _hearing_has_template_warning(hearing: dict[str, Any]) -> bool:
    warnings = hearing.get("warnings")
    return isinstance(warnings, list) and any(
        isinstance(item, str) and item == TEMPLATE_WARNING for item in warnings
    )


def validate_payload(payload: Any, *, partial: bool = False) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["participant_index.json must be an object."]
    if payload.get("schema_version") != 2:
        issues.append("schema_version must be 2.")
    if payload.get("source") != "record-participant-index":
        issues.append("source must be record-participant-index.")
    top_warnings = payload.get("warnings")
    if not partial and isinstance(top_warnings, list) and any(
        isinstance(item, str) and item == TEMPLATE_WARNING for item in top_warnings
    ):
        issues.append("the participant review has not been completed (template warning remains).")
    hearings = payload.get("hearings")
    if not isinstance(hearings, list) or not hearings:
        issues.append("hearings must be a nonempty list.")
        return issues
    ids: set[str] = set()
    for hearing_number, hearing in enumerate(hearings, start=1):
        label = f"hearing[{hearing_number}]"
        if not isinstance(hearing, dict):
            issues.append(f"{label} must be an object.")
            continue
        hearing_id = str(hearing.get("id") or "").strip()
        if not hearing_id or hearing_id in ids:
            issues.append(f"{label}.id must be nonempty and unique.")
        ids.add(hearing_id)
        start = page_number(hearing.get("start_page"))
        end = page_number(hearing.get("end_page"))
        if not start or end < start:
            issues.append(f"{label} has an invalid page range.")
        if partial and _hearing_has_template_warning(hearing):
            continue
        if not partial and _hearing_has_template_warning(hearing):
            issues.append(f"{label} has not been reviewed (template warning remains).")
        status = str(hearing.get("witness_status") or "")
        if status not in STATUSES:
            issues.append(f"{label}.witness_status is invalid.")
        counsel = hearing.get("counsel")
        if not isinstance(counsel, list):
            issues.append(f"{label}.counsel must be a list.")
            counsel = []
        for counsel_number, person in enumerate(counsel, start=1):
            person_label = f"{label}.counsel[{counsel_number}]"
            if not isinstance(person, dict):
                issues.append(f"{person_label} must be an object.")
                continue
            if str(person.get("role_id") or "") not in ROLE_IDS:
                issues.append(f"{person_label}.role_id is invalid.")
            if not str(person.get("name") or "").strip():
                issues.append(f"{person_label}.name is required.")
            if not isinstance(person.get("aliases"), list):
                issues.append(f"{person_label}.aliases must be a list.")
            if not isinstance(person.get("organization"), str):
                issues.append(f"{person_label}.organization must be a string.")
            if str(person.get("appearance_status") or "") not in {"present", "remote", "unknown"}:
                issues.append(f"{person_label}.appearance_status is invalid.")
            _validate_evidence(person.get("evidence"), person_label, issues)
            if not person.get("evidence"):
                issues.append(f"{person_label}.evidence must not be empty.")
        participants = hearing.get("participants")
        if not isinstance(participants, list):
            issues.append(f"{label}.participants must be a list.")
            participants = []
        participant_ids: set[str] = set()
        for participant_number, person in enumerate(participants, start=1):
            person_label = f"{label}.participants[{participant_number}]"
            if not isinstance(person, dict):
                issues.append(f"{person_label} must be an object.")
                continue
            participant_id = str(person.get("id") or "").strip()
            if not participant_id or participant_id in participant_ids:
                issues.append(f"{person_label}.id must be nonempty and unique within the hearing.")
            participant_ids.add(participant_id)
            if str(person.get("role_id") or "") not in PARTICIPANT_ROLE_IDS:
                issues.append(f"{person_label}.role_id is invalid.")
            if not str(person.get("role_label") or "").strip():
                issues.append(f"{person_label}.role_label is required.")
            if not isinstance(person.get("name"), str):
                issues.append(f"{person_label}.name must be a string.")
            if not isinstance(person.get("aliases"), list):
                issues.append(f"{person_label}.aliases must be a list.")
            if str(person.get("attendance_status") or "") not in ATTENDANCE_STATUSES:
                issues.append(f"{person_label}.attendance_status is invalid.")
            if str(person.get("speaking_status") or "") not in SPEAKING_STATUSES:
                issues.append(f"{person_label}.speaking_status is invalid.")
            if str(person.get("sworn_status") or "") not in SWORN_STATUSES:
                issues.append(f"{person_label}.sworn_status is invalid.")
            _validate_evidence(person.get("evidence"), person_label, issues)
            if not person.get("evidence"):
                issues.append(f"{person_label}.evidence must not be empty.")
        witness_evidence = hearing.get("witness_evidence")
        _validate_evidence(witness_evidence, f"{label}.witness", issues)
        witnesses = hearing.get("witnesses")
        if not isinstance(witnesses, list):
            issues.append(f"{label}.witnesses must be a list.")
            witnesses = []
        if status in {"none", "unknown"} and witnesses:
            issues.append(f"{label} cannot list witnesses when status is {status}.")
        if status == "none" and not witness_evidence:
            issues.append(f"{label} must cite witness_evidence when status is none.")
        if status == "verified" and not witnesses:
            issues.append(f"{label} must list a witness when status is verified.")
        if status == "conflict" and not hearing.get("warnings"):
            issues.append(f"{label} must explain conflict status in warnings.")
        witness_ids: set[str] = set()
        counsel_names = {str(item.get("name") or "").casefold() for item in counsel if isinstance(item, dict)}
        for witness_number, witness in enumerate(witnesses, start=1):
            witness_label = f"{label}.witnesses[{witness_number}]"
            if not isinstance(witness, dict):
                issues.append(f"{witness_label} must be an object.")
                continue
            witness_id = str(witness.get("id") or "").strip()
            name = str(witness.get("name") or "").strip()
            if not witness_id or witness_id in witness_ids:
                issues.append(f"{witness_label}.id must be nonempty and unique within the hearing.")
            witness_ids.add(witness_id)
            if not name:
                issues.append(f"{witness_label}.name is required.")
            if name.casefold() in counsel_names and status != "conflict":
                issues.append(f"{witness_label} matches counsel and must be marked as a conflict.")
            _validate_evidence(witness.get("evidence"), witness_label, issues)
            examinations = witness.get("examinations")
            if not isinstance(examinations, list) or not examinations:
                issues.append(f"{witness_label}.examinations must be a nonempty list.")
                continue
            previous_start = 0
            for exam_number, exam in enumerate(examinations, start=1):
                exam_label = f"{witness_label}.examinations[{exam_number}]"
                if not isinstance(exam, dict):
                    issues.append(f"{exam_label} must be an object.")
                    continue
                if str(exam.get("type") or "") not in EXAM_TYPES:
                    issues.append(f"{exam_label}.type is invalid.")
                role_id = str(exam.get("examiner_role_id") or "")
                if role_id and role_id not in ROLE_IDS:
                    issues.append(f"{exam_label}.examiner_role_id is invalid.")
                exam_start = page_number(exam.get("start_file_page"))
                exam_end = page_number(exam.get("end_file_page"))
                if exam_start and not (start <= exam_start <= end):
                    issues.append(f"{exam_label}.start_file_page is outside the hearing.")
                if exam_end and (not exam_start or exam_end < exam_start or exam_end > end):
                    issues.append(f"{exam_label}.end_file_page is invalid.")
                if exam_start and previous_start and exam_start < previous_start:
                    issues.append(f"{exam_label} is out of order.")
                previous_start = exam_start or previous_start
                _validate_evidence(exam.get("evidence"), exam_label, issues)
    return list(dict.fromkeys(issues))


def validate(root: Path, *, partial: bool = False) -> list[str]:
    path = root.resolve(strict=False) / "artifacts" / "participant_index.json"
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"participant_index.json is missing or invalid: {exc}"]
    return validate_payload(payload, partial=partial)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "worklist", "cleanup", "validate"))
    parser.add_argument("case_bundle", type=Path)
    parser.add_argument(
        "--partial",
        action="store_true",
        help="validate only the hearings reviewed so far (permits template warnings).",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(f"Wrote {prepare(args.case_bundle)}")
            return 0
        if args.command == "worklist":
            print(f"Wrote {worklist(args.case_bundle)}")
            return 0
        if args.command == "cleanup":
            print(f"Removed {cleanup(args.case_bundle)}")
            return 0
        issues = validate(args.case_bundle, partial=args.partial)
        if issues:
            for issue in issues:
                print(f"participant-index validation: {issue}", file=sys.stderr)
            return 1
        if args.partial:
            print("participant_index.json partial validation passed.")
        else:
            print("participant_index.json is valid.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"participant-index failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
