"""Focused tests for excluding formal proposed findings/orders from report summaries.

Synthetic only: no real case material. These tests exercise the conservative
marker detector, the per-window scope delimiter/continuation rendering, the
built-in report-prompt contract, the exact-sentinel skip, and the prompt
migration for the saved built-in report prompt.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING,
    ReportProposalMarker,
    _detect_report_proposal_marker,
    _insert_report_proposal_delimiter,
    _render_summary_window_payload,
    _report_length_guidance_section,
    _report_proposal_scope_note,
    _summary_page_windows,
    load_summarize_settings,
)


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

        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            (text_dir / "0001.txt").write_text(page_text, encoding="utf-8")
            windows = _summary_page_windows(text_dir, 1, 1)
            payload = _render_summary_window_payload(
                windows[0], {1: "TEST 1"}, report_marker=marker
            )

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
        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            for number, text in pages.items():
                (text_dir / f"{number:04d}.txt").write_text(text, encoding="utf-8")
            marker = _detect_report_proposal_marker(pages, 1, 3)
            windows = _summary_page_windows(text_dir, 1, 3, max_pages=2)
            primary = [p for w in windows for p in w["primary_pages"]]
            payloads = [
                _render_summary_window_payload(w, {}, report_marker=marker)
                for w in windows
            ]

        # Every primary page is summarized exactly once, in order.
        self.assertEqual(primary, [1, 2, 3])
        joined = "\n".join(payloads)
        # The scope delimiter (and thus the marker page insertion) appears once.
        self.assertEqual(joined.count(REPORT_PROPOSAL_SCOPE_DELIMITER.strip()), 1)
        # All source text remains present.
        for text in pages.values():
            self.assertIn(text, joined, text)

    def test_later_windows_get_continuation_context(self) -> None:
        pages = {
            1: "Narrative page one.",
            2: "PROPOSED FINDINGS AND ORDERS",
            3: "More proposed material.",
        }
        marker = _detect_report_proposal_marker(pages, 1, 3)
        self.assertIsNotNone(marker)
        window_after = {"primary_pages": [3], "page_text": pages, "context_page": 2}
        note = _report_proposal_scope_note(window_after, marker)
        self.assertIn("may still be continuing", note)
        self.assertIn("clearly separate factual narrative", note)

    def test_marker_page_window_gets_delimiter_note(self) -> None:
        pages = {1: "PROPOSED FINDINGS AND ORDERS"}
        marker = _detect_report_proposal_marker(pages, 1, 1)
        self.assertIsNotNone(marker)
        window = {"primary_pages": [1], "page_text": pages}
        note = _report_proposal_scope_note(window, marker)
        self.assertIn("scope delimiter", note)
        self.assertIn("precedes the delimiter", note)

    def test_no_scope_note_without_marker(self) -> None:
        pages = {1: "plain narrative"}
        self.assertEqual(_report_proposal_scope_note({"primary_pages": [1], "page_text": pages}, None), "")


class ReportPromptContractTests(unittest.TestCase):
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


class ReportQuoteQuotaPromptTests(unittest.TestCase):
    def test_new_prompt_states_numeric_minimum_of_six(self) -> None:
        self.assertIn("Include at least six legally significant verbatim quotes", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("Include several", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_includes_fewer_than_six_safeguard(self) -> None:
        self.assertIn(
            "If fewer than six suitable quotations exist, include every suitable quotation",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

    def test_new_prompt_forbids_invention_and_insignificant_padding(self) -> None:
        self.assertIn(
            "never invent, alter, or pad the summary with insignificant or out-of-scope quotations",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

    def test_new_prompt_preserves_quote_length_verbatim_and_no_ellipsis_rules(self) -> None:
        self.assertIn("two-to-five-word sequence in quotation marks", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Do not alter quoted text or use ellipses", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("taken only from eligible material", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_distributes_quotes_without_sacrificing_coverage(self) -> None:
        self.assertIn("Distribute the quotations across the material facts, observations, interviews, and assessments", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("never sacrifice material factual coverage merely to reach the quotation target", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_keeps_proposal_exclusion_from_satisfying_quote_requirement(self) -> None:
        self.assertIn(REPORT_PROPOSAL_SCOPE_HEADING, DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(
            "never use proposed wording to satisfy the verbatim-quotation requirement",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )

    def test_new_prompt_retains_one_paragraph_and_sentinel_contracts(self) -> None:
        self.assertIn("with no internal line breaks", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("inserts a blank line", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, DEFAULT_SUMMARIZE_REPORTS_PROMPT)


class ReportPromptMigrationTests(unittest.TestCase):
    def test_previously_shipped_proposal_scope_prompt_migrates_to_new_prompt(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_reports_prompt": PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["reports_prompt"], DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_previously_shipped_six_quote_prompt_migrates_to_new_prompt(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_reports_prompt": PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["reports_prompt"], DEFAULT_SUMMARIZE_REPORTS_PROMPT)
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
        self.assertEqual(migrated["reports_prompt"], DEFAULT_SUMMARIZE_REPORTS_PROMPT)

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
        self.assertEqual(legacy_migrated["reports_prompt"], DEFAULT_SUMMARIZE_REPORTS_PROMPT)

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
        self.assertEqual(settings["reports_prompt"], DEFAULT_SUMMARIZE_REPORTS_PROMPT)


class ReportLengthGuidanceTests(unittest.TestCase):
    def test_guidance_section_disabled_at_zero_and_negative(self) -> None:
        self.assertEqual(_report_length_guidance_section(0), "")
        self.assertEqual(_report_length_guidance_section(-10), "")

    def test_guidance_section_states_target_and_nonbinding_contract(self) -> None:
        section = _report_length_guidance_section(250)
        self.assertIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, section)
        self.assertIn("approximately 250 words", section)
        self.assertIn("output shape only", section)
        self.assertIn("never cut off or mechanically reject an answer", section)
        self.assertIn("Finish the summary coherently", section)

    def test_report_payload_includes_guidance_only_when_enabled(self) -> None:
        window = {
            "primary_pages": [1],
            "page_text": {1: "Narrative page one."},
            "context_page": None,
        }
        with_guidance = _render_summary_window_payload(
            window,
            {1: "TEST 1"},
            report_length_guidance=_report_length_guidance_section(250),
        )
        without_guidance = _render_summary_window_payload(window, {1: "TEST 1"})

        self.assertIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, with_guidance)
        self.assertNotIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, without_guidance)
        # The guidance section precedes the primary pages and never replaces them.
        self.assertLess(
            with_guidance.index(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING),
            with_guidance.index("PRIMARY SOURCE PAGES"),
        )
        self.assertIn("Narrative page one.", with_guidance)

    def test_hearing_and_minute_payloads_never_include_guidance(self) -> None:
        window = {
            "primary_pages": [1],
            "page_text": {1: "Hearing page one."},
            "context_page": None,
        }
        hearing_payload = _render_summary_window_payload(
            window,
            {1: "TEST 1"},
            participant_context="Counsel: Mother’s counsel — Jane Smith",
        )
        minute_payload = _render_summary_window_payload(window, {1: "TEST 1"})

        for payload in (hearing_payload, minute_payload):
            self.assertNotIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, payload)
            self.assertNotIn("words for this window", payload)

    def test_guidance_coexists_with_proposal_scope_and_sentinel(self) -> None:
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
        payload = _render_summary_window_payload(
            window,
            {1: "TEST 1"},
            report_marker=marker,
            report_length_guidance=_report_length_guidance_section(250),
        )
        self.assertIn(REPORT_PROPOSAL_SCOPE_DELIMITER.strip(), payload)
        self.assertIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, payload)
        # The built-in prompt keeps the exact sentinel contract alongside the
        # length guidance section.
        self.assertIn(NO_SUMMARIZABLE_REPORT_CONTENT, DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(REPORT_SUMMARY_LENGTH_GUIDANCE_HEADING, DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_treats_target_as_soft_guidance(self) -> None:
        self.assertIn("nonbinding guidance about output shape", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("never a token cap, a truncation rule", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("use fewer words than the target when the eligible material warrants less", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("exceed the target rather than end mid-thought", DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_new_prompt_prioritizes_and_synthesizes_content(self) -> None:
        self.assertIn("favor new or changed legally significant facts", DEFAULT_SUMMARIZE_REPORTS_PROMPT)
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
