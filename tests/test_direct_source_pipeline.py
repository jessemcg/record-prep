import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep.ui.main_window import (
    DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    _append_summary_paragraph,
    _cleanup_legacy_generated_artifacts,
    _hearing_participant_context,
    _render_summary_window_payload,
    load_summarize_settings,
    _summary_page_windows,
)


class DirectSourcePipelineTests(unittest.TestCase):
    def test_retired_artifact_pipeline_is_not_exposed_or_depended_on(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "recordprep/ui/main_window.py").read_text(encoding="utf-8")
        dependencies = (project / "pyproject.toml").read_text(encoding="utf-8")

        for obsolete in (
            'title="Create raw"',
            'title="Create pre-optimized"',
            'title="Create optimized"',
            'title="Create RAG index"',
            "def _run_step_eight",
            "def _run_step_preoptimized",
            "def _run_step_nine",
            "def _run_step_eleven",
            "def _run_step_twelve",
        ):
            self.assertNotIn(obsolete, source)
        self.assertIn('title="Create case overview"', source)
        self.assertIn('"create_case_overview"', source)
        for dependency in ("chromadb", "langchain", "voyageai", "isaacus"):
            self.assertNotIn(dependency, dependencies.casefold())

    def test_legacy_saved_prompts_migrate_to_integrated_prompts(self) -> None:
        legacy_config = {
            "summarize_chunk_size": "15",
            "summarize_hearings_prompt": (
                "I need to understand the factual and procedural history of this juvenile "
                "dependency case. Therefore, summarize the following court hearing in one "
                "very concise paragraph. Here is the hearing:"
            ),
            "summarize_reports_prompt": (
                "I need to understand the factual and procedural history of this juvenile "
                "dependency case. Therefore, summarize the following report in one very "
                "concise paragraph. Here is the report:"
            ),
        }

        with patch(
            "recordprep.ui.main_window._read_config",
            return_value=legacy_config,
        ):
            settings = load_summarize_settings()

        self.assertEqual(
            settings["hearings_prompt"],
            DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        )
        self.assertEqual(
            settings["reports_prompt"],
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertEqual(settings["target_chars"], "6000")
        self.assertEqual(settings["max_pages"], "6")

    def test_summary_windows_cover_every_primary_page_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            for page in range(1, 8):
                (text_dir / f"{page:04d}.txt").write_text(
                    f"Material detail on page {page}.\n", encoding="utf-8"
                )

            windows = _summary_page_windows(
                text_dir,
                1,
                7,
                max_pages=3,
                target_chars=10_000,
                preferred_breaks={4, 6},
            )

            primary = [page for window in windows for page in window["primary_pages"]]
            self.assertEqual(primary, list(range(1, 8)))
            self.assertEqual(len(primary), len(set(primary)))
            self.assertIsNone(windows[0]["context_page"])
            self.assertEqual(windows[1]["context_page"], windows[0]["primary_end"])
            payload = _render_summary_window_payload(
                windows[1], {page: f"2RT {page}" for page in range(1, 8)}
            )
            self.assertIn(
                "OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE",
                payload,
            )
            self.assertIn("PRIMARY SOURCE PAGES", payload)

    def test_summary_windows_adapt_by_characters_without_splitting_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            page_sizes = (1800, 1900, 2100, 3500, 1200, 1300)
            for page, size in enumerate(page_sizes, start=1):
                (text_dir / f"{page:04d}.txt").write_text("x" * size, encoding="utf-8")

            windows = _summary_page_windows(
                text_dir,
                1,
                len(page_sizes),
                max_pages=4,
                target_chars=6000,
                max_chars=12_000,
            )

            self.assertEqual(
                [window["primary_pages"] for window in windows],
                [[1, 2, 3], [4, 5, 6]],
            )
            self.assertEqual(windows[1]["context_page"], 3)
            primary = [page for window in windows for page in window["primary_pages"]]
            self.assertEqual(primary, list(range(1, 7)))

    def test_private_context_distinguishes_counsel_participants_and_testimony(self) -> None:
        hearing = {
            "witness_status": "verified",
            "counsel": [
                {
                    "role_id": "mothers_counsel",
                    "role_label": "Mother’s counsel",
                    "name": "Jane Smith",
                    "aliases": ["Ms. Smith"],
                    "organization": "JCA",
                    "appearance_status": "remote",
                }
            ],
            "participants": [
                {
                    "role_label": "Maternal great-aunt",
                    "name": "Janette McKinley",
                    "attendance_status": "present",
                    "speaking_status": "spoke",
                    "sworn_status": "unsworn",
                }
            ],
            "witnesses": [
                {
                    "name": "Father",
                    "description": "presumed father",
                    "examinations": [
                        {
                            "type": "direct",
                            "examiner_role_id": "fathers_counsel",
                            "start_citation_label": "2RT 101",
                            "end_citation_label": "2RT 118",
                        }
                    ],
                }
            ],
        }

        context = _hearing_participant_context(hearing)

        self.assertIn("Counsel: Mother’s counsel — Jane Smith", context)
        self.assertIn("organization: JCA", context)
        self.assertIn("personal aliases: Ms. Smith", context)
        self.assertIn("appearance: remote", context)
        self.assertIn("Maternal great-aunt — Janette McKinley", context)
        self.assertIn("speaking: spoke; sworn: unsworn", context)
        self.assertIn("Father (presumed father)", context)
        self.assertIn("direct by Father’s counsel", context)
        self.assertIn("2RT 101–2RT 118", context)
        self.assertIn(
            "PARTICIPANT INDEX CONTEXT — FOR ATTRIBUTION ONLY",
            DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
        )
        self.assertIn("do not reproduce it as an appearance", DEFAULT_SUMMARIZE_HEARINGS_PROMPT)
        self.assertNotIn("MANDATORY ATTRIBUTION CONTRACT", DEFAULT_SUMMARIZE_HEARINGS_PROMPT)
        self.assertNotIn("AUTHORITATIVE HEARING CONTEXT", DEFAULT_SUMMARIZE_HEARINGS_PROMPT)
        self.assertNotIn("Preserve every material event", DEFAULT_SUMMARIZE_HEARINGS_PROMPT)
        self.assertIn(
            "OPTIONAL PRECEDING CONTEXT PAGE — DO NOT SUMMARIZE",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        self.assertIn(
            "PRIMARY SOURCE PAGES — SUMMARIZE ALL MATERIAL DETAILS",
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        )
        for prompt in (
            DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
            DEFAULT_SUMMARIZE_REPORTS_PROMPT,
        ):
            self.assertIn("with no internal line breaks", prompt)
            self.assertIn("inserts a blank line", prompt)

    def test_summary_pipeline_has_no_model_output_content_validator(self) -> None:
        project = Path(__file__).resolve().parents[1]
        source = (project / "recordprep/ui/main_window.py").read_text(encoding="utf-8")

        self.assertNotIn("_hearing_summary_validation_issue", source)
        self.assertNotIn("Summary validation failed", source)
        self.assertNotIn("repair attempts", source)

    def test_summary_paragraphs_have_one_blank_line_between_windows(self) -> None:
        lines = ["January 2, 2025", ""]

        _append_summary_paragraph(lines, "First window.\nStill first window.")
        _append_summary_paragraph(lines, "Second window.")

        self.assertEqual(
            "\n".join(lines),
            "January 2, 2025\n\nFirst window. Still first window.\n\nSecond window.\n",
        )

    def test_previous_integrated_prompt_migrates_but_custom_prompt_is_preserved(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_hearings_prompt": PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
                "summarize_reports_prompt": DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(migrated["hearings_prompt"], DEFAULT_SUMMARIZE_HEARINGS_PROMPT)

        custom_prompt = "My genuinely customized hearing prompt."
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_hearings_prompt": custom_prompt,
                "summarize_reports_prompt": DEFAULT_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            preserved = load_summarize_settings()
        self.assertEqual(preserved["hearings_prompt"], custom_prompt)

    def test_cleanup_removes_only_known_legacy_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts" / "optimized").mkdir(parents=True)
            (root / "artifacts" / "optimized" / "0001.txt").write_text("old")
            (root / "rag" / "vector_database").mkdir(parents=True)
            (root / "summaries").mkdir()
            organized = root / "summaries/hearings_sum_case_organized.txt"
            organized.write_text("retired derived summary")
            source = root / "text_pages" / "0001.txt"
            source.parent.mkdir()
            source.write_text("source")
            unrelated = root / "notes.txt"
            unrelated.write_text("keep")

            removed = _cleanup_legacy_generated_artifacts(root)

            self.assertIn("artifacts/optimized", removed)
            self.assertIn("rag", removed)
            self.assertIn("summaries/hearings_sum_case_organized.txt", removed)
            self.assertFalse(organized.exists())
            self.assertTrue(source.is_file())
            self.assertTrue(unrelated.is_file())


if __name__ == "__main__":
    unittest.main()
