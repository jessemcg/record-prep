import tempfile
import unittest
from pathlib import Path

from recordprep.ui.main_window import (
    HEARING_SUMMARY_ATTRIBUTION_CONTRACT,
    _cleanup_legacy_generated_artifacts,
    _hearing_participant_context,
    _hearing_summary_validation_issue,
    _render_summary_window_payload,
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
            'title="Case overview"',
            'title="Create RAG index"',
            "def _run_step_eight",
            "def _run_step_preoptimized",
            "def _run_step_nine",
            "def _run_step_eleven",
            "def _run_step_twelve",
        ):
            self.assertNotIn(obsolete, source)
        for dependency in ("chromadb", "langchain", "voyageai", "isaacus"):
            self.assertNotIn(dependency, dependencies.casefold())

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
                target_pages=3,
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
            self.assertIn("CONTEXT ONLY — DO NOT SUMMARIZE", payload)
            self.assertIn("PRIMARY SOURCE PAGES", payload)

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
        self.assertIn("do not list appearances", HEARING_SUMMARY_ATTRIBUTION_CONTRACT)
        self.assertIn(
            "unsworn participant Janette McKinley",
            _hearing_summary_validation_issue(
                "The maternal great-aunt Janette McKinley testified.", hearing
            ) or "",
        )

    def test_summary_validation_rejects_false_testimony_and_bare_counsel_name(self) -> None:
        hearing = {
            "witness_status": "none",
            "witnesses": [],
            "counsel": [
                {
                    "role_id": "mothers_counsel",
                    "role_label": "Mother’s counsel",
                    "name": "Jane Smith",
                    "aliases": ["Ms. Smith"],
                }
            ],
        }

        self.assertIn(
            "witness status is none",
            _hearing_summary_validation_issue("The father testified.", hearing) or "",
        )
        self.assertIn(
            "without the party role",
            _hearing_summary_validation_issue("Jane Smith objected.", hearing) or "",
        )
        self.assertIn(
            "without the party role",
            _hearing_summary_validation_issue("Ms. Smith objected.", hearing) or "",
        )
        self.assertIn(
            "counsel Ms. Smith as testifying",
            _hearing_summary_validation_issue(
                "After testifying before the court, Ms. Smith objected.",
                {**hearing, "witness_status": "verified"},
            ) or "",
        )
        self.assertIsNone(
            _hearing_summary_validation_issue("Mother’s counsel (Jane Smith) objected.", hearing)
        )

    def test_cleanup_removes_only_known_legacy_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts" / "optimized").mkdir(parents=True)
            (root / "artifacts" / "optimized" / "0001.txt").write_text("old")
            (root / "rag" / "vector_database").mkdir(parents=True)
            source = root / "text_pages" / "0001.txt"
            source.parent.mkdir()
            source.write_text("source")
            unrelated = root / "notes.txt"
            unrelated.write_text("keep")

            removed = _cleanup_legacy_generated_artifacts(root)

            self.assertIn("artifacts/optimized", removed)
            self.assertIn("rag", removed)
            self.assertTrue(source.is_file())
            self.assertTrue(unrelated.is_file())


if __name__ == "__main__":
    unittest.main()
