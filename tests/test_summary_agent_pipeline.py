"""Two-stage summary-agent pipeline tests.

Synthetic only: no real case material and no paid calls. Covers the category
digest contracts, permissive candidate normalization, quote resolution,
window coverage, atomic Markdown publication, resume semantics, synthesis
normalization (deterministic fallback and warning codes), deterministic
plain-text rendering, settings persistence without .pi/settings.json
mutation, and end-to-end runner acceptance runs against a fake PI executable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from recordprep import pi_bundle, summary_agents as sa
from recordprep.summary_editions import (
    build_summary_edition,
    publish_summary_edition,
    summary_edition_is_complete,
    validate_summary_edition_files,
)
from tests.summary_agent_fixtures import (
    publish_valid_summary,
    synthetic_facts_row,
    write_facts_bundle,
    write_legacy_digest_jsonl,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
RUNNER = PROJECT_DIR / ".pi" / "scripts" / "run_recordprep_skill.py"


def _boundary_entry(start: int, end: int, date: str, name: str = "") -> dict:
    entry: dict = {"date": date, "start_page": f"{start:04d}", "end_page": f"{end:04d}"}
    if name:
        entry["report_name"] = name
        entry["report_date"] = date
        entry["report_label"] = f"{date} - {name}"
    return entry


def _participant_index(hearings: list[tuple[int, int, str]]) -> dict:
    return {
        "schema_version": 2,
        "source": "record-participant-index",
        "warnings": [],
        "hearings": [
            {
                "id": f"hearing:{start:04d}",
                "date": date,
                "start_page": start,
                "end_page": end,
                "witness_status": "none",
                "witness_evidence": [
                    {
                        "text_path": f"text_pages/{start:04d}.txt",
                        "file_page": start,
                        "citation_label": f"RT {start}",
                        "citation_key": f"RT:{start}",
                        "note": "Synthetic no-witness index.",
                    }
                ],
                "witnesses": [],
                "counsel": [],
                "participants": [],
                "warnings": ["Synthetic review complete."],
            }
            for start, end, date in hearings
        ],
    }


class BundleBuilder:
    """Synthetic case bundle with unique quotable markers per document."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "text_pages").mkdir(parents=True)
        (root / "artifacts").mkdir(parents=True)
        (root / "case_name.txt").write_text("SynCase", encoding="utf-8")

    def add_pages(self, start: int, end: int, marker: str) -> None:
        for number in range(start, end + 1):
            (self.root / "text_pages" / f"{number:04d}.txt").write_text(
                f"Page {number} narrative. QUOTEME:{marker} unique phrase here.\n",
                encoding="utf-8",
            )

    def finish(
        self,
        hearings: list[tuple[int, int, str]],
        reports: list[tuple[int, int, str, str]],
        minutes: list[tuple[int, int, str]] | None = None,
    ) -> None:
        transcript = {
            "schema_version": 2,
            "entries": [
                {"file_page": number, "citation_label": f"RT {number}"}
                for number in range(1, 60)
            ],
            "citation_series": [],
        }
        (self.root / "artifacts" / "transcript_page_numbers.json").write_text(
            json.dumps(transcript), encoding="utf-8"
        )
        (self.root / "artifacts" / "hearing_boundaries.json").write_text(
            json.dumps([_boundary_entry(s, e, d) for s, e, d in hearings]),
            encoding="utf-8",
        )
        (self.root / "artifacts" / "report_boundaries.json").write_text(
            json.dumps(
                [_boundary_entry(s, e, d, n) for s, e, d, n in reports]
            ),
            encoding="utf-8",
        )
        (self.root / "artifacts" / "minutes_boundaries.json").write_text(
            json.dumps(
                [
                    _boundary_entry(s, e, d)
                    for s, e, d in (minutes or [(s, e, d) for s, e, d, _ in reports])
                ]
            ),
            encoding="utf-8",
        )
        (self.root / "artifacts" / "participant_index.json").write_text(
            json.dumps(
                _participant_index([(s, e, d) for s, e, d in hearings])
            ),
            encoding="utf-8",
        )


def _extraction_config(kind: str = "hearings", **overrides) -> sa.ExtractionConfig:
    defaults: dict[str, Any] = {
        "kind": kind,
        "guidance": (
            sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE
            if kind == "hearings"
            else sa.DEFAULT_REPORT_EXTRACTION_GUIDANCE
        ),
        "model": "synthetic-model",
        "provider": "synthetic",
        "thinking": "low",
    }
    defaults.update(overrides)
    return sa.ExtractionConfig(**defaults)


