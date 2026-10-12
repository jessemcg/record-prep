"""Complete-report extraction, source verification and frozen prompt recognition.

Synthetic only. Proposal headings do not establish application source cutoffs.
Historical built-ins remain recognition data, not active extraction instructions.
"""
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep.ui.main_window import load_summarize_settings


def payload(pages, *, participant_context=""):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for page, text in pages.items():
            (root / f"{page:04d}.txt").write_text(text)
        item = SimpleNamespace(start_page=min(pages), end_page=max(pages),
                               participant_context=participant_context)
        return sa.item_source_payload(item, root, {page: f"TEST {page}" for page in pages})


class CompleteReportSourceTests(unittest.TestCase):
    def test_formal_heading_variations_never_insert_exclusion(self):
        variants = (
            "PROPOSED FINDINGS AND ORDERS",
            "# RECOMMENDED FINDINGS AND ORDERS",
            "1. PROPOSED FINDINGS / ORDERS.",
            "PROPOSED\nFINDINGS AND ORDERS",
            "The agency recommends that the court make the following findings and orders:",
            "The agency requests that the court find the allegations true and order services.",
        )
        for heading in variants:
            with self.subTest(heading=heading):
                pages = {1: "Prior narrative.", 2: heading + "\nRequested relief.",
                         3: "Later material qualifications."}
                source = payload(pages)
                for page, text in pages.items():
                    self.assertIn(text, source)
                    self.assertEqual(source.count(f"source page {page:04d}]"), 1)
                self.assertNotIn("EXCLUDED FROM REPORT SUMMARY", source)
                self.assertNotIn("OPTIONAL PRECEDING CONTEXT", source)
                self.assertLess(source.index(heading), source.index(pages[3]))

    def test_split_findings_and_orders_keep_later_narrative(self):
        pages = {1: "Initial narrative.", 2: "PROPOSED FINDINGS\nA requested finding.",
                 3: "PROPOSED ORDERS\nA requested order.", 4: "Material subsequent discussion."}
        source = payload(pages)
        for text in pages.values():
            self.assertIn(text, source)
        self.assertNotIn("EXCLUDED", source)

    def test_attribution_context_is_retained(self):
        source = payload({1: "Hearing source."}, participant_context="Synthetic counsel attribution.")
        self.assertIn("PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY", source)
        self.assertIn("Synthetic counsel attribution.", source)
        self.assertIn("Hearing source.", source)

    def test_detector_cutoff_and_work_item_fields_are_removed(self):
        for name in ("_detect_report_proposal_marker", "_insert_report_proposal_delimiter",
                     "ReportProposalMarker", "REPORT_PROPOSAL_SCOPE_DELIMITER"):
            self.assertFalse(hasattr(sa, name), name)
        self.assertNotIn("report_cutoff", inspect.signature(sa.canonicalize_extraction_candidate).parameters)
        self.assertNotIn("proposal_marker", sa.SummaryWorkItem.__dataclass_fields__)
        self.assertNotIn("proposal_page_count", sa.SummaryWorkItem.__dataclass_fields__)

    def test_current_guidance_has_no_exclusion_directive(self):
        guidance = sa.default_guidance("reports", "extract")
        self.assertIn("Read every supplied page", guidance)
        self.assertIn("no heading-based source cutoff", guidance)
        self.assertIn("requested relief wherever they appear", guidance)
        self.assertNotIn("Source after the formal proposal scope delimiter", guidance)
        self.assertNotIn("Never quote excluded proposal material", guidance)
        self.assertNotIn("excluded proposed-findings material", sa.default_guidance("hearings", "extract"))

    def test_old_digest_guidance_is_recognized_without_reattaching_it(self):
        for kind, text in (("reports", sa.PREVIOUS_PROPOSAL_CUTOFF_REPORT_EXTRACTION_GUIDANCE),
                           ("hearings", sa.PREVIOUS_PROPOSAL_CUTOFF_HEARING_EXTRACTION_GUIDANCE)):
            with self.subTest(kind=kind):
                result = sa.resolve_phase_guidance(kind, "extract", text)
                self.assertIn(result.origin, {"default", "migrated"})
                self.assertEqual(result.custom_guidance, "")
                self.assertEqual(result.immutable_guidance, sa.default_guidance(kind, "extract"))

    def test_report_freshness_distinguishes_pre_removal_extraction(self):
        config = sa.ExtractionConfig("reports", "Synthetic guidance.")
        current = config.fingerprint_payload()
        previous = dict(current)
        previous.pop("report_source_contract")
        self.assertNotEqual(sa.sha256_json(previous), config.fingerprint)
        self.assertNotIn("report_source_contract", sa.ExtractionConfig("hearings", "Synthetic guidance.").fingerprint_payload())


