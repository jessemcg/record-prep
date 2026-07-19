#!/usr/bin/env python3
"""Build a citation-aware source map for a RecordPrep case_bundle."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


SOURCE_MAP_SCHEMA_VERSION = 1


def natural_key(value: str | Path) -> list[object]:
    name = value.name if isinstance(value, Path) else Path(str(value)).name
    key: list[object] = []
    for part in re.split(r"(\d+)", name):
        key.append(int(part) if part.isdigit() else part.lower())
    return key


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def relpath(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except ValueError:
        return os.path.relpath(str(path), str(root))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_output_paths(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    files = manifest.get("files")
    files = files if isinstance(files, dict) else {}
    result = {
        "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
        "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
        "source_map": "artifacts/source_map.json",
    }
    summaries_dir = root / "summaries"
    for kind in ("hearings", "reports"):
        source_key = f"summarized_{kind}"
        raw_source = files.get(source_key)
        source = None
        if isinstance(raw_source, str) and raw_source.strip():
            candidate = Path(raw_source)
            source = candidate if candidate.is_absolute() else root / candidate
        if source is not None:
            organized = source.with_name(f"{source.stem}_organized{source.suffix}")
        else:
            candidates = sorted(
                summaries_dir.glob(f"*{kind}*_organized.txt"),
                key=natural_key,
            )
            organized = candidates[0] if len(candidates) == 1 else None
        if organized is None or not organized.is_file():
            raise FileNotFoundError(f"Organized {kind} summary not found.")
        result[f"organized_{kind}"] = relpath(root, organized)
    return result


def resolve_manifest_path(root: Path, manifest: dict[str, Any], section: str, key: str, fallback: Path) -> Path:
    section_value = manifest.get(section)
    if isinstance(section_value, dict):
        raw = section_value.get(key)
        if isinstance(raw, str) and raw.strip():
            path = Path(raw)
            return path if path.is_absolute() else root / path
    return fallback


def page_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"(\d+)", text)
    if not match:
        return text
    return f"{int(match.group(1)):04d}"


def file_name_for_page(value: Any) -> str:
    label = page_label(value)
    return f"{label}.txt" if label else ""


def date_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def safe_char_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def load_case_name(root: Path) -> str:
    path = root / "case_name.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("manifest.json not found. Run this skill from a RecordPrep case_bundle.")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("manifest.json must contain a JSON object.")
    return payload


def load_transcript_artifact(root: Path, manifest: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    numbers_path = resolve_manifest_path(
        root,
        manifest,
        "files",
        "transcript_page_numbers",
        root / "artifacts" / "transcript_page_numbers.json",
    )
    series_path = resolve_manifest_path(
        root,
        manifest,
        "files",
        "transcript_page_number_series",
        root / "artifacts" / "transcript_page_number_series.md",
    )
    missing = [str(path) for path in (numbers_path, series_path) if not path.exists()]
    if missing:
        joined = "\n".join(f"- {item}" for item in missing)
        raise FileNotFoundError(
            "Transcript citation artifacts are missing. Run transcript-page-numbering first:\n"
            f"{joined}"
        )
    payload = read_json(numbers_path)
    if not isinstance(payload, dict):
        raise ValueError(f"{numbers_path} must contain a JSON object.")
    if int(payload.get("schema_version") or 0) < 2:
        raise ValueError(
            f"{numbers_path} must be transcript-page-numbering schema_version 2 or newer."
        )
    return numbers_path, series_path, payload


def build_pages(root: Path, transcript_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    text_dir = root / "text_pages"
    image_dir = root / "image_pages"
    if not text_dir.is_dir():
        raise FileNotFoundError("text_pages/ not found. Run this skill from a RecordPrep case_bundle.")

    entries = transcript_payload.get("entries")
    entry_list = entries if isinstance(entries, list) else []
    citation_by_file: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for item in entry_list:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("file_name") or "").strip()
        if file_name:
            citation_by_file[file_name] = item

    pages: list[dict[str, Any]] = []
    for path in sorted(text_dir.glob("[0-9][0-9][0-9][0-9].txt"), key=natural_key):
        citation = citation_by_file.get(path.name, {})
        file_page = citation.get("file_page")
        if file_page is None:
            try:
                file_page = int(path.stem)
            except ValueError:
                file_page = None
        image_path = image_dir / f"{path.stem}.png"
        page: dict[str, Any] = {
            "file_name": path.name,
            "file_page": file_page,
            "text_path": relpath(root, path),
            "image_path": relpath(root, image_path) if image_path.exists() else "",
            "record_type": str(citation.get("record_type") or "").strip(),
            "page_type": str(citation.get("page_type") or "").strip(),
            "transcript_page_number": citation.get("transcript_page_number"),
            "transcript_page_label": str(citation.get("transcript_page_label") or "").strip(),
            "citation_series_id": str(citation.get("citation_series_id") or "").strip(),
            "citation_prefix": str(citation.get("citation_prefix") or "").strip(),
            "citation_label": str(citation.get("citation_label") or "").strip(),
            "citation_key": str(citation.get("citation_key") or "").strip(),
            "status": str(citation.get("status") or "").strip(),
            "confidence": str(citation.get("confidence") or "").strip(),
            "method": str(citation.get("method") or "").strip(),
            "start_offset": citation.get("start_offset"),
            "end_offset": citation.get("end_offset"),
            "line_index": citation.get("line_index"),
        }
        if not page["citation_key"]:
            warnings.append(f"No citation key for {path.name}.")
        pages.append(page)
    return pages, {str(page["file_name"]): page for page in pages}, warnings


def load_boundary_indexes(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    artifacts = root / "artifacts"
    indexes = {
        "hearing_by_date": {},
        "report_by_id": {},
        "report_by_label": {},
        "minute_by_date": {},
    }
    for entry in read_json_list(artifacts / "hearing_boundaries.json"):
        key = date_key(entry.get("date"))
        if key:
            indexes["hearing_by_date"].setdefault(key, entry)
    for entry in read_json_list(artifacts / "report_boundaries.json"):
        report_id = str(entry.get("report_id") or "").strip()
        if report_id:
            indexes["report_by_id"].setdefault(report_id, entry)
        label = str(entry.get("report_label") or "").strip()
        if label:
            indexes["report_by_label"].setdefault(label.lower(), entry)
    for entry in read_json_list(artifacts / "minutes_boundaries.json"):
        key = date_key(entry.get("date"))
        if key:
            indexes["minute_by_date"].setdefault(key, entry)
    return indexes


def chunk_entries(root: Path, section_dir: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(section_dir.glob("[0-9][0-9][0-9][0-9].txt"), key=natural_key), start=1):
        chunks.append(
            {
                "index": index,
                "path": relpath(root, path),
                "char_count": safe_char_count(path),
            }
        )
    return chunks


def page_range(start_page: str, end_page: str) -> list[str]:
    if not start_page or not end_page:
        return []
    try:
        start = int(start_page)
        end = int(end_page)
    except ValueError:
        return []
    if end < start:
        return []
    return [f"{page:04d}" for page in range(start, end + 1)]


def citation_range(start: dict[str, Any] | None, end: dict[str, Any] | None) -> str:
    start_label = str((start or {}).get("citation_label") or "").strip()
    end_label = str((end or {}).get("citation_label") or "").strip()
    if not start_label:
        return ""
    if not end_label or end_label == start_label:
        return start_label
    return f"{start_label}-{end_label}"


def build_document(
    *,
    root: Path,
    doc_id: str,
    doc_type: str,
    label: str,
    start_page: str,
    end_page: str,
    pages_by_file: dict[str, dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    section_dir: Path | None = None,
) -> dict[str, Any]:
    normalized_start = page_label(start_page)
    normalized_end = page_label(end_page)
    start_file = file_name_for_page(normalized_start)
    end_file = file_name_for_page(normalized_end)
    start_page_entry = pages_by_file.get(start_file)
    end_page_entry = pages_by_file.get(end_file)
    raw_metadata = metadata if isinstance(metadata, dict) else {}
    display_date = str(
        raw_metadata.get("hearing_date")
        or raw_metadata.get("date")
        or raw_metadata.get("report_date")
        or ""
    ).strip()
    document: dict[str, Any] = {
        "id": doc_id,
        "type": doc_type,
        "label": label,
        "date": display_date,
        "date_key": date_key(display_date),
        "report_name": str(raw_metadata.get("report_name") or "").strip(),
        "report_date": str(raw_metadata.get("report_date") or "").strip(),
        "report_label": str(raw_metadata.get("report_label") or "").strip(),
        "report_id": str(raw_metadata.get("report_id") or "").strip(),
        "start_page": normalized_start,
        "end_page": normalized_end,
        "start_file": start_file,
        "end_file": end_file,
        "start_citation_label": str((start_page_entry or {}).get("citation_label") or "").strip(),
        "end_citation_label": str((end_page_entry or {}).get("citation_label") or "").strip(),
        "citation_range": citation_range(start_page_entry, end_page_entry),
        "start_citation_key": str((start_page_entry or {}).get("citation_key") or "").strip(),
        "end_citation_key": str((end_page_entry or {}).get("citation_key") or "").strip(),
        "page_labels": page_range(normalized_start, normalized_end),
        "metadata": raw_metadata,
        "optimized_dir": relpath(root, section_dir) if section_dir else "",
        "metadata_path": relpath(root, section_dir / "metadata.json") if section_dir else "",
        "chunks": chunk_entries(root, section_dir) if section_dir else [],
        "aliases": [],
    }
    aliases = {
        document["label"],
        document["date"],
        document["report_name"],
        document["report_date"],
        document["report_label"],
        document["report_id"],
        document["citation_range"],
    }
    document["aliases"] = sorted(str(alias).strip() for alias in aliases if str(alias).strip())
    return document


def load_optimized_documents(
    root: Path,
    pages_by_file: dict[str, dict[str, Any]],
    boundary_indexes: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    warnings: list[str] = []
    specs = [
        ("hearing", root / "artifacts" / "optimized" / "hearings", "hearing_date"),
        ("report", root / "artifacts" / "optimized" / "reports", "report_name"),
    ]
    for doc_type, base_dir, label_key in specs:
        if not base_dir.exists():
            warnings.append(f"Optimized {doc_type} directory not found: {relpath(root, base_dir)}")
            continue
        for index, section_dir in enumerate(sorted((p for p in base_dir.iterdir() if p.is_dir()), key=natural_key), start=1):
            metadata_path = section_dir / "metadata.json"
            metadata: dict[str, Any] = {}
            if metadata_path.exists():
                try:
                    payload = read_json(metadata_path)
                    if isinstance(payload, dict):
                        metadata = payload
                except (OSError, json.JSONDecodeError):
                    warnings.append(f"Could not read metadata for {relpath(root, section_dir)}.")
            label_path = section_dir / "label.txt"
            label = (
                label_path.read_text(encoding="utf-8", errors="ignore").strip()
                if label_path.exists()
                else str(metadata.get(label_key) or section_dir.name).strip()
            )
            start_page = str(metadata.get("start_page") or "").strip()
            end_page = str(metadata.get("end_page") or "").strip()
            if doc_type == "hearing":
                boundary = boundary_indexes["hearing_by_date"].get(date_key(metadata.get("hearing_date")), {})
                start_page = start_page or str(boundary.get("start_page") or "").strip()
                end_page = end_page or str(boundary.get("end_page") or "").strip()
                if "date" not in metadata and metadata.get("hearing_date"):
                    metadata["date"] = metadata["hearing_date"]
            else:
                boundary = {}
                report_id = str(metadata.get("report_id") or "").strip()
                report_label = str(metadata.get("report_label") or "").strip().lower()
                if report_id:
                    boundary = boundary_indexes["report_by_id"].get(report_id, {})
                if not boundary and report_label:
                    boundary = boundary_indexes["report_by_label"].get(report_label, {})
                start_page = start_page or str(boundary.get("start_page") or "").strip()
                end_page = end_page or str(boundary.get("end_page") or "").strip()
            if not start_page or not end_page:
                warnings.append(f"No page range for {relpath(root, section_dir)}.")
            documents.append(
                build_document(
                    root=root,
                    doc_id=f"{doc_type}:{index:04d}",
                    doc_type=doc_type,
                    label=label,
                    start_page=start_page,
                    end_page=end_page,
                    pages_by_file=pages_by_file,
                    metadata=metadata,
                    section_dir=section_dir,
                )
            )
    return documents, warnings


def load_minute_documents(root: Path, pages_by_file: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for index, entry in enumerate(read_json_list(root / "artifacts" / "minutes_boundaries.json"), start=1):
        date_value = str(entry.get("date") or "").strip()
        metadata = {
            "type": "minute_order",
            "date": date_value,
            "start_page": str(entry.get("start_page") or "").strip(),
            "end_page": str(entry.get("end_page") or "").strip(),
        }
        documents.append(
            build_document(
                root=root,
                doc_id=f"minute_order:{index:04d}",
                doc_type="minute_order",
                label=date_value or f"Minute Order {index}",
                start_page=metadata["start_page"],
                end_page=metadata["end_page"],
                pages_by_file=pages_by_file,
                metadata=metadata,
                section_dir=None,
            )
        )
    return documents


def path_if_exists(root: Path, path: Path) -> str:
    return relpath(root, path) if path.exists() else ""


def build_paths(root: Path, manifest: dict[str, Any], numbers_path: Path, series_path: Path) -> dict[str, Any]:
    summaries_dir = root / "summaries"
    summary_paths = []
    if summaries_dir.exists():
        summary_paths = [
            relpath(root, path)
            for path in sorted(summaries_dir.glob("*.txt"), key=natural_key)
        ]
    return {
        "manifest": "manifest.json",
        "source_map": "artifacts/source_map.json",
        "text_pages": path_if_exists(root, root / "text_pages"),
        "image_pages": path_if_exists(root, root / "image_pages"),
        "toc": path_if_exists(root, root / "artifacts" / "toc.txt"),
        "hearing_boundaries": path_if_exists(root, root / "artifacts" / "hearing_boundaries.json"),
        "report_boundaries": path_if_exists(root, root / "artifacts" / "report_boundaries.json"),
        "minutes_boundaries": path_if_exists(root, root / "artifacts" / "minutes_boundaries.json"),
        "optimized_hearings": path_if_exists(root, root / "artifacts" / "optimized_hearings.txt"),
        "optimized_reports": path_if_exists(root, root / "artifacts" / "optimized_reports.txt"),
        "optimized_hearing_sections": path_if_exists(root, root / "artifacts" / "optimized" / "hearings"),
        "optimized_report_sections": path_if_exists(root, root / "artifacts" / "optimized" / "reports"),
        "case_overview": path_if_exists(root, root / "rag" / "case_overview.txt"),
        "vector_database": path_if_exists(root, root / "rag" / "vector_database"),
        "transcript_page_numbers": relpath(root, numbers_path),
        "transcript_page_number_series": relpath(root, series_path),
        "summaries": summary_paths,
        "manifest_files": manifest.get("files") if isinstance(manifest.get("files"), dict) else {},
    }


def build_lookup(pages: list[dict[str, Any]], documents: list[dict[str, Any]]) -> dict[str, Any]:
    by_file: dict[str, dict[str, Any]] = {}
    by_citation_key: dict[str, list[str]] = {}
    by_type: dict[str, list[str]] = {}
    by_date: dict[str, list[str]] = {}
    by_report_id: dict[str, list[str]] = {}
    by_page: dict[str, dict[str, Any]] = {}

    for page in pages:
        file_name = str(page.get("file_name") or "")
        page_label_value = page_label(page.get("file_page"))
        by_file[file_name] = {
            "file_page": page.get("file_page"),
            "citation_label": page.get("citation_label"),
            "citation_key": page.get("citation_key"),
            "record_type": page.get("record_type"),
            "page_type": page.get("page_type"),
            "status": page.get("status"),
        }
        citation_key = str(page.get("citation_key") or "").strip()
        if citation_key:
            by_citation_key.setdefault(citation_key, []).append(file_name)
        if page_label_value:
            by_page.setdefault(
                page_label_value,
                {
                    "file_name": file_name,
                    "citation_label": page.get("citation_label"),
                    "citation_key": page.get("citation_key"),
                    "documents": [],
                },
            )

    for document in documents:
        doc_id = str(document.get("id") or "").strip()
        doc_type = str(document.get("type") or "").strip()
        if doc_type and doc_id:
            by_type.setdefault(doc_type, []).append(doc_id)
        doc_date_key = str(document.get("date_key") or "").strip()
        if doc_date_key and doc_id:
            by_date.setdefault(doc_date_key, []).append(doc_id)
        report_id = str(document.get("report_id") or "").strip()
        if report_id and doc_id:
            by_report_id.setdefault(report_id, []).append(doc_id)
        for label in document.get("page_labels") or []:
            if label in by_page and doc_id:
                by_page[label].setdefault("documents", []).append(doc_id)

    return {
        "by_file": by_file,
        "by_citation_key": by_citation_key,
        "by_type": by_type,
        "by_date": by_date,
        "by_report_id": by_report_id,
        "by_page": by_page,
    }


def build_source_map(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=False)
    manifest = load_manifest(root)
    files = manifest.get("files")
    files = dict(files) if isinstance(files, dict) else {}
    files.update(prepare_output_paths(root, manifest))
    manifest["files"] = files
    numbers_path, series_path, transcript_payload = load_transcript_artifact(root, manifest)
    pages, pages_by_file, warnings = build_pages(root, transcript_payload)
    boundary_indexes = load_boundary_indexes(root)
    optimized_documents, optimized_warnings = load_optimized_documents(root, pages_by_file, boundary_indexes)
    warnings.extend(optimized_warnings)
    minute_documents = load_minute_documents(root, pages_by_file)
    documents = optimized_documents + minute_documents
    citation_series = transcript_payload.get("citation_series")
    if not isinstance(citation_series, list):
        citation_series = []
        warnings.append("No citation_series list found in transcript_page_numbers.json.")
    anomalies = transcript_payload.get("anomalies")
    if not isinstance(anomalies, list):
        anomalies = []
    counts = {
        "pages": len(pages),
        "documents": len(documents),
        "hearings": sum(1 for item in documents if item.get("type") == "hearing"),
        "reports": sum(1 for item in documents if item.get("type") == "report"),
        "minute_orders": sum(1 for item in documents if item.get("type") == "minute_order"),
        "optimized_chunks": sum(len(item.get("chunks") or []) for item in documents),
        "citation_series": len(citation_series),
        "citation_anomalies": len(anomalies),
    }
    return {
        "schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source": "record-source-map",
        "case_name": load_case_name(root),
        "root_dir": str(root),
        "paths": build_paths(root, manifest, numbers_path, series_path),
        "counts": counts,
        "citation_series": citation_series,
        "citation_anomalies": anomalies,
        "pages": pages,
        "documents": documents,
        "lookup": build_lookup(pages, documents),
        "warnings": sorted(set(warnings)),
    }


def update_manifest(root: Path) -> None:
    manifest_path = root / "manifest.json"
    manifest = load_manifest(root)
    files = manifest.get("files")
    if not isinstance(files, dict):
        files = {}
    files.update(prepare_output_paths(root, manifest))
    manifest["files"] = files
    manifest["updated_at"] = utc_now()
    atomic_write_json(manifest_path, manifest)


def write_source_map(root: Path) -> tuple[Path, dict[str, Any]]:
    payload = build_source_map(root)
    output_path = root / "artifacts" / "source_map.json"
    atomic_write_json(output_path, payload)
    update_manifest(root)
    return output_path, payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build artifacts/source_map.json for a RecordPrep case_bundle."
    )
    parser.add_argument(
        "case_bundle",
        nargs="?",
        default=".",
        help="Path to the RecordPrep case_bundle root. Defaults to current directory.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.case_bundle)
    try:
        output_path, payload = write_source_map(root)
    except Exception as exc:  # noqa: BLE001
        print(f"record-source-map failed: {exc}", file=sys.stderr)
        return 1

    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    print(f"Wrote {output_path}")
    print(f"Pages: {counts.get('pages', 0)}")
    print(f"Documents: {counts.get('documents', 0)}")
    print(f"Citation series: {counts.get('citation_series', 0)}")
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