class CategoryContractTests(unittest.TestCase):
    def test_exact_category_ids_and_order(self) -> None:
        self.assertEqual(
            sa.SUMMARY_CATEGORY_IDS["hearings"],
            (
                "parent_appearances",
                "evidence_considered",
                "testimony",
                "disputed_legal_issues",
                "party_positions_and_reasons",
                "court_orders_and_reasons",
            ),
        )
        self.assertEqual(
            sa.SUMMARY_CATEGORY_IDS["reports"],
            (
                "agency_recommendations",
                "petition_events",
                "allegation_interviews_and_evidence",
                "disputed_issues_and_party_positions",
                "court_findings_and_orders",
                "reunification_barriers",
                "new_setbacks_or_material_changes",
                "indian_ancestry",
                "services_progress",
                "visitation_frequency_and_quality",
                "parent_relationship_history",
                "placement_and_caregiver_adoption_approval",
            ),
        )

    def test_digest_schema_contract(self) -> None:
        self.assertEqual(sa.SUMMARY_FACTS_SCHEMA_VERSION, 2)
        self.assertEqual(sa.SUMMARY_FACTS_ARTIFACT, "recordprep-summary-digest")
        self.assertEqual(sa.SUMMARY_RENDERER_VERSION, "recordprep-summary-renderer-5")
        row = synthetic_facts_row("hearings")
        self.assertEqual(sa.validate_digest_row(row), [])
        for category in row["categories"]:
            self.assertIsNone(category["digest"])

    def test_digest_paths_use_new_names_and_lock_path_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "case_name.txt").write_text("SynCase", encoding="utf-8")
            self.assertEqual(
                sa.summary_digest_path(root, "hearings").name,
                "hearings_digests_SynCase.md",
            )
            self.assertEqual(
                sa.summary_digest_meta_path(root, "reports").name,
                "reports_digests_SynCase.meta.json",
            )
            self.assertEqual(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").name,
                "hearings_digests_SynCase.jsonl",
            )
            self.assertEqual(
                sa.legacy_summary_facts_path(root, "hearings").name,
                "hearings_facts_SynCase.jsonl",
            )
            self.assertEqual(
                sa.SummaryKindLock(root, "hearings")._path.name,
                ".hearings_facts.lock",
            )

    def test_canonical_row_orders_and_fills_categories(self) -> None:
        """Exactly one null-or-object digest per category in canonical order."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            candidate = {
                # A wrong submitted item_id is ignored and re-owned.
                "item_id": "hearing:9999",
                "categories": [
                    {"id": "testimony", "digest": {"text": "Later category."}},
                    {"id": "not_a_category", "digest": {"text": "Unknown."}},
                    {"id": "parent_appearances", "digest": None},
                    {"id": "parent_appearances", "digest": {"text": "Duplicate."}},
                ],
            }
            warnings: list[str] = []
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages", warnings=warnings
            )
            ids = [category["id"] for category in row["categories"]]
            self.assertEqual(ids, list(sa.SUMMARY_CATEGORY_IDS["hearings"]))
            by_id = {category["id"]: category for category in row["categories"]}
            # First usable duplicate wins.
            self.assertEqual(
                by_id["parent_appearances"]["digest"],
                {"text": "Duplicate.", "evidence": []},
            )
            self.assertEqual(by_id["testimony"]["digest"]["text"], "Later category.")
            # Missing/malformed/unknown categories fill with null.
            self.assertIsNone(by_id["evidence_considered"]["digest"])
            flags = " ".join(row["quality_flags"])
            self.assertIn("unknown_categories_ignored:1", flags)
            self.assertIn("duplicate_categories:1", flags)
            self.assertIn("missing_categories_filled_null:", flags)
            self.assertIn("candidate_item_id_ignored", " ".join(warnings) + flags)

    def test_malformed_candidate_normalizes_with_flags_not_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            text_dir = root / "text_pages"

            # Wholly unusable candidates publish all-null rows with flags.
            for unusable in (None, {"categories": "not-a-list"}, [1, 2, 3]):
                warnings: list[str] = []
                row = sa.canonicalize_extraction_candidate(
                    unusable, items[0], text_dir, warnings=warnings
                )
                self.assertTrue(
                    all(category["digest"] is None for category in row["categories"])
                )
                self.assertTrue(
                    any("candidate_unusable" in flag for flag in row["quality_flags"])
                )

            # Whitespace is collapsed in digest text; malformed digests fill null.
            candidate = {
                "categories": [
                    {
                        "id": "parent_appearances",
                        "digest": {"text": "Spaced   out\t text.\n"},
                    },
                    {"id": "evidence_considered", "digest": ["not an object"]},
                    {"id": "testimony", "digest": {"text": "   "}},
                ]
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], text_dir
            )
            by_id = {category["id"]: category for category in row["categories"]}
            self.assertEqual(
                by_id["parent_appearances"]["digest"]["text"],
                "Spaced out text.",
            )
            self.assertEqual(by_id["parent_appearances"]["digest"]["evidence"], [])
            self.assertIsNone(by_id["evidence_considered"]["digest"])
            self.assertIsNone(by_id["testimony"]["digest"])
            flags = " ".join(row["quality_flags"])
            self.assertIn("empty_evidence_kept:parent_appearances", flags)
            self.assertIn("malformed_digest_filled_null:evidence_considered", flags)

    def test_flattened_string_digest_variant_is_accepted(self) -> None:
        """The common flattened model shape normalizes to the canonical form."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            candidate = {
                "item_id": "ignored",
                "categories": [
                    {
                        "id": "parent_appearances",
                        "digest": "Mother appeared remotely for the hearing.",
                        "text": "Mother appeared remotely for the hearing.",
                        "evidence": [
                            {"text": "unique phrase", "file_page": "1"}
                        ],
                    },
                    {"id": "testimony", "digest": None, "evidence": []},
                ],
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            by_id = {category["id"]: category for category in row["categories"]}
            self.assertEqual(
                by_id["parent_appearances"]["digest"]["text"],
                "Mother appeared remotely for the hearing.",
            )
            evidence = by_id["parent_appearances"]["digest"]["evidence"]
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["file_page"], 1)
            self.assertTrue(evidence[0]["verified"])
            self.assertIsNone(by_id["testimony"]["digest"])
            flags = " ".join(row["quality_flags"])
            self.assertIn("candidate_item_id_ignored", flags)
            self.assertNotIn("malformed_digest", flags)

    def test_empty_facts_shape_is_normalized_not_rejected(self) -> None:
        """The old empty-facts rejection is now normalization with flags."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            candidate = {
                "item_id": items[0].item_id,
                "categories": [
                    {"id": category.identifier, "digest": None}
                    for category in sa.summary_category_definitions("hearings")
                ],
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            self.assertEqual(
                [category["id"] for category in row["categories"]],
                list(sa.SUMMARY_CATEGORY_IDS["hearings"]),
            )
            # A submitted empty-list digest is unusable and fills null.
            candidate["categories"][0]["digest"] = []
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            self.assertIsNone(row["categories"][0]["digest"])

    def test_content_contract_in_fingerprint_and_label_in_item_fingerprint(self) -> None:
        # The content-contract version participates in every generation
        # fingerprint; guidance changes also change fingerprints.
        config_one = _extraction_config("hearings")
        config_two = _extraction_config(
            "hearings",
            guidance=config_one.guidance + "\n\nAdditional guidance.\n",
        )
        self.assertNotEqual(config_one.fingerprint, config_two.fingerprint)
        self.assertIn(
            sa.SUMMARY_CONTENT_CONTRACT_VERSION,
            list(config_one.fingerprint_payload().values()),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config("hearings"))
            # The shared payload helper is the single composition contract:
            # configuration plus every payload dependency (label, private
            # participant context, citation labels, proposal marker).
            payload = sa.item_fingerprint_payload(
                items[0], config_one, sa.transcript_citation_map(root)
            )
            self.assertEqual(items[0].generation_sha256, sa.sha256_json(payload))
            self.assertIn(
                "participant_context_sha256", payload
            )
            self.assertIn("citation_labels_sha256", payload)
            # Relabeling the trusted document label re-extracts the row.
            relabeled = sa.build_work_items(
                root,
                _extraction_config("hearings"),
            )
            relabeled[0].label = "March 3, 2025 - Relabeled"
            fingerprint_payload = sa.item_fingerprint_payload(
                relabeled[0], config_one, sa.transcript_citation_map(root)
            )
            self.assertNotEqual(
                items[0].generation_sha256, sa.sha256_json(fingerprint_payload)
            )


class QuoteResolutionTests(unittest.TestCase):
    def test_quote_offsets_and_page_hash_are_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            page_text = (root / "text_pages" / "0001.txt").read_text(encoding="utf-8")
            candidate = {
                "item_id": items[0].item_id,
                "categories": [
                    {
                        "id": "parent_appearances",
                        "digest": {
                            "text": "A parent appeared.",
                            "evidence": [{"text": "unique phrase", "file_page": 1}],
                        },
                    }
                ],
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            digest = row["categories"][0]["digest"]
            first = digest["evidence"][0]
            self.assertEqual(
                page_text[first["source_start"] : first["source_end"]],
                "unique phrase",
            )
            self.assertEqual(first["source_sha256"], sa.sha256_text(page_text))
            self.assertTrue(first["verified"])
            self.assertEqual(
                first["quote_id"],
                f"{items[0].item_id}/parent_appearances/1",
            )

    def test_out_of_document_evidence_is_discarded_with_flags(self) -> None:
        """Page scope discards the evidence entry, never the run."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            candidate = {
                "item_id": items[0].item_id,
                "categories": [
                    {
                        "id": "parent_appearances",
                        "digest": {
                            "text": "A parent appeared.",
                            "evidence": [
                                {"text": "Page 2 narrative", "file_page": 2},
                                {"text": "malformed"},
                                {"text": "", "file_page": 1},
                            ],
                        },
                    }
                ],
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            digest = row["categories"][0]["digest"]
            self.assertEqual(digest["evidence"], [])
            flags = " ".join(row["quality_flags"])
            self.assertIn("evidence_discarded:3", flags)
            self.assertIn("empty_evidence_kept:parent_appearances", flags)

    def test_quote_fidelity_is_best_effort_not_fatal(self) -> None:
        """Slightly-off quotes are kept with verified=false, never rejected."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())

            def candidate(quote: str) -> dict:
                return {
                    "item_id": items[0].item_id,
                    "categories": [
                        {
                            "id": "parent_appearances",
                            "digest": {
                                "text": "A parent appeared.",
                                "evidence": [
                                    {"text": quote, "file_page": 1}
                                ],
                            },
                        }
                    ],
                }

            warnings: list[str] = []

            # Exact normalized match: verified with original offsets.
            row = sa.canonicalize_extraction_candidate(
                candidate("unique phrase"), items[0], root / "text_pages",
                warnings=warnings,
            )
            evidence = row["categories"][0]["digest"]["evidence"][0]
            page_text = (root / "text_pages" / "0001.txt").read_text(encoding="utf-8")
            self.assertTrue(evidence["verified"])
            self.assertEqual(
                page_text[evidence["source_start"] : evidence["source_end"]],
                "unique phrase",
            )
            self.assertNotIn("quotes_unverified", " ".join(warnings))

            # Ambiguous matches keep the first occurrence.
            (root / "text_pages" / "0001.txt").write_text(
                "the court considered the matter and the court also "
                "QUOTEME:aa bb unique phrase here.\n",
                encoding="utf-8",
            )
            items = sa.build_work_items(root, _extraction_config())
            row = sa.canonicalize_extraction_candidate(
                candidate("the court"), items[0], root / "text_pages",
                warnings=warnings,
            )
            evidence = row["categories"][0]["digest"]["evidence"][0]
            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["source_start"], 0)

            # Typography-only differences (case, marks, dashes) verify via
            # the relaxed matcher.
            row = sa.canonicalize_extraction_candidate(
                candidate("Aa Bb"), items[0], root / "text_pages",
                warnings=warnings,
            )
            evidence = row["categories"][0]["digest"]["evidence"][0]
            self.assertTrue(evidence["verified"])

            # A quote that does not appear at all is kept as submitted,
            # flagged unverified, with a sanitized count warning — never a
            # stage failure.
            row = sa.canonicalize_extraction_candidate(
                candidate("absent words"), items[0], root / "text_pages",
                warnings=warnings,
            )
            evidence = row["categories"][0]["digest"]["evidence"][0]
            self.assertFalse(evidence["verified"])
            self.assertNotIn("source_start", evidence)
            flags = " ".join(row["quality_flags"])
            self.assertIn("quotes_unverified:1", flags)
            self.assertIn("quotes_unverified", " ".join(warnings))
            # No case text in the warning output.
            self.assertNotIn("absent", " ".join(warnings))

    def test_quote_matching_survives_ligatures_and_hyphen_wraps(self) -> None:
        page = " disposi-\ntion of the \ufb01nal order. "
        span = sa.find_quote_span("disposition of the final order", page)
        self.assertIsNotNone(span)
        start, end = span
        # The original offsets cover the hyphen-wrapped, ligatured source.
        self.assertIn("disposi", page[start:end])
        self.assertIn("nal order", page[start:end])

    def test_report_proposal_cutoff_discards_category_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 3, "rr 01")
            (root / "text_pages" / "0002.txt").write_text(
                "PROPOSED FINDINGS AND ORDERS\nQUOTEME:cc dd excluded material.\n",
                encoding="utf-8",
            )
            builder.finish([], [(1, 3, "March 3, 2025", "Detention Report")])
            items = sa.build_work_items(root, _extraction_config("reports"))
            self.assertIsNotNone(items[0].proposal_marker)
            self.assertEqual(items[0].proposal_marker.source_page, 2)

            def candidate(page: int, quote: str) -> dict:
                return {
                    "item_id": items[0].item_id,
                    "categories": [
                        {
                            "id": "agency_recommendations",
                            "digest": {
                                "text": "Agency recommendation digest.",
                                "evidence": [
                                    {"text": quote, "file_page": page}
                                ],
                            },
                        }
                    ],
                }

            row = sa.canonicalize_extraction_candidate(
                candidate(1, "unique phrase"),
                items[0],
                root / "text_pages",
                report_cutoff=(items[0].proposal_marker.source_page, 0),
            )
            self.assertEqual(
                row["categories"][0]["digest"]["evidence"][0]["file_page"], 1
            )
            # Evidence past the cutoff conservatively discards the whole
            # category digest so excluded proposal material is not published.
            row = sa.canonicalize_extraction_candidate(
                candidate(3, "unique phrase"),
                items[0],
                root / "text_pages",
                report_cutoff=(items[0].proposal_marker.source_page, 0),
            )
            self.assertIsNone(row["categories"][0]["digest"])
            self.assertIn(
                "digest_discarded_proposal_cutoff:agency_recommendations",
                row["quality_flags"],
            )


class SourcePayloadTests(unittest.TestCase):
    """Extraction serves each document's complete source pages in one payload.

    The page-intact window algorithm remains only for the direct-API paths
    (minute orders and prompt testing); PI extraction does not use it.
    """

    def test_source_payload_covers_every_page_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 4, "aa bb")
            builder.finish([(1, 4, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            payload = sa.item_source_payload(
                items[0], root / "text_pages", {page: f"RT {page}" for page in range(1, 5)}
            )
            for page in range(1, 5):
                self.assertIn(f"[RT {page} | source page {page:04d}]", payload)
                self.assertIn(f"Page {page} narrative.", payload)
            self.assertIn("COMPLETE SOURCE PAGES 0001-0004", payload)
            self.assertLess(payload.index("[RT 1 |"), payload.index("[RT 4 |"))

    def test_source_payload_carries_participant_context_and_proposal_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "rr 01")
            (root / "text_pages" / "0002.txt").write_text(
                "PROPOSED FINDINGS AND ORDERS\nQUOTEME:cc dd excluded material.\n",
                encoding="utf-8",
            )
            builder.finish([], [(1, 2, "March 3, 2025", "Detention Report")])
            items = sa.build_work_items(root, _extraction_config("reports"))
            payload = sa.item_source_payload(
                items[0], root / "text_pages", {}
            )
            self.assertIn(sa.REPORT_PROPOSAL_SCOPE_DELIMITER.strip(), payload)
            self.assertLess(
                payload.index("QUOTEME:rr 01"),
                payload.index(sa.REPORT_PROPOSAL_SCOPE_DELIMITER.strip()),
            )
            self.assertNotIn("PARTICIPANT INDEX CONTEXT", payload)

    def test_hearing_source_payload_includes_participant_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            payload = sa.item_source_payload(items[0], root / "text_pages", {})
            self.assertIn("PARTICIPANT INDEX CONTEXT", payload)
            self.assertIn("Counsel:", payload)
            self.assertIn("Participants:", payload)
            self.assertIn("Testimony:", payload)

    def test_work_spec_carries_digest_contract_and_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            spec = sa.build_work_spec(items[0], _extraction_config(), root, Path("c.json"))
            self.assertNotIn("windows", spec)
            self.assertIn("source", spec)
            self.assertEqual(spec["schema_version"], 3)
            self.assertNotIn("length_guidance", spec)
            self.assertIn("Relevance", spec["guidance"])
            # No generated word/paragraph budgets in any spec section.
            self.assertNotIn("target", spec["source"].lower())
            self.assertNotIn("words", spec["source"].lower())


class MarkdownStoreTests(unittest.TestCase):
    def _bundle(self, root: Path) -> list[sa.SummaryWorkItem]:
        builder = BundleBuilder(root)
        builder.add_pages(1, 1, "aa bb")
        builder.add_pages(2, 2, "cc dd")
        builder.finish(
            [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")], []
        )
        return sa.build_work_items(root, _extraction_config())

    def test_publication_replace_and_metadata_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256=items[0].generation_sha256,
                )
            ]
            sa.publish_digests(root, "hearings", items, _extraction_config(), rows)
            meta = sa.load_digest_meta(root, "hearings")
            self.assertEqual(meta["complete"], False)
            self.assertEqual(meta["total"], 2)
            self.assertEqual(meta["completed"], 1)
            self.assertEqual(meta["schema_version"], sa.SUMMARY_FACTS_META_SCHEMA_VERSION)
            self.assertTrue(sa.summary_digest_path(root, "hearings").is_file())
            self.assertFalse(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").exists()
            )

            rows.append(
                synthetic_facts_row(
                    "hearings",
                    start=2,
                    end=2,
                    ordinal=2,
                    generation_sha256=items[1].generation_sha256,
                )
            )
            rows, _stale = sa.reconcile_digest_rows(rows, items)
            sa.publish_digests(root, "hearings", items, _extraction_config(), rows)
            meta = sa.load_digest_meta(root, "hearings")
            self.assertEqual(meta["complete"], True)
            self.assertEqual(meta["schema_version"], sa.SUMMARY_FACTS_META_SCHEMA_VERSION)

            # Simulated crash between Markdown and metadata writes self-heals.
            meta_path = sa.summary_digest_meta_path(root, "hearings")
            meta_path.unlink()
            ordered, pending = sa.validate_digest_state(
                root, "hearings", items, _extraction_config()
            )
            self.assertEqual(pending, [])
            sa.publish_digests(root, "hearings", items, _extraction_config(), ordered)
            self.assertEqual(sa.load_digest_meta(root, "hearings")["complete"], True)

    def test_guidance_change_makes_rows_stale_but_targets_do_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256=items[0].generation_sha256,
                )
            ]
            ordered, stale = sa.reconcile_digest_rows(rows, items)
            self.assertEqual(stale, [])
            # A guidance change invalidates the generation fingerprint.
            reguided = sa.build_work_items(
                root,
                _extraction_config(
                    "hearings",
                    guidance=_extraction_config("hearings").guidance
                    + "\n\nMore guidance.\n",
                ),
            )
            _ordered, stale = sa.reconcile_digest_rows(rows, reguided)
            self.assertEqual(stale, ["hearing:0001"])

    def test_stale_fingerprint_and_removed_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            rows = [
                synthetic_facts_row("hearings", start=1, end=1, generation_sha256="stale"),
                synthetic_facts_row(
                    "hearings",
                    start=2,
                    end=2,
                    ordinal=2,
                    generation_sha256=items[1].generation_sha256,
                ),
            ]
            ordered, stale = sa.reconcile_digest_rows(rows, items)
            self.assertEqual(stale, ["hearing:0001"])
            # Removing the second boundary prunes its row.
            trimmed = sa.build_work_items(
                root, _extraction_config()
            )[:1]
            ordered, _stale = sa.reconcile_digest_rows(rows, trimmed)
            self.assertEqual(
                [row["item_id"] for row in ordered], ["hearing:0001"]
            )

    def test_legacy_facts_artifacts_are_ignored_then_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            summaries = root / "summaries"
            summaries.mkdir()
            legacy = sa.legacy_summary_facts_path(root, "hearings")
            legacy_meta = sa.legacy_summary_facts_meta_path(root, "hearings")
            legacy.write_text('{"artifact": "recordprep-summary-facts"}\n', encoding="utf-8")
            legacy_meta.write_text("{}", encoding="utf-8")
            # Legacy artifacts never block or feed digest validation.
            ordered, pending = sa.validate_digest_state(
                root, "hearings", items, _extraction_config()
            )
            self.assertEqual(ordered, [])
            self.assertEqual(pending, [item.item_id for item in items])
            # Cleanup removes exactly the known legacy paths.
            removed = sa.cleanup_legacy_facts_artifacts(root, "hearings")
            self.assertEqual(len(removed), 2)
            self.assertFalse(legacy.exists())
            self.assertFalse(legacy_meta.exists())
            self.assertEqual(sa.cleanup_legacy_facts_artifacts(root, "hearings"), [])

    def test_malformed_markdown_is_reported_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._bundle(root)
            path = sa.summary_digest_path(root, "hearings")
            path.parent.mkdir(parents=True, exist_ok=True)
            malformed = "# RecordPrep hearings digests — SynCase\ntruncated\n"
            path.write_text(malformed, encoding="utf-8")
            with self.assertRaises(ValueError) as context:
                sa.load_digest_markdown(root, "hearings")
            self.assertIn("preserved untouched", str(context.exception))
            self.assertEqual(path.read_text(encoding="utf-8"), malformed)

    def test_truncated_markdown_never_falls_back_to_legacy(self) -> None:
        """A corrupt Markdown file is authoritative: no silent JSONL fallback."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256="g" * 64,
                )
            ]
            write_facts_bundle(root, "hearings", rows)
            text = sa.summary_digest_path(root, "hearings").read_text(
                encoding="utf-8"
            )
            sa.summary_digest_path(root, "hearings").write_text(
                text[: len(text) // 2], encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                sa.validate_digest_state(
                    root, "hearings", items, _extraction_config()
                )

    def test_markdown_structure_rejects_duplicates_bad_versions_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._bundle(root)
            rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256="g" * 64,
                )
            ]
            text = sa.serialize_digest_markdown("hearings", "SynCase", rows)

            # Duplicate document id: the appended heading reuses hearing:0001.
            duplicated = text + "\n## March 3, 2025 — Hearing (hearing:0001)\n"
            with self.assertRaises(ValueError) as context:
                sa.parse_digest_markdown(duplicated, "hearings", "SynCase")
            self.assertIn("duplicate", str(context.exception))

            # Unsupported Markdown format version in the document comment.
            with self.assertRaises(ValueError) as context:
                sa.parse_digest_markdown(
                    text.replace(
                        '"format_version": 1',
                        '"format_version": 99',
                    ),
                    "hearings",
                    "SynCase",
                )
            self.assertIn("format version", str(context.exception))

            # Visible heading and technical metadata disagree.
            with self.assertRaises(ValueError) as context:
                sa.parse_digest_markdown(
                    text.replace(
                        "Source pages: 1-1",
                        "Source pages: 1-3",
                    ),
                    "hearings",
                    "SynCase",
                )
            self.assertIn("disagrees", str(context.exception))

            # Case-stem mismatch is rejected (cross-case contamination guard).
            with self.assertRaises(ValueError):
                sa.parse_digest_markdown(text, "hearings", "OtherCase")

    def test_per_kind_lock_rejects_concurrent_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sa.SummaryKindLock(root, "hearings"):
                with self.assertRaises(ValueError):
                    with sa.SummaryKindLock(root, "hearings"):
                        pass
            # Released cleanly for the next run.
            with sa.SummaryKindLock(root, "hearings"):
                pass


