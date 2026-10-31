"""Offline behavioral-contract regression checks against pre-profile intent.

These assert instructions and isolation, not model-output quality. Synthetic inputs
exercise sparse/dense source handling without model calls or real case material.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep import summary_profiles as sp
from recordprep.profile_contract import RETIRED_SUMMARY_RESOURCES, json_bytes, validate_contents
from test_profile_generation import bundled, changed


class SummaryContractTests(unittest.TestCase):
    def prompt(self, kind, phase):
        return " ".join(sp.compile_summary(bundled("general"), kind, phase).prompt.split())

    def test_extraction_preserves_materiality_and_adaptive_detail(self):
        for kind in ("hearings", "reports"):
            prompt = self.prompt(kind, "extract")
            for rule in (
                "Read every supplied page", "omitting it would materially change",
                "not only facts supporting an outcome you already know",
                "never treat silence as proof", "they do not impose equal length",
                "may expand when it holds several genuinely distinct material points",
                "never impose word, sentence, or paragraph counts",
                "differences, chronology, credibility, or legal significance matter",
                "never assume a detail is already covered elsewhere",
                "Write digest prose as paraphrase", "exactly null",
                "Do not stitch fragments, insert ellipses, or silently clean up source wording",
                "never from participant-index context",
            ):
                with self.subTest(kind=kind, rule=rule):
                    self.assertIn(rule, prompt)
        self.assertIn("later synthesis stage determines what is genuinely new across reports",
                      self.prompt("reports", "extract"))
        self.assertIn("no heading-based source cutoff", self.prompt("reports", "extract"))
        self.assertIn("Q/A formatting alone does not establish testimony", self.prompt("hearings", "extract"))

    def test_synthesis_preserves_narrative_quotes_and_continuity(self):
        for kind in ("hearings", "reports"):
            prompt = self.prompt(kind, "synthesize")
            for rule in (
                "one cohesive narrative section", "supporting reasons and evidence",
                "not category order, bullets or category headings",
                "as many paragraphs as the distinct material issues require",
                "never retell the same event under multiple themes",
                "Write chronological, flowing prose", "{{quote:<quote_id>}}",
                "never independent proof of an inferred proposition",
                "never mechanically shorten a stored quotation",
                "correct the affected section and submit it again",
                "compression must not erase conflicting evidence",
                "internal null markers", "all null needs no paragraphs",
                'view="submitted_section"', "rather than relying on the compaction summary",
            ):
                with self.subTest(kind=kind, rule=rule):
                    self.assertIn(rule, prompt)
        reports = self.prompt("reports", "synthesize")
        self.assertIn("new, changed, disputed, or newly significant", reports)
        self.assertIn("Distinguish the date of an event from the later date", reports)
        self.assertIn("Do not reduce the account to changes alone", reports)
        self.assertNotIn("REPORT-TO-REPORT CONTINUITY", self.prompt("hearings", "synthesize"))

    def test_historical_fields_cannot_reach_prompt_or_freshness(self):
        profile = bundled("general")
        from test_practice_profiles import historical_snapshot
        old = historical_snapshot(profile, version=2)
        files = dict(old.files)
        manifest = old.manifest
        for name in RETIRED_SUMMARY_RESOURCES:
            files[manifest["resources"][name]] = b"REMOVED_EXTRA_INSTRUCTION_CANARY"
        files["profile.json"] = json_bytes(manifest)
        historical = validate_contents(tuple(files.items()), "recordprep")
        original = historical.files
        for kind in ("hearings", "reports"):
            for phase in ("extract", "synthesize"):
                current = sp.compile_summary(profile, kind, phase)
                old = sp.compile_summary(historical, kind, phase)
                self.assertEqual(current.prompt, old.prompt)
                self.assertEqual(current.component_sha256, old.component_sha256)
                self.assertNotIn("REMOVED_EXTRA_INSTRUCTION_CANARY", old.prompt)
                self.assertNotIn("Read the complete supplied document", old.prompt if phase == "synthesize" else "")
        self.assertEqual(historical.files, original)

    def test_sparse_and_dense_complete_sources_and_multiparagraph_digests(self):
        # A sparse two-page item and a dense three-page item, both complete.
        for kind, stem in (("hearings", "hearing"), ("reports", "report")):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "artifacts").mkdir()
                (root / "text_pages").mkdir()
                (root / "case_name.txt").write_text("Synthetic")
                pages = {1: "Routine scheduling. disputed payment date", 2: "End of sparse item.",
                         3: "Witness one disputes the date. ", 4: "Witness two gives a different account. ",
                         5: "The decision retains material uncertainty. "}
                for page, text in pages.items():
                    (root / "text_pages" / f"{page:04d}.txt").write_text(text * (60 if page >= 3 else 1))
                boundaries = [{"start_page": 1, "end_page": 2, "date": "2025-01-01", "report_name": "Sparse"},
                              {"start_page": 3, "end_page": 5, "date": "2025-02-01", "report_name": "Dense"}]
                (root / "artifacts" / f"{stem}_boundaries.json").write_text(json.dumps(boundaries))
                config = sa.ExtractionConfig(kind, "", profile=bundled("general"))
                participant_fixture = {"schema_version": 4,
                                       "hearings": boundaries}
                with patch.object(sa, "_participant_index", return_value=participant_fixture):
                    items = sa.build_work_items(root, config)
                self.assertEqual([(item.start_page, item.end_page) for item in items], [(1, 2), (3, 5)])
                for item in items:
                    payload = sa.item_source_payload(item, root / "text_pages", {})
                    for page in range(item.start_page, item.end_page + 1):
                        self.assertIn(pages[page], payload)
                    text = "Material issue and reasons.\n\nDistinct conflicting account and qualification."
                    candidate = {"categories": [{"id": config.definitions[0].identifier,
                                                  "digest": {"text": text, "evidence": []}}]}
                    row = sa.canonicalize_extraction_candidate(candidate, item, root / "text_pages")
                    self.assertEqual(row["categories"][0]["digest"]["text"], " ".join(text.split()))

    def test_new_bundles_have_no_extra_instruction_files(self):
        for name in ("general", "california_dependency"):
            profile = bundled(name)
            self.assertIn(profile.manifest["schema_version"], (6, 7, 8))
            self.assertFalse(RETIRED_SUMMARY_RESOURCES.intersection(profile.manifest["resources"]))
            for filename, _ in profile.files:
                self.assertFalse(filename.endswith(("-extraction.md", "-synthesis.md")))

    def test_only_topic_or_core_changes_stale_the_relevant_summary(self):
        profile = bundled("general")
        original = {phase: sp.compile_summary(profile, "reports", phase) for phase in ("extract", "synthesize")}
        topics = profile.resource("reports")
        topics[0]["guidance"] = "Capture the synthetic disputed payment date and both accounts."
        revised = changed(profile, "reports", topics)
        for phase in original:
            after = sp.compile_summary(revised, "reports", phase)
            self.assertIn(topics[0]["guidance"], after.prompt)
            self.assertNotEqual(original[phase].component_sha256, after.component_sha256)
        with patch.object(sp, "EXTRACTION", sp.EXTRACTION + "\nSynthetic core revision."):
            self.assertNotEqual(original["extract"].component_sha256,
                                sp.compile_summary(profile, "reports", "extract").component_sha256)
            self.assertEqual(original["synthesize"].component_sha256,
                             sp.compile_summary(profile, "reports", "synthesize").component_sha256)


if __name__ == "__main__":
    unittest.main()
