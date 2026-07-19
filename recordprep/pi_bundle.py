from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PREPARE_BUNDLE_MANIFEST_KEYS = {
    "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
    "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
    "source_map": "artifacts/source_map.json",
}
PI_STEP_IDS = (
    "number_transcript_pages",
    "organize_hearing_summary",
    "organize_report_summary",
    "build_source_map",
)


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
    return []


def source_map_prerequisite_issues(root: Path) -> list[str]:
    issues = validate_transcript_numbering_outputs(root)
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
    if organized_hearings is None or not organized_hearings.is_file():
        issues.append("the organized hearing summary is missing.")
    if organized_reports is None or not organized_reports.is_file():
        issues.append("the organized report summary is missing.")

    source_map = _read_json(source_map_path)
    if source_map is None:
        issues.append("artifacts/source_map.json is missing or invalid.")
    else:
        if int(source_map.get("schema_version") or 0) < 1:
            issues.append("source_map.json has an unsupported schema version.")
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
    if step_id == "organize_hearing_summary":
        return validate_organized_summary_output(root, "hearings")
    if step_id == "organize_report_summary":
        return validate_organized_summary_output(root, "reports")
    if step_id == "build_source_map":
        return validate_prepare_bundle_outputs(root)
    return [f"Unknown PI step: {step_id}"]


def pi_step_complete(step_id: str, root: Path) -> bool:
    return not validate_pi_step_outputs(step_id, root)