class MarkdownCodecRoundTripTests(unittest.TestCase):
    """The codec preserves every row field, exact quote text, and structure."""

    NASTY_TEXT = (
        "Tricky: # heading\n"
        "<!-- comment --> with </script> and &amp; entity\n"
        "```\nfence\n```\n"
        "[link](page:0002) ![img](x.png) and - dash\n"
        "1. ordered 2) alt -minus +plus *star* _under_ = eq | pipe > gt \\ back\\"
        "Tab\tchar and “curly” quotes — em-dash …"
    )

    def _row(self, kind: str) -> dict:
        row = synthetic_facts_row(kind, start=7, end=9, ordinal=3)
        category_id = (
            "agency_recommendations" if kind == "reports" else "parent_appearances"
        )
        row["label"] = (
            "March 3, 2025 - odd (label) #heading *stars* — em\nsecond line"
            if kind == "hearings"
            else "Report #1 - (od d) \\slash\nmulti"
        )
        row["categories"][0]["digest"] = {
            "text": self.NASTY_TEXT,
            "evidence": [
                {
                    "quote_id": f"{row['item_id']}/{category_id}/1",
                    "text": "Line one\nLine two with <b>html</b>, `ticks`, and \\back\\",
                    "file_page": 7,
                    "source_sha256": "a" * 64,
                    "source_start": 0,
                    "source_end": 5,
                    "verified": True,
                },
                {
                    "quote_id": f"{row['item_id']}/{category_id}/2",
                    "text": "No material content.",
                    "file_page": 8,
                    "source_sha256": "b" * 64,
                    "verified": False,
                },
            ],
        }
        row["categories"][1]["digest"] = {
            "text": "No direct quotes.",
            "evidence": [],
        }
        row["categories"][2]["digest"] = None
        row["quality_flags"] = ["empty_evidence_kept:testimony"]
        return row

    def test_round_trip_preserves_rows_exactly(self) -> None:
        for kind in ("hearings", "reports"):
            with self.subTest(kind=kind):
                row = self._row(kind)
                text = sa.serialize_digest_markdown(kind, "SynCase", [row])
                parsed = sa.parse_digest_markdown(text, kind, "SynCase")
                self.assertEqual(len(parsed), 1)
                self.assertEqual(parsed[0], row)
                self.assertEqual(
                    sa.serialize_digest_markdown(kind, "SynCase", parsed), text
                )

    def test_marker_colliding_digests_stay_prose(self) -> None:
        row = self._row("hearings")
        row["categories"][3]["digest"] = {
            "text": "No material content.",
            "evidence": [],
        }
        text = sa.serialize_digest_markdown("hearings", "SynCase", [row])
        parsed = sa.parse_digest_markdown(text, "hearings", "SynCase")
        self.assertEqual(parsed[0], row)
        # The null category after it still parses as null.
        self.assertIsNone(parsed[0]["categories"][4]["digest"])

    def test_zero_rows_produce_valid_header_only_document(self) -> None:
        text = sa.serialize_digest_markdown("reports", "SynCase", [])
        self.assertTrue(text.startswith("# RecordPrep reports digests — SynCase\n"))
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(sa.parse_digest_markdown(text, "reports", "SynCase"), [])

    def test_document_block_omits_comments_but_keeps_visible_content(self) -> None:
        row = self._row("hearings")
        block = sa.document_markdown_block(row)
        self.assertNotIn("<!--", block)
        self.assertIn("(hearing:0007)", block)
        self.assertIn("### Testimony (testimony)", block)
        self.assertIn(sa.DIGEST_NULL_MARKER, block)
        self.assertIn("#### Direct quotes", block)
        self.assertIn("Quote: `hearing:0007/parent_appearances/1` — File page 7 — Verified", block)
        self.assertIn("— Unverified", block)
        self.assertIn("> Line one", block)


