"""Production direct-source regression coverage after end-user sandbox removal."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from recordprep import config, documents, manifest, prompts, summaries
from recordprep import summary_agents as sa
from recordprep.ui import main_window as ui


class DirectSourcePipelineTests(unittest.TestCase):
    def test_removed_actions_windows_and_payload_paths_stay_absent(self):
        source = Path(ui.__file__).read_text()
        for text in ("app.test-prompts", "TestPromptsWindow", "Prompt-test sandbox", "run_test_", "_build_test_",
                     "_render_summary_window_payload", "_test_summary_payloads", "_summary_window_limits"):
            self.assertNotIn(text, source)
        self.assertFalse(hasattr(sa, "_summary_page_windows"))
        self.assertFalse(hasattr(ui.RecordPrepWindow, "_request_plain_text"))
        self.assertTrue(callable(ui.RecordPrepWindow._classify_image))

    def test_retired_execution_paths_are_absent(self):
        for name in ("_extract_embedding_vectors", "_infer_case_name_from_text",
                     "_limit_case_name_words", "_looks_like_case_name"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ui, name))
        for name in ("_build_summarize_request_settings", "_classify_text",
                     "_stream_text_with_retries", "_read_sse_text_response",
                     "_extract_stream_text_parts", "_coerce_stream_text"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ui.RecordPrepWindow, name))

    def test_summary_handlers_dispatch_to_existing_pi_stages(self):
        for kind, step, row in (
            ("hearing", "create_hearing_summaries", "step_hearing_summaries_row"),
            ("report", "create_report_summaries", "step_report_summaries_row"),
            ("minute_order", "create_minute_order_summaries", "step_minute_order_summaries_row"),
        ):
            with self.subTest(kind=kind):
                handler = getattr(ui.RecordPrepWindow, f"_run_step_{step}")
                sentinel = object()
                for result in (True, False, None):
                    dispatch = Mock(return_value=result)
                    window = SimpleNamespace(_run_pi_skill_step=dispatch, **{row: sentinel})
                    self.assertIs(handler(window), result)
                    dispatch.assert_called_once_with(step, sentinel)

    def test_supported_compatibility_import_surfaces_remain_available(self):
        # Historical settings APIs are supported even though direct requests retired.
        for category in ("advanced_classify", "case_name", "classifier", "classify_dates",
                         "classify_names", "local_ocr", "summarize"):
            for action in ("load", "save"):
                name = f"{action}_{category}_settings"
                with self.subTest(name=name):
                    self.assertIs(getattr(config, name), getattr(ui, name))
        for module, names in (
            (documents, ("_merge_pdfs", "_generate_text_files", "_generate_image_page_files")),
            (manifest, ("_read_manifest", "_write_manifest")),
            (summaries, ("_summary_output_paths", "_minutes_summary_output_path")),
        ):
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertIs(getattr(module, name), getattr(ui, name))
        for name in ("DEFAULT_CASE_NAME_PROMPT", "DEFAULT_SUMMARIZE_HEARINGS_PROMPT",
                     "DEFAULT_SUMMARIZE_REPORTS_PROMPT", "DEFAULT_SUMMARIZE_MINUTES_PROMPT"):
            self.assertEqual(getattr(prompts, name), getattr(ui, name))
        for name in ("legacy_summary_digest_jsonl_path", "migrate_legacy_digest_jsonl",
                     "load_digest_markdown", "cleanup_legacy_digest_jsonl"):
            self.assertIs(getattr(summaries, name), getattr(sa, name))

    def test_production_model_loader_does_not_read_inert_sandbox_controls(self):
        config = {"summarize_api_url": "INERT_CANARY", "summarize_api_key": "INERT_CANARY",
                  "summarize_model_id": "INERT_CANARY", "summarize_minutes_window_max_pages": "INERT_CANARY",
                  "summary_extract_pi_model": "synthetic-model", "summary_synthesize_pi_thinking": "low"}
        with patch.object(ui, "_read_config", return_value=config):
            settings = ui.load_summarize_settings()
        self.assertEqual(settings["extract_model"], "")
        self.assertEqual(settings["synthesize_thinking"], "")
        self.assertFalse(hasattr(ui, "load_summary_model_settings"))
        self.assertFalse(hasattr(ui.SettingsWindow, "_build_summarize_prompt_page"))

    def test_complete_document_payload_covers_every_page_once_without_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for page in range(1, 21):
                (root / f"{page:04d}.txt").write_text(f"Synthetic source page {page}. " + "X" * 1800)
            item = SimpleNamespace(start_page=1, end_page=20, participant_context="Synthetic counsel and witness attribution.")
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
