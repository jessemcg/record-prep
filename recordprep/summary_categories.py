"""Strict loader for the tracked summary-category guidance resources.

Category ids, display titles, ordering, and null semantics are code-owned
here; only the per-category guidance prose lives in the tracked Markdown
resources under ``recordprep/resources/summary_categories/``. The loader
uses only the standard library and fails with actionable errors before any
paid work when a resource is missing or malformed — embedded fallback
guidance is never silently substituted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SUMMARY_CATEGORIES_RESOURCE_VERSION = 1
RESOURCE_HEADER_ARTIFACT = "recordprep:summary-categories"
DEFAULT_RESOURCE_DIR = Path(__file__).resolve().parent / "resources" / "summary_categories"

_HEADER_PATTERN = re.compile(
    rf"^<!--\s*{re.escape(RESOURCE_HEADER_ARTIFACT)}\s+"
    rf"v(?P<version>\d+)\s+kind:(?P<kind>[a-z]+)\s*-->\s*$"
)
_HEADING_PATTERN = re.compile(r"^##\s+(?P<id>\S+)\s*$")


class SummaryResourceError(ValueError):
    """A tracked summary resource is missing or malformed."""


@dataclass(frozen=True, slots=True)
class CategoryContract:
    """Code-owned category identity; guidance lives in the resource file."""

    identifier: str
    title: str


# Code-owned category ids, display titles, and order per summary kind.
CATEGORY_CONTRACTS: dict[str, tuple[CategoryContract, ...]] = {
    "hearings": (
        CategoryContract("parent_appearances", "Parent Appearances"),
        CategoryContract("evidence_considered", "Evidence Considered"),
        CategoryContract("testimony", "Testimony"),
        CategoryContract("disputed_legal_issues", "Disputed Legal Issues"),
        CategoryContract(
            "party_positions_and_reasons", "Party Positions and Reasons"
        ),
        CategoryContract("court_orders_and_reasons", "Court Orders and Reasons"),
    ),
    "reports": (
        CategoryContract("agency_recommendations", "Agency Recommendations"),
        CategoryContract("petition_events", "Petition Events"),
        CategoryContract(
            "allegation_interviews_and_evidence",
            "Allegations, Interviews, and Evidence",
        ),
        CategoryContract(
            "disputed_issues_and_party_positions",
            "Disputed Issues and Party Positions",
        ),
        CategoryContract("court_findings_and_orders", "Court Findings and Orders"),
        CategoryContract("reunification_barriers", "Reunification Barriers"),
        CategoryContract(
            "new_setbacks_or_material_changes", "New Setbacks or Material Changes"
        ),
        CategoryContract("indian_ancestry", "Indian Ancestry"),
        CategoryContract("services_progress", "Services Progress"),
        CategoryContract(
            "visitation_frequency_and_quality", "Visitation"
        ),
        CategoryContract(
            "parent_relationship_history", "Parent-Child Relationship"
        ),
        CategoryContract(
            "placement_and_caregiver_adoption_approval",
            "Placement and Caregiver Approval",
        ),
    ),
}

RESOURCE_FILENAMES: dict[str, str] = {
    "hearings": "hearings.md",
    "reports": "reports.md",
}


def summary_category_resource_path(kind: str, *, resource_dir: Path | None = None) -> Path:
    """Repository path of one kind's category-guidance resource."""
    if kind not in RESOURCE_FILENAMES:
        raise SummaryResourceError(f"Unknown summary kind: {kind}")
    return (resource_dir or DEFAULT_RESOURCE_DIR) / RESOURCE_FILENAMES[kind]


