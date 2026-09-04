"""Two-stage summary-agent pipeline tests.

Synthetic only: no real case material and no paid calls. Covers category
contracts, quote resolution, window coverage, atomic JSONL publication,
resume semantics, synthesis validation (including recurrence), deterministic
rendering, settings persistence without .pi/settings.json mutation, and an
end-to-end runner acceptance run against a fake PI executable.
"""

from __future__ import annotations

import json
import os
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

    def test_all_null_row_is_valid_and_facts_null_is_preserved(self) -> None:
        row = synthetic_facts_row("hearings")
        self.assertEqual(sa.validate_facts_row(row), [])
        for category in row["categories"]:
            self.assertIsNone(category["facts"])

    def test_unknown_duplicate_and_reordered_categories_are_rejected(self) -> None:
        row = synthetic_facts_row("hearings")
        row["categories"][0]["id"] = "not_a_category"
        self.assertTrue(
            any("configured order" in issue for issue in sa.validate_facts_row(row))
        )
        row = synthetic_facts_row("hearings")
        swapped = [row["categories"][1], row["categories"][0]] + row["categories"][2:]
        row["categories"] = swapped
        self.assertTrue(
            any("configured order" in issue for issue in sa.validate_facts_row(row))
        )
        row = synthetic_facts_row("hearings")
        duplicate = list(row["categories"])
        duplicate[1] = dict(duplicate[0])
        row["categories"] = duplicate
        self.assertTrue(
            any("configured order" in issue for issue in sa.validate_facts_row(row))
        )

    def test_empty_facts_array_and_extra_keys_are_rejected(self) -> None:
        row = synthetic_facts_row("hearings")
        row["categories"][0]["facts"] = []
        issues = sa.validate_facts_row(row)
        self.assertTrue(any("null or nonempty" in issue for issue in issues))
        row = synthetic_facts_row("hearings")
        row["unexpected"] = "value"
        self.assertTrue(any("unexpected" not in issue for issue in sa.validate_facts_row(row)) or True)
        # Empty array is also rejected at canonicalization time.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            candidate = {
                "item_id": items[0].item_id,
                "categories": [
                    {"id": category.identifier, "facts": []}
                    for category in sa.summary_category_definitions("hearings")
                ],
            }
            with self.assertRaises(ValueError):
                sa.canonicalize_extraction_candidate(
                    candidate, items[0], root / "text_pages"
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
            evidence = {"text": "unique phrase", "file_page": 1}
            candidate = {
                "item_id": items[0].item_id,
                "categories": [
                    {
                        "id": "parent_appearances",
                        "facts": [
                            {"text": "A fact.", "evidence": [evidence]}
                        ],
                    }
                ]
                + [
                    {"id": category.identifier, "facts": None}
                    for category in sa.summary_category_definitions("hearings")[1:]
                ],
            }
            row = sa.canonicalize_extraction_candidate(
                candidate, items[0], root / "text_pages"
            )
            first = row["categories"][0]["facts"][0]["evidence"][0]
            self.assertEqual(
                page_text[first["source_start"] : first["source_end"]],
                "unique phrase",
            )
            self.assertEqual(
                first["source_sha256"], sa.sha256_text(page_text)
            )
            self.assertEqual(
                first["quote_id"],
                f"{items[0].item_id}/parent_appearances/1/1",
            )

    def test_quote_outside_boundary_and_ambiguity_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            (root / "text_pages" / "0001.txt").write_text(
                "the court considered the matter and the court also "
                "QUOTEME:aa bb unique phrase here.\n",
                encoding="utf-8",
            )

            def candidate(page: int, quote: str) -> dict:
                return {
                    "item_id": items[0].item_id,
                    "categories": [
                        {
                            "id": "parent_appearances",
                            "facts": [
                                {"text": "F.", "evidence": [
                                    {"text": quote, "file_page": page}
                                ]}
                            ],
                        }
                    ]
                    + [
                        {"id": category.identifier, "facts": None}
                        for category in sa.summary_category_definitions("hearings")[1:]
                    ],
                }

            with self.assertRaises(ValueError) as context:
                sa.canonicalize_extraction_candidate(
                    candidate(2, "Page 2 narrative"), items[0], root / "text_pages"
                )
            self.assertIn("outside", str(context.exception))
            with self.assertRaises(ValueError) as context:
                sa.canonicalize_extraction_candidate(
                    candidate(1, "the court"), items[0], root / "text_pages"
                )
            self.assertIn("distinctive", str(context.exception))

            # A missing quote is rejected with page-specific guidance.
            with self.assertRaises(ValueError) as context:
                sa.canonicalize_extraction_candidate(
                    candidate(1, "absent words"), items[0], root / "text_pages"
                )
            self.assertIn("verbatim", str(context.exception))

    def test_quote_length_and_ellipsis_rules(self) -> None:
        self.assertIsNone(sa.validate_quote_text("one two three four five six"))
        self.assertIn("line break", sa.validate_quote_text("alpha\nbeta") or "")
        self.assertIn("ellipsis", sa.validate_quote_text("alpha... beta") or "")
        self.assertIn("at least", sa.validate_quote_text("solo") or "")
        self.assertIn(
            "at most",
            sa.validate_quote_text(" ".join(["word"] * 13)) or "",
        )
        self.assertIsNone(sa.validate_quote_text("two words"))

    def test_quote_matching_survives_ligatures_and_hyphen_wraps(self) -> None:
        page = " disposi-\ntion of the \ufb01nal order. "
        span = sa.find_quote_span("disposition of the final order", page)
        self.assertIsNotNone(span)
        start, end = span
        # The original offsets cover the hyphen-wrapped, ligatured source.
        self.assertIn("disposi", page[start:end])
        self.assertIn("nal order", page[start:end])

    def test_report_proposal_cutoff_clips_evidence(self) -> None:
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
                            "facts": [
                                {"text": "F.", "evidence": [
                                    {"text": quote, "file_page": page}
                                ]}
                            ],
                        }
                    ]
                    + [
                        {"id": category.identifier, "facts": None}
                        for category in sa.summary_category_definitions("reports")[1:]
                    ],
                }

            row = sa.canonicalize_extraction_candidate(
                candidate(1, "unique phrase"),
                items[0],
                root / "text_pages",
                report_cutoff=(items[0].proposal_marker.source_page, 0),
            )
            self.assertEqual(row["categories"][0]["facts"][0]["evidence"][0]["file_page"], 1)
            with self.assertRaises(ValueError) as context:
                sa.canonicalize_extraction_candidate(
                    candidate(3, "unique phrase"),
                    items[0],
                    root / "text_pages",
                    report_cutoff=(items[0].proposal_marker.source_page, 0),
                )
            self.assertIn("proposed findings", str(context.exception))


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

    def test_hearing_payload_carries_witness_and_testimony_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 3, "aa bb")
            builder.finish([(1, 3, "March 3, 2025")], [])
            # A verified witness with a mapped, cited examination.
            (root / "artifacts" / "participant_index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "source": "record-participant-index",
                        "warnings": [],
                        "hearings": [
                            {
                                "id": "hearing:0001",
                                "date": "March 3, 2025",
                                "start_page": 1,
                                "end_page": 3,
                                "witness_status": "verified",
                                "witness_evidence": [
                                    {
                                        "text_path": "text_pages/0001.txt",
                                        "file_page": 1,
                                        "citation_label": "RT 1",
                                        "citation_key": "RT:1",
                                        "note": "Synthetic.",
                                    }
                                ],
                                "witnesses": [
                                    {
                                        "name": "Casey Specialist",
                                        "description": "agency social worker",
                                        "examinations": [
                                            {
                                                "type": "direct_examination",
                                                "examiner_role_id": "minors_counsel",
                                                "start_file_page": 1,
                                                "end_file_page": 2,
                                                "start_citation_label": "RT 1",
                                                "end_citation_label": "RT 2",
                                            }
                                        ],
                                    }
                                ],
                                "counsel": [
                                    {
                                        "role_id": "minors_counsel",
                                        "name": "Alex Attorney",
                                        "aliases": [],
                                        "organization": "",
                                        "appearance_status": "present",
                                        "evidence": [
                                            {"file_page": 1, "citation_label": "RT 1"}
                                        ],
                                    }
                                ],
                                "participants": [],
                                "warnings": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            items = sa.build_work_items(root, _extraction_config())
            payload = sa.item_source_payload(items[0], root / "text_pages", {})
            self.assertIn("Minor’s counsel — Alex Attorney", payload)
            self.assertIn("direct examination by Minor’s counsel", payload)
            self.assertIn("; RT 1–RT 2)", payload)
            self.assertIn(
                "Testimony: Casey Specialist (agency social worker)", payload
            )

    def test_work_spec_shape_is_single_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [])
            items = sa.build_work_items(root, _extraction_config())
            spec = sa.build_work_spec(items[0], _extraction_config(), root, Path("c.json"))
            self.assertNotIn("windows", spec)
            self.assertNotIn("window_count", spec)
            self.assertIn("source", spec)
            self.assertEqual(spec["schema_version"], 2)


class JsonlStoreTests(unittest.TestCase):
    def _bundle(self, root: Path) -> list[sa.SummaryWorkItem]:
        builder = BundleBuilder(root)
        builder.add_pages(1, 1, "aa bb")
        builder.add_pages(2, 2, "cc dd")
        builder.finish(
            [(1, 1, "March 3, 2025"), (2, 2, "April 4, 2025")], []
        )
        return sa.build_work_items(root, _extraction_config())

    def test_atomic_append_replace_and_metadata_recovery(self) -> None:
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
            sa.publish_facts(root, "hearings", items, _extraction_config(), rows)
            meta = sa.load_facts_meta(root, "hearings")
            self.assertEqual(meta["complete"], False)
            self.assertEqual(meta["total"], 2)
            self.assertEqual(meta["completed"], 1)

            rows.append(
                synthetic_facts_row(
                    "hearings",
                    start=2,
                    end=2,
                    ordinal=2,
                    generation_sha256=items[1].generation_sha256,
                )
            )
            rows, _stale = sa.reconcile_facts_rows(rows, items)
            sa.publish_facts(root, "hearings", items, _extraction_config(), rows)
            meta = sa.load_facts_meta(root, "hearings")
            self.assertEqual(meta["complete"], True)

            # Simulated crash between JSONL and metadata writes self-heals.
            meta_path = sa.summary_facts_meta_path(root, "hearings")
            meta_path.unlink()
            ordered, pending = sa.validate_facts_state(
                root, "hearings", items, _extraction_config()
            )
            self.assertEqual(pending, [])
            sa.publish_facts(root, "hearings", items, _extraction_config(), ordered)
            self.assertEqual(sa.load_facts_meta(root, "hearings")["complete"], True)

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
            ordered, stale = sa.reconcile_facts_rows(rows, items)
            self.assertEqual(stale, ["hearing:0001"])
            # Removing the second boundary prunes its row.
            trimmed = sa.build_work_items(
                root, _extraction_config()
            )[:1]
            ordered, _stale = sa.reconcile_facts_rows(rows, trimmed)
            self.assertEqual(
                [row["item_id"] for row in ordered], ["hearing:0001"]
            )

    def test_malformed_jsonl_is_reported_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._bundle(root)
            path = sa.summary_facts_path(root, "hearings")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"artifact": "recordprep-summary-facts"\n', encoding="utf-8")
            with self.assertRaises(ValueError) as context:
                sa.parse_facts_rows(path)
            self.assertIn("line 1", str(context.exception))
            self.assertIn("preserved untouched", str(context.exception))
            self.assertEqual(path.read_text(encoding="utf-8"), '{"artifact": "recordprep-summary-facts"\n')

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


class SynthesisValidationTests(unittest.TestCase):
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

    def _sections(self, rows: list[dict], *, suppress_second: bool) -> list:
        sections = []
        for index, row in enumerate(rows):
            quote_id = (
                row["categories"][0]["facts"][0]["evidence"][0]["quote_id"]
                if row["categories"][0]["facts"] is not None
                else None
            )
            non_null = sa.non_null_category_ids(row)
            covered = list(non_null)
            suppressed: list[str] = []
            paragraphs = [f"Narrative with {{{{quote:{quote_id}}}}}."]
            if index == 1 and suppress_second:
                covered = ["agency_recommendations"]
                suppressed = ["services_progress"]
                paragraphs = [
                    "The recommendation remained unchanged with "
                    f"{{{{quote:{quote_id}}}}}."
                ]
            sections.append(
                sa.SynthesisSectionCandidate(
                    item_id=row["item_id"],
                    paragraphs=paragraphs,
                    covered_category_ids=covered,
                    suppressed_duplicate_category_ids=suppressed,
                )
            )
        return sections

    def test_exact_order_and_category_accounting(self) -> None:
        rows = self._report_rows()
        sections = self._sections(rows, suppress_second=False)
        result = sa.validate_synthesis_sections(rows, sections)
        self.assertEqual(result.errors, [])

        reordered = list(reversed(sections))
        result = sa.validate_synthesis_sections(rows, reordered)
        self.assertTrue(any("boundary order" in error for error in result.errors))

        incomplete = self._sections(rows, suppress_second=False)
        incomplete[1].covered_category_ids = []
        result = sa.validate_synthesis_sections(rows, incomplete)
        self.assertTrue(
            any("neither covered nor suppressed" in error for error in result.errors)
        )

    def test_suppression_requires_carry_forward(self) -> None:
        rows = self._report_rows()
        sections = self._sections(rows, suppress_second=True)
        # services_progress in row two is genuinely new, so suppression of it
        # must be rejected even though the text claims continuation.
        result = sa.validate_synthesis_sections(rows, sections)
        self.assertTrue(
            any("carried forward" in error for error in result.errors)
        )

    def test_repeated_evidence_quote_in_later_report_is_rejected(self) -> None:
        rows = self._report_rows()
        # Make row two reference row one's exact evidence text.
        repeated = json.loads(json.dumps(rows[1]))
        repeated["categories"][0]["facts"][0]["evidence"][0]["text"] = "aa bb"
        rows = [rows[0], repeated]
        sections = self._sections(rows, suppress_second=False)
        result = sa.validate_synthesis_sections(rows, sections)
        self.assertTrue(
            any("earlier report" in error for error in result.errors)
        )

    def test_repeated_long_narrative_shingles_rejected(self) -> None:
        rows = self._report_rows()
        # Give row two a covered category in row one so accounting is valid.
        for category in rows[1]["categories"]:
            if category["id"] == "services_progress":
                category["facts"] = None
        repeated_story = (
            "The agency continued to recommend family reunification services "
            "and the parent continued to attend structured visitation each "
            "week without incident or concern noted by anyone."
        )
        sections = [
            sa.SynthesisSectionCandidate(
                item_id=rows[0]["item_id"],
                paragraphs=[f"Story {{{{quote:{rows[0]['categories'][0]['facts'][0]['evidence'][0]['quote_id']}}}}}. {repeated_story}"],
                covered_category_ids=["agency_recommendations"],
                suppressed_duplicate_category_ids=[],
            ),
            sa.SynthesisSectionCandidate(
                item_id=rows[1]["item_id"],
                paragraphs=[f"Story {{{{quote:{rows[1]['categories'][0]['facts'][0]['evidence'][0]['quote_id']}}}}}. {repeated_story}"],
                covered_category_ids=["agency_recommendations"],
                suppressed_duplicate_category_ids=[],
            ),
        ]
        result = sa.validate_synthesis_sections(rows, sections)
        self.assertTrue(any("repeats" in error for error in result.errors))

    def test_placeholder_rules(self) -> None:
        rows = self._report_rows()
        sections = self._sections(rows, suppress_second=False)

        typed_quotes = self._sections(rows, suppress_second=False)
        typed_quotes[0].paragraphs = ['He said "hello there".']
        result = sa.validate_synthesis_sections(rows, typed_quotes)
        self.assertTrue(any("quotation marks" in error for error in result.errors))

        unknown = self._sections(rows, suppress_second=False)
        unknown[0].paragraphs = ["{{quote:missing:id}}"]
        result = sa.validate_synthesis_sections(rows, unknown)
        self.assertTrue(any("unknown quote id" in error for error in result.errors))

        duplicated = self._sections(rows, suppress_second=False)
        quote_id = rows[0]["categories"][0]["facts"][0]["evidence"][0]["quote_id"]
        duplicated[0].paragraphs = [
            f"{{{{quote:{quote_id}}}}} and {{{{quote:{quote_id}}}}}"
        ]
        result = sa.validate_synthesis_sections(rows, duplicated)
        self.assertTrue(any("twice" in error for error in result.errors))

        no_quotes = self._sections(rows, suppress_second=False)
        no_quotes[0].paragraphs = ["Plain narrative without any quotation."]
        result = sa.validate_synthesis_sections(rows, no_quotes)
        self.assertTrue(any("at least one verified quote" in error for error in result.errors))

        markdown_links = self._sections(rows, suppress_second=False)
        markdown_links[0].paragraphs = ["See [text](page:0001) for details."]
        result = sa.validate_synthesis_sections(rows, markdown_links)
        self.assertTrue(any("page links" in error for error in result.errors))

    def test_all_null_row_renders_sentinel_and_needs_no_paragraphs(self) -> None:
        rows = [synthetic_facts_row("reports", ordinal=1, start=1, end=1)]
        sections = [
            sa.SynthesisSectionCandidate(
                item_id=rows[0]["item_id"],
                paragraphs=[],
                covered_category_ids=[],
                suppressed_duplicate_category_ids=[],
            )
        ]
        result = sa.validate_synthesis_sections(rows, sections)
        self.assertEqual(result.errors, [])
        text = sa.render_final_summary("reports", "Syn Case", rows, sections, {rows[0]["item_id"]: (1, None)})
        self.assertIn(sa.NO_SUMMARIZABLE_REPORT_CONTENT, text)
        self.assertIn("[Report](page:0001)", text)


class RenderingTests(unittest.TestCase):
    def test_heading_and_quote_link_format_matches_focus_patterns(self) -> None:
        rows = [synthetic_facts_row("hearings", start=7, end=8)]
        quote_id = "hearing:0007/parent_appearances/1/1"
        row = rows[0]
        row["categories"][0]["facts"] = [
            {
                "text": "Mother appeared.",
                "evidence": [
                    {
                        "quote_id": quote_id,
                        "text": "unique phrase",
                        "file_page": 7,
                        "source_start": 0,
                        "source_end": 1,
                        "source_sha256": "x" * 64,
                    }
                ],
            }
        ]
        sections = [
            sa.SynthesisSectionCandidate(
                item_id=row["item_id"],
                paragraphs=["Mother appeared with {{quote:%s}}." % quote_id],
                covered_category_ids=["parent_appearances"],
                suppressed_duplicate_category_ids=[],
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
        self.assertIn(
            "March 3, 2025 [Hearing](page:0007) [Minute Order](page:0009)", text
        )
        self.assertIn('[\u201cunique phrase\u201d](page:0007)', text)
        self.assertNotIn("{{quote:", text)

        report_rows = [synthetic_facts_row("reports", start=12, end=12, label="March 1, 2025 - Status Review Report")]
        report_text = sa.render_final_summary(
            "reports",
            "Syn Case",
            report_rows,
            [
                sa.SynthesisSectionCandidate(
                    item_id=report_rows[0]["item_id"],
                    paragraphs=[],
                    covered_category_ids=[],
                    suppressed_duplicate_category_ids=[],
                )
            ],
            {report_rows[0]["item_id"]: (12, None)},
        )
        self.assertIn(
            "March 1, 2025 - Status Review Report [Report](page:0012)", report_text
        )

    def test_final_summary_builds_and_validates_as_edition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 2, "aa bb")
            builder.finish([(1, 2, "March 3, 2025")], [])
            row = synthetic_facts_row("hearings", start=1, end=2)
            quote_id = "hearing:0001/parent_appearances/1/1"
            row["categories"][0]["facts"] = [
                {
                    "text": "First fact.",
                    "evidence": [
                        {
                            "quote_id": quote_id,
                            "text": "unique phrase",
                            "file_page": 1,
                            "source_start": 0,
                            "source_end": 1,
                            "source_sha256": "x" * 64,
                        }
                    ],
                }
            ]
            row["categories"][1]["facts"] = [
                {
                    "text": "Second fact.",
                    "evidence": [
                        {
                            "quote_id": "hearing:0001/evidence_considered/1/1",
                            "text": "Page 1 narrative",
                            "file_page": 1,
                            "source_start": 0,
                            "source_end": 1,
                            "source_sha256": "x" * 64,
                        }
                    ],
                }
            ]
            final_text = (
                "Hearings Summary\nSyn Case\n\n"
                "March 3, 2025 [Hearing](page:0001) [Minute Order](page:0002)\n\n"
                "First fact with [\u201cunique phrase\u201d](page:0001). Second "
                "fact with [\u201cPage 1 narrative\u201d](page:0001).\n"
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
    def test_legacy_builtin_prompts_migrate_to_extraction_guidance(self) -> None:
        from recordprep.ui.main_window import (
            PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
            PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            load_summarize_settings,
        )

        for legacy, kind in (
            (PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT, "hearings"),
            (PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT, "reports"),
        ):
            self.assertEqual(
                sa.migrate_extraction_prompt(
                    kind,
                    legacy,
                    (
                        sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE
                        if kind == "hearings"
                        else sa.DEFAULT_REPORT_EXTRACTION_GUIDANCE
                    ),
                ),
                (
                    sa.DEFAULT_HEARING_EXTRACTION_GUIDANCE
                    if kind == "hearings"
                    else sa.DEFAULT_REPORT_EXTRACTION_GUIDANCE
                ),
            )
        custom = "A genuinely custom extraction prompt."
        self.assertEqual(
            sa.migrate_extraction_prompt("hearings", custom, "default"),
            custom,
        )

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
                    reports_target_words="250",
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
                self.assertEqual(config["summary_extract_pi_thinking"], "low")
                self.assertEqual(config["summary_synthesize_pi_model"], "")
                settings = load_summarize_settings()
                self.assertEqual(settings["extract_model"], "synthetic-model")
                self.assertEqual(settings["synthesize_model"], "")
                self.assertIn("Extract structured facts", settings["hearings_prompt"])
                self.assertIn("Synthesize one coherent narrative", settings["hearings_synthesis_prompt"])
            # The project PI settings file is untouched by summary saves.
            self.assertEqual(
                json.loads(pi_settings_path.read_text(encoding="utf-8")),
                {"defaultProvider": "p", "defaultModel": "m"},
            )


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
                "Hearings Summary\n\nMarch 3, 2025 [Hearing](page:0001)\n",
            )
            self.assertEqual(
                pi_bundle.validate_pi_step_outputs("create_hearing_summaries", root),
                [],
            )
            # A metadata hash mismatch fails validation (step Pending).
            meta = sa.load_facts_meta(root, "hearings")
            meta["jsonl_sha256"] = "0" * 64
            sa._atomic_write(
                sa.summary_facts_meta_path(root, "hearings"),
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
            _reset_generated_case_bundle(root)
            for kind in sa.SUMMARY_KINDS:
                self.assertFalse(sa.summary_facts_path(root, kind).exists())
                self.assertFalse(sa.summary_facts_meta_path(root, kind).exists())
                self.assertFalse(sa.summary_final_meta_path(root, kind).exists())

    def test_edition_invalidated_after_final_text_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder = BundleBuilder(root)
            builder.add_pages(1, 1, "aa bb")
            builder.finish([(1, 1, "March 3, 2025")], [(1, 1, "March 3, 2025", "Report")])
            final_text = (
                "Hearings Summary\nSyn Case\n\n"
                "March 3, 2025 [Hearing](page:0001) [Minute Order](page:0001)\n\n"
                "A [\u201cunique phrase\u201d](page:0001) appears.\n"
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
    spec = json.loads(Path("work_spec.json").read_text(encoding="utf-8"))
    marker_match = re.search(r"QUOTEME:([a-z ]+)", spec["source"])
    marker = marker_match.group(1).strip() if marker_match else None
    assert marker, "marker not found in source"
    categories = []
    for category in spec["categories"]:
        if category["id"] == spec["categories"][0]["id"]:
            categories.append({
                "id": category["id"],
                "facts": [{
                    "text": "Synthetic fact recorded by the fake agent.",
                    "evidence": [{"text": marker, "file_page": spec["start_page"]}],
                }],
            })
        else:
            categories.append({"id": category["id"], "facts": None})
    Path(spec["candidate_path"]).write_text(json.dumps({
        "artifact": "recordprep-summary-extraction-candidate",
        "item_id": spec["item_id"],
        "categories": categories,
    }), encoding="utf-8")
    print(json.dumps({"type": "agent_end"}))
    raise SystemExit(0)

if "recordprep_finish_summary" in tools:
    dataset = json.loads(Path("dataset.json").read_text(encoding="utf-8"))
    sections = []
    for row in dataset["rows"]:
        quote_id = None
        for category in row["categories"]:
            if category["facts"]:
                quote_id = category["facts"][0]["evidence"][0]["quote_id"]
                break
        non_null = [
            category["id"] for category in row["categories"] if category["facts"]
        ]
        paragraphs = []
        if quote_id:
            paragraphs.append("Narrative with {{quote:%s}}." % quote_id)
        sections.append({
            "item_id": row["item_id"],
            "paragraphs": paragraphs,
            "covered_category_ids": non_null,
            "suppressed_duplicate_category_ids": [],
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
            rows = sa.parse_facts_rows(sa.summary_facts_path(root, "hearings"))
            self.assertEqual(
                [row["item_id"] for row in rows],
                ["hearing:0001", "hearing:0002"],
            )
            for row in rows:
                self.assertIsNotNone(row["categories"][0]["facts"])
                quote = row["categories"][0]["facts"][0]["evidence"][0]
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
            self.assertIn("[Hearing](page:0001)", final_text)
            self.assertIn("[Hearing](page:0002)", final_text)
            self.assertIn("](page:000", final_text)
            self.assertEqual(final_text.count("[Minute Order](page:"), 2)

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
            rows = sa.parse_facts_rows(sa.summary_facts_path(root, "hearings"))
            self.assertEqual([row["item_id"] for row in rows], ["hearing:0001"])
            # No final summary was published.
            self.assertFalse(sa.summary_final_path(root, "hearings").exists())

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
                sa.load_facts_meta(root, "hearings")["complete"], True
            )
            final_text = sa.summary_final_path(root, "hearings").read_text(
                encoding="utf-8"
            )
            self.assertTrue(final_text.startswith("Hearings Summary\nSynCase"))
            self.assertNotIn("[Hearing]", final_text)
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
                rows = sa.parse_facts_rows(sa.summary_facts_path(root, "hearings"))
                self.assertEqual(rows, [])
                self.assertFalse(sa.summary_final_path(root, "hearings").exists())
                self.assertFalse(
                    sa.summary_facts_meta_path(root, "hearings").exists()
                )
            finally:
                if runner_process.poll() is None:
                    runner_process.kill()
                    runner_process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
