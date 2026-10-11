"""Versioned, instruction-free artifact metadata shared by Focus and RecordPrep.

Readers validate recorded descriptors, never current profiles or instruction stores.
Keep the vendored copies byte-identical. No filesystem access or acceptance here.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import PurePosixPath
from typing import Any

from .profile_contract import DIGEST, STAGE_RESOURCES, ProfileError, ProfileRef, ProfileSnapshot
from .profile_contract import _identifier, _object, _require, _text

PARTICIPANT_TEMPLATE_WARNING = "Participant review has not been completed."
LEGACY_COUNSEL_ROLES = (
    "mothers_counsel", "fathers_counsel", "alleged_fathers_counsel",
    "presumed_fathers_counsel", "parents_counsel", "minors_counsel",
    "county_counsel", "tribes_counsel", "guardian_ad_litem", "other_counsel", "unresolved_counsel",
)
LEGACY_PARTICIPANT_ROLES = (
    "mother", "father", "alleged_father", "presumed_father", "minor", "relative", "caregiver",
    "social_worker", "agency_representative", "judicial_officer", "interpreter", "audience_member",
    "other_participant", "unresolved_participant",
)


def descriptors(value: Any, *, roles: bool = False) -> tuple[tuple[str, str], ...]:
    """Bounded ordered structural metadata; guidance/paths are never accepted."""
    _require(isinstance(value, list) and 1 <= len(value) <= 128, "invalid_catalog", "artifact")
    label = "label" if roles else "title"
    result = []
    seen = set()
    for entry in value:
        _object(entry, {"id", label}, "artifact")
        identifier = _identifier(entry["id"], "artifact")
        _require(identifier not in seen, "duplicate_id", "artifact")
        seen.add(identifier)
        title = _text(entry[label], "artifact", 160)
        _require(title == title.strip() and not any(ord(c) < 32 or ord(c) == 127 for c in title),
                 "invalid_label", "artifact")
        result.append((identifier, title))
    return tuple(result)


def category_descriptor(snapshot: ProfileSnapshot, kind: str) -> list[dict[str, str]]:
    _require(snapshot.ref.application == "recordprep" and kind in ("hearings", "reports"),
             "wrong_application", "categories")
    result = [{"id": entry["id"], "title": entry["title"]} for entry in snapshot.resource(kind)]
    descriptors(result)
    return result


def role_descriptor(snapshot: ProfileSnapshot) -> dict[str, list[dict[str, str]]]:
    _require(snapshot.ref.application == "recordprep", "wrong_application", "roles")
    result = {group: [{"id": e["id"], "label": e["label"]} for e in entries]
              for group, entries in snapshot.resource("roles").items()}
    validate_role_descriptor(result)
    return result


def validate_role_descriptor(value: Any) -> dict[str, tuple[tuple[str, str], ...]]:
    _object(value, {"counsel", "participants"}, "roles")
    result = {group: descriptors(entries, roles=True) for group, entries in value.items()}
    for entries in result.values():
        _require({"unknown", "other"}.issubset(dict(entries)), "missing_fallback_roles", "roles")
    return result


def preparation_selection(value: Any) -> ProfileRef:
    """A case reference is metadata, never authorization to load instructions."""
    _object(value, {"schema_version", "profile_ref"}, "selection")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "unsupported_version", "selection")
    ref = ProfileRef.from_dict(value["profile_ref"])
    _require(ref.application == "recordprep", "wrong_application", "selection")
    return ref


def preparation_provenance(value: Any) -> dict:
    _object(value, {"schema_version", "profile_ref", "components"}, "provenance")
    _require(type(value["schema_version"]) is int and value["schema_version"] == 1,
             "unsupported_version", "provenance")
    ref = ProfileRef.from_dict(value["profile_ref"])
    _require(ref.application == "recordprep", "wrong_application", "provenance")
    components = value["components"]
    _require(isinstance(components, dict) and 1 <= len(components) <= len(STAGE_RESOURCES["recordprep"]),
             "invalid_components", "provenance")
    for stage, digest in components.items():
        _require(stage in STAGE_RESOURCES["recordprep"] and isinstance(digest, str)
                 and DIGEST.fullmatch(digest) is not None, "invalid_components", "provenance")
    return {"schema_version": 1, "profile_ref": asdict(ref), "components": dict(components)}


def digest_profile_metadata(value: Any, kind: str) -> dict:
    _require(kind in ("hearings", "reports"), "unsupported_kind", "digest")
    _object(value, {"category_catalog", "profile_provenance"}, "digest")
    catalog = descriptors(value["category_catalog"])
    provenance = preparation_provenance(value["profile_provenance"])
    stage = "hearing_extraction" if kind == "hearings" else "report_extraction"
    _require(stage in provenance["components"], "missing_component", "digest")
    return {"category_catalog": [{"id": i, "title": t} for i, t in catalog],
            "profile_provenance": provenance}


def participant_roles(payload: Any) -> dict[str, tuple[tuple[str, str], ...]]:
    _require(isinstance(payload, dict), "invalid_fields", "participants")
    version = payload.get("schema_version")
    _require(type(version) is int and version in (2, 3), "unsupported_version", "participants")
    if version == 2:
        _require(not {"role_catalog", "profile_provenance"}.intersection(payload),
                 "unexpected_profile_metadata", "participants")
        return {"counsel": tuple((i, i.replace("_", " ").title()) for i in LEGACY_COUNSEL_ROLES),
                "participants": tuple((i, i.replace("_", " ").title()) for i in LEGACY_PARTICIPANT_ROLES)}
    provenance = preparation_provenance(payload.get("profile_provenance"))
    _require("participants" in provenance["components"], "missing_component", "participants")
    return validate_role_descriptor(payload.get("role_catalog"))


def source_map_profile_metadata(payload: Any) -> dict | None:
    """Return validated preparation metadata without resolving any instructions."""
    _require(isinstance(payload, dict), "invalid_fields", "source_map")
    version = payload.get("schema_version", 1)
    _require(type(version) is int and version in (1, 2, 3), "unsupported_version", "source_map")
    if version < 3:
        _require("preparation_provenance" not in payload, "unexpected_profile_metadata", "source_map")
        participant = payload.get("participant_index")
        _require(not isinstance(participant, dict) or participant.get("schema_version", 2) in (1, 2),
                 "unsupported_version", "participants")
        return None
    provenance = preparation_provenance(payload.get("preparation_provenance"))
    participant = payload.get("participant_index")
    if participant is not None:
        _require(isinstance(participant, dict) and participant.get("schema_version") == 3,
                 "unsupported_version", "participants")
        _require(not participant_index_issues(participant, allow_empty=True),
                 "invalid_participants", "source_map")
    return provenance


def participant_index_issues(payload: Any, *, allow_empty: bool = False) -> list[str]:
    issues: list[str] = []
    try:
        catalog = participant_roles(payload)
    except ProfileError as exc:
        return [f"participant index metadata is invalid ({exc.issue.code})."]
    if payload.get("source") != "record-participant-index":
        issues.append("participant index has an invalid source.")
    hearings = payload.get("hearings")
    top_warnings = payload.get("warnings")
    if isinstance(top_warnings, list) and any(
        isinstance(item, str) and item == PARTICIPANT_TEMPLATE_WARNING
        for item in top_warnings
    ):
        issues.append(
            "participant index review has not been completed "
            "(template warning remains)."
        )
    if not isinstance(hearings, list) or (not hearings and not allow_empty):
        return [*issues, "participant index hearings must be a nonempty list."]
    valid_statuses = {"verified", "none", "unknown", "conflict"}
    valid_roles = dict(catalog["counsel"])
    valid_participant_roles = dict(catalog["participants"])
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
        hearing_warnings = hearing.get("warnings")
        if isinstance(hearing_warnings, list) and any(
            isinstance(item, str) and item == PARTICIPANT_TEMPLATE_WARNING
            for item in hearing_warnings
        ):
            issues.append(
                f"{label} has not been reviewed (template warning remains)."
            )
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
            if payload["schema_version"] == 3 and person.get("role_label") != valid_participant_roles.get(str(person.get("role_id") or "")):
                issues.append(f"{label} participant role_label disagrees with the recorded catalog.")
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
    if payload["schema_version"] == 3:
        issues.extend(_profile_evidence_issues(payload, valid_roles))
    return list(dict.fromkeys(issues))


def _profile_evidence_issues(payload: dict, counsel_roles: dict) -> list[str]:
    """Keep the native helper's evidence-path/examination safeguards for v3."""
    issues = []

    def evidence(value):
        if not isinstance(value, list):
            issues.append("participant evidence must be a list.")
            return
        for item in value:
            if not isinstance(item, dict):
                issues.append("participant evidence must contain objects.")
                continue
            path = item.get("text_path", "")
            if not isinstance(path, str) or (path and (PurePosixPath(path).is_absolute()
                    or ".." in PurePosixPath(path).parts or "\\" in path)):
                issues.append("participant evidence has an unsafe text_path.")

    for hearing in payload["hearings"]:
        if not isinstance(hearing, dict):
            continue
        evidence(hearing.get("witness_evidence"))
        for group in ("counsel", "participants", "witnesses"):
            people = hearing.get(group)
            if not isinstance(people, list):
                continue
            witness_ids = set()
            for person in people:
                if not isinstance(person, dict):
                    continue
                evidence(person.get("evidence"))
                if group != "witnesses":
                    continue
                identifier = str(person.get("id") or "")
                if not identifier or identifier in witness_ids:
                    issues.append("witness ids must be nonempty and unique within a hearing.")
                witness_ids.add(identifier)
                exams = person.get("examinations")
                if not isinstance(exams, list):
                    continue
                previous_start = 0
                for exam in exams:
                    if not isinstance(exam, dict):
                        continue
                    if exam.get("type") not in ("direct", "cross", "redirect", "recross", "court", "continued", "other"):
                        issues.append("participant examination type is invalid.")
                    role = str(exam.get("examiner_role_id") or "")
                    if role and role not in counsel_roles:
                        issues.append("participant examination role is not in its recorded catalog.")
                    try:
                        start = int(exam.get("start_file_page") or 0)
                    except (TypeError, ValueError):
                        start = 0
                    if start and previous_start and start < previous_start:
                        issues.append("participant examinations are out of order.")
                    previous_start = start or previous_start
                    evidence(exam.get("evidence"))
    return issues
