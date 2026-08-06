#!/usr/bin/env python3
"""Prepare and validate RecordPrep participant_index.json."""

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


def prepare(root: Path) -> Path:
    root = root.resolve(strict=False)
    artifacts = root / "artifacts"
    boundaries = read_json(artifacts / "hearing_boundaries.json")
    transcript = read_json(artifacts / "transcript_page_numbers.json")
    if not isinstance(boundaries, list) or not isinstance(transcript, dict):
        raise ValueError("Hearing boundaries and transcript numbering are required.")
    entries = transcript.get("entries") if isinstance(transcript.get("entries"), list) else []
    by_file_page: dict[int, dict[str, Any]] = {}
    for item in entries:
        if isinstance(item, dict):
            number = page_number(item.get("file_page") or item.get("file_name"))
            if number:
                by_file_page[number] = item

    index_pages: list[dict[str, Any]] = []
    for row in classification_rows(root):
        page_type = str(row.get("page_type") or row.get("classification") or row.get("type") or "")
        if page_type.casefold() != "rt_index":
            continue
        number = page_number(row.get("file_page") or row.get("page") or row.get("file_name"))
        entry = by_file_page.get(number, {})
        index_pages.append({
            "text_path": f"text_pages/{number:04d}.txt" if number else "",
            "file_page": number,
            "citation_label": str(entry.get("citation_label") or ""),
            "citation_key": str(entry.get("citation_key") or ""),
            "note": "Page classified as RT_index; inspect for witness/examination evidence.",
        })

    hearings: list[dict[str, Any]] = []
    for index, item in enumerate(boundaries, start=1):
        if not isinstance(item, dict):
            continue
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
            "candidate_index_pages": index_pages,
            "counsel": [],
            "witness_status": "unknown",
            "witness_evidence": [],
            "witnesses": [],
            "warnings": ["Participant review has not been completed."],
        })

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "record-participant-index",
        "hearings": hearings,
        "warnings": ["Participant review has not been completed."],
    }
    output = artifacts / "participant_index.json"
    write_json(output, payload)
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


def validate_payload(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["participant_index.json must be an object."]
    if payload.get("schema_version") != 1:
        issues.append("schema_version must be 1.")
    if payload.get("source") != "record-participant-index":
        issues.append("source must be record-participant-index.")
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
            _validate_evidence(person.get("evidence"), person_label, issues)
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


def validate(root: Path) -> list[str]:
    path = root.resolve(strict=False) / "artifacts" / "participant_index.json"
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"participant_index.json is missing or invalid: {exc}"]
    return validate_payload(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate"))
    parser.add_argument("case_bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(f"Wrote {prepare(args.case_bundle)}")
            return 0
        issues = validate(args.case_bundle)
        if issues:
            for issue in issues:
                print(f"participant-index validation: {issue}", file=sys.stderr)
            return 1
        print("participant_index.json is valid.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"participant-index failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
