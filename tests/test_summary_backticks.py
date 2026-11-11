"""Formatting cleanup uses fictional text only; evidence remains source-exact."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from recordprep import summary_agents as sa
from recordprep.summary_editions import (
    build_summary_edition, publish_summary_edition, validate_summary_edition_files,
)


class SummaryBacktickTests(unittest.TestCase):
    def row(self, kind, text="only after repairs"):
        item = {"hearings": "hearing", "reports": "report", "motions": "motion"}[kind] + ":0001"
        quote = item + "/assessment/1"
        return {"item_id": item, "label": "March 3, 2025 - Inspection",
                "categories": [{"id": "assessment", "digest": {
                    "text": "The inspector required `repairs`.",
                    "evidence": [{"quote_id": quote, "text": text}]}}]}, quote

    def test_wrappers_prose_and_fallback_for_all_shared_summary_kinds(self):
        for kind in sa.SUMMARY_KINDS:
            row, quote = self.row(kind)
            original = copy.deepcopy(row)
            placeholder = "{{quote:" + quote + "}}"
            for wrapper in ("`", "``", "```", "\\`", '`"'):
                with self.subTest(kind=kind, wrapper=wrapper):
                    closing = '"`' if wrapper == '`"' else wrapper
                    paragraphs = [f"Reopen {wrapper}{placeholder}{closing}.",
                                  "An `inspection` remains necessary.`"]
                    result = sa.render_section_paragraphs(row, paragraphs)
                    self.assertEqual(result, ["Reopen “only after repairs”.",
                                              "An inspection remains necessary."])
            self.assertEqual(sa.render_section_paragraphs(
                row, sa.fallback_section_paragraphs(row)),
                ["The inspector required repairs."])
            self.assertEqual(row, original)

    def test_cleanup_does_not_rewrite_source_evidence_or_apostrophes(self):
        row, quote = self.row("reports", "the `literal` source's words")
        result = sa.render_section_paragraphs(row, [
            "The inspector's condition: `{{quote:" + quote + "}}`."])
        self.assertEqual(result, ["The inspector's condition: “the `literal` source's words”."])
        self.assertEqual(sa.row_quote_text(row, quote), "the `literal` source's words")

    def test_final_txt_and_edition_have_no_formatting_backticks(self):
        for kind in sa.SUMMARY_KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                row, quote = self.row(kind)
                section = sa.SynthesisSectionCandidate(row["item_id"], [
                    "The inspector recommended reopening `{{quote:" + quote + "}}`."])
                text = sa.render_final_summary(kind, "Fictional Inspection", [row],
                                               [section], {row["item_id"]: (1, None)})
                self.assertNotIn("`", text)
                self.assertIn("“only after repairs”", text)
                path = root / "summaries" / (kind + "_sum_Fictional.txt")
                path.parent.mkdir()
                path.write_text(text)
                edition = build_summary_edition(kind, path, root)
                publish_summary_edition(edition, path)
                self.assertEqual(validate_summary_edition_files(kind, path, root), [])
                sidecar = next((path.parent / "editions").glob("*.pages.json"))
                pages = json.loads(sidecar.read_text())["pages"]
                self.assertTrue(any(p["quotes"] for p in pages))
                for page in pages:
                    self.assertNotIn("`", page["text"])
                    for span in page["quotes"]:
                        self.assertEqual(span["phrase"], "only after repairs")

    def test_report_examples_show_bare_placeholders(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / ".pi/skills/recordprep-synthesize-reports/SKILL.md").read_text()
        self.assertNotIn("`{{quote:", skill)
        self.assertIn("without backticks or Markdown code formatting", skill)
        self.assertIn("Prefer: The inspector recommended reopening {{quote:", skill)
