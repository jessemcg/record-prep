"""Conservative repair of NEW schema-4 candidates, never historical artifacts.

The reader stays strict. Generation may retain useful supported entries while
turning missing/invalid optional status information into explicit uncertainty.
Source paths and runner-owned hearing identities are not model repair targets.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath

from .profile_artifacts import PARTICIPANT_TEMPLATE_WARNING, participant_index_issues


class ParticipantCandidateError(ValueError):
    """Content-free candidate integrity failure suitable for model feedback."""


def normalize_participant_candidate(payload: dict, *, partial: bool = False) -> tuple[dict, list[str]]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 4:
        raise ParticipantCandidateError("Candidate must retain application schema_version 4.")
    result = deepcopy(payload)
    hearings = result.get("hearings")
    if not isinstance(hearings, list) or not hearings or not all(isinstance(h, dict) for h in hearings):
        raise ParticipantCandidateError("Candidate hearings must retain the prepared hearing objects.")
    changes: set[str] = set()

    def text(value):
        return value.strip() if isinstance(value, str) else ""

    def strings(value):
        return [v for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []

    def evidence(value):
        if not isinstance(value, list):
            hearing_changes.add("evidence_unresolved")
            return []
        out = []
        for item in value:
            if not isinstance(item, dict):
                hearing_changes.add("malformed_evidence_omitted")
                continue
            path = item.get("text_path", "")
            if not isinstance(path, str) or (path and (PurePosixPath(path).is_absolute()
                    or ".." in PurePosixPath(path).parts or "\\" in path)):
                raise ParticipantCandidateError("Candidate evidence contains an unsafe text_path; use relative text_pages paths.")
            # Missing evidence is not repaired by fabricating source references.
            if not path or not path.startswith("text_pages/") or not text(item.get("note")):
                hearing_changes.add("incomplete_evidence_omitted")
                continue
            out.append(item)
        return out

    for number, hearing in enumerate(hearings, 1):
        raw_warnings = hearing.get("warnings")
        warnings = [PARTICIPANT_TEMPLATE_WARNING] if raw_warnings == PARTICIPANT_TEMPLATE_WARNING else strings(raw_warnings)
        hearing["warnings"] = warnings
        # Never turn an untouched template into a reviewed empty hearing.
        if PARTICIPANT_TEMPLATE_WARNING in warnings:
            continue
        hearing_changes: set[str] = set()
        for group in ("counsel", "participants"):
            people = hearing.get(group)
            if not isinstance(people, list):
                people = []
                hearing_changes.add(f"{group}_unresolved")
            kept = []
            used_ids: set[str] = {text(p.get("id")) for p in people if isinstance(p, dict)}
            seen_ids: set[str] = set()
            for index, person in enumerate(people, 1):
                if not isinstance(person, dict):
                    hearing_changes.add("malformed_person_omitted")
                    continue
                person["evidence"] = evidence(person.get("evidence"))
                if not person["evidence"]:
                    hearing_changes.add("unsupported_person_omitted")
                    continue
                person["name"] = text(person.get("name"))
                person["aliases"] = strings(person.get("aliases"))
                if not person["name"] and not person["aliases"]:
                    hearing_changes.add("unidentified_person_omitted")
                    continue
                role = text(person.get("role_label"))
                if not role or len(role) > 512 or "\x00" in role:
                    role = "Unknown"
                    hearing_changes.add("role_unresolved")
                person["role_label"] = role
                if "role_id" in person:
                    person.pop("role_id")
                    hearing_changes.add("retired_role_id_removed")
                attendance = "appearance_status" if group == "counsel" else "attendance_status"
                for key, allowed in ((attendance, {"present", "remote", "absent", "unknown"}),
                                     ("speaking_status", {"spoke", "did_not_speak", "unknown"}),
                                     ("sworn_status", {"sworn", "unsworn", "not_applicable", "unknown"})):
                    value = text(person.get(key)).lower()
                    if value not in allowed:
                        value = "unknown"
                        hearing_changes.add("status_unresolved")
                    person[key] = value
                if group == "counsel":
                    person["organization"] = text(person.get("organization"))
                    represents = text(person.get("represents"))
                    if len(represents) > 512 or "\x00" in represents:
                        represents = ""
                        hearing_changes.add("representation_unresolved")
                    person["represents"] = represents
                else:
                    # These are internal hearing-local navigation IDs, not facts.
                    identifier = text(person.get("id"))
                    if not identifier or identifier in seen_ids:
                        identifier = f"participant:{number}:{index}"
                        while identifier in used_ids:
                            identifier += "_"
                        used_ids.add(identifier)
                        hearing_changes.add("navigation_id_repaired")
                    person["id"] = identifier
                    seen_ids.add(identifier)
                kept.append(person)
            hearing[group] = kept
        hearing["witness_evidence"] = evidence(hearing.get("witness_evidence"))
        witnesses = hearing.get("witnesses")
        if not isinstance(witnesses, list):
            witnesses = []
            hearing_changes.add("witnesses_unresolved")
        kept = []
        used_ids = {text(w.get("id")) for w in witnesses if isinstance(w, dict)}
        seen_ids = set()
        for index, witness in enumerate(witnesses, 1):
            if not isinstance(witness, dict) or not text(witness.get("name")):
                hearing_changes.add("unidentified_witness_omitted")
                continue
            witness["evidence"] = evidence(witness.get("evidence"))
            exams = witness.get("examinations")
            if not witness["evidence"] or not isinstance(exams, list) or not exams:
                hearing_changes.add("unsupported_witness_omitted")
                continue
            identifier = text(witness.get("id"))
            if not identifier or identifier in seen_ids:
                identifier = f"witness:{number}:{index}"
                while identifier in used_ids:
                    identifier += "_"
                used_ids.add(identifier)
                hearing_changes.add("navigation_id_repaired")
            witness["id"] = identifier
            seen_ids.add(identifier)
            witness["aliases"] = strings(witness.get("aliases"))
            witness["description"] = text(witness.get("description"))
            # Range/order/path errors are NOT repaired by inventing examinations.
            for exam in exams:
                if not isinstance(exam, dict):
                    raise ParticipantCandidateError("Examinations must be objects with hearing-scoped page ranges.")
                exam["evidence"] = evidence(exam.get("evidence"))
                exam["examiner_name"] = text(exam.get("examiner_name"))
                role = text(exam.get("examiner_role_label"))
                exam["examiner_role_label"] = role if len(role) <= 512 and "\x00" not in role else ""
                exam.pop("examiner_role_id", None)
                if text(exam.get("type")).lower() not in {"direct", "cross", "redirect", "recross", "court", "continued", "other"}:
                    exam["type"] = "other"
                    hearing_changes.add("examination_type_unresolved")
                else:
                    exam["type"] = text(exam["type"]).lower()
            if any(not exam["evidence"] for exam in exams):
                hearing_changes.add("unsupported_witness_omitted")
                continue
            kept.append(witness)
        hearing["witnesses"] = kept
        status = text(hearing.get("witness_status")).lower()
        if kept:
            counsel_names = {p["name"].casefold() for p in hearing["counsel"] if p["name"]}
            if status != "verified" or any(text(w.get("name")).casefold() in counsel_names for w in kept):
                status = "conflict"
                hearing_changes.add("witness_status_conflict")
        elif (status != "none" or not hearing["witness_evidence"]
              or {"unsupported_witness_omitted", "unidentified_witness_omitted"}.intersection(hearing_changes)):
            if status != "unknown":
                hearing_changes.add("witness_status_unresolved")
            status = "unknown"
        hearing["witness_status"] = status
        changes.update(hearing_changes)
        for code in sorted(hearing_changes):
            warning = f"Participant candidate quality: {code}; unresolved information is not a finding of absence."
            if warning not in warnings:
                warnings.append(warning)
    # A forgotten top-level marker is bookkeeping, provided every hearing was
    # explicitly reviewed. Hearing-level template markers remain hard failures.
    if all(PARTICIPANT_TEMPLATE_WARNING not in h["warnings"] for h in hearings):
        result["warnings"] = [w for w in strings(result.get("warnings")) if w != PARTICIPANT_TEMPLATE_WARNING]
    issues = participant_index_issues(result, partial=partial)
    if issues:
        # Reader messages can contain a witness name. Keep feedback content-free.
        import re
        safe = [re.sub(r"witness .* has no examinations", "witness has no examinations", issue) for issue in issues]
        raise ParticipantCandidateError("\n".join(safe[:20]))
    return result, sorted(changes)