class LegacyDigestMigrationTests(unittest.TestCase):
    """Valid v2 JSONL converts losslessly; inconsistent pairs stay preserved."""

    def _bundle(self, root: Path) -> list[sa.SummaryWorkItem]:
        builder = BundleBuilder(root)
        builder.add_pages(1, 1, "aa bb")
        builder.add_pages(2, 2, "cc dd")
        builder.finish(
            [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")], []
        )
        return sa.build_work_items(root, _extraction_config())

    def test_migration_preserves_rows_with_zero_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            legacy_rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256=items[0].generation_sha256,
                ),
                synthetic_facts_row(
                    "hearings",
                    start=2,
                    end=2,
                    ordinal=2,
                    generation_sha256="stale" * 16,
                ),
            ]
            write_legacy_digest_jsonl(root, "hearings", legacy_rows)

            migrated = sa.migrate_legacy_digest_jsonl(root, "hearings")
            self.assertIsNotNone(migrated)
            self.assertEqual(migrated, legacy_rows)
            # The runner publishes through the normal Markdown path.
            sa.publish_digests(root, "hearings", items, _extraction_config(), migrated)
            # Reconciled against current items: only the stale row re-extracts.
            ordered, pending = sa.validate_digest_state(
                root, "hearings", items, _extraction_config()
            )
            self.assertEqual(pending, ["hearing:0002"])
            self.assertEqual(ordered, legacy_rows)
            # Migrated rows are byte-identical through the Markdown store.
            self.assertEqual(
                sa.load_digest_markdown(root, "hearings"), legacy_rows
            )
            # A rerun never re-migrates: Markdown is authoritative.
            self.assertIsNone(sa.migrate_legacy_digest_jsonl(root, "hearings"))

            # Success cleanup removes only the obsolete JSONL.
            removed = sa.cleanup_legacy_digest_jsonl(root, "hearings")
            self.assertEqual(removed, ["hearings_digests_SynCase.jsonl"])
            self.assertFalse(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").exists()
            )
            self.assertTrue(sa.summary_digest_meta_path(root, "hearings").exists())

    def test_inconsistent_legacy_pair_is_preserved_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._bundle(root)
            rows = [
                synthetic_facts_row("hearings", start=1, end=1, generation_sha256="g" * 64)
            ]
            write_legacy_digest_jsonl(
                root, "hearings", rows, jsonl_sha256="0" * 64
            )
            with self.assertRaises(ValueError) as context:
                sa.migrate_legacy_digest_jsonl(root, "hearings")
            self.assertIn("disagree", str(context.exception))
            # Both files preserved for deliberate recovery.
            self.assertTrue(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").exists()
            )
            self.assertFalse(sa.summary_digest_path(root, "hearings").exists())

    def test_malformed_legacy_jsonl_is_preserved_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._bundle(root)
            path = sa.legacy_summary_digest_jsonl_path(root, "hearings")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"artifact": "recordprep-summary-digest"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                sa.migrate_legacy_digest_jsonl(root, "hearings")
            self.assertFalse(sa.summary_digest_path(root, "hearings").exists())

    def test_final_text_is_byte_identical_across_migration(self) -> None:
        """Same rows + same synthetic candidate render identical final text."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            items = self._bundle(root)
            rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256=items[0].generation_sha256,
                    facts={
                        "parent_appearances": [
                            {
                                "text": "Mother appeared remotely.",
                                "evidence": [
                                    {"text": "unique phrase", "file_page": 1}
                                ],
                            }
                        ]
                    },
                )
            ]
            write_legacy_digest_jsonl(root, "hearings", rows)
            migrated = sa.migrate_legacy_digest_jsonl(root, "hearings")
            sa.publish_digests(root, "hearings", items, _extraction_config(), migrated)
            stored = sa.load_digest_markdown(root, "hearings")
            quote_id = rows[0]["categories"][0]["digest"]["evidence"][0]["quote_id"]
            sections = [
                sa.SynthesisSectionCandidate(
                    item_id=rows[0]["item_id"],
                    paragraphs=[f"Mother appeared with {{{{quote:{quote_id}}}}}."],
                )
            ]
            heading_pages = {rows[0]["item_id"]: (1, None)}
            migrated_text = sa.render_final_summary(
                "hearings", "Syn Case", stored, sections, heading_pages
            )
            # The same render over the original in-memory rows is identical.
            self.assertEqual(
                migrated_text,
                sa.render_final_summary(
                    "hearings", "Syn Case", rows, sections, heading_pages
                ),
            )
            self.assertIn("\u201cunique phrase\u201d", migrated_text)
            self.assertNotIn(
                sa.NO_SUMMARIZABLE_REPORT_CONTENT, migrated_text
            )


class SynthesisNormalizationTests(unittest.TestCase):
    def _report_rows(self) -> list[dict]:
        facts_one = {
            "agency_recommendations": [
                {
                    "text": "Reunification services recommended for the parent.",
                    "evidence": [{"text": "aa bb", "file_page": 1}],
                }
            ]
        }
        facts_two = {
            "agency_recommendations": [
                {
                    "text": "Reunification services recommended for the parent.",
                    "evidence": [{"text": "ee ff", "file_page": 2}],
                }
            ],
            "services_progress": [
                {
                    "text": "The parent completed a parenting class.",
                    "evidence": [{"text": "gg hh", "file_page": 2}],
                }
            ],
        }
        row_one = synthetic_facts_row(
            "reports",
            ordinal=1,
            label="March 1, 2025 - Report One",
            start=1,
            end=1,
            facts=facts_one,
        )
        row_two = synthetic_facts_row(
            "reports",
            ordinal=2,
            label="April 1, 2025 - Report Two",
            start=2,
            end=2,
            facts=facts_two,
        )
        return [row_one, row_two]

    def test_sections_reorder_and_fill_in_order(self) -> None:
        rows = self._report_rows()
        quote_two = (
            rows[1]["categories"][0]["digest"]["evidence"][0]["quote_id"]
        )
        payload = [
            {
                "item_id": rows[1]["item_id"],
                "paragraphs": [f"Second section with {{{{quote:{quote_two}}}}}."],
            },
            {"item_id": "report:9999", "paragraphs": ["Unknown section."]},
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        self.assertEqual(
            [section.item_id for section in sections],
            [row["item_id"] for row in rows],
        )
        # Missing first section falls back to deterministic digest prose.
        self.assertIn("fallback_section:report:0001", flags)
        self.assertTrue(sections[0].paragraphs)
        self.assertIn("Reunification services", sections[0].paragraphs[0])
        # Unknown sections are dropped with a flag.
        self.assertTrue(any("unknown_section_ignored" in flag for flag in flags))

    def test_empty_section_falls_back_and_all_null_stays_empty(self) -> None:
        rows = self._report_rows()
        all_null = synthetic_facts_row("reports", ordinal=3, start=3, end=3)
        rows.append(all_null)
        payload = [
            {"item_id": rows[0]["item_id"], "paragraphs": ["", "  "]},
            {"item_id": all_null["item_id"], "paragraphs": ["Should be dropped."]},
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        self.assertTrue(sections[0].paragraphs)
        self.assertIn("empty_section_fallback:report:0001", flags)
        self.assertEqual(sections[2].paragraphs, [])
        self.assertIn("paragraphs_for_all_null_document:report:0003", flags)

    def test_known_placeholders_survive_and_page_links_flatten(self) -> None:
        rows = self._report_rows()
        known = rows[0]["categories"][0]["digest"]["evidence"][0]["quote_id"]
        payload = [
            {
                "item_id": rows[0]["item_id"],
                "paragraphs": [
                    f"Known {{{{quote:{known}}}}} plus [label](page:0007) markup.",
                ],
            },
            {"item_id": rows[1]["item_id"], "paragraphs": ["Second."]},
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        first = sections[0].paragraphs[0]
        self.assertIn("{{quote:%s}}" % known, first)
        self.assertIn("label", first)
        self.assertNotIn("](page:", first)
        self.assertFalse(any("unknown_placeholder" in flag for flag in flags))

    def test_unknown_placeholders_fallback_to_whole_section(self) -> None:
        rows = self._report_rows()
        known = rows[0]["categories"][0]["digest"]["evidence"][0]["quote_id"]
        payload = [
            {
                "item_id": rows[0]["item_id"],
                "paragraphs": [
                    f"Known {{{{quote:{known}}}}} and unknown {{{{quote:nope}}}} "
                    "plus [label](page:0007) markup.",
                ],
            },
            {"item_id": rows[1]["item_id"], "paragraphs": ["Second."]},
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        joined = " ".join(flags)
        # The affected section is replaced wholesale by deterministic digest
        # prose — quoted wording is never silently deleted from a sentence.
        self.assertIn("unknown_placeholder:report:0001:1", joined)
        self.assertIn("unknown_placeholder_fallback:report:0001", joined)
        first = " ".join(sections[0].paragraphs)
        self.assertIn("Reunification services", first)
        self.assertNotIn("{{quote:nope}}", first)
        # Unaffected sections pass through unchanged.
        self.assertEqual(sections[1].paragraphs, ["Second."])

    def test_unknown_placeholders_on_all_null_document_stay_empty(self) -> None:
        rows = self._report_rows()
        all_null = synthetic_facts_row("reports", ordinal=3, start=3, end=3)
        rows.append(all_null)
        payload = [
            {
                "item_id": all_null["item_id"],
                "paragraphs": ["Narrative with {{{{quote:nope}}}} inside."],
            },
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        self.assertEqual(sections[2].paragraphs, [])
        joined = " ".join(flags)
        self.assertIn("unknown_placeholder:report:0003:1", joined)
        self.assertIn("unknown_placeholder_fallback:report:0003", joined)

    def test_quality_problems_become_warning_codes(self) -> None:
        rows = self._report_rows()
        known = rows[0]["categories"][0]["digest"]["evidence"][0]["quote_id"]
        payload = [
            {
                "item_id": rows[0]["item_id"],
                "paragraphs": [
                    f'He said "hello there" twice: {{{{quote:{known}}}}} and '
                    f"{{{{quote:{known}}}}}."
                ],
            },
            {"item_id": rows[1]["item_id"], "paragraphs": ["Second."]},
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        joined = " ".join(flags)
        self.assertIn("typed_quotation_marks:report:0001", joined)
        self.assertIn("duplicate_quote_use:", joined)
        # No word-count or coverage diagnostics exist for any section.
        self.assertFalse(any("target_overrun" in flag for flag in flags))
        self.assertFalse(any("low_category_coverage" in flag for flag in flags))

    def test_quote_convention_diagnostics_are_sanitized_warnings(self) -> None:
        facts = {
            "agency_recommendations": [
                {
                    "text": "Reunification services recommended for the parent.",
                    "evidence": [
                        {"text": "aa", "file_page": 1},
                        {"text": "aa bb cc dd ee ff", "file_page": 1},
                        {"text": "aa bb...", "file_page": 1},
                        {"text": "aa bb.", "file_page": 1},
                        {"text": "aa bb", "file_page": 1},
                    ],
                }
            ]
        }
        row = synthetic_facts_row(
            "reports", ordinal=1, label="March 1, 2025", start=1, end=1, facts=facts
        )
        quote_ids = [
            evidence["quote_id"]
            for evidence in row["categories"][0]["digest"]["evidence"]
        ]
        one_word, six_word, ellipsis, terminal, compliant = quote_ids
        payload = [
            {
                "item_id": row["item_id"],
                "paragraphs": [
                    " ".join(f"{{{{quote:{qid}}}}}" for qid in quote_ids)
                ],
            }
        ]
        sections, flags = sa.normalize_synthesis_sections([row], payload)
        joined = " ".join(flags)
        self.assertIn(f"quote_length_out_of_range:{row['item_id']}:{one_word}:1", joined)
        self.assertIn(f"quote_length_out_of_range:{row['item_id']}:{six_word}:6", joined)
        self.assertIn(f"quote_ellipsis:{row['item_id']}:{ellipsis}", joined)
        self.assertIn(
            f"quote_terminal_punctuation:{row['item_id']}:{terminal}", joined
        )
        self.assertNotIn(
            f"quote_length_out_of_range:{row['item_id']}:{compliant}", joined
        )
        # Apostrophes and hyphenated compounds count as one word.
        self.assertEqual(len(sa._normalized_words("mother's in-home visit")), 3)
        # Diagnostics never shorten or drop useful paragraphs.
        self.assertEqual(len(sections[0].paragraphs), 1)

    def test_repeated_report_passages_are_warning_diagnostics(self) -> None:
        rows = self._report_rows()
        # Make row two reference row one's exact evidence text (diagnostic).
        repeated = json.loads(json.dumps(rows[1]))
        repeated["categories"][0]["digest"]["evidence"][0]["text"] = "aa bb"
        rows = [rows[0], repeated]
        repeated_story = (
            "The agency continued to recommend family reunification services "
            "and the parent continued to attend structured visitation each "
            "week without incident or concern noted by anyone."
        )
        payload = [
            {
                "item_id": rows[0]["item_id"],
                "paragraphs": [repeated_story],
            },
            {
                "item_id": rows[1]["item_id"],
                "paragraphs": [repeated_story],
            },
        ]
        sections, flags = sa.normalize_synthesis_sections(rows, payload)
        self.assertTrue(any("repeated_passage:report:0002" in flag for flag in flags))

    def test_all_fallback_when_candidate_is_unusable(self) -> None:
        rows = self._report_rows()
        sections, flags = sa.normalize_synthesis_sections(rows, "not-a-list")
        self.assertEqual(len(sections), 2)
        for section in sections:
            self.assertTrue(section.paragraphs)
        self.assertTrue(any("candidate_unusable" in flag for flag in flags))

    def test_recurrence_helpers_are_diagnostics_only(self) -> None:
        rows = self._report_rows()
        recurrence = sa.build_recurrence_index(rows)
        self.assertIn("digest_texts", recurrence)
        self.assertIn("quote_texts", recurrence)
        self.assertTrue(
            sa.facts_carry_forward(
                rows[1], "agency_recommendations", recurrence
            )
        )


class RenderingTests(unittest.TestCase):
    def test_plain_headings_and_curly_quotes_without_page_links(self) -> None:
        rows = [synthetic_facts_row("hearings", start=7, end=8)]
        quote_id = "hearing:0007/parent_appearances/1"
        row = rows[0]
        row["categories"][0]["digest"] = {
            "text": "Mother appeared.",
            "evidence": [
                {
                    "quote_id": quote_id,
                    "text": "unique phrase",
                    "file_page": 7,
                    "source_start": 0,
                    "source_end": 1,
                    "source_sha256": "x" * 64,
                    "verified": True,
                }
            ],
        }
        sections = [
            sa.SynthesisSectionCandidate(
                item_id=row["item_id"],
                paragraphs=["Mother appeared with {{quote:%s}}." % quote_id],
            )
        ]
        text = sa.render_final_summary(
            "hearings",
            "Syn Case",
            rows,
            sections,
            {row["item_id"]: (7, 9)},
        )
        self.assertTrue(text.startswith("Hearings Summary\nSyn Case\n"))
        self.assertIn("March 3, 2025 \u2014 Hearing", text)
        self.assertIn("\u201cunique phrase\u201d", text)
        self.assertNotIn("{{quote:", text)
        self.assertNotIn("](page:", text)
        self.assertNotIn("[Hearing]", text)
        self.assertNotIn("[Minute Order]", text)

        report_rows = [
            synthetic_facts_row(
                "reports",
                start=12,
                end=12,
                label="March 1, 2025 - Status Review Report",
            )
        ]
        report_text = sa.render_final_summary(
            "reports",
            "Syn Case",
            report_rows,
            [
                sa.SynthesisSectionCandidate(
                    item_id=report_rows[0]["item_id"],
                    paragraphs=[],
                )
            ],
            {report_rows[0]["item_id"]: (12, None)},
        )
        self.assertIn("March 1, 2025 - Status Review Report", report_text)
        self.assertNotIn("[Report]", report_text)
        # All-null documents keep the required heading without a sentinel
        # paragraph or any technical narrative.
        self.assertEqual(
            report_text.strip(),
            "Reports Summary\nSyn Case\n\nMarch 1, 2025 - Status Review Report",
        )
        self.assertNotIn(sa.NO_SUMMARIZABLE_REPORT_CONTENT, report_text)

    def test_all_null_documents_render_heading_only(self) -> None:
        all_null = synthetic_facts_row("hearings", start=3, end=3)
        text = sa.render_final_summary(
            "hearings",
            "Syn Case",
            [all_null],
            [sa.SynthesisSectionCandidate(item_id=all_null["item_id"], paragraphs=[])],
            {all_null["item_id"]: (3, None)},
        )
        self.assertEqual(
            text.strip(),
            "Hearings Summary\nSyn Case\n\nMarch 3, 2025 \u2014 Hearing",
        )
        self.assertEqual(sa.rendered_narrative_flags(text), [])

    def test_final_meta_enforces_renderer_version_and_quality_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = [synthetic_facts_row("hearings", start=1, end=1)]
            final_text = "Hearings Summary\n\nMarch 3, 2025 \u2014 Hearing\n"
            flags = ["typed_quotation_marks:hearing:0001"]
            meta = sa.build_final_meta(
                root,
                "hearings",
                rows,
                final_text,
                {},
                {"hearing:0001": (1, None)},
                quality_flags=flags,
            )
            self.assertEqual(meta["renderer_version"], sa.SUMMARY_RENDERER_VERSION)
            self.assertEqual(meta["quality_flags"], flags)
            sa._atomic_write(sa.summary_final_path(root, "hearings"), final_text)
            sa._atomic_write(
                sa.summary_final_meta_path(root, "hearings"),
                json.dumps(meta) + "\n",
            )
            self.assertEqual(sa.validate_final_meta(root, "hearings", final_text), [])
            # A retired renderer version makes the output regeneration-pending.
            stale = dict(meta)
            stale["renderer_version"] = "recordprep-summary-renderer-2"
            sa._atomic_write(
                sa.summary_final_meta_path(root, "hearings"),
                json.dumps(stale) + "\n",
            )
            issues = sa.validate_final_meta(root, "hearings", final_text)
            self.assertTrue(any("retired renderer" in issue for issue in issues))
            # Omitting the optional quality_flags field stays valid.
            valid_without_flags = dict(meta)
            del valid_without_flags["quality_flags"]
            sa._atomic_write(
                sa.summary_final_meta_path(root, "hearings"),
                json.dumps(valid_without_flags) + "\n",
            )
            self.assertEqual(sa.validate_final_meta(root, "hearings", final_text), [])
            # A missing renderer version also counts as regeneration-pending.
            missing_version = dict(valid_without_flags)
            del missing_version["renderer_version"]
            sa._atomic_write(
                sa.summary_final_meta_path(root, "hearings"),
                json.dumps(missing_version) + "\n",
            )
            issues = sa.validate_final_meta(root, "hearings", final_text)
            self.assertTrue(any("retired renderer" in issue for issue in issues))

    def test_rendered_narrative_flags_detect_technical_metadata(self) -> None:
        clean = "Hearings Summary\n\nMarch 3, 2025 \u2014 Hearing\n\nMother appeared."
        self.assertEqual(sa.rendered_narrative_flags(clean), [])
        dirty = (
            "Text with {{quote:hearing:0001/testimony/1}} placeholder, "
            "a [label](page:0007) link, and a recordprep:digest-row comment."
        )
        flags = sa.rendered_narrative_flags(dirty)
        self.assertIn("technical_metadata_in_narrative:placeholder", flags)
        self.assertIn("technical_metadata_in_narrative:page_link", flags)
        self.assertIn("technical_metadata_in_narrative:digest_marker", flags)

    def test_doubled_model_quotes_around_placeholders_render_once(self) -> None:
        """Model-typed straight quotes hugging a placeholder are dropped so the
        resolved quotation is published once, in ordinary curly quotes."""
        rows = [synthetic_facts_row("hearings", start=7, end=8)]
        quote_id = "hearing:0007/parent_appearances/1"
        row = rows[0]
        row["categories"][0]["digest"] = {
            "text": "Mother appeared.",
            "evidence": [
                {
                    "quote_id": quote_id,
                    "text": "unique phrase",
                    "file_page": 7,
                    "source_start": 0,
                    "source_end": 1,
                    "source_sha256": "x" * 64,
                    "verified": True,
                }
            ],
        }
        rendered = sa.render_section_paragraphs(
            row,
            [f'The court said "{{{{quote:{quote_id}}}}}" and moved on.'],
        )
        self.assertEqual(
            rendered,
            ["The court said \u201cunique phrase\u201d and moved on."],
        )
        # Typed marks elsewhere in the paragraph are left untouched.
        rendered_plain = sa.render_section_paragraphs(
            row,
            ['She said "good cause" plainly.'],
        )
        self.assertEqual(rendered_plain, ['She said "good cause" plainly.'])

    def test_final_summary_builds_and_validates_as_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "aa bb")
            builder.finish([(1, 2, "March 3, 2025")], [])
            row = synthetic_facts_row("hearings", start=1, end=2)
            quote_id = "hearing:0001/parent_appearances/1"
            row["categories"][0]["digest"] = {
                "text": "First synthesized account.",
                "evidence": [
                    {
                        "quote_id": quote_id,
                        "text": "unique phrase",
                        "file_page": 1,
                        "source_start": 0,
                        "source_end": 1,
                        "source_sha256": "x" * 64,
                        "verified": True,
                    }
                ],
            }
            row["categories"][1]["digest"] = {
                "text": "Second synthesized account.",
                "evidence": [
                    {
                        "quote_id": "hearing:0001/evidence_considered/1",
                        "text": "Page 1 narrative",
                        "file_page": 1,
                        "source_start": 0,
                        "source_end": 1,
                        "source_sha256": "x" * 64,
                        "verified": True,
                    }
                ],
            }
            final_text = (
                "Hearings Summary\nSyn Case\n\n"
                "March 3, 2025 \u2014 Hearing\n\n"
                "First account with \u201cunique phrase\u201d. Second account "
                "with \u201cPage 1 narrative\u201d.\n"
            )
            (root / "summaries").mkdir(exist_ok=True)
            final_path = sa.summary_final_path(root, "hearings")
            final_path.write_text(final_text, encoding="utf-8")
            edition = build_summary_edition("hearings", final_path, root)
            publish_summary_edition(edition, final_path)
            self.assertEqual(
                validate_summary_edition_files("hearings", final_path, root),
                [],
            )


class SettingsTests(unittest.TestCase):
    def test_effective_guidance_resolution_migrates_builtins_and_preserves_custom(
        self,
    ) -> None:
        # Every exact historical built-in — the full tracked-history chain —
        # advances to the current immutable contract for its phase.
        for (kind, phase), historical in sa.HISTORICAL_BUILTIN_GUIDANCE.items():
            self.assertTrue(historical, (kind, phase))
            for text in historical:
                resolution = sa.resolve_phase_guidance(kind, phase, text)
                self.assertEqual(resolution.origin, "migrated", (kind, phase))
                self.assertEqual(
                    resolution.immutable_guidance,
                    sa.default_guidance(kind, phase),
                )
                self.assertEqual(resolution.custom_guidance, "")

        # The current defaults resolve directly.
        for kind in ("hearings", "reports"):
            for phase in ("extract", "synthesize"):
                default = sa.default_guidance(kind, phase)
                resolution = sa.resolve_phase_guidance(kind, phase, default)
                self.assertEqual(resolution.origin, "default")
                self.assertEqual(resolution.custom_guidance, "")
                empty = sa.resolve_phase_guidance(kind, phase, "")
                self.assertEqual(empty.origin, "default")

        # A whitespace variant of an exact historical built-in still migrates.
        historical_hearing = sa.HISTORICAL_BUILTIN_GUIDANCE[
            ("hearings", "extract")
        ][0]
        resolution = sa.resolve_phase_guidance(
            "hearings", "extract", f"  {historical_hearing}\n"
        )
        self.assertEqual(resolution.origin, "migrated")

        # A customized prompt that opens like a retired built-in but differs
        # is custom: its byte-for-byte text becomes subordinate additional
        # guidance, including obsolete length instructions.
        similar_custom = sa.PRIOR_HEARING_EXTRACTION_GUIDANCE.replace(
            "never impose word, sentence, or paragraph counts",
            "keep digests near 200 words",
        )
        if similar_custom == sa.PRIOR_HEARING_EXTRACTION_GUIDANCE:
            similar_custom = sa.PRIOR_HEARING_EXTRACTION_GUIDANCE + "\nCustom note."
        resolution = sa.resolve_phase_guidance(
            "hearings", "extract", similar_custom
        )
        self.assertEqual(resolution.origin, "custom")
        self.assertEqual(resolution.custom_guidance, similar_custom)
        self.assertEqual(
            resolution.immutable_guidance,
            sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE,
        )

        # Custom text is preserved byte-for-byte, including whitespace, and
        # the stored representation is never rewritten.
        custom_with_whitespace = "  A genuinely custom extraction prompt.\n"
        resolution = sa.resolve_phase_guidance(
            "hearings", "extract", custom_with_whitespace
        )
        self.assertEqual(resolution.origin, "custom")
        self.assertEqual(resolution.custom_guidance, custom_with_whitespace)
        custom_synthesis = "A genuinely custom synthesis prompt."
        resolution = sa.resolve_phase_guidance(
            "hearings", "synthesize", custom_synthesis
        )
        self.assertEqual(resolution.origin, "custom")
        self.assertEqual(resolution.custom_guidance, custom_synthesis)

    def test_moved_direct_api_prompt_constants_match_summary_agents(self) -> None:
        """The GTK aliases and the migration registry share one source text."""
        from recordprep.ui import main_window

        self.assertEqual(
            main_window.DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
            sa.DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        )
        self.assertEqual(
            main_window.PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
            sa.PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        )
        self.assertEqual(
            main_window.DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertEqual(
            main_window.PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            sa.PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertEqual(
            main_window.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
            sa.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertEqual(
            main_window.PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
            sa.PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
        )
        # The sandbox-era defaults are registered as historical built-ins so
        # installations that stored them advance to the current contract.
        self.assertIn(
            sa.DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
            sa.HISTORICAL_BUILTIN_GUIDANCE[("hearings", "extract")],
        )
        self.assertIn(
            sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            sa.HISTORICAL_BUILTIN_GUIDANCE[("reports", "extract")],
        )

    def test_settings_buffers_edit_custom_guidance_byte_for_byte(self) -> None:
        """Settings exposes only custom additional guidance and stores it raw."""
        from recordprep.ui.main_window import (
            load_summarize_settings,
            save_summarize_settings,
        )

        # A stored historical built-in surfaces no custom guidance.
        with mock.patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_hearings_prompt": sa.PRIOR_HEARING_EXTRACTION_GUIDANCE,
                "summarize_reports_prompt": "",
                "summarize_hearings_synthesis_prompt": "",
                "summarize_reports_synthesis_prompt": "",
            },
        ):
            settings = load_summarize_settings()
        self.assertEqual(settings["hearings_prompt"], "")
        self.assertEqual(settings["reports_prompt"], "")
        self.assertEqual(settings["hearings_synthesis_prompt"], "")
        self.assertEqual(settings["reports_synthesis_prompt"], "")

        # A round trip through save preserves custom text byte-for-byte,
        # including surrounding whitespace, and never substitutes defaults.
        custom = "  Keep digests near 200 words.\n"
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                save_summarize_settings(
                    api_url="http://localhost:9999/v1/chat",
                    model_id="synthetic-model",
                    api_key="synthetic-key",
                    disable_reasoning=False,
                    minutes_target_chars="6000",
                    minutes_max_pages="6",
                    hearings_prompt=custom,
                    reports_prompt="",
                    minutes_prompt="minute prompt",
                    hearings_synthesis_prompt="",
                    reports_synthesis_prompt="",
                )
                config = json.loads(config_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    config["summarize_hearings_prompt"], custom
                )
                self.assertEqual(config["summarize_reports_prompt"], "")
                with mock.patch(
                    "recordprep.ui.main_window._read_config",
                    return_value=json.loads(config_path.read_text(encoding="utf-8")),
                ):
                    settings = load_summarize_settings()
                self.assertEqual(settings["hearings_prompt"], custom)
                self.assertEqual(settings["reports_prompt"], "")

    def test_stage_settings_persist_without_touching_pi_settings(self) -> None:
        from recordprep.ui.main_window import (
            _read_config,
            load_summarize_settings,
            save_summarize_settings,
        )

        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            pi_settings_path = Path(temporary) / "pi-settings.json"
            pi_settings_path.write_text(
                json.dumps({"defaultProvider": "p", "defaultModel": "m"}),
                encoding="utf-8",
            )
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                save_summarize_settings(
                    api_url="http://localhost:9999/v1/chat",
                    model_id="synthetic-model",
                    api_key="synthetic-key",
                    disable_reasoning=False,
                    minutes_target_chars="6000",
                    minutes_max_pages="6",
                    hearings_prompt=sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE,
                    reports_prompt=sa.DEFAULT_REPORT_EXTRACTION_GUIDANCE,
                    minutes_prompt="minute prompt",
                    hearings_synthesis_prompt=sa.DEFAULT_HEARING_SYNTHESIS_GUIDANCE,
                    reports_synthesis_prompt=sa.DEFAULT_REPORT_SYNTHESIS_GUIDANCE,
                    extract_provider="synthetic",
                    extract_model="synthetic-model",
                    extract_thinking="low",
                    synthesize_provider="",
                    synthesize_model="",
                    synthesize_thinking="",
                )
                config = _read_config()
                self.assertEqual(config["summary_extract_pi_model"], "synthetic-model")
                self.assertNotIn("summarize_hearings_window_target_chars", config)
                self.assertNotIn("summarize_reports_window_max_pages", config)
                # Retired word-target keys are never created by a save.
                self.assertNotIn(
                    "summarize_reports_window_target_words", config
                )
                self.assertNotIn(
                    "summarize_hearings_target_words", config
                )
                self.assertNotIn(
                    "summarize_reports_target_words", config
                )
                self.assertEqual(config["summary_extract_pi_thinking"], "low")
                self.assertEqual(config["summary_synthesize_pi_model"], "")
                settings = load_summarize_settings()
                self.assertEqual(settings["extract_model"], "synthetic-model")
                self.assertEqual(settings["synthesize_model"], "")
                self.assertNotIn("hearings_target_words", settings)
                self.assertNotIn("reports_target_words", settings)
                # Built-in defaults are not custom guidance; the Settings
                # buffers stay empty and the runner composes the immutable
                # contract at run time.
                self.assertEqual(settings["hearings_prompt"], "")
                self.assertEqual(settings["hearings_synthesis_prompt"], "")
            # The project PI settings file is untouched by summary saves.
            self.assertEqual(
                json.loads(pi_settings_path.read_text(encoding="utf-8")),
                {"defaultProvider": "p", "defaultModel": "m"},
            )

    def test_retired_word_targets_are_inert_and_preserved(self) -> None:
        from recordprep.ui.main_window import (
            load_summarize_settings,
            save_summarize_settings,
        )

        # Absent, zero, positive, and malformed stored values are all inert:
        # settings no longer expose target fields at all.
        for stored in (
            {},
            {"summarize_hearings_target_words": "0"},
            {"summarize_reports_target_words": "250"},
            {"summarize_hearings_target_words": "junk"},
            {"summarize_reports_window_target_words": "300"},
        ):
            with mock.patch(
                "recordprep.ui.main_window._read_config",
                return_value=dict(stored),
            ):
                settings = load_summarize_settings()
            self.assertNotIn("hearings_target_words", settings)
            self.assertNotIn("reports_target_words", settings)

        # A Settings save preserves existing retired values untouched instead
        # of migrating or zeroing them, and never creates new ones.
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "summarize_hearings_target_words": "0",
                        "summarize_reports_target_words": "250",
                        "summarize_reports_window_target_words": "300",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "recordprep.ui.main_window.CONFIG_FILE", config_path
            ):
                save_summarize_settings(
                    api_url="http://localhost:9999/v1/chat",
                    model_id="synthetic-model",
                    api_key="synthetic-key",
                    disable_reasoning=False,
                    minutes_target_chars="6000",
                    minutes_max_pages="6",
                    hearings_prompt=sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE,
                    reports_prompt=sa.DEFAULT_REPORT_EXTRACTION_GUIDANCE,
                    minutes_prompt="minute prompt",
                    hearings_synthesis_prompt=sa.DEFAULT_HEARING_SYNTHESIS_GUIDANCE,
                    reports_synthesis_prompt=sa.DEFAULT_REPORT_SYNTHESIS_GUIDANCE,
                )
                config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["summarize_hearings_target_words"], "0")
            self.assertEqual(config["summarize_reports_target_words"], "250")
            self.assertEqual(
                config["summarize_reports_window_target_words"], "300"
            )

        # Defaults apply even alongside a custom prompt.
        with mock.patch(
            "recordprep.ui.main_window._read_config",
            return_value={"summarize_reports_prompt": "A genuinely custom prompt."},
        ):
            settings = load_summarize_settings()
        self.assertEqual(settings["reports_prompt"], "A genuinely custom prompt.")


class CompletionAndRestartTests(unittest.TestCase):
    def test_summary_steps_validate_via_pi_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            rows = [synthetic_facts_row("hearings", start=1, end=1)]
            publish_valid_summary(
                root,
                "hearings",
                rows,
                "Hearings Summary\n\nMarch 3, 2025 \u2014 Hearing\n",
            )
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )
            # A metadata hash mismatch fails validation (step Pending).
            meta = sa.load_digest_meta(root, "hearings")
            meta["digest_markdown_sha256"] = "0" * 64
            sa._atomic_write(
                sa.summary_digest_meta_path(root, "hearings"),
                json.dumps(meta) + "\n",
            )
            self.assertTrue(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root)
            )

    def test_restart_clears_generated_summary_artifacts(self) -> None:
        from recordprep.ui.main_window import _reset_generated_case_bundle

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            rows = [synthetic_facts_row("hearings", start=1, end=1)]
            publish_valid_summary(root, "hearings", rows, "Hearings Summary\n")
            publish_valid_summary(root, "reports", [], "Reports Summary\n")
            # Legacy artifacts are also in the reset scope.
            legacy = sa.legacy_summary_facts_path(root, "hearings")
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text("{}\n", encoding="utf-8")
            legacy_jsonl = sa.legacy_summary_digest_jsonl_path(root, "hearings")
            legacy_jsonl.write_text("{}\n", encoding="utf-8")
            _reset_generated_case_bundle(root)
            for kind in sa.SUMMARY_KINDS:
                self.assertFalse(sa.summary_digest_path(root, kind).exists())
                self.assertFalse(sa.summary_digest_meta_path(root, kind).exists())
                self.assertFalse(sa.summary_final_meta_path(root, kind).exists())
                self.assertFalse(
                    sa.legacy_summary_digest_jsonl_path(root, kind).exists()
                )
                self.assertFalse(sa.legacy_summary_facts_path(root, kind).exists())
                self.assertFalse(
                    sa.legacy_summary_facts_meta_path(root, kind).exists()
                )

    def test_edition_invalidated_after_final_text_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [(1, 1, "March 3, 2025", "Report")])
            final_text = (
                "Hearings Summary\nSyn Case\n\n"
                "March 3, 2025 \u2014 Hearing\n\n"
                "A \u201cunique phrase\u201d appears.\n"
            )
            (root / "summaries").mkdir(exist_ok=True)
            final_path = sa.summary_final_path(root, "hearings")
            final_path.write_text(final_text, encoding="utf-8")
            edition = build_summary_edition("hearings", final_path, root)
            publish_summary_edition(edition, final_path)
            self.assertTrue(summary_edition_is_complete("hearings", final_path, root))
            # The runner removes the edition before publishing new text; an
            # ordinary failure must preserve the old edition instead.
            from recordprep.summary_editions import remove_summary_edition

            remove_summary_edition(final_path)
            self.assertFalse(
                summary_edition_is_complete("hearings", final_path, root)
            )


class FakePiEndToEndTests(unittest.TestCase):
    """Runner acceptance against a fake PI executable (no paid calls)."""

    FAKE_PI = r"""#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path

