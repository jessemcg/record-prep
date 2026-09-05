"""Synthetic summary-agent fixtures shared by pipeline tests.

Everything here is synthetic: no real case material. The helpers publish
canonical-shape digest rows, Markdown digest documents, metadata sidecars,
and final summaries so tests can build valid or deliberately malformed
bundles without paid calls. A legacy-writer helper constructs retired v2
JSONL bundles for migration tests only.
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
    """Build one canonical digest row.

    ``facts`` maps category id to a list of ``{"text", "evidence"}`` fact
    dicts (test readability only); the canonical digest text joins the fact
    texts and the evidence bank flattens their quotes with fresh quote ids.
    """
    if item_id is None:
        item_id = f"{sa.SUMMARY_ITEM_PREFIXES[kind]}:{start:04d}"
    categories: list[dict[str, Any]] = []
    for definition in sa.summary_category_definitions(kind):
        entry: dict[str, Any] = {"id": definition.identifier, "digest": None}
        if facts and definition.identifier in facts:
            digest_texts: list[str] = []
            evidence: list[dict[str, Any]] = []
            for fact in facts[definition.identifier]:
                digest_texts.append(str(fact.get("text") or ""))
                for quote in fact.get("evidence", []):
                    evidence.append(
                        {
                            "quote_id": sa.canonical_quote_id(
                                item_id,
                                definition.identifier,
                                len(evidence) + 1,
                            ),
                            "text": quote["text"],
                            "file_page": quote["file_page"],
                            "source_start": quote.get("source_start", 0),
                            "source_end": quote.get("source_end", 1),
                            "source_sha256": quote.get("source_sha256", "s" * 64),
                            "verified": quote.get("verified", True),
                        }
                    )
            entry["digest"] = {
                "text": " ".join(text for text in digest_texts if text),
                "evidence": evidence,
            }
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
        "quality_flags": [],
        "categories": categories,
    }


def write_facts_bundle(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    *,
    complete: bool = True,
) -> None:
    """Publish a canonical Markdown digest document and metadata sidecar."""
    markdown_path = sa.summary_digest_path(root, kind)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_text = sa.serialize_digest_markdown(
        kind, sa.summary_case_stem(root), list(rows)
    )
    markdown_path.write_text(markdown_text, encoding="utf-8")
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
        "digest_markdown_sha256": sa.digest_markdown_sha256(markdown_text),
        "markdown_format_version": sa.SUMMARY_DIGEST_MARKDOWN_FORMAT_VERSION,
        "quality_flags": {},
        "complete": complete,
    }
    sa.summary_digest_meta_path(root, kind).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


def write_legacy_digest_jsonl(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    *,
    jsonl_sha256: str | None = None,
    schema_version: int = 2,
) -> None:
    """Publish a retired v2 digest JSONL plus its v2 sidecar (migration tests)."""
    jsonl_path = sa.legacy_summary_digest_jsonl_path(root, kind)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        sa.serialize_legacy_digest_jsonl(list(rows)), encoding="utf-8"
    )
    meta = {
        "artifact": sa.SUMMARY_FACTS_META_ARTIFACT,
        "schema_version": schema_version,
        "kind": kind,
        "expected_item_ids": [row["item_id"] for row in rows],
        "completed": len(rows),
        "total": len(rows),
        "category_schema_sha256": "c" * 64,
        "source_boundary_fingerprint": "b" * 64,
        "extraction_config_sha256": "e" * 64,
        "jsonl_sha256": (
            jsonl_sha256
            if jsonl_sha256 is not None
            else sa.digest_jsonl_sha256(list(rows))
        ),
        "quality_flags": {},
        "complete": True,
    }
    sa.summary_digest_meta_path(root, kind).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


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
    meta = sa.build_final_meta(root, kind, list(rows), final_text, {}, {})
    sa._atomic_write(sa.summary_final_meta_path(root, kind), json.dumps(meta) + "\n")


def publish_valid_summary(
    root: Path,
    kind: str,
    rows: Sequence[dict[str, Any]],
    final_text: str,
) -> None:
    write_facts_bundle(root, kind, rows)
    write_final_summary(root, kind, rows, final_text)
