"""Production direct-source regression coverage after end-user sandbox removal."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from recordprep import summary_agents as sa
from recordprep.ui import main_window as ui


class DirectSourcePipelineTests(unittest.TestCase):
    def test_removed_actions_windows_and_payload_paths_stay_absent(self):
        source = Path(ui.__file__).read_text()
        for text in ("app.test-prompts", "TestPromptsWindow", "Prompt-test sandbox", "run_test_", "_build_test_",
                     "_render_summary_window_payload", "_test_summary_payloads", "_summary_window_limits"):
            self.assertNotIn(text, source)
        self.assertFalse(hasattr(sa, "_summary_page_windows"))
        self.assertTrue(callable(ui.RecordPrepWindow._request_plain_text))
        self.assertTrue(callable(ui.RecordPrepWindow._classify_image))
        for step in ("_run_step_create_hearing_summaries", "_run_step_create_report_summaries", "_run_step_create_minute_order_summaries"):
            # Existing GUI adapters still use the guided agentic pipeline.
            if hasattr(ui.RecordPrepWindow, step):
                self.assertTrue(callable(getattr(ui.RecordPrepWindow, step)))

    def test_production_model_loader_does_not_read_inert_sandbox_controls(self):
        config = {"summarize_api_url": "INERT_CANARY", "summarize_api_key": "INERT_CANARY",
                  "summarize_model_id": "INERT_CANARY", "summarize_minutes_window_max_pages": "INERT_CANARY",
                  "summary_extract_pi_model": "synthetic-model", "summary_synthesize_pi_thinking": "low"}
        with patch.object(ui, "_read_config", return_value=config):
            settings = ui.load_summary_model_settings()
        self.assertEqual(settings["extract_model"], "synthetic-model")
        self.assertEqual(settings["synthesize_thinking"], "low")
        self.assertNotIn("INERT_CANARY", str(settings))

    def test_complete_document_payload_covers_every_page_once_without_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for page in range(1, 21):
                (root / f"{page:04d}.txt").write_text(f"Synthetic source page {page}. " + "X" * 1800)
            item = SimpleNamespace(start_page=1, end_page=20, participant_context="Synthetic counsel and witness attribution.", proposal_marker=None)
            payload = sa.item_source_payload(item, root, {page: f"TEST {page}" for page in range(1, 21)})
            for page in range(1, 21):
                self.assertEqual(payload.count(f"source page {page:04d}]"), 1)
            self.assertIn("COMPLETE SOURCE PAGES 0001-0020", payload)
            self.assertIn("PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY", payload)
            self.assertNotIn("LENGTH GUIDANCE", payload)
            self.assertNotIn("OPTIONAL PRECEDING CONTEXT", payload)

    def test_historical_builtin_recognition_and_raw_custom_guidance_remain(self):
        for (kind, phase), values in sa.HISTORICAL_BUILTIN_GUIDANCE.items():
            for value in values:
                self.assertEqual(sa.resolve_phase_guidance(kind, phase, value).custom_guidance, "")
        custom = "  Synthetic personal guidance.\t\n\n"
        self.assertEqual(sa.resolve_phase_guidance("reports", "extract", custom).custom_guidance, custom)

    def test_private_context_keeps_roles_and_testimony_distinct(self):
        hearing = {"witness_status": "verified", "counsel": [{"role_id": "mothers_counsel", "role_label": "Mother’s counsel",
                   "name": "Synthetic Counsel", "aliases": [], "organization": "Synthetic organization", "appearance_status": "remote"}],
                   "participants": [{"role_label": "Relative", "name": "Synthetic Relative", "attendance_status": "present",
                                     "speaking_status": "spoke", "sworn_status": "unsworn"}],
                   "witnesses": [{"name": "Synthetic Witness", "description": "source-supported witness", "examinations": []}]}
        context = ui._hearing_participant_context(hearing)
        self.assertIn("Counsel:", context)
        self.assertIn("Synthetic organization", context)
        self.assertIn("speaking: spoke; sworn: unsworn", context)
        self.assertIn("Synthetic Witness", context)

    def test_cleanup_removes_only_known_legacy_generated_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts/optimized").mkdir(parents=True)
            (root / "artifacts/optimized/0001.txt").write_text("synthetic retired data")
            (root / "summaries").mkdir()
            organized = root / "summaries/hearings_sum_case_organized.txt"
            organized.write_text("synthetic retired summary")
            source = root / "text_pages/0001.txt"
            source.parent.mkdir()
            source.write_text("synthetic source")
            notes = root / "notes.txt"
            notes.write_text("keep")
            removed = ui._cleanup_legacy_generated_artifacts(root)
            self.assertIn("artifacts/optimized", removed)
            self.assertFalse(organized.exists())
            self.assertTrue(source.is_file())
            self.assertTrue(notes.is_file())


if __name__ == "__main__":
    unittest.main()
