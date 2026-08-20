from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PREPARE_BUNDLE_MANIFEST_KEYS = {
    "transcript_layout": "artifacts/transcript_layout.json",
    "transcript_page_numbers": "artifacts/transcript_page_numbers.json",
    "transcript_page_number_series": "artifacts/transcript_page_number_series.md",
    "participant_index": "artifacts/participant_index.json",
    "case_overview": "artifacts/case_overview.md",
    "source_map": "artifacts/source_map.json",
}
PI_STEP_IDS = (
    "detect_transcript_layout",
    "number_transcript_pages",
    "build_participant_index",
    "create_case_overview",
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
    return {
        key: root / relative
        for key, relative in PREPARE_BUNDLE_MANIFEST_KEYS.items()
    }


def case_overview_path(root: Path) -> Path:
    return root.resolve(strict=False) / "artifacts" / "case_overview.md"


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
    if payload.get("schema_version") != 2:
        issues.append("participant index must use schema version 2.")
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
    valid_participant_roles = {
        "mother", "father", "alleged_father", "presumed_father", "minor",
        "relative", "caregiver", "social_worker", "agency_representative",
        "judicial_officer", "interpreter", "audience_member",
        "other_participant", "unresolved_participant",
    }
    valid_attendance = {"present", "remote", "absent", "unknown"}
    valid_speaking = {"spoke", "did_not_speak", "unknown"}
    valid_sworn = {"sworn", "unsworn", "not_applicable", "unknown"}
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
            if not isinstance(person.get("aliases"), list):
                issues.append(f"{label} counsel aliases must be a list.")
            if not isinstance(person.get("organization"), str):
                issues.append(f"{label} counsel organization must be a string.")
            if str(person.get("appearance_status") or "") not in {"present", "remote", "unknown"}:
                issues.append(f"{label} counsel has an invalid appearance_status.")
            if not isinstance(person.get("evidence"), list) or not person.get("evidence"):
                issues.append(f"{label} counsel must cite evidence.")
            counsel_names.add(name.casefold())
        participants = hearing.get("participants")
        if not isinstance(participants, list):
            issues.append(f"{label} participants must be a list.")
            participants = []
        participant_ids: set[str] = set()
        for person in participants:
            if not isinstance(person, dict):
                issues.append(f"{label} has a malformed participant entry.")
                continue
            participant_id = str(person.get("id") or "").strip()
            if not participant_id or participant_id in participant_ids:
                issues.append(f"{label} participant id must be nonempty and unique.")
            participant_ids.add(participant_id)
            if str(person.get("role_id") or "") not in valid_participant_roles:
                issues.append(f"{label} participant has an invalid role_id.")
            if not str(person.get("role_label") or "").strip():
                issues.append(f"{label} participant has no role_label.")
            if not isinstance(person.get("aliases"), list):
                issues.append(f"{label} participant aliases must be a list.")
            if str(person.get("attendance_status") or "") not in valid_attendance:
                issues.append(f"{label} participant has an invalid attendance_status.")
            if str(person.get("speaking_status") or "") not in valid_speaking:
                issues.append(f"{label} participant has an invalid speaking_status.")
            if str(person.get("sworn_status") or "") not in valid_sworn:
                issues.append(f"{label} participant has an invalid sworn_status.")
            if not isinstance(person.get("evidence"), list) or not person.get("evidence"):
                issues.append(f"{label} participant must cite evidence.")
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


def validate_summary_source_outputs(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    manifest = _read_json(root / "manifest.json") or {}
    issues: list[str] = []
    for kind, label in (("hearings", "hearing"), ("reports", "report")):
        source = _summary_source(root, manifest, kind)
        if source is None:
            issues.append(f"the source {label} summary is missing or ambiguous.")
            continue
        try:
            if not source.read_text(encoding="utf-8").strip():
                issues.append(f"the source {label} summary is empty.")
        except OSError:
            issues.append(f"the source {label} summary is unreadable.")
    return issues


def validate_transcript_layout_output(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    path = root / "artifacts" / "transcript_layout.json"
    payload = _read_json(path)
    if payload is None:
        return ["artifacts/transcript_layout.json is missing or invalid."]
    issues: list[str] = []
    if payload.get("artifact") != "recordprep-transcript-layout":
        issues.append("transcript layout has an invalid artifact name.")
    if payload.get("schema_version") != 1:
        issues.append("transcript layout must use schema version 1.")
    if payload.get("status") not in {"resolved", "needs_review"}:
        issues.append("transcript layout status must be resolved or needs_review.")
    if payload.get("status") == "resolved" and payload.get("mode") is None:
        issues.append("a resolved transcript layout must declare a mode.")
    if payload.get("decision_source") not in {"pi-agent", "manual"}:
        issues.append("transcript layout decision_source is invalid.")
    input_count = len(
        list(
            (root / "text_pages").glob("[0-9][0-9][0-9][0-9].txt")
        )
    )
    if int(payload.get("input_page_count") or -1) != input_count:
        issues.append(
            "transcript layout input_page_count does not match the text pages."
        )
    try:
        signature_matches = payload.get("input_signature") == _input_signature(root)
    except OSError:
        signature_matches = False
    if not signature_matches:
        issues.append("transcript layout input_signature is stale.")
    return list(dict.fromkeys(issues))


def _input_signature(root: Path) -> str:
    import hashlib

    text_dir = root / "text_pages"
    image_dir = root / "image_pages"
    digest = hashlib.sha256()
    digest.update(b"recordprep-transcript-layout-signature-v1\n")
    names = sorted(
        path.name
        for path in text_dir.glob("[0-9][0-9][0-9][0-9].txt")
        if path.is_file()
    )
    for name in names:
        digest.update(name.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\n")
        try:
            content = (text_dir / name).read_bytes()
        except OSError:
            content = b""
        digest.update(str(len(content)).encode("ascii"))
        digest.update(b"\n")
        image_path = image_dir / (Path(name).stem + ".png")
        size = 0
        try:
            if image_path.is_file():
                size = image_path.stat().st_size
        except OSError:
            size = 0
        digest.update(image_path.name.encode("utf-8", errors="surrogateescape"))
        digest.update(b":")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def case_overview_prerequisite_issues(root: Path) -> list[str]:
    issues = validate_participant_index_output(root)
    issues.extend(validate_summary_source_outputs(root))
    return list(dict.fromkeys(issues))


def validate_case_overview_output(root: Path) -> list[str]:
    root = root.resolve(strict=False)
    issues = case_overview_prerequisite_issues(root)
    path = case_overview_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [*issues, "artifacts/case_overview.md is missing or unreadable."]

    required_fragments = (
        "---\nartifact: recordprep-case-overview\n"
        "schema_version: 1\nstatus: nonauthoritative-orientation\n---",
        "# Case Overview",
        "> Orientation aid only. Verify every factual claim against mapped source "
        "pages before relying on or citing it.",
        "## Parties and Roles",
        "## Procedural Posture",
        "## Key Events",
        "## Principal Issues",
        "## Record Scope",
    )
    for fragment in required_fragments:
        if fragment not in text:
            issues.append(
                "artifacts/case_overview.md is missing required versioning, "
                "disclaimer, or section structure."
            )
            break

    prose = text.split("---", 2)[-1]
    word_count = len(re.findall(r"\b[\w’'-]+\b", prose, flags=re.UNICODE))
    if word_count < 150:
        issues.append("artifacts/case_overview.md must contain at least 150 prose words.")
    if word_count > 900:
        issues.append("artifacts/case_overview.md must not exceed 900 prose words.")

    manifest = _read_json(root / "manifest.json") or {}
    prerequisites = [root / "artifacts" / "participant_index.json"]
    for kind in ("hearings", "reports"):
        source = _summary_source(root, manifest, kind)
        if source is not None:
            prerequisites.append(source)
    minutes = _summary_source(root, manifest, "minutes")
    if minutes is not None:
        prerequisites.append(minutes)
    case_name = root / "case_name.txt"
    if case_name.is_file():
        prerequisites.append(case_name)
    try:
        if path.is_file() and any(
            source.is_file() and path.stat().st_mtime < source.stat().st_mtime
            for source in prerequisites
        ):
            issues.append("artifacts/case_overview.md is stale.")
    except OSError:
        issues.append("unable to compare case overview freshness.")
    return list(dict.fromkeys(issues))


def source_map_prerequisite_issues(root: Path) -> list[str]:
    issues = validate_transcript_layout_output(root)
    issues.extend(validate_transcript_numbering_outputs(root))
    issues.extend(validate_case_overview_output(root))
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
    overview_path = paths["case_overview"]
    source_map_path = paths["source_map"]
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
    issues.extend(validate_summary_source_outputs(root))
    issues.extend(validate_case_overview_output(root))

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
        source_paths = (
            source_map.get("paths")
            if isinstance(source_map.get("paths"), dict)
            else {}
        )
        if source_paths.get("case_overview") != "artifacts/case_overview.md":
            issues.append(
                "source_map.json paths.case_overview must be "
                "artifacts/case_overview.md."
            )

    issues.extend(validate_transcript_layout_output(root))

    expected_manifest_paths = dict(PREPARE_BUNDLE_MANIFEST_KEYS)
    for key, expected in expected_manifest_paths.items():
        if files.get(key) != expected:
            issues.append(f"manifest.json files.{key} must be {expected}.")

    freshness_pairs: list[tuple[Path, Path, str]] = []
    summary_sources = [
        source
        for kind in ("hearings", "reports", "minutes")
        if (source := _summary_source(root, manifest, kind)) is not None
    ]
    for prerequisite in (
        root / "artifacts" / "transcript_layout.json",
        transcript_path,
        series_path,
        participant_index_path,
        overview_path,
        *summary_sources,
    ):
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
    if step_id == "detect_transcript_layout":
        return validate_transcript_layout_output(root)
    if step_id == "number_transcript_pages":
        return validate_transcript_numbering_outputs(root)
    if step_id == "build_participant_index":
        issues = validate_transcript_numbering_outputs(root)
        issues.extend(validate_participant_index_output(root))
        return list(dict.fromkeys(issues))
    if step_id == "create_case_overview":
        return validate_case_overview_output(root)
    if step_id == "build_source_map":
        return validate_prepare_bundle_outputs(root)
    return [f"Unknown PI step: {step_id}"]


def pi_step_complete(step_id: str, root: Path) -> bool:
    return not validate_pi_step_outputs(step_id, root)