argv = sys.argv[1:]
log = os.environ["FAKE_PI_LOG"]
with open(log, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"cwd": os.getcwd(), "argv": argv}) + "\n")

if "--version" in argv:
    print("0.85.0")
    raise SystemExit(0)

if "--mode" in argv and "rpc" in argv:
    # No model metadata available in the fake; runner warns and continues.
    raise SystemExit(0)

tools_index = argv.index("--tools") if "--tools" in argv else None
tools = argv[tools_index + 1] if tools_index is not None else ""

if "recordprep_get_source" in tools:
    # The real extension reads the work spec through this env contract.
    assert os.environ.get("RECORDPREP_SUMMARY_MODE") == "extract", \
        "RECORDPREP_SUMMARY_MODE must be set for extraction children"
    spec = json.loads(Path(os.environ["RECORDPREP_SUMMARY_WORK_SPEC"]).read_text(encoding="utf-8"))
    marker_match = re.search(r"QUOTEME:([a-z ]+)", spec["source"])
    marker = marker_match.group(1).strip() if marker_match else None
    assert marker, "marker not found in source"
    # The runner prompt must carry the real digest instructions.
    assert "EXTRACTION GUIDANCE" in " ".join(argv), "digest guidance missing"
    assert "PER-CATEGORY GUIDANCE" in " ".join(argv), "category guidance missing"
    categories = []
    for category in spec["categories"]:
        if category["id"] == spec["categories"][0]["id"]:
            categories.append({
                "id": category["id"],
                "digest": {
                    "text": "Synthetic digest recorded by the fake agent.",
                    "evidence": [{"text": marker, "file_page": spec["start_page"]}],
                },
            })
        else:
            categories.append({"id": category["id"], "digest": None})
    Path(spec["candidate_path"]).write_text(json.dumps({
        "artifact": "recordprep-summary-extraction-candidate",
        "item_id": spec["item_id"],
        "categories": categories,
    }), encoding="utf-8")
    print(json.dumps({"type": "agent_end"}))
    raise SystemExit(0)

