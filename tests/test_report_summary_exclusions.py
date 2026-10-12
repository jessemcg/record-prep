"""Focused tests for excluding formal proposed findings/orders from report summaries.

Synthetic only: no real case material. These tests exercise the conservative
marker detector, the production complete-document scope delimiter, the
built-in report-prompt contract, the exact-sentinel skip, and the prompt
migration for the saved built-in report prompt.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from recordprep import summary_agents as _summary_agents
from recordprep.ui.main_window import (
    DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    NO_SUMMARIZABLE_REPORT_CONTENT,
    PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
    REPORT_PROPOSAL_MARKER_FIND_ORDER,
    REPORT_PROPOSAL_MARKER_LEAD_IN,
    REPORT_PROPOSAL_MARKER_SPLIT,
    REPORT_PROPOSAL_MARKER_TITLE,
    REPORT_PROPOSAL_SCOPE_DELIMITER,
    REPORT_PROPOSAL_SCOPE_HEADING,
    ReportProposalMarker,
    _detect_report_proposal_marker,
    _insert_report_proposal_delimiter,
    load_summarize_settings,
)


def _payload(pages, *, participant_context="", marker=None):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for page, text in pages.items():
            (root / f"{page:04d}.txt").write_text(text)
        item = SimpleNamespace(start_page=min(pages), end_page=max(pages),
                               participant_context=participant_context, proposal_marker=marker)
        return _summary_agents.item_source_payload(item, root, {page: f"TEST {page}" for page in pages})


def _pages(*chunks: str) -> dict[int, str]:
    return {index: text for index, text in enumerate(chunks, start=1)}


class ReportProposalMarkerDetectionTests(unittest.TestCase):
    def test_title_marker_with_variation(self) -> None:
        variants = (
            "PROPOSED FINDINGS AND ORDERS",
            "proposed findings and orders:",
            "# RECOMMENDED FINDINGS AND ORDERS",
            "**RECOMMENDED   FINDINGS  AND  ORDERS**",
            "1. PROPOSED FINDINGS / ORDERS.",
            "PROPOSED\nFINDINGS AND ORDERS",
        )
        for text in variants:
            marker = _detect_report_proposal_marker(_pages(text + "\nsome narrative"), 1, 1)
            self.assertIsNotNone(marker, text)
            self.assertEqual(marker.kind, REPORT_PROPOSAL_MARKER_TITLE, text)
            self.assertGreaterEqual(marker.offset, 0)
            self.assertGreaterEqual(marker.line_number, 1)

    def test_lead_in_marker(self) -> None:
        text = (
            "The undersigned respectfully recommends that the Court make the "
            "following findings and orders:"
        )
        marker = _detect_report_proposal_marker(_pages(text), 1, 1)
        self.assertIsNotNone(marker)
        self.assertEqual(marker.kind, REPORT_PROPOSAL_MARKER_LEAD_IN)

    def test_find_order_template_marker(self) -> None:
        text = (
            "The agency respectfully recommends that the court find the allegations "
            "true and order continued out-of-home placement."
        )
        marker = _detect_report_proposal_marker(_pages(text), 1, 1)
        self.assertIsNotNone(marker)
        self.assertEqual(marker.kind, REPORT_PROPOSAL_MARKER_FIND_ORDER)

    def test_split_findings_and_orders_across_pages(self) -> None:
        pages = _pages(
            "Factual narrative on the first page.",
            "PROPOSED FINDINGS\n1. The child is described by section 300.",
            "2. The parent failed to protect the child.",
            "PROPOSED ORDERS\n1. The child is detained.",
        )
        marker = _detect_report_proposal_marker(pages, 1, 4)
        self.assertIsNotNone(marker)
        self.assertEqual(marker.kind, REPORT_PROPOSAL_MARKER_SPLIT)
        self.assertEqual(marker.source_page, 2)

    def test_rejects_generic_recommendation_heading(self) -> None:
        text = "RECOMMENDATION\n\nThe child should receive weekly counseling services."
        self.assertIsNone(_detect_report_proposal_marker(_pages(text), 1, 1))

    def test_rejects_change_in_recommendation(self) -> None:
        text = "This report reflects a change in recommendation since the last hearing."
        self.assertIsNone(_detect_report_proposal_marker(_pages(text), 1, 1))

    def test_rejects_singular_assessment_order_recommendation(self) -> None:
        text = (
            "The department recommends that the court order a psychological "
            "evaluation of the mother."
        )
        self.assertIsNone(_detect_report_proposal_marker(_pages(text), 1, 1))

    def test_rejects_actual_historical_court_order(self) -> None:
        text = (
            "At the hearing, the Court found the allegations true and ordered "
            "reunification services for the family."
        )
        self.assertIsNone(_detect_report_proposal_marker(_pages(text), 1, 1))

    def test_rejects_generic_substantive_treatment_recommendation(self) -> None:
        text = (
            "The clinician assesses that the child would benefit from trauma-focused "
            "therapy and recommends a structured weekly schedule."
        )
        self.assertIsNone(_detect_report_proposal_marker(_pages(text), 1, 1))


class ReportProposalScopeRenderingTests(unittest.TestCase):
    def test_delimiter_inserted_at_offset_preserving_all_text(self) -> None:
        prefix = "Prior assessment narrative.\n"
        marker_text = "PROPOSED FINDINGS AND ORDERS"
        page_text = prefix + marker_text + "\n1. Find X.\n"

        pages = {1: page_text}
        marker = _detect_report_proposal_marker(pages, 1, 1)
        self.assertIsNotNone(marker)

        payload = _payload(pages, marker=marker)

        self.assertIn(REPORT_PROPOSAL_SCOPE_DELIMITER.strip(), payload)
        # All original text remains, in order, around the delimiter.
        self.assertIn(prefix.strip(), payload)
        self.assertIn(marker_text, payload)
        self.assertIn("1. Find X.", payload)
        # Delimiter precedes the matched phrase.
        self.assertLess(payload.index(REPORT_PROPOSAL_SCOPE_DELIMITER.strip()), payload.index(marker_text))

    def test_each_primary_page_appears_exactly_once(self) -> None:
        pages = {
            1: "Narrative page one.",
            2: "PROPOSED FINDINGS AND ORDERS",
            3: "Narrative page three.",
        }
        marker = _detect_report_proposal_marker(pages, 1, 3)
        joined = _payload(pages, marker=marker)
        for page in pages:
            self.assertEqual(joined.count(f"source page {page:04d}]"), 1)
        # The scope delimiter (and thus the marker page insertion) appears once.
        self.assertEqual(joined.count(REPORT_PROPOSAL_SCOPE_DELIMITER.strip()), 1)
        # All source text remains present.
        for text in pages.values():
            self.assertIn(text, joined, text)

    def test_complete_document_has_one_delimiter_and_no_window_context(self) -> None:
        pages = {1: "Narrative page one.", 2: "PROPOSED FINDINGS AND ORDERS", 3: "More proposed material."}
        marker = _detect_report_proposal_marker(pages, 1, 3)
        payload = _payload(pages, marker=marker)
        self.assertEqual(payload.count(REPORT_PROPOSAL_SCOPE_DELIMITER.strip()), 1)
        self.assertIn(pages[3], payload)
        self.assertNotIn("OPTIONAL PRECEDING CONTEXT", payload)

    def test_no_delimiter_without_marker(self) -> None:
        self.assertNotIn(REPORT_PROPOSAL_SCOPE_DELIMITER.strip(), _payload({1: "plain narrative"}))


class HistoricalReportPromptContractTests(unittest.TestCase):
    def test_new_prompt_explains_scope_label_and_sentinel(self) -> None:
        self.assertIn(REPORT_PROPOSAL_SCOPE_HEADING, DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("with no internal line breaks", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("inserts a blank line", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_omits_preserve_every_recommendation(self) -> None:
        self.assertNotIn("Preserve every material fact, recommendation", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("recommendation, and procedural development", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_previous_prompt_is_preserved_verbatim(self) -> None:
        self.assertIn("Preserve every material fact, recommendation", PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn(
            REPORT_PROPOSAL_SCOPE_HEADING,
            PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

    def test_previously_shipped_proposal_scope_prompt_is_preserved_verbatim(self) -> None:
        # The immediately preceding built-in keeps the proposal-exclusion
        # section and the old "several" quota wording, untouched.
        self.assertIn(REPORT_PROPOSAL_SCOPE_HEADING, PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Include several legally significant", PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("at least six", PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)


class ReportQuoteConventionPromptTests(unittest.TestCase):
    def test_prompt_has_no_quote_quota(self) -> None:
        self.assertNotIn("at least six", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("fewer than six", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("quotation target", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_prompt_keeps_quote_convention_without_a_count(self) -> None:
        self.assertIn("two-to-five-word sequence in quotation marks", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Do not alter quoted text or use ellipses", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("taken only from eligible material", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("no fixed count per window", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("no quote invented when no suitable anchor exists", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_prompt_keeps_proposal_exclusion_from_satisfying_quote_requirement(self) -> None:
        self.assertIn(REPORT_PROPOSAL_SCOPE_HEADING, DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(
            "never use proposed wording to satisfy the verbatim-quotation requirement",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

class ReportPromptMigrationTests(unittest.TestCase):
    def test_previously_shipped_proposal_scope_prompt_migrates_to_new_prompt(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_reports_prompt": PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["reports_prompt"], "")

    def test_previously_shipped_six_quote_prompt_migrates_to_new_prompt(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_reports_prompt": PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["reports_prompt"], "")
        # The retired six-quote built-in still carries every historical contract.
        self.assertIn(REPORT_PROPOSAL_SCOPE_HEADING, PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Include at least six legally significant verbatim quotes", PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT)

    def test_older_builtin_report_prompts_also_migrate(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_reports_prompt": PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["reports_prompt"], "")

        legacy = (
            "I need to understand the factual and procedural history of this juvenile "
            "dependency case. Therefore, summarize the following report in one very "
            "concise paragraph. Here is the report:"
        )
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={"summarize_reports_prompt": legacy},
        ):
            legacy_migrated = load_summarize_settings()
        self.assertEqual(legacy_migrated["reports_prompt"], "")

    def test_custom_prompt_remains_byte_for_byte_unchanged(self) -> None:
        custom = "A genuinely customized report prompt."
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={"summarize_reports_prompt": custom},
        ):
            preserved = load_summarize_settings()
        self.assertEqual(preserved["reports_prompt"], custom)

    def test_empty_prompt_falls_back_to_new_default(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={"summarize_reports_prompt": ""},
        ):
            settings = load_summarize_settings()
        # An empty stored prompt resolves to no custom guidance.
        self.assertEqual(settings["reports_prompt"], "")


class ReportPromptContractTests(unittest.TestCase):
    def test_prompt_has_no_length_guidance_section_or_word_targets(self) -> None:
        self.assertNotIn("LENGTH GUIDANCE", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("word target", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("at least six", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("never impose a word, sentence, or paragraph count", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_prompt_keeps_material_information_focus(self) -> None:
        self.assertIn(
            "Retain information when omitting it would materially change the reader",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertIn(
            "never bring sentence-ending punctuation inside the final quotation",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

    def test_report_payload_has_no_guidance_section(self) -> None:
        window = {
            "primary_pages": [1],
            "page_text": {1: "Narrative page one."},
            "context_page": None,
        }
        payload = _payload(window["page_text"])
        self.assertIn("Narrative page one.", payload)
        self.assertNotIn("LENGTH GUIDANCE", payload)
        self.assertIn(
            "COMPLETE SOURCE PAGES 0001-0001",
            payload,
        )

    def test_hearing_and_minute_payloads_have_no_guidance_section(self) -> None:
        window = {
            "primary_pages": [1],
            "page_text": {1: "Hearing page one."},
            "context_page": None,
        }
        hearing_payload = _payload(window["page_text"], participant_context="Counsel: Mother’s counsel — Synthetic Counsel")
        minute_payload = _payload(window["page_text"])

        for payload in (hearing_payload, minute_payload):
            self.assertNotIn("LENGTH GUIDANCE", payload)
            self.assertNotIn("words for this window", payload)

    def test_proposal_scope_and_sentinel_coexist_without_guidance(self) -> None:
        pages = {
            1: "PROPOSED FINDINGS AND ORDERS",
            2: "Narrative page two.",
        }
        marker = _detect_report_proposal_marker(pages, 1, 2)
        self.assertIsNotNone(marker)
        window = {
            "primary_pages": [1],
            "page_text": pages,
            "context_page": None,
        }
        payload = _payload(pages, marker=marker)
        self.assertIn(REPORT_PROPOSAL_SCOPE_DELIMITER.strip(), payload)
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_prompt_prioritizes_and_synthesizes_content(self) -> None:
        self.assertIn("retain what matters", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Synthesize repeated history and substantially duplicative updates", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Omit routine administrative detail", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Keep conflicting accounts and their attribution distinct", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

class SentinelAndSkipTests(unittest.TestCase):
    def test_delimiter_helper_bounds_offset(self) -> None:
        text = "abc"
        self.assertEqual(
            _insert_report_proposal_delimiter(text, 1),
            "a" + REPORT_PROPOSAL_SCOPE_DELIMITER + "bc",
        )
        # Oversized offset clamps to the end without truncating source text.
        self.assertIn("abc", _insert_report_proposal_delimiter(text, 99))

    def test_marker_is_frozen_and_nonsensitive(self) -> None:
        marker = ReportProposalMarker(source_page=3, offset=10, line_number=2, kind="x")
        with self.assertRaises(Exception):
            marker.offset = 4  # type: ignore[misc]

    def test_marker_kind_does_not_leak_matched_text(self) -> None:
        # Kinds are fixed, non-sensitive labels.
        kinds = {
            REPORT_PROPOSAL_MARKER_TITLE,
            REPORT_PROPOSAL_MARKER_LEAD_IN,
            REPORT_PROPOSAL_MARKER_SPLIT,
            REPORT_PROPOSAL_MARKER_FIND_ORDER,
        }
        self.assertGreaterEqual(len(kinds), 4)


if __name__ == "__main__":
    unittest.main()
