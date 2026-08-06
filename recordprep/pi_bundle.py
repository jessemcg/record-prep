from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PREPARE_BUNDLE_MANIFEST_KEYS = {
    "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
    "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
    "participant_index": "artifacts/participant_index.json",
    "source_map": "artifacts/source_map.json",
}
PI_STEP_IDS = (
    "number_transcript_pages",
    "build_participant_index",
    "organize_hearing_summary",
    "organize_report_summary",
    "build_source_map",
)
_LONG_US_DATE = (
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December) \d{1,2}, \d{4}"
)
_HEARING_DATE_LINE_RE = re.compile(
    rf"^{_LONG_US_DATE}\b.*(?:\[Hearing\]|\[Minute Order\])\("
)
_REPORT_DATE_TITLE_LINE_RE = re.compile(rf"^{_LONG_US_DATE}\s+-\s+\S")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _safe_relative_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    resolved = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return resolved


def _summary_source(root: Path, manifest: dict[str, Any], kind: str) -> Path | None:
    files = manifest.get("files")
    if isinstance(files, dict):
        configured = _safe_relative_path(root, files.get(f"summarized_{kind}"))
        if configured is not None and configured.exists():
            return configured
    summaries_dir = root / "summaries"
    patterns = (
        f"{kind}_sum_*.txt",
        f"summarized_{kind}.txt",
    )
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(summaries_dir.glob(pattern))
    candidates = sorted(
        {
            path
            for path in candidates
            if path.is_file() and not path.stem.endswith("_organized")
        }
    )
    return candidates[0] if len(candidates) == 1 else None


def expected_prepare_bundle_paths(root: Path) -> dict[str, Path]:
    manifest = _read_json(root / "manifest.json") or {}
    paths = {
        key: root / relative
        for key, relative in PREPARE_BUNDLE_MANIFEST_KEYS.items()
    }
    for kind in ("hearings", "reports"):
        source = _summary_source(root, manifest, kind)
        if source is not None:
            paths[f"organized_{kind}"] = source.with_name(
                f"{source.stem}_organized{source.suffix}"
            )
    return paths


def expected_organized_summary_path(root: Path, kind: str) -> Path | None:
    if kind not in {"hearings", "reports"}:
        raise ValueError(f"Unknown summary kind: {kind}")
    manifest = _read_json(root / "manifest.json") or {}
    source = _summary_source(root, manifest, kind)
    if source is None:
        return None
    return source.with_name(f"{source.stem}_organized{source.suffix}")


def legacy_organized_summary_path(root: Path, kind: str) -> Path | None:
    if kind not in {"hearings", "reports"}:
        raise ValueError(f"Unknown summary kind: {kind}")
    manifest = _read_json(root / "manifest.json") or {}
    source = _summary_source(root, manifest, kind)
    if source is None:
        return None
    return source.with_name(f"{source.stem}._organized{source.suffix}")