if "recordprep_finish_summary" in tools:
    assert os.environ.get("RECORDPREP_SUMMARY_MODE") == "synthesize", \
        "RECORDPREP_SUMMARY_MODE must be set for synthesis children"
    dataset = json.loads(Path(os.environ["RECORDPREP_SUMMARY_DATASET"]).read_text(encoding="utf-8"))
    assert len(dataset["documents"]) == len(dataset["rows"]), \
        "the dataset must carry one Markdown block per row"
    assert "<!--" not in dataset["documents"][0], \
        "model-visible Markdown must omit fingerprint comments"
    sections = []
    for row in dataset["rows"]:
        quote_id = None
        for category in row["categories"]:
            digest = category.get("digest") or {}
            if digest.get("evidence"):
                quote_id = digest["evidence"][0]["quote_id"]
                break
        paragraphs = []
        if quote_id:
            paragraphs.append("Narrative with {{quote:%s}}." % quote_id)
        sections.append({
            "item_id": row["item_id"],
            "paragraphs": paragraphs,
        })
    Path(dataset["candidate_path"]).write_text(json.dumps({
        "artifact": "recordprep-summary-synthesis-candidate",
        "sections": sections,
    }), encoding="utf-8")
    print(json.dumps({"type": "agent_end"}))
    raise SystemExit(0)

