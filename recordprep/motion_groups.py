"""Contract-aware motion context over immutable physical paper identities.

Schema 2 is deterministic classification continuity; schema 1 remains historical
relationship metadata. Readers never migrate either policy or saved output.
"""
from __future__ import annotations

import hashlib
import json

from .profile_artifacts import validate_motion_groups, MOTION_CONTINUITY_EXPLANATION

ARTIFACT = "recordprep-motion-groups"
PATH = "artifacts/motion_groups.json"
ORGANIZATION_CONTRACT = "recordprep-motion-organization-2"
CONTINUITY_NOTE = MOTION_CONTINUITY_EXPLANATION


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def text(value, fallback="", limit=1024):
    return value.strip() if (isinstance(value, str) and value.strip() and len(value) <= limit
                            and all(c.isprintable() for c in value)) else fallback


def inventory_from_boundaries(rows, *, allow_unnamed=False):
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid physical motion inventory; prior output preserved.")
        try:
            start, end = int(row["start_page"]), int(row["end_page"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Invalid physical motion range; prior output preserved.") from None
        identifier = f"motion:{start:04d}"
        for key in ("motion_name", "motion_date", "naming_rule_id"):
            raw = row.get(key, "")
            if not isinstance(raw, str) or len(raw) > 1024 or not all(c.isprintable() for c in raw):
                raise ValueError("Invalid physical motion metadata; prior output preserved.")
        title = text(row.get("motion_name"))
        basis = row.get("motion_date_basis", "unknown")
        if (start < 1 or end < start or (not title and not allow_unnamed) or identifier in seen
                or not isinstance(basis, str) or basis not in {"filed", "document", "unknown"}
                or ("motion_id" in row and row["motion_id"] != identifier)):
            raise ValueError("Invalid/overlapping physical motion inventory; prior output preserved.")
        seen.add(identifier)
        result.append({"paper_id": identifier, "start_page": start, "end_page": end,
                       "source_title": title, "date": text(row.get("motion_date")),
                       "date_basis": basis, "naming_rule_id": text(row.get("naming_rule_id"))})
    result.sort(key=lambda p: p["start_page"])
    if any(left["end_page"] >= right["start_page"] for left, right in zip(result, result[1:])):
        raise ValueError("Overlapping physical motion inventory; prior output preserved.")
    return result


def boundaries_from_inventory(inventory):
    return [{"start_page": f"{p['start_page']:04d}", "end_page": f"{p['end_page']:04d}",
             "motion_id": p["paper_id"], "motion_name": p["source_title"], "motion_date": p["date"],
             "motion_date_basis": p["date_basis"],
             "motion_label": f"{p['date']} - {p['source_title']}" if p["date"] else p["source_title"],
             **({"naming_rule_id": p["naming_rule_id"]} if p["naming_rule_id"] else {})} for p in inventory]


def source_fingerprint(root, inventory):
    from .case_name_stage import _read
    hashes = {}
    for paper in inventory:
        for page in range(paper["start_page"], paper["end_page"] + 1):
            name = f"text_pages/{page:04d}.txt"
            if name in hashes:
                raise ValueError("Duplicate motion source membership; prior output preserved.")
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


def canonical_packets(inventory, packets, findings, input_sha256, *, inputs=None):
    by_id = {p["paper_id"]: p for p in inventory}
    groups = []
    for members in packets:
        lead = by_id[members[0]]
        group = singleton(lead, CONTINUITY_NOTE)
        group.update(filing_role="motion packet", member_paper_ids=list(members),
                     components=[{"paper_id": m, "role": "lead" if i == 0 else "continuation",
                                  "start_page": by_id[m]["start_page"], "end_page": by_id[m]["end_page"]}
                                 for i, m in enumerate(members)])
        groups.append(group)
    result = {"artifact": ARTIFACT, "schema_version": 2, "organization_contract": ORGANIZATION_CONTRACT,
              "inventory": inventory, "input_sha256": input_sha256, "inputs": inputs or {},
              "groups": groups, "findings": findings, "coverage_status": "complete"}
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


def resolve_context(root, boundaries=None, *, verify_classification=True):
    """Return inventory, groups, warning, and current saved artifact (or None).

    Without saved boundaries this resolves classification selection for TOC/boundary
    rebuilding. With boundaries, a current v2 selection must match exactly: consumers
    may not silently lose unnamed components. Stale/missing grouping uses named-only
    singleton compatibility, never unnamed singleton fabrication.
    """
    from .motion_organization import selected_inventory, MotionPreparationUnavailable
    value = load(root)
    continuous = value is not None and value["schema_version"] == 2
    selected = None
    classification = None
    if verify_classification:
        try:
            selected, classification = selected_inventory(root, continuous=continuous)
        except MotionPreparationUnavailable:
            pass
    if selected is None and boundaries is None:
        raise MotionPreparationUnavailable("Motion preparation unavailable; run final classification and naming.")
    fallback_boundaries = boundaries if continuous else [b for b in (boundaries or [])
        if text(b.get("motion_name")) and b.get("naming_status") != "unresolved"]
    candidate = selected if selected is not None else inventory_from_boundaries(fallback_boundaries, allow_unnamed=continuous)
    stale = value is None or (verify_classification and selected is None)
    if value is not None:
        fingerprint, _ = source_fingerprint(root, candidate)
        stale |= candidate != value["inventory"] or fingerprint != value["input_sha256"]
        if continuous and verify_classification:
            stale |= classification != value["inputs"].get("classification")
    if not stale:
        if boundaries is not None and inventory_from_boundaries(boundaries, allow_unnamed=continuous) != candidate:
            if continuous:
                raise ValueError("Motion boundaries do not match the current motion packet inventory. Run Find boundaries → Filter boundary entries before summaries or source map.")
            stale = True
        else:
            return candidate, value["groups"], "", value
    # Preserve historical saved-boundary behavior, but exclude unnamed standalone fragments.
    if boundaries is not None:
        named = [b for b in boundaries if text(b.get("motion_name")) and b.get("naming_status") != "unresolved"]
        inventory = inventory_from_boundaries(named)
    elif continuous:
        inventory, _ = selected_inventory(root, continuous=False)
    else:
        inventory = candidate
    warning = ("Grouping unavailable; using named physical entries. Run Organize motion papers to adopt packets."
               if value is None else "Grouping is stale; using named physical entries. Rerun Organize motion papers.")
    return inventory, [singleton(p) for p in inventory], warning, None


def current_groups(root, boundaries, *, verify_classification=True):
    _, groups, warning, _ = resolve_context(root, boundaries, verify_classification=verify_classification)
    return groups, warning


def count_text(count, singular, plural=None):
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def review_text(value):
    validate_motion_groups(value)
    papers = {p["paper_id"]: p for p in value["inventory"]}
    continuous = value["schema_version"] == 2
    lines = ["Motion grouping", ("Selected-inventory accounting: " if continuous else "Review coverage: ") + value['coverage_status'],
             f"{count_text(len(value['groups']), 'entry', 'entries')} / {count_text(len(papers), 'physical paper')}", ""]
    if continuous:
        lines.extend([CONTINUITY_NOTE, "Complete accounts for selected components only; it is not legal relationship review or inclusion of every motion fragment.", ""])
    for group in value["groups"]:
        lines.append(group["display_title"])
        lines.append(f"  {group['filing_role']}; lead source page {group['anchor_page']}; {group['group_id']}")
        if not continuous:
            lines.append("  Filing party: " + (group["filing_party"] or "Unknown"))
        lines.append(f"  Date: {group['date'] or 'Unknown'} ({group['date_basis']})")
        if group["purpose"]:
            lines.append("  Purpose: " + group["purpose"])
        lines.append("  Components:")
        roles = {part["paper_id"]: part["role"] for part in group["components"]}
        for member in group["member_paper_ids"]:
            paper = papers[member]
            lines.append(f"    {roles[member]}: {paper['source_title'] or 'Unnamed motion paper'} — source pages {paper['start_page']}–{paper['end_page']}")
        if group["relationship_notes"]:
            lines.append(("  Grouping explanation: " if continuous else "  Relationship explanation: ") + group["relationship_notes"])
        if group["relationship_to"]:
            lines.append("  Related entry: " + group["relationship_to"])
        lines.append("")
    lines.append("Notes:")
    lines.extend(value["findings"] or ["None recorded."])
    return "\n".join(lines)