class HistoricalReportPromptContractTests(unittest.TestCase):
    """These frozen window-era strings are never current extraction guidance."""
    def test_historical_scope_label_and_sentinel_are_byte_preserved(self):
        self.assertIn(sa.REPORT_PROPOSAL_SCOPE_HEADING, sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(sa.NO_SUMMARIZABLE_REPORT_CONTENT, sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("with no internal line breaks", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("inserts a blank line", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_historical_prompt_omits_preserve_every_recommendation(self):
        self.assertNotIn("Preserve every material fact, recommendation", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("recommendation, and procedural development", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_previous_prompt_is_preserved_verbatim(self):
        self.assertIn("Preserve every material fact, recommendation", sa.PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn(sa.REPORT_PROPOSAL_SCOPE_HEADING, sa.PREVIOUS_DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_prior_proposal_prompt_is_preserved_verbatim(self):
        self.assertIn(sa.REPORT_PROPOSAL_SCOPE_HEADING, sa.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("Include several legally significant", sa.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("at least six", sa.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn(sa.NO_SUMMARIZABLE_REPORT_CONTENT, sa.PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT)

    def test_frozen_prompt_has_no_quote_quota(self):
        for phrase in ("at least six", "fewer than six", "quotation target"):
            self.assertNotIn(phrase, sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_frozen_quote_convention_is_preserved(self):
        for phrase in ("two-to-five-word sequence in quotation marks", "Do not alter quoted text or use ellipses",
                       "taken only from eligible material", "no fixed count per window",
                       "no quote invented when no suitable anchor exists"):
            self.assertIn(phrase, sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_frozen_exclusion_text_is_recognition_data(self):
        self.assertIn("never use proposed wording to satisfy the verbatim-quotation requirement", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        result = sa.resolve_phase_guidance("reports", "extract", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertEqual(result.custom_guidance, "")
        self.assertNotIn(sa.REPORT_PROPOSAL_SCOPE_HEADING, result.immutable_guidance)

    def test_frozen_prompt_has_no_length_targets(self):
        self.assertNotIn("LENGTH GUIDANCE", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertNotIn("word target", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("never impose a word, sentence, or paragraph count", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_frozen_prompt_preserves_material_information_focus(self):
        self.assertIn("Retain information when omitting it would materially change the reader", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)
        self.assertIn("never bring sentence-ending punctuation inside the final quotation", sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)

    def test_frozen_prompt_preserves_salience_and_attribution(self):
        for phrase in ("retain what matters", "Synthesize repeated history and substantially duplicative updates",
                       "Omit routine administrative detail", "Keep conflicting accounts and their attribution distinct"):
            self.assertIn(phrase, sa.DEFAULT_SUMMARIZE_REPORTS_PROMPT)


class ReportPromptRecognitionTests(unittest.TestCase):
    def test_all_former_report_builtins_resolve_without_custom_overrides(self):
        for text in sa.HISTORICAL_BUILTIN_GUIDANCE[("reports", "extract")]:
            with self.subTest(text_hash=sa.sha256_text(text)):
                with patch("recordprep.ui.main_window._read_config", return_value={"summarize_reports_prompt": text}):
                    settings = load_summarize_settings()
                self.assertEqual(settings["reports_prompt"], "")

    def test_six_quote_history_remains_unchanged(self):
        text = sa.PREVIOUS_SIX_QUOTE_SUMMARIZE_REPORTS_PROMPT
        self.assertIn("Include at least six legally significant verbatim quotes", text)
        self.assertIn(sa.REPORT_PROPOSAL_SCOPE_HEADING, text)
        self.assertIn(sa.NO_SUMMARIZABLE_REPORT_CONTENT, text)

    def test_custom_prompt_remains_byte_for_byte_unchanged(self):
        custom = "\n A genuinely customized report prompt. \n"
        with patch("recordprep.ui.main_window._read_config", return_value={"summarize_reports_prompt": custom}):
            self.assertEqual(load_summarize_settings()["reports_prompt"], custom)

    def test_empty_prompt_has_no_custom_override(self):
        with patch("recordprep.ui.main_window._read_config", return_value={"summarize_reports_prompt": ""}):
            self.assertEqual(load_summarize_settings()["reports_prompt"], "")


if __name__ == "__main__":
    unittest.main()