raise SystemExit(3)
"""

    def _write_fake_pi(self, directory: Path) -> Path:
        fake = directory / "fake-pi"
        fake.write_text(self.FAKE_PI, encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def _staged_project(self, directory: Path) -> Path:
        """Minimal staged .pi project directory with summary resources."""
        project = directory / "staged-project"
        project.mkdir()
        (project / "config.json").write_text("{}", encoding="utf-8")
        source_pi = PROJECT_DIR / ".pi"
        shutil_pi = project / ".pi"
        shutil_pi.mkdir()
        for name in ("settings.json", "SYSTEM.md"):
            (shutil_pi / name).write_text(
                (source_pi / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        for skill in (
            "recordprep-extract-hearing",
            "recordprep-extract-report",
            "recordprep-synthesize-hearings",
            "recordprep-synthesize-reports",
        ):
            (shutil_pi / "skills" / skill).mkdir(parents=True)
            (shutil_pi / "skills" / skill / "SKILL.md").write_text(
                (source_pi / "skills" / skill / "SKILL.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        (shutil_pi / "extensions").mkdir()
        (shutil_pi / "extensions" / "recordprep-summary-tools.ts").write_text(
            (source_pi / "extensions" / "recordprep-summary-tools.ts").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        return project

    def _run_stage(
        self, stage: str, root: Path, project: Path, fake_pi: Path, log: Path
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["RECORDPREP_CASE_BUNDLE"] = str(root)
        env["RECORDPREP_PI_PROJECT_DIR"] = str(project / ".pi")
        env["RECORDPREP_PI_COMMAND_ARGC"] = "1"
        env["RECORDPREP_PI_COMMAND_ARG_0"] = str(fake_pi)
        env["FAKE_PI_LOG"] = str(log)
        cache = directory_cache = Path(tempfile.mkdtemp(prefix="rp-cache."))
        env["XDG_CACHE_HOME"] = str(cache)
        env.pop("RECORDPREP_PI_STALL_TIMEOUT_SECONDS", None)
        try:
            return subprocess.run(
                [sys.executable, str(RUNNER), stage],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                capture_output=True,
                timeout=120,
            )
        finally:
            import shutil as _shutil

            _shutil.rmtree(cache, ignore_errors=True)

    def test_hearings_stage_end_to_end_with_fake_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.add_pages(2, 2, "cc dd")
            builder.finish(
                [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
                [],
                minutes=[(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
            )
            fake_pi = self._write_fake_pi(temp)
            project = self._staged_project(temp)
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake_pi, log
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if "--version" not in line and "rpc" not in line
            ]
            # Two fresh extraction children plus exactly one synthesis child.
            self.assertEqual(len(invocations), 3)
            def _tools(entry):
                argv = entry["argv"]
                return argv[argv.index("--tools") + 1]

            extraction = [
                entry
                for entry in invocations
                if "recordprep_get_source" in _tools(entry)
            ]
            synthesis = [
                entry
                for entry in invocations
                if "recordprep_finish_summary" in _tools(entry)
            ]
            self.assertEqual(len(extraction), 2)
            self.assertEqual(len(synthesis), 1)
            # Fresh process/workspace per document: distinct cwds.
            cwds = {entry["cwd"] for entry in invocations}
            self.assertEqual(len(cwds), 3)
            for entry in extraction + synthesis:
                self.assertIn("--mode", entry["argv"])
                self.assertIn("json", entry["argv"])
                self.assertIn("--no-session", entry["argv"])
                self.assertIn("--approve", entry["argv"])
            for entry in extraction:
                tools = entry["argv"][entry["argv"].index("--tools") + 1]
                self.assertEqual(
                    tools, "recordprep_get_source,recordprep_submit_extraction"
                )
            synthesis_tools = synthesis[0]["argv"][
                synthesis[0]["argv"].index("--tools") + 1
            ]
            self.assertNotIn("read", synthesis_tools.split(","))
            self.assertNotIn("bash", synthesis_tools.split(","))
            self.assertNotIn("write", synthesis_tools.split(","))
            self.assertNotIn("edit", synthesis_tools.split(","))

            # Canonical artifacts validate and contain both rows in order.
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )
            # Fresh runs publish Markdown and no canonical digest JSONL.
            self.assertTrue(sa.summary_digest_path(root, "hearings").is_file())
            self.assertEqual(sa.summary_digest_path(root, "hearings").suffix, ".md")
            self.assertFalse(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").exists()
            )
            rows = sa.load_digest_markdown(root, "hearings")
            self.assertEqual(
                [row["item_id"] for row in rows],
                ["hearing:0001", "hearing:0002"],
            )
            for row in rows:
                self.assertIsNotNone(row["categories"][0]["digest"])
                quote = row["categories"][0]["digest"]["evidence"][0]
                page_text = (
                    root / "text_pages" / f"{row['start_page']:04d}.txt"
                ).read_text(encoding="utf-8")
                span = sa.find_quote_span(quote["text"], page_text)
                self.assertIsNotNone(span)
                self.assertEqual(
                    page_text[span[0] : span[1]], quote["text"]
                )
            final_text = sa.summary_final_path(root, "hearings").read_text(
                encoding="utf-8"
            )
            self.assertIn("Hearings Summary", final_text)
            # Plain headings and clean quoted prose: no generated link markup.
            self.assertIn("March 3, 2025 \u2014 Hearing", final_text)
            self.assertIn("April 4, 2025 \u2014 Hearing", final_text)
            self.assertNotIn("](page:", final_text)
            self.assertNotIn("{{quote:", final_text)
            self.assertIn("\u201c", final_text)

    def test_malformed_fake_agent_candidate_still_completes(self) -> None:
        """A malformed candidate normalizes to warnings and a readable fallback."""
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [], minutes=[(1, 1, "March 3, 2025")])
            fake_script = self.FAKE_PI.replace(
                """    categories = []
    for category in spec["categories"]:
        if category["id"] == spec["categories"][0]["id"]:
            categories.append({
                "id": category["id"],
                "digest": {
                    "text": "Synthetic digest recorded by the fake agent.",
                    "evidence": [{"text": marker, "file_page": spec["start_page"]}],
                },
            })
        else:
            categories.append({"id": category["id"], "digest": None})""",
                """    categories = [{"id": "not_a_category"}, {"id": 42},
                  {"id": "testimony", "digest": {"text": 99}}]""",
            )
            fake = temp / "fake-pi"
            fake.write_text(fake_script, encoding="utf-8")
            fake.chmod(0o755)
            project = self._staged_project(temp)
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake, log
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = sa.load_digest_markdown(root, "hearings")
            row = rows[0]
            # Unknown/malformed categories fill null; the numeric digest text
            # is retained as a usable (if poor) string with no evidence.
            usable = [
                category
                for category in row["categories"]
                if category["digest"] is not None
            ]
            self.assertEqual(len(usable), 1)
            self.assertEqual(usable[0]["id"], "testimony")
            self.assertEqual(usable[0]["digest"]["evidence"], [])
            self.assertTrue(row["quality_flags"])
            # Warnings carry only codes/counts, never case content.
            self.assertNotIn("QUOTEME", result.stdout)
            final_text = sa.summary_final_path(root, "hearings").read_text(
                encoding="utf-8"
            )
            self.assertIn("March 3, 2025 \u2014 Hearing", final_text)
            self.assertIn("99", final_text)

    def test_extraction_failure_preserves_canonical_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.add_pages(2, 2, "cc dd")
            builder.finish([(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")], [])
            # Accept only the first document; the second child exits nonzero.
            fake_script = self.FAKE_PI.replace(
                "marker = marker_match.group(1).strip() if marker_match else None",
                "marker = marker_match.group(1).strip() if marker_match else None\n"
                '    if spec["ordinal"] > 1: raise SystemExit(4)',
            )
            fake = temp / "fake-pi"
            fake.write_text(fake_script, encoding="utf-8")
            fake.chmod(0o755)
            project = self._staged_project(temp)
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake, log
            )

            self.assertNotEqual(result.returncode, 0)
            rows = sa.load_digest_markdown(root, "hearings")
            self.assertEqual([row["item_id"] for row in rows], ["hearing:0001"])
            # No final summary was published.
            self.assertFalse(sa.summary_final_path(root, "hearings").exists())

    def test_legacy_jsonl_bundle_migrates_with_zero_extraction_calls(self) -> None:
        """A valid v2 JSONL bundle converts and synthesizes without extraction."""
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.add_pages(2, 2, "cc dd")
            builder.finish(
                [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
                [],
                minutes=[(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
            )
            items = sa.build_work_items(root, _extraction_config())
            legacy_rows = [
                synthetic_facts_row(
                    "hearings",
                    start=1,
                    end=1,
                    generation_sha256=items[0].generation_sha256,
                    facts={
                        "parent_appearances": [
                            {
                                "text": "Mother appeared remotely.",
                                "evidence": [
                                    {"text": "unique phrase", "file_page": 1}
                                ],
                            }
                        ]
                    },
                ),
                synthetic_facts_row(
                    "hearings",
                    start=2,
                    end=2,
                    ordinal=2,
                    generation_sha256=items[1].generation_sha256,
                    facts={
                        "parent_appearances": [
                            {
                                "text": "Father appeared in person.",
                                "evidence": [
                                    {"text": "unique phrase", "file_page": 2}
                                ],
                            }
                        ]
                    },
                ),
            ]
            write_legacy_digest_jsonl(root, "hearings", legacy_rows)
            fake_pi = self._write_fake_pi(temp)
            project = self._staged_project(temp)
            # Match the fixture extraction config so the migrated rows are
            # current under the runner's own fingerprint computation.
            (project / "config.json").write_text(
                json.dumps(
                    {
                        "summary_extract_hearings_pi_provider": "synthetic",
                        "summary_extract_hearings_pi_model": "synthetic-model",
                        "summary_extract_hearings_pi_thinking": "low",
                        "summarize_hearings_target_words": "250",
                        "summarize_reports_target_words": "250",
                    }
                ),
                encoding="utf-8",
            )
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake_pi, log
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if "--version" not in line and "rpc" not in line
            ]
            # Migration is lossless: no extraction children ran at all, and
            # exactly one synthesis child consumed the converted Markdown.
            self.assertEqual(len(invocations), 1)
            self.assertIn(
                "recordprep_finish_summary",
                invocations[0]["argv"][
                    invocations[0]["argv"].index("--tools") + 1
                ],
            )
            self.assertFalse(
                sa.legacy_summary_digest_jsonl_path(root, "hearings").exists()
            )
            self.assertTrue(sa.summary_digest_path(root, "hearings").is_file())
            self.assertEqual(
                sa.load_digest_markdown(root, "hearings"), legacy_rows
            )
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )

    def test_child_prompts_carry_no_length_budgets_or_quotas(self) -> None:
        """Captured child prompts have no word budgets, length sections,
        six-quote quotas, or the retired material-details header."""
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            fake_pi = self._write_fake_pi(temp)
            project = self._staged_project(temp)
            # Stored retired word-target values are inert.
            (project / "config.json").write_text(
                json.dumps(
                    {
                        "summarize_hearings_target_words": "250",
                        "summary_extract_hearings_pi_provider": "synthetic",
                        "summary_extract_hearings_pi_model": "synthetic-model",
                        "summary_extract_hearings_pi_thinking": "low",
                    }
                ),
                encoding="utf-8",
            )
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake_pi, log
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if "--version" not in line and "rpc" not in line
            ]
            self.assertTrue(invocations)
            for entry in invocations:
                prompt = " ".join(
                    str(part) for part in entry["argv"]
                )
                self.assertNotIn("LENGTH GUIDANCE", prompt)
                self.assertNotIn("SUMMARIZE ALL MATERIAL DETAILS", prompt)
                self.assertNotIn("approximately 250 words", prompt)
                self.assertNotIn("at least six", prompt)
                self.assertNotIn("six useful short quotations", prompt)
                self.assertNotIn("target words", prompt.lower())
                self.assertNotIn("word target", prompt.lower())

    def test_zero_item_boundary_set_publishes_empty_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.finish([], [])
            fake_pi = self._write_fake_pi(temp)
            project = self._staged_project(temp)
            log = temp / "invocations.log"

            result = self._run_stage(
                "create_hearing_summaries", root, project, fake_pi, log
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            invocations = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if "--version" not in line and "rpc" not in line
            ]
            self.assertEqual(invocations, [])
            self.assertEqual(
                sa.load_digest_meta(root, "hearings")["complete"], True
            )
            final_text = sa.summary_final_path(root, "hearings").read_text(
                encoding="utf-8"
            )
            self.assertTrue(final_text.startswith("Hearings Summary\nSynCase"))
            self.assertNotIn("\u2014 Hearing", final_text)
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )


HANGING_FAKE_PI = r"""#!/usr/bin/env python3
import json, os, sys, time

