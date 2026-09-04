import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recordprep import summary_agents as _summary_agents
from recordprep.ui.main_window import (
    DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    DEFAULT_SUMMARIZE_HEARINGS_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_HEARINGS_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_REPORTS_PROMPT,
    DEFAULT_SUMMARIZE_REPORTS_WINDOW_MAX_PAGES,
    DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_CHARS,
    DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_WORDS,
    PREVIOUS_DEFAULT_SUMMARIZE_HEARINGS_PROMPT,
    PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
    SUMMARY_TEST_MODE_CATEGORIES,
    SUMMARY_WINDOW_CATEGORIES,
    _append_summary_paragraph,
    _cleanup_legacy_generated_artifacts,
    _hearing_participant_context,
    _render_summary_window_payload,
    _summary_page_windows,
    _summary_window_limits,
    load_summarize_settings,
    save_summarize_settings,
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
            _summary_agents.DEFAULT_HEARING_EXTRACTION_GUIDANCE,
        )
        self.assertEqual(
            settings["reports_prompt"],
            _summary_agents.DEFAULT_REPORT_EXTRACTION_GUIDANCE,
        )
        # The untouched legacy default pair leaves minute orders at 6000/6.
        self.assertEqual(settings["minutes_target_chars"], "6000")
        self.assertEqual(settings["minutes_max_pages"], "6")

    def test_default_summary_window_settings_are_minute_order_only(self) -> None:
        """PI extraction no longer uses windows; only minute orders keep them."""
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={},
        ):
            settings = load_summarize_settings()

        self.assertNotIn("hearings_target_chars", settings)
        self.assertNotIn("hearings_max_pages", settings)
        self.assertNotIn("reports_target_chars", settings)
        self.assertNotIn("reports_max_pages", settings)
        self.assertEqual(
            settings["minutes_target_chars"],
            str(DEFAULT_SUMMARIZE_MINUTES_WINDOW_TARGET_CHARS),
        )
        self.assertEqual(
            settings["minutes_max_pages"],
            str(DEFAULT_SUMMARIZE_MINUTES_WINDOW_MAX_PAGES),
        )
        self.assertEqual(
            settings["reports_target_words"],
            str(DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_WORDS),
        )

    def test_customized_legacy_pair_migrates_to_minute_orders(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_window_target_chars": "8000",
                "summarize_window_max_pages": "8",
            },
        ):
            settings = load_summarize_settings()

        self.assertNotIn("hearings_target_chars", settings)
        self.assertNotIn("reports_target_chars", settings)
        self.assertEqual(settings["minutes_target_chars"], "8000")
        self.assertEqual(settings["minutes_max_pages"], "8")

    def test_explicit_keys_win_over_legacy_pair(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_window_target_chars": "8000",
                "summarize_window_max_pages": "8",
                "summarize_minutes_window_target_chars": "7000",
                "summarize_minutes_window_max_pages": "4",
            },
        ):
            settings = load_summarize_settings()

        self.assertEqual(settings["minutes_target_chars"], "7000")
        self.assertEqual(settings["minutes_max_pages"], "4")

    def test_invalid_window_values_fall_back_to_defaults(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_window_target_chars": "not-a-number",
                "summarize_window_max_pages": "0",
                "summarize_minutes_window_max_pages": "-3",
            },
        ):
            settings = load_summarize_settings()

        self.assertEqual(settings["minutes_target_chars"], "6000")
        # Numeric values clamp to the minimum like the legacy loader; only
        # non-numeric text falls back to the default.
        self.assertEqual(settings["minutes_max_pages"], "1")

    def test_report_word_target_explicit_values_and_zero_disable(self) -> None:
        cases = (
            ("0", "0"),
            ("300", "300"),
            ("-5", str(DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_WORDS)),
            ("junk", str(DEFAULT_SUMMARIZE_REPORTS_WINDOW_TARGET_WORDS)),
        )
        for raw, expected in cases:
            with patch(
                "recordprep.ui.main_window._read_config",
                return_value={"summarize_reports_window_target_words": raw},
            ):
                settings = load_summarize_settings()
            self.assertEqual(settings["reports_target_words"], expected, raw)

    def test_custom_report_prompt_migrates_word_target_as_disabled(self) -> None:
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={"summarize_reports_prompt": "A genuinely custom prompt."},
        ):
            settings = load_summarize_settings()
        self.assertEqual(settings["reports_prompt"], "A genuinely custom prompt.")
        self.assertEqual(settings["reports_target_words"], "0")

    def test_save_summarize_settings_writes_new_keys_and_removes_legacy(self) -> None:
        captured: dict[str, object] = {}

        def fake_read_config() -> dict[str, object]:
            return {
                "summarize_window_target_chars": "6000",
                "summarize_window_max_pages": "6",
                "summarize_chunk_size": "15",
            }

        def fake_write_config(config: dict[str, object]) -> None:
            captured.update(config)

        with patch(
            "recordprep.ui.main_window._read_config",
            side_effect=fake_read_config,
        ), patch(
            "recordprep.ui.main_window._write_config",
            side_effect=fake_write_config,
        ):
            save_summarize_settings(
                api_url="https://example.test/v1",
                model_id="test-model",
                api_key="key",
                disable_reasoning=False,
                reports_target_words="250",
                minutes_target_chars="6000",
                minutes_max_pages="6",
                hearings_prompt="hearing prompt",
                reports_prompt="report prompt",
                minutes_prompt="minute prompt",
            )

        self.assertEqual(captured["summarize_reports_window_target_words"], "250")
        self.assertEqual(captured["summarize_minutes_window_target_chars"], "6000")
        self.assertEqual(captured["summarize_minutes_window_max_pages"], "6")
        self.assertNotIn("summarize_window_target_chars", captured)
        self.assertNotIn("summarize_window_max_pages", captured)
        self.assertNotIn("summarize_chunk_size", captured)
        # Retired PI extraction window keys are removed on save.
        self.assertNotIn("summarize_hearings_window_target_chars", captured)
        self.assertNotIn("summarize_hearings_window_max_pages", captured)
        self.assertNotIn("summarize_reports_window_target_chars", captured)
        self.assertNotIn("summarize_reports_window_max_pages", captured)

    def test_summary_window_limits_are_per_category_and_normalized(self) -> None:
        settings = {
            "hearings_target_chars": "5000",
            "hearings_max_pages": "5",
            "reports_target_chars": "20000",
            "reports_max_pages": "12",
            "minutes_target_chars": "4000",
            "minutes_max_pages": "4",
        }
        self.assertEqual(_summary_window_limits(settings, "hearings"), (5000, 5))
        # A target above the 12,000-character safety ceiling normalizes to it.
        self.assertEqual(_summary_window_limits(settings, "reports"), (12000, 12))
        self.assertEqual(_summary_window_limits(settings, "minutes"), (4000, 4))
        with self.assertRaises(ValueError):
            _summary_window_limits(settings, "forms")
        self.assertEqual(SUMMARY_WINDOW_CATEGORIES, ("hearings", "reports", "minutes"))

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

    def test_category_limits_produce_different_boundaries_with_exact_coverage(self) -> None:
        page_sizes = (1200,) * 20
        with tempfile.TemporaryDirectory() as temporary:
            text_dir = Path(temporary) / "text_pages"
            text_dir.mkdir()
            for page, size in enumerate(page_sizes, start=1):
                (text_dir / f"{page:04d}.txt").write_text("x" * size, encoding="utf-8")

            settings = {
                "hearings_target_chars": "6000",
                "hearings_max_pages": "6",
                "reports_target_chars": "10000",
                "reports_max_pages": "10",
                "minutes_target_chars": "6000",
                "minutes_max_pages": "6",
            }
            category_windows = {
                category: _summary_page_windows(
                    text_dir,
                    1,
                    20,
                    max_pages=max_pages,
                    target_chars=target_chars,
                    max_chars=12_000,
                )
                for category, (target_chars, max_pages) in (
                    (category, _summary_window_limits(settings, category))
                    for category in SUMMARY_WINDOW_CATEGORIES
                )
            }

        hearing_sizes = [
            len(window["primary_pages"])
            for window in category_windows["hearings"]
        ]
        report_sizes = [
            len(window["primary_pages"])
            for window in category_windows["reports"]
        ]
        minute_sizes = [
            len(window["primary_pages"])
            for window in category_windows["minutes"]
        ]
        # 1200-char pages: hearings/minutes pack five pages per 6,000-character
        # window; reports pack eight pages per 10,000-character window.
        self.assertEqual(hearing_sizes, [5, 5, 5, 5])
        self.assertEqual(minute_sizes, [5, 5, 5, 5])
        self.assertEqual(report_sizes, [8, 8, 4])
        for category, windows in category_windows.items():
            primary = [
                page for window in windows for page in window["primary_pages"]
            ]
            self.assertEqual(primary, list(range(1, 21)), category)
            self.assertEqual(len(primary), len(set(primary)), category)

    def test_prompt_test_mode_maps_each_mode_to_its_category(self) -> None:
        self.assertEqual(
            SUMMARY_TEST_MODE_CATEGORIES,
            {
                "summarize_hearings": "hearings",
                "summarize_reports": "reports",
                "summarize_minutes": "minutes",
            },
        )
        settings = {
            "hearings_target_chars": "5000",
            "hearings_max_pages": "5",
            "reports_target_chars": "10000",
            "reports_max_pages": "10",
            "minutes_target_chars": "4000",
            "minutes_max_pages": "4",
        }
        for mode_id, category in SUMMARY_TEST_MODE_CATEGORIES.items():
            self.assertEqual(
                _summary_window_limits(settings, category),
                {
                    "hearings": (5000, 5),
                    "reports": (10000, 10),
                    "minutes": (4000, 4),
                }[category],
                mode_id,
            )

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
                "summarize_reports_prompt": PREVIOUS_PROPOSAL_SCOPE_SUMMARIZE_REPORTS_PROMPT,
            },
        ):
            migrated = load_summarize_settings()
        self.assertEqual(
            migrated["hearings_prompt"],
            _summary_agents.DEFAULT_HEARING_EXTRACTION_GUIDANCE,
        )
        self.assertEqual(
            migrated["reports_prompt"],
            _summary_agents.DEFAULT_REPORT_EXTRACTION_GUIDANCE,
        )

        custom_prompt = "My genuinely customized hearing prompt."
        with patch(
            "recordprep.ui.main_window._read_config",
            return_value={
                "summarize_hearings_prompt": custom_prompt,
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