def validate_transcript_numbering_outputs(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    paths = expected_prepare_bundle_paths(root)
    transcript_path = paths["transcript_page_numbers"]
    series_path = paths["transcript_page_number_series"]
    issues: list[str] = []
    transcript = _read_json(transcript_path)
    if transcript is None:
        return ["artifacts/transcript_page_numbers.json is missing or invalid."]
    if int(transcript.get("schema_version") or 0) < 2:
        issues.append("transcript page numbers must use schema version 2 or newer.")
    entries = transcript.get("entries")
    if not isinstance(entries, list):
        issues.append("transcript page numbers entries must be a list.")
    else:
        text_pages = sorted((root / "text_pages").glob("[0-9][0-9][0-9][0-9].txt"))
        if len(entries) != len(text_pages):
            issues.append(
                "transcript page numbers must contain one entry per text page."
            )
    if not isinstance(transcript.get("citation_series"), list):
        issues.append("transcript page numbers citation_series must be a list.")
    try:
        if not series_path.is_file() or not series_path.read_text(
            encoding="utf-8"
        ).strip():
            issues.append("artifacts/transcript_page_number_series.md is missing or empty.")
    except OSError:
        issues.append("artifacts/transcript_page_number_series.md is unreadable.")
    return list(dict.fromkeys(issues))


def validate_participant_index_output(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    path = root / "artifacts" / "participant_index.json"
    payload = _read_json(path)
    if payload is None:
        return ["artifacts/participant_index.json is missing or invalid."]
    issues: list[str] = []
    if payload.get("schema_version") != 1:
        issues.append("participant index must use schema version 1.")
    if payload.get("source") != "record-participant-index":
        issues.append("participant index has an invalid source.")
    hearings = payload.get("hearings")
    if not isinstance(hearings, list) or not hearings:
        return [*issues, "participant index hearings must be a nonempty list."]
    valid_statuses = {"verified", "none", "unknown", "conflict"}
    valid_roles = {
        "mothers_counsel", "fathers_counsel", "alleged_fathers_counsel",
        "presumed_fathers_counsel", "parents_counsel", "minors_counsel",
        "county_counsel", "tribes_counsel", "guardian_ad_litem",
        "other_counsel", "unresolved_counsel",
    }
    seen: set[str] = set()
    for index, hearing in enumerate(hearings, start=1):
        label = f"participant index hearing {index}"
        if not isinstance(hearing, dict):
            issues.append(f"{label} must be an object.")
            continue
        hearing_id = str(hearing.get("id") or "").strip()
        if not hearing_id or hearing_id in seen:
            issues.append(f"{label} id must be nonempty and unique.")
        seen.add(hearing_id)
        try:
            start = int(hearing.get("start_page") or 0)
            end = int(hearing.get("end_page") or 0)
        except (TypeError, ValueError):
            start = end = 0
        if not start or end < start:
            issues.append(f"{label} has an invalid page range.")
        status = str(hearing.get("witness_status") or "")
        if status not in valid_statuses:
            issues.append(f"{label} has an invalid witness_status.")
        witness_evidence = hearing.get("witness_evidence")
        if not isinstance(witness_evidence, list):
            issues.append(f"{label} witness_evidence must be a list.")
            witness_evidence = []
        witnesses = hearing.get("witnesses")
        if not isinstance(witnesses, list):
            issues.append(f"{label} witnesses must be a list.")
            witnesses = []
        if status in {"none", "unknown"} and witnesses:
            issues.append(f"{label} cannot list witnesses when status is {status}.")
        if status == "none" and not witness_evidence:
            issues.append(f"{label} must cite witness_evidence when status is none.")
        if status == "verified" and not witnesses:
            issues.append(f"{label} must list a witness when status is verified.")
        if status == "conflict" and not hearing.get("warnings"):
            issues.append(f"{label} must explain conflict status in warnings.")
        counsel = hearing.get("counsel")
        if not isinstance(counsel, list):
            issues.append(f"{label} counsel must be a list.")
            counsel = []
        counsel_names: set[str] = set()
        for person in counsel:
            if not isinstance(person, dict):
                issues.append(f"{label} has a malformed counsel entry.")
                continue
            if str(person.get("role_id") or "") not in valid_roles:
                issues.append(f"{label} has an invalid counsel role_id.")
            name = str(person.get("name") or "").strip()
            if not name:
                issues.append(f"{label} has counsel without a name.")
            counsel_names.add(name.casefold())
        for witness in witnesses:
            if not isinstance(witness, dict):
                issues.append(f"{label} has a malformed witness entry.")
                continue
            name = str(witness.get("name") or "").strip()
            if not name:
                issues.append(f"{label} has a witness without a name.")
            if name.casefold() in counsel_names and status != "conflict":
                issues.append(f"{label} lists counsel as a witness without conflict status.")
            exams = witness.get("examinations")
            if not isinstance(exams, list) or not exams:
                issues.append(f"{label} witness {name or '(unnamed)'} has no examinations.")
                continue
            for exam in exams:
                if not isinstance(exam, dict):
                    issues.append(f"{label} has a malformed examination.")
                    continue
                try:
                    exam_start = int(exam.get("start_file_page") or 0)
                    exam_end = int(exam.get("end_file_page") or 0)
                except (TypeError, ValueError):
                    exam_start = exam_end = 0
                if exam_start and not start <= exam_start <= end:
                    issues.append(f"{label} has an examination outside its page range.")
                if exam_end and (not exam_start or exam_end < exam_start or exam_end > end):
                    issues.append(f"{label} has an invalid examination end page.")
    return list(dict.fromkeys(issues))


def validate_organized_summary_output(root: Path, kind: str) -> list[str]:
    root = root.resolve(strict=False)
    manifest = _read_json(root / "manifest.json") or {}
    source = _summary_source(root, manifest, kind)
    label = "hearing" if kind == "hearings" else "report"
    if source is None:
        return [f"the source {label} summary is missing or ambiguous."]
    organized = source.with_name(f"{source.stem}_organized{source.suffix}")
    if not organized.is_file():
        return [f"the organized {label} summary is missing: {organized.name}."]
    try:
        if organized.stat().st_mtime < source.stat().st_mtime:
            return [f"the organized {label} summary is stale."]
    except OSError:
        return [f"unable to compare {label} summary freshness."]
    try:
        lines = organized.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [f"the organized {label} summary is unreadable."]
    boundary_pattern = (
        _HEARING_DATE_LINE_RE
        if kind == "hearings"
        else _REPORT_DATE_TITLE_LINE_RE
    )
    missing_blank_lines = [
        line_number
        for line_number, line in enumerate(lines, start=1)
        if boundary_pattern.match(line)
        and line_number > 1
        and lines[line_number - 2].strip()
    ]
    if missing_blank_lines:
        boundary_label = (
            "hearing date/link line"
            if kind == "hearings"
            else "retained report date/title line"
        )
        line_list = ", ".join(str(value) for value in missing_blank_lines)
        return [
            f"the organized {label} summary must have a blank line immediately "
            f"before every {boundary_label}; missing before line(s): {line_list}."
        ]
    return []


def source_map_prerequisite_issues(root: Path) -> list[str]:
    issues = validate_transcript_numbering_outputs(root)
    issues.extend(validate_participant_index_output(root))
    issues.extend(validate_organized_summary_output(root, "hearings"))
    issues.extend(validate_organized_summary_output(root, "reports"))
    return list(dict.fromkeys(issues))


def validate_prepare_bundle_outputs(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    issues: list[str] = []
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest is None:
        return ["manifest.json is missing or invalid."]
    files = manifest.get("files")
    if not isinstance(files, dict):
        return ["manifest.json files must be an object."]

    paths = expected_prepare_bundle_paths(root)
    transcript_path = paths["transcript_page_numbers"]
    series_path = paths["transcript_page_number_series"]
    participant_index_path = paths["participant_index"]
    source_map_path = paths["source_map"]
    organized_hearings = paths.get("organized_hearings")
    organized_reports = paths.get("organized_reports")

    transcript = _read_json(transcript_path)
    if transcript is None:
        issues.append("artifacts/transcript_page_numbers.json is missing or invalid.")
    else:
        if int(transcript.get("schema_version") or 0) < 2:
            issues.append("transcript page numbers must use schema version 2 or newer.")
        if not isinstance(transcript.get("entries"), list):
            issues.append("transcript page numbers entries must be a list.")
        if not isinstance(transcript.get("citation_series"), list):
            issues.append("transcript page numbers citation_series must be a list.")

    if not series_path.is_file():
        issues.append("artifacts/transcript_page_number_series.md is missing.")
    issues.extend(validate_participant_index_output(root))
    if organized_hearings is None or not organized_hearings.is_file():
        issues.append("the organized hearing summary is missing.")
    if organized_reports is None or not organized_reports.is_file():
        issues.append("the organized report summary is missing.")

    source_map = _read_json(source_map_path)
    if source_map is None:
        issues.append("artifacts/source_map.json is missing or invalid.")
    else:
        if int(source_map.get("schema_version") or 0) < 2:
            issues.append("source_map.json must use schema version 2 or newer.")
        if not isinstance(source_map.get("pages"), list):
            issues.append("source_map.json pages must be a list.")
        if not isinstance(source_map.get("citation_series"), list):
            issues.append("source_map.json citation_series must be a list.")

    expected_manifest_paths = dict(PREPARE_BUNDLE_MANIFEST_KEYS)
    if organized_hearings is not None:
        expected_manifest_paths["organized_hearings"] = organized_hearings.relative_to(
            root
        ).as_posix()
    if organized_reports is not None:
        expected_manifest_paths["organized_reports"] = organized_reports.relative_to(
            root
        ).as_posix()
    for key, expected in expected_manifest_paths.items():
        if files.get(key) != expected:
            issues.append(f"manifest.json files.{key} must be {expected}.")

    freshness_pairs: list[tuple[Path, Path, str]] = []
    for kind, organized in (
        ("hearings", organized_hearings),
        ("reports", organized_reports),
    ):
        source = _summary_source(root, manifest, kind)
        if source is not None and organized is not None:
            freshness_pairs.append(
                (organized, source, f"the organized {kind} summary is stale.")
            )
    for prerequisite in (
        transcript_path,
        series_path,
        participant_index_path,
        organized_hearings,
        organized_reports,
    ):
        if prerequisite is not None:
            freshness_pairs.append(
                (source_map_path, prerequisite, "source_map.json is stale.")
            )
    for output, source, message in freshness_pairs:
        try:
            if output.is_file() and source.is_file() and output.stat().st_mtime < source.stat().st_mtime:
                issues.append(message)
        except OSError:
            issues.append(f"unable to compare output freshness for {output.name}.")

    return list(dict.fromkeys(issues))


def prepare_bundle_complete(root: Path) -> bool:
    return not validate_prepare_bundle_outputs(root)


def validate_pi_step_outputs(step_id: str, root: Path) -> list[str]:
    if step_id == "number_transcript_pages":
        return validate_transcript_numbering_outputs(root)
    if step_id == "build_participant_index":
        issues = validate_transcript_numbering_outputs(root)
        issues.extend(validate_participant_index_output(root))
        return list(dict.fromkeys(issues))
    if step_id == "organize_hearing_summary":
        return validate_organized_summary_output(root, "hearings")
    if step_id == "organize_report_summary":
        return validate_organized_summary_output(root, "reports")
    if step_id == "build_source_map":
        return validate_prepare_bundle_outputs(root)
    return [f"Unknown PI step: {step_id}"]


def pi_step_complete(step_id: str, root: Path) -> bool:
    return not validate_pi_step_outputs(step_id, root)