argv = sys.argv[1:]
with open(os.environ["FAKE_PI_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"cwd": os.getcwd(), "argv": argv, "pid": os.getpid()}) + "\n")

if "--version" in argv:
    print("0.85.0")
    raise SystemExit(0)
if "--mode" in argv and "rpc" in argv:
    raise SystemExit(0)

# Extraction child: hang until signaled.
print(json.dumps({"type": "agent_start"}), flush=True)
time.sleep(300)
"""


class StopPropagationTests(unittest.TestCase):
    """Stop terminates the active child process group and stays Pending."""

    def test_stop_kills_child_group_and_publishes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            root = temp / "bundle"
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.add_pages(2, 2, "cc dd")
            builder.finish(
                [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
                [],
                minutes=[(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")],
            )
            fake = temp / "fake-pi"
            fake.write_text(HANGING_FAKE_PI, encoding="utf-8")
            fake.chmod(0o755)
            project = FakePiEndToEndTests._staged_project(
                FakePiEndToEndTests, temp
            )
            log = temp / "inv.log"

            env = os.environ.copy()
            env["RECORDPREP_CASE_BUNDLE"] = str(root)
            env["RECORDPREP_PI_PROJECT_DIR"] = str(project / ".pi")
            env["RECORDPREP_PI_COMMAND_ARGC"] = "1"
            env["RECORDPREP_PI_COMMAND_ARG_0"] = str(fake)
            env["FAKE_PI_LOG"] = str(log)
            cache = temp / "cache"
            env["XDG_CACHE_HOME"] = str(cache)

            runner_process = subprocess.Popen(
                [sys.executable, str(RUNNER), "create_hearing_summaries"],
                cwd=PROJECT_DIR,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            try:
                # Wait until the hanging extraction child has started.
                child_pid = None
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if log.exists():
                        entries = [
                            json.loads(line)
                            for line in log.read_text().splitlines()
                        ]
                        children = [
                            entry for entry in entries if entry.get("pid")
                        ]
                        if children:
                            child_pid = children[-1]["pid"]
                            break
                    if runner_process.poll() is not None:
                        break
                    time.sleep(0.1)
                self.assertIsNotNone(child_pid, "hanging child never started")

                runner_process.terminate()
                try:
                    runner_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.fail("runner did not exit after SIGTERM")

                # The child process group is gone.
                self.assertFalse(Path(f"/proc/{child_pid}").exists())

                # No canonical row or final summary was published.
                rows = sa.load_digest_markdown(root, "hearings")
                self.assertEqual(rows, [])
                self.assertFalse(sa.summary_final_path(root, "hearings").exists())
                self.assertFalse(
                    sa.summary_digest_meta_path(root, "hearings").exists()
                )
            finally:
                if runner_process.poll() is None:
                    runner_process.kill()
                    runner_process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