def parse_category_descriptions(
    kind: str,
    resource_text: str,
    *,
    resource_path: Path | None = None,
) -> dict[str, str]:
    """Parse one category resource strictly, returning id -> guidance prose.

    Raises :class:`SummaryResourceError` with an actionable message when the
    header is missing or unsupported, a heading is duplicated, unknown, or
    out of order, a code-owned category is missing, or a description is
    empty.
    """
    label = f"{resource_path.name if resource_path else kind} category resource"
    lines = resource_text.splitlines()
    if not lines:
        raise SummaryResourceError(f"{label} is empty.")
    header = _HEADER_PATTERN.match(lines[0].strip())
    if header is None:
        raise SummaryResourceError(
            f"{label} must start with the exact header comment "
            f"'<!-- {RESOURCE_HEADER_ARTIFACT} "
            f"v{SUMMARY_CATEGORIES_RESOURCE_VERSION} kind:{kind} -->'."
        )
    if int(header.group("version")) != SUMMARY_CATEGORIES_RESOURCE_VERSION:
        raise SummaryResourceError(
            f"{label} declares unsupported resource version "
            f"v{header.group('version')}; this RecordPrep supports "
            f"v{SUMMARY_CATEGORIES_RESOURCE_VERSION}."
        )
    if header.group("kind") != kind:
        raise SummaryResourceError(
            f"{label} declares kind '{header.group('kind')}' but was loaded "
            f"for kind '{kind}'."
        )

    contracts = CATEGORY_CONTRACTS[kind]
    expected_ids = [contract.identifier for contract in contracts]
    descriptions: dict[str, str] = {}
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    for line in lines[1:]:
        heading = _HEADING_PATTERN.match(line.strip())
        if heading is not None:
            current = heading.group("id")
            if current in buckets:
                raise SummaryResourceError(
                    f"{label} declares category '{current}' more than once; "
                    "each category id must appear exactly once."
                )
            if current not in expected_ids:
                raise SummaryResourceError(
                    f"{label} declares unknown category '{current}'; the "
                    f"configured {kind} categories are: "
                    f"{', '.join(expected_ids)}."
                )
            buckets[current] = []
            order.append(current)
            continue
        if current is not None:
            buckets[current].append(line)
    for category_id, text in buckets.items():
        descriptions[category_id] = "\n".join(text).strip()

    if order != expected_ids:
        missing = [key for key in expected_ids if key not in buckets]
        if missing:
            raise SummaryResourceError(
                f"{label} is missing category sections: {', '.join(missing)}."
            )
        raise SummaryResourceError(
            f"{label} declares categories out of the configured order; "
            f"expected: {', '.join(expected_ids)} "
            f"(found: {', '.join(order)})."
        )
    empty = [key for key in expected_ids if not descriptions[key]]
    if empty:
        raise SummaryResourceError(
            f"{label} has empty guidance for: {', '.join(empty)}; write "
            "guidance prose or delete the category's headings entirely — an "
            "empty section is never accepted."
        )
    return descriptions


def load_category_descriptions(
    kind: str,
    *,
    resource_dir: Path | None = None,
) -> dict[str, str]:
    """Load and validate one kind's category descriptions from disk."""
    path = summary_category_resource_path(kind, resource_dir=resource_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SummaryResourceError(
            f"The {kind} category resource is missing: {path}. Restore the "
            "tracked file under recordprep/resources/summary_categories/."
        ) from exc
    except OSError as exc:
        raise SummaryResourceError(
            f"The {kind} category resource is unreadable: {path}: {exc}"
        ) from exc
    return parse_category_descriptions(kind, text, resource_path=path)


def category_contracts(kind: str) -> tuple[CategoryContract, ...]:
    if kind not in CATEGORY_CONTRACTS:
        raise SummaryResourceError(f"Unknown summary kind: {kind}")
    return CATEGORY_CONTRACTS[kind]


def category_ids(kind: str) -> tuple[str, ...]:
    return tuple(contract.identifier for contract in category_contracts(kind))


def category_titles(kind: str) -> tuple[str, ...]:
    return tuple(contract.title for contract in category_contracts(kind))


def validate_resource_dir(resource_dir: Path, kinds: Iterable[str] | None = None) -> list[str]:
    """Load every requested kind's resource; return actionable error strings."""
    issues: list[str] = []
    for kind in kinds or CATEGORY_CONTRACTS:
        try:
            load_category_descriptions(kind, resource_dir=resource_dir)
        except SummaryResourceError as exc:
            issues.append(str(exc))
    return issues
