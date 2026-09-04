"""Synthetic summary-agent fixtures shared by pipeline tests.

Everything here is synthetic: no real case material. The helpers publish
canonical-shape facts rows, metadata sidecars, and final summaries so tests
can build valid or deliberately malformed bundles without paid calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from recordprep import summary_agents as sa


def synthetic_facts_row(
    kind: str = "hearings",
    item_id: str | None = None,
    ordinal: int = 1,
    label: str = "March 3, 2025",
    start: int = 1,
    end: int = 2,
    facts: dict[str, Any] | None = None,
    generation_sha256: str = "g" * 64,
    input_sha256: str = "i" * 64,
) -> dict[str, Any]:
    """Build one canonical facts row. ``facts`` maps category id to evidence."""
    if item_id is None:
        item_id = f"{sa.SUMMARY_ITEM_PREFIXES[kind]}:{start:04d}"
    categories: list[dict[str, Any]] = []
    for definition in sa.summary_category_definitions(kind):
        entry: dict[str, Any] = {"id": definition.identifier, "facts": None}
        if facts and definition.identifier in facts:
            canonical: list[dict[str, Any]] = []
            for fact_ordinal, fact in enumerate(facts[definition.identifier], start=1):
                evidence: list[dict[str, Any]] = []
                for evidence_ordinal, quote in enumerate(fact["evidence"], start=1):
                    evidence.append(
                        {
                            "quote_id": sa.canonical_quote_id(
                                item_id,
                                definition.identifier,
                                fact_ordinal,
                                evidence_ordinal,
                            ),
                            "text": quote["text"],
                            "file_page": quote["file_page"],
                            "source_start": quote.get("source_start", 0),
                            "source_end": quote.get("source_end", 1),
                            "source_sha256": quote.get("source_sha256", "s" * 64),
                        }
                    )
                canonical.append({"text": fact["text"], "evidence": evidence})
            entry["facts"] = canonical
        categories.append(entry)
    return {
        "artifact": sa.SUMMARY_FACTS_ARTIFACT,
        "schema_version": sa.SUMMARY_FACTS_SCHEMA_VERSION,
        "kind": kind,
        "item_id": item_id,
        "ordinal": ordinal,
        "label": label,
        "start_page": start,
        "end_page": end,
        "input_sha256": input_sha256,
        "generation_sha256": generation_sha256,
        "categories": categories,
    }


def write_facts_bundle(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    *,
    complete: bool = True,
) -> None:
    """Publish a facts JSONL and a matching metadata sidecar."""
    jsonl_path = sa.summary_facts_path(root, kind)
    meta_path = sa.summary_facts_meta_path(root, kind)
    sa.write_facts_jsonl(jsonl_path, list(rows))
    meta = {
        "artifact": sa.SUMMARY_FACTS_META_ARTIFACT,
        "schema_version": sa.SUMMARY_FACTS_META_SCHEMA_VERSION,
        "kind": kind,
        "expected_item_ids": [row["item_id"] for row in rows],
        "completed": len(rows),
        "total": len(rows),
        "category_schema_sha256": "c" * 64,
        "source_boundary_fingerprint": "b" * 64,
        "extraction_config_sha256": "e" * 64,
        "jsonl_sha256": sa.facts_jsonl_sha256(list(rows)),
        "complete": complete,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def write_final_summary(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    final_text: str,
) -> None:
    """Publish a final summary text and its matching metadata sidecar."""
    final_path = sa.summary_final_path(root, kind)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(final_text, encoding="utf-8")
    meta = sa.build_final_meta(kind, list(rows), final_text, {}, {})
    sa._atomic_write(sa.summary_final_meta_path(root, kind), json.dumps(meta) + "\n")


def publish_valid_summary(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    final_text: str,
) -> None:
    write_facts_bundle(root, kind, rows)
    write_final_summary(root, kind, rows, final_text)
