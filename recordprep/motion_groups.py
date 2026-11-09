"""Logical motion entries over immutable physical paper identities/ranges.

No inference from proximity. Only the organization agent proposes relationships;
Python normalizes proposals independently, retains singletons and owns publication.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .motion_guidance import ORGANIZATION_CONTRACT
from .profile_artifacts import validate_motion_groups

ARTIFACT = "recordprep-motion-groups"
PATH = "artifacts/motion_groups.json"
ROLES = {"motion/application", "opposition", "reply", "supplement", "unresolved supporting paper"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def text(value, fallback="", limit=1024):
    return value.strip() if (isinstance(value, str) and value.strip() and len(value) <= limit
                            and all(c.isprintable() for c in value)) else fallback


def inventory_from_boundaries(rows):
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid physical motion inventory; prior output preserved.")
        try:
            start, end = int(row["start_page"]), int(row["end_page"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid physical motion range; prior output preserved.") from None
        identifier = f"motion:{start:04d}"
        title = text(row.get("motion_name"))
        basis = row.get("motion_date_basis", "unknown")
        if (start < 1 or end < start or not title or identifier in seen
                or not isinstance(basis, str) or basis not in {"filed", "document", "unknown"}):
            raise ValueError("Invalid/overlapping physical motion inventory; prior output preserved.")
        seen.add(identifier)
        result.append({"paper_id": identifier, "start_page": start, "end_page": end,
                       "source_title": title, "date": text(row.get("motion_date")),
                       "date_basis": basis, "naming_rule_id": text(row.get("naming_rule_id"))})
    result.sort(key=lambda p: p["start_page"])
    if any(left["end_page"] >= right["start_page"] for left, right in zip(result, result[1:])):
        raise ValueError("Overlapping physical motion inventory; prior output preserved.")
    return result


def source_fingerprint(root, inventory):
    # Safe reads reject links, special files, missing pages and changed inventories.
    from .case_name_stage import _read
    hashes = {}
    for paper in inventory:
        for page in range(paper["start_page"], paper["end_page"] + 1):
            name = f"text_pages/{page:04d}.txt"
            hashes[name] = hashlib.sha256(_read(root / name, 16 * 1024 * 1024)).hexdigest()
    return digest({"inventory": inventory, "sources": hashes}), hashes


def singleton(paper, note="Not linked to a lead paper; retained as a standalone entry."):
    return {"group_id": paper["paper_id"], "lead_paper_id": paper["paper_id"],
            "anchor_page": paper["start_page"], "filing_role": "unresolved supporting paper",
            "member_paper_ids": [paper["paper_id"]],
            "components": [{"paper_id": paper["paper_id"], "role": "unresolved",
                            "start_page": paper["start_page"], "end_page": paper["end_page"]}],
            "display_title": paper["source_title"], "filing_party": "", "purpose": "",
            "date": paper["date"], "date_basis": paper["date_basis"],
            "relationship_to": "", "relationship_notes": note}


def normalize_candidate(candidate, inventory, input_sha256, *, inputs=None):
    """Reject contradictory proposals locally, never discard selected papers.

    All proposals sharing a duplicate assignment are rejected, not first-wins.
    Relationship evidence is reviewable prose, not an evidence-matching gate.
    """
    by_id = {p["paper_id"]: p for p in inventory}
    findings, proposals, counts = [], [], {}
    good_output = isinstance(candidate, dict) and isinstance(candidate.get("groups"), list)
    # Review coverage is independent of advisory prose and unresolved relationships.
    # Only rejected membership work or automatic fallback makes accounting incomplete.
    coverage_problem = not good_output
    raw = candidate["groups"] if good_output else []
    if not good_output and inventory:
        findings.append("Successful agent returned no usable grouping candidate; singleton coverage is incomplete.")
    for value in raw:
        members = value.get("member_paper_ids") if isinstance(value, dict) else None
        lead = value.get("lead_paper_id") if isinstance(value, dict) else None
        if (not isinstance(members, list) or not members or any(not isinstance(m, str) for m in members)
                or len(members) != len(set(members)) or lead not in members
                or any(m not in by_id for m in members) or not isinstance(value.get("filing_role"), str)
                or value["filing_role"] not in ROLES):
            coverage_problem = True
            findings.append("Malformed group or unknown/contradictory references; affected papers remain standalone.")
            # Known IDs in malformed proposals also participate in duplicate checks.
            for m in members if isinstance(members, list) else []:
                if isinstance(m, str) and m in by_id:
                    counts[m] = counts.get(m, 0) + 1
            continue
        proposals.append(value)
        for member in members:
            counts[member] = counts.get(member, 0) + 1
    groups, assigned = [], set()
    for proposal in proposals:
        members = proposal["member_paper_ids"]
        if any(counts[m] != 1 for m in members):
            coverage_problem = True
            findings.append("Duplicate membership proposals rejected; affected papers remain standalone.")
            continue
        lead = by_id[proposal["lead_paper_id"]]
        group = singleton(lead, "")
        if not text(proposal.get("display_title")):
            findings.append("Short title unavailable; original source title retained without truncation.")
        ordered = sorted(members, key=lambda m: by_id[m]["start_page"])
        roles = {}
        for component in proposal.get("components", []) if isinstance(proposal.get("components"), list) else []:
            if isinstance(component, dict) and component.get("paper_id") in ordered:
                roles[component["paper_id"]] = text(component.get("role"), "support", 160)
        group.update(member_paper_ids=ordered, filing_role=proposal["filing_role"],
                     components=[{"paper_id": m, "role": roles.get(m, "lead" if m == lead["paper_id"] else "support"),
                                  "start_page": by_id[m]["start_page"], "end_page": by_id[m]["end_page"]} for m in ordered],
                     display_title=text(proposal.get("display_title"), lead["source_title"]),
                     filing_party=text(proposal.get("filing_party")), purpose=text(proposal.get("purpose")),
                     relationship_notes=text(proposal.get("relationship_notes"), text(proposal.get("evidence"))),
                     relationship_to=text(proposal.get("relationship_to")))
        # Never replace a known filed date with a model-recovered signature date.
        basis = proposal.get("date_basis")
        if isinstance(basis, str) and basis in {"filed", "document"} and (not lead["date"] or (lead["date_basis"] != "filed" and basis == "filed")):
            from .document_naming import _date_value
            candidate_date = proposal.get("date")
            recovered = _date_value(candidate_date) if isinstance(candidate_date, str) else None
            if recovered:
                group.update(date=recovered, date_basis=basis)
            else:
                findings.append("Optional date recovery unavailable; original lead date and basis retained.")
        groups.append(group)
        assigned.update(ordered)
    for paper in inventory:
        if paper["paper_id"] not in assigned:
            coverage_problem = True
            groups.append(singleton(paper))
            findings.append("Unassigned or unresolved physical paper retained as a standalone entry.")
    group_ids = {g["group_id"] for g in groups}
    for group in groups:
        if group["relationship_to"] and (group["relationship_to"] not in group_ids or group["relationship_to"] == group["group_id"]):
            group["relationship_to"] = ""
            findings.append("Unresolved relationship reference omitted; source paper retained.")
    if isinstance(candidate, dict) and isinstance(candidate.get("findings"), list):
        findings.extend(text(f) for f in candidate["findings"] if text(f))
    result = {"artifact": ARTIFACT, "schema_version": 1, "organization_contract": ORGANIZATION_CONTRACT,
              "inventory": copy.deepcopy(inventory), "input_sha256": input_sha256,
              "inputs": inputs or {}, "groups": sorted(groups, key=lambda g: g["anchor_page"]),
              "findings": list(dict.fromkeys(findings)),
              "coverage_status": "complete" if (not inventory or (good_output and not coverage_problem
                  and assigned == set(by_id) and candidate.get("coverage_status") == "complete")) else "incomplete"}
    validate_motion_groups(result)
    return result


def output_fingerprint(root):
    from .case_name_stage import _read, _sha
    path = root / PATH
    return _sha(_read(path, 16 * 1024 * 1024)) if path.exists() or path.is_symlink() else "absent"


def load(root):
    path = root / PATH
    if not path.exists() and not path.is_symlink():
        return None
    from .case_name_stage import _read
    from .profile_contract import _json
    value = _json(_read(path, 16 * 1024 * 1024), "motion_groups")
    validate_motion_groups(value)
    return value


def current_groups(root, boundaries, *, verify_classification=True):
    """Missing/stale is legacy singleton mode; corrupt canonical data raises.

    Membership must match both saved physical boundaries and resolved selection.
    Does not consult model/profile settings or rewrite anything.
    """
    inventory = inventory_from_boundaries(boundaries)
    value = load(root)
    if value is None:
        return [singleton(p) for p in inventory], "Grouping unavailable; using physical entries. Run Organize motion papers to adopt grouped entries."
    fingerprint, _ = source_fingerprint(root, inventory)
    stale = value["inventory"] != inventory or value["input_sha256"] != fingerprint
    if verify_classification:
        from .motion_organization import selected_inventory, MotionPreparationUnavailable
        try:
            selected, _ = selected_inventory(root)
        except MotionPreparationUnavailable:
            # Historical preparation absence allows singleton compatibility.
            # Corrupt/unreadable present classification remains a genuine failure.
            stale = True
        else:
            stale |= selected != inventory
    if stale:
        return [singleton(p) for p in inventory], "Grouping is stale; using current physical entries. Rerun Organize motion papers."
    return value["groups"], ""


def count_text(count, singular, plural=None):
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def review_text(value):
    validate_motion_groups(value)
    papers = {p["paper_id"]: p for p in value["inventory"]}
    lines = ["Motion grouping", f"Review coverage: {value['coverage_status']}",
             f"{count_text(len(value['groups']), 'entry', 'entries')} / {count_text(len(papers), 'physical paper')}", ""]
    for group in value["groups"]:
        lines.append(group["display_title"])
        lines.append(f"  {group['filing_role']}; lead source page {group['anchor_page']}; {group['group_id']}")
        lines.append("  Filing party: " + (group["filing_party"] or "Unknown"))
        lines.append(f"  Date: {group['date'] or 'Unknown'} ({group['date_basis']})")
        if group["purpose"]:
            lines.append("  Purpose: " + group["purpose"])
        lines.append("  Components:")
        roles = {part["paper_id"]: part["role"] for part in group["components"]}
        for member in group["member_paper_ids"]:
            paper = papers[member]
            lines.append(f"    {roles[member]}: {paper['source_title']} — source pages {paper['start_page']}–{paper['end_page']}")
        if group["relationship_notes"]:
            lines.append("  Relationship explanation: " + group["relationship_notes"])
        if group["relationship_to"]:
            lines.append("  Related entry: " + group["relationship_to"])
        lines.append("")
    lines.append("Notes:")
    lines.extend(value["findings"] or ["None recorded."])
    return "\n".join(lines)
