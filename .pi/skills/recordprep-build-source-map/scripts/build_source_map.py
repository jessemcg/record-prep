#!/usr/bin/env python3
"""Build citation-aware source-map v2 directly from RecordPrep source pages."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SOURCE_MAP_SCHEMA_VERSION = 2
LEGACY_FILE_KEYS = {
    "raw_hearings", "raw_reports", "preoptimized_hearings", "preoptimized_reports",
    "optimized_hearings", "optimized_reports", "optimized_hearing_sections",
    "optimized_report_sections", "chunk_metadata", "organized_hearings",
    "organized_reports", "vector_database",
}


def natural_key(value: str | Path) -> list[object]:
    name = value.name if isinstance(value, Path) else Path(str(value)).name
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        value = read_json(path)
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def relpath(root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def page_number(value: Any) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else 0


def date_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def citation_range(start: str, end: str) -> str:
    return start if start and (not end or start == end) else f"{start}-{end}" if start else ""


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is missing or invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object.")
    return payload


def validated_case_overview_path(root: Path) -> str:
    path = root / "artifacts" / "case_overview.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileNotFoundError("artifacts/case_overview.md is missing or unreadable.") from exc
    required = (
        "artifact: recordprep-case-overview",
        "schema_version: 1",
        "status: nonauthoritative-orientation",
        "# Case Overview",
        "> Orientation aid only.",
    )
    if any(fragment not in text for fragment in required):
        raise ValueError("artifacts/case_overview.md is malformed.")
    return relpath(root, path)


def summary_paths(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    result: dict[str, str] = {}
    for kind in ("hearings", "reports", "minutes"):
        configured = files.get(f"summarized_{kind}")
        source = root / configured if isinstance(configured, str) and configured else None
        if source is None or not source.is_file():
            matches = sorted(
                (path for path in (root / "summaries").glob(f"*{kind}*.txt") if "_organized" not in path.stem),
                key=natural_key,
            )
            source = matches[0] if len(matches) == 1 else None
        if source and source.is_file():
            result[f"summarized_{kind}"] = relpath(root, source)
    for required in ("summarized_hearings", "summarized_reports"):
        if required not in result:
            raise FileNotFoundError(f"{required.replace('_', ' ')} not found.")
    return result


def build_pages(root: Path, transcript: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[str]]:
    entries = transcript.get("entries") if isinstance(transcript.get("entries"), list) else []
    by_name = {
        str(item.get("file_name") or ""): item
        for item in entries if isinstance(item, dict) and str(item.get("file_name") or "")
    }
    pages: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted((root / "text_pages").glob("[0-9][0-9][0-9][0-9].txt"), key=natural_key):
        entry = by_name.get(path.name, {})
        number = page_number(entry.get("file_page") or path.stem)
        image = root / "image_pages" / f"{path.stem}.png"
        page = {
            "file_name": path.name,
            "file_page": number,
            "text_path": relpath(root, path),
            "image_path": relpath(root, image) if image.is_file() else "",
            "record_type": str(entry.get("record_type") or ""),
            "page_type": str(entry.get("page_type") or ""),
            "transcript_page_number": entry.get("transcript_page_number"),
            "transcript_page_label": str(entry.get("transcript_page_label") or ""),
            "citation_series_id": str(entry.get("citation_series_id") or ""),
            "citation_prefix": str(entry.get("citation_prefix") or ""),
            "citation_label": str(entry.get("citation_label") or ""),
            "citation_key": str(entry.get("citation_key") or ""),
            "status": str(entry.get("status") or ""),
            "confidence": str(entry.get("confidence") or ""),
            "method": str(entry.get("method") or ""),
            "document_ids": [],
            "hearing_id": "",
            "counsel_roles": [],
            "participants": [],
            "witnesses": [],
            "examinations": [],
        }
        if not page["citation_key"]:
            warnings.append(f"No citation key for {path.name}.")
        pages.append(page)
    return pages, {int(page["file_page"]): page for page in pages}, warnings


def boundary_documents(root: Path, pages_by_number: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    specifications = (
        ("hearing", "hearing_boundaries.json"),
        ("report", "report_boundaries.json"),
        ("minute_order", "minutes_boundaries.json"),
    )
    documents: list[dict[str, Any]] = []
    for doc_type, file_name in specifications:
        for index, item in enumerate(read_json_list(root / "artifacts" / file_name), start=1):
            start = page_number(item.get("start_page"))
            end = page_number(item.get("end_page"))
            start_page = pages_by_number.get(start, {})
            end_page = pages_by_number.get(end, {})
            date = str(item.get("date") or item.get("hearing_date") or item.get("report_date") or "").strip()
            report_id = str(item.get("report_id") or "").strip()
            label = str(
                item.get("report_label") or item.get("report_name") or date
                or f"{doc_type.replace('_', ' ').title()} {index}"
            ).strip()
            doc_id = str(item.get("id") or report_id or f"{doc_type}:{index:04d}")
            documents.append({
                "id": doc_id,
                "type": doc_type,
                "label": label,
                "date": date,
                "date_key": date_key(date),
                "report_name": str(item.get("report_name") or ""),
                "report_date": str(item.get("report_date") or ""),
                "report_label": str(item.get("report_label") or ""),
                "report_id": report_id,
                "start_page": start,
                "end_page": end,
                "start_file": f"{start:04d}.txt" if start else "",
                "end_file": f"{end:04d}.txt" if end else "",
                "start_citation_label": str(start_page.get("citation_label") or ""),
                "end_citation_label": str(end_page.get("citation_label") or ""),
                "citation_range": citation_range(
                    str(start_page.get("citation_label") or ""),
                    str(end_page.get("citation_label") or ""),
                ),
                "page_labels": [f"{number:04d}" for number in range(start, end + 1)] if start and end >= start else [],
                "aliases": sorted({value for value in (label, date, report_id, str(item.get("report_name") or ""), str(item.get("report_label") or "")) if value}),
                "metadata": item,
            })
    return documents


def annotate_pages(
    pages_by_number: dict[int, dict[str, Any]],
    documents: list[dict[str, Any]],
    participants: dict[str, Any],
) -> None:
    for document in documents:
        for number in range(int(document.get("start_page") or 0), int(document.get("end_page") or -1) + 1):
            page = pages_by_number.get(number)
            if page is not None:
                page["document_ids"].append(document["id"])
                if document["type"] == "hearing":
                    page["hearing_id"] = document["id"]
    hearings = participants.get("hearings") if isinstance(participants.get("hearings"), list) else []
    for hearing in hearings:
        if not isinstance(hearing, dict):
            continue
        start = page_number(hearing.get("start_page"))
        end = page_number(hearing.get("end_page"))
        roles = sorted({str(item.get("role_id") or "") for item in hearing.get("counsel", []) if isinstance(item, dict) and item.get("role_id")})
        hearing_participants = [
            {
                "id": str(item.get("id") or ""),
                "role_id": str(item.get("role_id") or ""),
                "role_label": str(item.get("role_label") or ""),
                "name": str(item.get("name") or ""),
                "attendance_status": str(item.get("attendance_status") or ""),
                "speaking_status": str(item.get("speaking_status") or ""),
                "sworn_status": str(item.get("sworn_status") or ""),
            }
            for item in hearing.get("participants", []) if isinstance(item, dict)
        ]
        for number in range(start, end + 1):
            page = pages_by_number.get(number)
            if page is not None:
                page["hearing_id"] = str(hearing.get("id") or page["hearing_id"])
                page["counsel_roles"] = roles
                page["participants"] = hearing_participants
        for witness in hearing.get("witnesses", []):
            if not isinstance(witness, dict):
                continue
            witness_payload = {
                "id": str(witness.get("id") or ""),
                "name": str(witness.get("name") or ""),
                "description": str(witness.get("description") or ""),
            }
            for examination in witness.get("examinations", []):
                if not isinstance(examination, dict):
                    continue
                exam_start = page_number(examination.get("start_file_page"))
                exam_end = page_number(examination.get("end_file_page")) or exam_start
                for number in range(exam_start, exam_end + 1):
                    page = pages_by_number.get(number)
                    if page is None:
                        continue
                    if witness_payload not in page["witnesses"]:
                        page["witnesses"].append(witness_payload)
                    page["examinations"].append({
                        "witness_id": witness_payload["id"],
                        "witness_name": witness_payload["name"],
                        "type": str(examination.get("type") or ""),
                        "examiner_name": str(examination.get("examiner_name") or ""),
                        "examiner_role_id": str(examination.get("examiner_role_id") or ""),
                    })


def build_lookup(pages: list[dict[str, Any]], documents: list[dict[str, Any]], participants: dict[str, Any]) -> dict[str, Any]:
    by_file: dict[str, dict[str, Any]] = {}
    by_citation: dict[str, list[str]] = {}
    by_type: dict[str, list[str]] = {}
    by_date: dict[str, list[str]] = {}
    by_report: dict[str, list[str]] = {}
    by_counsel: dict[str, list[dict[str, str]]] = {}
    by_participant: dict[str, list[dict[str, str]]] = {}
    by_witness: dict[str, list[dict[str, Any]]] = {}
    for page in pages:
        by_file[page["file_name"]] = {
            "file_page": page["file_page"], "citation_label": page["citation_label"],
            "citation_key": page["citation_key"], "record_type": page["record_type"],
            "page_type": page["page_type"], "documents": page["document_ids"],
            "hearing_id": page["hearing_id"],
        }
        if page["citation_key"]:
            by_citation.setdefault(page["citation_key"], []).append(page["file_name"])
    for document in documents:
        by_type.setdefault(document["type"], []).append(document["id"])
        if document["date_key"]:
            by_date.setdefault(document["date_key"], []).append(document["id"])
        if document["report_id"]:
            by_report.setdefault(document["report_id"], []).append(document["id"])
    for hearing in participants.get("hearings", []):
        if not isinstance(hearing, dict):
            continue
        hearing_id = str(hearing.get("id") or "")
        for counsel in hearing.get("counsel", []):
            if not isinstance(counsel, dict):
                continue
            value = {"hearing_id": hearing_id, "name": str(counsel.get("name") or ""), "role_label": str(counsel.get("role_label") or "")}
            keys = [str(counsel.get("role_id") or ""), str(counsel.get("name") or ""), *[str(alias) for alias in counsel.get("aliases", [])]]
            for key in keys:
                if key:
                    by_counsel.setdefault(key.casefold(), []).append(value)
        for participant in hearing.get("participants", []):
            if not isinstance(participant, dict):
                continue
            value = {
                "hearing_id": hearing_id,
                "participant_id": str(participant.get("id") or ""),
                "name": str(participant.get("name") or ""),
                "role_id": str(participant.get("role_id") or ""),
                "role_label": str(participant.get("role_label") or ""),
                "attendance_status": str(participant.get("attendance_status") or ""),
                "speaking_status": str(participant.get("speaking_status") or ""),
            }
            keys = [value["name"], value["role_id"], value["role_label"], *[str(alias) for alias in participant.get("aliases", [])]]
            for key in keys:
                if key:
                    by_participant.setdefault(key.casefold(), []).append(value)
        for witness in hearing.get("witnesses", []):
            if not isinstance(witness, dict):
                continue
            value = {"hearing_id": hearing_id, "witness_id": str(witness.get("id") or ""), "name": str(witness.get("name") or ""), "description": str(witness.get("description") or ""), "examinations": witness.get("examinations", [])}
            for key in [value["name"], *[str(alias) for alias in witness.get("aliases", [])]]:
                if key:
                    by_witness.setdefault(key.casefold(), []).append(value)
    return {"by_file": by_file, "by_citation_key": by_citation, "by_type": by_type, "by_date": by_date, "by_report_id": by_report, "by_counsel": by_counsel, "by_participant": by_participant, "by_witness": by_witness}


def build_source_map(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve(strict=False)
    manifest = load_object(root / "manifest.json", "manifest.json")
    transcript = load_object(root / "artifacts" / "transcript_page_numbers.json", "transcript_page_numbers.json")
    if int(transcript.get("schema_version") or 0) < 2:
        raise ValueError("Transcript numbering schema version 2 or newer is required.")
    participants = load_object(root / "artifacts" / "participant_index.json", "participant_index.json")
    if participants.get("schema_version") != 2:
        raise ValueError("Participant index schema version 2 is required.")
    summaries = summary_paths(root, manifest)
    case_overview = validated_case_overview_path(root)
    pages, pages_by_number, warnings = build_pages(root, transcript)
    documents = boundary_documents(root, pages_by_number)
    annotate_pages(pages_by_number, documents, participants)
    participant_warnings = participants.get("warnings") if isinstance(participants.get("warnings"), list) else []
    warnings.extend(str(item) for item in participant_warnings if str(item).strip())
    citation_series = transcript.get("citation_series") if isinstance(transcript.get("citation_series"), list) else []
    anomalies = transcript.get("anomalies") if isinstance(transcript.get("anomalies"), list) else []
    paths = {
        "manifest": "manifest.json", "source_map": "artifacts/source_map.json",
        "text_pages": "text_pages", "image_pages": "image_pages" if (root / "image_pages").is_dir() else "",
        "toc": "artifacts/toc.txt" if (root / "artifacts" / "toc.txt").is_file() else "",
        "hearing_boundaries": "artifacts/hearing_boundaries.json",
        "report_boundaries": "artifacts/report_boundaries.json",
        "minutes_boundaries": "artifacts/minutes_boundaries.json",
        "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
        "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
        "participant_index": "artifacts/participant_index.json",
        "case_overview": case_overview,
        "summaries": summaries,
    }
    payload = {
        "schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "generated_at": utc_now(), "source": "record-source-map",
        "case_name": (root / "case_name.txt").read_text(encoding="utf-8", errors="ignore").strip() if (root / "case_name.txt").is_file() else "",
        "root_dir": ".", "paths": paths,
        "counts": {
            "pages": len(pages), "documents": len(documents),
            "hearings": sum(item["type"] == "hearing" for item in documents),
            "reports": sum(item["type"] == "report" for item in documents),
            "minute_orders": sum(item["type"] == "minute_order" for item in documents),
            "participants": sum(len(item.get("counsel", [])) + len(item.get("participants", [])) + len(item.get("witnesses", [])) for item in participants.get("hearings", []) if isinstance(item, dict)),
            "citation_series": len(citation_series), "citation_anomalies": len(anomalies),
        },
        "citation_series": citation_series, "citation_anomalies": anomalies,
        "participant_index": participants, "pages": pages, "documents": documents,
        "lookup": build_lookup(pages, documents, participants),
        "warnings": sorted(set(warnings)),
    }
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    for key in LEGACY_FILE_KEYS:
        files.pop(key, None)
    files.update({
        "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
        "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
        "participant_index": "artifacts/participant_index.json",
        "case_overview": case_overview,
        "source_map": "artifacts/source_map.json",
        **summaries,
    })
    manifest["schema_version"] = max(2, int(manifest.get("schema_version") or 0))
    manifest["files"] = files
    manifest.pop("rag", None)
    directories = manifest.get("directories") if isinstance(manifest.get("directories"), dict) else {}
    for key in ("raw", "preoptimized", "optimized", "rag"):
        directories.pop(key, None)
    manifest["directories"] = directories
    manifest["updated_at"] = utc_now()
    return payload, manifest


def remove_legacy_organized_summaries(root: Path) -> list[Path]:
    removed: list[Path] = []
    for path in sorted((root / "summaries").glob("*_organized.txt")):
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def write_source_map(root: Path) -> tuple[Path, dict[str, Any]]:
    root = root.resolve(strict=False)
    payload, manifest = build_source_map(root)
    output = root / "artifacts" / "source_map.json"
    atomic_write_json(output, payload)
    atomic_write_json(root / "manifest.json", manifest)
    remove_legacy_organized_summaries(root)
    return output, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_bundle", nargs="?", default=".")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output, payload = write_source_map(Path(args.case_bundle))
    except Exception as exc:  # noqa: BLE001
        print(f"record-source-map failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {output}")
    print(f"Pages: {payload['counts']['pages']}")
    print(f"Documents: {payload['counts']['documents']}")
    for warning in payload.get("warnings", []):
        print(f"Warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
